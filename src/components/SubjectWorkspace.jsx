import React, { useEffect, useMemo, useState } from 'react';
import { BookOpen, GraduationCap, Layers, CalendarRange, Volume2, Zap } from 'lucide-react';
import { CoursesTab } from './MathLab';
import { FlashcardDeck, TimelineView } from './Activities';

const VOICES = [['es', 'Spanish'], ['fr', 'French'], ['de', 'German'], ['it', 'Italian'], ['pt', 'Portuguese'], ['zh', 'Chinese'], ['ja', 'Japanese'],
  ['ko', 'Korean'], ['ar', 'Arabic'], ['ru', 'Russian'], ['la', 'Latin'], ['en', 'English']];
const IPA = [['i', 'see'], ['ɪ', 'sit'], ['e', 'say (fr. été)'], ['ɛ', 'bed'], ['æ', 'cat'], ['ɑ', 'father'], ['ɔ', 'thought'], ['o', 'go (fr. eau)'],
  ['ʊ', 'put'], ['u', 'food'], ['ʌ', 'cup'], ['ə', 'about'], ['θ', 'think'], ['ð', 'this'], ['ʃ', 'she'], ['ʒ', 'vision'], ['ŋ', 'sing'],
  ['tʃ', 'church'], ['dʒ', 'judge'], ['ɲ', 'sp. año'], ['x', 'sp. jota'], ['ʁ', 'fr. rouge'], ['y', 'fr. tu'], ['ø', 'fr. peu']];

function PronounceTab() {
  const [text, setText] = useState('¿Dónde está la biblioteca?');
  const [lang, setLang] = useState('es');
  const [rate, setRate] = useState(0.9);
  const say = (t, l = lang) => {
    if (!window.speechSynthesis) return;
    const u = new SpeechSynthesisUtterance(t); u.lang = l; u.rate = rate;
    window.speechSynthesis.cancel(); window.speechSynthesis.speak(u);
  };
  return (
    <div className="stack" style={{ marginTop: 'var(--space-4)' }}>
      <div className="panel stack-sm">
        <h2>Hear it</h2>
        <div className="btn-row">
          <input className="input" style={{ flex: '1 1 280px' }} value={text} onChange={(e) => setText(e.target.value)} aria-label="Text to pronounce" />
          <select className="input" style={{ width: 150 }} value={lang} onChange={(e) => setLang(e.target.value)} aria-label="Language">
            {VOICES.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
          </select>
          <button type="button" className="btn btn-primary" onClick={() => say(text)}><Volume2 size={15} /> Listen</button>
        </div>
        <label className="slider" style={{ maxWidth: 320 }}>
          <span className="hint">Speed {rate.toFixed(2)}×</span>
          <input type="range" min={0.5} max={1.3} step={0.05} value={rate} onChange={(e) => setRate(Number(e.target.value))} />
        </label>
        <p className="hint">Uses your browser's voices; install more in your system's speech settings for better accents.</p>
      </div>
      <div className="panel stack-sm">
        <h2>IPA quick reference</h2>
        <div className="ipa-grid">
          {IPA.map(([sym, ex]) => <div key={sym} className="ipa-cell"><span className="ipa-sym">{sym}</span><span className="hint">{ex}</span></div>)}
        </div>
      </div>
    </div>
  );
}

/**
 * History and Languages workspaces: their course classes open here, next to the tools that subject needs:
 * every flashcard from the subject's lessons in one deck, plus a merged timeline (History) or pronunciation and
 * IPA (Languages). Lessons themselves carry speed rounds, matching and ordering challenges.
 */
export default function SubjectWorkspace({ kind, classTopic, topics = [], onOpenTopic, renderClass }) {
  const isHistory = kind === 'history';
  const [tab, setTab] = useState(classTopic ? 'class' : 'courses');
  useEffect(() => { if (classTopic) setTab('class'); }, [classTopic?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const cards = useMemo(() => topics.flatMap((t) => (t.flashcards || []).map((c) => ({ ...c, _t: t.id }))), [topics]);
  const events = useMemo(() => topics.flatMap((t) => t.timeline || []).sort((a, b) => a.year - b.year), [topics]);
  const tabs = [
    ...(classTopic ? [{ id: 'class', label: `Class ${classTopic.source?.classSeq ?? ''}`.trim(), icon: BookOpen }] : []),
    { id: 'courses', label: 'Courses', icon: GraduationCap },
    { id: 'cards', label: `All flashcards${cards.length ? ` (${cards.length})` : ''}`, icon: Layers },
    isHistory ? { id: 'timeline', label: 'Timeline', icon: CalendarRange } : { id: 'pronounce', label: 'Pronunciation', icon: Volume2 },
  ];
  const current = tabs.some((t) => t.id === tab) ? tab : 'courses';
  return (
    <div className="page page-wide">
      <div className="page-head">
        <div>
          <h1>{isHistory ? 'History' : 'Languages'}</h1>
          <p>{isHistory
            ? 'Your history classes with a timeline of everything you have studied, flashcards for people and terms, matching and ordering challenges, and speed rounds.'
            : 'Your language and linguistics classes with flashcards read aloud, pronunciation practice, an IPA reference, matching games and speed rounds.'}</p>
        </div>
      </div>
      <div className="tabs" role="tablist" aria-label={`${kind} tools`}>
        {tabs.map(({ id, label, icon: Icon }) => (
          <button key={id} type="button" role="tab" aria-selected={current === id} className="tab" onClick={() => setTab(id)}><Icon size={16} aria-hidden="true" /> {label}</button>
        ))}
      </div>
      <section role="tabpanel">
        {current === 'class' && classTopic && renderClass(classTopic)}
        {current === 'courses' && <CoursesTab topics={topics} onOpenTopic={onOpenTopic} activeId={classTopic?.id} empty={`No ${isHistory ? 'history' : 'language'} courses yet. Start one from My courses: its classes open here.`} />}
        {current === 'cards' && <div style={{ marginTop: 'var(--space-4)' }}><FlashcardDeck key={cards.length} cards={cards} topicId={`${kind}-all`} /></div>}
        {current === 'timeline' && <div style={{ marginTop: 'var(--space-4)' }}><TimelineView events={events} topicId="history-all" /></div>}
        {current === 'pronounce' && <PronounceTab />}
      </section>
      {current === 'courses' && topics.some((t) => (t.quiz || []).length >= 3) && (
        <p className="hint"><Zap size={13} aria-hidden="true" /> Every class with 3 or more quiz questions has a Speed round tab.</p>
      )}
    </div>
  );
}
