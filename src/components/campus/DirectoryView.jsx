import React, { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import EventCard from './EventCard';
import { CATEGORIES, campusPath, dayLabel, useCampusFetch } from './format';

const PAGE = 20;

/** Every listed event: search, category, calendar and date filters, paged; save an event or add it to a calendar. */
export default function DirectoryView({ userId, feeds, refresh, onChanged }) {
  const [text, setText] = useState('');
  const [q, setQ] = useState('');  // the debounced search text
  const [category, setCategory] = useState('');
  const [calendar, setCalendar] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => { setQ(text.trim()); setOffset(0); }, 300);
    return () => clearTimeout(t);
  }, [text]);
  const filter = (set) => (e) => { set(e.target.value); setOffset(0); };

  const badRange = Boolean(from && to && to < from);
  const params = new URLSearchParams({ limit: String(PAGE), offset: String(offset) });
  if (q) params.set('q', q);
  if (category) params.set('category', category);
  if (calendar) params.set('calendar', calendar);
  if (from) params.set('from', from);
  if (to) params.set('to', to);
  const { data, error, loading } = useCampusFetch(badRange ? null : `${campusPath(userId, '/events')}?${params}`, refresh);

  const events = data?.events || [];
  const total = data?.total || 0;
  const shownOffset = data?.offset || 0;
  const filtered = Boolean(q || category || calendar || from || to);
  const clear = () => { setText(''); setQ(''); setCategory(''); setCalendar(''); setFrom(''); setTo(''); setOffset(0); };
  return (
    <section className="panel stack" aria-labelledby="campus-dir-h">
      <div className="campus-head">
        <h2 id="campus-dir-h">Event directory</h2>
        {filtered && <button type="button" className="btn btn-quiet btn-sm" onClick={clear}>Clear filters</button>}
      </div>
      <div className="campus-filters">
        <div className="field campus-filter-wide">
          <label htmlFor="campus-q">Search</label>
          <input id="campus-q" type="search" className="input" maxLength={80} value={text} onChange={(e) => setText(e.target.value)} placeholder="Title, place or description" />
        </div>
        <div className="field">
          <label htmlFor="campus-cat">Category</label>
          <select id="campus-cat" className="select" value={category} onChange={filter(setCategory)}>
            <option value="">All categories</option>
            {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="campus-cal">Calendar</label>
          <select id="campus-cal" className="select" value={calendar} onChange={filter(setCalendar)}>
            <option value="">All calendars</option>
            {(feeds || []).map((f) => <option key={f.slug} value={f.slug}>{f.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="campus-from">From</label>
          <input id="campus-from" type="date" className="input" value={from} onChange={filter(setFrom)} />
        </div>
        <div className="field">
          <label htmlFor="campus-to">To</label>
          <input id="campus-to" type="date" className="input" value={to} min={from || undefined} onChange={filter(setTo)} aria-invalid={badRange || undefined} />
        </div>
      </div>
      {badRange && <p className="notice notice-bad" role="alert">The end date is before the start date.</p>}
      {error && <p className="notice notice-bad" role="alert">{error}</p>}
      {!badRange && !data && !error && <p className="hint" role="status"><Loader2 size={13} className="spin" aria-hidden="true" /> Loading events…</p>}

      {!badRange && data && (
        <>
          <p className="hint" role="status">
            {total === 0 ? 'No events' : `${shownOffset + 1}–${shownOffset + events.length} of ${total} event${total === 1 ? '' : 's'}`}
            {' '}from {dayLabel(data.from)} to {dayLabel(data.to)} (at most 90 days at a time; dates are campus time)
            {loading && <> <Loader2 size={12} className="spin" aria-hidden="true" /></>}
          </p>
          {events.length === 0
            ? <p className="hint">{filtered ? 'Nothing matches these filters. Try fewer words or a wider date range.' : 'No upcoming events are listed for these dates.'}</p>
            : <ul className="campus-list">{events.map((ev) => <EventCard key={ev.uid} event={ev} userId={userId} onChanged={onChanged} />)}</ul>}
          {total > PAGE && (
            <nav className="campus-pager" aria-label="Event pages">
              <button type="button" className="btn btn-secondary btn-sm" disabled={shownOffset === 0 || loading} onClick={() => setOffset(Math.max(0, shownOffset - PAGE))}>
                <ChevronLeft size={14} aria-hidden="true" /> Previous
              </button>
              <span className="hint num">Page {Math.floor(shownOffset / PAGE) + 1} of {Math.ceil(total / PAGE)}</span>
              <button type="button" className="btn btn-secondary btn-sm" disabled={shownOffset + PAGE >= total || loading} onClick={() => setOffset(shownOffset + PAGE)}>
                Next <ChevronRight size={14} aria-hidden="true" />
              </button>
            </nav>
          )}
        </>
      )}
    </section>
  );
}
