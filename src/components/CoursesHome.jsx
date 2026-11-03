import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Plus, Upload, X, Loader2 } from 'lucide-react';
import { api, uploadFiles, useAgyEvents } from '../lib/api';

export const STATUS = {
  planning: ['Writing diagnostic', 'status-working'],
  diagnostic_ready: ['Diagnostic ready', 'status-working'],
  generating: ['Writing classes', 'status-working'],
  ready: ['Ready', 'status-ready'],
  error: ['Needs attention', 'status-error'],
};

function NewCourse({ userId, onCreated, onCancel }) {
  const [goal, setGoal] = useState('');
  const [text, setText] = useState('');
  const [files, setFiles] = useState([]);
  const [over, setOver] = useState(false);
  const [questions, setQuestions] = useState(8);
  const [classes, setClasses] = useState('');
  const [step, setStep] = useState(null);
  const [error, setError] = useState(null);
  const pickerRef = useRef(null);

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
      setStep('Starting your course');
      const { course } = await api('/api/courses', {
        method: 'POST',
        body: { userId, goal: goal.trim(), materials_text: materials, filenames: files.map((f) => f.name),
                num_questions: Number(questions), class_count: classes ? Number(classes) : null },
      });
      onCreated(course.id);
    } catch (err) {
      setError(err.message);
      setStep(null);
    }
  };

  const ready = goal.trim().length + text.trim().length >= 20 || files.length > 0;

  return (
    <form className="panel stack" onSubmit={submit} aria-labelledby="new-course-h">
      <div className="page-head" style={{ alignItems: 'center' }}>
        <h2 id="new-course-h">New course</h2>
        <button type="button" className="btn btn-quiet btn-sm" onClick={onCancel}>Cancel</button>
      </div>

      <div className="field">
        <label htmlFor="nc-goal">What do you want to learn?</label>
        <input id="nc-goal" className="input" value={goal} onChange={(e) => setGoal(e.target.value)}
          placeholder="e.g. Rotational dynamics for my Physics 101 midterm" />
      </div>

      <div className="field">
        <span className="label" id="nc-files-l">Materials</span>
        <div className="dropzone" data-over={over} aria-labelledby="nc-files-l"
          onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); addFiles(e.dataTransfer.files); }}>
          <button type="button" className="btn btn-secondary" onClick={() => pickerRef.current?.click()}>
            <Upload size={16} aria-hidden="true" /> Choose files
          </button>
          <span className="hint">or drop them here: PDF, DOCX, notebooks, text, images of notes</span>
          <input ref={pickerRef} type="file" multiple hidden accept=".pdf,.docx,.ipynb,.txt,.md,.py,.csv,.json,.png,.jpg,.jpeg,.webp"
            onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }} />
        </div>
        {files.length > 0 && (
          <div className="file-chips">
            {files.map((f) => (
              <span key={f.name} className="chip">{f.name}
                <button type="button" className="btn btn-quiet btn-sm btn-icon" style={{ minHeight: 22, width: 22, border: 0 }}
                  onClick={() => setFiles((l) => l.filter((x) => x !== f))} aria-label={`Remove ${f.name}`}><X size={12} /></button>
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="field">
        <label htmlFor="nc-text">Or paste notes</label>
        <textarea id="nc-text" className="textarea" value={text} onChange={(e) => setText(e.target.value)}
          placeholder="Syllabus, lecture notes, a problem set…" />
      </div>

      <div className="btn-row" style={{ gap: 'var(--space-4)' }}>
        <div className="field" style={{ width: 170 }}>
          <label htmlFor="nc-q">Diagnostic questions</label>
          <input id="nc-q" className="input num" type="number" min={4} max={15} value={questions} onChange={(e) => setQuestions(e.target.value)} />
        </div>
        <div className="field" style={{ width: 170 }}>
          <label htmlFor="nc-c">Classes</label>
          <input id="nc-c" className="input num" type="number" min={2} max={12} value={classes} placeholder="Auto"
            onChange={(e) => setClasses(e.target.value)} />
        </div>
      </div>

      {error && <p className="notice notice-bad" role="alert">{error}</p>}
      <div className="btn-row">
        <button type="submit" className="btn btn-primary" disabled={!ready || Boolean(step)}>
          {step ? <><Loader2 size={16} className="spin" aria-hidden="true" /> {step}</> : 'Build my course'}
        </button>
        {!ready && <span className="hint">Add a file, or write at least a sentence about your goal.</span>}
      </div>
    </form>
  );
}

export default function CoursesHome({ user, onOpenCourse }) {
  const [courses, setCourses] = useState(null);
  const [creating, setCreating] = useState(false);
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
          <h1>Your courses</h1>
          <p>Each course remembers your diagnostic, your quiz scores and every class written for you.</p>
        </div>
        {!creating && (
          <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
            <Plus size={16} aria-hidden="true" /> New course
          </button>
        )}
      </div>

      {creating && <NewCourse userId={user.id} onCancel={() => setCreating(false)} onCreated={(id) => { setCreating(false); onOpenCourse(id); }} />}
      {error && <p className="notice notice-bad" role="alert">{error}</p>}
      {courses === null && !error && <p className="hint">Loading your courses…</p>}

      {courses && courses.length === 0 && !creating && (
        <div className="panel stack-sm">
          <h2>No courses yet</h2>
          <p>Start with the materials for something you're studying. Your first diagnostic takes about a minute to write.</p>
          <div className="btn-row"><button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>Build my first course</button></div>
        </div>
      )}

      {courses && courses.length > 0 && (
        <div className="course-grid">
          {courses.map((c) => {
            const [label, cls] = STATUS[c.status] || [c.status, 'status-pending'];
            const pct = c.class_count ? Math.round((c.completed_count / c.class_count) * 100) : 0;
            return (
              <button key={c.id} type="button" className="course-card" onClick={() => onOpenCourse(c.id)}>
                <span className={`status ${cls}`}>{label}</span>
                <h3>{c.title}</h3>
                {c.goal && c.goal !== c.title && <p className="hint">{c.goal}</p>}
                <div className="meter" aria-hidden="true"><span style={{ width: `${pct}%` }} /></div>
                <div className="meta">
                  <span>{c.class_count ? `${c.ready_count} of ${c.class_count} classes written` : 'Planning'}</span>
                  <span>{c.completed_count} completed</span>
                  {c.avg_score !== null && c.avg_score !== undefined && <span>Quiz average {Math.round(c.avg_score * 100)}%</span>}
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
