import React, { useEffect, useMemo, useState } from 'react';
import { BookOpen, GraduationCap, Layers, CalendarRange, Volume2, Zap } from 'lucide-react';
import { CoursesTab } from './MathLab';
import { FlashcardDeck, TimelineView } from './Activities';
import { LANGUAGES, languageName, voicesFor, pickVoice, setPreferredVoice, speak, noVoiceHelp } from '../lib/speech';

const IPA = [['i', 'see'], ['ɪ', 'sit'], ['e', 'say (fr. été)'], ['ɛ', 'bed'], ['æ', 'cat'], ['ɑ', 'father'], ['ɔ', 'thought'], ['o', 'go (fr. eau)'],
  ['ʊ', 'put'], ['u', 'food'], ['ʌ', 'cup'], ['ə', 'about'], ['θ', 'think'], ['ð', 'this'], ['ʃ', 'she'], ['ʒ', 'vision'], ['ŋ', 'sing'],
  ['tʃ', 'church'], ['dʒ', 'judge'], ['ɲ', 'sp. año'], ['x', 'sp. jota'], ['ʁ', 'fr. rouge'], ['y', 'fr. tu'], ['ø', 'fr. peu'], ['ɦ', 'uk. голова'], ['ɨ', 'uk. син / ru. сын'], ['ʲ', 'soft sign: uk. день'], ['ʋ', 'uk. вода']];

const SAMPLES = { uk: 'Добрий день! Як справи?', es: '¿Dónde está la biblioteca?', fr: 'Où est la bibliothèque ?', de: 'Wo ist die Bibliothek?',
  it: "Dov'è la biblioteca?", pt: 'Onde fica a biblioteca?', pl: 'Gdzie jest biblioteka?', ru: 'Где библиотека?', zh: '图书馆在哪里？',
  ja: '図書館はどこですか？', ko: '도서관이 어디에 있어요?', ar: 'أين المكتبة؟', en: 'Where is the library?' };

function PronounceTab() {
  const [lang, setLang] = useState(() => { try { return localStorage.getItem('andedu_pron_lang') || 'uk'; } catch { return 'uk'; } });
  const [text, setText] = useState(SAMPLES[lang] || '');
  const [rate, setRate] = useState(0.9);
  const [voices, setVoices] = useState([]);
  const [voice, setVoice] = useState('');
  const [note, setNote] = useState(null);
  useEffect(() => {
    try { localStorage.setItem('andedu_pron_lang', lang); } catch { /* private mode */ }
    let live = true;
    voicesFor(lang).then((list) => { if (!live) return; setVoices(list); pickVoice(lang).then((v) => live && setVoice(v?.name || '')); });
    return () => { live = false; };
  }, [lang]);
  const changeLang = (l) => { setLang(l); setText(SAMPLES[l] || ''); setNote(null); };
  const say = async () => {
    const r = await speak(text, lang, { rate });
    setNote(r.ok ? null : r.reason === 'no-voice' ? noVoiceHelp(r.language) : 'This browser cannot read text aloud.');
  };
  return (
    <div className="stack" style={{ marginTop: 'var(--space-4)' }}>
      <div className="panel stack-sm">
        <h2>Hear it</h2>
        <div className="btn-row">
          <select className="input" style={{ width: 160 }} value={lang} onChange={(e) => changeLang(e.target.value)} aria-label="Language">
            {LANGUAGES.map(([c, n]) => <option key={c} value={c}>{n}</option>)}
          </select>
          <input className="input" style={{ flex: '1 1 280px' }} value={text} onChange={(e) => setText(e.target.value)} aria-label="Text to pronounce" lang={lang} />
          <button type="button" className="btn btn-primary" onClick={say} disabled={!text.trim()}><Volume2 size={15} /> Listen</button>
        </div>
        <div className="btn-row">
          <label className="field" style={{ minWidth: 240 }}>
            <span className="hint">Voice</span>
            {voices.length ? (
              <select className="input" value={voice} onChange={(e) => { setVoice(e.target.value); setPreferredVoice(lang, e.target.value); }}>
                {voices.map((v) => <option key={v.name} value={v.name}>{v.name} ({v.lang}){v.localService ? '' : ' · online'}</option>)}
              </select>
            ) : <span className="notice notice-bad">No {languageName(lang)} voice installed</span>}
          </label>
          <label className="slider" style={{ minWidth: 220 }}>
            <span className="hint">Speed {rate.toFixed(2)}×</span>
            <input type="range" min={0.5} max={1.3} step={0.05} value={rate} onChange={(e) => setRate(Number(e.target.value))} />
          </label>
        </div>
        {(note || !voices.length) && <p className="notice notice-info">{note || noVoiceHelp(languageName(lang))}</p>}
        <p className="hint">Uses the voices installed on your computer. "Enhanced" and "Premium" voices sound far more natural than the default ones.</p>
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
