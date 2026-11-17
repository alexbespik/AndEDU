import React, { useEffect, useId, useRef } from 'react';

/** Strict number parser for desk inputs: plain decimals or exponents only, never evaluated as code. */
export function num(text, label) {
  const t = String(text ?? '').trim();
  if (!/^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$/.test(t)) throw new Error(`${label} must be a number (for example 2.5 or 1e3).`);
  return Number(t);
}

const SI = { p: 1e-12, n: 1e-9, u: 1e-6, m: 1e-3, k: 1e3, K: 1e3, M: 1e6, G: 1e9 };
/** "4.7k", "10u", "2" -> a number (engineering suffixes p n u m k M G). */
export function siNum(text, label) {
  const t = String(text ?? '').trim();
  const m = t.match(/^(.*?)([pnumkKMG])$/);
  if (m && m[1] !== '') return num(m[1], label) * SI[m[2]];
  return num(t, label);
}

/** "1, 2.5  3" -> [1, 2.5, 3]. */
export function nums(text, label) {
  const parts = String(text ?? '').split(/[\s,;]+/).filter(Boolean);
  if (!parts.length) throw new Error(`${label}: enter at least one number.`);
  return parts.map((p) => num(p, label));
}

/** Lines of numbers -> rows; every row the same width. */
export function rows(text, label) {
  const lines = String(text ?? '').split('\n').map((l) => l.trim()).filter(Boolean);
  if (!lines.length) throw new Error(`${label}: enter at least one row.`);
  const out = lines.map((l, i) => nums(l, `${label}, row ${i + 1}`));
  if (out.some((r) => r.length !== out[0].length)) throw new Error(`${label}: every row needs the same number of values.`);
  return out;
}

/** Whole-number rows, for counts. */
export function intRows(text, label) {
  const r = rows(text, label);
  if (r.some((row) => row.some((v) => !Number.isInteger(v) || v < 0))) throw new Error(`${label}: use whole numbers, 0 or more.`);
  return r;
}

/** A number for display: 4 significant digits, exponent for the very large or small; null -> a dash. */
export function fmt(v, digits = 4) {
  if (v === null || v === undefined) return '-';
  if (typeof v !== 'number') return String(v);
  if (!Number.isFinite(v)) return String(v);
  if (v === 0) return '0';
  const a = Math.abs(v);
  if (a >= 1e6 || a < 1e-3) return v.toExponential(2);
  return String(Number(v.toPrecision(digits)));
}

/** Runs fn at once on mount, then debounced (default 400 ms) whenever deps change. For sliders. */
export function useAutoRun(fn, deps, delay = 600) {
  const ref = useRef(fn);
  const first = useRef(true);
  useEffect(() => { ref.current = fn; });
  useEffect(() => {
    if (first.current) { first.current = false; ref.current(); return undefined; }
    const t = setTimeout(() => ref.current(), delay);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

/** Label + control + optional hint. `children` is a render function of the input id. */
export function Field({ label, hint, className = '', children }) {
  const id = useId();
  return (
    <div className={`field ${className}`.trim()}>
      <label htmlFor={id}>{label}</label>
      {children(id)}
      {hint && <span className="hint">{hint}</span>}
    </div>
  );
}

/** A row of preset buttons: [{label, apply}]. */
export function Presets({ items, label = 'Examples' }) {
  return (
    <div className="kt-tagbtns" role="group" aria-label={label}>
      <span className="kt-sub">{label}:</span>
      {items.map((p) => <button key={p.label} type="button" className="btn btn-quiet btn-sm" onClick={p.apply}>{p.label}</button>)}
    </div>
  );
}

/** A two-or-more-way choice as radio-style buttons. */
export function Choice({ label, value, options, onChange }) {
  return (
    <div className="kt-tabs" role="radiogroup" aria-label={label}>
      {options.map(([id, text]) => (
        <button key={id} type="button" role="radio" aria-checked={value === id} className="kt-seg" onClick={() => onChange(id)}>{text}</button>
      ))}
    </div>
  );
}

function niceTicks(lo, hi, count = 5) {
  const span = hi - lo;
  if (!(span > 0)) return [lo];
  const raw = span / count;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * pow).find((s) => s >= raw) || pow * 10;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(Number(v.toPrecision(12)));
  return out;
}

const tickText = (v) => {
  if (v === 0) return '0';
  const a = Math.abs(v);
  return a >= 1e5 || a < 1e-3 ? v.toExponential(0) : String(Number(v.toPrecision(4)));
};

/**
 * A small line chart in SVG (CSS variables only). series: [{points: [{x, y}], tone: 't0'..'t6', dashed, dots, label}];
 * areas: [{points, tone}] closed polygons in data units; vlines: [{x, label, tone}]; hlines: [{y, label}]; marks: [{x, y, label, tone}].
 */
export function Plot({ title, xLabel, yLabel, series = [], areas = [], vlines = [], hlines = [], marks = [], xLog = false, xDomain, yDomain, height = 220 }) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '');
  const W = 560;
  const L = 50, R = 14, T = 12, B = 36;
  const all = [...series.flatMap((s) => s.points), ...areas.flatMap((a) => a.points)].filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y) && (!xLog || p.x > 0));
  const tx = (x) => (xLog ? Math.log10(x) : x);
  let [x0, x1] = xDomain || [Math.min(...all.map((p) => p.x)), Math.max(...all.map((p) => p.x))];
  let [y0, y1] = yDomain || [Math.min(...all.map((p) => p.y), ...hlines.map((h) => h.y)), Math.max(...all.map((p) => p.y), ...hlines.map((h) => h.y))];
  if (!all.length || !Number.isFinite(x0) || !Number.isFinite(y0)) return <p className="hint">Nothing to plot.</p>;
  if (!yDomain) { const pad = (y1 - y0) * 0.06 || 1; y0 -= pad; y1 += pad; }
  if (x1 === x0) { x0 -= 1; x1 += 1; }
  const a0 = tx(x0), a1 = tx(x1);
  const sx = (x) => L + ((tx(x) - a0) / (a1 - a0)) * (W - L - R);
  const sy = (y) => T + (1 - (y - y0) / (y1 - y0)) * (height - T - B);
  const xTicks = xLog
    ? Array.from({ length: Math.max(0, Math.floor(a1) - Math.ceil(a0) + 1) }, (_, i) => 10 ** (Math.ceil(a0) + i))
    : niceTicks(x0, x1, 6);
  const yTicks = niceTicks(y0, y1, 5);
  const path = (pts) => pts.filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y)).map((p, i) => `${i ? 'L' : 'M'}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join('');
  return (
    <svg className="kt-plot" viewBox={`0 0 ${W} ${height}`} role="img" aria-label={title}>
      <title>{title}</title>
      <clipPath id={`clip${uid}`}><rect x={L} y={T} width={W - L - R} height={height - T - B} /></clipPath>
      {yTicks.map((v) => (
        <g key={`y${v}`}>
          <line className="kt-gridline" x1={L} x2={W - R} y1={sy(v)} y2={sy(v)} />
          <text className="kt-axis-text" x={L - 6} y={sy(v) + 3} textAnchor="end">{tickText(v)}</text>
        </g>
      ))}
      {xTicks.map((v) => (
        <g key={`x${v}`}>
          <line className="kt-gridline" x1={sx(v)} x2={sx(v)} y1={T} y2={height - B} />
          <text className="kt-axis-text" x={sx(v)} y={height - B + 14} textAnchor="middle">{tickText(v)}</text>
        </g>
      ))}
      <line className="kt-axis" x1={L} x2={W - R} y1={height - B} y2={height - B} />
      <line className="kt-axis" x1={L} x2={L} y1={T} y2={height - B} />
      <g clipPath={`url(#clip${uid})`}>
        {areas.map((a, i) => <path key={`a${i}`} className={`kt-area ${a.tone || 't0'}`} d={`${path(a.points)}Z`} />)}
        {hlines.map((h, i) => <line key={`h${i}`} className="kt-ref" x1={L} x2={W - R} y1={sy(h.y)} y2={sy(h.y)} />)}
        {vlines.filter((v) => Number.isFinite(v.x)).map((v, i) => <line key={`v${i}`} className={`kt-ref ${v.tone || ''}`} x1={sx(v.x)} x2={sx(v.x)} y1={T} y2={height - B} />)}
        {series.map((s, i) => (
          <g key={`s${i}`}>
            <path className={`kt-line ${s.tone || 't0'}${s.dashed ? ' kt-dash' : ''}`} d={path(s.points)} />
            {s.dots && s.points.map((p, j) => <circle key={j} className={`kt-dot ${s.tone || 't0'}`} cx={sx(p.x)} cy={sy(p.y)} r="2.5" />)}
          </g>
        ))}
        {marks.map((m, i) => <circle key={`m${i}`} className={`kt-dot kt-mark ${m.tone || 't1'}`} cx={sx(m.x)} cy={sy(m.y)} r="5" />)}
      </g>
      {hlines.filter((h) => h.label).map((h, i) => <text key={`ht${i}`} className="kt-axis-text" x={W - R - 2} y={sy(h.y) - 3} textAnchor="end">{h.label}</text>)}
      {vlines.filter((v) => v.label && Number.isFinite(v.x)).map((v, i) => (
        <text key={`vt${i}`} className="kt-axis-text kt-strong" x={Math.min(sx(v.x) + 3, W - R - 40)} y={T + 9 + (i % 3) * 11}>{v.label}</text>
      ))}
      {marks.filter((m) => m.label).map((m, i) => <text key={`mt${i}`} className="kt-axis-text kt-strong" x={Math.min(sx(m.x) + 8, W - R - 50)} y={sy(m.y) - 8}>{m.label}</text>)}
      {xLabel && <text className="kt-axis-text" x={(L + W - R) / 2} y={height - 3} textAnchor="middle">{xLabel}</text>}
      {yLabel && <text className="kt-axis-text" transform={`rotate(-90 11 ${(T + height - B) / 2})`} x="11" y={(T + height - B) / 2} textAnchor="middle">{yLabel}</text>}
    </svg>
  );
}

/** Legend for several series: items [{tone, label}]. */
export function Legend({ items }) {
  return (
    <ul className="kt-legend" aria-label="Legend">
      {items.map((it) => <li key={it.label}><span className={`kt-sw ${it.tone}`} aria-hidden="true" />{it.label}</li>)}
    </ul>
  );
}
