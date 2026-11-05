import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Upload, Loader2, Search, X, Compass, Sparkles, ClipboardCheck, BookMarked } from 'lucide-react';
import { api, uploadFiles } from '../lib/api';
import AdvisorChat from './AdvisorChat';

/** Evaluates prerequisite CNF groups (AND of OR-choice groups). */
function prereqGroups(course) {
  // an older backend sends prereq_tree as the raw JSON column ("[]"); a string here used to crash the page
  let tree = course.prereq_tree;
  if (typeof tree === 'string') { try { tree = JSON.parse(tree); } catch { tree = []; } }
  const groups = Array.isArray(tree) ? tree.map((g) => (Array.isArray(g) ? g : [g]).filter((c) => typeof c === 'string')).filter((g) => g.length) : [];
  return groups.length ? groups : (Array.isArray(course.prereq_codes) ? course.prereq_codes : []).map((c) => [c]);
}

function readiness(course, done) {
  const tree = prereqGroups(course);

  const levelMatch = (course.code || '').match(/\d+/);
  const level = levelMatch ? parseInt(levelMatch[0], 10) : 100;
  const rawPrereqs = (course.prereqs || '').trim().toLowerCase();
  const isExplicitNone = ['none', 'none.', 'n/a', 'no prerequisites'].includes(rawPrereqs);

  if (!tree.length) {
    if (level >= 300 && !isExplicitNone) {
      return { met: false, missing: [], status: 'unknown' };
    }
    return { met: true, missing: [], status: 'none' };
  }

  const missing = [];
  for (const group of tree) {
    if (!group.some((c) => done.has(c))) {
      missing.push(group.length > 1 ? `(${group.join(' or ')})` : group[0]);
    }
  }
  return { met: missing.length === 0, missing, status: missing.length === 0 ? 'met' : 'missing' };
}

function DegreeAudit({ user, doneLength }) {
  const [audit, setAudit] = useState(null);
  useEffect(() => {
    if (!user?.id) return;
    api(`/api/advisor/${user.id}/degree-audit`).then(setAudit).catch(() => {});
  }, [user?.id, doneLength]);

  if (!audit || !user?.id) return null;
  const { coll, proficiencies, total_credits } = audit;

  return (
    <section className="panel stack-sm" style={{ marginBottom: 'var(--space-4)' }} aria-labelledby="coll-h" role="region">
      <div className="btn-row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 id="coll-h" style={{ fontSize: '1rem', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Sparkles size={16} /> Degree Progress · College Curriculum (COLL)
        </h2>
        <span className="hint">{total_credits} credits completed</span>
      </div>
      <div className="file-chips" style={{ marginTop: 'var(--space-2)' }}>
        {coll && Object.entries(coll).map(([k, req]) => (
          <span
            key={k}
            className="chip"
            style={{
              background: req.met ? 'var(--ok-tint)' : 'var(--surface)',
              color: req.met ? 'var(--ok-ink)' : 'var(--ink)',
              borderColor: req.met ? 'var(--ok-border, var(--ok-ink))' : 'var(--rule)',
              padding: '4px 10px',
            }}
            title={req.courses?.length ? `Applied: ${req.courses.join(', ')}` : 'No courses applied'}
          >
            <strong>{req.name}</strong>:{' '}
            {req.met ? 'Done' : `${req.earned}/${req.required} cr`}
            {k === 'coll200' && !req.met && (
              <span className="hint" style={{ fontSize: '0.72rem', marginLeft: '4px' }}>
                (ALV: {req.alv}/3 · CSI: {req.csi}/3 · NQR: {req.nqr}/3)
              </span>
            )}
            {req.likely > 0 && !req.met && (
              <span
                className="chip"
                style={{
                  fontSize: '0.72rem',
                  padding: '1px 6px',
                  marginLeft: '6px',
                  background: 'var(--accent-tint, rgba(99, 102, 241, 0.1))',
                  color: 'var(--accent-ink, #4f46e5)',
                  border: '1px solid var(--accent-border, rgba(99, 102, 241, 0.3))',
                }}
                title={
                  req.likely_courses?.length
                    ? `AI identified candidate course(s) awaiting official advisor review: ${req.likely_courses.join(', ')}`
                    : 'AI identified candidate courses awaiting official advisor review'
                }
              >
                +{req.likely} likely (AI)
              </span>
            )}
          </span>
        ))}
        {proficiencies && Object.entries(proficiencies).map(([k, p]) => (
          <span
            key={k}
            className="chip"
            style={{
              background: p.met ? 'var(--ok-tint)' : 'var(--surface)',
              color: p.met ? 'var(--ok-ink)' : 'var(--ink)',
              borderColor: p.met ? 'var(--ok-border, var(--ok-ink))' : 'var(--rule)',
              padding: '4px 10px',
            }}
            title={p.courses?.length ? `Applied: ${p.courses.join(', ')}` : 'Not yet completed'}
          >
            <strong>{p.name}</strong>: {p.met ? 'Done' : 'Needed'}
          </span>
        ))}
      </div>
    </section>
  );
}

function Importer({ label, hint, onText, accept }) {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const pick = useRef(null);
  const send = async (t) => { setBusy('Saving'); setError(null); try { await onText(t); setText(''); } catch (e) { setError(e.message); } setBusy(null); };
  const files = async (list) => {
    if (!list?.length) return;
    setBusy(`Reading ${list.length} file${list.length > 1 ? 's' : ''}`); setError(null);
    try { const up = await uploadFiles(Array.from(list)); await onText(up.extracted_text || ''); } catch (e) { setError(e.message); }
    setBusy(null);
  };
  return (
    <div className="stack-sm">
      <label className="label" htmlFor={`imp-${label}`}>{label}</label>
      <textarea id={`imp-${label}`} className="textarea" rows={4} value={text} onChange={(e) => setText(e.target.value)} placeholder={hint} />
      <div className="btn-row">
        <button type="button" className="btn btn-primary btn-sm" disabled={!text.trim() || Boolean(busy)} onClick={() => send(text)}>Add from text</button>
        <button type="button" className="btn btn-secondary btn-sm" disabled={Boolean(busy)} onClick={() => pick.current?.click()}><Upload size={14} /> Upload screenshot or PDF</button>
        <input ref={pick} type="file" multiple hidden accept={accept} onChange={(e) => { files(e.target.files); e.target.value = ''; }} />
        {busy && <span className="hint"><Loader2 size={13} className="spin" /> {busy}…</span>}
      </div>
      {error && <p className="notice notice-bad">{error}</p>}
    </div>
  );
}

/** Course advisor: your record, the catalog, readiness for a course, and what to take next. */
export default function AdvisorPage({ user, onOpenCourse }) {
  const [done, setDone] = useState([]);
  const [stats, setStats] = useState(null);
  const [q, setQ] = useState('');
  const [dept, setDept] = useState('');
  const [results, setResults] = useState([]);
  const [recs, setRecs] = useState(null);
  const [interests, setInterests] = useState('');
  const [open, setOpen] = useState(null);
  const [sectionsMap, setSectionsMap] = useState({});
  const [notice, setNotice] = useState(null);
  const doneSet = new Set(done.filter((d) => !d.grade || !['F', 'W', 'U', 'I'].includes(d.grade.trim().toUpperCase())).map((d) => d.code));

  const loadDone = useCallback(() => api(`/api/advisor/${user.id}/completed`).then((d) => setDone(d.completed)).catch(() => {}), [user.id]);
  const search = useCallback(() => api(`/api/advisor/catalog?q=${encodeURIComponent(q)}&dept=${encodeURIComponent(dept)}`)
    .then((d) => { setResults(d.courses); setStats(d.stats); }).catch(() => {}), [q, dept]);
  useEffect(() => { loadDone(); }, [loadDone]);
  useEffect(() => { const t = setTimeout(search, 250); return () => clearTimeout(t); }, [search]);

  const requestedSections = useRef(new Set());

  const fetchSections = useCallback((code) => {
    if (requestedSections.current.has(code)) return;
    requestedSections.current.add(code);
    setSectionsMap((prev) => ({ ...prev, [code]: null }));
    api(`/api/advisor/catalog/${encodeURIComponent(code)}/sections`)
      .then((d) => setSectionsMap((latest) => ({ ...latest, [code]: d.sections || [] })))
      .catch(() => setSectionsMap((latest) => ({ ...latest, [code]: [] })));
  }, []);

  const toggleOpen = (code) => {
    if (open === code) {
      setOpen(null);
    } else {
      setOpen(code);
      fetchSections(code);
    }
  };

  const readyCourse = async (code) => {
    setNotice(`Building a readiness check for ${code}…`);
    try { const r = await api(`/api/advisor/${user.id}/readiness-course`, { method: 'POST', body: { code } }); onOpenCourse(r.course.id); }
    catch (e) { setNotice(e.message); }
  };
  const recommend = () => api(`/api/advisor/${user.id}/recommend?interests=${encodeURIComponent(interests)}`).then((d) => setRecs(d.courses)).catch((e) => setNotice(e.message));

  const CourseRow = ({ c, extra }) => {
    const r = readiness(c, doneSet);
    const taken = doneSet.has(c.code);
    const secs = sectionsMap[c.code];
    return (
      <li className="advisor-row">
        <button type="button" className="card-link advisor-head" onClick={() => toggleOpen(c.code)} aria-expanded={open === c.code}>
          <span className="num advisor-code">{c.code}</span><span>{c.title}</span>
          <span className={`status ${taken ? 'status-pending' : r.status === 'unknown' ? 'status-pending' : r.met ? 'status-ready' : 'status-error'}`}>
            {taken ? 'Done' : r.status === 'unknown' ? 'Prerequisites not listed' : r.met ? (r.status === 'none' ? 'No prerequisites' : 'Prerequisites met') : `Missing: ${r.missing.join(' · ')}`}
          </span>
          {extra}
        </button>
        {open === c.code && (
          <div className="stack-sm advisor-detail">
            {c.credits && <span className="hint">{c.credits} credits{c.attributes?.length ? ` · ${c.attributes.join(', ')}` : ''}</span>}
            {c.description && <p>{c.description}</p>}
            {c.prereqs && <p className="hint">Prerequisites: {c.prereqs}</p>}
            <div className="advisor-sections stack-xs" style={{ borderTop: '1px solid var(--border)', paddingTop: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
              <span className="label" style={{ fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Scheduled Classes &amp; Sections</span>
              {secs === null || secs === undefined ? (
                <span className="hint"><Loader2 size={12} className="spin" /> Checking active schedule…</span>
              ) : secs.length > 0 ? (
                <ul className="stack-xs" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {secs.map((s) => (
                    <li key={s.term + s.crn} className="hint" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', alignItems: 'center' }}>
                      <span className="chip" style={{ fontSize: '0.75rem', padding: '1px 6px' }}>{s.term_name || s.term} · Sec {s.section}</span>
                      {s.meets && <span>{s.meets}</span>}
                      {s.instructor && <span>· {s.instructor}</span>}
                      <span className="num" style={{ opacity: 0.7 }}>CRN {s.crn}{s.credits ? ` · ${s.credits} cr` : ''}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <span className="hint">No active sections listed for upcoming semesters.</span>
              )}
            </div>
            {!taken && (
              <div className="btn-row">
                <button type="button" className="btn btn-gold btn-sm" onClick={() => readyCourse(c.code)}><ClipboardCheck size={14} /> Test my readiness</button>
                <span className="hint">A diagnostic on what {c.code} assumes, then short bridge classes for any gaps.</span>
              </div>
            )}
          </div>
        )}
      </li>
    );
  };

  return (
    <div className="page page-wide">
      <div className="page-head">
        <div>
          <h1>Course advisor</h1>
          <p>Add the courses you have done, explore the W&amp;M catalog, see what you can take next, and test whether you're ready for a course before you register.</p>
        </div>
      </div>
      {stats && (stats.courses ? stats.outdated : true) && (
        <div className="notice notice-bad" role="note">
          <strong>Catalog may be out of date.</strong>{' '}
          {stats.courses
            ? <>This advisor works on {stats.years?.length ? `the ${stats.years.join(', ')} catalog` : 'an imported catalog of unknown year'}.
              Course numbers, titles and prerequisites can change from year to year: check every course in the current catalog
              (catalog.wm.edu) and with your advisor before you register.</>
            : <>No catalog is loaded. W&amp;M's current catalog and course list can't be downloaded automatically; import the pages or
              a catalog PDF below, and treat any older catalog as a guide only.</>}
        </div>
      )}
      {notice && <p className="notice notice-info">{notice}</p>}

      <DegreeAudit user={user} doneLength={done.length} />

      <AdvisorChat user={user} doneCount={done.length} />

      <div className="split">
        <section className="panel stack" aria-labelledby="rec-h">
          <h2 id="rec-h"><Sparkles size={18} aria-hidden="true" /> What to take next</h2>
          <div className="btn-row">
            <input className="input" style={{ flex: '1 1 220px' }} value={interests} onChange={(e) => setInterests(e.target.value)} placeholder="Interests, e.g. machine learning, statistics" />
            <button type="button" className="btn btn-primary" onClick={recommend} disabled={!stats?.courses}>Recommend</button>
          </div>
          {!stats?.courses && <p className="hint">Import the catalog first (below).</p>}
          {recs && (recs.length ? (
            <ul className="advisor-list">{recs.map((c) => <CourseRow key={c.code} c={c} extra={c.builds_on?.length ? <span className="hint">builds on {c.builds_on.join(', ')}</span> : null} />)}</ul>
          ) : <p className="hint">Nothing matches yet: add your completed courses or import more of the catalog.</p>)}
        </section>

        <section className="panel stack" aria-labelledby="rec-done">
          <h2 id="rec-done"><BookMarked size={18} aria-hidden="true" /> Courses you've done ({done.length})</h2>
          <div className="file-chips">
            {done.map((d) => (
              <span key={d.code} className="chip" title={d.title}>{d.code}{d.grade ? ` · ${d.grade}` : ''}
                <button type="button" className="btn btn-quiet btn-sm btn-icon" style={{ minHeight: 22, width: 22, border: 0 }} aria-label={`Remove ${d.code}`}
                  onClick={() => api(`/api/advisor/${user.id}/completed/${encodeURIComponent(d.code)}`, { method: 'DELETE' }).then((r) => setDone(r.completed))}><X size={12} /></button>
              </span>
            ))}
          </div>
          <Importer label="Add courses" hint={'Paste a transcript or degree audit, or type codes:\nCSCI 141 A-\nMATH 111 B+'} accept=".pdf,.png,.jpg,.jpeg,.webp,.txt"
            onText={(text) => api(`/api/advisor/${user.id}/completed`, { method: 'POST', body: { text, source: 'upload' } }).then((r) => { setDone(r.completed); setNotice(`Added ${r.added} course${r.added === 1 ? '' : 's'}.`); })} />
          <p className="hint">Screenshots are read on the server; only course codes, titles and grades are kept.</p>
        </section>
      </div>

      <section className="panel stack" aria-labelledby="cat-h">
        <div className="btn-row" style={{ justifyContent: 'space-between' }}>
          <h2 id="cat-h"><Compass size={18} aria-hidden="true" /> Catalog {stats ? `(${stats.courses} courses${stats.sections ? ` · ${stats.sections.toLocaleString()} classes scheduled` : ''})` : ''}</h2>
          <div className="btn-row">
            <Search size={15} aria-hidden="true" />
            <input className="input" style={{ width: 240 }} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search titles and descriptions" aria-label="Search the catalog" />
            <select className="input" style={{ width: 120 }} value={dept} onChange={(e) => setDept(e.target.value)} aria-label="Department">
              <option value="">All</option>
              {(stats?.departments || []).map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
        </div>
        {results.length > 0 && <ul className="advisor-list">{results.map((c) => <CourseRow key={c.code} c={c} />)}</ul>}
        <details open={!stats?.courses}>
          <summary className="label" style={{ cursor: 'pointer' }}>Import catalog courses</summary>
          <div className="stack-sm" style={{ marginTop: 'var(--space-3)' }}>
            <p className="hint">
              W&amp;M's catalog (catalog.wm.edu) blocks automated downloads, so import what your browser shows: save a department's course
              page or a catalog PDF and upload it, or copy its text here. Entries like <code>CSCI 241. Data Structures. (3 Credits)</code> are
              read directly; past catalogs are in the SWEM archive (dspace.swem.wm.edu). The catalog year is read from the
              file (or say it in the text, e.g. "2016-2017") so students see how old the data is.
            </p>
            <Importer label="Catalog text or PDF" hint="Paste catalog course listings…" accept=".pdf,.txt,.html,.png,.jpg"
              onText={(text) => api('/api/advisor/catalog/import', { method: 'POST', body: { text, source: 'upload', useModel: true } })
                .then((r) => { setStats(r.stats); setNotice(`Imported ${r.imported} catalog course${r.imported === 1 ? '' : 's'}.`); search(); })} />
          </div>
        </details>
      </section>
    </div>
  );
}
