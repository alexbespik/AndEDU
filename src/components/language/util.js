// Pure helpers for the extra language activities (stories, dialogues, grammar tips).

export const SCRIPT_LANG = { hiragana: 'ja', katakana: 'ja', cyrillic: 'ru', hangul: 'ko', greek: 'el', arabic: 'ar', devanagari: 'hi' };

// Each speaker of a story gets their own reading style (speak() options), in order of first appearance.
const VOICE_STYLES = [{ rate: 0.9, pitch: 1 }, { rate: 0.8, pitch: 0.8 }, { rate: 1, pitch: 1.25 }, { rate: 0.85, pitch: 1.1 }, { rate: 0.95, pitch: 0.9 }];

/** {speaker: {rate, pitch}} for the speakers of a story's lines. */
export function speakerStyles(lines) {
  const out = {};
  for (const l of lines || []) if (!(l.speaker in out)) out[l.speaker] = VOICE_STYLES[Object.keys(out).length % VOICE_STYLES.length];
  return out;
}

/**
 * Corrections from a /api/language/roleplay reply as [{said, better, why}]. Newer servers send `corrections`
 * objects; older ones send `feedback.corrections` as plain strings, which become the `why`.
 */
export function correctionsOf(res) {
  if (Array.isArray(res?.corrections) && res.corrections.length) {
    return res.corrections.filter((c) => c && (c.better || c.said || c.why))
      .map((c) => (typeof c === 'string' ? { said: '', better: '', why: c } : { said: String(c.said || ''), better: String(c.better || ''), why: String(c.why || '') }));
  }
  const old = res?.feedback?.corrections;
  return Array.isArray(old) ? old.filter(Boolean).map((c) => (typeof c === 'string' ? { said: '', better: '', why: c } : { said: String(c.said || ''), better: String(c.better || ''), why: String(c.why || '') })) : [];
}

/** Lesson markdown sections whose heading mentions grammar or tips: [{heading, body}] (fenced code is not a heading). */
export function grammarSections(markdown) {
  const out = [];
  let cur = null, fence = false;
  for (const line of String(markdown || '').split('\n')) {
    if (/^\s*(```|~~~)/.test(line)) fence = !fence;
    const m = !fence && /^(#{1,6})\s+(.+?)\s*#*\s*$/.exec(line);
    if (m) {
      if (cur && m[1].length <= cur.level) { out.push(cur); cur = null; }
      if (!cur && /grammar|tip/i.test(m[2])) { cur = { level: m[1].length, heading: m[2], lines: [] }; continue; }
    }
    if (cur) cur.lines.push(line);
  }
  if (cur) out.push(cur);
  return out.map(({ heading, lines }) => ({ heading, body: lines.join('\n').trim() })).filter((s) => s.body);
}

/** Every practice item of a type across the topics, with its topic: [{topic, item}]. */
export function itemsOfType(topics, type) {
  return (topics || []).flatMap((t) => (t.practice || []).filter((p) => p.type === type).map((p) => ({ topic: t, item: { ...p, topicId: t.id } })));
}

// German noun genders (Gender.jsx colours them): der m, die f, das n, plural die.
const ARTICLE_GENDER = { der: 'm', das: 'n', die: 'f' };
export const GENDER_LABEL = { m: 'masculine', f: 'feminine', n: 'neuter', pl: 'plural' };
export const GERMAN_NOUN = /^(der|die|das)\s+(\p{Lu}.*)$/u;   // "der Apfel"; "Das ist ..." is a sentence, not a noun
const langBase = (lang) => String(lang || '').toLowerCase().split(/[-_]/)[0];

/** 'm' | 'f' | 'n' | 'pl' | null for a German card front ("die Eltern" + "(plural)" on the back is plural). */
export function genderOf(front, lang, { gender, back } = {}) {
  if (GENDER_LABEL[gender]) return gender;
  if (langBase(lang) !== 'de') return null;
  const m = GERMAN_NOUN.exec(String(front || '').trim());
  if (!m) return null;
  if (m[1] === 'die' && /\(plural\)/i.test(String(back || ''))) return 'pl';
  return ARTICLE_GENDER[m[1]];
}

// ---- Word strength with memory decay -------------------------------------------------------------------------
// A word's progress is {n, firstReviewed, lastReviewed} (ms timestamps): n counts net right answers (0-4).
const DAY = 86400000;

/** Bars (0-4) to show: 0 = never reviewed or never answered right (n 0); otherwise min(n, 4) minus one per full 7 days
 * since lastReviewed (never below 1); the 4th bar needs n >= 4 and a first review at least 14 days before the last
 * one, otherwise 3 at most. */
export function strengthBars(entry, now = Date.now()) {
  const e = normalizeEntry(entry, now);
  if (!e.firstReviewed || e.n < 1) return 0;
  const decay = Math.floor(Math.max(0, now - e.lastReviewed) / (7 * DAY));
  let bars = Math.min(e.n, 4) - decay;
  const mastered = e.n >= 4 && e.lastReviewed - e.firstReviewed >= 14 * DAY;
  if (bars >= 4 && !mastered) bars = 3;
  return Math.max(1, Math.min(4, bars));
}

/** A stored value as an entry: old files stored a bare number (n); a positive one counts as reviewed at `now`. */
export function normalizeEntry(raw, now = Date.now()) {
  if (raw && typeof raw === 'object') {
    return { n: Math.max(0, Math.min(4, Number(raw.n) || 0)), firstReviewed: raw.firstReviewed || null, lastReviewed: raw.lastReviewed || raw.firstReviewed || null };
  }
  const n = Math.max(0, Math.min(4, Number(raw) || 0));
  return n > 0 ? { n, firstReviewed: now, lastReviewed: now } : { n: 0, firstReviewed: null, lastReviewed: null };
}

/** The strength map with every old numeric value migrated: {map, changed}. */
export function migrateStrength(map, now = Date.now()) {
  const out = {};
  let changed = false;
  for (const [k, v] of Object.entries(map || {})) {
    if (v && typeof v === 'object') { out[k] = v; continue; }
    changed = true;
    const e = normalizeEntry(v, now);
    if (e.firstReviewed) out[k] = e;  // a stored 0 meant "never reviewed"
  }
  return { map: out, changed };
}

/** The entry after one review: a right answer adds 1 to n, a wrong one removes 1; the times move forward. */
export function reviewEntry(entry, delta, now = Date.now()) {
  const e = normalizeEntry(entry, now);
  return { n: Math.max(0, Math.min(4, e.n + delta)), firstReviewed: e.firstReviewed || now, lastReviewed: now };
}

/** The stem most forms of a verb share, and which forms break it (irregular): {stem, irregular: [bool per form]}.
 * Forms are grouped by their first two letters; the biggest group (3 or more forms) gives the stem. */
export function conjugationStem(forms) {
  const words = (forms || []).map((f) => String(f[1] || '').toLowerCase());
  const none = { stem: '', irregular: words.map(() => false) };
  const groups = {};
  words.forEach((w, i) => { if (w.length >= 2) (groups[w.slice(0, 2)] ||= []).push(i); });
  const best = Object.values(groups).sort((a, b) => b.length - a.length)[0];
  if (!best || best.length < 3) return none;
  let stem = words[best[0]];
  for (const i of best) while (stem && !words[i].startsWith(stem)) stem = stem.slice(0, -1);
  if (stem.length < 2) return none;
  return { stem, irregular: words.map((_, i) => !best.includes(i)) };
}

/** A lesson's minimal-pair drill (add_minimal_pairs): a listen_choose asking "which word" among single words. */
export function isMinimalPair(p) {
  return p?.type === 'listen_choose' && /which word/i.test(p.prompt || '') && (p.options || []).length >= 2 && (p.options || []).every((o) => !/\s/.test(String(o).trim()));
}

/** A lesson's dictation item (add_dictation): a listen_type whose audio is a sentence of 3 or more words. */
export function isDictation(p) {
  return p?.type === 'listen_type' && String(p.audio_text || '').trim().split(/\s+/).length >= 3;
}
