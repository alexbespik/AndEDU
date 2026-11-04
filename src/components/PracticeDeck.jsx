import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { ArrowUp, ArrowDown, RotateCcw, Play, Loader2 } from 'lucide-react';
import { runPython } from '../lib/pyodide';
import Md, { MdInline } from './Md';
import { MatchPairs } from './Activities';
import DrawingBoard from './DrawingBoard';
import { api } from '../lib/api';

const TYPE_LABEL = {
  fill_blank: 'Fill in the blank',
  order_steps: 'Put the steps in order',
  numeric: 'Calculate',
  true_false: 'True or false',
  code: 'Write the code',
  match_pairs: 'Match the pairs',
  draw: 'Draw it',
};

function seededShuffle(items, seed) {
  const out = [...items];
  let h = 0;
  for (const ch of String(seed)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  for (let i = out.length - 1; i > 0; i--) {
    h = (h * 1103515245 + 12345) >>> 0;
    const j = h % (i + 1);
    [out[i], out[j]] = [out[j], out[i]];
  }
  // never start already solved
  if (out.length > 1 && out.every((v, i) => v === items[i])) out.push(out.shift());
  return out;
}

// Lets the page that shows the deck award XP for a solved item (TopicViewer, Math practice)
const SolvedCtx = createContext(null);
function useReportSolved(ok, item) {
  const onSolved = useContext(SolvedCtx);
  useEffect(() => { if (ok && onSolved) onSolved(item); }, [ok]); // eslint-disable-line react-hooks/exhaustive-deps
}

function Feedback({ ok, item, extra }) {
  useReportSolved(ok, item);
  return (
    <div className={`feedback ${ok ? 'ok' : 'bad'}`} aria-live="polite">
      <p style={{ fontWeight: 700, marginBottom: 4 }}>{ok ? 'Correct.' : 'Not yet.'}{extra ? ` ${extra}` : ''}</p>
      {item.explanation && <Md>{item.explanation}</Md>}
    </div>
  );
}

function FillBlank({ item }) {
  const [pick, setPick] = useState(null);
  const done = pick !== null;
  return (
    <div className="stack-sm">
      <div className="choices">
        {item.options.map((opt, i) => (
          <button key={opt} type="button" className="choice" disabled={done} aria-pressed={pick === opt}
            data-result={done ? (opt === item.answer ? 'correct' : opt === pick ? 'wrong' : undefined) : undefined}
            onClick={() => setPick(opt)}>
            <span className="key">{'ABCDEFGH'[i]}</span><span><MdInline>{opt}</MdInline></span><span />
          </button>
        ))}
      </div>
      {done && <Feedback ok={pick === item.answer} item={item} />}
      {done && <div className="btn-row"><button type="button" className="btn btn-quiet btn-sm" onClick={() => setPick(null)}><RotateCcw size={14} aria-hidden="true" /> Try again</button></div>}
    </div>
  );
}

function OrderSteps({ item }) {
  const start = useMemo(() => seededShuffle(item.steps, item.id), [item]);
  const [order, setOrder] = useState(start);
  const [checked, setChecked] = useState(false);
  const move = (i, d) => {
    const j = i + d;
    if (j < 0 || j >= order.length) return;
    const next = [...order];
    [next[i], next[j]] = [next[j], next[i]];
    setOrder(next);
    setChecked(false);
  };
  const right = order.filter((s, i) => s === item.steps[i]).length;
  return (
    <div className="stack-sm">
      <ol className="order-list">
        {order.map((step, i) => (
          <li key={step} className="order-item" style={checked ? { borderColor: step === item.steps[i] ? 'var(--ok)' : 'var(--bad)' } : undefined}>
            <span className="n">{i + 1}</span>
            <span><MdInline>{step}</MdInline></span>
            <span className="btn-row">
              <button type="button" className="btn btn-quiet btn-sm btn-icon" onClick={() => move(i, -1)} disabled={i === 0} aria-label={`Move step ${i + 1} up`}><ArrowUp size={14} /></button>
              <button type="button" className="btn btn-quiet btn-sm btn-icon" onClick={() => move(i, 1)} disabled={i === order.length - 1} aria-label={`Move step ${i + 1} down`}><ArrowDown size={14} /></button>
            </span>
          </li>
        ))}
      </ol>
      <div className="btn-row">
        <button type="button" className="btn btn-primary btn-sm" onClick={() => setChecked(true)}>Check order</button>
        <button type="button" className="btn btn-quiet btn-sm" onClick={() => { setOrder(start); setChecked(false); }}>Reset</button>
      </div>
      {checked && <Feedback ok={right === item.steps.length} item={item} extra={right === item.steps.length ? '' : `${right} of ${item.steps.length} steps are in the right place.`} />}
    </div>
  );
}

function Numeric({ item }) {
  const [value, setValue] = useState('');
  const [result, setResult] = useState(null);
  const check = (e) => {
    e.preventDefault();
    const v = parseFloat(value.replace(',', '.'));
    if (!Number.isFinite(v)) return setResult({ ok: false, extra: 'Enter a number.' });
    const tol = Math.max(Math.abs(item.answer) * (item.tolerance ?? 0.02), 1e-9);
    setResult({ ok: Math.abs(v - item.answer) <= tol, extra: '' });
  };
  return (
    <form className="stack-sm" onSubmit={check}>
      <div className="inline-answer">
        <label className="visually-hidden" htmlFor={`num-${item.id}`}>Your answer</label>
        <input id={`num-${item.id}`} className="input num" inputMode="decimal" value={value}
          onChange={(e) => { setValue(e.target.value); setResult(null); }} placeholder="Your answer" />
        {item.unit && <span>{item.unit}</span>}
        <button type="submit" className="btn btn-primary btn-sm">Check</button>
      </div>
      {result && <Feedback ok={result.ok} item={item} extra={result.ok ? '' : result.extra} />}
    </form>
  );
}

function TrueFalse({ item }) {
  const [pick, setPick] = useState(null);
  return (
    <div className="stack-sm">
      <div className="btn-row">
        {[true, false].map((v) => (
          <button key={String(v)} type="button" className={`btn ${pick === v ? 'btn-primary' : 'btn-secondary'} btn-sm`}
            aria-pressed={pick === v} onClick={() => setPick(v)}>{v ? 'True' : 'False'}</button>
        ))}
      </div>
      {pick !== null && <Feedback ok={pick === item.answer} item={item} />}
    </div>
  );
}

/** Turns a Pyodide traceback into what a student needs: which test failed, or the error and its line. */
function explainError(raw, script, userLines) {
  if (!raw) return '';
  const lines = raw.split('\n').map((l) => l.trimEnd()).filter(Boolean);
  const last = lines[lines.length - 1] || raw;
  const frames = [...raw.matchAll(/File "<exec>", line (\d+)/g)];
  const n = frames.length ? Number(frames[frames.length - 1][1]) : null;
  const src = n ? (script.split('\n')[n - 1] || '').trim() : '';
  if (/^AssertionError/.test(last) && n && n > userLines) return `Failed: ${src}${last.length > 15 ? `\n${last}` : ''}`;
  return n && n <= userLines ? `${last}\n(your code, line ${n}: ${src})` : last;
}

function CodeExercise({ item }) {
  const [code, setCode] = useState(item.starter || '');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [tried, setTried] = useState(false);
  const [showSolution, setShowSolution] = useState(false);

  const run = async () => {
    setRunning(true);
    setResult(null);
    const script = `${code}\n\n${item.tests}\nprint("__ALL_TESTS_PASSED__")`;
    const res = await runPython(script);
    const passed = res.ok && (res.output || '').includes('__ALL_TESTS_PASSED__');
    const error = res.timedOut ? res.error : explainError(res.error, script, code.split('\n').length);
    setResult({ ...res, error, passed, output: (res.output || '').replace('__ALL_TESTS_PASSED__\n', '').trim() });
    setTried(true);
    setRunning(false);
  };

  // Tab inserts four spaces instead of leaving the editor
  const onKeyDown = (e) => {
    if (e.key !== 'Tab' || e.shiftKey) return;
    e.preventDefault();
    const el = e.target;
    const { selectionStart: a, selectionEnd: b } = el;
    const next = `${code.slice(0, a)}    ${code.slice(b)}`;
    setCode(next);
    requestAnimationFrame(() => { el.selectionStart = el.selectionEnd = a + 4; });
  };

  return (
    <div className="stack-sm">
      <label htmlFor={`code-${item.id}`} className="visually-hidden">Your code</label>
      <textarea id={`code-${item.id}`} className="textarea code-editor" spellCheck={false} value={code}
        onChange={(e) => setCode(e.target.value)} onKeyDown={onKeyDown}
        rows={Math.min(18, Math.max(6, code.split('\n').length + 1))} />
      <details className="hint">
        <summary style={{ cursor: 'pointer' }}>Tests your code must pass</summary>
        <pre className="code-tests">{item.tests}</pre>
      </details>
      <div className="btn-row">
        <button type="button" className="btn btn-primary btn-sm" onClick={run} disabled={running}>
          {running ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <Play size={14} aria-hidden="true" />}
          {running ? ' Running…' : ' Run tests'}
        </button>
        <button type="button" className="btn btn-quiet btn-sm" onClick={() => { setCode(item.starter || ''); setResult(null); }}>Reset</button>
        {item.solution && tried && (
          <button type="button" className="btn btn-quiet btn-sm" onClick={() => setShowSolution((v) => !v)} aria-expanded={showSolution}>
            {showSolution ? 'Hide solution' : 'Show solution'}
          </button>
        )}
        <span className="hint">Runs in your browser; the first run loads Python (a few seconds).</span>
      </div>
      {result && <SolvedReporter ok={result.passed} item={item} />}
      {result && (
        <div className={`feedback ${result.passed ? 'ok' : 'bad'}`} aria-live="polite">
          <p style={{ fontWeight: 700, marginBottom: 4 }}>
            {result.passed ? 'All tests pass.' : result.timedOut ? 'Stopped.' : 'Not yet: a test failed or the code raised an error.'}
          </p>
          {(result.error || result.output) && <pre className="code-tests">{[result.output, result.error].filter(Boolean).join('\n')}</pre>}
          {result.passed && item.explanation && <Md>{item.explanation}</Md>}
        </div>
      )}
      {showSolution && <pre className="code-tests">{item.solution}</pre>}
    </div>
  );
}

function DrawExercise({ item }) {
  const board = useRef(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [dirty, setDirty] = useState(false);
  useReportSolved(Boolean(result?.passed), item);
  const check = async () => {
    if (board.current?.isEmpty()) { setError('Draw something first.'); return; }
    setBusy(true); setError(null);
    try {
      const image = await board.current.toPNG();
      setResult(await api('/api/draw/check', { method: 'POST', body: { image, prompt: item.prompt, criteria: item.criteria, reference: item.reference || '' } }));
      setDirty(false);
    } catch (e) { setError(e.message); }
    setBusy(false);
  };
  return (
    <div className="stack-sm">
      <details className="hint" open>
        <summary style={{ cursor: 'pointer' }}>What the checker looks for</summary>
        <ul className="draw-criteria">{item.criteria.map((c) => <li key={c}><MdInline>{c}</MdInline></li>)}</ul>
      </details>
      <DrawingBoard ref={board} background={item.background || 'grid'} onChange={() => setDirty(true)} />
      <div className="btn-row">
        <button type="button" className="btn btn-primary btn-sm" onClick={check} disabled={busy}>
          {busy ? <Loader2 size={14} className="spin" aria-hidden="true" /> : null} {busy ? 'Checking your drawing…' : result ? 'Check again' : 'Check with AI'}
        </button>
        <span className="hint">Your drawing is sent to the AI to be checked. Neatness doesn't count; content does.</span>
      </div>
      {error && <p className="notice notice-bad">{error}</p>}
      {result && (
        <div className={`feedback ${result.passed ? 'ok' : 'bad'}`} aria-live="polite">
          <p style={{ fontWeight: 700, marginBottom: 4 }}>
            {result.passed ? 'Looks right.' : 'Not yet.'} {Math.round(result.score * 100)}% of the criteria met{dirty ? ' (before your latest changes)' : ''}.
          </p>
          <ul className="draw-results">
            {result.criteria.map((c, k) => (
              <li key={k} data-met={c.met === true}><span aria-hidden="true">{c.met ? '✓' : '✗'}</span> <MdInline>{c.criterion}</MdInline>{c.comment ? <span className="hint"> · {c.comment}</span> : null}</li>
            ))}
          </ul>
          {result.feedback && <p style={{ marginTop: 6 }}><MdInline>{result.feedback}</MdInline></p>}
          {result.passed && item.explanation && <Md>{item.explanation}</Md>}
        </div>
      )}
    </div>
  );
}

function MatchBody({ item }) {
  const [ok, setOk] = useState(false);
  useReportSolved(ok, item);
  return <MatchPairs item={item} onSolved={() => setOk(true)} />;
}

function SolvedReporter({ ok, item }) {
  useReportSolved(ok, item);
  return null;
}

const RENDER = { fill_blank: FillBlank, order_steps: OrderSteps, numeric: Numeric, true_false: TrueFalse, code: CodeExercise, match_pairs: MatchBody, draw: DrawExercise };

export default function PracticeDeck({ items = [], onSolved }) {
  const usable = items.filter((p) => RENDER[p.type]);
  if (!usable.length) {
    return <div className="panel"><p>No practice puzzles for this topic yet. Lessons generated in a course come with them.</p></div>;
  }
  return (
    <SolvedCtx.Provider value={onSolved || null}>
    <div className="stack">
      {usable.map((item, i) => {
        const Body = RENDER[item.type];
        return (
          <section key={item.id || i} className="panel stack-sm" aria-labelledby={`pr-${i}`}>
            <p className="hint">{i + 1}. {TYPE_LABEL[item.type]}</p>
            <div id={`pr-${i}`} className="question"><Md>{item.prompt}</Md></div>
            <Body item={item} />
          </section>
        );
      })}
    </div>
    </SolvedCtx.Provider>
  );
}
