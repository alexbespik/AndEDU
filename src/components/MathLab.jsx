import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  LineChart, NotebookPen, Sigma, Plus, X, Loader2, Crosshair, BookOpen,
  GraduationCap, Shapes, ZoomIn, ZoomOut, Keyboard,
} from 'lucide-react';
import { tryCompile, CONSTS, FUNCS, RESERVED_NAMES } from '../lib/expr';
import { canvasPalette } from '../theme';
import { api } from '../lib/api';
import { reportXp } from '../lib/engage';
import Md from './Md';
import PracticeDeck from './PracticeDeck';
import MathSim from '../simulations/MathSim';

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
    // "k x" and "x(x+1)": a variable or constant next to a variable or bracket multiplies; functions stay calls
    .replace(/([A-Za-z_][A-Za-z0-9_]*)(\s*)(?=[A-Za-z_(])/g, (m, name, space, offset, all) => {
      const next = all[offset + m.length];
      if (Object.hasOwn(FUNCS, name) || name === 'if') return next === '(' ? name : m;
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
    if (m[0] === 'x' || RESERVED_NAMES.has(m[0])) continue;
    names.add(m[0]);
  }
  return [...names];
}

// ---- numeric analysis on a compiled f(x) ----
const dfdx = (f, x) => { const h = 1e-5 * Math.max(1, Math.abs(x)); return (f(x + h) - f(x - h)) / (2 * h); };

function bisect(g, a, b) {
  let ga = g(a);
  for (let k = 0; k < 60; k++) {
    const m = (a + b) / 2, gm = g(m);
    if (!Number.isFinite(gm)) return null;
    if (gm === 0) return m;
    if ((ga < 0) === (gm < 0)) { a = m; ga = gm; } else b = m;
  }
  return (a + b) / 2;
}

/** Sign changes of g on [x0, x1]; poles (where |f| blows up) are not reported as roots. */
function signChanges(g, x0, x1, check, n = 600) {
  const out = [];
  let px = x0, pv = g(x0);
  for (let i = 1; i <= n; i++) {
    const x = x0 + ((x1 - x0) * i) / n, v = g(x);
    if (Number.isFinite(pv) && Number.isFinite(v)) {
      if (v === 0) out.push(x);
      else if ((pv < 0) !== (v < 0) && pv !== 0) {
        const r = bisect(g, px, x);
        if (r !== null && check(r)) out.push(r);
      }
    }
    px = x; pv = v;
  }
  return out.filter((r, i) => i === 0 || Math.abs(r - out[i - 1]) > (x1 - x0) / n);
}

export function analyze(f, x0, x1) {
  const span = x1 - x0;
  const roots = signChanges(f, x0, x1, (r) => Math.abs(f(r)) < 1e-6 * (1 + span));
  const d = (x) => dfdx(f, x);
  const extrema = signChanges(d, x0, x1, (r) => Number.isFinite(f(r)) && Math.abs(d(r)) < 1e-3 * (1 + Math.abs(f(r))))
    .map((x) => ({ x, y: f(x), kind: dfdx(d, x) > 0 ? 'min' : 'max' }));
  return { roots, extrema, y0: f(0) };
}

export function integrate(f, a, b, n = 2000) {
  if (a === b) return 0;
  const h = (b - a) / n;
  let sum = f(a) + f(b);
  for (let i = 1; i < n; i++) sum += f(a + i * h) * (i % 2 ? 4 : 2);
  return (sum * h) / 3;
}

const EXAMPLES = [
  ['Parabola', ['a*(x - h)^2 + k']],
  ['Waves', ['A*sin(w*x)', 'A*cos(w*x)']],
  ['Growth & decay', ['exp(r*x)', 'exp(-r*x)']],
  ['Asymptotes', ['1/(x - a)', '(x^2 - 1)/(x^2 - 4)']],
  ['Normal curve', ['exp(-(x - m)^2 / (2*s^2)) / (s*sqrt(2*pi))']],
  ['Polynomial', ['x^3 - 3x + c']],
];

function niceStep(span) {
  const raw = span / 14;
  const p = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 5, 10].map((k) => k * p).find((s) => s >= raw) || p * 10;
}

export function MathKeypad({ onInsert, onBackspace, onClose }) {
  const [tab, setTab] = useState('123');

  const keys123 = [
    '7', '8', '9', '/', '(', ')',
    '4', '5', '6', '*', '^', 'x',
    '1', '2', '3', '-', 'pi', 'y',
    '0', '.', ',', '+', 'e', '⌫',
  ];

  const keysTrig = [
    'sin', 'cos', 'tan', 'csc', 'sec', 'cot',
    'asin', 'acos', 'atan', 'acsc', 'asec', 'acot',
    'sinh', 'cosh', 'tanh', 'csch', 'sech', 'coth',
  ];

  const keysFunc = [
    'sqrt', 'cbrt', 'nthroot', 'abs', 'round', 'clamp',
    'ln', 'log', 'log10', 'mod', 'gcd', 'lcm',
    'fact', 'nCr', 'nPr', 'erf', 'gamma', 'sinc',
  ];

  const currentKeys = tab === '123' ? keys123 : tab === 'Trig' ? keysTrig : keysFunc;

  const handleKey = (k) => {
    if (k === '⌫') {
      onBackspace();
    } else {
      const isFunc = (tab === 'Trig' || tab === 'Func') && !['pi', 'e', 'x', 'y'].includes(k);
      onInsert(isFunc ? `${k}(` : k);
    }
  };

  return (
    <div className="math-keypad" role="region" aria-label="Math Virtual Keypad">
      <div className="keypad-header">
        <div className="keypad-tabs">
          <button type="button" className={`keypad-tab-btn ${tab === '123' ? 'active' : ''}`}
            onMouseDown={(e) => { e.preventDefault(); setTab('123'); }}>123</button>
          <button type="button" className={`keypad-tab-btn ${tab === 'Trig' ? 'active' : ''}`}
            onMouseDown={(e) => { e.preventDefault(); setTab('Trig'); }}>Trig</button>
          <button type="button" className={`keypad-tab-btn ${tab === 'Func' ? 'active' : ''}`}
            onMouseDown={(e) => { e.preventDefault(); setTab('Func'); }}>Func</button>
        </div>
        {onClose && (
          <button type="button" className="btn btn-quiet btn-sm btn-icon" title="Close keypad"
            onMouseDown={(e) => { e.preventDefault(); onClose(); }} aria-label="Close keypad">
            <X size={14} />
          </button>
        )}
      </div>
      <div className="keypad-grid">
        {currentKeys.map((k) => (
          <button key={k} type="button" className={`keypad-btn ${k === '⌫' ? 'action' : ''}`}
            onMouseDown={(e) => { e.preventDefault(); handleKey(k); }} aria-label={k === '⌫' ? 'Backspace' : k}>
            {k}
          </button>
        ))}
      </div>
    </div>
  );
}

export function ValuesTable({ curveName, color, tableConfig, setTableConfig, tableRows }) {
  const [newX, setNewX] = useState('');

  const addCustomPoint = (e) => {
    e.preventDefault();
    if (newX.trim() !== '' && Number.isFinite(Number(newX))) {
      const val = Number(newX.trim());
      setTableConfig((prev) => ({
        ...prev,
        custom: [...(prev.custom || []), val],
      }));
      setNewX('');
    }
  };

  const removeCustomPoint = (xVal) => {
    setTableConfig((prev) => ({
      ...prev,
      custom: (prev.custom || []).filter((x) => x !== xVal),
    }));
  };

  return (
    <div className="values-table-container">
      <div className="values-table-controls">
        <span className="swatch" style={{ background: `var(--${color})` }} aria-hidden="true" />
        <span className="label" style={{ fontWeight: 600 }}>Table of values: <span className="mono">{curveName}</span></span>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginLeft: 'auto', flexWrap: 'wrap' }}>
          <label className="hint" htmlFor="vt-start">From</label>
          <input id="vt-start" className="input num" style={{ width: 54, padding: '2px 4px' }} type="number"
            value={tableConfig.start ?? -5}
            onChange={(e) => setTableConfig((c) => ({ ...c, start: Number(e.target.value) }))} />
          <label className="hint" htmlFor="vt-end">To</label>
          <input id="vt-end" className="input num" style={{ width: 54, padding: '2px 4px' }} type="number"
            value={tableConfig.end ?? 5}
            onChange={(e) => setTableConfig((c) => ({ ...c, end: Number(e.target.value) }))} />
          <label className="hint" htmlFor="vt-step">Step</label>
          <input id="vt-step" className="input num" style={{ width: 50, padding: '2px 4px' }} type="number" min="0.01" step="any"
            value={tableConfig.step ?? 1}
            onChange={(e) => setTableConfig((c) => ({ ...c, step: Math.max(0.01, Math.abs(Number(e.target.value)) || 1) }))} />
        </div>
      </div>
      <form onSubmit={addCustomPoint} className="btn-row" style={{ alignItems: 'center', gap: 'var(--space-2)' }}>
        <input className="input mono" style={{ width: 110, padding: '2px 6px', minHeight: 28 }} placeholder="Add x point" value={newX}
          onChange={(e) => setNewX(e.target.value)} />
        <button type="submit" className="btn btn-quiet btn-sm" style={{ minHeight: 28 }}><Plus size={13} /> Add point</button>
        {tableConfig.custom?.length > 0 && (
          <button type="button" className="btn btn-quiet btn-sm" style={{ minHeight: 28 }}
            onClick={() => setTableConfig((c) => ({ ...c, custom: [] }))}>
            Reset custom
          </button>
        )}
      </form>
      <div className="values-table-scroll">
        <table className="values-table">
          <thead>
            <tr>
              <th style={{ width: '40%' }}>x</th>
              <th style={{ width: '45%' }}>y = f(x)</th>
              <th style={{ width: '15%' }}></th>
            </tr>
          </thead>
          <tbody>
            {tableRows.map((r, i) => (
              <tr key={i}>
                <td className="mono">{r.x}</td>
                <td className="mono">{Number.isFinite(r.y) ? r.y : 'undefined'}</td>
                <td style={{ textAlign: 'right' }}>
                  {r.isCustom && (
                    <button type="button" className="btn btn-quiet btn-sm btn-icon" title="Remove custom point"
                      onClick={() => removeCustomPoint(r.x)}>
                      <X size={12} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function GraphTab({ userId, incoming }) {
  const key = `andedu_math_graph_${userId}`;
  const [rows, setRows] = useState(() => store.get(key, { list: ['sin(x)', 'a*x^2 + b'], params: {} }));
  useEffect(() => {  // functions sent by the assistant replace the current list
    if (!incoming?.functions?.length) return;
    setRows((r) => ({ list: incoming.functions, params: { ...r.params, ...Object.fromEntries(Object.entries(incoming.params || {}).map(([k, v]) => [k, { value: v, min: Math.min(-5, v * 2), max: Math.max(5, v * 2) }])) } }));
  }, [incoming]);
  const [view, setView] = useState({ cx: 0, cy: 0, scale: 50 }); // px per unit
  const [hover, setHover] = useState(null);
  const [size, setSize] = useState({ W: 800, H: 600 });
  const [tools, setTools] = useState(() => store.get(`${key}_tools`, { sel: 0, deriv: false, tangent: true, area: false, table: false, a: 0, b: 1 }));
  const [calc, setCalc] = useState('');
  const [showKeypad, setShowKeypad] = useState(false);
  const [tableConfig, setTableConfig] = useState(() => store.get(`${key}_table`, { start: -5, end: 5, step: 1, custom: [] }));
  const canvasRef = useRef(null);
  const dragRef = useRef(null);
  const lastFocusedRef = useRef(null);

  useEffect(() => { store.set(key, rows); }, [key, rows]);
  useEffect(() => { store.set(`${key}_tools`, tools); }, [key, tools]);
  useEffect(() => { store.set(`${key}_table`, tableConfig); }, [key, tableConfig]);

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

  const sel = curves[tools.sel] && !curves[tools.sel].err && curves[tools.sel].src ? tools.sel : curves.findIndex((c) => !c.err && c.src);
  const selFn = useMemo(() => (sel >= 0 ? (x) => curves[sel].fn({ ...scopeBase, x }) : null), [sel, curves, scopeBase]);
  const xRange = [view.cx - size.W / 2 / view.scale, view.cx + size.W / 2 / view.scale];
  const facts = useMemo(() => (selFn ? analyze(selFn, xRange[0], xRange[1]) : null), [selFn, xRange[0], xRange[1]]); // eslint-disable-line react-hooks/exhaustive-deps
  const area = useMemo(() => (selFn && tools.area ? integrate(selFn, Number(tools.a), Number(tools.b)) : null), [selFn, tools.area, tools.a, tools.b]);

  const tableRows = useMemo(() => {
    if (!selFn) return [];
    const start = Number(tableConfig.start ?? -5);
    const end = Number(tableConfig.end ?? 5);
    const step = Math.max(0.0001, Math.abs(Number(tableConfig.step) || 1));
    const rowsList = [];
    if (Number.isFinite(start) && Number.isFinite(end) && start <= end) {
      const count = Math.min(101, Math.floor((end - start) / step + 1e-9) + 1);
      for (let k = 0; k < count; k++) {
        const x = Number((start + k * step).toFixed(6));
        rowsList.push({ x, isCustom: false });
      }
    }
    (tableConfig.custom || []).forEach((c) => {
      const x = Number(c);
      if (Number.isFinite(x) && !rowsList.some((r) => Math.abs(r.x - x) < 1e-9)) {
        rowsList.push({ x, isCustom: true });
      }
    });
    rowsList.sort((a, b) => a.x - b.x);
    return rowsList.map((r) => {
      const y = selFn(r.x);
      return { ...r, y: Number.isFinite(y) ? Number(y.toPrecision(6)) : NaN };
    });
  }, [selFn, tableConfig]);

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

    if (selFn) {
      const color = pal[CURVE_TOKENS[sel % CURVE_TOKENS.length]];
      // shaded area from a to b
      if (tools.area) {
        const a = Number(tools.a), b = Number(tools.b);
        ctx.fillStyle = pal.gold; ctx.globalAlpha = 0.25;
        ctx.beginPath(); ctx.moveTo(toX(a), toY(0));
        for (let i = 0; i <= 300; i++) { const x = a + ((b - a) * i) / 300, y = selFn(x); if (Number.isFinite(y)) ctx.lineTo(toX(x), toY(y)); }
        ctx.lineTo(toX(b), toY(0)); ctx.closePath(); ctx.fill(); ctx.globalAlpha = 1;
      }
      // derivative, dashed in the curve's color
      if (tools.deriv) {
        ctx.strokeStyle = color; ctx.lineWidth = 1.8; ctx.setLineDash([6, 5]); ctx.beginPath();
        let pen = false;
        for (let px = 0; px <= W; px += 2) {
          const y = dfdx(selFn, fromX(px));
          if (!Number.isFinite(y) || Math.abs(y) > 1e6) { pen = false; continue; }
          if (pen) ctx.lineTo(px, toY(y)); else { ctx.moveTo(px, toY(y)); pen = true; }
        }
        ctx.stroke(); ctx.setLineDash([]);
      }
      // discrete table points
      if (tools.table && tableRows.length) {
        ctx.font = '10px "IBM Plex Mono", monospace';
        ctx.textAlign = 'left';
        tableRows.forEach(({ x, y }) => {
          if (!Number.isFinite(y)) return;
          const px = toX(x), py = toY(y);
          if (px < -30 || px > W + 30 || py < -30 || py > H + 30) return;
          ctx.beginPath();
          ctx.arc(px, py, 4.5, 0, Math.PI * 2);
          ctx.fillStyle = color;
          ctx.fill();
          ctx.lineWidth = 1.5;
          ctx.strokeStyle = pal.surface;
          ctx.stroke();

          ctx.fillStyle = pal.ink;
          ctx.fillText(`(${fmt(x)}, ${fmt(y)})`, px + 6, py - 6);
        });
      }
      // roots and turning points
      if (facts) {
        ctx.font = '11px "IBM Plex Mono", monospace'; ctx.textAlign = 'left';
        for (const r of facts.roots) {
          ctx.fillStyle = pal.gold; ctx.beginPath(); ctx.arc(toX(r), toY(0), 5, 0, Math.PI * 2); ctx.fill();
          ctx.fillStyle = pal['gold-text']; ctx.fillText(fmt(Number(r.toFixed(4))), toX(r) + 6, toY(0) - 7);
        }
        for (const p of facts.extrema) {
          ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.fillStyle = pal.surface;
          ctx.beginPath(); ctx.arc(toX(p.x), toY(p.y), 5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
          ctx.fillStyle = pal.ink; ctx.fillText(`${p.kind} (${fmt(Number(p.x.toFixed(3)))}, ${fmt(Number(p.y.toFixed(3)))})`, toX(p.x) + 7, toY(p.y) + (p.kind === 'max' ? -8 : 16));
        }
      }
      // tangent line at the cursor
      if (tools.tangent && hover) {
        const y = selFn(hover.x), m = dfdx(selFn, hover.x);
        if (Number.isFinite(y) && Number.isFinite(m)) {
          const L = (W / scale) * 0.18;
          ctx.strokeStyle = pal.ink; ctx.lineWidth = 1.5; ctx.beginPath();
          ctx.moveTo(toX(hover.x - L), toY(y - m * L)); ctx.lineTo(toX(hover.x + L), toY(y + m * L)); ctx.stroke();
          ctx.fillStyle = pal.ink; ctx.font = '11px "IBM Plex Mono", monospace'; ctx.textAlign = 'left';
          ctx.fillText(`slope ${fmt(Number(m.toPrecision(4)))}`, toX(hover.x) + 8, toY(y) + 18);
        }
      }
    }

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
  }, [view, curves, scopeBase, hover, selFn, sel, tools, facts, tableRows]);

  useEffect(() => { draw(); }, [draw]);
  useEffect(() => {
    const ro = new ResizeObserver(() => {
      const c = canvasRef.current;
      if (c) setSize((sz) => (sz.W === c.clientWidth && sz.H === c.clientHeight ? sz : { W: c.clientWidth, H: c.clientHeight }));
      draw();
    });
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

  const calcResult = useMemo(() => {
    const src = normalizeFormula(calc);
    if (!src) return null;
    const [fn, err] = tryCompile(src, NaN);
    if (err) return { err: err.replace(/ in ".*"$/, '') };
    const v = fn({ ...scopeBase, x: hover ? hover.x : 0 });
    return Number.isFinite(v) ? { v: Number(v.toPrecision(10)) } : { err: 'Not a finite number' };
  }, [calc, scopeBase, hover]);

  const setList = (list) => setRows((r) => ({ ...r, list }));
  const setTool = (patch) => setTools((t) => ({ ...t, ...patch }));
  const fmtN = (v) => Number(Number(v).toPrecision(5));
  const setParam = (n, patch) => setRows((r) => ({ ...r, params: { ...r.params, [n]: { ...param(n), ...patch } } }));

  const insertAtCursor = useCallback((text) => {
    const el = (lastFocusedRef.current?.isConnected ? lastFocusedRef.current : null) || document.getElementById('f-0') || document.getElementById('m-calc');
    if (!el) return;
    const start = el.selectionStart ?? el.value.length;
    const end = el.selectionEnd ?? el.value.length;
    const val = el.value || '';
    const nextVal = val.slice(0, start) + text + val.slice(end);
    const nextPos = start + text.length;

    if (el.dataset.inputRole === 'formula') {
      const idx = Number(el.dataset.formulaIdx);
      setRows((r) => ({
        ...r,
        list: r.list.map((item, j) => (j === idx ? nextVal : item)),
      }));
    } else if (el.dataset.inputRole === 'calc') {
      setCalc(nextVal);
    } else {
      el.value = nextVal;
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }

    requestAnimationFrame(() => {
      el.focus();
      try { el.setSelectionRange(nextPos, nextPos); } catch { /* ignore */ }
    });
  }, [setRows, setCalc]);

  const handleBackspace = useCallback(() => {
    const el = (lastFocusedRef.current?.isConnected ? lastFocusedRef.current : null) || document.getElementById('f-0') || document.getElementById('m-calc');
    if (!el) return;
    const start = el.selectionStart ?? el.value.length;
    const end = el.selectionEnd ?? el.value.length;
    const val = el.value || '';
    if (start === 0 && end === 0) return;
    const newStart = start === end ? Math.max(0, start - 1) : start;
    const nextVal = val.slice(0, newStart) + val.slice(end);

    if (el.dataset.inputRole === 'formula') {
      const idx = Number(el.dataset.formulaIdx);
      setRows((r) => ({
        ...r,
        list: r.list.map((item, j) => (j === idx ? nextVal : item)),
      }));
    } else if (el.dataset.inputRole === 'calc') {
      setCalc(nextVal);
    } else {
      el.value = nextVal;
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }

    requestAnimationFrame(() => {
      el.focus();
      try { el.setSelectionRange(newStart, newStart); } catch { /* ignore */ }
    });
  }, [setRows, setCalc]);

  return (
    <div className="math-graph">
      <div className="stack-sm math-side">
        <div className="btn-row" style={{ gap: 'var(--space-1)' }} aria-label="Examples">
          {EXAMPLES.map(([label, list]) => (
            <button key={label} type="button" className="btn btn-quiet btn-sm" onClick={() => { setList(list); setTool({ sel: 0 }); }}>{label}</button>
          ))}
        </div>
        {curves.map((c, i) => (
          <div key={i} className="formula-row">
            <span className="swatch" style={{ background: `var(--${CURVE_TOKENS[i % CURVE_TOKENS.length]})` }} aria-hidden="true" />
            <label className="sr-only" htmlFor={`f-${i}`}>Function {i + 1}</label>
            <input id={`f-${i}`} className="input mono" value={c.text} spellCheck={false} placeholder="e.g. x^3 - 2x"
              data-input-role="formula" data-formula-idx={i}
              onFocus={(e) => { lastFocusedRef.current = e.target; }}
              onChange={(e) => setList(rows.list.map((t, j) => (j === i ? e.target.value : t)))} aria-invalid={Boolean(c.err)} />
            <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label={`Remove function ${i + 1}`}
              onClick={() => setList(rows.list.filter((_, j) => j !== i))}><X size={14} /></button>
            {c.err && <span className="hint err">{c.err.replace(/ in ".*"$/, '')}</span>}
            {hover && !c.err && c.src && (
              <span className="hint mono">f({Number(hover.x.toPrecision(4))}) = {Number(c.fn({ ...scopeBase, x: hover.x }).toPrecision(5))}</span>
            )}
          </div>
        ))}
        <div className="btn-row" style={{ gap: 'var(--space-2)' }}>
          {rows.list.length < 6 && (
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => setList([...rows.list, ''])}>
              <Plus size={14} aria-hidden="true" /> Add function
            </button>
          )}
          <button type="button" className={`btn btn-sm ${showKeypad ? 'btn-secondary' : 'btn-quiet'}`}
            onClick={() => setShowKeypad((v) => !v)} aria-label="Toggle virtual keypad">
            <Keyboard size={14} aria-hidden="true" /> {showKeypad ? 'Hide Keypad' : 'Keypad'}
          </button>
        </div>

        {showKeypad && (
          <MathKeypad onInsert={insertAtCursor} onBackspace={handleBackspace} onClose={() => setShowKeypad(false)} />
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
      <div className="stack-sm" style={{ minWidth: 0 }}>
        <div className="math-canvas-wrap">
          <canvas ref={canvasRef} className="math-canvas" aria-label="Graph of the functions"
            onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); dragRef.current = { x: e.clientX, y: e.clientY, cx: view.cx, cy: view.cy }; }}
            onPointerUp={() => { dragRef.current = null; }} onPointerMove={onPointerMove} onPointerLeave={() => setHover(null)} />
          <div className="canvas-overlay-controls" role="toolbar" aria-label="Graph controls">
            <button type="button" className="canvas-control-btn" title="Zoom in" aria-label="Zoom in"
              onClick={() => setView((v) => ({ ...v, scale: Math.min(5000, v.scale * 1.3) }))}>
              <ZoomIn size={16} aria-hidden="true" />
            </button>
            <button type="button" className="canvas-control-btn" title="Zoom out" aria-label="Zoom out"
              onClick={() => setView((v) => ({ ...v, scale: Math.max(2, v.scale / 1.3) }))}>
              <ZoomOut size={16} aria-hidden="true" />
            </button>
            <button type="button" className="canvas-control-btn" title="Reset home" aria-label="Reset home"
              onClick={() => setView({ cx: 0, cy: 0, scale: 50 })}>
              <Crosshair size={16} aria-hidden="true" />
            </button>
          </div>
        </div>

        <div className="math-tools panel">
          <div className="btn-row" style={{ alignItems: 'center' }}>
            <label className="label" htmlFor="m-sel">Analyse</label>
            <select id="m-sel" className="input" style={{ width: 'auto', minWidth: 160 }} value={sel} onChange={(e) => setTool({ sel: Number(e.target.value) })}>
              {curves.map((c, i) => (!c.err && c.src ? <option key={i} value={i}>f{i + 1}(x) = {c.text}</option> : null))}
            </select>
            <label className="check-row"><input type="checkbox" checked={tools.deriv} onChange={(e) => setTool({ deriv: e.target.checked })} /> Derivative f′</label>
            <label className="check-row"><input type="checkbox" checked={tools.tangent} onChange={(e) => setTool({ tangent: e.target.checked })} /> Tangent at cursor</label>
            <label className="check-row"><input type="checkbox" checked={tools.area} onChange={(e) => setTool({ area: e.target.checked })} /> Area from</label>
            <input className="input num" style={{ width: 72 }} type="number" aria-label="Area lower limit" value={tools.a} onChange={(e) => setTool({ a: e.target.value, area: true })} />
            <span className="hint">to</span>
            <input className="input num" style={{ width: 72 }} type="number" aria-label="Area upper limit" value={tools.b} onChange={(e) => setTool({ b: e.target.value, area: true })} />
            <label className="check-row"><input type="checkbox" checked={Boolean(tools.table)} onChange={(e) => setTool({ table: e.target.checked })} /> Table of values</label>
          </div>
          {facts && (
            <dl className="facts">
              <div><dt>Zeros in view</dt><dd className="mono">{facts.roots.length ? facts.roots.map((r) => `x = ${fmtN(r)}`).join(',  ') : 'none'}</dd></div>
              <div><dt>Turning points</dt><dd className="mono">{facts.extrema.length ? facts.extrema.map((p) => `${p.kind} (${fmtN(p.x)}, ${fmtN(p.y)})`).join(',  ') : 'none'}</dd></div>
              <div><dt>y-intercept</dt><dd className="mono">{Number.isFinite(facts.y0) ? fmtN(facts.y0) : 'undefined'}</dd></div>
              {hover && <div><dt>At cursor</dt><dd className="mono">f({fmtN(hover.x)}) = {fmtN(selFn(hover.x))},  f′ = {fmtN(dfdx(selFn, hover.x))}</dd></div>}
              {area !== null && <div><dt>∫ from {tools.a} to {tools.b}</dt><dd className="mono">{Number.isFinite(area) ? fmtN(area) : 'diverges'}</dd></div>}
            </dl>
          )}

          {tools.table && sel >= 0 && curves[sel] && (
            <ValuesTable
              curveName={curves[sel].text || `f${sel + 1}`}
              color={CURVE_TOKENS[sel % CURVE_TOKENS.length]}
              tableConfig={tableConfig}
              setTableConfig={setTableConfig}
              tableRows={tableRows}
            />
          )}

          <div className="field">
            <label htmlFor="m-calc">Calculator (uses your sliders; x is the cursor position)</label>
            <div className="btn-row" style={{ alignItems: 'center' }}>
              <input id="m-calc" className="input mono" style={{ flex: '1 1 220px' }} value={calc} spellCheck={false}
                data-input-role="calc" onFocus={(e) => { lastFocusedRef.current = e.target; }}
                placeholder="e.g. sqrt(2) * pi / 4" onChange={(e) => setCalc(e.target.value)} />
              {calcResult && (calcResult.err ? <span className="hint err">{calcResult.err}</span> : <b className="num calc-out">= {calcResult.v}</b>)}
            </div>
          </div>
        </div>
      </div>
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
          <PracticeDeck key={set.title + set.items.length} items={set.items}
            onSolved={(item) => reportXp('math_correct', `${set.title}:${item.id}:${item.prompt.slice(0, 60)}`)} />
        </>
      )}
    </div>
  );
}

/** Math workspace: graphing with sliders, a LaTeX notebook and checked practice. */
// Ready-made widgets for the Sim kit tab (same format the class generator writes: SimSpec kind "math")
const P = (name, min, max, value, label = name, step) => ({ name, label, min, max, value, step: step ?? (max - min) / 200, unit: '' });
const KIT = [
  { id: 'ed', name: 'ε-δ limit', spec: { widget: 'epsilon_delta', title: 'ε-δ: lim x→2 of x² = 4', description: 'The proof picks δ = min(1, ε/5): press Animate to shrink ε and watch δ follow, always inside the largest δ that works (inset). Untick the link to hunt for δ by hand.', f: 'x^2', a: '2', L: '4', delta_rule: 'min(1, eps/5)', params: [P('eps', 0.02, 2, 0.8, 'ε'), P('delta', 0.005, 1.5, 0.5, 'δ')] } },
  { id: 'en', name: 'ε-N sequence', spec: { widget: 'epsilon_n', title: 'ε-N: aₙ = 1 + (−1)ⁿ/n → 1', description: 'For each ε there is an N after which every term stays in the band. Shrink ε and watch N grow.', term: '1 + (-1)^n / n', L: '1', nmax: 60, params: [P('eps', 0.01, 0.6, 0.25, 'ε')] } },
  { id: 'st', name: 'Secant → tangent', spec: { widget: 'secant_tangent', title: 'From secant to tangent', description: 'Drag h toward 0: the secant slope approaches the derivative.', f: 'sin(x) + x/2', a: '1', params: [P('h', -3, 3, 2, 'h')] } },
  { id: 'rs', name: 'Riemann sums', spec: { widget: 'riemann', title: 'Riemann sums of x² on [0, 2]', description: 'Raise n and switch rules: every sum approaches the exact area 8/3.', f: 'x^2', a: '0', b: '2', method: 'left', params: [P('n', 1, 60, 4, 'n', 1)] } },
  { id: 'ts', name: 'Taylor: sin x', spec: { widget: 'series', title: 'Taylor polynomials of sin x', description: 'Each extra term hugs sin x over a wider interval.', term: '(-1)^k * x^(2*k+1) / fact(2*k+1)', target: 'sin(x)', params: [P('N', 0, 12, 2, 'N (terms − 1)', 1)] } },
  { id: 'te', name: 'Taylor: eˣ', spec: { widget: 'series', title: 'Partial sums of eˣ = Σ xᵏ/k!', description: 'Hover anywhere to compare the partial sum with eˣ.', term: 'x^k / fact(k)', target: 'exp(x)', view: { xmin: -4, xmax: 4, ymin: -2, ymax: 20 }, params: [P('N', 0, 15, 2, 'N', 1)] } },
  { id: 'uc', name: 'Unit circle', spec: { widget: 'unit_circle', title: 'Sine and cosine on the unit circle', description: 'cos θ and sin θ are the coordinates of the point; the sine graph unrolls as θ grows.', params: [P('theta', 0, 360, 45, 'θ (degrees)', 1)] } },
  { id: 'pc', name: 'Parametric curve', spec: { widget: 'parametric', title: 'Lissajous curve x = cos 3t, y = sin 2t', description: 'Move t to trace the curve; the arrow is the velocity (dx/dt, dy/dt).', x: 'cos(3*t)', y: 'sin(2*t)', tmin: '0', tmax: '2*pi', params: [P('t', 0, 1, 0.3, 't (fraction of the way)')] } },
  { id: 'vf', name: 'Vector field', spec: { widget: 'vector_field', title: 'F(x, y) = (−y, x − 0.3y)', description: 'Click to drop flow lines. Hover to read divergence and curl.', P: '-y', Q: 'x - 0.3*y', params: [] } },
  { id: 'lt', name: 'Linear transform', spec: { widget: 'transform2d', title: 'A 2×2 matrix acting on the plane', description: 'The unit square maps to a parallelogram with area |det|; a red square means orientation flipped.', a: 'm11', b: 'm12', c: 'm21', d: 'm22', params: [P('m11', -3, 3, 1), P('m12', -3, 3, 0.5), P('m21', -3, 3, 0), P('m22', -3, 3, 1)] } },
].map((k) => ({ ...k, spec: { kind: 'math', ...k.spec } }));

function KitTab({ preview }) {
  const [pick, setPick] = useState(() => (preview ? 'preview' : store.get('andedu_math_kit', 'ed')));
  useEffect(() => { if (pick !== 'preview') store.set('andedu_math_kit', pick); }, [pick]);
  useEffect(() => { if (preview) setPick('preview'); }, [preview]);
  const kit = preview ? [{ id: 'preview', name: 'From the assistant', spec: preview }, ...KIT] : KIT;
  const item = kit.find((k) => k.id === pick) || KIT[0];
  return (
    <div className="stack" style={{ marginTop: 'var(--space-4)' }}>
      <div className="btn-row" role="group" aria-label="Widgets">
        {kit.map((k) => (
          <button key={k.id} type="button" className={`btn btn-sm ${k.id === item.id ? 'btn-primary' : 'btn-quiet'}`} aria-pressed={k.id === item.id} onClick={() => setPick(k.id)}>{k.name}</button>
        ))}
      </div>
      <p className="hint">Edit the functions to explore your own examples. Class simulations in math courses use these same widgets.</p>
      <MathSim key={item.id} spec={item.spec} editable />
    </div>
  );
}

export function CoursesTab({ topics, onOpenTopic, activeId, empty }) {
  const courses = [];
  for (const t of topics) {
    const cid = t.source?.courseId || 'library';
    const c = courses.find((x) => x.id === cid) || (courses.push({ id: cid, title: t.source?.courseTitle || 'Library lessons', classes: [] }), courses[courses.length - 1]);
    c.classes.push(t);
  }
  if (!courses.length) {
    return <div className="panel" style={{ marginTop: 'var(--space-4)' }}><p>{empty || 'No math courses yet. Start one from My courses: its classes open here, next to the math tools.'}</p></div>;
  }
  return (
    <div className="stack" style={{ marginTop: 'var(--space-4)' }}>
      {courses.map((c) => (
        <section key={c.id} className="panel stack-sm">
          <h2>{c.title}</h2>
          <ol className="class-list">
            {c.classes.sort((a, b) => (a.source?.classSeq || 0) - (b.source?.classSeq || 0)).map((t) => (
              <li key={t.id}>
                <button type="button" className="card-link" aria-current={t.id === activeId ? 'page' : undefined} onClick={() => onOpenTopic(t.id)}>
                  {t.source?.classSeq && <span className="class-num-sm">{String(t.source.classSeq).padStart(2, '0')}</span>} {t.title.replace(/^Class \d+:\s*/, '')}
                </button>
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}

/**
 * Math workspace: math course classes open here (Class tab) next to the tools a math student needs:
 * graphing, a LaTeX notebook, checked practice and the simulation kit.
 */
export default function MathLab({ user, classTopic, mathTopics = [], onOpenTopic, renderClass, push }) {
  const [tab, setTab] = useState(() => (classTopic ? 'class' : store.get('andedu_math_tab', 'graph')));
  useEffect(() => { if (classTopic) setTab('class'); }, [classTopic?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (tab !== 'class') store.set('andedu_math_tab', tab); }, [tab]);
  useEffect(() => { if (push?.graph) setTab('graph'); else if (push?.spec) setTab('kit'); }, [push?.at]); // eslint-disable-line react-hooks/exhaustive-deps
  const tabs = [
    ...(classTopic ? [{ id: 'class', label: `Class ${classTopic.source?.classSeq ?? ''}`.trim(), icon: BookOpen }] : []),
    { id: 'courses', label: 'Courses', icon: GraduationCap },
    ...TABS,
    { id: 'kit', label: 'Sim kit', icon: Shapes },
  ];
  const current = tabs.some((t) => t.id === tab) ? tab : 'graph';
  return (
    <div className="page page-wide">
      <div className="page-head">
        <div>
          <h1>Math</h1>
          <p>Your math classes, with graphing, a LaTeX notebook, checked practice and interactive math simulations beside them.</p>
        </div>
      </div>
      <div className="tabs" role="tablist" aria-label="Math tools">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button key={id} type="button" role="tab" id={`mt-${id}`} aria-selected={current === id} aria-controls={`mp-${id}`}
            className="tab" onClick={() => setTab(id)}><Icon size={16} aria-hidden="true" /> {label}</button>
        ))}
      </div>
      <section role="tabpanel" id={`mp-${current}`} aria-labelledby={`mt-${current}`}>
        {current === 'class' && classTopic && renderClass(classTopic)}
        {current === 'courses' && <CoursesTab topics={mathTopics} onOpenTopic={onOpenTopic} activeId={classTopic?.id} />}
        {current === 'graph' && <GraphTab userId={user.id} incoming={push?.graph} />}
        {current === 'notebook' && <NotebookTab userId={user.id} />}
        {current === 'practice' && <PracticeTab />}
        {current === 'kit' && <KitTab preview={push?.spec} />}
      </section>
    </div>
  );
}
