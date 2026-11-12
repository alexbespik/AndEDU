// Reads Google's answer to a test request made with a Gemini key (GET /v1beta/models).
// Pure, so it can be tested with node --test. server.py's _is_bad_key matches the same error text;
// keep the two in step (ARCHITECTURE.md section 5.4).
const REJECTED_RE = /API_KEY_INVALID|API key not valid/i;
const REVOKED_RE = /leaked|suspended/i;
const DISABLED_RE = /SERVICE_DISABLED|has not been used in project|is disabled/i;

// 'valid' | 'rejected' (wrong, revoked or leaked key) | 'disabled' (the key's project lacks the Gemini API)
// | 'unknown' (quota, server trouble, anything unclear: the key is saved unverified)
function classifyKeyResponse(status, body) {
  const text = String(body || '');
  if (status === 200) return 'valid';
  if ((status === 400 || status === 401) && REJECTED_RE.test(text)) return 'rejected';
  if (status === 401) return 'rejected';
  if (status === 403 && (REVOKED_RE.test(text) || REJECTED_RE.test(text))) return 'rejected';
  if (status === 403 && DISABLED_RE.test(text)) return 'disabled';
  return 'unknown';
}

module.exports = { classifyKeyResponse };
