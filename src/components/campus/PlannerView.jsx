import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, ChevronLeft, ChevronRight, Download, Loader2, Plus, ShoppingCart, Trash2 } from 'lucide-react';
import { api, downloadFile } from '../../lib/api';
import EventCard from './EventCard';
import { WEEKDAYS, WEEKDAYS_SHORT, campusPath, dateLabel, dayLabel, hmLabel, icsPath, shiftDay, useCampusFetch } from './format';

const EXPORTS = [
  { scope: 'saved', label: 'Saved events', file: 'campus_saved.ics' },
  { scope: 'classes', label: 'Classes', file: 'campus_classes.ics' },
  { scope: 'all', label: 'Everything', file: 'campus_calendar.ics' },
];

/** The student's weekly class times: add by hand, copy from the planning cart, delete. */
function ClassManager({ userId, onChanged }) {
  const [classes, setClasses] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(null);  // 'add' | 'cart' | a class id being deleted
  const [name, setName] = useState('');
  const [days, setDays] = useState([]);
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [location, setLocation] = useState('');

  useEffect(() => {
    let stale = false;
    setClasses(null); setError(null);
    api(campusPath(userId, '/classes'))
      .then((d) => { if (!stale) setClasses(d.classes || []); })
      .catch((e) => { if (!stale) { setClasses([]); setError(e.message); } });
    return () => { stale = true; };
  }, [userId]);

  const run = async (tag, work) => {
    setBusy(tag); setError(null); setNotice(null);
    try { const r = await work(); setClasses(r.classes || []); onChanged(); return r; }
    catch (e) { setError(e.message); return null; }
    finally { setBusy(null); }
  };
  const timesOk = Boolean(start && end && start < end);
  const add = async (e) => {
    e.preventDefault();
    const r = await run('add', () => api(campusPath(userId, '/classes'), {
      method: 'POST', body: { course_name: name.trim(), days, start_time: start, end_time: end, location: location.trim() },
    }));
    if (r) { setName(''); setDays([]); setStart(''); setEnd(''); setLocation(''); }
  };
  const importCart = async () => {
    const r = await run('cart', () => api(campusPath(userId, '/classes/import-cart'), { method: 'POST', body: {} }));
    if (!r) return;
    const skipped = r.skipped?.length ? ` Not copied (no section with meeting times chosen): ${r.skipped.join(', ')}.` : '';
    setNotice(r.imported
      ? `Copied ${r.imported} class meeting${r.imported === 1 ? '' : 's'} from your ${r.term_name || r.term} cart.${skipped}`
      : `Your ${r.term_name || r.term} cart has no sections with meeting times yet: pick sections in Courses first.${skipped}`);
  };
  const toggleDay = (d) => setDays((cur) => (cur.includes(d) ? cur.filter((x) => x !== d) : [...cur, d].sort()));

  return (
    <section className="panel stack" aria-labelledby="campus-classes-h">
      <div className="campus-head">
        <h2 id="campus-classes-h">Your classes</h2>
        <button type="button" className="btn btn-secondary btn-sm" disabled={busy !== null} onClick={importCart}>
          {busy === 'cart' ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <ShoppingCart size={14} aria-hidden="true" />} Import from my cart
        </button>
      </div>
      <p className="hint">Class times are used to show what you have today and to mark events that clash. Importing replaces the classes copied from your cart earlier.</p>
      {notice && <p className="notice notice-info" role="status">{notice}</p>}
      {error && <p className="notice notice-bad" role="alert">{error}</p>}
      {classes === null && <p className="hint" role="status"><Loader2 size={13} className="spin" aria-hidden="true" /> Loading your classes…</p>}
      {classes?.length === 0 && !error && <p className="hint">No classes yet.</p>}
      {classes?.length > 0 && (
        <ul className="campus-list">
          {classes.map((c) => (
            <li key={c.id} className="campus-class">
              <strong>{WEEKDAYS_SHORT[c.day_of_week] || ''}</strong>
              <span className="campus-when">{hmLabel(c.start_time)} – {hmLabel(c.end_time)}</span>
              <span>{c.course_name}</span>
              {c.location && <span className="hint">{c.location}</span>}
              {c.source === 'cart' && <span className="status status-pending">From cart</span>}
              <button type="button" className="btn btn-quiet btn-sm btn-icon campus-push" disabled={busy !== null} aria-label={`Delete ${c.course_name}, ${WEEKDAYS[c.day_of_week] || ''}`}
                onClick={() => run(c.id, () => api(campusPath(userId, `/classes/${encodeURIComponent(c.id)}`), { method: 'DELETE' }))}>
                {busy === c.id ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <Trash2 size={14} aria-hidden="true" />}
              </button>
            </li>
          ))}
        </ul>
      )}
      <form className="stack-sm" onSubmit={add}>
        <h3>Add a class</h3>
        <div className="campus-filters">
          <div className="field campus-filter-wide">
            <label htmlFor="campus-class-name">Class name</label>
            <input id="campus-class-name" className="input" maxLength={120} value={name} onChange={(e) => setName(e.target.value)} placeholder="CSCI 241 Data Structures" required />
          </div>
          <div className="field">
            <label htmlFor="campus-class-start">Starts</label>
            <input id="campus-class-start" type="time" className="input" value={start} onChange={(e) => setStart(e.target.value)} required />
          </div>
          <div className="field">
            <label htmlFor="campus-class-end">Ends</label>
            <input id="campus-class-end" type="time" className="input" value={end} onChange={(e) => setEnd(e.target.value)} required aria-invalid={Boolean(start && end && !timesOk) || undefined} />
          </div>
          <div className="field">
            <label htmlFor="campus-class-loc">Location (optional)</label>
            <input id="campus-class-loc" className="input" maxLength={120} value={location} onChange={(e) => setLocation(e.target.value)} />
          </div>
        </div>
        <fieldset className="campus-days">
          <legend className="label">Days</legend>
          <div className="campus-days-row">
            {WEEKDAYS.map((d, i) => (
              <label key={d} className="check-row">
                <input type="checkbox" checked={days.includes(i)} onChange={() => toggleDay(i)} /> {WEEKDAYS_SHORT[i]}<span className="sr-only"> ({d})</span>
              </label>
            ))}
          </div>
        </fieldset>
        {start && end && !timesOk && <p className="hint err">The class must start before it ends.</p>}
        <div className="btn-row">
          <button type="submit" className="btn btn-primary btn-sm" disabled={busy !== null || !name.trim() || !days.length || !timesOk}>
            {busy === 'add' ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <Plus size={14} aria-hidden="true" />} Add class
          </button>
          <span className="hint">Times are campus time (Williamsburg).</span>
        </div>
      </form>
    </section>
  );
}

/** A week of classes and events (saved ones, or everything listed), class management and calendar export. */
export default function PlannerView({ userId, refresh, onChanged }) {
  const [week, setWeek] = useState('');  // '' = the current campus week
  const [scope, setScope] = useState('saved');
  const [local, setLocal] = useState(0);  // classes changed here: reload the week
  const [exporting, setExporting] = useState(null);
  const [exportError, setExportError] = useState(null);
  const params = new URLSearchParams({ scope });
  if (week) params.set('week', week);
  const { data, error, loading } = useCampusFetch(`${campusPath(userId, '/planner')}?${params}`, refresh + local);

  const classesChanged = useCallback(() => { setLocal((n) => n + 1); onChanged(); }, [onChanged]);
  const exportIcs = async ({ scope: s, file }) => {
    setExporting(s); setExportError(null);
    try { await downloadFile(icsPath(userId, { scope: s }), file); }
    catch (e) { setExportError(e.message); }
    setExporting(null);
  };
  const stats = data?.stats;
  return (
    <div className="stack">
      <section className="panel stack" aria-labelledby="campus-week-h">
        <div className="campus-head">
          <h2 id="campus-week-h">{data ? `Week of ${dayLabel(data.week_start)}` : 'Week'}</h2>
          <div className="btn-row">
            <button type="button" className="btn btn-quiet btn-sm" disabled={!data || loading} onClick={() => setWeek(shiftDay(data.week_start, -7))}>
              <ChevronLeft size={14} aria-hidden="true" /> Previous week
            </button>
            <button type="button" className="btn btn-quiet btn-sm" disabled={!week || loading} onClick={() => setWeek('')}>This week</button>
            <button type="button" className="btn btn-quiet btn-sm" disabled={!data || loading} onClick={() => setWeek(shiftDay(data.week_start, 7))}>
              Next week <ChevronRight size={14} aria-hidden="true" />
            </button>
          </div>
        </div>
        <div className="campus-head">
          <div className="btn-row" role="group" aria-label="Events shown">
            <button type="button" className={`btn btn-sm ${scope === 'saved' ? 'btn-primary' : 'btn-quiet'}`} aria-pressed={scope === 'saved'} onClick={() => setScope('saved')}>Saved events</button>
            <button type="button" className={`btn btn-sm ${scope === 'all' ? 'btn-primary' : 'btn-quiet'}`} aria-pressed={scope === 'all'} onClick={() => setScope('all')}>All events</button>
          </div>
          {stats && (
            <div className="btn-row" role="status">
              <span className="status status-pending">{stats.classes} class meeting{stats.classes === 1 ? '' : 's'}</span>
              <span className="status status-pending">{stats.events} event{stats.events === 1 ? '' : 's'}</span>
              <span className={`status ${stats.conflicts ? 'status-error' : 'status-ready'}`}>
                {stats.conflicts > 0 && <AlertTriangle size={13} aria-hidden="true" />} {stats.conflicts} clash{stats.conflicts === 1 ? '' : 'es'}
              </span>
              {loading && <Loader2 size={13} className="spin" aria-hidden="true" />}
            </div>
          )}
        </div>
        {error && <p className="notice notice-bad" role="alert">{error}</p>}
        {!data && !error && <p className="hint" role="status"><Loader2 size={13} className="spin" aria-hidden="true" /> Loading the week…</p>}
        {data && (
          <ol className="campus-week">
            {data.days.map((d) => (
              <li key={d.date} className="campus-day" data-today={d.is_today || undefined}>
                <h3>
                  <span>{WEEKDAYS[d.weekday] || ''}</span>
                  <span className="hint num">{dateLabel(d.date)}</span>
                  {d.is_today && <span className="status status-working">Today</span>}
                </h3>
                {d.classes.length === 0 && d.events.length === 0 && <p className="hint">Nothing planned.</p>}
                {d.classes.length > 0 && (
                  <ul className="campus-list" aria-label={`Classes on ${WEEKDAYS[d.weekday] || d.date}`}>
                    {d.classes.map((c) => (
                      <li key={c.id} className="campus-class">
                        <span className="campus-when">{hmLabel(c.start_time)} – {hmLabel(c.end_time)}</span>
                        <span>{c.course_name}</span>
                        {c.location && <span className="hint">{c.location}</span>}
                      </li>
                    ))}
                  </ul>
                )}
                {d.events.length > 0 && (
                  <ul className="campus-list" aria-label={`Events on ${WEEKDAYS[d.weekday] || d.date}`}>
                    {d.events.map((ev) => <EventCard key={ev.uid} event={ev} userId={userId} onChanged={onChanged} compact day={ev.is_multi_day} />)}
                  </ul>
                )}
                {d.more > 0 && <p className="hint">and {d.more} more: see the Directory for the full day.</p>}
              </li>
            ))}
          </ol>
        )}
        {data && scope === 'saved' && stats?.events === 0 && <p className="hint">No saved events this week. Save events in the Directory, or switch to All events.</p>}
        <div className="btn-row">
          <span className="label">Export to your calendar (.ics):</span>
          {EXPORTS.map((x) => (
            <button key={x.scope} type="button" className="btn btn-secondary btn-sm" disabled={exporting !== null} onClick={() => exportIcs(x)}>
              {exporting === x.scope ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <Download size={14} aria-hidden="true" />} {x.label}
            </button>
          ))}
        </div>
        <p className="hint">"Everything" holds your classes, your saved events and the next 100 listed events.</p>
        {exportError && <p className="notice notice-bad" role="alert">{exportError}</p>}
      </section>
      <ClassManager userId={userId} onChanged={classesChanged} />
    </div>
  );
}
