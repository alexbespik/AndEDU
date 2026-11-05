// Text-to-speech with the right voice. Setting utterance.lang alone is not enough: without a voice the browser
// often reads Spanish or Ukrainian with an English voice (robotic and wrong), so we pick an installed voice for
// the language, best quality first, and say clearly when none exists.

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
 * Returns {ok: true, voice} or {ok: false, reason: 'unsupported' | 'no-voice', language}.
 */
export async function speak(text, lang = 'en', { rate = 0.9, pitch = 1 } = {}) {
  if (!window.speechSynthesis) return { ok: false, reason: 'unsupported' };
  const voice = await pickVoice(lang);
  if (!voice) return { ok: false, reason: 'no-voice', language: languageName(lang) };
  const u = new SpeechSynthesisUtterance(speakable(text));
  u.voice = voice;
  u.lang = voice.lang;
  u.rate = rate;
  u.pitch = pitch;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
  return { ok: true, voice: voice.name };
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
