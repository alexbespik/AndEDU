// Activities for Lab, Math and IDE classes: label_diagram, sort_by, odd_one_out, cloze, spot_the_bug
// (docs/agy-tasks/other_subject_activities.md). Same contract as ./language.jsx: each body takes
// {item, onResult(ok, given), retry}. Items arrive cleaned by practice_general.py; diagrams are offline files
// in public/diagrams/ or an svg_spec drawn as React elements (never injected as markup).
import React, { useMemo, useRef, useState } from 'react';
import { ArrowUp, ArrowDown, RotateCcw, Check, Play, Loader2 } from 'lucide-react';
import Md, { MdInline } from '../components/Md';
import { gradeText } from '../lib/langgrade';
import { runPython } from '../lib/pyodide';
import { ExplainAnswerButton } from '../components/ExplainDialog';
import '../styles/general.css';

export const GENERAL_TYPES = ['label_diagram', 'sort_by', 'odd_one_out', 'cloze', 'spot_the_bug'];

const NEAR = 0.06;  // a label counts when dropped this close to its spot (fractions of the diagram)
const CLOZE_GAP = /\[\[([^[\]]*)\]\]/;

function seeded(items, seed) {
  const out = [...items];
  let h = 7;
  for (const ch of String(seed)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  for (let i = out.length - 1; i > 0; i--) { h = (h * 1103515245 + 12345) >>> 0; const j = h % (i + 1); [out[i], out[j]] = [out[j], out[i]]; }
  if (out.length > 1 && out.every((v, i) => v === items[i])) out.push(out.shift());  // never start solved
  return out;
}

function Result({ ok, note, answer, item, onRetry, given, detail }) {
  return (
    <div className={`feedback ${ok ? 'ok' : 'bad'}`} aria-live="polite">
      <p style={{ fontWeight: 700, marginBottom: 4 }}>{ok ? 'Correct.' : 'Not quite.'}{note ? ` ${note}` : ''}</p>
      {!ok && answer && <p>Correct answer: <strong><MdInline>{answer}</MdInline></strong></p>}
      {detail && <Md>{detail}</Md>}
      {item.explanation && item.explanation !== detail && <Md>{item.explanation}</Md>}
      {!ok && (
        <div className="btn-row" style={{ marginTop: 6 }}>
          <ExplainAnswerButton item={item} studentAnswer={given} correctAnswer={answer || item.answer} question={item.prompt} />
          {onRetry && (
            <button type="button" className="btn btn-quiet btn-sm" onClick={onRetry}>
              <RotateCcw size={14} aria-hidden="true" /> Try again
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function useCheck(onResult) {
  const [res, setRes] = useState(null);
  const done = (r, given) => { setRes(r); onResult?.(r.ok, given); };
  return [res, done, () => setRes(null)];
}

// ---- label_diagram

const TONES = new Set(['ink', 'muted', 'accent', 'ok', 'bad', 'gold', 'info']);
const tone = (t) => `var(--${TONES.has(t) ? t : 'ink'})`;  // the server allows only these; files written by hand may not be checked

/** svg_spec ({width, height, shapes}) as React SVG elements; only whitelisted numeric attributes are passed. */
function SpecArt({ spec }) {
  const pick = (s, keys) => Object.fromEntries(keys.filter((k) => Number.isFinite(s[k])).map((k) => [k, s[k]]));
  return (
    <svg className="act-diagram-svg" viewBox={`0 0 ${spec.width} ${spec.height}`} role="img" aria-label="Diagram">
      {spec.shapes.map((s, i) => {
        const color = tone(s.tone);
        const style = { stroke: color, fill: s.filled ? color : 'none', fillOpacity: s.filled ? 0.25 : undefined, strokeWidth: 2 };
        if (s.kind === 'rect') return <rect key={i} {...pick(s, ['x', 'y', 'width', 'height', 'rx'])} style={style} />;
        if (s.kind === 'circle') return <circle key={i} {...pick(s, ['cx', 'cy', 'r'])} style={style} />;
        if (s.kind === 'line') return <line key={i} {...pick(s, ['x1', 'y1', 'x2', 'y2'])} style={style} />;
        if (s.kind === 'text') return <text key={i} {...pick(s, ['x', 'y'])} style={{ fill: color, fontSize: Number.isFinite(s.size) ? Math.min(Math.max(s.size, 6), 72) : 14 }}>{String(s.text)}</text>;
        return null;
      })}
    </svg>
  );
}

/** An offline SVG from public/diagrams/, drawn as a CSS mask so its currentColor strokes follow the theme. */
function ImageArt({ name }) {
  const url = `/diagrams/${encodeURIComponent(name)}`;
  return (
    <>
      <img className="act-diagram-sizer" src={url} alt="" draggable={false} />
      <div className="act-diagram-mask" aria-hidden="true" style={{ WebkitMaskImage: `url("${url}")`, maskImage: `url("${url}")` }} />
    </>
  );
}

function LabelDiagram({ item, onResult, retry = true }) {
  const board = useRef(null);
  const drag = useRef(null);
  const bank = useMemo(() => seeded(item.labels.map((_, i) => i), item.id || item.prompt), [item]);
  const [placed, setPlaced] = useState({});     // label index -> {x, y}
  const [selected, setSelected] = useState(null);
  const [ghost, setGhost] = useState(null);     // {i, cx, cy} while dragging
  const [res, done, reset] = useCheck(onResult);
  const spots = item.labels.map((l) => ({ x: l.x, y: l.y }));

  const place = (i, pt) => { setPlaced((p) => ({ ...p, [i]: pt })); setSelected(null); };
  const snap = (pt) => {
    let best = null, d = NEAR;
    for (const s of spots) { const e = Math.hypot(s.x - pt.x, s.y - pt.y); if (e <= d) { best = s; d = e; } }
    return best || pt;
  };
  const onDown = (i) => (e) => {
    if (res) return;
    drag.current = { i, x0: e.clientX, y0: e.clientY, moved: false };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  };
  const onMove = (e) => {
    const d = drag.current;
    if (!d) return;
    if (!d.moved && Math.hypot(e.clientX - d.x0, e.clientY - d.y0) < 6) return;
    d.moved = true;
    setGhost({ i: d.i, cx: e.clientX, cy: e.clientY });
  };
  const onUp = (e) => {
    const d = drag.current;
    drag.current = null;
    setGhost(null);
    if (!d) return;
    if (!d.moved) { setSelected((s) => (s === d.i ? null : d.i)); return; }  // a tap selects; then tap a spot
    const r = board.current?.getBoundingClientRect();
    if (!r) return;
    const pt = { x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height };
    if (pt.x >= 0 && pt.x <= 1 && pt.y >= 0 && pt.y <= 1) place(d.i, snap(pt));
  };
  const occupied = (s) => Object.values(placed).some((p) => p.x === s.x && p.y === s.y);
  const right = (i) => placed[i] && Math.hypot(placed[i].x - item.labels[i].x, placed[i].y - item.labels[i].y) <= NEAR;
  const allPlaced = item.labels.every((_, i) => placed[i]);
  const check = () => {
    const good = item.labels.filter((_, i) => right(i)).length;
    const given = item.labels.map((l, i) => `${l.text}: ${right(i) ? 'right spot' : 'wrong spot'}`).join('; ');
    done({ ok: good === item.labels.length, given, note: good === item.labels.length ? '' : `${good} of ${item.labels.length} labels are in the right place; the dashed ones show where the rest belong.` }, given);
  };
  const chipProps = (i) => ({
    onPointerDown: onDown(i), onPointerMove: onMove, onPointerUp: onUp, onPointerCancel: () => { drag.current = null; setGhost(null); },
    onClick: (e) => { if (e.detail === 0) setSelected((s) => (s === i ? null : i)); },  // keyboard: Enter/Space selects
  });

  return (
    <div className="stack-sm">
      <div className="act-diagram" ref={board}
        style={item.svg_spec ? { aspectRatio: `${item.svg_spec.width} / ${item.svg_spec.height}` } : undefined}>
        {item.svg_spec ? <SpecArt spec={item.svg_spec} /> : <ImageArt name={item.image} />}
        {spots.map((s, k) => !occupied(s) && (
          <button key={k} type="button" className="act-spot" style={{ left: `${s.x * 100}%`, top: `${s.y * 100}%` }}
            disabled={!!res || selected === null} aria-label={`Spot ${k + 1}`}
            onClick={() => selected !== null && place(selected, s)} />
        ))}
        {item.labels.map((l, i) => placed[i] && (
          <button key={i} type="button" className="act-chip act-chip-placed" disabled={!!res}
            data-result={res ? (right(i) ? 'correct' : 'wrong') : undefined}
            style={{ left: `${placed[i].x * 100}%`, top: `${placed[i].y * 100}%` }}
            onClick={() => setPlaced((p) => { const n = { ...p }; delete n[i]; return n; })}
            aria-label={`${l.text} (placed; tap to take back)`}>{l.text}</button>
        ))}
        {res && item.labels.map((l, i) => !right(i) && (
          <span key={`a${i}`} className="act-chip act-chip-answer" style={{ left: `${l.x * 100}%`, top: `${l.y * 100}%` }}>{l.text}</span>
        ))}
      </div>
      <div className="act-bank" aria-label="Labels">
        {bank.filter((i) => !placed[i]).map((i) => (
          <button key={i} type="button" className="act-chip" aria-pressed={selected === i} disabled={!!res} {...chipProps(i)}>
            {item.labels[i].text}
          </button>
        ))}
        {!allPlaced && <span className="hint">Drag each label onto its spot, or tap a label and then a spot.</span>}
      </div>
      {ghost && <span className="act-chip act-chip-ghost" style={{ left: ghost.cx, top: ghost.cy }}>{item.labels[ghost.i].text}</span>}
      {!res && (
        <div className="btn-row">
          <button type="button" className="btn btn-primary btn-sm" disabled={!allPlaced} onClick={check}><Check size={14} aria-hidden="true" /> Check</button>
          <button type="button" className="btn btn-quiet btn-sm" disabled={!Object.keys(placed).length} onClick={() => { setPlaced({}); setSelected(null); }}>Clear</button>
        </div>
      )}
      {res && <Result ok={res.ok} note={res.note} item={item} given={res.given}
        onRetry={retry ? () => { reset(); setPlaced({}); } : null} />}
    </div>
  );
}

// ---- sort_by

function SortBy({ item, onResult, retry = true }) {
  const start = useMemo(() => seeded(item.items, item.id || item.prompt), [item]);
  const [order, setOrder] = useState(start);
  const [res, done, reset] = useCheck(onResult);
  const sorted = useMemo(() => [...item.items].sort((a, b) => a.value - b.value), [item]);
  const fmt = (v) => `${Number(v).toLocaleString()}${item.unit ? ` ${item.unit}` : ''}`;
  const move = (i, d) => {
    const j = i + d;
    if (res || j < 0 || j >= order.length) return;
    const next = [...order];
    [next[i], next[j]] = [next[j], next[i]];
    setOrder(next);
  };
  const check = () => {
    const good = order.filter((it, i) => it.text === sorted[i].text).length;
    done({ ok: good === order.length, note: good === order.length ? '' : `${good} of ${order.length} are in the right place.` },
      order.map((it) => it.text).join(' < '));
  };
  return (
    <div className="stack-sm">
      <p className="hint">Lowest {item.property} at the top, highest at the bottom.</p>
      <ol className="order-list">
        {order.map((it, i) => (
          <li key={it.text} className="order-item" data-result={res ? (it.text === sorted[i].text ? 'correct' : 'wrong') : undefined}>
            <span className="n">{i + 1}</span>
            <span><MdInline>{it.text}</MdInline>{res && <span className="act-value"> {fmt(it.value)}</span>}</span>
            <span className="btn-row">
              <button type="button" className="btn btn-quiet btn-sm btn-icon" onClick={() => move(i, -1)} disabled={!!res || i === 0} aria-label={`Move ${it.text} up`}><ArrowUp size={14} /></button>
              <button type="button" className="btn btn-quiet btn-sm btn-icon" onClick={() => move(i, 1)} disabled={!!res || i === order.length - 1} aria-label={`Move ${it.text} down`}><ArrowDown size={14} /></button>
            </span>
          </li>
        ))}
      </ol>
      {!res && <div className="btn-row"><button type="button" className="btn btn-primary btn-sm" onClick={check}><Check size={14} aria-hidden="true" /> Check order</button></div>}
      {res && <Result ok={res.ok} note={res.note} item={item} given={order.map((it) => it.text).join(' < ')}
        answer={sorted.map((it) => `${it.text} (${fmt(it.value)})`).join(' < ')}
        onRetry={retry ? () => { reset(); setOrder(start); } : null} />}
    </div>
  );
}

// ---- odd_one_out

function OddOneOut({ item, onResult, retry = true }) {
  const opts = useMemo(() => seeded(item.options, item.id || item.prompt), [item]);
  const [pick, setPick] = useState(null);
  const choose = (opt) => { if (pick !== null) return; setPick(opt); onResult?.(opt === item.answer, opt); };
  return (
    <div className="stack-sm">
      <div className="choices">
        {opts.map((opt, i) => (
          <button key={opt} type="button" className="choice" disabled={pick !== null} aria-pressed={pick === opt}
            data-result={pick !== null ? (opt === item.answer ? 'correct' : opt === pick ? 'wrong' : undefined) : undefined}
            onClick={() => choose(opt)}>
            <span className="key">{'ABCD'[i]}</span><span><MdInline>{opt}</MdInline></span><span />
          </button>
        ))}
      </div>
      {pick !== null && <Result ok={pick === item.answer} answer={item.answer} item={item} given={pick} detail={item.why}
        onRetry={retry ? () => setPick(null) : null} />}
    </div>
  );
}

// ---- cloze

function Cloze({ item, onResult, retry = true }) {
  const parts = useMemo(() => item.text.split(new RegExp(CLOZE_GAP.source, 'g')), [item]);  // odd indices are gaps
  const [values, setValues] = useState(() => item.gaps.map(() => ''));
  const [active, setActive] = useState(0);
  const [res, done, reset] = useCheck(onResult);
  const set = (k, v) => setValues((vs) => vs.map((x, j) => (j === k ? v : x)));
  const fromBank = (w) => {
    const k = values[active] ? values.findIndex((v) => !v) : active;
    if (k < 0) return;
    set(k, w);
    const next = values.findIndex((v, j) => !v && j !== k);
    if (next >= 0) setActive(next);
  };
  const check = (e) => {
    e?.preventDefault();
    if (res) return;
    const grades = item.gaps.map((answers, k) => gradeText(values[k], answers));
    const good = grades.filter((g) => g.ok).length;
    done({ ok: good === grades.length, grades, note: good === grades.length ? '' : `${good} of ${grades.length} gaps are right.` }, values.join(' | '));
  };
  let gap = -1;
  return (
    <form className="stack-sm" onSubmit={check}>
      <div className="act-cloze">
        {parts.map((seg, i) => {
          if (i % 2 === 0) return seg ? <MdInline key={i}>{seg}</MdInline> : null;
          gap += 1;
          const k = gap;
          const g = res?.grades[k];
          return (
            <input key={i} className="input act-gap" value={values[k]} readOnly={!!res} aria-label={`Gap ${k + 1}`}
              data-result={g ? (g.ok ? 'correct' : 'wrong') : undefined}
              size={Math.max(6, Math.min(20, (item.gaps[k][0] || '').length + 2))}
              onFocus={() => setActive(k)} onChange={(e) => set(k, e.target.value)} />
          );
        })}
      </div>
      {item.bank?.length > 0 && !res && (
        <div className="act-bank" aria-label="Word bank">
          {item.bank.map((w) => (
            <button key={w} type="button" className="act-chip" disabled={values.includes(w)} onClick={() => fromBank(w)}>{w}</button>
          ))}
        </div>
      )}
      {!res && (
        <div className="btn-row">
          <button type="submit" className="btn btn-primary btn-sm" disabled={values.some((v) => !v.trim())}><Check size={14} aria-hidden="true" /> Check</button>
          <button type="button" className="btn btn-quiet btn-sm" disabled={!values.some(Boolean)} onClick={() => { setValues(item.gaps.map(() => '')); setActive(0); }}>Clear</button>
        </div>
      )}
      {res && <Result ok={res.ok} note={[res.note, ...res.grades.filter((g) => g.ok && g.note).map((g) => g.note)].filter(Boolean).join(' ')}
        item={item} given={values.join(' | ')} answer={res.ok ? '' : res.grades.map((g) => g.best).join(' | ')}
        onRetry={retry ? () => { reset(); setValues(item.gaps.map(() => '')); setActive(0); } : null} />}
    </form>
  );
}

// ---- spot_the_bug

function SpotTheBug({ item, onResult, retry = true }) {
  const lines = useMemo(() => item.code.split('\n'), [item]);
  const [pick, setPick] = useState(null);
  const [edit, setEdit] = useState(lines[item.bug_line - 1]);
  const [running, setRunning] = useState(false);
  const [run, setRun] = useState(null);
  const [showFix, setShowFix] = useState(false);
  const choose = (n) => {
    if (pick !== null) return;
    setPick(n);
    onResult?.(n === item.bug_line, `line ${n}: ${lines[n - 1].trim()}`);
  };
  const runFix = async () => {
    setRunning(true);
    setRun(null);
    const script = lines.map((l, i) => (i === item.bug_line - 1 ? edit : l)).join('\n');
    const r = await runPython(script);  // in a Web Worker in the browser, like the IDE and code exercises
    setRun(r);
    setRunning(false);
  };
  return (
    <div className="stack-sm">
      <ol className="act-code" aria-label="Code: click the line with the bug">
        {lines.map((l, i) => {
          const n = i + 1;
          return (
            <li key={n}>
              <button type="button" className="act-code-line" disabled={pick !== null || !l.trim()}
                data-result={pick !== null ? (n === item.bug_line ? 'correct' : n === pick ? 'wrong' : undefined) : undefined}
                onClick={() => choose(n)} aria-label={`Line ${n}: ${l.trim()}`}>
                <span className="act-code-n">{n}</span><code>{l || ' '}</code>
              </button>
            </li>
          );
        })}
      </ol>
      {pick !== null && (
        <>
          <Result ok={pick === item.bug_line} item={item} given={`line ${pick}: ${lines[pick - 1].trim()}`}
            answer={`line ${item.bug_line}: \`${lines[item.bug_line - 1].trim()}\``}
            onRetry={retry ? () => { setPick(null); setRun(null); setShowFix(false); } : null} />
          <div className="act-fix stack-sm">
            <label className="hint" htmlFor={`fix-${item.id}`}>Fix line {item.bug_line} and run the program</label>
            <input id={`fix-${item.id}`} className="input act-fix-input" spellCheck={false} value={edit} onChange={(e) => setEdit(e.target.value)} />
            <div className="btn-row">
              <button type="button" className="btn btn-primary btn-sm" onClick={runFix} disabled={running}>
                {running ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <Play size={14} aria-hidden="true" />}
                {running ? ' Running…' : ' Run the fix'}
              </button>
              {item.fix && <button type="button" className="btn btn-quiet btn-sm" aria-expanded={showFix} onClick={() => setShowFix((v) => !v)}>{showFix ? 'Hide the fix' : 'Show the fix'}</button>}
              <span className="hint">Runs in your browser; the first run loads Python (a few seconds).</span>
            </div>
            {showFix && <pre className="code-tests">{item.fix}</pre>}
            {run && (
              <div className={`feedback ${run.ok ? 'ok' : 'bad'}`} aria-live="polite">
                <p style={{ fontWeight: 700, marginBottom: 4 }}>{run.ok ? 'It ran without errors.' : run.timedOut ? 'Stopped.' : 'It raised an error.'}</p>
                {(run.output || run.error) && <pre className="code-tests">{[run.output, run.error].filter(Boolean).join('\n').trim()}</pre>}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export const GENERAL_RENDER = { label_diagram: LabelDiagram, sort_by: SortBy, odd_one_out: OddOneOut, cloze: Cloze, spot_the_bug: SpotTheBug };

export const GENERAL_LABEL = {
  label_diagram: 'Label the diagram', sort_by: 'Put them in order', odd_one_out: 'Odd one out',
  cloze: 'Fill the gaps', spot_the_bug: 'Spot the bug',
};
