import React, { useState } from 'react';
import { AlertTriangle, Bookmark, BookmarkCheck, CalendarPlus, ExternalLink, Loader2, MapPin } from 'lucide-react';
import { api, downloadFile } from '../../lib/api';
import { campusPath, categoryClass, eventWhen, hmLabel, icsName, icsPath } from './format';

/**
 * One campus event (EventOut). All event text is rendered as text; the source link opens only an https URL.
 * `note`: a short status next to the time ("ends in 20 min"); `children`: extra buttons (alert actions);
 * `compact`: the planner's narrow columns (no description, icon buttons); `onChanged`: called after save/unsave.
 */
export default function EventCard({ event, userId, onChanged, note = null, children = null, compact = false, day = true, saveControl = true }) {
  const [busy, setBusy] = useState(null);  // 'save' | 'ics'
  const [error, setError] = useState(null);

  const toggleSave = async () => {
    setBusy('save'); setError(null);
    try {
      if (event.saved) await api(`${campusPath(userId, '/saved')}?uid=${encodeURIComponent(event.uid)}`, { method: 'DELETE' });
      else await api(campusPath(userId, '/saved'), { method: 'POST', body: { uid: event.uid } });
      onChanged?.();
    } catch (e) { setError(e.message); }
    setBusy(null);
  };
  const download = async () => {
    setBusy('ics'); setError(null);
    try { await downloadFile(icsPath(userId, { uid: event.uid }), icsName(event.title)); }
    catch (e) { setError(e.message); }
    setBusy(null);
  };

  const link = typeof event.source_url === 'string' && event.source_url.startsWith('https://') ? event.source_url : '';
  const calendars = (event.calendars || []).map((c) => c.name).filter(Boolean);
  const SaveIcon = event.saved ? BookmarkCheck : Bookmark;
  const saveLabel = event.saved ? 'Saved' : 'Save';
  return (
    <li className={`campus-event ${categoryClass(event)}`} data-compact={compact || undefined}>
      <span className="campus-event-title">{event.title}</span>
      <div className="campus-event-meta">
        <span className="campus-when">{eventWhen(event, { day })}</span>
        {note && <span className="status status-working">{note}</span>}
        {event.is_ongoing && <span className="status status-pending">Ongoing</span>}
        {event.location && <span><MapPin size={13} aria-hidden="true" /> {event.location}</span>}
      </div>
      {event.conflict && (
        <span className="status status-error">
          <AlertTriangle size={13} aria-hidden="true" /> Clashes with {event.conflict.course_name} ({hmLabel(event.conflict.start_time)} – {hmLabel(event.conflict.end_time)})
        </span>
      )}
      {!compact && event.description && <p className="campus-desc">{event.description}</p>}
      <div className="campus-event-meta">
        <span className="campus-cat">{event.category?.name || 'Academic & Professional'}</span>
        {!compact && calendars.length > 0 && <span className="hint">{calendars.join(' · ')}</span>}
      </div>
      <div className="btn-row">
        {saveControl && (
          <button type="button" className={`btn btn-sm ${event.saved ? 'btn-secondary' : 'btn-quiet'}${compact ? ' btn-icon' : ''}`} disabled={Boolean(busy)}
            aria-pressed={Boolean(event.saved)} aria-label={`${event.saved ? 'Remove from saved' : 'Save'}: ${event.title}`} title={event.saved ? 'Remove from saved' : 'Save to your planner'} onClick={toggleSave}>
            {busy === 'save' ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <SaveIcon size={14} aria-hidden="true" />}{!compact && ` ${saveLabel}`}
          </button>
        )}
        {children}
        <button type="button" className={`btn btn-quiet btn-sm${compact ? ' btn-icon' : ''}`} disabled={Boolean(busy)}
          aria-label={`Add to calendar: ${event.title}`} title="Download an .ics file for your calendar app" onClick={download}>
          {busy === 'ics' ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <CalendarPlus size={14} aria-hidden="true" />}{!compact && ' Add to calendar'}
        </button>
        {link && (
          <a className={`btn btn-quiet btn-sm${compact ? ' btn-icon' : ''}`} href={link} target="_blank" rel="noopener noreferrer"
            aria-label={`Event page (opens in a new tab): ${event.title}`} title="Event page (opens in a new tab)">
            <ExternalLink size={14} aria-hidden="true" />{!compact && ' Event page'}
          </a>
        )}
      </div>
      {error && <p className="notice notice-bad" role="alert">{error}</p>}
    </li>
  );
}
