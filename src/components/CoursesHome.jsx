import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Upload, X, Loader2, BookOpen, Target, ListPlus, Code2, Plus } from 'lucide-react';
import { api, uploadFiles, useAgyEvents } from '../lib/api';

export const STATUS = {
  planning: ['Writing diagnostic', 'status-working'],
  diagnostic_ready: ['Diagnostic ready', 'status-working'],
  generating: ['Writing classes', 'status-working'],
  ready: ['Ready', 'status-ready'],
  error: ['Needs attention', 'status-error'],
};

const INTENTS = [
  { id: 'learn', icon: BookOpen, title: 'Learn it', text: 'A diagnostic, then a sequence of classes built around your gaps.' },
  { id: 'test_prep', icon: Target, title: 'Prepare for a test', text: 'Exam-focused review classes, exam-style quizzes and a final mock exam.' },
  { id: 'continue', icon: ListPlus, title: 'Continue a course', text: 'New materials become the next classes of a course you already have.' },
  { id: 'code', icon: Code2, title: 'Coding practice', text: 'Hands-on exercises in the IDE: fill-in slots, block ordering and code you run.' },
];

/**
 * The one place materials go in: drop files or paste notes, say what you want, pick learn / test prep / continue.
 */
export function StudyHub({ userId, courses = [], preset, onOpened, onCodePractice, onCancel, lockIntent = false }) {
  const [intent, setIntent] = useState(preset?.intent || 'learn');
  const [target, setTarget] = useState(preset?.courseId || '');
  const [goal, setGoal] = useState('');
  const [text, setText] = useState('');
  const [files, setFiles] = useState([]);
  const [over, setOver] = useState(false);
  const [examDate, setExamDate] = useState('');
  const [questions, setQuestions] = useState(8);
  const [classes, setClasses] = useState('');
  const [step, setStep] = useState(null);
  const [error, setError] = useState(null);
  const pickerRef = useRef(null);
  const rootRef = useRef(null);

  // courses that can take more classes: set up, not mid-planning
  const extendable = courses.filter((c) => !['planning', 'diagnostic_ready'].includes(c.status) && c.class_count > 0);

  const presetKey = preset ? `${preset.intent}:${preset.courseId || ''}:${preset.at || ''}` : '';
  useEffect(() => {
    if (!preset) return;
    setIntent(preset.intent);
    if (preset.courseId) setTarget(preset.courseId);
    if (!lockIntent) rootRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [presetKey]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (intent === 'continue' && !extendable.some((c) => c.id === target)) setTarget(extendable[0]?.id || '');
  }, [intent, extendable, target]);

  const addFiles = (list) => setFiles((f) => [...f, ...Array.from(list).filter((x) => !f.some((y) => y.name === x.name))]);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      let materials = text.trim();
      if (files.length) {
        setStep(`Reading ${files.length} file${files.length > 1 ? 's' : ''}`);
        const up = await uploadFiles(files);
        materials = [up.extracted_text, materials].filter(Boolean).join('\n\n');
      }
      const base = { goal: goal.trim(), materials_text: materials, filenames: files.map((f) => f.name),
                     class_count: classes ? Number(classes) : null };
      if (intent === 'code') {
        onCodePractice({ topic: goal.trim(), text: materials, chapters: classes ? Number(classes) : null,
                         files: files.map((f) => f.name), at: Date.now() });
        return;
      }
      if (intent === 'continue') {
        setStep('Planning the next classes');
        await api(`/api/courses/${target}/extend`, { method: 'POST', body: base });
        onOpened(target);
      } else {
        setStep(intent === 'test_prep' ? 'Starting your test prep' : 'Starting your course');
        const { course } = await api('/api/courses', {
          method: 'POST',
          body: { ...base, userId, num_questions: Number(questions), mode: intent, exam_date: intent === 'test_prep' ? examDate || null : null },
        });
        onOpened(course.id);
      }
    } catch (err) {
      setError(err.message);
      setStep(null);
    }
  };

  const enough = goal.trim().length + text.trim().length >= 20 || files.length > 0;
  const ready = enough && (intent !== 'continue' || target);
  const goalLabel = { learn: 'What do you want to learn?', test_prep: 'Which test, and what does it cover?',
                      continue: 'What should the next classes cover?', code: 'What do you want to practise coding?' }[intent];
  const goalHint = { learn: 'e.g. Rotational dynamics for Physics 101', test_prep: 'e.g. Chem 121 final: stoichiometry, gases, thermochemistry',
                     continue: 'e.g. Next week: angular momentum and gyroscopes', code: 'e.g. Python loops and the accumulator pattern' }[intent];

  return (
    <form ref={rootRef} className="panel stack hub" onSubmit={submit} aria-labelledby="hub-h">
      <div className="page-head" style={{ alignItems: 'flex-start' }}>
       <div>
        <h2 id="hub-h">{lockIntent ? 'Continue this course' : 'New course'}</h2>
        <p className="hint">{lockIntent ? 'New materials become the next classes, built on what you already did.'
          : 'Drop slides, notes or a problem set, then choose what to do with them.'}</p>
       </div>
        {onCancel && <button type="button" className="btn btn-quiet btn-sm" onClick={onCancel}>Cancel</button>}
      </div>

      <div className="dropzone dropzone-lg" data-over={over}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); addFiles(e.dataTransfer.files); }}>
        <Upload size={22} aria-hidden="true" className="dz-icon" />
        <div className="stack-sm" style={{ flex: 1, minWidth: 200 }}>
          <strong>Drop files here</strong>
          <span className="hint">PDF, DOCX, notebooks, text, or photos of handwritten notes</span>
        </div>
        <button type="button" className="btn btn-secondary" onClick={() => pickerRef.current?.click()}>Choose files</button>
        <input ref={pickerRef} type="file" multiple hidden accept=".pdf,.docx,.ipynb,.txt,.md,.py,.csv,.json,.png,.jpg,.jpeg,.webp"
          onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }} />
        {files.length > 0 && (
          <div className="file-chips" style={{ flexBasis: '100%' }}>
            {files.map((f) => (
              <span key={f.name} className="chip">{f.name}
                <button type="button" className="btn btn-quiet btn-sm btn-icon" style={{ minHeight: 22, width: 22, border: 0 }}
                  onClick={() => setFiles((l) => l.filter((x) => x !== f))} aria-label={`Remove ${f.name}`}><X size={12} /></button>
              </span>
            ))}
          </div>
        )}
      </div>

      {!lockIntent && <fieldset className="intents">
        <legend className="label">What should we do with them?</legend>
        {INTENTS.map(({ id, icon: Icon, title, text: t }) => {
          const disabled = id === 'continue' && extendable.length === 0;
          return (
            <label key={id} className="intent" data-checked={intent === id} data-disabled={disabled}>
              <input type="radio" name="intent" value={id} checked={intent === id} disabled={disabled} onChange={() => setIntent(id)} />
              <Icon size={18} aria-hidden="true" />
              <span className="intent-title">{title}</span>
              <span className="hint">{disabled ? 'Build a course first.' : t}</span>
            </label>
          );
        })}
      </fieldset>}

      {intent === 'continue' && !lockIntent && (
        <div className="field">
          <label htmlFor="hub-target">Course</label>
          <select id="hub-target" className="input" value={target} onChange={(e) => setTarget(e.target.value)}>
            {extendable.map((c) => <option key={c.id} value={c.id}>{c.title} ({c.class_count} classes)</option>)}
          </select>
        </div>
      )}

      <div className="field">
        <label htmlFor="hub-goal">{goalLabel}</label>
        <input id="hub-goal" className="input" value={goal} onChange={(e) => setGoal(e.target.value)} placeholder={goalHint} />
      </div>

      {intent === 'test_prep' && (
        <div className="field" style={{ maxWidth: 220 }}>
          <label htmlFor="hub-date">Exam date (optional)</label>
          <input id="hub-date" className="input" type="date" value={examDate} onChange={(e) => setExamDate(e.target.value)} />
        </div>
      )}

      <details className="hub-more">
        <summary>Paste notes, or set the number of classes</summary>
        <div className="stack" style={{ marginTop: 'var(--space-3)' }}>
          <div className="field">
            <label htmlFor="hub-text">Notes</label>
            <textarea id="hub-text" className="textarea" value={text} onChange={(e) => setText(e.target.value)}
              placeholder="Syllabus, lecture notes, a problem set…" />
          </div>
          <div className="btn-row" style={{ gap: 'var(--space-4)' }}>
            {(intent === 'learn' || intent === 'test_prep') && (
              <div className="field" style={{ width: 170 }}>
                <label htmlFor="hub-q">Diagnostic questions</label>
                <input id="hub-q" className="input num" type="number" min={4} max={15} value={questions} onChange={(e) => setQuestions(e.target.value)} />
              </div>
            )}
            <div className="field" style={{ width: 170 }}>
              <label htmlFor="hub-c">{{ continue: 'New classes', code: 'Chapters' }[intent] || 'Classes'}</label>
              <input id="hub-c" className="input num" type="number" min={1} max={12} value={classes} placeholder="Auto"
                onChange={(e) => setClasses(e.target.value)} />
            </div>
          </div>
        </div>
      </details>

      {intent !== 'code' && (
        <p className="hint">Every class comes with a lesson, simulation, quiz, practice, a Socratic tutor and a spoken lecture (in its More menu).</p>
      )}
      {error && <p className="notice notice-bad" role="alert">{error}</p>}
      <div className="btn-row">
        <button type="submit" className="btn btn-gold" disabled={!ready || Boolean(step)}>
          {step ? <><Loader2 size={16} className="spin" aria-hidden="true" /> {step}</>
            : { learn: 'Build my course', test_prep: 'Build my test prep', continue: 'Add the next classes', code: 'Open in the IDE' }[intent]}
        </button>
        {!enough && <span className="hint">Add a file, or write at least a sentence about what you want.</span>}
      </div>
    </form>
  );
}

export default function CoursesHome({ user, onOpenCourse, onCodePractice, initialPreset }) {
  const [courses, setCourses] = useState(null);
  const [preset, setPreset] = useState(initialPreset || null);
  const [creating, setCreating] = useState(Boolean(initialPreset));
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    api(`/api/users/${user.id}/courses`)
      .then((d) => { setCourses(d.courses || []); setError(null); })
      .catch((e) => setError(e.message));
  }, [user.id]);

  useEffect(() => { load(); }, [load]);
  useAgyEvents((evt) => { if (evt.type === 'COURSE_UPDATED') load(); });

  return (
    <div className="page page-wide">
      <div className="page-head">
        <div>
          <h1>My courses</h1>
          <p>Everything you study starts here. Each course remembers your diagnostic, your quiz scores and every class written for you.</p>
        </div>
        {!creating && (
          <button type="button" className="btn btn-gold" onClick={() => { setPreset(null); setCreating(true); }}>
            <Plus size={16} aria-hidden="true" /> New course
          </button>
        )}
      </div>

      {(creating || (courses && courses.length === 0)) && (
        <StudyHub userId={user.id} courses={courses || []} preset={preset} onOpened={onOpenCourse} onCodePractice={onCodePractice}
          onCancel={courses && courses.length ? () => setCreating(false) : undefined} />
      )}
      {error && <p className="notice notice-bad" role="alert">{error}</p>}
      {courses === null && !error && <p className="hint">Loading your courses…</p>}

      {courses && courses.length > 0 && (
        <>
          <h2 className="section-h">Your courses</h2>
          <div className="course-grid">
            {courses.map((c) => {
              const [label, cls] = STATUS[c.status] || [c.status, 'status-pending'];
              const pct = c.class_count ? Math.round((c.completed_count / c.class_count) * 100) : 0;
              const canExtend = !['planning', 'diagnostic_ready'].includes(c.status) && c.class_count > 0;
              return (
                <div key={c.id} className="course-card">
                  <div className="btn-row" style={{ gap: 'var(--space-2)' }}>
                    <span className={`status ${cls}`}>{label}</span>
                    {c.mode === 'test_prep' && (
                      <span className="status status-gold"><Target size={12} aria-hidden="true" /> Test prep{c.exam_date ? ` · ${formatDate(c.exam_date)}` : ''}</span>
                    )}
                  </div>
                  <h3><button type="button" className="card-link" onClick={() => onOpenCourse(c.id)}>{c.title}</button></h3>
                  {c.goal && c.goal !== c.title && <p className="hint">{c.goal}</p>}
                  <div className="meter" aria-hidden="true"><span style={{ width: `${pct}%` }} /></div>
                  <div className="meta">
                    <span>{c.class_count ? `${c.ready_count} of ${c.class_count} classes written` : 'Planning'}</span>
                    <span>{c.completed_count} completed</span>
                    {c.avg_score !== null && c.avg_score !== undefined && <span>Quiz average {Math.round(c.avg_score * 100)}%</span>}
                  </div>
                  <div className="btn-row" style={{ marginTop: 'auto' }}>
                    <button type="button" className="btn btn-primary btn-sm" onClick={() => onOpenCourse(c.id)}>Open</button>
                    {canExtend && (
                      <button type="button" className="btn btn-quiet btn-sm" onClick={() => { setCreating(true); setPreset({ intent: 'continue', courseId: c.id, at: Date.now() }); }}>
                        <ListPlus size={14} aria-hidden="true" /> Add materials
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

function formatDate(iso) {
  const d = new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
