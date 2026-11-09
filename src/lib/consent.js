// ---------------------------------------------------------------------------
// Upload consent: images and scanned PDFs are read by Google Gemini, so ask once per profile.
// ---------------------------------------------------------------------------
import { api, loadProfile } from './api';

const NEEDS_GEMINI = /\.(png|jpe?g|webp|gif|pdf)$/i;
const cacheKey = (userId) => `andedu_upload_consent:${userId}`;

function readCache(key) {
  try { return localStorage.getItem(key) === '1'; } catch { return false; }
}
function writeCache(key, on) {
  try { if (on) localStorage.setItem(key, '1'); else localStorage.removeItem(key); } catch { /* storage blocked: ask again next time */ }
}

/**
 * Resolves true when the upload may go ahead; false when the student declined (cancel quietly).
 * `anyFile`: the files' text goes to Gemini whatever their type (e.g. building a course from them), so ask for any file.
 */
export async function confirmGeminiUpload(files, { anyFile = false } = {}) {
  const list = Array.from(files || []);
  if (!anyFile && !list.some((f) => NEEDS_GEMINI.test(f?.name || f?._displayName || ''))) return true;
  const user = loadProfile();
  const key = cacheKey(user?.id || 'anon');
  if (readCache(key)) return true;
  const ok = window.confirm((anyFile
    ? 'Files you add are sent to Google Gemini: their text is used to plan your course, and images and scanned PDFs are read by it. '
    : 'Images and scanned PDFs are sent to Google Gemini so it can read the text in them. ')
    + "Don't upload anything confidential.\n\nSend these files to Google Gemini?");
  if (!ok) return false;
  let recorded = !user?.id;  // no profile: nothing to record on the server
  if (user?.id) {
    try { await api(`/api/users/${user.id}/consent`, { method: 'POST', body: { kind: 'upload' } }); recorded = true; }
    catch { /* older server or offline: go ahead this time, but ask again next time */ }
  }
  if (recorded) writeCache(key, true);  // cache only what the server has on record, so a 428 can't get stuck
  return true;
}

/**
 * Call from an upload's catch: on a 428 (server has no upload consent on record) forget the cached
 * answer so the next try asks again. Returns the message to show.
 */
export function handleUploadConsentError(err) {
  if (err?.status === 428) writeCache(cacheKey(loadProfile()?.id || 'anon'), false);
  return err?.message || 'Upload failed.';
}
