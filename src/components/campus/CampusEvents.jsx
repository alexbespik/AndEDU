import React, { useCallback, useState } from 'react';
import { Bell, CalendarDays, Clock, List, Loader2, RefreshCw } from 'lucide-react';
import { api } from '../../lib/api';
import NowView from './NowView';
import DirectoryView from './DirectoryView';
import PlannerView from './PlannerView';
import ConciergeView from './ConciergeView';
import { campusPath, stampLabel, useCampusFetch } from './format';

const TABS = [
  { id: 'now', label: 'Now', icon: Clock },
  { id: 'directory', label: 'Directory', icon: List },
  { id: 'planner', label: 'Planner', icon: CalendarDays },
  { id: 'concierge', label: 'Concierge', icon: Bell },
];

function syncMessage(e) {
  if (e.status === 409) return 'A calendar refresh is already running. Check back in a minute.';
  if (e.status === 429) return e.message || 'The calendars were refreshed a moment ago. Try again in a few minutes.';
  if (e.status === 403) return 'Only the administrator can refresh the campus calendars.';
  return e.message || 'The calendars could not be refreshed.';
}

/** W&M campus events inside the advisor: what is on now, the full directory, a week planner and interest alerts. */
export default function CampusEvents({ user }) {
  const userId = user.id;
  const [tab, setTab] = useState('now');
  const [visited, setVisited] = useState(() => new Set(['now']));  // a visited tab stays mounted (filters, drafts)
  const [refresh, setRefresh] = useState(0);  // bump: saved events, classes, alerts or the calendars changed
  const [statusKey, setStatusKey] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const [syncNote, setSyncNote] = useState(null);  // {ok, text}
  const [notifyNow, setNotifyNow] = useState(null);  // the notify setting just saved in Concierge

  const status = useCampusFetch('/api/campus/status', statusKey);
  const unread = useCampusFetch(`${campusPath(userId, '/alerts')}?unread_only=1`, refresh);
  const intent = useCampusFetch(campusPath(userId, '/intent'));
  const changed = useCallback(() => setRefresh((n) => n + 1), []);
  // a sync started elsewhere (the automatic one, another admin): keep checking until it ends, then reload the views
  const remoteSync = Boolean(status.data?.sync_running) && !syncing;
  useEffect(() => {
    if (!remoteSync) return undefined;
    const timer = setInterval(() => setStatusKey((n) => n + 1), 5000);
    return () => { clearInterval(timer); setRefresh((n) => n + 1); };
  }, [remoteSync]);
  const onIntent = useCallback((r) => setNotifyNow(r.notify !== false), []);

  const open = (id) => { setTab(id); setVisited((cur) => (cur.has(id) ? cur : new Set(cur).add(id))); };
  const sync = async () => {
    setSyncing(true); setSyncNote(null);
    try {
      const r = await api('/api/campus/sync', { method: 'POST' });
      const feeds = `${r.feeds_ok} calendar${r.feeds_ok === 1 ? '' : 's'} read${r.feeds_failed ? `, ${r.feeds_failed} could not be read` : ''}`;
      setSyncNote(r.status === 'failed'
        ? { ok: false, text: 'No calendar could be read. Check the internet connection and try again later.' }
        : { ok: true, text: `Calendars refreshed: ${feeds}, ${r.total_events} events listed${r.new_alerts ? `, ${r.new_alerts} new alert${r.new_alerts === 1 ? '' : 's'}` : ''}.` });
      changed();
    } catch (e) { setSyncNote({ ok: false, text: syncMessage(e) }); }
    setStatusKey((n) => n + 1);
    setSyncing(false);
  };

  const s = status.data;
  const notify = notifyNow ?? (intent.data ? intent.data.notify !== false : true);
  const unreadCount = notify ? (unread.data?.unread_count || 0) : 0;
  const running = syncing || Boolean(s?.sync_running);
  return (
    <div className="campus">
      <div className="campus-head">
        <div className="stack-xs">
          <h2>Campus events</h2>
          <span className="hint" role="status">
            {status.loading && !s ? <><Loader2 size={13} className="spin" aria-hidden="true" /> Checking the calendars…</>
              : s ? `${s.total_events} event${s.total_events === 1 ? '' : 's'} · ${s.last_sync ? `last refreshed ${stampLabel(s.last_sync)}` : 'never refreshed'}`
                + `${s.last_result?.feeds_failed ? ` · ${s.last_result.feeds_failed} calendar${s.last_result.feeds_failed === 1 ? '' : 's'} failed last time` : ''}`
                + `${s.auto_sync_hours > 0 ? ` · refreshes automatically every ${s.auto_sync_hours} h` : ''} · times are campus time`
                : ''}
          </span>
        </div>
        {s?.can_sync && (
          <button type="button" className="btn btn-secondary btn-sm" disabled={running} onClick={sync}>
            {running ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <RefreshCw size={14} aria-hidden="true" />} {running ? 'Syncing…' : 'Sync'}
          </button>
        )}
      </div>
      {status.error && <p className="notice notice-bad" role="alert">{status.error}</p>}
      {syncNote && <p className={`notice ${syncNote.ok ? 'notice-ok' : 'notice-bad'}`} role={syncNote.ok ? 'status' : 'alert'}>{syncNote.text}</p>}
      {s && s.total_events === 0 && (
        <div className="panel stack-sm campus-empty">
          <h3>No events yet</h3>
          <p>
            Events come from W&amp;M's public calendars and have to be downloaded with a sync first.{' '}
            {s.can_sync ? 'Press Sync to download them now (it takes up to a minute).'
              : s.auto_sync_hours > 0 ? 'The next automatic refresh will bring them in.'
                : 'Ask the administrator of this &.edu to run a sync.'}
          </p>
          <p className="hint">You can already add your classes in Planner and describe your interests in Concierge.</p>
        </div>
      )}

      <div className="tabs" role="tablist" aria-label="Campus events tools">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button key={id} type="button" role="tab" id={`campus-tab-${id}`} aria-selected={tab === id} aria-controls={`campus-panel-${id}`} className="tab" onClick={() => open(id)}>
            <Icon size={16} aria-hidden="true" /> {label}
            {id === 'concierge' && unreadCount > 0 && <span className="count" aria-label={`${unreadCount} new alert${unreadCount === 1 ? '' : 's'}`}>{unreadCount}</span>}
          </button>
        ))}
      </div>
      {TABS.filter(({ id }) => visited.has(id)).map(({ id }) => (
        <section key={id} role="tabpanel" id={`campus-panel-${id}`} aria-labelledby={`campus-tab-${id}`} hidden={tab !== id}>
          {id === 'now' && <NowView userId={userId} refresh={refresh} onChanged={changed} active={tab === 'now'} />}
          {id === 'directory' && <DirectoryView userId={userId} feeds={s?.feeds} refresh={refresh} onChanged={changed} />}
          {id === 'planner' && <PlannerView userId={userId} refresh={refresh} onChanged={changed} />}
          {id === 'concierge' && <ConciergeView userId={userId} refresh={refresh} onChanged={changed} onIntent={onIntent} />}
        </section>
      ))}
    </div>
  );
}
