import React, { useCallback, useEffect, useState } from 'react';
import { Loader2, ArrowRight, RefreshCw, Trash2, ListPlus, Target, CalendarRange, PenLine, Zap, Layers, Check, Eye, Undo2 } from 'lucide-react';
import Md, { MdInline } from './Md';
import { api, useAgyEvents } from '../lib/api';
import { STATUS, StudyHub } from './CoursesHome';
import LoadingPanel from './LoadingPanel';

const LETTERS = 'ABCDEFGH';
const CLASS_STATUS = {
  planned: ['Planned', 'status-planned'],
  pending: ['Waiting', 'status-pending'],
  generating: ['Writing now', 'status-working'],
  ready: ['Ready', 'status-ready'],
  error: ['Failed', 'status-error'],
};
const KIND_LABEL = { review: 'Unit review', midterm: 'Midterm review', final: 'Final review' };
const formatDay = (seconds) => new Date(seconds * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });

/** Semester classes in runs of the same week (falls back to unit), in syllabus order. */
function groupByWeek(classes) {
  const groups = [];
  for (const k of classes) {
    const meta = k.meta || {};
    const key = meta.week ? `w${meta.week}` : `u${meta.unit || ''}`;
    const last = groups[groups.length - 1];
    if (last && last.key === key) last.classes.push(k);
    else groups.push({ key, week: meta.week, unit: meta.unit, classes: [k] });
  }
  return groups;
}

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
  const planned = klass.status === 'planned';
  return (
    <form className="adjust-form" onSubmit={submit} style={{ gridColumn: '1 / -1' }}>
      <label htmlFor={`adj-${klass.seq}`} className="visually-hidden">How should class {klass.seq} change?</label>
      <input id={`adj-${klass.seq}`} className="input" value={text} onChange={(e) => setText(e.target.value)} autoFocus
        placeholder="e.g. easier, more worked examples, focus on vectors" />
      <button type="submit" className="btn btn-primary btn-sm" disabled={busy || !text.trim()}>{planned ? 'Save for this class' : 'Rewrite class'}</button>
      <button type="button" className="btn btn-quiet btn-sm" onClick={() => setOpen(false)}>Cancel</button>
      {error && <span className="hint" style={{ color: 'var(--bad)' }}>{error}</span>}
    </form>
  );
}

function JobProgress({ job }) {
  if (!job || job.status === 'done' || job.status === 'error') return null;
  return (
    <div className="panel">
      <LoadingPanel compact label={job.step || 'Working'} progress={job.progress || 0.05} log={job.log} />
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

/** One part of a sprint problem: steps open one per click; the answer shows after a checked attempt or the last step. */
function SprintPart({ courseId, seq, part, locked, onCourse }) {
  const [value, setValue] = useState('');
  const [unit, setUnit] = useState('');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const post = async (path, body) => {
    setBusy(true);
    setError(null);
    try {
      const res = await api(`/api/courses/${courseId}/classes/${seq}/${path}`, { method: 'POST', body });
      onCourse(res.course);
      return res;
    } catch (e) { setError(e.message); return null; }
    finally { setBusy(false); }
  };
  const check = async (e) => {
    e.preventDefault();
    const n = Number(value.replace(',', '.').trim());
    if (!value.trim() || !Number.isFinite(n)) { setError('Enter a number, e.g. 4.2 or 1.6e-19.'); return; }
    const res = await post('check', { part: part.id, value: n, unit });
    if (res) setResult(res.result);
  };
  const idBase = `sp-${seq}-${part.id}`;
  return (
    <div className="sprint-part">
      <div className="sprint-part-head">
        <span className="sprint-part-id" aria-hidden="true">({part.id})</span>
        <div className="sprint-part-prompt"><MdInline>{part.prompt}</MdInline></div>
        {part.solved && <span className="status status-ready"><Check size={12} aria-hidden="true" /> Done</span>}
      </div>
      {part.steps.length > 0 && (
        <ol className="sprint-steps">{part.steps.map((s, i) => <li key={i}><Md>{s}</Md></li>)}</ol>
      )}
      {!locked && part.revealed < part.stepCount && (
        <button type="button" className="btn btn-secondary btn-sm" disabled={busy}
          onClick={() => post('reveal', { part: part.id, step: part.revealed + 1 })}>
          <Eye size={14} aria-hidden="true" /> Show step {part.revealed + 1} of {part.stepCount}
        </button>
      )}
      {!locked && part.autoCheck && (
        <form className="sprint-check" onSubmit={check}>
          <div className="field">
            <label htmlFor={`${idBase}-v`}>Your answer</label>
            <input id={`${idBase}-v`} className="input num" inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor={`${idBase}-u`}>Unit</label>
            <input id={`${idBase}-u`} className="input" value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="e.g. m/s" />
          </div>
          <button type="submit" className="btn btn-primary btn-sm" disabled={busy || !value.trim()}>Check</button>
        </form>
      )}
      {!part.autoCheck && (
        <p className="hint">No automatic check for this part: it counts as done once you have worked through every step.</p>
      )}
      {result && <p className={`feedback ${result.correct ? 'ok' : 'bad'}`} role="status">{result.message}</p>}
      {'answer' in part ? (
        <p className="sprint-answer">Answer: <strong className="num">{part.answer}</strong>{part.unit ? ` ${part.unit}` : ''}</p>
      ) : part.autoCheck && !part.solved && (
        <p className="hint">Try it once to see the answer: it appears after your first check, right or wrong, or after the last step.</p>
      )}
      {error && <p className="hint" role="alert" style={{ color: 'var(--bad)' }}>{error}</p>}
    </div>
  );
}

function SprintDone({ course, busy, onAction }) {
  const s = course.sprint;
  return (
    <section className="panel sprint-done stack-sm" aria-labelledby="sprint-done-h" aria-live="polite">
      <h2 id="sprint-done-h"><Check size={18} aria-hidden="true" /> All {s.problems} problem{s.problems === 1 ? '' : 's'} done</h2>
      {s.cleared ? (
        <>
          <p>This sprint is hidden from My courses and will be deleted for good on {s.undoUntil ? formatDay(s.undoUntil) : 'its purge date'}.</p>
          <div className="btn-row">
            <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={() => onAction('keep')}>Keep in My courses</button>
            <button type="button" className="btn btn-quiet btn-sm" disabled={busy} onClick={() => onAction('restore')}>
              <Undo2 size={14} aria-hidden="true" /> Undo
            </button>
          </div>
        </>
      ) : s.autoCleanup ? (
        <div className="btn-row">
          <span>Back in My courses.</span>
          <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => onAction('keep')}>Keep it for good</button>
        </div>
      ) : <p>It stays in My courses.</p>}
    </section>
  );
}

/** Problem sprint: the primer, then each of the student's problems with its parts, steps and answer checks. */
function SprintDesk({ course, busy, renderClass, onCourse, onAction, onOpenTopic }) {
  const classes = course.classes || [];
  const problems = classes.filter((k) => k.meta?.kind === 'problem');
  const firstOpen = problems.find((k) => (k.meta?.sprint?.parts || []).some((p) => !p.solved));
  const [openSeq, setOpenSeq] = useState(firstOpen?.seq ?? problems[0]?.seq);
  const s = course.sprint || {};
  const locked = Boolean(s.cleared);
  return (
    <div className="stack sprint-desk">
      {s.complete && <SprintDone course={course} busy={busy} onAction={onAction} />}
      <p className="sprint-progress" aria-live="polite">{s.done || 0} of {s.problems || problems.length} problems done</p>
      {!locked && <ol className="syllabus">{classes.filter((k) => k.meta?.kind !== 'problem').map((k) => renderClass(k))}</ol>}
      <ol className="sprint-problems">
        {problems.map((k) => {
          const parts = k.meta?.sprint?.parts || [];
          const open = openSeq === k.seq;
          const [kl, kc] = CLASS_STATUS[k.status] || [k.status, 'status-pending'];
          return (
            <li key={k.id} className="sprint-problem panel">
              <button type="button" className="sprint-problem-head" aria-expanded={open} onClick={() => setOpenSeq(open ? null : k.seq)}>
                <span className="class-num">{String(k.meta?.problemIndex ?? k.seq).padStart(2, '0')}</span>
                <span className="sprint-problem-title">{k.title}</span>
                <span className="sprint-chips">
                  {k.status !== 'ready' && <span className={`status ${kc}`}>{kl}</span>}
                  {parts.map((p) => (
                    <span key={p.id} className="sprint-chip" data-solved={p.solved}
                      aria-label={`Part ${p.id}: ${p.solved ? 'done' : 'not done'}`}>{p.id}{p.solved ? ' ✓' : ''}</span>
                  ))}
                </span>
              </button>
              {open && (
                <div className="stack-sm sprint-problem-body">
                  {k.meta?.statement && <div className="sprint-statement"><Md>{k.meta.statement}</Md></div>}
                  {k.meta?.sprint?.given?.length > 0 && (
                    <ul className="sprint-given">{k.meta.sprint.given.map((g, i) => <li key={i}><MdInline>{`${g.symbol} = ${g.value}`}</MdInline></li>)}</ul>
                  )}
                  {k.status === 'ready' && k.topic_id && !locked && (
                    <div className="btn-row">
                      <button type="button" className="btn btn-quiet btn-sm" onClick={() => onOpenTopic(k.topic_id)}>
                        What you need for it <ArrowRight size={14} aria-hidden="true" />
                      </button>
                    </div>
                  )}
                  {parts.map((p) => <SprintPart key={p.id} courseId={course.id} seq={k.seq} part={p} locked={locked} onCourse={onCourse} />)}
                  {k.status === 'ready' && parts.length === 0 && <p className="hint">This problem has no steps to work through; open its lesson.</p>}
                  {k.status === 'error' && (
                    <div className="btn-row">
                      {k.error && <span className="hint" style={{ color: 'var(--bad)' }}>{k.error}</span>}
                      <button type="button" className="btn btn-secondary btn-sm" disabled={busy} onClick={() => onAction(`classes/${k.seq}/regenerate`)}>Retry</button>
                    </div>
                  )}
                  {k.meta?.sprint?.pitfalls?.length > 0 && (
                    <details className="sprint-pitfalls">
                      <summary>Common pitfalls</summary>
                      <ul>{k.meta.sprint.pitfalls.map((t, i) => <li key={i}><MdInline>{t}</MdInline></li>)}</ul>
                    </details>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export default function CourseView({ courseId, onOpenTopic, onBack }) {
  const [course, setCourse] = useState(null);
  const [graded, setGraded] = useState(null);
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const load = useCallback(() => {
    api(`/api/courses/${courseId}`).then((c) => { setCourse(c); setError(null); }).catch((e) => setError(e.message));
  }, [courseId]);

  useEffect(() => { load(); }, [load]);
  useAgyEvents((evt) => {
    if (evt.type === 'COURSE_UPDATED' && evt.payload.courseId === courseId) { load(); return; }
    if (evt.type !== 'JOB_UPDATE' || !course?.job_id || evt.payload.id !== course.job_id) return;
    const prev = course.job || {};
    // a new headline step or status can mean classes changed: reload; a log-only note just updates the job in place
    if (evt.payload.status !== prev.status || evt.payload.step !== prev.step) load();
    else setCourse((c) => (c && c.job ? { ...c, job: { ...c.job, progress: evt.payload.progress, log: evt.payload.log } } : c));
  });

  const act = async (path, method = 'POST') => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api(path, { method });
      if (method === 'DELETE') onBack();
      else setCourse(res?.course || res);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };

  if (error && !course) return <div className="page"><p className="notice notice-bad">{error}</p></div>;
  if (!course) return <LoadingPanel page label="Loading course…" />;

  const [label, cls] = STATUS[course.status] || [course.status, 'status-pending'];
  const classes = course.classes || [];
  const showSyllabus = classes.length > 0 && course.status !== 'diagnostic_ready';
  const jobBusy = course.job && ['queued', 'running'].includes(course.job.status);
  const isSprint = course.mode === 'problem_sprint';
  const canExtend = showSyllabus && !jobBusy && course.status !== 'planning' && !isSprint;
  const semester = course.mode === 'semester';
  const written = classes.filter((k) => k.status === 'ready').length;
  const nextPlanned = classes.find((k) => k.status === 'planned');
  const writing = classes.some((k) => ['pending', 'generating'].includes(k.status));

  const renderClass = (k, Title = 'h3') => {
    const [kl, kc] = CLASS_STATUS[k.status] || [k.status, 'status-pending'];
    const kind = KIND_LABEL[k.meta?.kind];
    return (
      <li key={k.id} className={`class-row${k.status === 'planned' ? ' is-planned' : ''}`}>
        <span className="class-num">{String(k.seq).padStart(2, '0')}</span>
        <div style={{ minWidth: 0 }}>
          <Title>{k.title}{kind && <span className={`sem-kind sem-kind-${k.meta.kind}`}>{kind}</span>}</Title>
          {k.objectives?.length > 0 && (
            <ul className="objectives">{k.objectives.slice(0, 3).map((o, i) => <li key={i}>{o}</li>)}</ul>
          )}
          {k.error && <p className="hint" style={{ color: 'var(--bad)' }}>{k.error}</p>}
          {k.adapted_from !== null && k.adapted_from !== undefined && (
            <p className="adapted">
              {k.status === 'planned' ? 'Will be written' : 'Rewritten'} {k.adapted_from < 0.5 ? 'with more support' : 'to be more challenging'} after your {Math.round(k.adapted_from * 100)}% on the previous quiz
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
          {(k.status === 'ready' || k.status === 'planned') && <AdjustClass courseId={courseId} klass={k} onDone={setCourse} />}
        </div>
      </li>
    );
  };

  return (
    <div className="page">
      <nav className="crumbs" aria-label="Breadcrumb"><button type="button" onClick={onBack}>My courses</button></nav>
      <div className="page-head">
        <div>
          <h1>{course.title}</h1>
          {course.goal && course.goal !== course.title && <p>{course.goal}</p>}
        </div>
        <div className="btn-row" style={{ gap: 'var(--space-2)' }}>
          {semester && (
            <span className="status status-gold"><CalendarRange size={12} aria-hidden="true" /> Semester{course.weeks ? ` · ${course.weeks} weeks` : ''}</span>
          )}
          {course.mode === 'test_prep' && (
            <span className="status status-gold"><Target size={12} aria-hidden="true" /> Test prep{course.exam_date ? ` · exam ${course.exam_date}` : ''}</span>
          )}
          {isSprint && (
            <span className="status status-gold"><Zap size={12} aria-hidden="true" /> Problem sprint{course.auto_cleanup ? '' : ' · kept'}</span>
          )}
          {course.mode === 'thematic_reference' && (
            <span className="status status-gold"><Layers size={12} aria-hidden="true" /> Like my problems</span>
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
      {course.status === 'error' && (
        <div className="notice notice-bad btn-row" style={{ justifyContent: 'space-between' }}>
          <span>{course.error || 'The course encountered an error.'}</span>
          <button type="button" className="btn btn-secondary btn-sm" disabled={busy || jobBusy} onClick={() => act(`/api/courses/${courseId}/resume`)}>
            <RefreshCw size={14} aria-hidden="true" /> {course.diagnostic?.length > 0 ? 'Resume' : 'Retry planning'}
          </button>
        </div>
      )}

      {course.status === 'diagnostic_ready' && <Diagnostic course={course} onSubmitted={(g) => { setGraded(g); load(); }} />}

      {showSyllabus && isSprint && (
        <SprintDesk course={course} busy={busy} renderClass={renderClass} onCourse={setCourse} onOpenTopic={onOpenTopic}
          onAction={(what) => act(`/api/courses/${courseId}/${what}`)} />
      )}
      {showSyllabus && !isSprint && (
        <div className="split">
          <section className="stack" aria-labelledby="classes-h">
            <h2 id="classes-h">Classes</h2>
            {semester && (
              <div className="sem-progress btn-row" aria-live="polite">
                <span>{written} of {classes.length} written{course.plannedCount ? ` · ${course.plannedCount} planned, written as you reach them` : ''}</span>
                {nextPlanned && (
                  <button type="button" className="btn btn-secondary btn-sm" disabled={writing}
                    title={writing ? 'A class is being written right now' : `Write class ${nextPlanned.seq} without waiting`}
                    onClick={() => act(`/api/courses/${courseId}/classes/${nextPlanned.seq}/generate`)}>
                    <PenLine size={14} aria-hidden="true" /> Write next class now
                  </button>
                )}
              </div>
            )}
            {semester ? groupByWeek(classes).map((g) => (
              <section key={`${g.key}-${g.classes[0].seq}`} className="sem-week stack-sm">
                <h3 className="sem-week-h">{g.week ? `Week ${g.week}` : 'Unit'}{g.unit ? ` · ${g.unit}` : ''}</h3>
                <ol className="syllabus" start={g.classes[0].seq}>{g.classes.map((k) => renderClass(k, 'h4'))}</ol>
              </section>
            )) : (
              <ol className="syllabus">{classes.map((k) => renderClass(k))}</ol>
            )}
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
