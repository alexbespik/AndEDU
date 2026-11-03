import React, { useCallback, useEffect, useState } from 'react';
import { Loader2, ArrowRight, RefreshCw, Trash2, ListPlus, Target } from 'lucide-react';
import Md, { MdInline } from './Md';
import { api, useAgyEvents } from '../lib/api';
import { STATUS, StudyHub } from './CoursesHome';

const LETTERS = 'ABCDEFGH';
const CLASS_STATUS = {
  pending: ['Waiting', 'status-pending'],
  generating: ['Writing now', 'status-working'],
  ready: ['Ready', 'status-ready'],
  error: ['Failed', 'status-error'],
};

function AdjustClass({ courseId, klass, onDone }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  if (!open) {
    return <button type="button" className="btn btn-quiet btn-sm" onClick={() => setOpen(true)}>Adjust</button>;
  }
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onDone(await api(`/api/courses/${courseId}/classes/${klass.seq}/regenerate`, { method: 'POST', body: { instruction: text } }));
      setOpen(false);
      setText('');
    } catch (err) { setError(err.message); }
    setBusy(false);
  };
  return (
    <form className="adjust-form" onSubmit={submit} style={{ gridColumn: '1 / -1' }}>
      <label htmlFor={`adj-${klass.seq}`} className="visually-hidden">How should class {klass.seq} change?</label>
      <input id={`adj-${klass.seq}`} className="input" value={text} onChange={(e) => setText(e.target.value)} autoFocus
        placeholder="e.g. easier, more worked examples, focus on vectors" />
      <button type="submit" className="btn btn-primary btn-sm" disabled={busy || !text.trim()}>Rewrite class</button>
      <button type="button" className="btn btn-quiet btn-sm" onClick={() => setOpen(false)}>Cancel</button>
      {error && <span className="hint" style={{ color: 'var(--bad)' }}>{error}</span>}
    </form>
  );
}

function JobProgress({ job }) {
  if (!job || job.status === 'done') return null;
  if (job.status === 'error') return <p className="notice notice-bad">{job.error}</p>;
  return (
    <div className="panel stack-sm" aria-live="polite">
      <p><Loader2 size={16} className="spin" aria-hidden="true" /> {job.step || 'Working'}</p>
      <div className="meter gold" aria-hidden="true"><span style={{ width: `${Math.round((job.progress || 0.05) * 100)}%` }} /></div>
    </div>
  );
}

function Diagnostic({ course, onSubmitted }) {
  const [answers, setAnswers] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const qs = course.diagnostic || [];
  const answered = Object.keys(answers).length;

  const submit = async (skip = false) => {
    setBusy(true);
    setError(null);
    try {
      const res = skip
        ? { graded: null, course: await api(`/api/courses/${course.id}/skip-diagnostic`, { method: 'POST' }) }
        : await api(`/api/courses/${course.id}/diagnostic`, { method: 'POST', body: { answers } });
      onSubmitted(res.graded);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  };

  return (
    <section className="stack" aria-labelledby="diag-h">
      <div className="stack-sm">
        <h2 id="diag-h">Diagnostic quiz</h2>
        <p>{qs.length} questions. Answer what you can and skip what you don't know: wrong and blank answers decide what your classes focus on.</p>
      </div>
      {qs.map((q, n) => (
        <fieldset key={q.id} className="panel stack-sm" style={{ margin: 0 }}>
          <legend className="hint" style={{ padding: 0 }}>Question {n + 1}</legend>
          <div className="question"><Md>{q.question}</Md></div>
          <div className="choices">
            {q.options.map((opt, i) => (
              <button key={i} type="button" className="choice" aria-pressed={answers[q.id] === i}
                onClick={() => setAnswers((a) => ({ ...a, [q.id]: i }))}>
                <span className="key">{LETTERS[i]}</span><span><MdInline>{opt}</MdInline></span><span />
              </button>
            ))}
          </div>
        </fieldset>
      ))}
      {error && <p className="notice notice-bad" role="alert">{error}</p>}
      <div className="btn-row">
        <button type="button" className="btn btn-primary" disabled={busy || answered === 0} onClick={() => submit(false)}>
          {busy ? 'Grading…' : `Submit ${answered} of ${qs.length} answers`}
        </button>
        <button type="button" className="btn btn-quiet" disabled={busy} onClick={() => submit(true)}>Skip the diagnostic</button>
      </div>
    </section>
  );
}

function Mastery({ course }) {
  const m = course.mastery || {};
  const rows = (course.concepts || []).filter((c) => m[c.id]?.total);
  if (!rows.length) return null;
  return (
    <section className="panel stack-sm" aria-labelledby="mastery-h">
      <h2 id="mastery-h">What the diagnostic showed</h2>
      {rows.map((c) => {
        const s = m[c.id];
        const pct = Math.round((s.score || 0) * 100);
        return (
          <div key={c.id} className="stack-sm" style={{ gap: 4 }}>
            <div className="btn-row" style={{ justifyContent: 'space-between' }}>
              <span>{c.name}</span>
              <span className="num">{s.correct}/{s.total}</span>
            </div>
            <div className={`meter${pct < 75 ? ' gold' : ''}`} aria-label={`${c.name}: ${pct}%`}><span style={{ width: `${pct}%` }} /></div>
          </div>
        );
      })}
      <p className="hint">Gold bars are the concepts your classes spend the most time on.</p>
    </section>
  );
}

function Graded({ graded, course }) {
  if (!graded) return null;
  const right = graded.filter((g) => g.selected === g.correctAnswer).length;
  return (
    <details className="panel">
      <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Diagnostic answers: {right} of {graded.length} correct</summary>
      <div className="stack-sm" style={{ marginTop: 'var(--space-3)' }}>
        {graded.map((g, i) => {
          const q = (course.diagnostic || []).find((x) => x.id === g.id);
          return (
            <div key={g.id} className={`feedback ${g.selected === g.correctAnswer ? 'ok' : 'bad'}`}>
              <p style={{ fontWeight: 600 }}>{i + 1}. {g.selected === g.correctAnswer ? 'Correct' : `Answer: ${LETTERS[g.correctAnswer]}`}</p>
              {q && <Md>{q.question}</Md>}
              {g.explanation && <Md>{g.explanation}</Md>}
            </div>
          );
        })}
      </div>
    </details>
  );
}

export default function CourseView({ courseId, onOpenTopic, onBack }) {
  const [course, setCourse] = useState(null);
  const [graded, setGraded] = useState(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const load = useCallback(() => {
    api(`/api/courses/${courseId}`).then((c) => { setCourse(c); setError(null); }).catch((e) => setError(e.message));
  }, [courseId]);

  useEffect(() => { load(); }, [load]);
  useAgyEvents((evt) => {
    if ((evt.type === 'COURSE_UPDATED' && evt.payload.courseId === courseId) ||
        (evt.type === 'JOB_UPDATE' && course?.job_id && evt.payload.id === course.job_id)) load();
  });

  const act = async (path, method = 'POST') => {
    setError(null);
    try {
      const res = await api(path, { method });
      if (method === 'DELETE') onBack();
      else setCourse(res);
    } catch (e) { setError(e.message); }
  };

  if (error && !course) return <div className="page"><p className="notice notice-bad">{error}</p></div>;
  if (!course) return <div className="page"><p className="hint">Loading course…</p></div>;

  const [label, cls] = STATUS[course.status] || [course.status, 'status-pending'];
  const classes = course.classes || [];
  const showSyllabus = classes.length > 0 && course.status !== 'diagnostic_ready';
  const jobBusy = course.job && ['queued', 'running'].includes(course.job.status);
  const canExtend = showSyllabus && !jobBusy && course.status !== 'planning';

  return (
    <div className="page">
      <nav className="crumbs" aria-label="Breadcrumb"><button type="button" onClick={onBack}>My courses</button></nav>
      <div className="page-head">
        <div>
          <h1>{course.title}</h1>
          {course.goal && course.goal !== course.title && <p>{course.goal}</p>}
        </div>
        <div className="btn-row" style={{ gap: 'var(--space-2)' }}>
          {course.mode === 'test_prep' && (
            <span className="status status-gold"><Target size={12} aria-hidden="true" /> Test prep{course.exam_date ? ` · exam ${course.exam_date}` : ''}</span>
          )}
          <span className={`status ${cls}`}>{label}</span>
          {canExtend && (
            <button type="button" className="btn btn-secondary btn-sm" aria-expanded={adding} onClick={() => setAdding((a) => !a)}>
              <ListPlus size={14} aria-hidden="true" /> {adding ? 'Close' : 'Add materials'}
            </button>
          )}
        </div>
      </div>
      {adding && canExtend && (
        <StudyHub lockIntent courses={[{ ...course, class_count: classes.length }]} preset={{ intent: 'continue', courseId }}
          onOpened={() => { setAdding(false); load(); }} />
      )}

      <JobProgress job={course.job} />
      {course.status === 'error' && course.error && (
        <div className="notice notice-bad btn-row" style={{ justifyContent: 'space-between' }}>
          <span>{course.error}</span>
          {course.diagnostic?.length > 0 && (
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => act(`/api/courses/${courseId}/resume`)}>
              <RefreshCw size={14} aria-hidden="true" /> Resume
            </button>
          )}
        </div>
      )}

      {course.status === 'diagnostic_ready' && <Diagnostic course={course} onSubmitted={(g) => { setGraded(g); load(); }} />}

      {showSyllabus && (
        <div className="split">
          <section className="stack" aria-labelledby="classes-h">
            <h2 id="classes-h">Classes</h2>
            <ol className="syllabus">
              {classes.map((k) => {
                const [kl, kc] = CLASS_STATUS[k.status] || [k.status, 'status-pending'];
                return (
                  <li key={k.id} className="class-row">
                    <span className="class-num">{String(k.seq).padStart(2, '0')}</span>
                    <div style={{ minWidth: 0 }}>
                      <h3>{k.title}</h3>
                      {k.objectives?.length > 0 && (
                        <ul className="objectives">{k.objectives.slice(0, 3).map((o, i) => <li key={i}>{o}</li>)}</ul>
                      )}
                      {k.error && <p className="hint" style={{ color: 'var(--bad)' }}>{k.error}</p>}
                      {k.adapted_from !== null && k.adapted_from !== undefined && (
                        <p className="adapted">
                          Rewritten {k.adapted_from < 0.5 ? 'with more support' : 'to be more challenging'} after your {Math.round(k.adapted_from * 100)}% on the previous quiz
                        </p>
                      )}
                      {k.instruction && (k.adapted_from === null || k.adapted_from === undefined) && (
                        <p className="adapted">Adjusted: {k.instruction}</p>
                      )}
                    </div>
                    <div className="class-actions">
                      {k.score !== null && k.score !== undefined && <span className="num hint">{Math.round(k.score * 100)}%</span>}
                      <span className={`status ${kc}`}>{k.status === 'generating' && <Loader2 size={12} className="spin" aria-hidden="true" />}{kl}</span>
                      {k.status === 'ready' && k.topic_id && (
                        <button type="button" className="btn btn-primary btn-sm" onClick={() => onOpenTopic(k.topic_id)}>
                          Open <ArrowRight size={14} aria-hidden="true" />
                        </button>
                      )}
                      {k.status === 'error' && (
                        <button type="button" className="btn btn-secondary btn-sm" onClick={() => act(`/api/courses/${courseId}/classes/${k.seq}/regenerate`)}>Retry</button>
                      )}
                      {k.status === 'ready' && <AdjustClass courseId={courseId} klass={k} onDone={setCourse} />}
                    </div>
                  </li>
                );
              })}
            </ol>
          </section>
          <div className="stack">
            <Mastery course={course} />
            <Graded graded={graded} course={course} />
          </div>
        </div>
      )}

      {error && <p className="notice notice-bad" role="alert">{error}</p>}

      <div className="btn-row" style={{ marginTop: 'var(--space-5)' }}>
        {!confirmDelete ? (
          <button type="button" className="btn btn-danger btn-sm" onClick={() => setConfirmDelete(true)}>
            <Trash2 size={14} aria-hidden="true" /> Delete course
          </button>
        ) : (
          <>
            <span>Delete this course and all {classes.length} of its classes?</span>
            <button type="button" className="btn btn-danger btn-sm" onClick={() => act(`/api/courses/${courseId}`, 'DELETE')}>Delete</button>
            <button type="button" className="btn btn-quiet btn-sm" onClick={() => setConfirmDelete(false)}>Keep it</button>
          </>
        )}
      </div>
    </div>
  );
}
