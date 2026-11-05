// History > Timeline: a zoomable chart with century (or wider) bands and named eras (timeline events that carry an
// `era`, e.g. from the add_timeline_era tool), above the shared TimelineView list and ordering challenge.
import React, { useMemo, useState } from 'react';
import { ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';
import { TimelineView } from '../Activities';
import { fmtYear, eraSpans } from './historyUtil';
import '../../styles/history.css';

const BAND_SIZES = [10, 25, 50, 100, 250, 500, 1000];
const BASE_W = 760;

const ordinal = (n) => `${n}${n % 100 >= 11 && n % 100 <= 13 ? 'th' : { 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th'}`;
function bandLabel(start, size) {
  if (size === 100) {
    const c = start >= 0 ? Math.floor(start / 100) + 1 : Math.floor(-start / 100);
    return start >= 0 ? `${ordinal(c)} c.` : `${ordinal(c)} c. BCE`;
  }
  return fmtYear(start);
}

function EraChart({ events }) {
  const [zoom, setZoom] = useState(1);
  const eras = useMemo(() => eraSpans(events), [events]);
  const years = events.map((e) => e.year);
  const lo0 = Math.min(...years), hi0 = Math.max(...years);
  const pad = Math.max(5, (hi0 - lo0) * 0.04);
  const lo = lo0 - pad, hi = hi0 + pad;
  const width = BASE_W * zoom;
  const X = (y) => ((y - lo) / (hi - lo)) * width;
  const size = BAND_SIZES.find((s) => (s / (hi - lo)) * width >= 44) || 1000;
  const bands = [];
  for (let b = Math.floor(lo / size) * size; b < hi; b += size) bands.push(b);
  const eraRows = eras.length ? 26 * Math.min(3, eras.length) : 0;
  const axisY = 30 + eraRows + 18;
  const height = axisY + 70;
  return (
    <div className="stack-sm hist-tl">
      <div className="hist-zoom">
        <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label="Zoom out" disabled={zoom <= 1} onClick={() => setZoom((z) => Math.max(1, z / 2))}><ZoomOut size={14} /></button>
        <input type="range" min={0} max={5} step={1} value={Math.log2(zoom)} onChange={(e) => setZoom(2 ** Number(e.target.value))} aria-label="Zoom" />
        <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label="Zoom in" disabled={zoom >= 32} onClick={() => setZoom((z) => Math.min(32, z * 2))}><ZoomIn size={14} /></button>
        <button type="button" className="btn btn-quiet btn-sm" onClick={() => setZoom(1)} disabled={zoom === 1}><Maximize2 size={14} aria-hidden="true" /> Fit</button>
        <span className="hint">{fmtYear(lo0)} to {fmtYear(hi0)} · bands of {size === 100 ? 'centuries' : `${size} years`}{zoom > 1 ? ' · scroll sideways' : ''}</span>
      </div>
      <div className="hist-tl-scroll" tabIndex={0} aria-label="Timeline chart; scroll sideways when zoomed">
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Timeline from ${fmtYear(lo0)} to ${fmtYear(hi0)}`}>
          {bands.map((b, k) => {
            const x0 = Math.max(0, X(b)), x1 = Math.min(width, X(b + size));
            return (
              <g key={b}>
                <rect className={k % 2 ? 'hist-band-b' : 'hist-band-a'} x={x0} y={0} width={Math.max(0, x1 - x0)} height={height} />
                {x1 - x0 > 40 && <text className="hist-band-label" x={x0 + 4} y={14}>{bandLabel(b, size)}</text>}
              </g>
            );
          })}
          {eras.map((e, k) => {
            const x0 = X(e.start), w = Math.max(6, X(e.end) - x0), y = 24 + (k % 3) * 26;
            return (
              <g key={e.label} className="hist-era">
                <title>{`${e.label}: ${fmtYear(e.start)} to ${fmtYear(e.end)}`}</title>
                <rect x={x0} y={y} width={w} height={20} rx={3} />
                <text x={x0 + 5} y={y + 14}>{w > 60 || zoom > 2 ? e.label : ''}</text>
              </g>
            );
          })}
          <line className="hist-axis" x1={0} x2={width} y1={axisY} y2={axisY} />
          {events.map((e, k) => {
            const x = X(e.year), row = k % 3;
            const showLabel = (width / events.length) * 3 > 90;
            return (
              <g key={`${e.title}-${k}`} className="hist-ev">
                <title>{`${e.date || fmtYear(e.year)}: ${e.title}`}</title>
                <line x1={x} x2={x} y1={axisY} y2={axisY + 14 + row * 16} />
                <circle cx={x} cy={axisY} r={5} />
                {showLabel && <text x={x + 3} y={axisY + 24 + row * 16}>{e.title.length > 28 ? `${e.title.slice(0, 27)}…` : e.title}</text>}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

/** The History workspace timeline: era bands and zoom on top, the shared list / ordering challenge below. */
export default function HistoryTimeline({ events = [], topicId, initialMode = 'view' }) {
  return (
    <div className="stack">
      {events.length >= 2 && <EraChart events={events} />}
      <TimelineView events={events} topicId={topicId} initialMode={initialMode} />
    </div>
  );
}
