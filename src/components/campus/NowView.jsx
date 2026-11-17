import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import EventCard from './EventCard';
import { campusPath, dayLabel, hmLabel, minutesLabel, useCampusFetch } from './format';

function classNote(c) {
  if (c.status === 'current') return `Now · ${minutesLabel(c.minutes_remaining)} left`;
  if (c.status === 'upcoming') return `In ${minutesLabel(c.minutes_until_start)}`;
  return 'Done';
}

function ClassLine({ item, lead }) {
  return (
    <li className="campus-class" data-status={item.status}>
      {lead && <strong>{lead}</strong>}
      <span className="campus-when">{hmLabel(item.start_time)} – {hmLabel(item.end_time)}</span>
      <span>{item.course_name}</span>
      {item.location && <span className="hint">{item.location}</span>}
      <span className={`status ${item.status === 'current' ? 'status-ready' : item.status === 'upcoming' ? 'status-working' : 'status-pending'}`}>{classNote(item)}</span>
    </li>
  );
}

function EventSection({ id, title, empty, events, userId, onChanged, note }) {
  return (
    <section className="panel stack-sm" aria-labelledby={id}>
      <h2 id={id}>{title} <span className="hint num">({events.length})</span></h2>
      {events.length === 0
        ? <p className="hint">{empty}</p>
        : <ul className="campus-list">{events.map((ev) => <EventCard key={ev.uid} event={ev} userId={userId} onChanged={onChanged} day={false} note={note?.(ev)} />)}</ul>}
    </section>
  );
}

/** Today on campus: the class you are in or the next one, and today's events by how soon they start. */
export default function NowView({ userId, refresh, onChanged, active = true }) {
  const [tick, setTick] = useState(0);
  // the minute counters go stale quickly: reload each minute while the page is visible
  useEffect(() => {
    if (!active) return undefined;
    const t = setInterval(() => { if (!document.hidden) setTick((n) => n + 1); }, 60000);
    return () => clearInterval(t);
  }, [active]);
  const { data, error, loading } = useCampusFetch(campusPath(userId, '/now'), refresh + tick);

  if (!data) {
    return error
      ? <p className="notice notice-bad" role="alert">{error}</p>
      : <p className="hint" role="status"><Loader2 size={13} className="spin" aria-hidden="true" /> Loading today…</p>;
  }
  const { current_class: current, next_class: next } = data;
  const classes = data.today_classes || [];
  return (
    <div className="stack">
      {error && <p className="notice notice-bad" role="alert">{error}</p>}
      <section className="panel stack-sm" aria-labelledby="campus-now-classes">
        <div className="campus-head">
          <h2 id="campus-now-classes">Your classes today</h2>
          <span className="hint">{dayLabel(data.today)}{loading && <> <Loader2 size={12} className="spin" aria-hidden="true" /></>}</span>
        </div>
        {classes.length === 0 ? (
          <p className="hint">No classes today. Add your class times in Planner to see them here and to spot clashes with events.</p>
        ) : (
          <>
            <ul className="campus-list">
              {current && <ClassLine item={current} lead="Current class" />}
              {next && <ClassLine item={next} lead="Next class" />}
              {!current && !next && <li className="hint">Your classes are done for today.</li>}
            </ul>
            <details>
              <summary className="label">All of today ({classes.length})</summary>
              <ul className="campus-list campus-list-gap">{classes.map((c) => <ClassLine key={c.id} item={c} />)}</ul>
            </details>
          </>
        )}
      </section>
      <EventSection id="campus-now-on" title="Happening now" empty="Nothing is on right now." events={data.happening_now || []} userId={userId} onChanged={onChanged}
        note={(ev) => (typeof ev.minutes_remaining === 'number' ? `${minutesLabel(ev.minutes_remaining)} left` : null)} />
      <EventSection id="campus-now-soon" title="Starting soon" empty="Nothing starts in the next three hours." events={data.starting_soon || []} userId={userId} onChanged={onChanged}
        note={(ev) => (typeof ev.starts_in_minutes === 'number' ? `in ${minutesLabel(ev.starts_in_minutes)}` : null)} />
      <EventSection id="campus-now-later" title="Later today" empty="Nothing else is listed for today." events={data.later_today || []} userId={userId} onChanged={onChanged} />
    </div>
  );
}
