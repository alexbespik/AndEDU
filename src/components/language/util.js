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
