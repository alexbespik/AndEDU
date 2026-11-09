import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Upload, Loader2, Search, X, Compass, Sparkles, ClipboardCheck, BookMarked, ShoppingCart } from 'lucide-react';
import { api, uploadFiles } from '../lib/api';
import { confirmGeminiUpload, handleUploadConsentError } from '../lib/consent';
import AdvisorChat from './AdvisorChat';
import PlanningCart from './PlanningCart';

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

/** AI-inferred College Curriculum labels (AC-5b): shown apart from official attributes, never counted as Done. */
function aiTags(course) {
  const list = Array.isArray(course?.inferred_attributes) ? course.inferred_attributes : [];
  const official = new Set(course?.attributes || []);
  return list.filter((a) => a?.attr && !official.has(a.attr)).map((a) => {
    const conf = Number(a.confidence);
    const pct = Number.isFinite(conf) ? Math.round(conf <= 1 ? conf * 100 : conf) : null;
    return (
      <span key={a.attr} className="ai-tag" title={`AI guess${pct !== null ? `, ${pct}% confident` : ''}, not official: ${a.reason || 'no reason given'}`}>
        likely {a.attr} (AI)
      </span>
    );
  });
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

// `geminiText`: the imported text itself may go to Gemini (catalog import with useModel), so ask for consent first.
function Importer({ label, hint, onText, accept, geminiText = false }) {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const pick = useRef(null);
  const send = async (t) => {
    if (geminiText && !(await confirmGeminiUpload(null, { anyFile: true }))) return;
    setBusy('Saving'); setError(null);
    try { await onText(t); setText(''); } catch (e) { setError(handleUploadConsentError(e)); }
    setBusy(null);
  };
  const files = async (list) => {
    if (!list?.length) return;
    const picked = Array.from(list);
    if (!(await confirmGeminiUpload(picked, { anyFile: geminiText }))) return;
    setBusy(`Reading ${picked.length} file${picked.length > 1 ? 's' : ''}`); setError(null);
    try { const up = await uploadFiles(picked); await onText(up.extracted_text || ''); } catch (e) { setError(handleUploadConsentError(e)); }
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

/** Course advisor: your record, the catalog, a planning cart, and readiness for a course. */
export default function AdvisorPage({ user, onOpenCourse }) {
  const [done, setDone] = useState([]);
  const [stats, setStats] = useState(null);
  const [q, setQ] = useState('');
  const [dept, setDept] = useState('');
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [reload, setReload] = useState(0);  // bump to search again (after an import)
  const [cart, setCart] = useState(null);
  const [askRequest, setAskRequest] = useState(null);  // {id, text}: a question for the advisor chat to send
  const [open, setOpen] = useState(null);
  const [sectionsMap, setSectionsMap] = useState({});
  const [notice, setNotice] = useState(null);
  const doneSet = new Set(done.filter((d) => !d.grade || !['F', 'W', 'U', 'I'].includes(d.grade.trim().toUpperCase())).map((d) => d.code));

  const loadDone = useCallback(() => api(`/api/advisor/${user.id}/completed`).then((d) => setDone(d.completed)).catch(() => {}), [user.id]);
  useEffect(() => { loadDone(); }, [loadDone]);
  const loadCart = useCallback((term = '') => api(`/api/advisor/${user.id}/cart?term=${encodeURIComponent(term)}`)
    .then(setCart).catch((e) => setNotice(e.message)), [user.id]);
  useEffect(() => { loadCart(); }, [loadCart]);
  // course rows and the advisor's answers add here; a section's term switches the cart to that term
  const addToCart = async (code, cartType = 'primary', crn = '', term = '') => {
    const r = await api(`/api/advisor/${user.id}/cart`, { method: 'POST', body: { code, term: term || cart?.term || '', cart_type: cartType, section_crn: crn } });
    setCart(r);
    setNotice(`${code.toUpperCase()} is in your ${cartType === 'backup' ? 'backups' : 'cart'} for ${r.term_name}${crn ? ` (CRN ${crn})` : ''}.`);
    return r;
  };
  const tryAdd = (...args) => addToCart(...args).catch((e) => setNotice(e.message));
  const cartItem = (code, term) => (cart && (!term || cart.term === term) ? cart.items.find((i) => i.code === code) : null);
  useEffect(() => {
    let stale = false;  // a slow answer for an older query must not replace a newer one
    const t = setTimeout(() => api(`/api/advisor/catalog?q=${encodeURIComponent(q)}&dept=${encodeURIComponent(dept)}&limit=500`)
      .then((d) => { if (!stale) { setResults(d.courses); setTotal(d.total ?? d.courses.length); setStats(d.stats); } })
      .catch(() => { if (!stale) { setResults([]); setTotal(0); } }), 250);
    return () => { stale = true; clearTimeout(t); };
  }, [q, dept, reload]);

  const requestedSections = useRef(new Set());

  const fetchSections = useCallback((code) => {
    if (requestedSections.current.has(code)) return;
    requestedSections.current.add(code);
    setSectionsMap((prev) => ({ ...prev, [code]: null }));
    api(`/api/advisor/catalog/${encodeURIComponent(code)}/sections`)
      .then((d) => setSectionsMap((latest) => ({ ...latest, [code]: {
        next: d.next_term_sections || [], nextName: d.next_term_name || 'the next term', other: d.other_terms || [],
        later: d.later_terms || [],
      } })))
      .catch(() => setSectionsMap((latest) => ({ ...latest, [code]: { next: [], nextName: 'the next term', other: [], failed: true } })));
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

  // a plain render function, not a component: a component defined here would remount every row on each render
  const courseRow = (c, extra) => {
    const r = readiness(c, doneSet);
    const taken = doneSet.has(c.code);
    const secs = sectionsMap[c.code];
    return (
      <li key={c.code} className="advisor-row">
        <button type="button" className="card-link advisor-head" onClick={() => toggleOpen(c.code)} aria-expanded={open === c.code}>
          <span className="num advisor-code">{c.code}</span><span>{c.title}{aiTags(c)}</span>
          {/* the full missing list can be hundreds of characters: the row shows a count, the tooltip and the detail the list */}
          <span className={`status ${taken ? 'status-pending' : r.status === 'unknown' ? 'status-pending' : r.met ? 'status-ready' : 'status-error'}`}
            title={!taken && !r.met && r.missing?.length ? `Missing: ${r.missing.join(' · ')}` : undefined}>
            {taken ? 'Done' : r.status === 'unknown' ? 'Prerequisites not listed' : r.met ? (r.status === 'none' ? 'No prerequisites' : 'Prerequisites met')
              : r.missing.length === 1 && r.missing[0].length <= 40 ? `Missing: ${r.missing[0]}` : `Missing prerequisites (${r.missing.length})`}
          </span>
          {extra}
        </button>
        {open === c.code && (
          <div className="stack-sm advisor-detail">
            {c.credits && <span className="hint">{c.credits} credits{c.attributes?.length ? ` · ${c.attributes.join(', ')}` : ''}</span>}
            {c.description && <p>{c.description}</p>}
            {c.prereqs && <p className="hint">Prerequisites: {c.prereqs}</p>}
            <div className="advisor-sections stack-xs" style={{ borderTop: '1px solid var(--border)', paddingTop: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
              <span className="label" style={{ fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                {secs ? `${secs.nextName} sections` : 'Scheduled sections'}
              </span>
              {secs === null || secs === undefined ? (
                <span className="hint"><Loader2 size={12} className="spin" /> Checking active schedule…</span>
              ) : secs.failed ? (
                <span className="hint">Couldn't load the schedule. Import your own schedule data.</span>
              ) : secs.next.length > 0 ? (
                <ul className="stack-xs" style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {secs.next.map((s) => (
                    <li key={s.term + s.crn} className="hint" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', alignItems: 'center' }}>
                      <span className="chip" style={{ fontSize: '0.75rem', padding: '1px 6px' }}>{s.term_name || s.term} · Sec {s.section}</span>
                      {s.meets && <span>{s.meets}</span>}
                      {s.instructor && <span>· {s.instructor}</span>}
                      <span className="num" style={{ opacity: 0.7 }}>CRN {s.crn}{s.credits ? ` · ${s.credits} cr` : ''}</span>
                      {cartItem(c.code, s.term)?.section_crn === String(s.crn)
                        ? <span className="status status-ready">In your cart</span>
                        : <button type="button" className="btn btn-quiet btn-sm" onClick={() => tryAdd(c.code, cartItem(c.code, s.term)?.cart_type || 'primary', String(s.crn), s.term)}>Pick this section</button>}
                    </li>
                  ))}
                </ul>
              ) : (
                <span className="hint">Not offered in {secs.nextName}: no sections listed.</span>
              )}
              {secs && secs.later?.length > 0 && (
                <span className="hint">Also scheduled later: {secs.later.slice(0, 4).join(', ')}</span>
              )}
              {secs && secs.other?.length > 0 && (
                <span className="hint" style={{ opacity: 0.75 }}>Other terms it ran: {secs.other.slice(0, 6).join(', ')}</span>
              )}
            </div>
            <div className="btn-row">
              {cartItem(c.code) && <span className="status status-ready"><ShoppingCart size={12} aria-hidden="true" /> In your {cartItem(c.code).cart_type === 'backup' ? 'backups' : 'cart'}</span>}
              <button type="button" className="btn btn-secondary btn-sm" onClick={() => tryAdd(c.code, 'primary')}>+ Cart</button>
              <button type="button" className="btn btn-quiet btn-sm" onClick={() => tryAdd(c.code, 'backup')}>+ Backup</button>
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
          <p>Add the courses you have done, explore the W&amp;M catalog, plan a term in your cart, and test whether you're ready for a course before you register.</p>
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

      <PlanningCart user={user} cart={cart} onCart={setCart} onLoadTerm={loadCart} onAdd={addToCart} onOpenCourse={onOpenCourse}
        onAsk={(text) => setAskRequest({ id: Date.now(), text })} />

      <AdvisorChat user={user} doneCount={done.length} onOpenCourse={onOpenCourse} onAddToCart={tryAdd} askRequest={askRequest} />

      <section className="panel stack" aria-labelledby="rec-done">
        <h2 id="rec-done"><BookMarked size={18} aria-hidden="true" /> Courses you've done ({done.length})</h2>
        <div className="file-chips">
          {done.map((d) => (
            <span key={d.code} className="chip" title={d.title}>{d.code}{d.grade ? ` · ${d.grade}` : ''}{aiTags(d)}
              <button type="button" className="btn btn-quiet btn-sm btn-icon" style={{ minHeight: 22, width: 22, border: 0 }} aria-label={`Remove ${d.code}`}
                onClick={() => api(`/api/advisor/${user.id}/completed/${encodeURIComponent(d.code)}`, { method: 'DELETE' }).then((r) => setDone(r.completed))}><X size={12} /></button>
            </span>
          ))}
        </div>
        <Importer label="Add courses" hint={'Paste a transcript or degree audit, or type codes:\nCSCI 141 A-\nMATH 111 B+'} accept=".pdf,.png,.jpg,.jpeg,.webp,.txt"
          onText={(text) => api(`/api/advisor/${user.id}/completed`, { method: 'POST', body: { text, source: 'upload' } }).then((r) => { setDone(r.completed); setNotice(`Added ${r.added} course${r.added === 1 ? '' : 's'}.`); })} />
        <p className="hint">Screenshots are read on the server; only course codes, titles and grades are kept.</p>
      </section>

      <section className="panel stack" aria-labelledby="cat-h">
        <div className="btn-row" style={{ justifyContent: 'space-between' }}>
          <h2 id="cat-h"><Compass size={18} aria-hidden="true" /> Catalog {stats ? `(${stats.courses} courses${stats.sections ? ` · ${stats.sections.toLocaleString()} classes scheduled` : ''})` : ''}</h2>
          <div className="btn-row">
            <Search size={15} aria-hidden="true" />
            <input className="input" style={{ width: 240, maxWidth: '100%' }} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search titles and descriptions" aria-label="Search the catalog" />
            <select className="input" style={{ width: 120 }} value={dept} onChange={(e) => setDept(e.target.value)} aria-label="Department">
              <option value="">All</option>
              {(stats?.departments || []).map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
        </div>
        {results.length > 0 && <ul className="advisor-list">{results.map((c) => courseRow(c))}</ul>}
        {total > results.length && <p className="hint">Showing the first {results.length} of {total} matches: {dept ? 'add words' : 'pick a department or add words'} to narrow it.</p>}
        <details open={!stats?.courses}>
          <summary className="label" style={{ cursor: 'pointer' }}>Import catalog courses</summary>
          <div className="stack-sm" style={{ marginTop: 'var(--space-3)' }}>
            <p className="hint">
              W&amp;M's catalog (catalog.wm.edu) blocks automated downloads, so import what your browser shows: save a department's course
              page or a catalog PDF and upload it, or copy its text here. Entries like <code>CSCI 241. Data Structures. (3 Credits)</code> are
              read directly; past catalogs are in the SWEM archive (dspace.swem.wm.edu). The catalog year is read from the
              file (or say it in the text, e.g. "2016-2017") so students see how old the data is.
            </p>
            <Importer label="Catalog text or PDF" hint="Paste catalog course listings…" accept=".pdf,.txt,.html,.png,.jpg" geminiText
              onText={(text) => api('/api/advisor/catalog/import', { method: 'POST', body: { text, source: 'upload', useModel: true } })
                .then((r) => { setStats(r.stats); setNotice(`Imported ${r.imported} catalog course${r.imported === 1 ? '' : 's'}.`); setReload((n) => n + 1); })} />
          </div>
        </details>
      </section>
    </div>
  );
}
