import { api } from '../../lib/api';

/** One call to a deterministic kit tool (no model, no cost): {ok: true, result} or {ok: false, error: {code, message, at?}}. */
export const runKitTool = (kind, op, args) => api(`/api/kits/${kind}/tool`, { method: 'POST', body: { op, args } });
