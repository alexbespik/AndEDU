// Client-side Venn logic for categorical syllogisms. The engine decides validity; this only draws the premises.
// Regions are named by the circles they lie in: "S", "P", "M", "SP", "SM", "PM", "SPM" (outside every circle is not drawn).
export const REGIONS = ['S', 'P', 'M', 'SP', 'SM', 'PM', 'SPM'];
export const CIRCLES = { S: { cx: 120, cy: 115, r: 80 }, P: { cx: 200, cy: 115, r: 80 }, M: { cx: 160, cy: 185, r: 80 } };
// where a mark sits inside each region
export const CENTERS = { S: [85, 85], P: [235, 85], M: [160, 245], SP: [160, 75], SM: [115, 170], PM: [205, 170], SPM: [160, 135] };

// term positions (subject, predicate) of the major premise and minor premise in each figure
export const FIGURES = { 1: [['M', 'P'], ['S', 'M']], 2: [['P', 'M'], ['S', 'M']], 3: [['M', 'P'], ['M', 'S']], 4: [['P', 'M'], ['M', 'S']] };

export const STATEMENT = { A: ['All', 'are'], E: ['No', 'are'], I: ['Some', 'are'], O: ['Some', 'are not'] };

// (mood-figure) -> traditional name, for the picker (the engine returns the name too)
export const NAMED = [
  ['AAA-1', 'Barbara'], ['EAE-1', 'Celarent'], ['AII-1', 'Darii'], ['EIO-1', 'Ferio'],
  ['EAE-2', 'Cesare'], ['AEE-2', 'Camestres'], ['EIO-2', 'Festino'], ['AOO-2', 'Baroco'],
  ['AII-3', 'Datisi'], ['IAI-3', 'Disamis'], ['OAO-3', 'Bocardo'], ['EIO-3', 'Ferison'],
  ['AEE-4', 'Calemes'], ['IAI-4', 'Dimatis'], ['EIO-4', 'Fresison'],
  ['AAI-1', 'Barbari (needs S to exist)'], ['EAO-1', 'Celaront (needs S to exist)'], ['EAO-2', 'Cesaro (needs S to exist)'],
  ['AEO-2', 'Camestros (needs S to exist)'], ['AAI-3', 'Darapti (needs M to exist)'], ['EAO-3', 'Felapton (needs M to exist)'],
  ['AAI-4', 'Bamalip (needs P to exist)'], ['AEO-4', 'Calemos (needs S to exist)'], ['EAO-4', 'Fesapo (needs M to exist)'],
];

const inCircle = (region, t) => region.includes(t);
const regionsWhere = (pred) => REGIONS.filter(pred);

/** The regions a statement "kind X Y" refers to: X and Y (I, E) or X without Y (A, O). */
function regionsOf(kind, x, y) {
  return regionsWhere((r) => inCircle(r, x) && (kind === 'A' || kind === 'O' ? !inCircle(r, y) : inCircle(r, y)));
}

/**
 * statements: [{kind, x, y}] (premises). Universals shade first, then particulars place an X in the one open region,
 * or on the line between the two regions when both are open. existential: term letters that must be non-empty.
 * Returns {shaded: Set, marks: [{regions: [..], kind: 'x'|'line'|'exist'}], clash: bool}.
 */
export function drawPremises(statements, existential = []) {
  const shaded = new Set();
  statements.filter((s) => s.kind === 'A' || s.kind === 'E').forEach((s) => {
    regionsOf(s.kind === 'A' ? 'A' : 'E', s.x, s.y).forEach((r) => shaded.add(r));
  });
  const marks = [];
  let clash = false;
  statements.filter((s) => s.kind === 'I' || s.kind === 'O').forEach((s) => {
    const open = regionsOf(s.kind, s.x, s.y).filter((r) => !shaded.has(r));
    if (!open.length) clash = true;
    else marks.push({ regions: open, kind: open.length === 1 ? 'x' : 'line' });
  });
  existential.forEach((t) => {
    const open = regionsWhere((r) => inCircle(r, t) && !shaded.has(r));
    if (open.length) marks.push({ regions: open.length === 1 ? open : [open[0]], kind: 'exist', term: t });
  });
  return { shaded, marks, clash };
}

/** Is the conclusion (kind S P) already drawn: universals by shading, particulars by a mark lying wholly inside its regions. */
export function depicts(drawing, concl) {
  const target = regionsOf(concl.kind, concl.x, concl.y);
  if (concl.kind === 'A' || concl.kind === 'E') return target.every((r) => drawing.shaded.has(r));
  return drawing.marks.some((m) => m.regions.every((r) => target.includes(r)));
}
