import React, { useState } from 'react';
import { BookOpen, Compass, Award, Puzzle, Copy, Check, Download, FlaskConical, Loader2 } from 'lucide-react';
import RollingWithoutSlippingSim from '../simulations/RollingWithoutSlippingSim';
import BilliardSim from '../simulations/BilliardSim';
import QuizEngine from './QuizEngine';
import PracticeDeck from './PracticeDeck';
import MermaidViewer from './MermaidViewer';
import Md, { MdInline } from './Md';
import { api, useAgyEvents, downloadFile } from '../lib/api';

const BUILTIN = {
  rolling_without_slipping: () => <RollingWithoutSlippingSim />,
  billiard_collisions: (cfg) => <BilliardSim config={cfg} />,
};

function SimulationTab({ topic, liveSimConfig }) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);

  useAgyEvents((evt) => {
    if (evt.type === 'JOB_UPDATE' && job && evt.payload.id === job.id) setJob(evt.payload);
  });

  if (BUILTIN[topic.simulationType]) return BUILTIN[topic.simulationType](liveSimConfig);

  if (topic.simulation) {
    const s = topic.simulation;
    return (
      <section className="panel stack">
        <h2>{s.title}</h2>
        {s.description && <p>{s.description}</p>}
        {s.params?.length > 0 && (
          <ul className="stack-sm" style={{ margin: 0, paddingLeft: '1.2em' }}>
            {s.params.map((p) => (
              <li key={p.name}>{p.label}: {p.min} to {p.max}{p.unit ? ` ${p.unit}` : ''}</li>
            ))}
          </ul>
        )}
        <p className="notice notice-info">This simulation is saved and validated. The interactive renderer for generated simulations isn't wired up yet, so it can't be played here.</p>
      </section>
    );
  }

  const running = job && (job.status === 'queued' || job.status === 'running');
  const start = async () => {
    setError(null);
    try {
      setJob(await api('/api/simulations/generate', { method: 'POST', body: { topicId: topic.id } }));
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <section className="panel empty-sim">
      <FlaskConical size={28} color="var(--wm-green)" aria-hidden="true" />
      <h2>No simulation for this topic yet</h2>
      <p style={{ maxWidth: '52ch' }}>AGY can design one from this lesson: sliders for the quantities that matter, plus live readouts of what they change.</p>
      <div className="btn-row" style={{ justifyContent: 'center' }}>
        <button type="button" className="btn btn-primary" onClick={start} disabled={running}>
          {running ? <><Loader2 size={16} className="spin" aria-hidden="true" /> {job.step || 'Working'}</> : 'Generate simulation'}
        </button>
      </div>
      {job?.status === 'error' && <p className="notice notice-bad">{job.error}</p>}
      {job?.status === 'done' && <p className="notice notice-ok">Simulation created. It will appear here in a moment.</p>}
      {error && <p className="notice notice-bad">{error}</p>}
    </section>
  );
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

export default function TopicViewer({ topic, activeTab, setActiveTab, liveSimConfig, userId, course, onOpenCourse }) {
  if (!topic) {
    return <div className="page"><p className="hint">Pick a topic from the list to start.</p></div>;
  }

  const hasSim = Boolean(topic.simulation || BUILTIN[topic.simulationType]);
  const tabs = [
    { id: 'theory', label: 'Lesson', icon: BookOpen },
    { id: 'simulation', label: 'Simulation', icon: Compass, note: hasSim ? null : 'none yet' },
    { id: 'quiz', label: 'Quiz', icon: Award, count: topic.quiz?.length || 0 },
    { id: 'practice', label: 'Practice', icon: Puzzle, count: topic.practice?.length || 0 },
  ];
  const tab = tabs.some((t) => t.id === activeTab) ? activeTab : 'theory';
  const src = topic.source || {};

  return (
    <div className="page">
      <header className="topic-head">
        {src.courseId && (
          <nav className="crumbs" aria-label="Breadcrumb">
            <button type="button" onClick={() => onOpenCourse?.(src.courseId)}>{course?.title || src.courseTitle || 'Course'}</button>
            <span aria-hidden="true">/</span>
            <span>Class {src.classSeq}{src.classTotal ? ` of ${src.classTotal}` : ''}</span>
          </nav>
        )}
        <h1>{topic.title}</h1>
        <div className="topic-tags">
          {topic.category && <span>{topic.category}</span>}
          {topic.difficulty && <span>{topic.difficulty}</span>}
        </div>
        {topic.summary && <p className="summary">{topic.summary}</p>}
        {topic.notesFile && (
          <div className="btn-row">
            <button type="button" className="btn btn-quiet btn-sm"
              onClick={() => downloadFile(`/api/notes/${topic.id}.md`, `${topic.id}.md`).catch(() => {})}>
              <Download size={14} aria-hidden="true" /> Download notes (.md)
            </button>
          </div>
        )}
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
        {tab === 'quiz' && <QuizEngine key={topic.id} quiz={topic.quiz} topicId={topic.id} userId={userId} />}
        {tab === 'practice' && <PracticeDeck key={topic.id} items={topic.practice} />}
      </div>
    </div>
  );
}
