// ---------------------------------------------------------------------------
// &.edu LAB client API: JSON helpers, ONE shared event poller, profile storage.
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
  const res = await fetch(path, {
    method,
    signal,
    headers: authHeaders(body !== undefined ? { 'Content-Type': 'application/json' } : undefined),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 && !path.startsWith('/api/auth/')) {
    window.dispatchEvent(new Event('andedu:signed-out'));  // expired or revoked session
  }
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    const detail = data?.detail;
    const msg = Array.isArray(detail) ? detail.map((d) => d.msg).join('; ') : detail;
    throw new Error(msg || `Request failed (HTTP ${res.status})`);
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
  if (!res.ok) throw new Error(`Upload failed (HTTP ${res.status})`);
  return res.json();
}

// --- Shared AGY event stream -------------------------------------------------
// The server numbers events; we start from its current cursor so a reload never
// replays old navigation, and every subscriber sees each event exactly once.
const subscribers = new Set();
let cursor = -1;
let timer = null;

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
  timer = setTimeout(pollOnce, document.hidden ? 4000 : 1000);
}

/** Subscribes to server events (TOPIC_UPDATED, SWITCH_TOPIC, JOB_UPDATE, COURSE_UPDATED, ...). */
export function useAgyEvents(handler) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    const fn = (evt) => ref.current(evt);
    subscribers.add(fn);
    if (!timer) pollOnce();
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
    if (user) localStorage.setItem(PROFILE_KEY, JSON.stringify({ id: user.id, name: user.name }));
    else localStorage.removeItem(PROFILE_KEY);
  } catch { /* storage blocked: profile lasts for this tab only */ }
}
