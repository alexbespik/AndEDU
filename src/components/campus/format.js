// Campus events: shared formatting, paths and the fetch hook. The server sends ISO strings, campus dates
// ("YYYY-MM-DD") and "HH:MM" wall-clock times; everything is shown in campus time, whatever the browser's zone.
import { useEffect, useRef, useState } from 'react';
import { api } from '../../lib/api';

export const CAMPUS_TZ = 'America/New_York';
export const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
export const WEEKDAYS_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
// ids and names of campus_events.CATEGORIES
export const CATEGORIES = [
  { id: 'cs', name: 'Computer Science & Technology' },
  { id: 'arts', name: 'Arts & Museum Exhibitions' },
  { id: 'sports', name: 'Athletics & Recreation' },
  { id: 'bio', name: 'Marine Science & Biology' },
  { id: 'civics', name: 'Civics, History & Dialogue' },
  { id: 'life', name: 'Student Life & RSO Clubs' },
  { id: 'acad', name: 'Academic & Professional' },
];
const CATEGORY_IDS = new Set(CATEGORIES.map((c) => c.id));

const fmt = (opts) => new Intl.DateTimeFormat(undefined, { timeZone: CAMPUS_TZ, ...opts });
const TIME = fmt({ hour: 'numeric', minute: '2-digit' });
const DAY = fmt({ weekday: 'short', month: 'short', day: 'numeric' });
const DATE = fmt({ month: 'short', day: 'numeric' });
const STAMP = fmt({ month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' });
const YMD = /^(\d{4})-(\d{2})-(\d{2})$/;

/** A campus calendar day as an instant inside it (noon UTC is morning of the same day in Williamsburg). */
function dayInstant(ymd) {
  const m = YMD.exec(ymd || '');
  return m ? new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 12)) : null;
}
function instant(iso) {
  if (!iso || YMD.test(iso)) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** "2026-11-16" → "Mon, Nov 16". */
export function dayLabel(ymd) {
  const d = dayInstant(ymd);
  return d ? DAY.format(d) : (ymd || '');
}
/** "2026-11-16" → "Nov 16". */
export function dateLabel(ymd) {
  const d = dayInstant(ymd);
  return d ? DATE.format(d) : (ymd || '');
}
/** "14:30" (campus wall clock) → "2:30 PM". January 1 is always UTC-5 on campus, so the shift is fixed. */
export function hmLabel(hm) {
  const m = /^(\d{1,2}):(\d{2})$/.exec(hm || '');
  return m ? TIME.format(new Date(Date.UTC(2001, 0, 1, Number(m[1]) + 5, Number(m[2])))) : (hm || '');
}
/** An ISO date-time → "Nov 16, 2:30 PM EST". */
export function stampLabel(iso) {
  const d = instant(iso);
  return d ? STAMP.format(d) : '';
}
export function shiftDay(ymd, days) {
  const d = dayInstant(ymd);
  if (!d) return ymd;
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
export function minutesLabel(n) {
  if (typeof n !== 'number' || n < 0) return '';
  if (n < 60) return `${n} min`;
  return n % 60 ? `${Math.floor(n / 60)} h ${n % 60} min` : `${Math.floor(n / 60)} h`;
}

/** When an event runs, in campus time. `day: false` leaves the date out of a single-day event (lists of one day). */
export function eventWhen(ev, { day = true } = {}) {
  const startDay = dayLabel(ev.date);
  if (ev.is_all_day) {
    const end = YMD.test(ev.end_at || '') ? shiftDay(ev.end_at, -1) : null;  // an all-day end is exclusive
    if (ev.is_multi_day && end && end !== ev.date) return `${startDay} – ${dayLabel(end)} · All day`;
    return day ? `${startDay} · All day` : 'All day';
  }
  const start = instant(ev.start_at);
  const end = instant(ev.end_at);
  const from = start ? TIME.format(start) : hmLabel(ev.start_hm);
  if (ev.is_multi_day && end) return `${startDay}, ${from} – ${DAY.format(end)}, ${TIME.format(end)}`;
  const to = end ? TIME.format(end) : hmLabel(ev.end_hm);
  const span = to && to !== from ? `${from} – ${to}` : from;
  return day ? `${startDay} · ${span}` : span;
}

export const categoryClass = (ev) => (CATEGORY_IDS.has(ev?.category?.id) ? `campus-cat-${ev.category.id}` : 'campus-cat-acad');

/** Route prefix of one student's campus data. Event uids never go here: they travel in the query or the body. */
export const campusPath = (userId, rest = '') => `/api/campus/${encodeURIComponent(userId)}${rest}`;
export const icsPath = (userId, params) => `${campusPath(userId, '/export.ics')}?${new URLSearchParams(params)}`;
export const icsName = (title) => `${(title || '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 40) || 'campus_event'}.ics`;

/**
 * GET `path` and follow it: {data, error, loading}. A newer path or `reloadKey` cancels the older request, and a
 * reload keeps the data on screen while it runs. A falsy path asks for nothing.
 */
export function useCampusFetch(path, reloadKey = 0) {
  const [state, setState] = useState({ data: null, error: null, loading: Boolean(path) });
  const shown = useRef(null);  // the path the data on screen came from
  useEffect(() => {
    if (!path) return undefined;
    const ctrl = new AbortController();
    let stale = false;
    setState((s) => ({ ...s, loading: true }));
    api(path, { signal: ctrl.signal })
      .then((data) => { if (!stale) { shown.current = path; setState({ data, error: null, loading: false }); } })
      .catch((e) => {
        if (stale) return;
        // a failed reload keeps what was shown; a failed new query must not leave another query's rows up
        setState((s) => ({ data: shown.current === path ? s.data : null, error: e.message || 'Could not load this.', loading: false }));
      });
    return () => { stale = true; ctrl.abort(); };
  }, [path, reloadKey]);
  return state;
}
