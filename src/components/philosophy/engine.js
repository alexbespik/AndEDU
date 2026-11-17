import { api } from '../../lib/api';

/** One call to the deterministic logic engine (no model, no cost): {ok, result} or {ok: false, error: {code, message, pos?}}. */
export async function logicCheck(request) {
  try {
    return await api('/api/logic/grade', { method: 'POST', body: request });
  } catch (err) {
    return { ok: false, error: { code: 'network', message: err.message || 'The logic engine could not be reached.' } };
  }
}

export const tf = (v) => (v ? 'T' : 'F');

export function rowText(row) {
  return Object.entries(row || {}).map(([k, v]) => `${k} = ${tf(v)}`).join(', ');
}
