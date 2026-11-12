import React, { useEffect, useState } from 'react';
import { LOADING_QUOTES, quoteCite, useLoadingPrefs } from '../lib/quotes.js';

const ROTATE_MS = 8000;

const reducedMotion = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

function Quote() {
  const [index, setIndex] = useState(() => Math.floor(Math.random() * LOADING_QUOTES.length));
  const [still] = useState(reducedMotion);
  useEffect(() => {
    if (still || LOADING_QUOTES.length < 2) return undefined;
    const t = setInterval(() => setIndex((i) => (i + 1) % LOADING_QUOTES.length), ROTATE_MS);
    return () => clearInterval(t);
  }, [still]);
  const q = LOADING_QUOTES[index];
  if (!q) return null;
  return (
    <figure className="loading-quote">
      <blockquote key={q.id}>“{q.text}”</blockquote>
      <figcaption>{quoteCite(q)}</figcaption>
      {still && LOADING_QUOTES.length > 1 && (
        <button type="button" className="btn btn-quiet btn-sm" onClick={() => setIndex((i) => (i + 1) % LOADING_QUOTES.length)}>
          Next quote
        </button>
      )}
    </figure>
  );
}

// One loading state for the whole app: a bar (determinate when `progress` is a number), the last steps of a
// background job (`log`: [{at, step}]), and a quote unless Focus mode is on. `compact` drops the quote and the
// page padding for small slots. Fast loads never flash it: it fades in after a short CSS delay.
export default function LoadingPanel({ label = 'Loading…', progress = null, log = null, compact = false, page = false }) {
  const { quotes } = useLoadingPrefs();
  const known = typeof progress === 'number';
  const pct = known ? Math.round(Math.min(Math.max(progress, 0), 1) * 100) : null;
  const done = (log || []).filter((s, i, all) => !(i === all.length - 1 && s.step === label));  // the label is the current step
  const steps = done.slice(-6);
  const body = (
    <div className={`loading-panel${compact ? ' compact' : ''}`}>
      <p className="loading-label">{label}</p>
      <div className={`loading-bar${known ? '' : ' indeterminate'}`} role="progressbar" aria-label={label}
           aria-valuemin={0} aria-valuemax={100} aria-valuenow={known ? pct : undefined}>
        <span style={known ? { width: `${Math.max(pct, 4)}%` } : undefined} />
      </div>
      {steps.length > 0 && (
        <ol className="loading-log" role="log" aria-live="polite">
          {steps.map((s, i) => <li key={`${s.at}-${i}`}>{s.step}</li>)}
        </ol>
      )}
      {quotes && !compact && <Quote />}
    </div>
  );
  return page ? <div className="page">{body}</div> : body;
}
