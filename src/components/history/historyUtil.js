// Plain helpers shared by the history practice bodies and the History workspace tabs.

export const MAP_NAMES = ['world', 'europe', 'mediterranean', 'americas', 'asia'];
export const MAP_LABEL = { world: 'World', europe: 'Europe', mediterranean: 'Mediterranean', americas: 'Americas', asia: 'Asia' };

export const fmtYear = (y) => (y < 0 ? `${Math.abs(Math.round(y))} BCE` : String(Math.round(y)));

/** Client point -> {x, y} as 0-1 fractions of the map (null outside it). */
export function pointToFraction(svg, clientX, clientY, w, h) {
  const ctm = svg?.getScreenCTM?.();
  if (!ctm) return null;
  const pt = new DOMPoint(clientX, clientY).matrixTransform(ctm.inverse());
  const x = pt.x / w, y = pt.y / h;
  return x >= 0 && x <= 1 && y >= 0 && y <= 1 ? { x, y } : null;
}

/** Every practice item of these types across the topics, tagged with its topic. */
export function collect(topics, ...types) {
  return topics.flatMap((t) => (t.practice || []).filter((p) => types.includes(p.type))
    .map((p) => ({ ...p, topicId: t.id, topicTitle: t.title })));
}

/** The century of a source's date text ("44 BCE", "c. 1215", "1789-08-26"): negative for BCE, or null. */
export function centuryOf(date) {
  const m = /(\d{1,4})(?:\s*(BCE|BC|B\.C\.))?/i.exec(String(date || ''));
  if (!m) return null;
  const c = Math.max(1, Math.floor((Number(m[1]) - 1) / 100) + 1);
  return m[2] ? -c : c;
}

/** Era bands from timeline events tagged with `era`: each spans its first to its last tagged event. */
export function eraSpans(events) {
  const by = new Map();
  for (const e of events) {
    if (!e.era) continue;
    const s = by.get(e.era) || { label: e.era, start: e.year, end: e.year };
    s.start = Math.min(s.start, e.year); s.end = Math.max(s.end, e.year);
    by.set(e.era, s);
  }
  return [...by.values()].sort((a, b) => a.start - b.start);
}

/** Points for a who_am_i solved after `shown` clues (fewer clues, more points); shown in the UI, never XP. */
export const whoPoints = (item, shown) => Math.max(1, item.clues.length - shown + 1) * 10;
