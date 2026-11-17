import React from 'react';
import { Bell, CalendarDays, ChevronRight, Clock, MapPin } from 'lucide-react';
import { campusPath, categoryClass, eventWhen, hmLabel, minutesLabel, shiftDay, useCampusFetch } from './format';

const MAX_ROWS = 3;

function EventRow({ event, note, day = false }) {
  return (
    <li className={`campus-glance-row ${categoryClass(event)}`}>
      <span className="campus-event-title">{event.title}</span>
      <span className="campus-event-meta">
        <span className="campus-when">{eventWhen(event, { day })}</span>
        {note && <span className="status status-working">{note}</span>}
        {event.location && <span><MapPin size={13} aria-hidden="true" /> {event.location}</span>}
      </span>
    </li>
  );
}

function Column({ icon: Icon, title, more, onOpen, openLabel, children }) {
  return (
    <div className="campus-glance-col">
      <h3><Icon size={15} aria-hidden="true" /> {title}</h3>
      <ul className="campus-list">{children}</ul>
      <button type="button" className="btn btn-quiet btn-sm" onClick={onOpen}>
        {more > 0 ? `${openLabel} (${more} more)` : openLabel} <ChevronRight size={14} aria-hidden="true" />
      </button>
    </div>
  );
}

/**
 * My courses: a short look at campus. What is on now (or starts soon) with the student's current or next class,
 * the saved events of the next seven days, and new interest alerts. Shows nothing when there is nothing to show
 * or the campus data cannot be read, so the home page never depends on it.
 * `alerts`: the unread alerts the app already holds ({alerts, unread_count}); `notify`: false when alerts are off.
 */
export default function CampusGlance({ userId, alerts, notify = true, onOpen }) {
  const now = useCampusFetch(campusPath(userId, '/now'));
  const saved = useCampusFetch(campusPath(userId, '/saved'));
  const data = now.data;
  if (!data) return null;

  const live = data.happening_now || [];
  const soon = data.starting_soon || [];
  const onNow = live.length ? live : soon;
  const klass = data.current_class || data.next_class;
  const today = data.today || '';
  const weekEnd = shiftDay(today, 7);
  const shownNow = new Set(onNow.slice(0, MAX_ROWS).map((e) => e.uid));
  // a saved event counts from its first day to its last: one that began earlier and is still running stays listed
  const lastDay = (e) => (e.is_multi_day && typeof e.end_at === 'string' ? e.end_at.slice(0, 10) : e.date);
  const upcoming = (saved.data?.saved || []).filter((e) => e.date && e.date <= weekEnd && lastDay(e) >= today && !shownNow.has(e.uid));
  const alertRows = notify ? (alerts?.alerts || []) : [];
  const unread = notify ? (alerts?.unread_count || alertRows.length) : 0;
  if (!onNow.length && !klass && !upcoming.length && !unread) return null;

  return (
    <section className="panel campus-glance" aria-labelledby="campus-glance-h">
      <div className="campus-head">
        <h2 id="campus-glance-h"><CalendarDays size={18} aria-hidden="true" /> On campus</h2>
        <button type="button" className="btn btn-secondary btn-sm" onClick={() => onOpen('now')}>Open Campus</button>
      </div>
      <div className="campus-glance-grid">
        {(onNow.length > 0 || klass) && (
          <Column icon={Clock} title={live.length || !soon.length ? 'Happening now' : 'Starting soon'} more={onNow.length - MAX_ROWS}
            onOpen={() => onOpen('now')} openLabel="Today on campus">
            {klass && (
              <li className="campus-class" data-status={klass.status}>
                <strong>{klass.status === 'current' ? 'Current class' : 'Next class'}</strong>
                <span className="campus-when">{hmLabel(klass.start_time)} – {hmLabel(klass.end_time)}</span>
                <span>{klass.course_name}</span>
              </li>
            )}
            {onNow.slice(0, MAX_ROWS).map((ev) => (
              <EventRow key={ev.uid} event={ev} note={typeof ev.minutes_remaining === 'number' ? `${minutesLabel(ev.minutes_remaining)} left`
                : typeof ev.starts_in_minutes === 'number' ? `in ${minutesLabel(ev.starts_in_minutes)}` : null} />
            ))}
            {onNow.length === 0 && <li className="hint">No events right now.</li>}
          </Column>
        )}
        {upcoming.length > 0 && (
          <Column icon={CalendarDays} title="Your saved events this week" more={upcoming.length - MAX_ROWS} onOpen={() => onOpen('planner')} openLabel="Week planner">
            {upcoming.slice(0, MAX_ROWS).map((ev) => <EventRow key={ev.uid} event={ev} day />)}
          </Column>
        )}
        {unread > 0 && (
          <Column icon={Bell} title={`${unread} new alert${unread === 1 ? '' : 's'} for your interests`} more={unread - MAX_ROWS} onOpen={() => onOpen('concierge')} openLabel="See alerts">
            {alertRows.slice(0, MAX_ROWS).map((ev) => <EventRow key={ev.id ?? ev.uid} event={ev} day note={ev.match_reason || null} />)}
          </Column>
        )}
      </div>
    </section>
  );
}
