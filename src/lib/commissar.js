// Commissar mode: an optional stern-coach skin and voice. State lives in localStorage. The voice is only ever a local
// voice pack (recorded clips from content/voice_packs/, voice_packs.py) for the events in commissarLines.json: no
// user content, lessons or answers, and no browser text-to-speech (an event without a clip stays silent).
import { useSyncExternalStore } from 'react';
import { commissarLines } from './commissarLines';
import { api, authFetch } from './api';

const KEY_ON = 'andedu_commissar';
const KEY_MUTE = 'andedu_commissar_mute';
const KEY_VOICE = 'andedu_commissar_voice';  // 'auto' (the premade pack) | a pack id
const PREMADE = 'commissar';
const KEY_ROUGH = 'andedu_commissar_rough';  // 0 (clean) .. 3 (gravel); recorded clips go through Web Audio
const ROUGH_DEFAULT = 2;
// rate < 1 with pitch preservation off lowers the voice; drive is the soft-clip amount; low/bark are dB boosts
const ROUGH = {
  1: { rate: 0.93, drive: 4, low: 4, bark: 2 },
  2: { rate: 0.87, drive: 12, low: 7, bark: 4 },
  3: { rate: 0.8, drive: 30, low: 9, bark: 6 },
};
const THROTTLE_MS = 8000;
// never throttled: the mode switching, every quiz answer (each gets its line; a new one cuts the last), and a quiz's
// start, result and walk-out. The same event twice within DEDUPE_MS is one line (React StrictMode mounts effects twice).
const ALWAYS = new Set(['on', 'off', 'quizPass', 'quizFail', 'quizStart', 'quizWin', 'quizLose', 'desert']);
const DEDUPE_MS = 1500;
let lastEvent = { name: '', at: 0 };

const read = (k) => { try { return localStorage.getItem(k) === '1'; } catch { return false; } };
const write = (k, v) => { try { if (v) localStorage.setItem(k, '1'); else localStorage.removeItem(k); } catch { /* storage blocked */ } };

const readVoice = () => {
  try { const v = localStorage.getItem(KEY_VOICE); return v && v !== 'browser' ? v : 'auto'; } catch { return 'auto'; }  // 'browser' was the old robot voice
};
const readRough = () => {
  try {
    const v = localStorage.getItem(KEY_ROUGH);
    return v != null && /^[0-3]$/.test(v) ? Number(v) : ROUGH_DEFAULT;
  } catch { return ROUGH_DEFAULT; }
};

let state = { enabled: read(KEY_ON), muted: read(KEY_MUTE), voice: readVoice(), rough: readRough(), packs: [] };
const listeners = new Set();
let lastSpoken = 0;

let clip = null;  // the <audio> playing a pack clip
let seq = 0;       // bumped by every new line and every stop: a clip that finishes loading late checks it
const stopSpeech = () => {
  seq += 1;
  try { clip?.pause(); } catch { /* ignore */ }
};
const emit = () => listeners.forEach((fn) => fn(state));

export const getState = () => state;
export function subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); }

/** The only place that sets or removes the skin attribute. */
export function applySkin() {
  if (typeof document === 'undefined') return;
  if (state.enabled) document.documentElement.dataset.skin = 'commissar';
  else delete document.documentElement.dataset.skin;
}

// ---- voice packs (local only; GET /api/voice-packs answers 404 with server accounts, then the mode is silent)
let packsLoaded = false;
const blobUrls = new Map();  // clip path -> object URL (the clip route needs the session token, which <audio> can't send)

export function loadPacks(force = false) {
  if (packsLoaded && !force) return Promise.resolve(state.packs);
  return api('/api/voice-packs')
    .then((r) => { packsLoaded = true; update({ packs: Array.isArray(r?.packs) ? r.packs : [] }); return state.packs; })
    .catch(() => { update({ packs: [] }); return []; });  // e.g. not signed in yet: the next say() tries again
}

/** The voice pack the current setting uses (null: none on this computer, so the mode is silent). */
export function activePack(st = state) {
  const id = st.voice === 'auto' ? PREMADE : st.voice;
  return st.packs.find((p) => p.id === id) || null;
}

/** The pack the current voice setting plays, if it has clips for `event`. */
function packFor(event) {
  const pack = activePack();
  return pack?.events?.[event]?.length ? pack : null;
}

// ---- the rough voice: slowed (so deeper), soft-clipped, bass and 'bark' boosted, compressed like a shout
let audioCtx = null;
const curves = new Map();
function clipCurve(k) {
  if (!curves.has(k)) {
    const n = 2048, c = new Float32Array(n);
    for (let i = 0; i < n; i += 1) { const x = (i * 2) / n - 1; c[i] = ((1 + k) * x) / (1 + k * Math.abs(x)); }
    curves.set(k, c);
  }
  return curves.get(k);
}

/** Routes a clip through the rough chain for the current level; leaves it clean when Web Audio is missing. */
function roughen(audio) {
  const p = ROUGH[state.rough];
  if (!p) return;
  audio.preservesPitch = false; audio.mozPreservesPitch = false; audio.webkitPreservesPitch = false;
  audio.playbackRate = p.rate;
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    audioCtx = audioCtx || new Ctx();
    if (audioCtx.state === 'suspended') audioCtx.resume().catch(() => {});
    const node = (make) => make(audioCtx);
    const src = audioCtx.createMediaElementSource(audio);
    const shaper = node((c) => c.createWaveShaper()); shaper.curve = clipCurve(p.drive); shaper.oversample = '4x';
    const low = node((c) => c.createBiquadFilter()); low.type = 'lowshelf'; low.frequency.value = 180; low.gain.value = p.low;
    const bark = node((c) => c.createBiquadFilter()); bark.type = 'peaking'; bark.frequency.value = 2200; bark.Q.value = 1.1; bark.gain.value = p.bark;
    const top = node((c) => c.createBiquadFilter()); top.type = 'lowpass'; top.frequency.value = 6500;
    const comp = audioCtx.createDynamicsCompressor(); comp.threshold.value = -26; comp.ratio.value = 6; comp.attack.value = 0.003; comp.release.value = 0.15;
    const out = audioCtx.createGain(); out.gain.value = 0.8;  // the clipper adds level: keep it near the clean volume
    src.connect(shaper).connect(low).connect(bark).connect(top).connect(comp).connect(out).connect(audioCtx.destination);
  } catch { /* the clip plays clean (only slowed) */ }
}

function playClip(pack, file) {
  stopSpeech();
  const mine = seq;
  const path = `/api/voice-packs/${encodeURIComponent(pack.id)}/${encodeURIComponent(file)}`;
  const cached = blobUrls.get(path);
  const url = cached ? Promise.resolve(cached) : authFetch(path).then((r) => {
    if (!r.ok) throw new Error(`clip ${r.status}`);
    return r.blob();
  }).then((b) => { const u = URL.createObjectURL(b); blobUrls.set(path, u); return u; });
  url.then((u) => {
    // say() already checked on/muted (the 'off' line plays after the mode turns off); stale requests stay silent
    if (mine !== seq || (typeof document !== 'undefined' && document.hidden)) return;
    clip = new Audio(u);
    if (pack.id === PREMADE) roughen(clip);  // the rough voice is the Commissar's; other packs play as recorded
    clip.play().catch(() => { /* autoplay blocked until the page gets a click or key press */ });
  }).catch(() => { /* a missing clip stays silent; the next event tries again */ });
}

/** Plays one recorded clip for `event`; returns true when it did (false: off, muted, no clip, or throttled). */
export function say(event) {
  if (!state.enabled || state.muted) return false;
  if (!packsLoaded) loadPacks();  // packs that failed to load (e.g. before sign-in) are retried; this event stays silent
  const lines = commissarLines[event];
  if (!lines?.length) return false;
  const now = Date.now();
  if (!ALWAYS.has(event) && now - lastSpoken < THROTTLE_MS) return false;
  if (lastEvent.name === event && now - lastEvent.at < DEDUPE_MS) return false;
  // leaving one quiz straight into the next: let the walk-out line play instead of cutting it with the next start
  if (event === 'quizStart' && lastEvent.name === 'desert' && now - lastEvent.at < DEDUPE_MS) return false;
  lastEvent = { name: event, at: now };
  const pack = packFor(event);
  if (!pack) return false;
  lastSpoken = now;
  const files = pack.events[event];
  playClip(pack, files[Math.floor(Math.random() * files.length)]);
  return true;
}

function update(next) {
  state = { ...state, ...next };
  write(KEY_ON, state.enabled);
  write(KEY_MUTE, state.muted);
  try { localStorage.setItem(KEY_VOICE, state.voice); localStorage.setItem(KEY_ROUGH, String(state.rough)); } catch { /* storage blocked */ }
  applySkin();
  emit();
}

export function setEnabled(on) {
  const was = state.enabled;
  const value = Boolean(on);
  if (!value && was) { say('off'); update({ enabled: false }); return; } // 'off' speaks while still enabled; kept, not cancelled
  update({ enabled: value });
  if (value && !was) loadPacks().then(() => say('on'));
}

/** How rough the voice sounds: 0 clean .. 3 gravel. Returns false for anything else. */
export function setRough(level) {
  const n = Number(level);
  if (!Number.isInteger(n) || n < 0 || n > 3) return false;
  update({ rough: n });
  lastEvent = { name: '', at: 0 };  // so the console's sample line plays at the new level
  return true;
}

/** 'auto' | a pack id from loadPacks(). Returns false for an unknown pack. */
export function setVoice(v) {
  const id = String(v || '').trim().toLowerCase();
  if (id !== 'auto' && !state.packs.some((p) => p.id === id)) return false;
  stopSpeech();
  lastEvent = { name: '', at: 0 };  // a new voice may confirm itself at once
  update({ voice: id });
  return true;
}

export function setMuted(m) {
  update({ muted: Boolean(m) });
  if (state.muted) stopSpeech();
}

export function toggle() { setEnabled(!state.enabled); return state.enabled; }

// Summon words: `yarrik` is the Commissar (the premade pack). Any other local pack may name its own word in its
// manifest (`"summon": "<word>"`, voice_packs.py), so a pack brings its trigger without code changes.
function summonTarget(word) {
  if (word === 'yarrik') return { voice: 'auto', same: ['auto', PREMADE], name: 'commissar' };
  const p = state.packs.find((x) => x.summon === word);
  return p ? { voice: p.id, same: [p.id], name: p.name.toLowerCase() } : null;
}

/** A summon word: turns the mode on in that voice, switches to that voice when another one is on, or stands the
 * mode down when that voice is already on. Resolves to the console line to show ('unknown command' for no match). */
export async function summon(word) {
  const w = String(word || '').trim().toLowerCase();
  let s = summonTarget(w);
  if (s && state.enabled && s.same.includes(state.voice)) { setEnabled(false); return `${s.name}: off`; }
  await loadPacks(true);
  s = summonTarget(w);
  if (!s) return 'unknown command';
  if (!state.packs.some((p) => p.id === (s.voice === 'auto' ? PREMADE : s.voice))) return `no ${s.name} voice pack on this computer`;
  setVoice(s.voice);
  if (state.enabled) { say('on'); return `${s.name}: on`; }
  setEnabled(true);
  return `${s.name}: on`;
}

export function useCommissar() { return useSyncExternalStore(subscribe, getState, getState); }

if (typeof window !== 'undefined') {
  window.yarrik = () => summon('yarrik');
  document.addEventListener('visibilitychange', () => { if (document.hidden) stopSpeech(); });
  if (state.enabled) loadPacks();
}
