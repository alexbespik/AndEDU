import React, { Suspense, lazy, useCallback, useEffect, useRef, useState } from 'react';
import { BookOpen, Compass, Award, Puzzle, Copy, Check, MessageCircleQuestion, ChevronLeft, ChevronRight, Layers, Zap, CalendarRange, Sparkles } from 'lucide-react';
import QuizEngine from './QuizEngine';
import PracticeDeck from './PracticeDeck';
import { FlashcardDeck, SpeedRound, TimelineView, ScoreStrip } from './Activities';
import { reportXp, reportActivity } from '../lib/engage';
import MermaidViewer from './MermaidViewer';
import Md, { MdInline } from './Md';
import { api } from '../lib/api';
import LessonTutor from './LessonTutor';
import MoreMenu from './MoreMenu';
import TextSelectionAskAgy from './TextSelectionAskAgy';
import ExplainPlayer from './ExplainPlayer';

// simulations load when the Simulation tab opens, not with every lesson
const RollingWithoutSlippingSim = lazy(() => import('../simulations/RollingWithoutSlippingSim'));
const BilliardSim = lazy(() => import('../simulations/BilliardSim'));
const SpecSim = lazy(() => import('../simulations/SpecSim'));

const BUILTIN = {
  rolling_without_slipping: () => <RollingWithoutSlippingSim />,
  billiard_collisions: (cfg) => <BilliardSim config={cfg} />,
};

function SimulationTab({ topic, liveSimConfig }) {
  const sim = topic.simulation ? <SpecSim spec={topic.simulation} />
    : BUILTIN[topic.simulationType] ? BUILTIN[topic.simulationType](liveSimConfig) : null;
  return sim && <Suspense fallback={<p className="hint">Loading the simulation…</p>}>{sim}</Suspense>;
}

/** The diagram's node labels ("A[Incident] --> B[Evanescent]" -> "Incident, Evanescent"), for the walkthrough writer. */
function diagramLabels(src) {
  const labels = [...String(src).matchAll(/[[({]+"?([^\])}"\n]{1,60})"?[\])}]+/g)].map((m) => m[1].trim()).filter(Boolean);
  return (labels.length ? labels.join(', ') : String(src)).slice(0, 160);
}

function LessonTab({ topic, explainAsk, onExplainUsed }) {
  const [copied, setCopied] = useState(null);
  const [touring, setTouring] = useState(false);  // the "Explain it to me" walkthrough is open
  const rootRef = useRef(null);
  const explainBtn = useRef(null);
  // "Explain it to me" from the More menu: start here once, then forget the request
  useEffect(() => {
    if (!explainAsk) return;
    setTouring(true);
    onExplainUsed?.();
  }, [explainAsk, onExplainUsed]);
  const closeTour = useCallback(() => { setTouring(false); explainBtn.current?.focus({ preventScroll: true }); }, []);
  const copy = async (text, i) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(i);
      setTimeout(() => setCopied(null), 1600);
    } catch { /* clipboard blocked; the formula is still selectable */ }
  };

  return (
    <div className="stack" ref={rootRef}>
      {topic.markdownContent && (
        <div className="explain-cta">
          <button type="button" ref={explainBtn} className="btn btn-primary explain-btn" onClick={() => setTouring(true)}
            aria-describedby="explain-cta-note" aria-expanded={touring}>
            <Sparkles size={16} aria-hidden="true" /> Explain it to me
          </button>
          <span id="explain-cta-note" className="hint">A narrated walkthrough that points at each idea on this page.</span>
        </div>
      )}
      {topic.cheatSheet?.length > 0 && (
        <section className="stack-sm" aria-labelledby="formulas-h">
          <h2 id="formulas-h" style={{ fontSize: '1.2rem' }}>Key formulas</h2>
          <div className="formula-grid">
            {topic.cheatSheet.map((item, i) => (
              <div key={i} className="formula" data-explain={`f${i}`}
                data-explain-text={`${item.label || item.name ? `${item.label || item.name}: ` : ''}${item.formula}`}>
                <div style={{ minWidth: 0 }}>
                  {(item.label || item.name) && <span className="lbl"><MdInline>{item.label || item.name}</MdInline></span>}
                  <div className="tex"><MdInline>{`$${item.formula}$`}</MdInline></div>
                </div>
                <button type="button" className="btn btn-quiet btn-sm btn-icon" onClick={() => copy(item.formula, i)}
                  aria-label={copied === i ? 'Copied' : `Copy LaTeX for ${item.label || 'formula'}`}>
                  {copied === i ? <Check size={14} /> : <Copy size={14} />}
                </button>
              </div>
            ))}
          </div>
        </section>
      )}
      {topic.mermaid && (
        <div data-explain="diagram" data-explain-text={diagramLabels(topic.mermaid)}>
          <MermaidViewer chart={topic.mermaid} />
        </div>
      )}
      <TextSelectionAskAgy topicId={topic.id} courseId={topic.source?.courseId}>
        <Md className="prose" explainIds>{topic.markdownContent}</Md>
      </TextSelectionAskAgy>
      {touring && <ExplainPlayer topic={topic} rootRef={rootRef} onClose={closeTour} />}
    </div>
  );
}

export default function TopicViewer({ topic, activeTab, setActiveTab, liveSimConfig, userId, course, onOpenCourse, onHome, prevClass, nextClass, onOpenClass, embedded = false }) {
  const [tutorFocus, setTutorFocus] = useState(null);
  const [explainAsk, setExplainAsk] = useState(0);  // the More menu asked for the walkthrough
  const explainUsed = useCallback(() => setExplainAsk(0), []);
  const solvedRef = useRef(new Set());  // practice items solved in this visit (for the practice & games score)
  useEffect(() => { solvedRef.current = new Set(); }, [topic?.id]);

  // Opening a course class tells the server, so adaptation never rewrites a lesson you're reading.
  useEffect(() => {
    if (topic?.source?.courseId) api(`/api/topics/${topic.id}/opened`, { method: 'POST' }).catch(() => {});
  }, [topic?.id, topic?.source?.courseId]);

  // Time spent with a lesson or a simulation counts (not just opening it)
  useEffect(() => {
    const source = activeTab === 'simulation' ? 'sim_explored' : activeTab === 'theory' || !activeTab ? 'lesson_read' : null;
    if (!source || !topic?.id) return undefined;
    const t = setTimeout(() => { if (!document.hidden) reportXp(source, topic.id); }, source === 'lesson_read' ? 90000 : 30000);
    return () => clearTimeout(t);
  }, [activeTab, topic?.id]);

  if (!topic) {
    return <div className="page"><p className="hint">Pick a topic from the list to start.</p></div>;
  }

  const hasSim = Boolean(topic.simulation || BUILTIN[topic.simulationType]);
  const tabs = [
    { id: 'theory', label: 'Lesson', icon: BookOpen },
    ...(hasSim ? [{ id: 'simulation', label: 'Simulation', icon: Compass }] : []),
    { id: 'quiz', label: 'Quiz', icon: Award, count: topic.quiz?.length || 0 },
    { id: 'practice', label: 'Practice', icon: Puzzle, count: topic.practice?.length || 0 },
    ...(topic.flashcards?.length ? [{ id: 'cards', label: 'Flashcards', icon: Layers, count: topic.flashcards.length }] : []),
    ...((topic.quiz?.length || 0) >= 3 ? [{ id: 'speed', label: 'Speed round', icon: Zap }] : []),
    ...(topic.timeline?.length ? [{ id: 'timeline', label: 'Timeline', icon: CalendarRange, count: topic.timeline.length }] : []),
    { id: 'tutor', label: 'Tutor', icon: MessageCircleQuestion },
  ];
  const tab = tabs.some((t) => t.id === activeTab) ? activeTab : 'theory';

  const src = topic.source || {};

  return (
    <div className={embedded ? 'stack embedded-topic' : 'page'}>
      <header className="topic-head">
        {src.courseId && (
          <div className="class-bar">
            <nav className="crumbs" aria-label="Breadcrumb">
              {onHome && <><button type="button" onClick={onHome}>My courses</button><span aria-hidden="true">/</span></>}
              <button type="button" onClick={() => onOpenCourse?.(src.courseId)}>{course?.title || src.courseTitle || 'Course'}</button>
              <span aria-hidden="true">/</span>
              <span>Class {src.classSeq}{src.classTotal ? ` of ${src.classTotal}` : ''}</span>
            </nav>
            {onOpenClass && (prevClass || nextClass) && (
              <div className="btn-row">
                <button type="button" className="btn btn-quiet btn-sm" disabled={!prevClass} onClick={() => onOpenClass(prevClass.id)}
                  title={prevClass?.title}><ChevronLeft size={14} aria-hidden="true" /> Previous class</button>
                <button type="button" className="btn btn-secondary btn-sm" disabled={!nextClass} onClick={() => onOpenClass(nextClass.id)}
                  title={nextClass?.title}>Next class <ChevronRight size={14} aria-hidden="true" /></button>
              </div>
            )}
          </div>
        )}
        <h1>{topic.title}</h1>
        <div className="topic-tags">
          {topic.category && <span>{topic.category}</span>}
          {topic.difficulty && <span>{topic.difficulty}</span>}
        </div>
        {topic.summary && <p className="summary"><MdInline>{topic.summary}</MdInline></p>}
        <MoreMenu key={topic.id} topic={topic} courseTitle={course?.title || src.courseTitle}
          onExplain={topic.markdownContent ? () => { setActiveTab('theory'); setExplainAsk((n) => n + 1); } : undefined} />
        <ScoreStrip topicId={topic.id} userId={userId} />
        <div className="tabs" role="tablist" aria-label="Topic sections">
          {tabs.map(({ id, label, icon: Icon, count, note }) => (
            <button key={id} type="button" role="tab" id={`tab-${id}`} aria-selected={tab === id} aria-controls={`panel-${id}`}
              className="tab" onClick={() => setActiveTab(id)}>
              <Icon size={16} aria-hidden="true" /> {label}
              {count > 0 && <span className="count">{count}</span>}
              {note && <span className="count">{note}</span>}
            </button>
          ))}
        </div>
      </header>

      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === 'theory' && <LessonTab key={topic.id} topic={topic} explainAsk={explainAsk} onExplainUsed={explainUsed} />}
        {tab === 'simulation' && <SimulationTab key={topic.id} topic={topic} liveSimConfig={liveSimConfig} />}
        {tab === 'quiz' && (
          <QuizEngine key={topic.id} quiz={topic.quiz} topicId={topic.id} userId={userId}
            onAskTutor={(focus) => { setTutorFocus(focus); setActiveTab('tutor'); }} />
        )}
        {tab === 'tutor' && <LessonTutor key={topic.id} topic={topic} focus={tutorFocus} onFocusUsed={() => setTutorFocus(null)} />}
        {tab === 'cards' && <FlashcardDeck key={topic.id} cards={topic.flashcards} topicId={topic.id} />}
        {tab === 'speed' && <SpeedRound key={topic.id} quiz={topic.quiz} topicId={topic.id} userId={userId} />}
        {tab === 'timeline' && <TimelineView key={topic.id} events={topic.timeline} topicId={topic.id} />}
        {tab === 'practice' && <PracticeDeck key={topic.id} items={topic.practice} topicId={topic.id} onSolved={(item) => {
          reportXp('practice_correct', `${topic.id}:${item.id}`);
          solvedRef.current.add(item.id);
          reportActivity(topic.id, 'practice', solvedRef.current.size, (topic.practice || []).length);
        }} />}
      </div>
    </div>
  );
}
