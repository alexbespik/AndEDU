import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Upload, X, Loader2, BookOpen, Target, ListPlus, Code2, Plus, Folder, ChevronDown, ChevronRight, CalendarRange, Zap, Layers } from 'lucide-react';
import { api, uploadFiles, useAgyEvents } from '../lib/api';
import { confirmGeminiUpload, handleUploadConsentError } from '../lib/consent';
import { disambiguateFile } from '../lib/files';
import TodayPanel from './TodayPanel';
import LoadingPanel from './LoadingPanel';

export const STATUS = {
  planning: ['Writing diagnostic', 'status-working'],
  diagnostic_ready: ['Diagnostic ready', 'status-working'],
  generating: ['Writing classes', 'status-working'],
  ready: ['Ready', 'status-ready'],
  error: ['Needs attention', 'status-error'],
  cleared: ['Finished', 'status-ready'],
};

const INTENTS = [
  { id: 'learn', icon: BookOpen, title: 'Learn it', text: 'A diagnostic, then a sequence of classes built around your gaps.' },
  { id: 'test_prep', icon: Target, title: 'Prepare for a test', text: 'Exam-focused review classes, exam-style quizzes and a final mock exam.' },
  { id: 'semester', icon: CalendarRange, title: 'Semester plan', text: 'A whole term planned week by week, with unit reviews; each class is written as you reach it.' },
  { id: 'problem_sprint', icon: Zap, title: 'Problem sprint: explain my problems', text: 'A short course: what you need, then each of your problems step by step. Removed when you finish, unless you keep it.' },
  { id: 'thematic_reference', icon: Layers, title: 'Practice like my problems (reference only)', text: 'New problems on the same topic, at the same level and format. Yours are never copied or solved.' },
  { id: 'continue', icon: ListPlus, title: 'Continue a course', text: 'New materials become the next classes of a course you already have.' },
  { id: 'code', icon: Code2, title: 'Coding practice', text: 'Hands-on exercises in the IDE: fill-in slots, block ordering and code you run.' },
];

const DEPT_ALIASES = {
  physics: 'PHYS',
  chemistry: 'CHEM',
  math: 'MATH',
  mathematics: 'MATH',
  biology: 'BIOL',
  'computer science': 'CS',
  computing: 'CS',
  history: 'HIST',
  languages: 'LANG',
  linguistics: 'LING',
};

const SORTED_DEPT_ENTRIES = Object.entries(DEPT_ALIASES).sort((a, b) => b[0].length - a[0].length);

const STOP_WORDS = new Set([
  'IN', 'TO', 'FOR', 'AND', 'THE', 'FROM', 'WITH', 'FALL', 'SPRING', 'SUMMER', 'WINTER', 'TERM', 'YEAR', 'PART', 'UNIT', 'WEEK', 'CLASS'
]);

function getCourseFolder(course) {
  if (!course) return 'General';

  const title = (course.title || '').trim();
  const goal = (course.goal || '').trim();
  const text = `${title} ${goal}`.trim();

  // 1. Natural written-out department names with course number (e.g. "Physics 101", "Computer Science 204")
  for (const [deptName, code] of SORTED_DEPT_ENTRIES) {
    const escaped = deptName.replace(/\s+/g, '\\s+');
    const m = text.match(new RegExp(`\\b${escaped}\\s*[-_]?\\s*(\\d{2,4}[A-Za-z]?)\\b`, 'i'));
    if (m) {
      return `${code} ${m[1].toUpperCase()}`;
    }
  }

  // 2. Standard course code regex (e.g. "PHYS 101", "CS-101", "MATH_211")
  const codeMatches = text.matchAll(/\b([A-Za-z]{2,5})\s*[-_]?\s*(\d{2,4}[A-Za-z]?)\b/g);
  for (const match of codeMatches) {
    const rawDept = match[1];
    const deptLower = rawDept.toLowerCase();
    const num = match[2].toUpperCase();

    // If dept is in alias map, e.g. "chem 101", accept it
    if (DEPT_ALIASES[deptLower]) {
      return `${DEPT_ALIASES[deptLower]} ${num}`;
    }

    // Otherwise require uppercase code (e.g. "PHYS 101", "CS 101", "BIOL 201")
    // And ignore calendar years (1900-2099) and stop-words (e.g. "in 2024", "to 1918", "Fall 2023")
    if (rawDept === rawDept.toUpperCase() && !STOP_WORDS.has(rawDept)) {
      if (!/^(19|20)\d{2}$/.test(num)) {
        return `${rawDept} ${num}`;
      }
    }
  }

  // 3. Fallback to course.subject or course.workspace mapping if code is missing
  const subj = (course.subject || '').trim().toLowerCase();
  if (subj) {
    if (DEPT_ALIASES[subj]) return DEPT_ALIASES[subj];
    return course.subject.trim().charAt(0).toUpperCase() + course.subject.trim().slice(1);
  }

  const ws = (course.workspace || '').trim().toLowerCase();
  if (ws) {
    if (DEPT_ALIASES[ws]) return DEPT_ALIASES[ws];
    return course.workspace.trim().charAt(0).toUpperCase() + course.workspace.trim().slice(1);
  }

  // Check if department name alone is mentioned in text
  for (const [deptName, code] of SORTED_DEPT_ENTRIES) {
    const escaped = deptName.replace(/\s+/g, '\\s+');
    if (new RegExp(`\\b${escaped}\\b`, 'i').test(text)) {
      return code;
    }
  }

  return 'General';
}

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
  const [weeks, setWeeks] = useState(15);
  const [keepSprint, setKeepSprint] = useState(false);  // unchecked: the sprint clears itself once every problem is done
  const [step, setStep] = useState(null);
  const [error, setError] = useState(null);
  const pickerRef = useRef(null);
  const rootRef = useRef(null);
  const detailsRef = useRef(null);

  // courses that can take more classes: set up, not mid-planning
  const extendable = courses.filter((c) => !['planning', 'diagnostic_ready'].includes(c.status) && c.class_count > 0 && c.mode !== 'problem_sprint');

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

  const addFiles = useCallback((list) => {
    if (!list || !list.length) return;
    setFiles((prev) => {
      const updated = [...prev];
      for (const item of Array.from(list)) {
        const file = disambiguateFile(item, updated);
        updated.push(file);
      }
      return updated;
    });
  }, []);

  useEffect(() => {
    const handlePaste = (e) => {
      const target = e.target;
      const isEditable = target?.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target?.tagName);
      const clipboardFiles = e.clipboardData?.files ? Array.from(e.clipboardData.files) : [];
      if (clipboardFiles.length > 0) {
        e.preventDefault();
        addFiles(clipboardFiles);
        return;
      }
      if (!isEditable) {
        const pastedText = e.clipboardData?.getData('text/plain')?.trim();
        if (pastedText) {
          e.preventDefault();
          setText((prev) => (prev ? `${prev}\n\n${pastedText}` : pastedText));
          if (detailsRef.current) detailsRef.current.open = true;
        }
      }
    };
    window.addEventListener('paste', handlePaste);
    return () => window.removeEventListener('paste', handlePaste);
  }, [addFiles]);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      let materials = text.trim();
      if (files.length) {
        if (!(await confirmGeminiUpload(files, { anyFile: true }))) return;  // their text plans the course via Gemini
        setStep(`Reading ${files.length} file${files.length > 1 ? 's' : ''}`);
        const up = await uploadFiles(files);
        materials = [up.extracted_text, materials].filter(Boolean).join('\n\n');
      }
      const base = { goal: goal.trim(), materials_text: materials, filenames: files.map((f) => f.name || f._displayName || 'uploaded_file'),
                     class_count: classes ? Number(classes) : null };
      if (intent === 'code') {
        onCodePractice({ topic: goal.trim(), text: materials, chapters: classes ? Number(classes) : null,
                         files: files.map((f) => f.name || f._displayName || 'uploaded_file'), at: Date.now() });
        return;
      }
      if (intent === 'continue') {
        setStep('Planning the next classes');
        await api(`/api/courses/${target}/extend`, { method: 'POST', body: base });
        onOpened(target);
      } else {
        setStep({ test_prep: 'Starting your test prep', semester: 'Planning your semester', problem_sprint: 'Finding your problems' }[intent] || 'Starting your course');
        const semesterWeeks = Math.min(Math.max(Number(weeks) || 15, 1), 20);
        const { course } = await api('/api/courses', {
          method: 'POST',
          body: { ...base, userId, num_questions: Number(questions), mode: intent, exam_date: intent === 'test_prep' ? examDate || null : null,
                  ...(intent === 'semester' ? { weeks: semesterWeeks, class_count: classes ? Number(classes) : Math.min(30, semesterWeeks * 2) } : {}),
                  ...(intent === 'problem_sprint' ? { keep: keepSprint, class_count: null } : {}) },
        });
        onOpened(course.id);
      }
    } catch (err) {
      setError(handleUploadConsentError(err));
      setStep(null);
    }
  };

  const enough = goal.trim().length + text.trim().length >= 20 || files.length > 0;
  const ready = enough && (intent !== 'continue' || target);
  const goalLabel = { learn: 'What do you want to learn?', test_prep: 'Which test, and what does it cover?', semester: 'Which course are you taking this term?',
                      problem_sprint: 'Which problems should be explained?', thematic_reference: 'What should the practice cover?',
                      continue: 'What should the next classes cover?', code: 'What do you want to practise coding?' }[intent];
  const goalHint = { learn: 'e.g. Rotational dynamics for Physics 101', test_prep: 'e.g. Chem 121 final: stoichiometry, gases, thermochemistry',
                     semester: 'e.g. PHYS 101 this fall, using the attached syllabus',
                     problem_sprint: 'e.g. Problems 2-5 of the attached homework', thematic_reference: 'e.g. Problems like these, for practice before the quiz',
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
        tabIndex={0}
        role="region"
        aria-label="File upload dropzone"
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            pickerRef.current?.click();
          }
        }}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); addFiles(e.dataTransfer.files); }}>
        <Upload size={22} aria-hidden="true" className="dz-icon" />
        <div className="stack-sm" style={{ flex: 1, minWidth: 200 }}>
          <strong>Drop files here, or paste (Ctrl+V / ⌘V)</strong>
          <span className="hint">PDF, DOCX, notebooks, text, or photos of handwritten notes</span>
        </div>
        <button type="button" className="btn btn-secondary" onClick={() => pickerRef.current?.click()}>Choose files</button>
        <input ref={pickerRef} type="file" multiple hidden accept=".pdf,.docx,.ipynb,.txt,.md,.py,.csv,.json,.png,.jpg,.jpeg,.webp"
          onChange={(e) => { addFiles(e.target.files); e.target.value = ''; }} />
        {files.length > 0 && (
          <div className="file-chips" style={{ flexBasis: '100%' }}>
            {files.map((f) => (
              <span key={f.uid || f.name} className="chip">{f.name}
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

      {!lockIntent && files.length > 0 && intent !== 'continue' && intent !== 'code' && (
        <div className="sprint-switch" role="group" aria-labelledby="sprint-switch-h">
          <span id="sprint-switch-h" className="label">These files are problems I have to solve:</span>
          <div className="sprint-switch-opts">
            <button type="button" className="btn btn-sm" aria-pressed={intent === 'problem_sprint'} onClick={() => setIntent('problem_sprint')}>
              <Zap size={14} aria-hidden="true" /> Explain these problems
            </button>
            <button type="button" className="btn btn-sm" aria-pressed={intent === 'thematic_reference'} onClick={() => setIntent('thematic_reference')}>
              <Layers size={14} aria-hidden="true" /> Use as reference only
            </button>
          </div>
        </div>
      )}

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

      {intent === 'semester' && (
        <div className="field sem-weeks">
          <label htmlFor="hub-weeks">Weeks in the term</label>
          <input id="hub-weeks" className="input num" type="number" min={1} max={20} value={weeks} onChange={(e) => setWeeks(e.target.value)}
            aria-describedby="hub-weeks-hint" />
          <span id="hub-weeks-hint" className="hint">About 2 classes a week, up to 30. Only the next class or two are written at a time.</span>
        </div>
      )}

      {intent === 'problem_sprint' && (
        <div className="stack-sm sprint-form">
          <label className="sprint-keep">
            <input type="checkbox" checked={keepSprint} onChange={(e) => setKeepSprint(e.target.checked)} />
            <span>Keep in My courses after I finish</span>
          </label>
          <span className="hint">{keepSprint ? 'The sprint stays in My courses.'
            : 'Unchecked: once every problem is done the sprint is hidden, and deleted for good a few days later (the date shows when you finish; you can undo until then).'}</span>
          <p className="hint sprint-honesty">Use it to understand your own work: steps open one at a time, and each answer shows only after you try.</p>
          <p className="hint sprint-honesty">For graded work you must follow your school's honor code and your instructor's rules on outside help.</p>
          <p className="hint">The problems found in your files become the classes straight away; there is no diagnostic.</p>
        </div>
      )}
      {intent === 'thematic_reference' && (
        <p className="hint sprint-honesty">Your files only set the topic, level and kind of assignment: every problem is written new, and practice that repeats your files' wording is removed.</p>
      )}

      <details className="hub-more" ref={detailsRef}>
        <summary>Paste notes, or set the number of classes</summary>
        <div className="stack" style={{ marginTop: 'var(--space-3)' }}>
          <div className="field">
            <label htmlFor="hub-text">Notes</label>
            <textarea id="hub-text" className="textarea" value={text} onChange={(e) => setText(e.target.value)}
              placeholder="Syllabus, lecture notes, a problem set…" />
          </div>
          <div className="btn-row" style={{ gap: 'var(--space-4)' }}>
            {(intent === 'learn' || intent === 'test_prep' || intent === 'semester' || intent === 'thematic_reference') && (
              <div className="field" style={{ width: 170 }}>
                <label htmlFor="hub-q">Diagnostic questions</label>
                <input id="hub-q" className="input num" type="number" min={4} max={15} value={questions} onChange={(e) => setQuestions(e.target.value)} />
              </div>
            )}
            {intent !== 'problem_sprint' && <div className="field" style={{ width: 170 }}>
              <label htmlFor="hub-c">{{ continue: 'New classes', code: 'Chapters' }[intent] || 'Classes'}</label>
              <input id="hub-c" className="input num" type="number" min={1} max={intent === 'semester' ? 30 : 12} value={classes} placeholder="Auto"
                onChange={(e) => setClasses(e.target.value)} />
            </div>}
          </div>
        </div>
      </details>

      {intent !== 'code' && intent !== 'problem_sprint' && (
        <p className="hint">Every class comes with a lesson, simulation, quiz, practice, a Socratic tutor and a spoken lecture (in its More menu).</p>
      )}
      {error && <p className="notice notice-bad" role="alert">{error}</p>}
      <div className="btn-row">
        <button type="submit" className="btn btn-gold" disabled={!ready || Boolean(step)}>
          {step ? <><Loader2 size={16} className="spin" aria-hidden="true" /> {step}</>
            : { learn: 'Build my course', test_prep: 'Build my test prep', semester: 'Plan my semester', problem_sprint: 'Start my sprint', thematic_reference: 'Build my practice course', continue: 'Add the next classes', code: 'Open in the IDE' }[intent]}
        </button>
        {!enough && <span className="hint">Add a file, or write at least a sentence about what you want.</span>}
      </div>
    </form>
  );
}

export default function CoursesHome({ user, onOpenCourse, onCodePractice, initialPreset, progress, onProgress, onOpenTopic, onReview }) {
  const [courses, setCourses] = useState(null);
  const [cleared, setCleared] = useState([]);  // finished sprints that can still be restored
  const [preset, setPreset] = useState(initialPreset || null);
  const [creating, setCreating] = useState(Boolean(initialPreset));
  const [error, setError] = useState(null);
  const [activeFolder, setActiveFolder] = useState('all');
  const [collapsedFolders, setCollapsedFolders] = useState(() => new Set());

  const toggleFolder = (folderName) => {
    setCollapsedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(folderName)) next.delete(folderName);
      else next.add(folderName);
      return next;
    });
  };

  const load = useCallback(() => {
    api(`/api/users/${user.id}/courses`)
      .then((d) => { setCourses(d.courses || []); setCleared(d.cleared || []); setError(null); })
      .catch((e) => setError(e.message));
  }, [user.id]);

  useEffect(() => { load(); }, [load]);
  useAgyEvents((evt) => { if (evt.type === 'COURSE_UPDATED') load(); });

  const getTime = (c) => {
    const v = c.updated_at ?? c.created_at ?? 0;
    return typeof v === 'number' ? v : Number(v) || 0;
  };

  const folderGroups = useMemo(() => {
    if (!courses || courses.length === 0) return [];

    const map = new Map();
    for (const c of courses) {
      const folder = getCourseFolder(c);
      if (!map.has(folder)) {
        map.set(folder, []);
      }
      map.get(folder).push(c);
    }

    const groups = [];
    for (const [name, items] of map.entries()) {
      items.sort((a, b) => getTime(b) - getTime(a));
      const lastActive = items.reduce((max, c) => Math.max(max, getTime(c)), 0);
      groups.push({ name, courses: items, lastActive });
    }

    groups.sort((a, b) => b.lastActive - a.lastActive);
    return groups;
  }, [courses]);

  const renderCard = (c) => {
    const [label, cls] = STATUS[c.status] || [c.status, 'status-pending'];
    const pct = c.class_count ? Math.round((c.completed_count / c.class_count) * 100) : 0;
    const canExtend = !['planning', 'diagnostic_ready'].includes(c.status) && c.class_count > 0 && c.mode !== 'problem_sprint';
    return (
      <div key={c.id} className="course-card">
        <div className="btn-row" style={{ gap: 'var(--space-2)' }}>
          <span className={`status ${cls}`}>{label}</span>
          {c.mode === 'test_prep' && (
            <span className="status status-gold"><Target size={12} aria-hidden="true" /> Test prep{c.exam_date ? ` · ${formatDate(c.exam_date)}` : ''}</span>
          )}
          {c.mode === 'semester' && (
            <span className="status status-gold"><CalendarRange size={12} aria-hidden="true" /> Semester</span>
          )}
          {c.mode === 'problem_sprint' && (
            <span className="status status-gold"><Zap size={12} aria-hidden="true" /> Sprint{c.auto_cleanup ? '' : ' · kept'}</span>
          )}
          {c.mode === 'thematic_reference' && (
            <span className="status status-gold"><Layers size={12} aria-hidden="true" /> Like my problems</span>
          )}
        </div>
        <h3><button type="button" className="card-link" onClick={() => onOpenCourse(c.id)}>{c.title}</button></h3>
        {c.goal && c.goal !== c.title && <p className="hint">{c.goal}</p>}
        <div className="meter" aria-hidden="true"><span style={{ width: `${pct}%` }} /></div>
        <div className="meta">
          <span>{c.class_count ? `${c.ready_count} of ${c.class_count} classes written` : 'Planning'}</span>
          {c.planned_count > 0 && <span>{c.planned_count} planned</span>}
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
  };

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

      <TodayPanel userId={user.id} progress={progress} onChange={onProgress} onContinue={onOpenTopic} onReview={onReview} />

      {(creating || (courses && courses.length === 0)) && (
        <StudyHub userId={user.id} courses={courses || []} preset={preset} onOpened={onOpenCourse} onCodePractice={onCodePractice}
          onCancel={courses && courses.length ? () => setCreating(false) : undefined} />
      )}
      {error && <p className="notice notice-bad" role="alert">{error}</p>}
      {courses === null && !error && <LoadingPanel label="Loading your courses…" />}
      {cleared.length > 0 && (
        <section className="sprint-cleared" aria-labelledby="sprint-cleared-h">
          <h2 id="sprint-cleared-h" className="label">Finished sprints</h2>
          <ul>
            {cleared.map((c) => (
              <li key={c.id}>
                <span className="sprint-cleared-title">{c.title}</span>
                <span className="hint">{c.undoUntil ? `deleted on ${formatDay(c.undoUntil)}` : 'deleted soon'}</span>
                <span className="btn-row" style={{ gap: 'var(--space-2)' }}>
                  <button type="button" className="btn btn-quiet btn-sm" onClick={() => onOpenCourse(c.id)}>Open</button>
                  <button type="button" className="btn btn-secondary btn-sm"
                    onClick={() => api(`/api/courses/${c.id}/keep`, { method: 'POST' }).then(load).catch((e) => setError(e.message))}>Keep in My courses</button>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {courses && courses.length > 0 && (
        <>
          <h2 className="section-h">Your courses</h2>

          {folderGroups.length > 1 && (
            <div className="folder-tabs" role="tablist" aria-label="Course folders">
              <button
                type="button"
                role="tab"
                aria-selected={activeFolder === 'all'}
                className={`folder-tab${activeFolder === 'all' ? ' active' : ''}`}
                onClick={() => setActiveFolder('all')}
              >
                All ({courses.length})
              </button>
              {folderGroups.map((g) => (
                <button
                  key={g.name}
                  type="button"
                  role="tab"
                  aria-selected={activeFolder === g.name}
                  className={`folder-tab${activeFolder === g.name ? ' active' : ''}`}
                  onClick={() => setActiveFolder(g.name)}
                >
                  <Folder size={14} aria-hidden="true" />
                  <span>{g.name}</span>
                  <span className="folder-badge">{g.courses.length}</span>
                </button>
              ))}
            </div>
          )}

          {folderGroups.length <= 1 ? (
            <div className="course-grid">
              {(folderGroups[0]?.courses || courses).map(renderCard)}
            </div>
          ) : activeFolder !== 'all' ? (
            <div className="course-grid">
              {(folderGroups.find((g) => g.name === activeFolder)?.courses || []).map(renderCard)}
            </div>
          ) : (
            folderGroups.map((g) => {
              const collapsed = collapsedFolders.has(g.name);
              return (
                <div key={g.name} className="course-folder-group">
                  <button
                    type="button"
                    className="course-folder-head"
                    onClick={() => toggleFolder(g.name)}
                    aria-expanded={!collapsed}
                  >
                    {collapsed ? <ChevronRight size={16} aria-hidden="true" /> : <ChevronDown size={16} aria-hidden="true" />}
                    <Folder size={16} aria-hidden="true" />
                    <span className="folder-title">{g.name}</span>
                    <span className="folder-badge">{g.courses.length}</span>
                  </button>
                  {!collapsed && (
                    <div className="course-grid">
                      {g.courses.map(renderCard)}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </>
      )}
    </div>
  );
}

/** A unix time in seconds as a short date (sprint purge dates). */
function formatDay(seconds) {
  return new Date(seconds * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatDate(iso) {
  const d = new Date(`${iso}T12:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
