import React, { useEffect, useState } from 'react';
import { ShoppingCart, Loader2, X, ArrowRightCircle, ArrowLeftRight, AlertTriangle, MessageCircle, Plus, ListOrdered } from 'lucide-react';
import { api } from '../lib/api';

const FLAG_TEXT = {
  no_section: 'No section picked', prereq_missing: 'Prerequisites missing', prereq_check: 'Check score or placement', already_done: 'Already done',
};
const FLAG_CLASS = { no_section: 'status-pending', prereq_check: 'status-working' };
const LOAD_TEXT = {
  underload: 'Under 12 credits: not full-time',
  full_time: 'Full-time, below the recommended 14–16',
  recommended: 'Recommended load (14–16)',
  heavy: 'Heavy: over 16 (the cart cap)',
  overload: 'Overload: over 18',
};
const PRIORITY_TEXT = { must: 'Must', want: 'Want', nice: 'Nice' };
const RISK_TEXT = { high: 'High', medium: 'Medium', low: 'Low', unknown: 'Unknown' };
const RISK_CLASS = { high: 'status-error', medium: 'status-working', low: 'status-ready', unknown: 'status-pending' };
const CLASS_YEARS = ['Freshman', 'Sophomore', 'Junior', 'Senior'];
const ESTIMATE_NOTE = 'Seat risk is an estimate from past imported schedules, not a promise. Many courses show Unknown or low '
  + 'confidence because the history is thin, and registration window dates aren\'t loaded.';
const GAUGE_MAX = 21;
const pct = (n) => `${Math.min(100, (n / GAUGE_MAX) * 100)}%`;

function sectionLabel(s) {
  return [`Sec ${s.section}`, s.meets, s.instructor, `CRN ${s.crn}`].filter(Boolean).join(' · ');
}

/** A section option: marked when the student's record misses that section's prerequisites. */
function sectionOption(s, done) {
  const mark = { missing: ' · prerequisites missing', check: ' · check score' }[s.prereq_status];
  return sectionLabel(s) + (!done && mark ? mark : '');
}

/** "AP Calculus BC (4+)" for a test, else the name PATH gives (an admission, an equivalency flag). */
const optionName = (o) => (o.kind === 'test' && o.min != null ? `${o.test} (${o.min}+)` : o.test);

/** The options for one group: tests and admissions by name, PATH equivalency/exemption/placement flags summarised. */
function scoreText(options) {
  const named = options.filter((o) => o.kind !== 'equivalent').map(optionName);
  const other = options.some((o) => o.kind === 'equivalent');
  return [...named, ...(other ? ['an equivalent/placement'] : [])].join(' or ');
}

/** What a "check" status means: each missing group with the scores PATH accepts instead (no score is on record). */
function checkText(p) {
  return (p.score_options || []).map((o) => `Missing ${o.group}, or a qualifying score: ${scoreText(o.options)}`).join('; ');
}

/**
 * What the chosen section requires (each section can list its own rule in PATH) or, before one is picked, the
 * course rule; plus the parts this check can't see (score alternatives, approval, grade minimums).
 */
function PrereqHint({ item }) {
  const chosen = item.section;
  const p = chosen || item.course_prereq;
  if (!p) return null;
  const lines = [];
  const check = p.prereq_status === 'check';
  if (chosen && p.prereqs) {
    const met = p.prereq_status === 'met';
    lines.push(
      <span key="req">This section requires: {p.prereqs} (course: {item.course_prereq?.prereqs || 'none listed'}){' '}
        <span className={`status ${met ? 'status-ready' : check ? 'status-working' : 'status-error'}`}>
          {met ? 'Met' : check ? (checkText(p) || 'Check score or admission') : `Missing ${p.prereq_missing.join('; ')}`}
        </span>
      </span>,
    );
  } else if (chosen && p.prereq_note) {
    lines.push(<span key="note">PATH lists for this section: {p.prereq_note} No course is named, so the course rule applies.</span>);
  } else if (chosen && item.sections_differ) {
    lines.push(<span key="own">This section lists no prerequisite of its own; the course rule applies.</span>);
  } else if (!chosen && item.sections_differ) {
    lines.push(<span key="differ">Sections of this course list different prerequisites: pick one to check yours.</span>);
  }
  if (check && p.score_options?.length && !(chosen && p.prereqs)) {  // else the badge above says it
    lines.push(<span key="check"><span className="status status-working">{checkText(p)}</span> (scores aren't on your record)</span>);
  }
  if (p.concurrent?.length) {
    lines.push(<span key="along">Taking {p.concurrent.join(', ')} alongside (PATH allows it in the same term).</span>);
  }
  // only the codes still missing: one the student already passed needs no same-term note
  const missingCodes = (p.prereq_missing || []).flatMap((g) => g.split(' or '));
  const sameTerm = (p.concurrent_ok || []).filter((c) => !(p.concurrent || []).includes(c) && missingCodes.includes(c));
  if (sameTerm.length && (p.prereq_status === 'missing' || check)) {
    lines.push(<span key="conc">{sameTerm.join(', ')} may be taken in the same term.</span>);
  }
  // one phrase per OR: any one option of a group is enough
  const required = p.required_any?.length ? p.required_any : (p.required_alts || []).map((a) => [a]);
  if (required.length) {
    const text = required.map((g) => (g.length === 1 ? optionName(g[0]) : `one of ${g.map(optionName).join(' or ')}`));
    lines.push(<span key="also">Also requires: {text.join(', ')} (not checked).</span>);
  }
  if (p.score_alternative && !check) lines.push(<span key="score">Or an equivalent score/placement (not checked here).</span>);
  if (chosen?.consent) lines.push(<span key="consent">{chosen.consent_kind || 'Approval'} required to register.</span>);
  if (p.grade_minimum && p.prereq_status !== 'none') lines.push(<span key="grade">{p.grade_minimum}</span>);
  if (!lines.length) return null;
  return <div className="hint stack-xs">{lines}</div>;
}

const asOf = (ts) => (ts ? new Date(ts * 1000).toLocaleString() : 'an unknown time');

/** Seat-risk badge; the evidence is in the tooltip. risk may be null when no estimate could be made. */
function RiskBadge({ risk }) {
  const level = risk?.level || 'unknown';
  const title = risk
    ? [`${RISK_TEXT[level]} seat risk (${risk.confidence} confidence)`, ...(risk.evidence || []), risk.estimate].join('\n')
    : 'No estimate available for this course.';
  return <span className={`status ${RISK_CLASS[level]} cart-risk`} title={title}>Risk: {RISK_TEXT[level]}</span>;
}

function liveLine(live) {
  if (!live) return null;
  return `Live seats: ${live.open} of ${live.capacity} open, as of ${asOf(live.as_of)}${live.started ? '' : ' (registration not started)'}.`;
}

/**
 * The student's planning cart for one term: primary picks (they count toward the load) and backups, each with a
 * section chosen from the imported schedule. The cart never picks courses or sections on its own.
 * `cart` / `onCart` are owned by the advisor page so "+ Cart" buttons elsewhere update the same cart.
 */
export default function PlanningCart({ user, cart, onCart, onLoadTerm, onAdd, onOpenCourse, onAsk }) {
  const [code, setCode] = useState('');
  const [options, setOptions] = useState([]);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [classYear, setClassYear] = useState('');
  const [plan, setPlan] = useState(null);
  const [planWanted, setPlanWanted] = useState(0);  // 0: the "Registration plan" panel is closed; bumped per click
  const [planBusy, setPlanBusy] = useState(false);

  useEffect(() => {  // the optional class year: only compared with class-year seat restrictions
    let stale = false;
    api(`/api/advisor/${user.id}/prefs`).then((d) => { if (!stale) setClassYear(d.class_year || ''); }).catch(() => {});
    return () => { stale = true; };
  }, [user.id]);

  const cartTerm = cart?.term;
  useEffect(() => {  // load the registration plan when asked, and keep it in step with cart edits while it is open
    if (!planWanted || !cartTerm) return undefined;
    let stale = false;
    api(`/api/advisor/${user.id}/cart/research?term=${encodeURIComponent(cartTerm)}`)
      .then((d) => { if (!stale) setPlan(d); })
      .catch((e) => { if (!stale) setError(e.message); })
      .finally(() => { if (!stale) setPlanBusy(false); });
    return () => { stale = true; };
  }, [cart, cartTerm, planWanted, user.id]);  // planWanted changes on every click, so a click always refreshes

  useEffect(() => {  // catalog autocomplete for the add-by-code box
    const text = code.trim();
    if (text.length < 2) { setOptions([]); return undefined; }
    let stale = false;
    const t = setTimeout(() => api(`/api/advisor/catalog?q=${encodeURIComponent(text)}&limit=8`)
      .then((d) => { if (!stale) setOptions(d.courses || []); })
      .catch(() => { if (!stale) setOptions([]); }), 250);
    return () => { stale = true; clearTimeout(t); };
  }, [code]);

  if (!cart) return null;
  const term = cart.term;
  const items = cart.items || [];
  const s = cart.summary || {};
  const credits = s.credits || 0;

  const run = async (label, fn) => {
    setBusy(label); setError(null);
    try { await fn(); } catch (e) { setError(e.message); }
    setBusy(null);
  };
  const patch = (c, body) => run(c, async () => onCart(await api(`/api/advisor/${user.id}/cart/${encodeURIComponent(c)}`, { method: 'PATCH', body: { term, ...body } })));
  const remove = (c) => run(c, async () => onCart(await api(`/api/advisor/${user.id}/cart/${encodeURIComponent(c)}?term=${encodeURIComponent(term)}`, { method: 'DELETE' })));
  const launch = (item) => run(item.code, async () => {
    if (item.studio_course_id) { onOpenCourse?.(item.studio_course_id); return; }
    const r = await api(`/api/advisor/${user.id}/launch-course`, { method: 'POST', body: { code: item.code, term } });
    onCart(await api(`/api/advisor/${user.id}/cart?term=${encodeURIComponent(term)}`));
    if (r.course_id) onOpenCourse?.(r.course_id);
  });
  const closePlan = () => { setPlanWanted(0); setPlan(null); setPlanBusy(false); };  // a fetch cut off by closing never clears it
  const saveClassYear = (value) => run('prefs', async () => {
    const d = await api(`/api/advisor/${user.id}/prefs`, { method: 'PUT', body: { class_year: value } });
    setClassYear(d.class_year || '');
    onCart(await api(`/api/advisor/${user.id}/cart?term=${encodeURIComponent(term)}`));
  });
  const addCode = (e) => {
    e.preventDefault();
    const c = code.trim();
    if (!c) return;
    run('add', async () => { await onAdd(c, 'primary', '', term); setCode(''); });
  };

  const column = (type, title, hint) => {
    const list = items.filter((i) => i.cart_type === type);
    return (
      <div className="cart-col stack-sm" aria-label={title}>
        <div className="cart-col-head">
          <h3>{title} ({list.length})</h3>
          <span className="hint">{hint}</span>
        </div>
        {list.length === 0 && <p className="hint">Nothing here yet.</p>}
        {list.map((i) => {
          const conflict = (s.conflicts || []).some((c) => c.course_a === i.code || c.course_b === i.code);
          const listed = i.sections || [];
          return (
            <div key={i.code} className={`cart-item stack-xs${conflict ? ' cart-item-conflict' : ''}`}>
              <div className="cart-item-head">
                <span className="num cart-code">{i.code}</span>
                <span className="cart-title">{i.title}</span>
                <span className="chip">{i.approximate ? '~' : ''}{i.credits} cr</span>
                <RiskBadge risk={i.risk} />
                <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label={`Remove ${i.code}`} disabled={Boolean(busy)} onClick={() => remove(i.code)}><X size={14} /></button>
              </div>
              {(i.flags.length > 0 || conflict) && (
                <div className="cart-flags">
                  {conflict && <span className="status status-error"><AlertTriangle size={11} aria-hidden="true" /> Time conflict</span>}
                  {i.flags.map((f) => (
                    <span key={f} className={`status ${FLAG_CLASS[f] || 'status-error'}`}>{FLAG_TEXT[f] || f}</span>
                  ))}
                </div>
              )}
              <label className="visually-hidden" htmlFor={`sec-${i.code}`}>Section of {i.code}</label>
              {listed.length > 0 ? (
                <select id={`sec-${i.code}`} className="input" value={i.section_crn} disabled={Boolean(busy)}
                  onChange={(e) => patch(i.code, { section_crn: e.target.value })}>
                  <option value="">Pick a section…</option>
                  {i.section_crn && !listed.some((x) => String(x.crn) === i.section_crn) && (
                    <option value={i.section_crn}>CRN {i.section_crn} (no longer listed)</option>
                  )}
                  {listed.map((x) => <option key={x.crn} value={String(x.crn)}>{sectionOption(x, i.flags.includes('already_done'))}</option>)}
                </select>
              ) : (
                <span className="hint">No sections listed for {cart.term_name}.</span>
              )}
              {!i.flags.includes('already_done') && <PrereqHint item={i} />}
              <div className="btn-row">
                <label className="visually-hidden" htmlFor={`pri-${i.code}`}>Priority of {i.code}</label>
                <select id={`pri-${i.code}`} className="input cart-priority" value={i.priority || 'want'} disabled={Boolean(busy)}
                  onChange={(e) => patch(i.code, { priority: e.target.value })} title="How much you need this course">
                  {Object.entries(PRIORITY_TEXT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
                <button type="button" className="btn btn-quiet btn-sm" disabled={Boolean(busy)}
                  onClick={() => patch(i.code, { cart_type: type === 'primary' ? 'backup' : 'primary' })}>
                  <ArrowLeftRight size={13} aria-hidden="true" /> Move to {type === 'primary' ? 'backups' : 'primary'}
                </button>
                <button type="button" className="btn btn-gold btn-sm" disabled={Boolean(busy)} onClick={() => launch(i)}
                  title={i.studio_course_id ? 'Open the Studio course made from this class' : 'Make a Studio course (diagnostic and classes) for this class'}>
                  {busy === i.code ? <Loader2 size={13} className="spin" /> : <ArrowRightCircle size={13} aria-hidden="true" />}
                  {i.studio_course_id ? 'Open in Studio' : 'Launch in Studio'}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <section className="panel stack cart" aria-labelledby="cart-h">
      <div className="btn-row cart-top">
        <h2 id="cart-h"><ShoppingCart size={18} aria-hidden="true" /> Planning cart</h2>
        <div className="btn-row">
          <label className="visually-hidden" htmlFor="cart-term">Term</label>
          <select id="cart-term" className="input cart-term" value={term} disabled={Boolean(busy)} onChange={(e) => onLoadTerm(e.target.value)}>
            {(cart.terms || [{ term, term_name: cart.term_name }]).map((t) => <option key={t.term} value={t.term}>{t.term_name}</option>)}
          </select>
          <label className="visually-hidden" htmlFor="cart-year">Class year (optional)</label>
          <select id="cart-year" className="input cart-year" value={classYear} disabled={Boolean(busy)}
            onChange={(e) => saveClassYear(e.target.value)} title="Optional: only used to check class-year seat restrictions">
            <option value="">Class year (optional)</option>
            {CLASS_YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
          <button type="button" className="btn btn-secondary btn-sm" disabled={!items.length || Boolean(busy) || planBusy} onClick={() => { setPlanBusy(true); setPlanWanted((n) => n + 1); }}>
            {planBusy ? <Loader2 size={14} className="spin" /> : <ListOrdered size={14} aria-hidden="true" />} Research my cart
          </button>
          <button type="button" className="btn btn-secondary btn-sm" disabled={!items.length}
            onClick={() => onAsk(`Look at my planning cart for ${cart.term_name}: is the credit load, the schedule and my prerequisites okay? What would you change?`)}>
            <MessageCircle size={14} aria-hidden="true" /> Ask advisor about my cart
          </button>
        </div>
      </div>

      <div className="cart-gauge" role="group" aria-label="Credit load">
        <div className="cart-gauge-line">
          <strong>{s.approximate ? '~' : ''}{credits} credits</strong>
          <span className={`status ${s.load === 'recommended' ? 'status-ready' : s.load === 'overload' || s.load === 'underload' ? 'status-error' : 'status-pending'}`}>
            {LOAD_TEXT[s.load] || ''}
          </span>
        </div>
        <div className="cart-track" aria-hidden="true">
          <div className="cart-band" style={{ left: pct(14), width: pct(2) }} />
          <div className={`cart-fill cart-fill-${s.load}`} style={{ width: pct(credits) }} />
          <div className="cart-mark" style={{ left: pct(12) }} />
          <div className="cart-mark" style={{ left: pct(18) }} />
        </div>
        <span className="hint">Primary courses only. 12 full-time · 14–16 recommended · 18 the normal maximum
          {s.approximate ? ' · ~ means a course lists no fixed credits, so 3 (or the low end) is assumed' : ''}.</span>
      </div>

      {(s.conflicts || []).length > 0 && (
        <div className="notice notice-bad" role="alert">
          <strong><AlertTriangle size={14} aria-hidden="true" /> Time conflicts</strong>
          <ul className="cart-conflicts">{s.conflicts.map((c, n) => <li key={n}>{c.description}</li>)}</ul>
        </div>
      )}

      <form className="btn-row" onSubmit={addCode}>
        <label className="visually-hidden" htmlFor="cart-add">Add a course by code</label>
        <input id="cart-add" className="input cart-add" list="cart-add-options" value={code} onChange={(e) => setCode(e.target.value)}
          placeholder="Add by code, e.g. CSCI 241" autoComplete="off" />
        <datalist id="cart-add-options">
          {options.map((c) => <option key={c.code} value={c.code}>{c.title}</option>)}
        </datalist>
        <button type="submit" className="btn btn-primary btn-sm" disabled={!code.trim() || Boolean(busy)}>
          {busy === 'add' ? <Loader2 size={14} className="spin" /> : <Plus size={14} aria-hidden="true" />} Add to cart
        </button>
      </form>
      {error && <p className="notice notice-bad">{error}</p>}

      {planWanted > 0 && plan && (
        <section className="cart-plan stack-sm" aria-labelledby="cart-plan-h">
          <div className="cart-col-head">
            <h3 id="cart-plan-h"><ListOrdered size={15} aria-hidden="true" /> Registration plan · {plan.term_name}</h3>
            <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label="Close the registration plan" onClick={closePlan}><X size={14} /></button>
          </div>
          <p className="hint">{ESTIMATE_NOTE}</p>
          {plan.order.length === 0 ? <p className="hint">Your cart is empty.</p> : (
            <ol className="cart-plan-list">
              {plan.order.map((o) => (
                <li key={o.code} className="cart-plan-item stack-xs">
                  <div className="cart-plan-head">
                    <span className="num cart-plan-rank">{o.rank}.</span>
                    <span className="num cart-code">{o.code}</span>
                    <span className="cart-title">{o.title}</span>
                    <span className="chip">{PRIORITY_TEXT[o.priority] || o.priority}</span>
                    <RiskBadge risk={o.risk} />
                    {o.cart_type === 'backup' && <span className="status status-planned">Backup</span>}
                  </div>
                  <span className="hint">{o.risk ? `${o.risk.fill_phase} · ${o.risk.confidence} confidence` : 'No estimate available.'}</span>
                  {o.risk?.live && <span className="hint">{liveLine(o.risk.live)}</span>}
                  {(o.risk?.evidence || []).length > 0 && (
                    <ul className="cart-plan-lines">{o.risk.evidence.map((e, n) => <li key={n}>{e}</li>)}</ul>
                  )}
                  {o.advice.length > 0 && (
                    <ul className="cart-plan-lines cart-plan-advice">{o.advice.map((a, n) => <li key={n}>{a}</li>)}</ul>
                  )}
                </li>
              ))}
            </ol>
          )}
          <p className="cart-plan-summary">{plan.summary}</p>
          <div className="btn-row">
            <button type="button" className="btn btn-secondary btn-sm" disabled={!plan.order.length}
              onClick={() => onAsk(`Look at my registration plan for ${plan.term_name}: ${plan.order.map((o) => `${o.rank}. ${o.code} (${o.priority}, risk ${o.risk?.level || 'unknown'})`).join('; ')}. Does this order make sense, and what backups should I add? Remember the seat risk is only an estimate from past schedules.`)}>
              <MessageCircle size={14} aria-hidden="true" /> Ask advisor
            </button>
          </div>
          <p className="hint cart-plan-foot">{plan.estimate_note} Registration plan suggestions never change your cart or pick a section for you.</p>
        </section>
      )}

      <div className="cart-cols">
        {column('primary', 'Primary', 'what you plan to register for')}
        {column('backup', 'Backups', 'alternatives if a class is full')}
      </div>
      <p className="hint">Add courses from the catalog below (+ Cart, + Backup, or Pick this section) or from the advisor's answers.
        Confirm your plan with your official advisor and register in PATH.</p>
    </section>
  );
}
