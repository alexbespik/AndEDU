// Crash reports from the browser: kept in this browser (last 10) and sent to POST /api/client-errors, which appends
// them to logs/client_errors.log under the data folder. Used by ErrorBoundary and by the page-wide handlers below.
import { api } from './api';

const RECENT_KEY = 'andedu.recentErrors';
const MAX_PER_PAGE = 20;  // one bad loop must not flood the log
const seen = new Set();

/** Keeps the last few crashes in this browser, so they can be read even when the backend could not be told. */
function remember(entry) {
  try {
    const list = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]');
    localStorage.setItem(RECENT_KEY, JSON.stringify([entry, ...list].slice(0, 10)));
  } catch { /* storage off or full: the report to the server still goes out */ }
}

/** Report one error. `view`: where it happened (a workspace mode, "window", "promise"). Repeats are sent once. */
export function reportClientError(view, error, componentStack = '') {
  const entry = {
    view: String(view || 'view').slice(0, 80),
    message: String(error?.message || error || 'unknown error').slice(0, 500),
    stack: String(error?.stack || '').slice(0, 4000),
    componentStack: String(componentStack || '').slice(0, 4000),
    path: `${window.location.pathname}${window.location.hash}`.slice(0, 200),
  };
  const key = `${entry.view}|${entry.message}`;
  if (seen.has(key) || seen.size >= MAX_PER_PAGE) return;
  seen.add(key);
  remember({ ...entry, at: new Date().toISOString() });
  api('/api/client-errors', { method: 'POST', body: entry }).catch(() => {});
}

// A page's code file (a lazy chunk) failed to load: the dev server rebuilt or restarted, or the app was updated while
// this window was open, so the old file names are gone. A reload fetches the current ones.
const CHUNK_RE = /dynamically imported module|Importing a module script failed|error loading dynamically imported|Outdated Optimize Dep|ChunkLoadError|Loading chunk [\w-]+ failed|Unable to preload CSS/i;
const RELOAD_KEY = 'andedu.chunkReloadAt';

export const isChunkLoadError = (error) => CHUNK_RE.test(String(error?.message || error || ''));

/** Reload once to pick up the current files; false (do nothing) when a reload already happened in the last minute. */
export function reloadForChunkError() {
  let last = 0;
  try { last = Number(sessionStorage.getItem(RELOAD_KEY)) || 0; } catch { /* storage off: still reload once */ }
  if (Date.now() - last < 60000) return false;
  try { sessionStorage.setItem(RELOAD_KEY, String(Date.now())); } catch { /* ignore */ }
  window.location.reload();
  return true;
}

/** Uncaught errors outside React rendering (event handlers, timers, promises): logged too, so a crash leaves a trace. */
export function installGlobalErrorReporting() {
  // Vite's own signal that a chunk's preload failed: reload instead of failing later
  window.addEventListener('vite:preloadError', (e) => {
    reportClientError('chunk', e.payload || 'preload failed');
    if (reloadForChunkError()) e.preventDefault();
  });
  window.addEventListener('error', (e) => {
    if (!e.error && !e.message) return;  // a failed <img>/<script> load, not a crash
    reportClientError('window', e.error || e.message);
  });
  window.addEventListener('unhandledrejection', (e) => {
    const r = e.reason;
    if (r?.name === 'AbortError') return;  // a cancelled fetch
    reportClientError('promise', r);
  });
}
