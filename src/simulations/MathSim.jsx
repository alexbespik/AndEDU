import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Play, Pause, RotateCcw } from 'lucide-react';
import { tryCompile } from '../lib/expr';
import { canvasPalette } from '../theme';

// ---------------------------------------------------------------------------
// Math simulation kit (SimSpec kind "math"). One widget per idea; fields and sliders are
// validated server-side by simspec.validate_math. Expressions compile with src/lib/expr.js.
// ---------------------------------------------------------------------------

const FIELDS = {
  epsilon_delta: ['f', 'a', 'L'], epsilon_n: ['term', 'L'], secant_tangent: ['f', 'a'], riemann: ['f', 'a', 'b'],
  series: ['term', 'target'], unit_circle: [], parametric: ['x', 'y', 'tmin', 'tmax'], vector_field: ['P', 'Q'],
  transform2d: ['a', 'b', 'c', 'd'],
};
const FIELD_VARS = { f: 'x', target: 'x', x: 't', y: 't', P: 'x, y', Q: 'x, y' };
const varsFor = (widget, f) => (f === 'term' ? (widget === 'series' ? 'k, x' : 'n') : FIELD_VARS[f] || '');
const SWEEP = { epsilon_delta: 'eps', epsilon_n: 'eps', secant_tangent: 'h', riemann: 'n', series: 'N', unit_circle: 'theta', parametric: 't' };
const EQUAL_AXES = new Set(['unit_circle', 'vector_field', 'transform2d', 'parametric']);

const fmt = (v, p = 4) => (Number.isFinite(v) ? String(Number(v.toPrecision(p))) : '–');

function useCompiled(spec, overrides) {
  return useMemo(() => {
    const out = {};
    const errs = [];
    for (const f of FIELDS[spec.widget] || []) {
      const src = overrides[f] ?? spec[f];
      if (src === undefined || src === null || src === '') continue;
      const [fn, err] = tryCompile(src, NaN);
      out[f] = fn;
      if (err) errs.push(`${f}: ${err.replace(/ in ".*"$/, '')}`);
    }
    return [out, errs];
  }, [spec, overrides]);
}

function frameFor(W, H, v, equal) {
  let { xmin, xmax, ymin, ymax } = v;
  if (equal) {
    const s = Math.min(W / (xmax - xmin), H / (ymax - ymin));
    const cx = (xmin + xmax) / 2, cy = (ymin + ymax) / 2;
    xmin = cx - W / s / 2; xmax = cx + W / s / 2; ymin = cy - H / s / 2; ymax = cy + H / s / 2;
  }
  const sx = W / (xmax - xmin), sy = H / (ymax - ymin);
  return {
    xmin, xmax, ymin, ymax, sx, sy,
    X: (x) => (x - xmin) * sx, Y: (y) => H - (y - ymin) * sy,
    fx: (px) => xmin + px / sx, fy: (py) => ymin + (H - py) / sy,
  };
}

function niceStep(span) {
  const raw = span / 10, p = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 5, 10].map((k) => k * p).find((s) => s >= raw) || p * 10;
}

function drawGrid(ctx, F, W, H, pal) {
  ctx.fillStyle = pal.surface; ctx.fillRect(0, 0, W, H);
  ctx.font = '11px "IBM Plex Mono", monospace'; ctx.lineWidth = 1;
  const sx = niceStep(F.xmax - F.xmin), sy = niceStep(F.ymax - F.ymin);
  ctx.fillStyle = pal.muted;
  for (let x = Math.ceil(F.xmin / sx) * sx; x <= F.xmax; x += sx) {
    ctx.strokeStyle = pal.rule; ctx.beginPath(); ctx.moveTo(F.X(x), 0); ctx.lineTo(F.X(x), H); ctx.stroke();
    ctx.textAlign = 'center'; ctx.fillText(fmt(x, 3), F.X(x), Math.min(H - 4, Math.max(12, F.Y(0) + 14)));
  }
  for (let y = Math.ceil(F.ymin / sy) * sy; y <= F.ymax; y += sy) {
    ctx.strokeStyle = pal.rule; ctx.beginPath(); ctx.moveTo(0, F.Y(y)); ctx.lineTo(W, F.Y(y)); ctx.stroke();
    if (Math.abs(y) > 1e-9) { ctx.textAlign = 'left'; ctx.fillText(fmt(y, 3), Math.min(W - 36, Math.max(4, F.X(0) + 4)), F.Y(y) - 3); }
  }
  ctx.strokeStyle = pal.ink; ctx.lineWidth = 1.4;
  ctx.beginPath(); ctx.moveTo(0, F.Y(0)); ctx.lineTo(W, F.Y(0)); ctx.moveTo(F.X(0), 0); ctx.lineTo(F.X(0), H); ctx.stroke();
}

function plot(ctx, F, W, H, fn, color, width = 2.5, dash = null) {
  ctx.strokeStyle = color; ctx.lineWidth = width; ctx.setLineDash(dash || []);
  ctx.beginPath();
  let pen = false, last = null;
  for (let px = 0; px <= W; px += 1) {
    const y = fn(F.fx(px)), py = F.Y(y);
    if (!Number.isFinite(y) || (last !== null && Math.abs(py - last) > H * 2)) { pen = false; last = Number.isFinite(y) ? py : null; continue; }
    if (pen) ctx.lineTo(px, py); else { ctx.moveTo(px, py); pen = true; }
    last = py;
  }
  ctx.stroke(); ctx.setLineDash([]);
}

function label(ctx, text, x, y, color, align = 'left') {
  ctx.font = '12px "IBM Plex Mono", monospace'; ctx.textAlign = align; ctx.fillStyle = color; ctx.fillText(text, x, y);
}

function rangeOf(fn, a, b, n = 200) {
  let lo = Infinity, hi = -Infinity;
  for (let i = 0; i <= n; i++) { const y = fn(a + ((b - a) * i) / n); if (Number.isFinite(y) && Math.abs(y) < 1e6) { lo = Math.min(lo, y); hi = Math.max(hi, y); } }
  return Number.isFinite(lo) ? [lo, hi] : [-1, 1];
}
const pad = ([lo, hi], k = 0.15) => { const s = Math.max(hi - lo, 1e-3); return [lo - s * k, hi + s * k]; };

function simpson(f, a, b, n = 2000) {
  const h = (b - a) / n; let s = f(a) + f(b);
  for (let i = 1; i < n; i++) s += f(a + i * h) * (i % 2 ? 4 : 2);
  return (s * h) / 3;
}

/** Each widget: view(spec, fns, scope) -> {xmin..}, draw(ctx, F, W, H, pal, fns, scope, state) -> readouts[] */
const WIDGETS = {
  epsilon_delta: {
    view: (s, fn, sc) => { const a = fn.a(sc), L = fn.L(sc); return { xmin: a - 2.5, xmax: a + 2.5, ymin: L - 3, ymax: L + 3 }; },
    draw(ctx, F, W, H, pal, fn, sc) {
      const a = fn.a(sc), L = fn.L(sc), eps = sc.eps, d = sc.delta, f = (x) => fn.f({ ...sc, x });
      ctx.fillStyle = pal.gold; ctx.globalAlpha = 0.18; ctx.fillRect(0, F.Y(L + eps), W, F.Y(L - eps) - F.Y(L + eps));
      ctx.fillStyle = pal.accent; ctx.globalAlpha = 0.13; ctx.fillRect(F.X(a - d), 0, F.X(a + d) - F.X(a - d), H); ctx.globalAlpha = 1;
      ctx.setLineDash([5, 4]); ctx.lineWidth = 1.2;
      ctx.strokeStyle = pal['gold-text']; for (const y of [L - eps, L + eps]) { ctx.beginPath(); ctx.moveTo(0, F.Y(y)); ctx.lineTo(W, F.Y(y)); ctx.stroke(); }
      ctx.strokeStyle = pal.accent; for (const x of [a - d, a + d]) { ctx.beginPath(); ctx.moveTo(F.X(x), 0); ctx.lineTo(F.X(x), H); ctx.stroke(); }
      ctx.setLineDash([]);
      plot(ctx, F, W, H, f, pal.ink, 2);
      // inside the delta band: green where |f - L| < eps, red where it escapes
      let worst = 0, worstX = null;
      ctx.lineWidth = 4;
      for (let i = 0; i <= 300; i++) {
        const x = a - d + (2 * d * i) / 300;
        if (Math.abs(x - a) < 1e-9) continue;
        const y = f(x), dev = Math.abs(y - L);
        if (!Number.isFinite(y)) continue;
        if (dev > worst) { worst = dev; worstX = x; }
        ctx.fillStyle = dev < eps ? pal.accent : pal.bad;
        ctx.fillRect(F.X(x) - 1.5, F.Y(y) - 1.5, 3, 3);
      }
      ctx.fillStyle = pal.surface; ctx.strokeStyle = pal.ink; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(F.X(a), F.Y(L), 5, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      label(ctx, `L ± ε`, 8, F.Y(L + eps) - 6, pal['gold-text']);
      label(ctx, `a ± δ`, F.X(a + d) + 6, 16, pal.accent);
      // largest delta that works (bisection on the worst deviation)
      const dev = (dd) => { let m = 0; for (let i = 0; i <= 200; i++) { const x = a - dd + (2 * dd * i) / 200; if (Math.abs(x - a) > 1e-9) { const v = Math.abs(f(x) - L); if (Number.isFinite(v)) m = Math.max(m, v); } } return m; };
      let lo = 0, hi = Math.max(2, d * 2);
      if (dev(hi) < eps) lo = hi; else for (let k = 0; k < 30; k++) { const m = (lo + hi) / 2; if (dev(m) < eps) lo = m; else hi = m; }
      const ok = worst < eps;
      return [
        ok ? `δ = ${fmt(d)} works for ε = ${fmt(eps)}: every x with 0 < |x − a| < δ has |f(x) − L| < ε`
          : `δ = ${fmt(d)} fails for ε = ${fmt(eps)}: at x = ${fmt(worstX)}, |f(x) − L| = ${fmt(worst)}`,
        `Largest δ that works here ≈ ${fmt(lo, 3)}`,
      ];
    },
  },

  epsilon_n: {
    view: (s, fn, sc) => { const L = fn.L(sc); const r = rangeOf((n) => fn.term({ ...sc, n: Math.max(1, Math.round(n)) }), 1, s.nmax || 60); return { xmin: -1, xmax: (s.nmax || 60) + 1, ymin: Math.min(r[0], L - 1) - 0.2, ymax: Math.max(r[1], L + 1) + 0.2 }; },
    draw(ctx, F, W, H, pal, fn, sc, s) {
      const L = fn.L(sc), eps = sc.eps, nmax = s.nmax || 60;
      const a = (n) => fn.term({ ...sc, n });
      let N = null;
      for (let n = nmax; n >= 1; n--) { if (!(Math.abs(a(n) - L) < eps)) { N = n + 1; break; } }
      if (N === null) N = 1;
      ctx.fillStyle = pal.gold; ctx.globalAlpha = 0.18; ctx.fillRect(0, F.Y(L + eps), W, F.Y(L - eps) - F.Y(L + eps)); ctx.globalAlpha = 1;
      ctx.strokeStyle = pal['gold-text']; ctx.setLineDash([5, 4]); ctx.beginPath(); ctx.moveTo(0, F.Y(L)); ctx.lineTo(W, F.Y(L)); ctx.stroke(); ctx.setLineDash([]);
      if (N <= nmax) { ctx.strokeStyle = pal.accent; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(F.X(N), 0); ctx.lineTo(F.X(N), H); ctx.stroke(); label(ctx, `N = ${N}`, F.X(N) + 5, 16, pal.accent); }
      for (let n = 1; n <= nmax; n++) {
        const y = a(n); if (!Number.isFinite(y)) continue;
        ctx.fillStyle = Math.abs(y - L) < eps ? (n >= N ? pal.accent : pal.info) : pal.bad;
        ctx.beginPath(); ctx.arc(F.X(n), F.Y(y), 3.5, 0, Math.PI * 2); ctx.fill();
      }
      return [N <= nmax ? `For ε = ${fmt(eps)}, every term from n = ${N} on stays within ε of L = ${fmt(L)}` : `No N up to ${nmax} works for ε = ${fmt(eps)}: the terms keep leaving the band`,
        `a_N = ${fmt(a(Math.min(N, nmax)))}, |a_N − L| = ${fmt(Math.abs(a(Math.min(N, nmax)) - L))}`];
    },
  },

  secant_tangent: {
    view: (s, fn, sc) => { const a = fn.a(sc); const r = pad(rangeOf((x) => fn.f({ ...sc, x }), a - 4, a + 4)); return { xmin: a - 4, xmax: a + 4, ymin: r[0], ymax: r[1] }; },
    draw(ctx, F, W, H, pal, fn, sc) {
      const a = fn.a(sc), h = Math.abs(sc.h) < 1e-6 ? 1e-6 : sc.h, f = (x) => fn.f({ ...sc, x });
      plot(ctx, F, W, H, f, pal.ink, 2.2);
      const m = (f(a + h) - f(a)) / h, e = 1e-5 * Math.max(1, Math.abs(a)), mt = (f(a + e) - f(a - e)) / (2 * e);
      plot(ctx, F, W, H, (x) => f(a) + mt * (x - a), pal.accent, 1.6, [6, 5]);
      plot(ctx, F, W, H, (x) => f(a) + m * (x - a), pal.gold, 2.4);
      for (const [x, c] of [[a, pal.ink], [a + h, pal['gold-text']]]) { ctx.fillStyle = c; ctx.beginPath(); ctx.arc(F.X(x), F.Y(f(x)), 5, 0, Math.PI * 2); ctx.fill(); }
      label(ctx, 'secant', F.X(a + h) + 8, F.Y(f(a + h)) - 8, pal['gold-text']);
      return [`Secant slope [f(a+h) − f(a)] / h = ${fmt(m)}  (h = ${fmt(h, 3)})`, `Tangent slope f′(a) ≈ ${fmt(mt)}, difference ${fmt(m - mt, 3)}`];
    },
  },

  riemann: {
    view: (s, fn, sc) => { const a = fn.a(sc), b = fn.b(sc), w = b - a || 1; const r = rangeOf((x) => fn.f({ ...sc, x }), a, b); return { xmin: a - w * 0.15, xmax: b + w * 0.15, ymin: Math.min(0, r[0]) - Math.abs(r[1] - r[0]) * 0.1 - 0.1, ymax: Math.max(0, r[1]) * 1.15 + 0.1 }; },
    draw(ctx, F, W, H, pal, fn, sc, s, st) {
      const a = fn.a(sc), b = fn.b(sc), n = Math.max(1, Math.round(sc.n)), f = (x) => fn.f({ ...sc, x }), dx = (b - a) / n, method = st.method;
      let sum = 0;
      for (let i = 0; i < n; i++) {
        const x0 = a + i * dx, x1 = x0 + dx;
        ctx.fillStyle = pal.gold; ctx.globalAlpha = 0.32; ctx.strokeStyle = pal['gold-text']; ctx.lineWidth = 1;
        if (method === 'trap') {
          const y0 = f(x0), y1 = f(x1); sum += ((y0 + y1) / 2) * dx;
          ctx.beginPath(); ctx.moveTo(F.X(x0), F.Y(0)); ctx.lineTo(F.X(x0), F.Y(y0)); ctx.lineTo(F.X(x1), F.Y(y1)); ctx.lineTo(F.X(x1), F.Y(0)); ctx.closePath(); ctx.fill(); ctx.globalAlpha = 1; ctx.stroke();
        } else {
          const xs = method === 'left' ? x0 : method === 'right' ? x1 : (x0 + x1) / 2, y = f(xs); sum += y * dx;
          ctx.fillRect(F.X(x0), Math.min(F.Y(y), F.Y(0)), F.X(x1) - F.X(x0), Math.abs(F.Y(y) - F.Y(0))); ctx.globalAlpha = 1;
          ctx.strokeRect(F.X(x0), Math.min(F.Y(y), F.Y(0)), F.X(x1) - F.X(x0), Math.abs(F.Y(y) - F.Y(0)));
        }
      }
      plot(ctx, F, W, H, f, pal.ink, 2.4);
      const exact = simpson(f, a, b);
      return [`${{ left: 'Left', right: 'Right', mid: 'Midpoint', trap: 'Trapezoid' }[method]} sum with n = ${n}: ${fmt(sum, 6)}`,
        `Exact area ∫ f dx from ${fmt(a, 3)} to ${fmt(b, 3)} = ${fmt(exact, 6)}, error ${fmt(sum - exact, 3)}`];
    },
  },

  series: {
    view: () => ({ xmin: -7, xmax: 7, ymin: -3, ymax: 3 }),
    draw(ctx, F, W, H, pal, fn, sc, s, st) {
      const N = Math.max(0, Math.round(sc.N));
      const S = (x) => { let t = 0; for (let k = 0; k <= N; k++) t += fn.term({ ...sc, k, x }); return t; };
      if (fn.target) plot(ctx, F, W, H, (x) => fn.target({ ...sc, x }), pal.ink, 2.2);
      plot(ctx, F, W, H, S, pal.gold, 2.6);
      const x0 = st.hoverX ?? 1;
      const out = [`S_${N}(${fmt(x0, 3)}) = ${fmt(S(x0), 6)}  (sum of ${N + 1} term${N ? 's' : ''})`];
      if (fn.target) out.push(`target(${fmt(x0, 3)}) = ${fmt(fn.target({ ...sc, x: x0 }), 6)}, error ${fmt(S(x0) - fn.target({ ...sc, x: x0 }), 3)}`);
      return out;
    },
  },

  unit_circle: {
    view: () => ({ xmin: -1.5, xmax: 8.2, ymin: -1.6, ymax: 1.6 }),
    draw(ctx, F, W, H, pal, fn, sc) {
      const th = (sc.theta * Math.PI) / 180, c = Math.cos(th), s = Math.sin(th), gx = 1.7;
      ctx.strokeStyle = pal.ink; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(F.X(0), F.Y(0), F.sx, 0, Math.PI * 2); ctx.stroke();
      ctx.strokeStyle = pal.gold; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(F.X(0), F.Y(0), F.sx * 0.25, 0, -th, th > 0); ctx.stroke();
      ctx.strokeStyle = pal.ink; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(F.X(0), F.Y(0)); ctx.lineTo(F.X(c), F.Y(s)); ctx.stroke();
      ctx.strokeStyle = pal.accent; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(F.X(0), F.Y(0)); ctx.lineTo(F.X(c), F.Y(0)); ctx.stroke();
      ctx.strokeStyle = pal['gold-text']; ctx.beginPath(); ctx.moveTo(F.X(c), F.Y(0)); ctx.lineTo(F.X(c), F.Y(s)); ctx.stroke();
      ctx.fillStyle = pal.ink; ctx.beginPath(); ctx.arc(F.X(c), F.Y(s), 5, 0, Math.PI * 2); ctx.fill();
      label(ctx, 'cos θ', F.X(c / 2), F.Y(0) + 16, pal.accent, 'center'); label(ctx, 'sin θ', F.X(c) + 6, F.Y(s / 2), pal['gold-text']);
      // sine graph traced up to theta, with a guide from the point
      plot(ctx, F, W, H, (x) => (x >= gx && x <= gx + 2 * Math.PI ? Math.sin(x - gx) : NaN), pal.rule, 1.5);
      plot(ctx, F, W, H, (x) => (x >= gx && x <= gx + ((th % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI) ? Math.sin(x - gx) : NaN), pal.gold, 2.6);
      const tx = gx + ((th % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
      ctx.setLineDash([4, 4]); ctx.strokeStyle = pal.muted; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(F.X(c), F.Y(s)); ctx.lineTo(F.X(tx), F.Y(s)); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = pal['gold-text']; ctx.beginPath(); ctx.arc(F.X(tx), F.Y(s), 4, 0, Math.PI * 2); ctx.fill();
      return [`θ = ${fmt(sc.theta, 4)}° = ${fmt(th, 4)} rad`, `cos θ = ${fmt(c)}, sin θ = ${fmt(s)}, tan θ = ${Math.abs(c) < 1e-9 ? 'undefined' : fmt(s / c)}`];
    },
  },

  parametric: {
    view: (s, fn, sc) => {
      const t0 = fn.tmin ? fn.tmin(sc) : 0, t1 = fn.tmax ? fn.tmax(sc) : 2 * Math.PI;
      const xs = rangeOf((t) => fn.x({ ...sc, t }), t0, t1), ys = rangeOf((t) => fn.y({ ...sc, t }), t0, t1);
      const px = pad(xs, 0.2), py = pad(ys, 0.2); return { xmin: px[0], xmax: px[1], ymin: py[0], ymax: py[1] };
    },
    draw(ctx, F, W, H, pal, fn, sc) {
      const t0 = fn.tmin ? fn.tmin(sc) : 0, t1 = fn.tmax ? fn.tmax(sc) : 2 * Math.PI, tc = t0 + (t1 - t0) * sc.t;
      const P = (t) => [fn.x({ ...sc, t }), fn.y({ ...sc, t })];
      for (const [end, col, w] of [[t1, pal.rule, 1.6], [tc, pal.gold, 2.8]]) {
        ctx.strokeStyle = col; ctx.lineWidth = w; ctx.beginPath();
        for (let i = 0; i <= 600; i++) { const t = t0 + ((end - t0) * i) / 600, [x, y] = P(t); if (i) ctx.lineTo(F.X(x), F.Y(y)); else ctx.moveTo(F.X(x), F.Y(y)); }
        ctx.stroke();
      }
      const [x, y] = P(tc), e = 1e-4 * Math.max(1, Math.abs(t1 - t0)), [x2, y2] = P(tc + e), vx = (x2 - x) / e, vy = (y2 - y) / e;
      ctx.strokeStyle = pal.accent; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(F.X(x), F.Y(y)); ctx.lineTo(F.X(x + vx * 0.25), F.Y(y + vy * 0.25)); ctx.stroke();
      ctx.fillStyle = pal.ink; ctx.beginPath(); ctx.arc(F.X(x), F.Y(y), 5, 0, Math.PI * 2); ctx.fill();
      return [`t = ${fmt(tc)}: (x, y) = (${fmt(x)}, ${fmt(y)})`, `velocity (dx/dt, dy/dt) = (${fmt(vx)}, ${fmt(vy)}), speed ${fmt(Math.hypot(vx, vy))}`];
    },
  },

  vector_field: {
    view: () => ({ xmin: -4, xmax: 4, ymin: -3, ymax: 3 }),
    draw(ctx, F, W, H, pal, fn, sc, s, st) {
      const V = (x, y) => [fn.P({ ...sc, x, y }), fn.Q({ ...sc, x, y })];
      const step = (F.xmax - F.xmin) / 18;
      let vmax = 1e-9;
      const pts = [];
      for (let x = F.xmin + step / 2; x <= F.xmax; x += step) for (let y = F.ymin + step / 2; y <= F.ymax; y += step) {
        const [u, v] = V(x, y); if (Number.isFinite(u) && Number.isFinite(v)) { pts.push([x, y, u, v]); vmax = Math.max(vmax, Math.hypot(u, v)); }
      }
      for (const [x, y, u, v] of pts) {
        const m = Math.hypot(u, v); if (m < 1e-12) continue;
        const len = step * 0.42 * Math.min(1, 0.35 + m / vmax), ex = x + (u / m) * len, ey = y + (v / m) * len;
        const ang = Math.atan2(F.Y(ey) - F.Y(y), F.X(ex) - F.X(x));
        ctx.strokeStyle = pal['ink-soft']; ctx.fillStyle = pal['ink-soft']; ctx.lineWidth = 1.4; ctx.globalAlpha = 0.45 + 0.55 * (m / vmax);
        ctx.beginPath(); ctx.moveTo(F.X(x), F.Y(y)); ctx.lineTo(F.X(ex), F.Y(ey)); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(F.X(ex), F.Y(ey)); ctx.lineTo(F.X(ex) - 6 * Math.cos(ang - 0.4), F.Y(ey) - 6 * Math.sin(ang - 0.4)); ctx.lineTo(F.X(ex) - 6 * Math.cos(ang + 0.4), F.Y(ey) - 6 * Math.sin(ang + 0.4)); ctx.fill();
      }
      ctx.globalAlpha = 1;
      for (const [x0, y0] of st.flows || []) {  // RK4 flow lines, forward and backward
        for (const dir of [1, -1]) {
          let x = x0, y = y0; const h = 0.02 * dir;
          ctx.strokeStyle = pal.gold; ctx.lineWidth = 2.4; ctx.beginPath(); ctx.moveTo(F.X(x), F.Y(y));
          for (let i = 0; i < 1500; i++) {
            const k1 = V(x, y), k2 = V(x + h * k1[0] / 2, y + h * k1[1] / 2), k3 = V(x + h * k2[0] / 2, y + h * k2[1] / 2), k4 = V(x + h * k3[0], y + h * k3[1]);
            const nx = x + (h / 6) * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0]), ny = y + (h / 6) * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1]);
            if (!Number.isFinite(nx) || !Number.isFinite(ny) || Math.abs(nx) > 1e3 || Math.abs(ny) > 1e3) break;
            x = nx; y = ny; ctx.lineTo(F.X(x), F.Y(y));
          }
          ctx.stroke();
        }
        ctx.fillStyle = pal.gold; ctx.beginPath(); ctx.arc(F.X(x0), F.Y(y0), 4.5, 0, Math.PI * 2); ctx.fill();
      }
      const out = ['Click the plot to drop a flow line (the path a particle would follow).'];
      if (st.hoverX !== undefined) {
        const x = st.hoverX, y = st.hoverY, e = 1e-4, [u, v] = V(x, y);
        const div = (V(x + e, y)[0] - V(x - e, y)[0] + V(x, y + e)[1] - V(x, y - e)[1]) / (2 * e);
        const curl = (V(x + e, y)[1] - V(x - e, y)[1] - (V(x, y + e)[0] - V(x, y - e)[0])) / (2 * e);
        out.push(`At (${fmt(x, 3)}, ${fmt(y, 3)}): F = (${fmt(u)}, ${fmt(v)}), div F = ${fmt(div, 3)}, curl F = ${fmt(curl, 3)}`);
      }
      return out;
    },
  },

  transform2d: {
    view: () => ({ xmin: -4, xmax: 4, ymin: -3, ymax: 3 }),
    draw(ctx, F, W, H, pal, fn, sc) {
      const a = fn.a(sc), b = fn.b(sc), c = fn.c(sc), d = fn.d(sc), T = (x, y) => [a * x + b * y, c * x + d * y];
      ctx.lineWidth = 1; ctx.strokeStyle = pal.accent; ctx.globalAlpha = 0.35;
      for (let k = -6; k <= 6; k++) {
        for (const [p, q] of [[[k, -6], [k, 6]], [[-6, k], [6, k]]]) {
          const [x1, y1] = T(...p), [x2, y2] = T(...q);
          ctx.beginPath(); ctx.moveTo(F.X(x1), F.Y(y1)); ctx.lineTo(F.X(x2), F.Y(y2)); ctx.stroke();
        }
      }
      ctx.globalAlpha = 1;
      const det = a * d - b * c;
      ctx.fillStyle = det >= 0 ? pal.gold : pal.bad; ctx.globalAlpha = 0.35;
      ctx.beginPath(); [[0, 0], [1, 0], [1, 1], [0, 1]].forEach(([x, y], i) => { const [u, v] = T(x, y); if (i) ctx.lineTo(F.X(u), F.Y(v)); else ctx.moveTo(F.X(u), F.Y(v)); });
      ctx.closePath(); ctx.fill(); ctx.globalAlpha = 1;
      const arrow = ([u, v], col, name) => {
        ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(F.X(0), F.Y(0)); ctx.lineTo(F.X(u), F.Y(v)); ctx.stroke();
        ctx.beginPath(); ctx.arc(F.X(u), F.Y(v), 4, 0, Math.PI * 2); ctx.fill(); label(ctx, name, F.X(u) + 6, F.Y(v) - 6, col);
      };
      arrow(T(1, 0), pal.accent, 'T(e₁)'); arrow(T(0, 1), pal['gold-text'], 'T(e₂)');
      const tr = a + d, disc = tr * tr - 4 * det;
      const eig = disc >= 0 ? `eigenvalues ${fmt((tr + Math.sqrt(disc)) / 2, 3)}, ${fmt((tr - Math.sqrt(disc)) / 2, 3)}` : `complex eigenvalues ${fmt(tr / 2, 3)} ± ${fmt(Math.sqrt(-disc) / 2, 3)}i (a rotation part)`;
      return [`Matrix [[${fmt(a, 3)}, ${fmt(b, 3)}], [${fmt(c, 3)}, ${fmt(d, 3)}]]: det = ${fmt(det)} (area ×${fmt(Math.abs(det), 3)}${det < 0 ? ', orientation flipped' : ''})`, eig];
    },
  },
};

/** Plays a SimSpec `kind: "math"` widget. `editable` lets the student type their own functions. */
export default function MathSim({ spec, editable = false }) {
  const W_ = WIDGETS[spec.widget];
  const [values, setValues] = useState(() => Object.fromEntries((spec.params || []).map((p) => [p.name, p.value])));
  const [overrides, setOverrides] = useState({});
  const [method, setMethod] = useState(spec.method || 'left');
  const [hover, setHover] = useState(null);
  const [flows, setFlows] = useState([]);
  const [playing, setPlaying] = useState(false);
  const [readouts, setReadouts] = useState([]);
  const canvasRef = useRef(null);
  const [fns, errs] = useCompiled(spec, overrides);
  const scope = useMemo(() => ({ e: Math.E, ...values }), [values]);
  const ready = W_ && !errs.length && (FIELDS[spec.widget] || []).every((f) => fns[f] || f === 'target' || f === 'tmin' || f === 'tmax');

  useEffect(() => { setValues(Object.fromEntries((spec.params || []).map((p) => [p.name, p.value]))); setFlows([]); }, [spec]);

  const view = useMemo(() => {
    if (!ready) return { xmin: -5, xmax: 5, ymin: -4, ymax: 4 };
    if (spec.view) return spec.view;
    try { const v = W_.view(spec, fns, scope); return Object.values(v).every(Number.isFinite) && v.xmax > v.xmin && v.ymax > v.ymin ? v : { xmin: -5, xmax: 5, ymin: -4, ymax: 4 }; }
    catch { return { xmin: -5, xmax: 5, ymin: -4, ymax: 4 }; }
    // the view follows the functions and a/b/L, not every slider tick
  }, [spec, fns, ready]); // eslint-disable-line react-hooks/exhaustive-deps

  const frameRef = useRef(null);
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !ready) return;
    const dpr = window.devicePixelRatio || 1, W = canvas.clientWidth, H = canvas.clientHeight;
    if (canvas.width !== W * dpr || canvas.height !== H * dpr) { canvas.width = W * dpr; canvas.height = H * dpr; }
    const ctx = canvas.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const pal = canvasPalette(), F = frameFor(W, H, view, EQUAL_AXES.has(spec.widget));
    frameRef.current = F;
    drawGrid(ctx, F, W, H, pal);
    try {
      setReadouts(W_.draw(ctx, F, W, H, pal, fns, scope, spec, { method, hoverX: hover?.x, hoverY: hover?.y, flows }) || []);
    } catch (e) { setReadouts([`Could not draw: ${e.message}`]); }
  }, [ready, view, spec, fns, scope, method, hover, flows, W_]);

  useEffect(() => { draw(); }, [draw]);
  useEffect(() => {
    const ro = new ResizeObserver(() => draw());
    if (canvasRef.current) ro.observe(canvasRef.current);
    return () => ro.disconnect();
  }, [draw]);

  // Animate: sweep the widget's main slider (h -> 0, n up, theta around ...)
  useEffect(() => {
    const name = SWEEP[spec.widget];
    const p = (spec.params || []).find((q) => q.name === name);
    if (!playing || !p) return undefined;
    let raf, last = performance.now();
    const shrink = name === 'eps' || name === 'h';
    const tick = (now) => {
      const dt = (now - last) / 1000; last = now;
      setValues((v) => {
        let x = v[name];
        if (shrink) { x = x * Math.exp(-0.6 * dt); if (Math.abs(x) < (p.max - p.min) * 0.004) x = p.max * (name === 'h' ? Math.sign(v[name]) || 1 : 1); }
        else { x += ((p.max - p.min) / 6) * dt; if (x > p.max) x = p.min; }
        return { ...v, [name]: name === 'n' || name === 'N' ? Math.round(x * 100) / 100 : x };
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, spec]);

  const onMove = (e) => {
    const F = frameRef.current; if (!F) return;
    const r = canvasRef.current.getBoundingClientRect();
    setHover({ x: F.fx(e.clientX - r.left), y: F.fy(e.clientY - r.top) });
  };
  const onClick = () => { if (spec.widget === 'vector_field' && hover) setFlows((f) => [...f.slice(-5), [hover.x, hover.y]]); };

  if (!W_) return <p className="notice notice-bad">Unknown math widget "{spec.widget}".</p>;

  return (
    <div className="sim stack-sm">
      <div className="btn-row" style={{ justifyContent: 'space-between' }}>
        <div>
          <h3>{spec.title}</h3>
          {spec.description && <p className="hint" style={{ maxWidth: '70ch' }}>{spec.description}</p>}
        </div>
        <div className="btn-row">
          {SWEEP[spec.widget] && (
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => setPlaying((p) => !p)}>
              {playing ? <Pause size={14} aria-hidden="true" /> : <Play size={14} aria-hidden="true" />} {playing ? 'Pause' : 'Animate'}
            </button>
          )}
          <button type="button" className="btn btn-quiet btn-sm" onClick={() => { setPlaying(false); setValues(Object.fromEntries((spec.params || []).map((p) => [p.name, p.value]))); setFlows([]); setOverrides({}); }}>
            <RotateCcw size={14} aria-hidden="true" /> Reset
          </button>
        </div>
      </div>

      {editable && (FIELDS[spec.widget] || []).length > 0 && (
        <div className="math-fields">
          {(FIELDS[spec.widget] || []).map((f) => (
            <label key={f} className="field">
              <span className="hint mono">{f}{varsFor(spec.widget, f) ? `(${varsFor(spec.widget, f)})` : ''}</span>
              <input className="input mono" spellCheck={false} value={overrides[f] ?? String(spec[f] ?? '')}
                onChange={(e) => setOverrides((o) => ({ ...o, [f]: e.target.value }))} />
            </label>
          ))}
        </div>
      )}
      {errs.length > 0 && <p className="notice notice-bad">{errs.join(' · ')}</p>}

      <div className="readouts math-readouts" role="status">
        {readouts.map((r, i) => <p key={i} className={i === 0 ? 'lead' : 'hint'}>{r}</p>)}
      </div>
      <canvas ref={canvasRef} className="math-canvas math-sim-canvas" aria-label={spec.title}
        onPointerMove={onMove} onPointerLeave={() => setHover(null)} onClick={onClick} />


      {spec.widget === 'riemann' && (
        <div className="btn-row" role="group" aria-label="Rule">
          {['left', 'right', 'mid', 'trap'].map((m) => (
            <button key={m} type="button" className={`btn btn-sm ${method === m ? 'btn-primary' : 'btn-quiet'}`} aria-pressed={method === m} onClick={() => setMethod(m)}>
              {{ left: 'Left', right: 'Right', mid: 'Midpoint', trap: 'Trapezoid' }[m]}
            </button>
          ))}
        </div>
      )}

      {(spec.params || []).length > 0 && (
        <div className="sliders">
          {spec.params.map((p) => (
            <div key={p.name} className="slider">
              <label htmlFor={`ms-${p.name}`}><span>{p.label || p.name}</span><b className="num">{fmt(values[p.name] ?? p.value)}{p.unit ? ` ${p.unit}` : ''}</b></label>
              <input id={`ms-${p.name}`} type="range" min={p.min} max={p.max} step={p.step || (p.max - p.min) / 200}
                value={values[p.name] ?? p.value} onChange={(e) => { setPlaying(false); setValues((v) => ({ ...v, [p.name]: Number(e.target.value) })); }} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
