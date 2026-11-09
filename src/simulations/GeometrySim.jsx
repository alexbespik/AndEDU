import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { RotateCcw } from 'lucide-react';
import katex from 'katex';
import { tryCompile } from '../lib/expr';

const NAMED_COLORS = {
  accent: 'var(--accent, #23a55a)',
  gold: 'var(--gold, #e5b85c)',
  green: 'var(--accent, #2ecc71)',
  cyan: 'var(--info, #66d9ef)',
  pink: 'var(--bad, #f92672)',
  orange: 'var(--gold-text, #fd971f)',
  purple: 'var(--plum, #ae81ff)',
  white: 'var(--ink, #ffffff)',
  bad: 'var(--bad, #f92672)',
  info: 'var(--info, #66d9ef)',
  muted: 'var(--muted, #747c78)',
};

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function resolveColor(c, fallback = 'var(--ink)') {
  if (!c) return fallback;
  const lower = String(c).toLowerCase().trim();
  if (NAMED_COLORS[lower]) return NAMED_COLORS[lower];
  return c;
}

function renderKaTeX(src) {
  if (!src) return '';
  const formula = String(src).replace(/^\$+|\$+$/g, '').trim();
  try {
    return katex.renderToString(formula, {
      throwOnError: false,
      displayMode: false,
      macros: {
        '\\ihat': '\\hat{\\imath}',
        '\\jhat': '\\hat{\\jmath}',
        '\\khat': '\\hat{k}',
        '\\uvec': '\\mathbf{\\hat{#1}}',
      },
    });
  } catch {
    return escapeHtml(src);
  }
}

export default function GeometrySim({ spec }) {
  // Initial parameters from spec.params
  const initialParams = useMemo(() => {
    const p = {};
    for (const item of (spec?.params || [])) {
      p[item.name] = Number(item.value ?? item.default ?? item.min ?? 0);
    }
    return p;
  }, [spec]);

  const [params, setParams] = useState(initialParams);
  const [showProjections, setShowProjections] = useState(true);
  const [draggedBodies, setDraggedBodies] = useState({});
  const [draggedForces, setDraggedForces] = useState({});
  const [activeDrag, setActiveDrag] = useState(null);
  const svgRef = useRef(null);

  useEffect(() => {
    setParams(initialParams);
    setDraggedBodies({});
    setDraggedForces({});
    setActiveDrag(null);
  }, [initialParams]);

  const resetParams = useCallback(() => {
    setParams(initialParams);
    setDraggedBodies({});
    setDraggedForces({});
    setActiveDrag(null);
  }, [initialParams]);

  const handleSliderChange = (name, val) => {
    setParams((prev) => ({ ...prev, [name]: Number(val) }));
    setDraggedForces({});
    setDraggedBodies({});
  };

  // Expression evaluator against current params
  const evalExpr = useCallback((exprOrVal, fallback = 0) => {
    if (typeof exprOrVal === 'number') return Number.isFinite(exprOrVal) ? exprOrVal : fallback;
    if (exprOrVal === null || exprOrVal === undefined || exprOrVal === '') return fallback;
    const [fn, err] = tryCompile(String(exprOrVal), fallback);
    if (err) return fallback;
    try {
      const res = fn(params);
      return Number.isFinite(res) ? res : fallback;
    } catch {
      return fallback;
    }
  }, [params]);

  // View bounds & transformations
  const view = spec?.view || {};
  const xmin = Number(view.xmin ?? -5);
  const xmax = Number(view.xmax ?? 5);
  const ymin = Number(view.ymin ?? -5);
  const ymax = Number(view.ymax ?? 5);
  const widthSpan = Math.max(0.1, xmax - xmin);
  const heightSpan = Math.max(0.1, ymax - ymin);

  const SVG_W = 640;
  const SVG_H = 460;
  const PADDING = 30;
  const innerW = SVG_W - 2 * PADDING;
  const innerH = SVG_H - 2 * PADDING;

  const toSvgX = useCallback((x) => PADDING + ((x - xmin) / widthSpan) * innerW, [xmin, widthSpan, innerW]);
  const toSvgY = useCallback((y) => SVG_H - PADDING - ((y - ymin) / heightSpan) * innerH, [ymin, heightSpan, innerH]);
  const scaleLenX = useCallback((l) => (l / widthSpan) * innerW, [widthSpan, innerW]);
  const scaleLenY = useCallback((l) => (l / heightSpan) * innerH, [heightSpan, innerH]);

  // Pointer to math coordinate inverter
  const getPointerMathCoords = useCallback((e) => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const ctm = svg.getScreenCTM();
    if (ctm) {
      const svgP = pt.matrixTransform(ctm.inverse());
      const mathX = xmin + ((svgP.x - PADDING) / innerW) * widthSpan;
      const mathY = ymin + ((SVG_H - PADDING - svgP.y) / innerH) * heightSpan;
      return { x: mathX, y: mathY };
    }
    return { x: 0, y: 0 };
  }, [xmin, ymin, widthSpan, heightSpan, innerW, innerH]);

  // Evaluated bodies map for force origins and rendering
  const evaluatedBodies = useMemo(() => {
    const bodies = spec?.bodies || [];
    return bodies.map((b) => {
      const override = b.id ? draggedBodies[b.id] : null;
      const type = b.type || 'box';
      const x = override ? override.x : evalExpr(b.x, 0);
      const y = override ? override.y : evalExpr(b.y, 0);
      const width = evalExpr(b.width, 1);
      const height = evalExpr(b.height, 1);
      const radius = evalExpr(b.radius, 0.5);
      const angle = evalExpr(b.angle, 0);
      const x1 = evalExpr(b.x1, 0);
      const y1 = evalExpr(b.y1, 0);
      const x2 = evalExpr(b.x2, 1);
      const y2 = evalExpr(b.y2, 1);
      return {
        ...b,
        type,
        x, y,
        width, height,
        radius, angle,
        x1, y1, x2, y2,
      };
    });
  }, [spec?.bodies, draggedBodies, evalExpr]);

  const bodyMap = useMemo(() => {
    const map = {};
    for (const b of evaluatedBodies) {
      if (b.id) map[b.id] = b;
    }
    return map;
  }, [evaluatedBodies]);

  // Evaluated forces
  const evaluatedForces = useMemo(() => {
    const forces = spec?.forces || [];
    return forces.map((f, idx) => {
      const fId = f.id || `f_${idx}`;
      const override = draggedForces[fId];

      let ox = 0;
      let oy = 0;
      if (f.body && bodyMap[f.body]) {
        const parent = bodyMap[f.body];
        ox = parent.x;
        oy = parent.y;
      }
      if (f.origin && Array.isArray(f.origin) && f.origin.length >= 2) {
        ox = evalExpr(f.origin[0], ox);
        oy = evalExpr(f.origin[1], oy);
      } else if (f.x !== undefined && f.y !== undefined) {
        ox = evalExpr(f.x, ox);
        oy = evalExpr(f.y, oy);
      }

      const mag = override ? override.mag : evalExpr(f.magnitude, 1);
      const deg = override ? override.deg : evalExpr(f.angle, 0);
      const rad = (deg * Math.PI) / 180;
      const dx = mag * Math.cos(rad);
      const dy = mag * Math.sin(rad);

      return {
        ...f,
        id: fId,
        ox,
        oy,
        dx,
        dy,
        mag,
        deg,
      };
    });
  }, [spec?.forces, bodyMap, draggedForces, evalExpr]);

  // Pointer drag event handlers with setPointerCapture
  const handleForcePointerDown = (e, f) => {
    e.stopPropagation();
    e.preventDefault();
    try {
      e.target.setPointerCapture(e.pointerId);
    } catch (err) {}
    setActiveDrag({
      type: 'force',
      id: f.id,
      force: f,
      pointerId: e.pointerId,
    });
  };

  const handleBodyPointerDown = (e, b) => {
    e.stopPropagation();
    e.preventDefault();
    try {
      e.target.setPointerCapture(e.pointerId);
    } catch (err) {}
    const coords = getPointerMathCoords(e);
    setActiveDrag({
      type: 'body',
      id: b.id || `b_${b.x}_${b.y}`,
      body: b,
      pointerId: e.pointerId,
      offsetX: coords.x - b.x,
      offsetY: coords.y - b.y,
    });
  };

  const handleSvgPointerMove = (e) => {
    if (!activeDrag) return;
    const coords = getPointerMathCoords(e);

    if (activeDrag.type === 'force') {
      const f = activeDrag.force;
      const dx = coords.x - f.ox;
      const dy = coords.y - f.oy;
      const newMag = Math.max(0.1, Math.sqrt(dx * dx + dy * dy));
      let newDeg = (Math.atan2(dy, dx) * 180) / Math.PI;
      if (newDeg < 0) newDeg += 360;

      // Update reactive sliders if corresponding param exists
      const magParam = (spec?.params || []).find((p) => p.name === f.magnitude || p.name === 'F' || p.name === 'mag');
      const angleParam = (spec?.params || []).find((p) => p.name === f.angle || p.name === 'theta' || p.name === 'angle');

      setParams((prev) => {
        const next = { ...prev };
        if (magParam) next[magParam.name] = Number(newMag.toFixed(2));
        if (angleParam) next[angleParam.name] = Number(newDeg.toFixed(1));
        return next;
      });

      setDraggedForces((prev) => ({
        ...prev,
        [activeDrag.id]: { mag: newMag, deg: newDeg }
      }));
    } else if (activeDrag.type === 'body') {
      const b = activeDrag.body;
      const newX = coords.x - (activeDrag.offsetX || 0);
      const newY = coords.y - (activeDrag.offsetY || 0);

      const xParam = (spec?.params || []).find((p) => p.name === b.x || p.name === `${b.id}_x`);
      const yParam = (spec?.params || []).find((p) => p.name === b.y || p.name === `${b.id}_y`);

      setParams((prev) => {
        const next = { ...prev };
        if (xParam) next[xParam.name] = Number(newX.toFixed(2));
        if (yParam) next[yParam.name] = Number(newY.toFixed(2));
        return next;
      });

      setDraggedBodies((prev) => ({
        ...prev,
        [activeDrag.id]: { x: newX, y: newY }
      }));
    }
  };

  const handleSvgPointerUp = (e) => {
    if (activeDrag) {
      try {
        e.target.releasePointerCapture(activeDrag.pointerId);
      } catch (err) {}
      setActiveDrag(null);
    }
  };

  // Evaluated elements
  const evaluatedElements = useMemo(() => {
    const elements = spec?.elements || [];
    return elements.map((el, idx) => {
      const type = el.type || 'line';
      const x = evalExpr(el.x, 0);
      const y = evalExpr(el.y, 0);
      const x1 = evalExpr(el.x1, 0);
      const y1 = evalExpr(el.y1, 0);
      const x2 = evalExpr(el.x2, 0);
      const y2 = evalExpr(el.y2, 0);
      const radius = evalExpr(el.radius, 1);
      const startAngle = evalExpr(el.startAngle, 0);
      const endAngle = evalExpr(el.endAngle, 90);
      const size = evalExpr(el.size, 0.4);
      const angle = evalExpr(el.angle, 0);
      let points = el.points;
      if (Array.isArray(points)) {
        points = points.map((pt) => [evalExpr(pt[0], 0), evalExpr(pt[1], 0)]);
      }
      return {
        ...el,
        idx,
        type,
        x, y,
        x1, y1, x2, y2,
        radius, startAngle, endAngle,
        size, angle,
        points,
      };
    });
  }, [spec?.elements, evalExpr]);

  // Grid lines
  const gridLines = useMemo(() => {
    if (view.grid === false) return { xLines: [], yLines: [] };
    const stepX = widthSpan > 20 ? 5 : widthSpan > 10 ? 2 : 1;
    const stepY = heightSpan > 20 ? 5 : heightSpan > 10 ? 2 : 1;
    const xLines = [];
    const yLines = [];

    const firstX = Math.ceil(xmin / stepX) * stepX;
    for (let gx = firstX; gx <= xmax; gx += stepX) {
      if (Math.abs(gx) < 1e-6) continue;
      xLines.push(gx);
    }
    const firstY = Math.ceil(ymin / stepY) * stepY;
    for (let gy = firstY; gy <= ymax; gy += stepY) {
      if (Math.abs(gy) < 1e-6) continue;
      yLines.push(gy);
    }
    return { xLines, yLines };
  }, [view.grid, xmin, xmax, ymin, ymax, widthSpan, heightSpan]);

  if (!spec) return null;

  return (
    <div className="geometry-sim-container panel" style={{ background: 'var(--surface)', border: '1px solid var(--rule)', borderRadius: 'var(--radius, 8px)', padding: 'var(--space-3, 12px)', margin: 'var(--space-3, 12px) 0' }}>
      {/* Title & Description */}
      {(spec.title || spec.description) && (
        <div style={{ marginBottom: 'var(--space-2, 8px)' }}>
          {spec.title && <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: 'var(--ink)' }}>{spec.title}</h4>}
          {spec.description && <p className="hint" style={{ margin: '4px 0 0 0', fontSize: '0.82rem', color: 'var(--muted)' }}>{spec.description}</p>}
        </div>
      )}

      {/* SVG Canvas */}
      <div style={{ position: 'relative', width: '100%', overflow: 'hidden', borderRadius: 'var(--radius-sm, 6px)', background: 'var(--code-bg, #0d1117)', border: '1px solid var(--rule)' }}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${SVG_W} ${SVG_H}`}
          style={{ display: 'block', width: '100%', height: 'auto', userSelect: 'none', touchAction: 'none' }}
          onPointerMove={handleSvgPointerMove}
          onPointerUp={handleSvgPointerUp}
          onPointerCancel={handleSvgPointerUp}
        >
          <defs>
            {/* Standard arrowhead markers */}
            {Object.keys(NAMED_COLORS).map((c) => (
              <marker
                key={c}
                id={`geom-arrow-${c}`}
                viewBox="0 0 10 10"
                refX="8"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill={NAMED_COLORS[c] || c} />
              </marker>
            ))}
            <marker
              id="geom-arrow-default"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="var(--ink)" />
            </marker>
            <marker
              id="geom-dim-arrow"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="5"
              markerHeight="5"
              orient="auto"
            >
              <path d="M 0 2 L 8 5 L 0 8 z" fill="var(--muted)" />
            </marker>
            <marker
              id="geom-dim-arrow-rev"
              viewBox="0 0 10 10"
              refX="0"
              refY="5"
              markerWidth="5"
              markerHeight="5"
              orient="auto"
            >
              <path d="M 8 2 L 0 5 L 8 8 z" fill="var(--muted)" />
            </marker>

            {/* Hatch pattern for ground / wall surfaces */}
            <pattern id="geom-hatch" width="10" height="10" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
              <line x1="0" y1="0" x2="0" y2="10" stroke="var(--muted)" strokeWidth="1.5" opacity="0.4" />
            </pattern>
          </defs>

          {/* Grid lines */}
          {gridLines.xLines.map((gx) => (
            <line
              key={`gx-${gx}`}
              x1={toSvgX(gx)}
              y1={PADDING}
              x2={toSvgX(gx)}
              y2={SVG_H - PADDING}
              stroke="var(--rule)"
              strokeDasharray="2 3"
              strokeWidth="0.8"
              opacity="0.35"
            />
          ))}
          {gridLines.yLines.map((gy) => (
            <line
              key={`gy-${gy}`}
              x1={PADDING}
              y1={toSvgY(gy)}
              x2={SVG_W - PADDING}
              y2={toSvgY(gy)}
              stroke="var(--rule)"
              strokeDasharray="2 3"
              strokeWidth="0.8"
              opacity="0.35"
            />
          ))}

          {/* Axes */}
          {view.axes !== false && (
            <g opacity="0.6">
              {ymin <= 0 && ymax >= 0 && (
                <line
                  x1={PADDING}
                  y1={toSvgY(0)}
                  x2={SVG_W - PADDING}
                  y2={toSvgY(0)}
                  stroke="var(--muted)"
                  strokeWidth="1.2"
                />
              )}
              {xmin <= 0 && xmax >= 0 && (
                <line
                  x1={toSvgX(0)}
                  y1={PADDING}
                  x2={toSvgX(0)}
                  y2={SVG_H - PADDING}
                  stroke="var(--muted)"
                  strokeWidth="1.2"
                />
              )}
            </g>
          )}

          {/* Rotated/Custom Coordinate Axes */}
          {spec.axes && (() => {
            const ax = evalExpr(spec.axes.x, 0);
            const ay = evalExpr(spec.axes.y, 0);
            const aDeg = evalExpr(spec.axes.angle, 0);
            const sx = toSvgX(ax);
            const sy = toSvgY(ay);
            const len = 60;
            const xLabel = spec.axes.xLabel || "x'";
            const yLabel = spec.axes.yLabel || "y'";
            return (
              <g transform={`translate(${sx}, ${sy}) rotate(${-aDeg})`}>
                <line x1={0} y1={0} x2={len} y2={0} stroke="var(--muted)" strokeWidth="1.5" markerEnd="url(#geom-arrow-default)" strokeDasharray="3 2" />
                <line x1={0} y1={0} x2={0} y2={-len} stroke="var(--muted)" strokeWidth="1.5" markerEnd="url(#geom-arrow-default)" strokeDasharray="3 2" />
                <text x={len + 6} y={4} fill="var(--muted)" fontSize="11" fontFamily="var(--font-mono)">{xLabel}</text>
                <text x={-4} y={-len - 6} fill="var(--muted)" fontSize="11" fontFamily="var(--font-mono)">{yLabel}</text>
              </g>
            );
          })()}

          {/* Render Elements (lines, arcs, right angles, dimensions, polygons) */}
          {evaluatedElements.map((el) => {
            const col = resolveColor(el.color, 'var(--ink-soft)');
            if (el.type === 'line' || el.type === 'segment') {
              const x1 = toSvgX(el.x1);
              const y1 = toSvgY(el.y1);
              const x2 = toSvgX(el.x2);
              const y2 = toSvgY(el.y2);
              return (
                <g key={`el-line-${el.idx}`}>
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke={col}
                    strokeWidth="1.5"
                    strokeDasharray={el.dashed ? '4 3' : undefined}
                    markerEnd={el.arrow ? 'url(#geom-arrow-default)' : undefined}
                  />
                  {el.label && (
                    <foreignObject x={(x1 + x2) / 2 - 20} y={(y1 + y2) / 2 - 24} width="80" height="30" style={{ overflow: 'visible', pointerEvents: 'none' }}>
                      <div
                        style={{ color: col, fontSize: '0.85rem', display: 'inline-block' }}
                        dangerouslySetInnerHTML={{ __html: renderKaTeX(el.label) }}
                      />
                    </foreignObject>
                  )}
                </g>
              );
            }
            if (el.type === 'angle_arc') {
              const cx = toSvgX(el.x);
              const cy = toSvgY(el.y);
              const r = scaleLenX(el.radius || 1);
              const sRad = (el.startAngle * Math.PI) / 180;
              const eRad = (el.endAngle * Math.PI) / 180;
              const x1 = cx + r * Math.cos(sRad);
              const y1 = cy - r * Math.sin(sRad);
              const x2 = cx + r * Math.cos(eRad);
              const y2 = cy - r * Math.sin(eRad);
              const diff = (el.endAngle - el.startAngle + 360) % 360;
              const largeArc = diff > 180 ? 1 : 0;
              const pathData = `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 0 ${x2} ${y2}`;
              const midRad = ((el.startAngle + el.endAngle) / 2 * Math.PI) / 180;
              const lx = cx + (r + 14) * Math.cos(midRad) - 15;
              const ly = cy - (r + 14) * Math.sin(midRad) - 14;

              return (
                <g key={`el-arc-${el.idx}`}>
                  <path d={pathData} fill="none" stroke={col} strokeWidth="1.5" />
                  {el.label && (
                    <foreignObject x={lx} y={ly} width="60" height="30" style={{ overflow: 'visible', pointerEvents: 'none' }}>
                      <div
                        style={{ color: col, fontSize: '0.85rem', display: 'inline-block' }}
                        dangerouslySetInnerHTML={{ __html: renderKaTeX(el.label) }}
                      />
                    </foreignObject>
                  )}
                </g>
              );
            }
            if (el.type === 'right_angle') {
              const cx = toSvgX(el.x);
              const cy = toSvgY(el.y);
              const s = scaleLenX(el.size || 0.4);
              return (
                <g key={`el-ra-${el.idx}`} transform={`translate(${cx}, ${cy}) rotate(${-el.angle})`}>
                  <path d={`M 0 0 L 0 ${-s} L ${s} ${-s} L ${s} 0`} fill="none" stroke={col} strokeWidth="1.2" />
                </g>
              );
            }
            if (el.type === 'dimension') {
              const x1 = toSvgX(el.x1);
              const y1 = toSvgY(el.y1);
              const x2 = toSvgX(el.x2);
              const y2 = toSvgY(el.y2);
              return (
                <g key={`el-dim-${el.idx}`}>
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke="var(--muted)"
                    strokeWidth="1.2"
                    markerStart="url(#geom-dim-arrow-rev)"
                    markerEnd="url(#geom-dim-arrow)"
                  />
                  {el.label && (
                    <foreignObject x={(x1 + x2) / 2 - 25} y={(y1 + y2) / 2 - 20} width="60" height="25" style={{ overflow: 'visible', pointerEvents: 'none' }}>
                      <div
                        style={{ color: 'var(--muted)', fontSize: '0.78rem', textAlign: 'center' }}
                        dangerouslySetInnerHTML={{ __html: renderKaTeX(el.label) }}
                      />
                    </foreignObject>
                  )}
                </g>
              );
            }
            if (el.type === 'polygon' && Array.isArray(el.points)) {
              const ptsStr = el.points.map(([px, py]) => `${toSvgX(px)},${toSvgY(py)}`).join(' ');
              return (
                <polygon
                  key={`el-poly-${el.idx}`}
                  points={ptsStr}
                  fill={el.fill || 'rgba(116, 124, 120, 0.15)'}
                  stroke={col}
                  strokeWidth="1.5"
                />
              );
            }
            return null;
          })}

          {/* Render Bodies (wedge, box, sphere, rod, wall, pulley, point) */}
          {evaluatedBodies.map((b) => {
            const strokeCol = resolveColor(b.color, 'var(--gold)');
            const fillCol = b.fill || 'rgba(229, 184, 92, 0.2)';

            if (b.type === 'wedge' || b.type === 'ramp') {
              const p1x = toSvgX(b.x);
              const p1y = toSvgY(b.y);
              const p2x = toSvgX(b.x + b.width);
              const p2y = toSvgY(b.y);
              const p3x = toSvgX(b.x + b.width);
              const p3y = toSvgY(b.y + b.height);
              const pts = `${p1x},${p1y} ${p2x},${p2y} ${p3x},${p3y}`;
              return (
                <g key={b.id || `wedge-${b.x}`}>
                  <polygon points={pts} fill={fillCol} stroke={strokeCol} strokeWidth="1.8" />
                  {b.label && (
                    <foreignObject x={(p1x + p2x) / 2 - 20} y={(p1y + p3y) / 2 - 15} width="60" height="30" style={{ overflow: 'visible', pointerEvents: 'none' }}>
                      <div style={{ color: strokeCol, fontSize: '0.85rem' }} dangerouslySetInnerHTML={{ __html: renderKaTeX(b.label) }} />
                    </foreignObject>
                  )}
                </g>
              );
            }

            if (b.type === 'box') {
              const cx = toSvgX(b.x);
              const cy = toSvgY(b.y);
              const w = scaleLenX(b.width);
              const h = scaleLenY(b.height);
              return (
                <g key={b.id || `box-${b.x}`} transform={`translate(${cx}, ${cy}) rotate(${-b.angle})`}>
                  <rect
                    x={-w / 2}
                    y={-h / 2}
                    width={w}
                    height={h}
                    fill={fillCol}
                    stroke={strokeCol}
                    strokeWidth="1.8"
                    rx="2"
                  />
                  {b.label && (
                    <foreignObject x={-w / 2} y={-14} width={w} height="28" style={{ overflow: 'visible', pointerEvents: 'none' }}>
                      <div
                        style={{ color: strokeCol, fontSize: '0.88rem', fontWeight: 600, textAlign: 'center', lineHeight: '28px' }}
                        dangerouslySetInnerHTML={{ __html: renderKaTeX(b.label) }}
                      />
                    </foreignObject>
                  )}
                  {/* Body Center Drag Handle */}
                  <g
                    style={{ cursor: activeDrag?.id === (b.id || `b_${b.x}_${b.y}`) ? 'grabbing' : 'grab' }}
                    onPointerDown={(e) => handleBodyPointerDown(e, b)}
                  >
                    <circle
                      cx="0"
                      cy="0"
                      r={activeDrag?.id === (b.id || `b_${b.x}_${b.y}`) ? 7 : 4.5}
                      fill="var(--gold, #e5b85c)"
                      stroke="#ffffff"
                      strokeWidth="1.5"
                      opacity="0.9"
                      style={{ filter: 'drop-shadow(0 1px 3px rgba(0,0,0,0.5))' }}
                    />
                    <circle cx="0" cy="0" r="14" fill="transparent" />
                  </g>
                </g>
              );
            }

            if (b.type === 'sphere' || b.type === 'circle') {
              const cx = toSvgX(b.x);
              const cy = toSvgY(b.y);
              const r = scaleLenX(b.radius);
              return (
                <g key={b.id || `sphere-${b.x}`}>
                  <circle cx={cx} cy={cy} r={r} fill={fillCol} stroke={strokeCol} strokeWidth="1.8" />
                  {b.label && (
                    <foreignObject x={cx - 20} y={cy - 12} width="40" height="24" style={{ overflow: 'visible', pointerEvents: 'none' }}>
                      <div style={{ color: strokeCol, fontSize: '0.85rem', textAlign: 'center' }} dangerouslySetInnerHTML={{ __html: renderKaTeX(b.label) }} />
                    </foreignObject>
                  )}
                  {/* Body Center Drag Handle */}
                  <g
                    style={{ cursor: activeDrag?.id === (b.id || `b_${b.x}_${b.y}`) ? 'grabbing' : 'grab' }}
                    onPointerDown={(e) => handleBodyPointerDown(e, b)}
                  >
                    <circle
                      cx={cx}
                      cy={cy}
                      r={activeDrag?.id === (b.id || `b_${b.x}_${b.y}`) ? 7 : 4.5}
                      fill="var(--gold, #e5b85c)"
                      stroke="#ffffff"
                      strokeWidth="1.5"
                      opacity="0.9"
                      style={{ filter: 'drop-shadow(0 1px 3px rgba(0,0,0,0.5))' }}
                    />
                    <circle cx={cx} cy={cy} r="14" fill="transparent" />
                  </g>
                </g>
              );
            }

            if (b.type === 'rod') {
              const x1 = toSvgX(b.x1);
              const y1 = toSvgY(b.y1);
              const x2 = toSvgX(b.x2);
              const y2 = toSvgY(b.y2);
              return (
                <g key={b.id || `rod-${b.x1}`}>
                  <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={strokeCol} strokeWidth={b.thickness || 4} strokeLinecap="round" />
                  {b.label && (
                    <foreignObject x={(x1 + x2) / 2 - 20} y={(y1 + y2) / 2 - 20} width="50" height="25" style={{ overflow: 'visible', pointerEvents: 'none' }}>
                      <div style={{ color: strokeCol, fontSize: '0.82rem' }} dangerouslySetInnerHTML={{ __html: renderKaTeX(b.label) }} />
                    </foreignObject>
                  )}
                </g>
              );
            }

            if (b.type === 'wall' || b.type === 'surface') {
              const x1 = toSvgX(b.x1);
              const y1 = toSvgY(b.y1);
              const x2 = toSvgX(b.x2);
              const y2 = toSvgY(b.y2);
              return (
                <g key={b.id || `wall-${b.x1}`}>
                  <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={strokeCol} strokeWidth="2.5" />
                  {/* Surface hatch indicator */}
                  <rect
                    x={Math.min(x1, x2)}
                    y={Math.min(y1, y2)}
                    width={Math.max(Math.abs(x2 - x1), 10)}
                    height={Math.max(Math.abs(y2 - y1), 8)}
                    fill="url(#geom-hatch)"
                    opacity="0.6"
                  />
                </g>
              );
            }

            if (b.type === 'pulley') {
              const cx = toSvgX(b.x);
              const cy = toSvgY(b.y);
              const r = scaleLenX(b.radius || 0.6);
              return (
                <g key={b.id || `pulley-${b.x}`}>
                  <circle cx={cx} cy={cy} r={r} fill="var(--surface)" stroke={strokeCol} strokeWidth="2" />
                  <circle cx={cx} cy={cy} r="3" fill={strokeCol} />
                </g>
              );
            }

            if (b.type === 'point') {
              const cx = toSvgX(b.x);
              const cy = toSvgY(b.y);
              return (
                <g
                  key={b.id || `point-${b.x}`}
                  style={{ cursor: activeDrag?.id === (b.id || `b_${b.x}_${b.y}`) ? 'grabbing' : 'grab' }}
                  onPointerDown={(e) => handleBodyPointerDown(e, b)}
                >
                  <circle cx={cx} cy={cy} r="4.5" fill={strokeCol} stroke="#ffffff" strokeWidth="1" />
                  <circle cx={cx} cy={cy} r="14" fill="transparent" />
                  {b.label && (
                    <foreignObject x={cx + 6} y={cy - 12} width="40" height="24" style={{ overflow: 'visible', pointerEvents: 'none' }}>
                      <div style={{ color: strokeCol, fontSize: '0.82rem' }} dangerouslySetInnerHTML={{ __html: renderKaTeX(b.label) }} />
                    </foreignObject>
                  )}
                </g>
              );
            }

            return null;
          })}

          {/* Render Forces (arrows, dashed projections, labels) */}
          {evaluatedForces.map((f) => {
            const sx = toSvgX(f.ox);
            const sy = toSvgY(f.oy);
            const ex = toSvgX(f.ox + f.dx);
            const ey = toSvgY(f.oy + f.dy);
            const rawCol = f.color || 'cyan';
            const col = resolveColor(rawCol, 'var(--info)');
            const markerName = NAMED_COLORS[rawCol.toLowerCase()] ? `geom-arrow-${rawCol.toLowerCase()}` : 'geom-arrow-default';

            return (
              <g key={`force-${f.id}`}>
                {/* Optional dashed component projections */}
                {showProjections && f.projections !== false && Math.abs(f.dx) > 1e-4 && Math.abs(f.dy) > 1e-4 && (
                  <g opacity="0.45" strokeDasharray="3 3" strokeWidth="1">
                    <line x1={sx} y1={sy} x2={ex} y2={sy} stroke={col} />
                    <line x1={ex} y1={sy} x2={ex} y2={ey} stroke={col} />
                  </g>
                )}

                {/* Main Force Vector Arrow */}
                <line
                  x1={sx}
                  y1={sy}
                  x2={ex}
                  y2={ey}
                  stroke={col}
                  strokeWidth="2.2"
                  markerEnd={`url(#${markerName})`}
                />

                {/* Direct SVG Pointer Drag Handle on Force Vector Arrowhead */}
                <g
                  style={{ cursor: activeDrag?.id === f.id ? 'grabbing' : 'grab' }}
                  onPointerDown={(e) => handleForcePointerDown(e, f)}
                >
                  <circle
                    cx={ex}
                    cy={ey}
                    r={activeDrag?.id === f.id ? 8.5 : 6}
                    fill="var(--accent, #2ecc71)"
                    stroke="#ffffff"
                    strokeWidth="1.8"
                    style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.5))' }}
                  />
                  <circle
                    cx={ex}
                    cy={ey}
                    r="16"
                    fill="transparent"
                  />
                </g>

                {/* Force KaTeX Label */}
                {f.label && (() => {
                  const labelOffset = 16;
                  const rad = (f.deg * Math.PI) / 180;
                  const lx = ex + labelOffset * Math.cos(rad) - 25;
                  const ly = ey - labelOffset * Math.sin(rad) - 14;
                  return (
                    <foreignObject x={lx} y={ly} width="80" height="30" style={{ overflow: 'visible', pointerEvents: 'none' }}>
                      <div
                        style={{
                          color: col,
                          fontSize: '0.9rem',
                          fontWeight: 600,
                          padding: '1px 4px',
                          borderRadius: '3px',
                          background: 'rgba(15, 23, 42, 0.75)',
                          display: 'inline-block',
                          boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
                        }}
                        dangerouslySetInnerHTML={{ __html: renderKaTeX(f.label) }}
                      />
                    </foreignObject>
                  );
                })()}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Interactive Controls Toolbar (Sliders + Reset + Projections Toggle) */}
      {(spec.params?.length > 0 || spec.forces?.length > 0) && (
        <div style={{ marginTop: 'var(--space-3, 12px)', paddingTop: 'var(--space-2, 8px)', borderTop: '1px solid var(--rule)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
            <span style={{ fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)', fontWeight: 600 }}>
              Parameters & Controls
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', color: 'var(--ink-soft)', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={showProjections}
                  onChange={(e) => setShowProjections(e.target.checked)}
                  style={{ cursor: 'pointer', accentColor: 'var(--accent)' }}
                />
                Show Projections ($F_x, F_y$)
              </label>
              <button
                type="button"
                className="btn btn-xs btn-quiet"
                onClick={resetParams}
                title="Reset parameters to defaults"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', padding: '2px 8px' }}
              >
                <RotateCcw size={12} />
                Reset
              </button>
            </div>
          </div>

          {/* Slider Inputs */}
          {spec.params?.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
              {spec.params.map((p) => {
                const curVal = params[p.name] ?? p.value ?? p.min ?? 0;
                return (
                  <div key={p.name} style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', color: 'var(--ink)' }}>
                      <span>{p.label || p.name}</span>
                      <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>
                        {curVal} {p.unit || ''}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={p.min ?? 0}
                      max={p.max ?? 100}
                      step={p.step ?? 1}
                      value={curVal}
                      onChange={(e) => handleSliderChange(p.name, e.target.value)}
                      style={{ width: '100%', accentColor: 'var(--accent)', cursor: 'pointer' }}
                    />
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
