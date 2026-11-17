import React, { useCallback, useEffect, useRef, useState } from 'react';
import { runKitTool } from './kitTool';

const CODE_WORDS = {
  bad_op: 'This tool is not available.',
  bad_args: 'Something in the input cannot be used.',
  too_large: 'That input is too large. Shorten it and try again.',
  too_complex: 'That input is too complex to compute. Try a smaller example.',
  bad_input: 'The tool could not read that input.',
  network: 'The tool could not be reached.',
};

/** Plain-words text for an {code, message, at} error from the server (or a thrown network error). */
export function errorWords(error) {
  if (!error) return '';
  const base = error.message || CODE_WORDS[error.code] || 'Something went wrong.';
  return error.at ? `${base} (field: ${error.at})` : base;
}

/** One kit's tool calls: run(op, args) -> state {loading, result, error}. A late answer to an older call is ignored. */
export function useTool(kind) {
  const [state, setState] = useState({ loading: false, result: null, error: null });
  const seq = useRef(0);
  useEffect(() => () => { seq.current = -1; }, []);
  // tag: what produced this result (e.g. the electoral method), so a desk renders a result by the input that made it
  const run = useCallback(async (op, args, tag = null) => {
    const id = ++seq.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    let res;
    try {
      res = await runKitTool(kind, op, args);
    } catch (err) {
      const msg = err?.status === 429 ? 'Too many requests just now. Wait a minute and try again.' : (err?.message || CODE_WORDS.network);
      res = { ok: false, error: { code: err?.status === 429 ? 'rate_limit' : 'network', message: msg } };
    }
    if (id !== seq.current) return null;
    setState(res?.ok ? { loading: false, result: res.result, error: null, tag } : { loading: false, result: null, error: res?.error || { code: 'bad_input' }, tag });
    return res;
  }, [kind]);
  return [state, run];
}

/** Live region around a tool result: loading text, a plain-words error, or render(result). */
export function Outcome({ state, render, idle }) {
  const { loading, result, error } = state;
  return (
    <div className="kt-out" aria-live="polite" aria-busy={loading}>
      {loading && <p className="hint">Computing...</p>}
      {error && <div className="notice notice-bad" role="alert">{errorWords(error)}</div>}
      {!loading && !error && result && render(result)}
      {!loading && !error && !result && idle && <p className="hint">{idle}</p>}
    </div>
  );
}

/** Horizontal bar, value in 0..1. */
export function Bar({ label, value, text, tone = '' }) {
  const pct = Math.max(0, Math.min(1, Number(value) || 0)) * 100;
  return (
    <div className="kt-bar">
      <span className="kt-bar-label">{label}</span>
      <span className="kt-bar-track" aria-hidden="true"><span className={`kt-bar-fill ${tone}`} style={{ width: `${pct}%` }} /></span>
      <span className="kt-bar-text">{text}</span>
    </div>
  );
}

export const pct = (v, digits = 1) => `${(Number(v) * 100).toFixed(digits)}%`;

/** "7/30" or a number -> a number. */
export function fracValue(s) {
  if (typeof s === 'number') return s;
  const [a, b] = String(s).split('/');
  const v = b ? Number(a) / Number(b) : Number(a);
  return Number.isFinite(v) ? v : 0;
}

/** A tool's card: title, one-line explanation, children. */
export function DeskCard({ title, what, children }) {
  return (
    <section className="panel stack-sm kt-card" style={{ marginTop: 'var(--space-4)' }}>
      <h2>{title}</h2>
      <p className="hint">{what}</p>
      {children}
    </section>
  );
}

export function RunButton({ loading, children = 'Run', onClick }) {
  return <button type="button" className="btn btn-primary" onClick={onClick} disabled={loading}>{loading ? 'Computing...' : children}</button>;
}

/** Whole-number text -> integer, or null. */
export function toInt(v) {
  const s = String(v ?? '').trim();
  return /^-?\d+$/.test(s) ? Number(s) : null;
}
