import React, { useEffect, useState } from 'react';
import { BookOpen, Compass, Award, Puzzle, Copy, Check, MessageCircleQuestion, ChevronLeft, ChevronRight } from 'lucide-react';
import RollingWithoutSlippingSim from '../simulations/RollingWithoutSlippingSim';
import BilliardSim from '../simulations/BilliardSim';
import SpecSim from '../simulations/SpecSim';
import QuizEngine from './QuizEngine';
import PracticeDeck from './PracticeDeck';
import { reportXp } from '../lib/engage';
import MermaidViewer from './MermaidViewer';
import Md, { MdInline } from './Md';
import { api } from '../lib/api';
import LessonTutor from './LessonTutor';
import MoreMenu from './MoreMenu';

const BUILTIN = {
  rolling_without_slipping: () => <RollingWithoutSlippingSim />,
  billiard_collisions: (cfg) => <BilliardSim config={cfg} />,
};

function SimulationTab({ topic, liveSimConfig }) {
  if (topic.simulation) {
    return <SpecSim spec={topic.simulation} />;
  }
  return BUILTIN[topic.simulationType] ? BUILTIN[topic.simulationType](liveSimConfig) : null;
}

function LessonTab({ topic }) {
  const [copied, setCopied] = useState(null);
  const copy = async (text, i) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(i);
      setTimeout(() => setCopied(null), 1600);
    } catch { /* clipboard blocked; the formula is still selectable */ }
  };

  return (
    <div className="stack">
      {topic.cheatSheet?.length > 0 && (
        <section className="stack-sm" aria-labelledby="formulas-h">
          <h2 id="formulas-h" style={{ fontSize: '1.2rem' }}>Key formulas</h2>
          <div className="formula-grid">
            {topic.cheatSheet.map((item, i) => (
              <div key={i} className="formula">
                <div style={{ minWidth: 0 }}>
                  {(item.label || item.name) && <span className="lbl">{item.label || item.name}</span>}
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
      {topic.mermaid && <MermaidViewer chart={topic.mermaid} />}
      <Md className="prose">{topic.markdownContent}</Md>
    </div>
  );
}

export default function TopicViewer({ topic, activeTab, setActiveTab, liveSimConfig, userId, course, onOpenCourse, onHome, prevClass, nextClass, onOpenClass, embedded = false }) {
  const [tutorFocus, setTutorFocus] = useState(null);

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
        {topic.summary && <p className="summary">{topic.summary}</p>}
        <MoreMenu key={topic.id} topic={topic} courseTitle={course?.title || src.courseTitle} />
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
        {tab === 'theory' && <LessonTab topic={topic} />}
        {tab === 'simulation' && <SimulationTab key={topic.id} topic={topic} liveSimConfig={liveSimConfig} />}
        {tab === 'quiz' && (
          <QuizEngine key={topic.id} quiz={topic.quiz} topicId={topic.id} userId={userId}
            onAskTutor={(focus) => { setTutorFocus(focus); setActiveTab('tutor'); }} />
        )}
        {tab === 'tutor' && <LessonTutor key={topic.id} topic={topic} focus={tutorFocus} onFocusUsed={() => setTutorFocus(null)} />}
        {tab === 'practice' && <PracticeDeck key={topic.id} items={topic.practice} onSolved={(item) => reportXp('practice_correct', `${topic.id}:${item.id}`)} />}
      </div>
    </div>
  );
}
