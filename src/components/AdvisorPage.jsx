import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Upload, Loader2, Search, X, Compass, Sparkles, ClipboardCheck, BookMarked } from 'lucide-react';
import { api, uploadFiles } from '../lib/api';

/** A course's listed prerequisites against the student's record ("or" wording: one of the group is enough). */
function readiness(course, done) {
  const missing = course.prereq_codes.filter((c) => !done.has(c));
  const either = /\bor\b/i.test(course.prereqs || '') && course.prereq_codes.some((c) => done.has(c));
  return { met: either || !missing.length, missing: either ? [] : missing };
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
  const [notice, setNotice] = useState(null);
  const doneSet = new Set(done.map((d) => d.code));

  const loadDone = useCallback(() => api(`/api/advisor/${user.id}/completed`).then((d) => setDone(d.completed)).catch(() => {}), [user.id]);
  const search = useCallback(() => api(`/api/advisor/catalog?q=${encodeURIComponent(q)}&dept=${encodeURIComponent(dept)}`)
    .then((d) => { setResults(d.courses); setStats(d.stats); }).catch(() => {}), [q, dept]);
  useEffect(() => { loadDone(); }, [loadDone]);
  useEffect(() => { const t = setTimeout(search, 250); return () => clearTimeout(t); }, [search]);

  const readyCourse = async (code) => {
    setNotice(`Building a readiness check for ${code}…`);
    try { const r = await api(`/api/advisor/${user.id}/readiness-course`, { method: 'POST', body: { code } }); onOpenCourse(r.course.id); }
    catch (e) { setNotice(e.message); }
  };
  const recommend = () => api(`/api/advisor/${user.id}/recommend?interests=${encodeURIComponent(interests)}`).then((d) => setRecs(d.courses)).catch((e) => setNotice(e.message));

  const CourseRow = ({ c, extra }) => {
    const r = readiness(c, doneSet);
    const taken = doneSet.has(c.code);
    return (
      <li className="advisor-row">
        <button type="button" className="card-link advisor-head" onClick={() => setOpen(open === c.code ? null : c.code)} aria-expanded={open === c.code}>
          <span className="num advisor-code">{c.code}</span><span>{c.title}</span>
          <span className={`status ${taken ? 'status-pending' : r.met ? 'status-ready' : 'status-error'}`}>
            {taken ? 'Done' : r.met ? 'Prerequisites met' : `Missing ${r.missing.join(', ')}`}
          </span>
          {extra}
        </button>
        {open === c.code && (
          <div className="stack-sm advisor-detail">
            {c.credits && <span className="hint">{c.credits} credits{c.attributes?.length ? ` · ${c.attributes.join(', ')}` : ''}</span>}
            {c.description && <p>{c.description}</p>}
            {c.prereqs && <p className="hint">Prerequisites: {c.prereqs}</p>}
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
      {notice && <p className="notice notice-info">{notice}</p>}

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
          <h2 id="cat-h"><Compass size={18} aria-hidden="true" /> Catalog {stats ? `(${stats.courses} courses)` : ''}</h2>
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
              read directly; past catalogs are in the SWEM archive (dspace.swem.wm.edu).
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
