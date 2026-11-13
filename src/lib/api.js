// ---------------------------------------------------------------------------
// &.edu client API: JSON helpers, ONE shared event poller, profile storage.
// ---------------------------------------------------------------------------
import { useEffect, useRef } from 'react';

// Bearer token for servers running with accounts (SCIEDU_AUTH=1); absent on a personal machine.
const TOKEN_KEY = 'andedu_lab_token';
export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(token) {
  try { if (token) localStorage.setItem(TOKEN_KEY, token); else localStorage.removeItem(TOKEN_KEY); } catch { /* tab-only */ }
}
/** The student's calendar day (streaks and daily goals follow local midnight, not UTC). */
export function localDay(d = new Date()) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
function authHeaders(extra) {
  const token = getToken();
  return { ...(extra || {}), 'X-Local-Day': localDay(), ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

export async function api(path, { method = 'GET', body, signal } = {}) {
  const sentToken = getToken();
  const res = await fetch(path, {
    method,
    signal,
    headers: authHeaders(body !== undefined ? { 'Content-Type': 'application/json' } : undefined),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  // expired or revoked session, or (accounts on this computer) a job's key that locked long ago: sign in again. Only
  // when this request carried the session still in use: a poll from the sign-in screen (no token) or one sent before
  // a new sign-in must not end the new session.
  const current = sentToken && sentToken === getToken();
  if (current && ((res.status === 401 && !path.startsWith('/api/auth/')) || data?.code === 'key_locked')) {
    window.dispatchEvent(new CustomEvent('andedu:signed-out', { detail: { reason: data?.code || null } }));
  }
  // accounts on this computer: a request that needed the account's Gemini key and found none opens the key card
  if (current && data?.code === 'gemini_key_missing') window.dispatchEvent(new Event('andedu:key-missing'));
  if (!res.ok) {
    const detail = data?.detail;
    const msg = Array.isArray(detail) ? detail.map((d) => d.msg).join('; ') : detail;
    // code: gemini_key_missing | key_locked (accounts on this computer)
    throw Object.assign(new Error(msg || `Request failed (HTTP ${res.status})`), { status: res.status, code: data?.code });
  }
  return data;
}

/** fetch() with the session token, for callers that need the raw Response (IDE, streams). */
export function authFetch(url, opts = {}) {
  return fetch(url, { ...opts, headers: authHeaders(opts.headers) });
}

/** Downloads an API file with the session token (a plain <a href> can't send it). */
export async function downloadFile(path, filename) {
  const res = await authFetch(path);
  if (!res.ok) throw new Error(`Download failed (HTTP ${res.status})`);
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement('a'), { href: url, download: filename });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function uploadFiles(files) {
  const form = new FormData();
  for (const f of files) form.append('files', f);
  const res = await fetch('/api/upload-multimodal', { method: 'POST', body: form, headers: authHeaders() });
  if (!res.ok) {
    let detail = null;
    try { detail = (await res.json())?.detail; } catch { /* empty body */ }
    const msg = Array.isArray(detail) ? detail.map((d) => d.msg).join('; ') : detail;
    // status lets callers spot 428 (upload consent missing on the server)
    throw Object.assign(new Error(msg || `Upload failed (HTTP ${res.status})`), { status: res.status });
  }
  return res.json();
}

// --- Shared AGY event stream -------------------------------------------------
// The server numbers events; we start from its current cursor so a reload never
// replays old navigation, and every subscriber sees each event exactly once.
const subscribers = new Set();
let cursor = -1;
// Set before the first request goes out: subscribers that mount while it is in flight
// must not start a second loop (each loop would deliver every event again).
let polling = false;

async function pollOnce() {
  try {
    const data = await api(`/api/agy/events?since=${cursor}`);
    if (typeof data.cursor === 'number') {
      if (data.cursor < cursor) cursor = -1; // backend restarted: resync without replay
      else {
        for (const evt of data.events || []) subscribers.forEach((fn) => fn(evt));
        cursor = data.cursor;
      }
    }
  } catch { /* backend offline: keep polling */ }
  setTimeout(pollOnce, document.hidden ? 4000 : 1000);
}

/** Subscribes to server events (TOPIC_UPDATED, SWITCH_TOPIC, JOB_UPDATE, COURSE_UPDATED, ...). */
export function useAgyEvents(handler) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    const fn = (evt) => ref.current(evt);
    subscribers.add(fn);
    if (!polling) {
      polling = true;
      pollOnce();
    }
    return () => subscribers.delete(fn);
  }, []);
}

// --- Local profile ------------------------------------------------------------
const PROFILE_KEY = 'andedu_lab_profile';

export function loadProfile() {
  try { return JSON.parse(localStorage.getItem(PROFILE_KEY) || 'null'); } catch { return null; }
}

export function saveProfile(user) {
  try {
    // local: an account on this computer (its session ends with each launch; the sign-in screen resumes it)
    if (user) localStorage.setItem(PROFILE_KEY, JSON.stringify({ id: user.id, name: user.name, ...(user.local ? { local: true } : {}) }));
    else localStorage.removeItem(PROFILE_KEY);
  } catch { /* storage blocked: profile lasts for this tab only */ }
}
