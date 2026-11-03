import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { LineChart, NotebookPen, Sigma, Plus, X, Loader2, Crosshair } from 'lucide-react';
import { tryCompile, RESERVED_NAMES } from '../lib/expr';
import { canvasPalette } from '../theme';
import { api } from '../lib/api';
import Md from './Md';
import PracticeDeck from './PracticeDeck';

const TABS = [
  { id: 'graph', label: 'Graph', icon: LineChart },
  { id: 'notebook', label: 'Notebook', icon: NotebookPen },
  { id: 'practice', label: 'Practice', icon: Sigma },
];
const CURVE_TOKENS = ['accent', 'gold-text', 'info', 'bad', 'plum', 'ink-soft'];

const store = {
  get(key, fallback) { try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ } },
};

/** "y = 2x sin(x)" -> "2*x*sin(x)": strip a "y =" / "f(x) =" prefix and add the multiplications people leave out. */
export function normalizeFormula(src) {
  return String(src || '')
    .replace(/^\s*(?:y|[a-zA-Z]\s*\(\s*x\s*\))\s*=/, '')
    .replace(/(\d)(?![eE][+-]?\d)\s*([A-Za-z(])/g, '$1*$2')
    .replace(/\)\s*([A-Za-z0-9(])/g, ')*$1')
    // "k x" and "x(x+1)": a variable next to a variable or a bracket multiplies; "sin (x)" stays a call
    .replace(/([A-Za-z_][A-Za-z0-9_]*)(\s*)(?=[A-Za-z_(])/g, (m, name, space, offset, all) => {
      const next = all[offset + m.length];
      if (RESERVED_NAMES.has(name)) return next === '(' ? name : m;
      return next === '(' || space ? `${name}*` : m;
    })
    .trim();
}

/** Free variables other than x: each becomes a slider. */
export function freeVariables(src) {
  const names = new Set();
  const re = /[A-Za-z_][A-Za-z0-9_]*/g;
  src = src.replace(/(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?/g, ' '); // numbers like 1e3 hold no variables
  let m;
  while ((m = re.exec(src))) {
    const after = src.slice(re.lastIndex).trimStart();
    if (after.startsWith('(') && RESERVED_NAMES.has(m[0])) continue; // function call
    if (m[0] === 'x' || m[0] === 'e' || RESERVED_NAMES.has(m[0])) continue;
    names.add(m[0]);
  }
  return [...names];
}

function niceStep(span) {
  const raw = span / 14;
  const p = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 5, 10].map((k) => k * p).find((s) => s >= raw) || p * 10;
}

function GraphTab({ userId }) {
  const key = `andedu_math_graph_${userId}`;
  const [rows, setRows] = useState(() => store.get(key, { list: ['sin(x)', 'a*x^2 + b'], params: {} }));
  const [view, setView] = useState({ cx: 0, cy: 0, scale: 50 }); // px per unit
  const [hover, setHover] = useState(null);
  const canvasRef = useRef(null);
  const dragRef = useRef(null);

  useEffect(() => { store.set(key, rows); }, [key, rows]);

  const curves = useMemo(() => rows.list.map((text) => {
    const src = normalizeFormula(text);
    const [fn, err] = src ? tryCompile(src, NaN) : [() => NaN, null];
    return { text, src, fn, err, vars: err ? [] : freeVariables(src) };
  }), [rows.list]);
  const vars = useMemo(() => [...new Set(curves.flatMap((c) => c.vars))], [curves]);
  const param = (n) => rows.params[n] || { value: 1, min: -5, max: 5 };
  const scopeBase = useMemo(() => {
    const s = { e: Math.E };
    for (const n of vars) s[n] = (rows.params[n] || { value: 1 }).value;
    return s;
  }, [vars, rows.params]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const W = canvas.clientWidth, H = canvas.clientHeight;
    if (canvas.width !== W * dpr || canvas.height !== H * dpr) { canvas.width = W * dpr; canvas.height = H * dpr; }
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const pal = canvasPalette();
    const { cx, cy, scale } = view;
    const toX = (x) => W / 2 + (x - cx) * scale;
    const toY = (y) => H / 2 - (y - cy) * scale;
    const fromX = (px) => cx + (px - W / 2) / scale;

    ctx.fillStyle = pal.surface; ctx.fillRect(0, 0, W, H);
    // grid + labels
    const step = niceStep(W / scale);
    const x0 = fromX(0), x1 = fromX(W), y0 = cy - H / 2 / scale, y1 = cy + H / 2 / scale;
    ctx.lineWidth = 1; ctx.font = '11px "IBM Plex Mono", monospace'; ctx.fillStyle = pal.muted;
    const fmt = (v) => (Math.abs(v) < 1e-9 ? '0' : Number(v.toPrecision(6)).toString());
    for (let gx = Math.ceil(x0 / step) * step; gx <= x1; gx += step) {
      ctx.strokeStyle = pal.rule; ctx.beginPath(); ctx.moveTo(toX(gx), 0); ctx.lineTo(toX(gx), H); ctx.stroke();
      ctx.textAlign = 'center'; ctx.fillText(fmt(gx), toX(gx), Math.min(H - 4, Math.max(12, toY(0) + 14)));
    }
    for (let gy = Math.ceil(y0 / step) * step; gy <= y1; gy += step) {
      ctx.strokeStyle = pal.rule; ctx.beginPath(); ctx.moveTo(0, toY(gy)); ctx.lineTo(W, toY(gy)); ctx.stroke();
      if (Math.abs(gy) > 1e-9) { ctx.textAlign = 'left'; ctx.fillText(fmt(gy), Math.min(W - 40, Math.max(4, toX(0) + 4)), toY(gy) - 3); }
    }
    ctx.strokeStyle = pal.ink; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(0, toY(0)); ctx.lineTo(W, toY(0)); ctx.moveTo(toX(0), 0); ctx.lineTo(toX(0), H); ctx.stroke();

    // curves: one sample per pixel, broken at gaps and vertical asymptotes
    curves.forEach((c, i) => {
      if (c.err || !c.src) return;
      ctx.strokeStyle = pal[CURVE_TOKENS[i % CURVE_TOKENS.length]]; ctx.lineWidth = 2.5;
      ctx.beginPath();
      let pen = false, lastY = null;
      for (let px = 0; px <= W; px += 1) {
        const y = c.fn({ ...scopeBase, x: fromX(px) });
        const py = toY(y);
        if (!Number.isFinite(y) || (lastY !== null && Math.abs(py - lastY) > H * 2)) { pen = false; lastY = Number.isFinite(y) ? py : null; continue; }
        if (pen) ctx.lineTo(px, py); else { ctx.moveTo(px, py); pen = true; }
        lastY = py;
      }
      ctx.stroke();
    });

    if (hover) {
      ctx.strokeStyle = pal.gold; ctx.setLineDash([4, 4]); ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(hover.px, 0); ctx.lineTo(hover.px, H); ctx.stroke(); ctx.setLineDash([]);
      curves.forEach((c, i) => {
        if (c.err || !c.src) return;
        const y = c.fn({ ...scopeBase, x: hover.x });
        if (!Number.isFinite(y)) return;
        ctx.fillStyle = pal[CURVE_TOKENS[i % CURVE_TOKENS.length]];
        ctx.beginPath(); ctx.arc(hover.px, toY(y), 4, 0, Math.PI * 2); ctx.fill();
      });
    }
  }, [view, curves, scopeBase, hover]);

  useEffect(() => { draw(); }, [draw]);
  useEffect(() => {
    const ro = new ResizeObserver(() => draw());
    if (canvasRef.current) ro.observe(canvasRef.current);
    return () => ro.disconnect();
  }, [draw]);

  // wheel zoom around the cursor (non-passive so the page doesn't scroll)
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const onWheel = (e) => {
      e.preventDefault();
      const r = canvas.getBoundingClientRect();
      setView((v) => {
        const k = Math.exp(-e.deltaY * 0.0015);
        const scale = Math.min(5000, Math.max(2, v.scale * k));
        const mx = v.cx + (e.clientX - r.left - r.width / 2) / v.scale;
        const my = v.cy - (e.clientY - r.top - r.height / 2) / v.scale;
        return { scale, cx: mx - (mx - v.cx) * (v.scale / scale), cy: my - (my - v.cy) * (v.scale / scale) };
      });
    };
    canvas.addEventListener('wheel', onWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', onWheel);
  }, []);

  const onPointerMove = (e) => {
    const r = canvasRef.current.getBoundingClientRect();
    const px = e.clientX - r.left;
    if (dragRef.current) {
      const d = dragRef.current;
      setView((v) => ({ ...v, cx: d.cx - (e.clientX - d.x) / v.scale, cy: d.cy + (e.clientY - d.y) / v.scale }));
    }
    setHover({ px, x: view.cx + (px - r.width / 2) / view.scale });
  };

  const setList = (list) => setRows((r) => ({ ...r, list }));
  const setParam = (n, patch) => setRows((r) => ({ ...r, params: { ...r.params, [n]: { ...param(n), ...patch } } }));

  return (
    <div className="math-graph">
      <div className="stack-sm math-side">
        {curves.map((c, i) => (
          <div key={i} className="formula-row">
            <span className="swatch" style={{ background: `var(--${CURVE_TOKENS[i % CURVE_TOKENS.length]})` }} aria-hidden="true" />
            <label className="sr-only" htmlFor={`f-${i}`}>Function {i + 1}</label>
            <input id={`f-${i}`} className="input mono" value={c.text} spellCheck={false} placeholder="e.g. x^3 - 2x"
              onChange={(e) => setList(rows.list.map((t, j) => (j === i ? e.target.value : t)))} aria-invalid={Boolean(c.err)} />
            <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label={`Remove function ${i + 1}`}
              onClick={() => setList(rows.list.filter((_, j) => j !== i))}><X size={14} /></button>
            {c.err && <span className="hint err">{c.err.replace(/ in ".*"$/, '')}</span>}
            {hover && !c.err && c.src && (
              <span className="hint mono">f({Number(hover.x.toPrecision(4))}) = {Number(c.fn({ ...scopeBase, x: hover.x }).toPrecision(5))}</span>
            )}
          </div>
        ))}
        {rows.list.length < 6 && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => setList([...rows.list, ''])}>
            <Plus size={14} aria-hidden="true" /> Add function
          </button>
        )}

        {vars.length > 0 && <h3 className="label" style={{ marginTop: 'var(--space-3)' }}>Sliders</h3>}
        {vars.map((n) => {
          const p = param(n);
          return (
            <div key={n} className="slider">
              <label htmlFor={`v-${n}`}><span className="mono">{n}</span><b className="num">{p.value}</b></label>
              <input id={`v-${n}`} type="range" min={p.min} max={p.max} step={(p.max - p.min) / 200} value={p.value}
                onChange={(e) => setParam(n, { value: Number(Number(e.target.value).toPrecision(4)) })} />
              <div className="range-edit">
                <input className="input num" aria-label={`${n} minimum`} type="number" value={p.min} onChange={(e) => setParam(n, { min: Number(e.target.value) })} />
                <input className="input num" aria-label={`${n} maximum`} type="number" value={p.max} onChange={(e) => setParam(n, { max: Number(e.target.value) })} />
              </div>
            </div>
          );
        })}
        <p className="hint">Write in x, like <code>2x^2 - 3</code> or <code>sin(k x)</code>. Any other letter becomes a slider.
          Scroll to zoom, drag to pan.</p>
        <button type="button" className="btn btn-quiet btn-sm" onClick={() => setView({ cx: 0, cy: 0, scale: 50 })}>
          <Crosshair size={14} aria-hidden="true" /> Reset view
        </button>
      </div>
      <canvas ref={canvasRef} className="math-canvas" aria-label="Graph of the functions"
        onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); dragRef.current = { x: e.clientX, y: e.clientY, cx: view.cx, cy: view.cy }; }}
        onPointerUp={() => { dragRef.current = null; }} onPointerMove={onPointerMove} onPointerLeave={() => setHover(null)} />
    </div>
  );
}

const SNIPPETS = [
  ['a/b', '\\frac{a}{b}'], ['√', '\\sqrt{x}'], ['xⁿ', 'x^{n}'], ['∫', '\\int_{a}^{b} f(x)\\,dx'], ['Σ', '\\sum_{k=1}^{n} k'],
  ['lim', '\\lim_{x \\to 0} '], ['d/dx', '\\frac{d}{dx}'], ['matrix', '\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}'],
];
const STARTER = '# My notes\n\nThe quadratic formula:\n\n$$x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}$$\n\nInline math works too: $e^{i\\pi} + 1 = 0$.\n';

function NotebookTab({ userId }) {
  const key = `andedu_math_notes_${userId}`;
  const [text, setText] = useState(() => store.get(key, STARTER));
  const taRef = useRef(null);
  useEffect(() => { const t = setTimeout(() => store.set(key, text), 300); return () => clearTimeout(t); }, [key, text]);

  const insert = (snippet) => {
    const ta = taRef.current;
    const a = ta?.selectionStart ?? text.length, b = ta?.selectionEnd ?? text.length;
    const wrapped = `$${snippet}$`;
    setText(text.slice(0, a) + wrapped + text.slice(b));
    requestAnimationFrame(() => { ta?.focus(); ta?.setSelectionRange(a + wrapped.length, a + wrapped.length); });
  };

  return (
    <div className="stack">
      <div className="btn-row" role="toolbar" aria-label="Insert math">
        {SNIPPETS.map(([label, s]) => (
          <button key={label} type="button" className="btn btn-quiet btn-sm mono" onClick={() => insert(s)} title={s}>{label}</button>
        ))}
      </div>
      <div className="math-notebook">
        <div className="field">
          <label htmlFor="nb-src">Markdown and LaTeX (saved on this device)</label>
          <textarea id="nb-src" ref={taRef} className="textarea mono" value={text} spellCheck={false} onChange={(e) => setText(e.target.value)} />
        </div>
        <div className="field">
          <span className="label">Preview</span>
          <div className="panel prose math-preview"><Md>{text}</Md></div>
        </div>
      </div>
    </div>
  );
}

const IDEAS = ['Derivatives with the chain rule', 'Solving quadratic equations', 'Definite integrals', 'Logarithm laws', 'Matrix multiplication', 'Probability with combinations'];

function PracticeTab() {
  const [topic, setTopic] = useState('');
  const [level, setLevel] = useState('high school');
  const [set, setSet] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const generate = async (t = topic) => {
    if (!t.trim()) return;
    setTopic(t); setBusy(true); setError(null);
    try {
      setSet(await api('/api/math/practice', { method: 'POST', body: { topic: t.trim(), level, count: 6 } }));
    } catch (e) { setError(e.message); }
    setBusy(false);
  };

  return (
    <div className="stack">
      <form className="btn-row" style={{ alignItems: 'flex-end' }} onSubmit={(e) => { e.preventDefault(); generate(); }}>
        <div className="field" style={{ flex: '1 1 280px' }}>
          <label htmlFor="mp-topic">What do you want to practise?</label>
          <input id="mp-topic" className="input" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. implicit differentiation" />
        </div>
        <div className="field" style={{ width: 190 }}>
          <label htmlFor="mp-level">Level</label>
          <select id="mp-level" className="input" value={level} onChange={(e) => setLevel(e.target.value)}>
            <option value="middle school">Middle school</option>
            <option value="high school">High school</option>
            <option value="AP / first-year university">AP / first year</option>
            <option value="upper university">Upper university</option>
          </select>
        </div>
        <button type="submit" className="btn btn-gold" disabled={busy || !topic.trim()}>
          {busy ? <><Loader2 size={16} className="spin" aria-hidden="true" /> Writing problems</> : 'Generate problems'}
        </button>
      </form>
      {!set && !busy && (
        <div className="btn-row">
          {IDEAS.map((t) => <button key={t} type="button" className="btn btn-quiet btn-sm" onClick={() => generate(t)}>{t}</button>)}
        </div>
      )}
      {error && <p className="notice notice-bad" role="alert">{error}</p>}
      {set && (
        <>
          <p className="hint">
            {set.title}. Every numeric answer was recomputed before you see it
            {set.dropped ? `; ${set.dropped} problem${set.dropped > 1 ? 's' : ''} failed that check and were left out` : ''}.
          </p>
          <PracticeDeck key={set.title + set.items.length} items={set.items} />
        </>
      )}
    </div>
  );
}

/** Math workspace: graphing with sliders, a LaTeX notebook and checked practice. */
export default function MathLab({ user }) {
  const [tab, setTab] = useState(() => store.get('andedu_math_tab', 'graph'));
  useEffect(() => { store.set('andedu_math_tab', tab); }, [tab]);
  return (
    <div className="page page-wide">
      <div className="page-head">
        <div>
          <h1>Math</h1>
          <p>Graph functions with live sliders, write notes in LaTeX, and practise with answers that are checked by computation.</p>
        </div>
      </div>
      <div className="tabs" role="tablist" aria-label="Math tools">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button key={id} type="button" role="tab" id={`mt-${id}`} aria-selected={tab === id} aria-controls={`mp-${id}`}
            className="tab" onClick={() => setTab(id)}><Icon size={16} aria-hidden="true" /> {label}</button>
        ))}
      </div>
      <section role="tabpanel" id={`mp-${tab}`} aria-labelledby={`mt-${tab}`}>
        {tab === 'graph' && <GraphTab userId={user.id} />}
        {tab === 'notebook' && <NotebookTab userId={user.id} />}
        {tab === 'practice' && <PracticeTab />}
      </section>
    </div>
  );
}
