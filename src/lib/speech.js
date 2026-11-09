// Text-to-speech with the right voice. Setting utterance.lang alone is not enough: without a voice the browser
// often reads Spanish or Ukrainian with an English voice (robotic and wrong), so we pick an installed voice for
// the language, best quality first, and say clearly when none exists.
import { authFetch } from './api';

const PREF_KEY = 'andedu_voice_by_lang';
const QUALITY = [/premium/i, /enhanced/i, /neural|natural/i, /google/i, /siri/i, /microsoft .* online/i];
// novelty voices on macOS that read every language badly
const NOVELTY = /albert|bad news|bahh|bells|boing|bubbles|cellos|good news|jester|organ|superstar|trinoids|whisper|wobble|zarvox|fred|junior|ralph|kathy|grandma|grandpa|eddy|flo|reed|rocko|sandy|shelley/i;

export const LANGUAGES = [
  ['uk', 'Ukrainian'], ['es', 'Spanish'], ['fr', 'French'], ['de', 'German'], ['it', 'Italian'], ['pt', 'Portuguese'],
  ['pl', 'Polish'], ['ru', 'Russian'], ['zh', 'Chinese'], ['ja', 'Japanese'], ['ko', 'Korean'], ['ar', 'Arabic'],
  ['hi', 'Hindi'], ['tr', 'Turkish'], ['nl', 'Dutch'], ['sv', 'Swedish'], ['el', 'Greek'], ['he', 'Hebrew'], ['en', 'English'],
];
export const languageName = (code) => (LANGUAGES.find(([c]) => c === String(code).split('-')[0]) || [code, code])[1];

let voicesReady = null;
/** Voices load asynchronously in Chrome/Brave; resolve once they are there (or after a short wait). */
export function loadVoices() {
  if (!window.speechSynthesis) return Promise.resolve([]);
  if (!voicesReady) {
    voicesReady = new Promise((resolve) => {
      const have = window.speechSynthesis.getVoices();
      if (have.length) return resolve(have);
      const done = () => resolve(window.speechSynthesis.getVoices());
      window.speechSynthesis.addEventListener('voiceschanged', done, { once: true });
      setTimeout(done, 1500);
    });
  }
  return voicesReady.then((v) => (v.length ? v : window.speechSynthesis.getVoices()));
}

const base = (lang) => String(lang || 'en').toLowerCase().split(/[-_]/)[0];

export async function voicesFor(lang) {
  const b = base(lang);
  const rank = (v) => {
    const q = QUALITY.findIndex((r) => r.test(v.name));
    return (q < 0 ? 10 : q) + (NOVELTY.test(v.name) ? 50 : 0);
  };
  return (await loadVoices())
    .filter((v) => base(v.lang) === b)
    .sort((a, c) => rank(a) - rank(c) || a.name.localeCompare(c.name));
}

function prefs() { try { return JSON.parse(localStorage.getItem(PREF_KEY) || '{}'); } catch { return {}; } }
export function setPreferredVoice(lang, name) {
  try { localStorage.setItem(PREF_KEY, JSON.stringify({ ...prefs(), [base(lang)]: name })); } catch { /* private mode */ }
}

export async function pickVoice(lang) {
  const list = await voicesFor(lang);
  const want = prefs()[base(lang)];
  return list.find((v) => v.name === want) || list[0] || null;
}

/** What should be read aloud: no IPA (/.../ or [...]), Markdown, math or English glosses in parentheses. */
export function speakable(text) {
  return String(text || '')
    .replace(/\$[^$]*\$/g, ' ')
    .replace(/\/[^/\n]{1,60}\//g, ' ')
    .replace(/\[[^\]\n]{1,60}\]/g, ' ')
    .replace(/\([^)]*\)/g, ' ')
    .replace(/[*_`#>|]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Speaks text in a language with an installed voice of that language.
 * Returns {ok: true, voice} or {ok: false, reason: 'unsupported' | 'no-voice' | 'stale', language}. onend runs when it
 * finishes, onerror when the utterance fails or is cut off. isStale() is checked once the voice is picked: when it
 * returns true nothing is spoken (and the current utterance is not cancelled), for callers whose line went out of date.
 */
export async function speak(text, lang = 'en', { rate = 0.9, pitch = 1, onend, onerror, isStale } = {}) {
  if (!window.speechSynthesis) return { ok: false, reason: 'unsupported' };
  const voice = await pickVoice(lang);
  if (isStale?.()) return { ok: false, reason: 'stale' };
  if (!voice) return { ok: false, reason: 'no-voice', language: languageName(lang) };
  const u = new SpeechSynthesisUtterance(speakable(text));
  u.voice = voice;
  u.lang = voice.lang;
  u.rate = rate;
  u.pitch = pitch;
  if (onend) u.onend = onend;
  if (onerror) u.onerror = onerror;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
  return { ok: true, voice: voice.name };
}

// ---- recorded voice (POST /api/language/tts: ElevenLabs clips cached on the server, when the server turns it on).
// Each text is asked for once per page load (memo); slow playback is the same clip at a lower playbackRate. When the
// server says "browser" (off, capped, or an upstream error) the browser's own voice reads it instead.
const MEMO_MAX = 60;
const audioMemo = new Map();   // "lang|text" -> Promise<blob URL | null>
let ttsOff = false;            // the server has no recorded voice: stop asking for this page load
const pausedUntil = {};       // budget ("language" | "explain") -> ms timestamp: capped or rate-limited, don't ask until then
const CAP_PAUSE_MS = 10 * 60 * 1000;
let current = null;            // the <audio> playing now
let playSeq = 0;               // bumps on every play/stop, so a slow fetch can't start after a newer request

/**
 * A blob URL for the server's recorded clip of text, or null (the browser voice should read it). purpose 'explain'
 * spends the lesson walkthroughs' own daily budget on the server instead of the Languages one.
 */
export function clipUrl(text, lang, { purpose } = {}) {
  const say = speakable(text);
  // a letter or two (script drills) stays with the browser voice: not worth a clip from the daily allowance
  if (ttsOff || !say || say.length < 3 || say.length > 300) return Promise.resolve(null);
  const key = `${base(lang)}|${say}`;
  const budget = purpose || 'language';
  if (!audioMemo.has(key) && Date.now() < (pausedUntil[budget] || 0)) return Promise.resolve(null);
  if (!audioMemo.has(key)) {
    let keep = true;  // remember a null only when asking again can't help (off, or a language without a voice)
    const p = (async () => {
      const res = await authFetch('/api/language/tts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: say, lang: base(lang), ...(purpose ? { purpose } : {}) }) });
      if (!res.ok) { keep = res.status === 400; return null; }
      const data = await res.json();
      if (!data?.url) {
        if (data?.reason === 'disabled') ttsOff = true;
        else {
          keep = false;
          if (data?.reason === 'daily_cap' || data?.reason === 'rate_limited') pausedUntil[budget] = Date.now() + CAP_PAUSE_MS;
        }
        return null;
      }
      const audio = await authFetch(data.url);  // with the session token: a plain <audio src> can't send it
      if (!audio.ok) { keep = false; return null; }
      return URL.createObjectURL(await audio.blob());
    })().catch(() => { keep = false; return null; });
    audioMemo.set(key, p);
    p.then((url) => { if (!url && !keep) audioMemo.delete(key); });
    if (audioMemo.size > MEMO_MAX) {
      const [oldKey, old] = audioMemo.entries().next().value;
      audioMemo.delete(oldKey);
      old.then((u) => u && setTimeout(() => URL.revokeObjectURL(u), 30000));
    }
  }
  return audioMemo.get(key);
}

/** Starts fetching the clip for text in the background (the next exercise), so it plays without a wait. */
export function prefetchAudio(text, lang) {
  if (text && lang) clipUrl(text, lang);
}

/** Stops the recorded voice and the browser voice. */
export function stopSpeech() {
  playSeq++;
  if (current) { current.pause(); current = null; }
  window.speechSynthesis?.cancel();
}

/** True while a clip or the browser voice is still speaking. */
export function isSpeaking() {
  const s = window.speechSynthesis;
  return Boolean((current && !current.paused && !current.ended) || (s && (s.speaking || s.pending)));
}

/**
 * Reads text aloud: the server's recorded voice when it has one, otherwise speak(). slow plays at 0.7x (pitch kept).
 * Resolves like speak(), plus source ('audio' | 'browser') and, for a clip, done (resolves when it stops).
 */
export async function speakAudio(text, lang = 'en', { slow = false, rate, pitch } = {}) {
  stopSpeech();
  const seq = ++playSeq;
  const url = await clipUrl(text, lang);
  if (seq !== playSeq) return { ok: true, source: 'cancelled', done: Promise.resolve() };
  if (url) {
    const a = new Audio(url);
    a.playbackRate = slow ? 0.7 : 1;
    a.preservesPitch = true;
    a.mozPreservesPitch = true;
    a.webkitPreservesPitch = true;
    const done = new Promise((resolve) => { a.onended = resolve; a.onpause = resolve; a.onerror = resolve; });
    current = a;
    try {
      await a.play();
      return { ok: true, source: 'audio', done };
    } catch {
      if (current === a) current = null;  // autoplay blocked or a broken clip: the browser voice tries instead
    }
  }
  const r = await speak(text, lang, { rate: rate ?? (slow ? 0.55 : 0.9), ...(pitch !== undefined ? { pitch } : {}) });
  return { ...r, source: 'browser' };
}

export function noVoiceHelp(language) {
  const mac = /Mac/.test(navigator.platform || navigator.userAgent);
  return mac
    ? `No ${language} voice is installed. On a Mac: System Settings → Accessibility → Spoken Content → System voice → Manage Voices, add a ${language} voice (the "Enhanced" ones sound best), then reload.`
    : `No ${language} voice is installed. Add one in your system's speech or language settings (Windows: Settings → Time & language → Speech), then reload.`;
}

// ---- speech recognition (Speak exercises). Chrome and Edge send the audio to their maker's servers to turn it
// into text, Safari uses Apple's; Firefox has none. Start it only from a click, and say so next to the button.
const REGION = { en: 'en-US', es: 'es-ES', fr: 'fr-FR', de: 'de-DE', it: 'it-IT', pt: 'pt-BR', uk: 'uk-UA', ru: 'ru-RU', pl: 'pl-PL',
  zh: 'zh-CN', ja: 'ja-JP', ko: 'ko-KR', ar: 'ar-SA', hi: 'hi-IN', tr: 'tr-TR', nl: 'nl-NL', sv: 'sv-SE', el: 'el-GR', he: 'he-IL' };
const Recognition = () => window.SpeechRecognition || window.webkitSpeechRecognition || null;

export const canRecognize = () => !!Recognition();
export const RECOGNITION_NOTICE = 'Speech recognition runs in your browser, which may send the recording to its maker (Google for Chrome, Apple for Safari) to turn it into text.';

/**
 * Listens once and resolves {ok: true, transcripts: [best, ...alternatives]} or {ok: false, reason}.
 * Returns null when the browser cannot recognize speech. Call stop() on the returned handle to finish early.
 */
export function recognize(lang, { timeoutMs = 8000 } = {}) {
  const R = Recognition();
  if (!R) return null;
  const rec = new R();
  rec.lang = String(lang).includes('-') ? lang : (REGION[base(lang)] || lang);
  rec.interimResults = false;
  rec.maxAlternatives = 4;
  const result = new Promise((resolve) => {
    let done = false;
    const finish = (v) => { if (!done) { done = true; clearTimeout(timer); resolve(v); } };
    const timer = setTimeout(() => { try { rec.stop(); } catch { /* already stopped */ } finish({ ok: false, reason: 'timeout' }); }, timeoutMs);
    rec.onresult = (e) => finish({ ok: true, transcripts: Array.from(e.results[0] || []).map((a) => a.transcript) });
    rec.onerror = (e) => finish({ ok: false, reason: e.error || 'error' });
    rec.onend = () => finish({ ok: false, reason: 'no-speech' });
  });
  try { rec.start(); } catch { return { result: Promise.resolve({ ok: false, reason: 'busy' }), stop() {} }; }
  return { result, stop: () => { try { rec.stop(); } catch { /* already stopped */ } } };
}
