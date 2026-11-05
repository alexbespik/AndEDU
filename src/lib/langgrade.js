// Grading for typed and spoken language answers (translate, word_bank, listen_type, speak).
// Lenient the way language apps are: case, punctuation and extra spaces never matter; a missing accent on a
// Latin letter or a one-letter typo in a long answer still counts, with a note.

const LATIN_MARK = /([a-z])[̀-ͯ]+/g;

/** Lowercase, punctuation to spaces, single spaces. accents=false also drops accents on Latin letters (é → e). */
export function normalizeAnswer(text, { accents = true } = {}) {
  let t = String(text || '').toLowerCase().normalize('NFD');
  if (!accents) t = t.replace(LATIN_MARK, '$1');
  return t.normalize('NFC').replace(/['’`]/g, '').replace(/[^\p{L}\p{N}\p{M}\s]/gu, ' ').replace(/\s+/g, ' ').trim();
}

function levenshtein(a, b) {
  const x = [...a], y = [...b];
  let prev = Array.from({ length: y.length + 1 }, (_, j) => j);
  for (let i = 1; i <= x.length; i++) {
    const cur = [i];
    for (let j = 1; j <= y.length; j++) cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x[i - 1] === y[j - 1] ? 0 : 1));
    prev = cur;
  }
  return prev[y.length];
}

/** 0..1, 1 = identical after normalizing. */
export function similarity(a, b) {
  const x = normalizeAnswer(a, { accents: false }), y = normalizeAnswer(b, { accents: false });
  if (!x && !y) return 1;
  return 1 - levenshtein(x, y) / Math.max([...x].length, [...y].length);
}

/**
 * Checks input against the answer and accepted alternatives.
 * Returns {ok, note?, best}: best is the closest accepted answer, shown when the student was wrong or nearly right.
 */
export function gradeText(input, answers) {
  const list = (Array.isArray(answers) ? answers : [answers]).filter(Boolean);
  const exact = normalizeAnswer(input);
  if (!exact) return { ok: false, best: list[0] };
  for (const a of list) if (normalizeAnswer(a) === exact) return { ok: true, best: a };
  const loose = normalizeAnswer(input, { accents: false });
  for (const a of list) if (normalizeAnswer(a, { accents: false }) === loose) return { ok: true, best: a, note: `Mind the accents: ${a}` };
  let best = list[0], score = -1;
  for (const a of list) { const s = similarity(input, a); if (s > score) { score = s; best = a; } }
  if ([...loose].length >= 6 && score >= 0.88) return { ok: true, best, note: `Almost: watch the spelling (${best}).` };
  return { ok: false, best };
}
