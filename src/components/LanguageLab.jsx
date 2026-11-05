import React, { useEffect, useMemo, useState } from 'react';
import { BookOpen, GraduationCap, Layers, Volume2, Route, Target, BookA, Heart, Crown, Headphones, Mic, RotateCcw, Sparkles, Trophy, MessageCircleQuestion, Loader2, X, Check, MessageSquare } from 'lucide-react';
import { CoursesTab } from './MathLab';
import { FlashcardDeck, MatchPairs } from './Activities';
import Md, { MdInline } from './Md';
import WorkspaceShell from './WorkspaceShell';
import PronounceTab from './PronounceTab';
import LanguageRoleplay from './LanguageRoleplay';
import { ExplainAnswerButton } from './ExplainDialog';
import { LANGUAGE_RENDER, LANGUAGE_LABEL, LANGUAGE_TYPES, ListenButtons } from '../practice/language';
import { LANGUAGE_EXTRA_RENDER, LANGUAGE_EXTRA_LABEL } from '../practice/language_extra';
import { EXTRA_LANGUAGE_TABS } from './language';
import { languageName } from '../lib/speech';
import { reportXp, reportActivity } from '../lib/engage';
import { api } from '../lib/api';

// Progress kept in this browser: word strength 0-4, crowns per unit (0-5), recently missed item ids.
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
};
const K_STRENGTH = 'andedu_lang_strength', K_CROWNS = 'andedu_lang_crowns', K_MISSED = 'andedu_lang_missed';
const HEARTS = 5;
let handledRequest = null;  // `at` of the last MCP/assistant tab request this workspace acted on
const SESSION_TYPES = new Set([...LANGUAGE_TYPES, 'conjugate', 'script_match', 'fill_blank', 'match_pairs', 'true_false']);  // story and dialogue are too long for a session
const shuffle = (a) => { const o = [...a]; for (let i = o.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [o[i], o[j]] = [o[j], o[i]]; } return o; };

/** The meaning on a card's back without IPA (/.../, [...]) or trailing separators. */
const meaningOf = (back) => String(back || '').replace(/\/[^/\n]{1,60}\//g, '').replace(/\[[^\]\n]{1,60}\]/g, '').replace(/[\s·—–-]+$/, '').replace(/^[\s·—–-]+/, '').trim() || String(back || '');

/** Every flashcard of the language lessons as a word: {key, topicId, front, meaning, lang}. */
export function wordsOf(topics) {
  return topics.flatMap((t) => (t.flashcards || []).map((c, i) => ({ key: `${t.id}:fc${i}`, topicId: t.id, unit: t.title, front: c.front, back: c.back, meaning: meaningOf(c.back), lang: c.lang })));
}

/** Up to k random items that pass f, without copying or shuffling the whole list (this runs once per word). */
function sample(list, k, f) {
  const out = new Set();
  for (let tries = 0; out.size < k && tries < k * 12 && list.length; tries++) {
    const x = list[Math.floor(Math.random() * list.length)];
    if (f(x)) out.add(x);
  }
  if (out.size < k) for (const x of list) { if (out.size >= k) break; if (f(x)) out.add(x); }  // small or sparse pools
  return [...out];
}

/** Every exercise a word can make, easiest first: meaning → hear and pick → hear and type → say it. */
function variantsFor(word, pool) {
  const others = (f) => sample(pool, 3, (w) => w.key !== word.key && w.lang === word.lang && f(w));
  const base = { topicId: word.topicId, cardKey: word.key, lang: word.lang };
  const out = [];
  const meanings = [...new Set([word.meaning, ...others((w) => w.meaning !== word.meaning).map((w) => w.meaning)])];
  if (meanings.length >= 3) out.push({ ...base, id: `${word.key}:meaning`, type: 'meaning', prompt: 'What does this mean?', front: word.front, options: shuffle(meanings), answer: word.meaning });
  if (!word.lang) return out;
  const fronts = [...new Set([word.front, ...others((w) => w.front !== word.front).map((w) => w.front)])];
  if (fronts.length >= 3) out.push({ ...base, id: `${word.key}:listen_choose`, type: 'listen_choose', prompt: 'What did you hear?', audio_text: word.front, options: shuffle(fronts), answer: word.front });
  if (word.front.length <= 40) out.push({ ...base, id: `${word.key}:listen_type`, type: 'listen_type', prompt: 'Type what you hear', audio_text: word.front, answer: word.front, accepted: [] });
  out.push({ ...base, id: `${word.key}:speak`, type: 'speak', prompt: 'Say it', target: word.front, translation: word.meaning });
  return out;
}

/** The exercise that fits a word's strength (plus the one below it once the word is familiar). */
function byStrength(variants, strength) {
  const level = Math.min(strength, variants.length - 1);
  return [variants[level], ...(strength >= 2 && variants[level - 1] ? [variants[level - 1]] : [])].filter(Boolean);
}

const MODE_TYPES = { listen: new Set(['listen_type', 'listen_choose']), speak: new Set(['speak']) };

/**
 * A session's items. mode: mixed | unit | missed | listen | speak | new.
 * Lesson practice items keep their own type; ids are "<topicId>:<itemId>" (XP refs, missed list).
 */
export function buildSession(topics, { mode = 'mixed', unitId = null, count = 12 } = {}) {
  const strength = store.get(K_STRENGTH, {});
  const missed = new Set(store.get(K_MISSED, []));
  const scope = unitId ? topics.filter((t) => t.id === unitId) : topics;
  const pool = wordsOf(topics);
  const lessonItems = scope.flatMap((t) => (t.practice || []).filter((p) => SESSION_TYPES.has(p.type)).map((p) => ({ ...p, id: `${t.id}:${p.id}`, topicId: t.id })));
  const words = wordsOf(scope).map((w) => [w, (strength[w.key] || 0) + Math.random()]).sort((a, b) => a[1] - b[1]).map(([w]) => w);
  let items;
  if (MODE_TYPES[mode]) {
    items = [...lessonItems, ...words.flatMap((w) => variantsFor(w, pool))].filter((p) => MODE_TYPES[mode].has(p.type));
  } else if (mode === 'missed') {
    items = [...lessonItems, ...words.flatMap((w) => variantsFor(w, pool))].filter((p) => missed.has(p.id));
  } else if (mode === 'new') {
    items = words.filter((w) => !strength[w.key]).flatMap((w) => byStrength(variantsFor(w, pool), 0));
  } else {
    items = [...lessonItems, ...words.flatMap((w) => byStrength(variantsFor(w, pool), strength[w.key] || 0))];
  }
  // weakest first, then a shuffle inside each half so sessions differ
  const isWeak = (p) => missed.has(p.id) || (p.cardKey && !strength[p.cardKey]);
  const weak = shuffle(items.filter(isWeak));
  const rest = shuffle(items.filter((p) => !isWeak(p)));
  return [...weak, ...rest].slice(0, count);
}

/** How many items each practice mode has, in one pass (the hub shows these; building every session would be slow). */
function countModes(topics) {
  const strength = store.get(K_STRENGTH, {});
  const missed = new Set(store.get(K_MISSED, []));
  const pool = wordsOf(topics);
  const lessonItems = topics.flatMap((t) => (t.practice || []).filter((p) => SESSION_TYPES.has(p.type)).map((p) => ({ type: p.type, id: `${t.id}:${p.id}` })));
  const perWord = pool.map((w) => [w, variantsFor(w, pool)]);
  const all = [...lessonItems, ...perWord.flatMap(([, v]) => v)];
  const typed = (types) => all.filter((p) => types.has(p.type)).length;
  return {
    mixed: lessonItems.length + perWord.reduce((n, [w, v]) => n + byStrength(v, strength[w.key] || 0).length, 0),
    missed: all.filter((p) => missed.has(p.id)).length,
    listen: typed(MODE_TYPES.listen),
    speak: typed(MODE_TYPES.speak),
    new: perWord.reduce((n, [w, v]) => n + (strength[w.key] ? 0 : byStrength(v, 0).length), 0),
  };
}

function ChoiceBody({ item, onResult }) {
  const [pick, setPick] = useState(null);
  const options = item.options || [];
  return (
    <div className="stack-sm">
      {item.front && <div className="lang-source"><span className="lang-target" lang={item.lang || undefined}>{item.front}</span>{item.lang && <ListenButtons text={item.front} lang={item.lang} />}</div>}
      <div className="choices">
        {options.map((opt, i) => (
          <button key={opt} type="button" className="choice" disabled={pick !== null}
            data-result={pick !== null ? (opt === item.answer ? 'correct' : opt === pick ? 'wrong' : undefined) : undefined}
            onClick={() => { setPick(opt); onResult(opt === item.answer, opt); }}>
            <span className="key">{'ABCDEF'[i]}</span><span><MdInline>{opt}</MdInline></span><span />
          </button>
        ))}
      </div>
      {pick !== null && pick !== item.answer && <div className="feedback bad"><p>Correct answer: <strong><MdInline>{item.answer}</MdInline></strong></p>{item.explanation && <Md>{item.explanation}</Md>}</div>}
    </div>
  );
}

function TrueFalseBody({ item, onResult }) {
  const [pick, setPick] = useState(null);
  return (
    <div className="stack-sm">
      <div className="btn-row">
        {[true, false].map((v) => (
          <button key={String(v)} type="button" className="choice" disabled={pick !== null} style={{ flex: 1 }}
            data-result={pick !== null ? (v === item.answer ? 'correct' : v === pick ? 'wrong' : undefined) : undefined}
            onClick={() => { setPick(v); onResult(v === item.answer, v ? 'true' : 'false'); }}><span /><span>{v ? 'True' : 'False'}</span><span /></button>
        ))}
      </div>
      {pick !== null && item.explanation && <div className={`feedback ${pick === item.answer ? 'ok' : 'bad'}`}><Md>{item.explanation}</Md></div>}
    </div>
  );
}

const SESSION_RENDER = {
  ...LANGUAGE_RENDER,
  conjugate: LANGUAGE_EXTRA_RENDER.conjugate,
  script_match: LANGUAGE_EXTRA_RENDER.script_match,
  meaning: ChoiceBody,
  fill_blank: ChoiceBody,
  true_false: TrueFalseBody,
  match_pairs: ({ item, onResult }) => <MatchPairs item={item} onSolved={() => onResult(true, '')} />,
};
const SESSION_LABEL = { ...LANGUAGE_LABEL, conjugate: LANGUAGE_EXTRA_LABEL.conjugate, script_match: LANGUAGE_EXTRA_LABEL.script_match, meaning: 'Pick the meaning', fill_blank: 'Fill in the blank', match_pairs: 'Match the pairs', true_false: 'True or false' };

function describeAnswer(item) {
  return item.answer ?? item.target ?? (item.pairs ? item.pairs.map((p) => p.join(' = ')).join('; ')
    : item.forms ? item.forms.map((f) => f.join(' ')).join(', ') : '');
}

/** "Explain my answer": one tutor reply about this mistake, only when the student asks (uses the model quota). */
function ExplainAnswer({ item, given }) {
  const what = item.source || item.front || item.audio_text || item.target || item.prompt;
  const answer = describeAnswer(item);
  return (
    <ExplainAnswerButton
      item={item}
      studentAnswer={given}
      correctAnswer={answer}
      question={what}
      context={item.source || item.translation || ''}
      lang={item.lang}
    />
  );
}

function bump(key, delta) {
  if (!key) return;
  const s = store.get(K_STRENGTH, {});
  s[key] = Math.max(0, Math.min(4, (s[key] || 0) + delta));
  store.set(K_STRENGTH, s);
}
function markMissed(id, missed) {
  const list = store.get(K_MISSED, []).filter((x) => x !== id);
  store.set(K_MISSED, missed ? [id, ...list].slice(0, 80) : list);
}

/** One practice session: a progress bar, hearts that refill for free, a mistake comes back at the end once. */
function Session({ items, unitId, title, onExit }) {
  const [queue, setQueue] = useState(items);
  const [pos, setPos] = useState(0);
  const [hearts, setHearts] = useState(HEARTS);
  const [refills, setRefills] = useState(0);
  const [stats, setStats] = useState({ right: 0, wrong: 0, xp: 0 });
  const [last, setLast] = useState(null);   // {ok, given}
  const item = queue[pos];
  const finished = !item;

  const onResult = (ok, given) => {
    if (last) return;
    setLast({ ok, given });
    if (ok === null) return;  // skipped: no heart lost, no XP
    if (ok) {
      setStats((s) => ({ ...s, right: s.right + 1 }));
      bump(item.cardKey, 1);
      markMissed(item.id, false);
      reportXp('practice_correct', `lang:${item.id}`).then((r) => r?.xp && setStats((s) => ({ ...s, xp: s.xp + r.xp })));
    } else {
      setStats((s) => ({ ...s, wrong: s.wrong + 1 }));
      bump(item.cardKey, -1);
      markMissed(item.id, true);
      if (!item._again) setQueue((q) => [...q, { ...item, _again: true }]);
      if (hearts > 1) setHearts(hearts - 1);
      else { setHearts(HEARTS); setRefills((n) => n + 1); }
    }
  };
  const next = () => { setLast(null); setPos((p) => p + 1); };

  useEffect(() => {
    if (!finished) return;
    const total = stats.right + stats.wrong;
    if (!total) return;
    if (unitId) reportActivity(unitId, 'practice', stats.right, total);  // mixed sessions span units: XP only
    if (unitId && stats.right / total >= 0.6) {
      const crowns = store.get(K_CROWNS, {});
      crowns[unitId] = Math.min(5, (crowns[unitId] || 0) + 1);
      store.set(K_CROWNS, crowns);
    }
  }, [finished]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!items.length) {
    return (
      <div className="panel stack-sm">
        <p>Nothing to practice here yet. Language classes come with words and exercises; the Assistant can add more (for example "add 10 food words to class 2").</p>
        <div className="btn-row"><button type="button" className="btn btn-quiet" onClick={onExit}>Back</button></div>
      </div>
    );
  }
  if (finished) {
    const total = stats.right + stats.wrong;
    return (
      <div className="panel stack-sm review-done">
        <Trophy size={32} className="trophy" aria-hidden="true" />
        <h2>Session complete</h2>
        <p className="num">{total ? Math.round((stats.right / total) * 100) : 100}% accuracy · {stats.right} right · {stats.wrong} to review{stats.xp ? ` · +${stats.xp} XP` : ''}</p>
        {unitId && total > 0 && stats.right / total >= 0.6 && <p><Crown size={15} aria-hidden="true" /> This unit earned a crown.</p>}
        <div className="btn-row">
          <button type="button" className="btn btn-primary" onClick={onExit}>Done</button>
        </div>
      </div>
    );
  }
  const Body = SESSION_RENDER[item.type];
  return (
    <div className="lang-session stack-sm">
      <div className="lang-session-top">
        <button type="button" className="btn btn-quiet btn-sm btn-icon" onClick={onExit} aria-label="End session"><X size={16} /></button>
        <div className="lang-progress" role="progressbar" aria-valuemin={0} aria-valuemax={queue.length} aria-valuenow={pos} aria-label="Session progress">
          <span style={{ width: `${(pos / queue.length) * 100}%` }} />
        </div>
        <span className="lang-hearts" aria-label={`${hearts} hearts`}><Heart size={16} aria-hidden="true" /> <span className="num">{hearts}</span></span>
      </div>
      {title && <p className="hint">{title}</p>}
      {refills > 0 && <p className="hint">Out of hearts, so they refilled. Here hearts are free and practice never stops.</p>}
      <section className="panel stack-sm">
        <p className="hint">{SESSION_LABEL[item.type] || item.type}{item._again ? ' · again' : ''}{item.lang ? ` · ${languageName(item.lang)}` : ''}</p>
        <div className="question"><Md>{item.prompt}</Md></div>
        {Body ? <Body key={`${item.id}-${pos}`} item={item} onResult={onResult} retry={false} /> : <p className="hint">This exercise type can't be shown here.</p>}
      </section>
      {(last || !Body) && (
        <div className={`lang-footer ${last?.ok ? 'ok' : last?.ok === false ? 'bad' : ''}`}>
          <strong>{last?.ok ? <><Check size={16} aria-hidden="true" /> Nice!</> : last?.ok === false ? 'Keep going: it comes back at the end.' : 'Skipped.'}</strong>
          <div className="btn-row">
            {last?.ok === false && <ExplainAnswer item={item} given={last.given} />}
            <button type="button" className="btn btn-primary" onClick={next} autoFocus>Continue</button>
          </div>
        </div>
      )}
    </div>
  );
}

/** Learn path: one unit per language class, in course order, with crowns and a start button. */
function PathTab({ topics, onStart, onOpenTopic }) {
  const crowns = store.get(K_CROWNS, {});
  const units = [...topics].sort((a, b) => String(a.source?.courseId || '').localeCompare(String(b.source?.courseId || '')) || (a.source?.classSeq || 0) - (b.source?.classSeq || 0));
  if (!units.length) {
    return <div className="panel" style={{ marginTop: 'var(--space-4)' }}><p>No language courses yet. Start one from My courses (for example "Spanish for travel, beginner"); each class becomes a unit on this path with words, listening, speaking and translation exercises.</p></div>;
  }
  let course = null;
  return (
    <ol className="lang-path" style={{ marginTop: 'var(--space-4)' }}>
      {units.map((t, i) => {
        const c = crowns[t.id] || 0;
        const header = t.source?.courseTitle !== course ? (course = t.source?.courseTitle, course) : null;
        const words = (t.flashcards || []).length;
        const exercises = (t.practice || []).filter((p) => SESSION_TYPES.has(p.type)).length;
        return (
          <li key={t.id} className="lang-node" data-done={c >= 1} style={{ '--offset': `${[0, 1, 2, 1][i % 4] * 2.2}rem` }}>
            {header && <h2 className="lang-unit-head">{header}</h2>}
            <div className="lang-node-row">
              <button type="button" className="lang-node-dot" onClick={() => onStart({ mode: 'unit', unitId: t.id, title: t.title })} disabled={!words && !exercises}
                aria-label={`Start ${t.title}`}>{c ? <span className="num">{c}</span> : <Sparkles size={18} aria-hidden="true" />}</button>
              <div className="stack-xs">
                <strong>{t.title.replace(/^Class \d+:\s*/, '')}</strong>
                <span className="hint">{words} words · {exercises} exercises · <Crown size={12} aria-hidden="true" /> {c}/5</span>
                <span className="btn-row">
                  <button type="button" className="btn btn-primary btn-sm" onClick={() => onStart({ mode: 'unit', unitId: t.id, title: t.title })} disabled={!words && !exercises}>{c ? 'Practice again' : 'Start'}</button>
                  <button type="button" className="btn btn-quiet btn-sm" onClick={() => onOpenTopic(t.id)}><BookOpen size={14} aria-hidden="true" /> Guidebook</button>
                </span>
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

const MODES = [
  { mode: 'mixed', icon: Target, title: 'Mixed practice', text: 'Your weakest words and exercises first, from every unit.' },
  { mode: 'missed', icon: RotateCcw, title: 'Mistakes', text: 'Only what you got wrong recently, until you get it right.' },
  { mode: 'listen', icon: Headphones, title: 'Listening', text: 'Hear it, then pick or type what was said.' },
  { mode: 'speak', icon: Mic, title: 'Speaking', text: 'Say words and phrases; the browser checks your pronunciation.' },
  { mode: 'new', icon: Sparkles, title: 'New words', text: 'Words you have not practiced yet.' },
];

function PracticeHub({ onStart, counts }) {
  return (
    <div className="lang-modes" style={{ marginTop: 'var(--space-4)' }}>
      {MODES.map(({ mode, icon: Icon, title, text }) => (
        <button key={mode} type="button" className="panel lang-mode" onClick={() => onStart({ mode, title })} disabled={counts[mode] === 0}>
          <Icon size={22} aria-hidden="true" />
          <strong>{title}</strong>
          <span className="hint">{text}</span>
          <span className="hint num">{counts[mode] === 0 ? 'Nothing here yet' : `${counts[mode]} available`}</span>
        </button>
      ))}
    </div>
  );
}

function WordsTab({ topics }) {
  const [q, setQ] = useState('');
  const strength = store.get(K_STRENGTH, {});
  const words = wordsOf(topics).filter((w) => !q || `${w.front} ${w.back}`.toLowerCase().includes(q.toLowerCase()));
  if (!topics.some((t) => (t.flashcards || []).length)) return <div className="panel" style={{ marginTop: 'var(--space-4)' }}><p>No words yet. Each language class brings its vocabulary here.</p></div>;
  return (
    <div className="stack-sm" style={{ marginTop: 'var(--space-4)' }}>
      <input className="input" placeholder="Search words" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search words" />
      <table className="lang-words">
        <thead><tr><th>Word</th><th>Meaning</th><th>Strength</th><th>Unit</th></tr></thead>
        <tbody>
          {words.map((w) => (
            <tr key={w.key}>
              <td lang={w.lang || undefined}><strong>{w.front}</strong></td>
              <td><MdInline>{w.back}</MdInline></td>
              <td><span className="lang-strength" aria-label={`strength ${strength[w.key] || 0} of 4`}>{[1, 2, 3, 4].map((n) => <i key={n} data-on={(strength[w.key] || 0) >= n} />)}</span></td>
              <td className="hint">{w.unit.replace(/^Class \d+:\s*/, '')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Languages workspace, a free take on AI: a learn path of units (one per class), practice sessions with
 * hearts that never run out, listening and speaking drills, a word list with strength, flashcards, pronunciation
 * and IPA, and "Explain my answer" from the tutor.
 */
export default function LanguageLab({ classTopic, topics = [], onOpenTopic, renderClass, requestedTab }) {
  const [tab, setTab] = useState(requestedTab?.tab === 'roleplay' ? 'roleplay' : classTopic ? 'class' : 'path');
  const [session, setSession] = useState(null);   // {items, unitId, title, at}
  const [, setTick] = useState(0);                 // re-read local progress after a session
  useEffect(() => { if (classTopic) setTab('class'); }, [classTopic?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const start = ({ mode, unitId = null, title = '' }) => { setSession({ items: buildSession(topics, { mode, unitId }), unitId, title, at: Date.now() }); setTab('practice'); };
  useEffect(() => {
    if (!requestedTab?.tab || requestedTab.at === handledRequest) return;
    if (!topics.length && requestedTab.tab !== 'roleplay') return;
    handledRequest = requestedTab.at;  // module-level: survives the remount when the student comes back to Languages
    if (requestedTab.tab === 'session') start({ mode: requestedTab.mode || 'mixed', unitId: requestedTab.unitId || null });
    else setTab(requestedTab.tab);
  }, [requestedTab?.at, topics.length]); // eslint-disable-line react-hooks/exhaustive-deps
  const cards = useMemo(() => topics.flatMap((t) => (t.flashcards || []).map((c) => ({ ...c, _t: t.id }))), [topics]);
  const counts = useMemo(() => countModes(topics), [topics, session]); // eslint-disable-line react-hooks/exhaustive-deps
  const tabs = [
    ...(classTopic ? [{ id: 'class', label: `Class ${classTopic.source?.classSeq ?? ''}`.trim(), icon: BookOpen }] : []),
    { id: 'path', label: 'Learn', icon: Route },
    { id: 'practice', label: 'Practice', icon: Target },
    { id: 'roleplay', label: 'Roleplay', icon: MessageSquare },
    ...EXTRA_LANGUAGE_TABS.map(({ id, label, icon }) => ({ id, label, icon })),
    { id: 'words', label: `Words${cards.length ? ` (${cards.length})` : ''}`, icon: BookA },
    { id: 'cards', label: 'Flashcards', icon: Layers },
    { id: 'pronounce', label: 'Pronunciation', icon: Volume2 },
    { id: 'courses', label: 'Courses', icon: GraduationCap },
  ];
  const current = tabs.some((t) => t.id === tab) ? tab : 'path';
  const endSession = () => { setSession(null); setTick((n) => n + 1); };
  return (
    <WorkspaceShell kind="language" title="Languages" tabs={tabs} current={current} onTab={setTab}
      intro="Learn by doing: a path of units from your language classes, short sessions that mix translating, building sentences, listening and speaking, a word list that tracks what you know, flashcards read aloud, and pronunciation with IPA.">
      {current === 'class' && classTopic && renderClass(classTopic)}
      {current === 'path' && <PathTab topics={topics} onStart={start} onOpenTopic={onOpenTopic} />}
      {current === 'practice' && (session
        ? <div style={{ marginTop: 'var(--space-4)' }}><Session key={session.at} {...session} onExit={endSession} /></div>
        : <PracticeHub onStart={start} counts={counts} />)}
      {current === 'roleplay' && <LanguageRoleplay defaultLang={topics[0]?.lang || topics[0]?.flashcards?.[0]?.lang || 'es'} />}
      {EXTRA_LANGUAGE_TABS.map((t) => current === t.id && <React.Fragment key={t.id}>{t.render(topics)}</React.Fragment>)}
      {current === 'words' && <WordsTab topics={topics} />}
      {current === 'cards' && <div style={{ marginTop: 'var(--space-4)' }}><FlashcardDeck key={cards.length} cards={cards} topicId="language-all" /></div>}
      {current === 'pronounce' && <PronounceTab />}
      {current === 'courses' && <CoursesTab topics={topics} onOpenTopic={onOpenTopic} activeId={classTopic?.id} empty="No language courses yet. Start one from My courses: its classes open here." />}
    </WorkspaceShell>
  );
}
