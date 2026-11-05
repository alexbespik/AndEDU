// Offline outline maps (public/maps/<name>.svg) drawn inline so they follow the theme. The file is never injected
// as markup: only its viewBox and the `d` of known path classes are read, checked, and re-rendered by React.
import React, { useEffect, useState } from 'react';
import { MAP_NAMES, MAP_LABEL } from './historyUtil';

const PATH_CLASSES = ['hist-grid', 'hist-land', 'hist-water'];
const SAFE_D = /^[MLHVZmlhvz0-9.,\s-]+$/;
const cache = new Map();

function parseMap(text) {
  const doc = new DOMParser().parseFromString(text, 'image/svg+xml');
  const root = doc.documentElement;
  const vb = (root?.getAttribute('viewBox') || '').trim().split(/\s+/).map(Number);
  if (root?.nodeName !== 'svg' || vb.length !== 4 || vb.some((n) => !Number.isFinite(n)) || vb[2] <= 0 || vb[3] <= 0) {
    throw new Error('Not a map file');
  }
  const paths = [];
  for (const el of root.querySelectorAll('path')) {
    const cls = el.getAttribute('class');
    const d = el.getAttribute('d') || '';
    if (PATH_CLASSES.includes(cls) && d.length < 200000 && SAFE_D.test(d)) paths.push({ cls, d });
  }
  return { w: vb[2], h: vb[3], paths };
}

/** {w, h, paths} for a map name, null while loading, or {error}. Fetched once per page. */
export function useOutlineMap(name) {
  const known = MAP_NAMES.includes(name) ? name : 'world';
  const [map, setMap] = useState(() => cache.get(known) || null);
  useEffect(() => {
    let live = true;
    if (cache.has(known)) { setMap(cache.get(known)); return undefined; }
    setMap(null);
    fetch(`/maps/${known}.svg`)
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.text(); })
      .then((t) => { const m = parseMap(t); cache.set(known, m); if (live) setMap(m); })
      .catch((e) => live && setMap({ error: e.message || 'Could not load the map' }));
    return () => { live = false; };
  }, [known]);
  return map;
}

/** The map with an overlay: children(w, h) draws pins in viewBox units. Extra props go to the <svg>. */
export const OutlineMap = React.forwardRef(function OutlineMap({ name, label, children, className = '', ...rest }, ref) {
  const map = useOutlineMap(name);
  if (!map) return <div className="hist-map-loading hint">Loading the map…</div>;
  if (map.error) return <p className="notice notice-info">The {MAP_LABEL[name] || name} map could not be loaded ({map.error}).</p>;
  return (
    <svg ref={ref} className={`hist-map ${className}`} viewBox={`0 0 ${map.w} ${map.h}`} role="img"
      aria-label={label || `Outline map: ${MAP_LABEL[name] || name}`} {...rest}>
      <rect className="hist-sea" x="0" y="0" width={map.w} height={map.h} />
      {map.paths.map((p, i) => <path key={i} className={p.cls} d={p.d} />)}
      {children?.(map.w, map.h)}
    </svg>
  );
});
