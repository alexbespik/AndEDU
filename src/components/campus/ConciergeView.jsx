import React, { useEffect, useState } from 'react';
import { Check, Loader2, Sparkles, X } from 'lucide-react';
import { api } from '../../lib/api';
import EventCard from './EventCard';
import { campusPath, stampLabel, useCampusFetch } from './format';

const MAX_PROMPT = 500;

/** Interest concierge: the student describes what they like; matching events arrive as alerts to add or dismiss. */
export default function ConciergeView({ userId, refresh, onChanged, onIntent }) {
  const [intent, setIntent] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [prompt, setPrompt] = useState('');
  const [autoAdd, setAutoAdd] = useState(false);
  const [notify, setNotify] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [acting, setActing] = useState(null);  // an alert id
  const [actError, setActError] = useState(null);
  const alerts = useCampusFetch(campusPath(userId, '/alerts'), refresh);

  useEffect(() => {
    let stale = false;
    setIntent(null); setLoadError(null);
    api(campusPath(userId, '/intent'))
      .then((d) => {
        if (stale) return;
        setIntent(d); setPrompt(d.prompt || ''); setAutoAdd(Boolean(d.auto_add)); setNotify(d.notify !== false);
      })
      .catch((e) => { if (!stale) setLoadError(e.message); });
    return () => { stale = true; };
  }, [userId]);

  const save = async (e) => {
    e.preventDefault();
    setSaving(true); setSaveError(null); setNotice(null);
    try {
      const r = await api(campusPath(userId, '/intent'), { method: 'PUT', body: { prompt: prompt.trim(), auto_add: autoAdd, notify } });
      setIntent(r); setPrompt(r.prompt || ''); setAutoAdd(Boolean(r.auto_add)); setNotify(r.notify !== false);
      onIntent(r);
      setNotice(r.prompt
        ? `Saved. ${r.matched_count} upcoming event${r.matched_count === 1 ? '' : 's'} match, ${r.new_alerts} new alert${r.new_alerts === 1 ? '' : 's'}`
          + `${r.auto_added_count ? `, ${r.auto_added_count} added to your saved events` : ''}.`
        : 'Saved. With no interests written, no new alerts will be made.');
      onChanged();
    } catch (err) { setSaveError(err.message); }
    setSaving(false);
  };
  const act = async (alert, action) => {
    setActing(alert.id); setActError(null);
    try { await api(campusPath(userId, `/alerts/${encodeURIComponent(alert.id)}`), { method: 'POST', body: { action } }); onChanged(); }
    catch (err) { setActError(err.message); }
    setActing(null);
  };

  const dirty = intent && (prompt.trim() !== (intent.prompt || '') || autoAdd !== Boolean(intent.auto_add) || notify !== (intent.notify !== false));
  const list = alerts.data?.alerts || [];
  return (
    <div className="stack">
      <section className="panel stack" aria-labelledby="campus-intent-h">
        <h2 id="campus-intent-h"><Sparkles size={18} aria-hidden="true" /> Your interests</h2>
        {loadError && <p className="notice notice-bad" role="alert">{loadError}</p>}
        {!intent && !loadError && <p className="hint" role="status"><Loader2 size={13} className="spin" aria-hidden="true" /> Loading your interests…</p>}
        {intent && (
          <form className="stack-sm" onSubmit={save}>
            <div className="field">
              <label htmlFor="campus-intent">What kind of events do you want to hear about?</label>
              <textarea id="campus-intent" className="textarea campus-intent" rows={3} maxLength={MAX_PROMPT} value={prompt} onChange={(e) => setPrompt(e.target.value)}
                placeholder="For example: robotics talks, choir concerts, anything about marine biology" aria-describedby="campus-intent-ai campus-intent-count" />
              <span id="campus-intent-count" className="hint num">{prompt.length}/{MAX_PROMPT}</span>
            </div>
            <p id="campus-intent-ai" className="notice notice-info" role="note">
              <strong>This text is sent to the AI model.</strong> When you save, what you wrote here goes to Google Gemini once, so it can pick
              search keywords. Don't write anything private. Event listings and your classes are never sent; later calendar refreshes reuse the
              stored keywords without calling the model.
            </p>
            <label className="check-row">
              <input type="checkbox" checked={autoAdd} onChange={(e) => setAutoAdd(e.target.checked)} /> Add matching events to my saved events automatically
            </label>
            <label className="check-row">
              <input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} /> Show the number of new alerts on the Concierge tab
            </label>
            <div className="btn-row">
              <button type="submit" className="btn btn-primary btn-sm" disabled={saving || !dirty}>
                {saving ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <Check size={14} aria-hidden="true" />} Save interests
              </button>
              {saving && <span className="hint" role="status">Picking keywords and matching events…</span>}
            </div>
            {saveError && <p className="notice notice-bad" role="alert">{saveError}</p>}
            {notice && <p className="notice notice-ok" role="status">{notice}</p>}
            {intent.prompt && (
              <div className="stack-sm">
                <span className="label">Keywords in use ({intent.keywords?.length || 0})</span>
                {intent.keywords?.length > 0
                  ? <ul className="campus-keywords">{intent.keywords.map((k) => <li key={k} className="chip">{k}</li>)}</ul>
                  : <span className="hint">No usable keywords came out of this text: try naming topics or activities.</span>}
                <span className="hint">
                  Source: {intent.keyword_source === 'gemini' ? 'your words, expanded by the AI model' : 'taken from your own words (the AI model was not used or did not answer)'}
                  {intent.updated_at ? ` · saved ${stampLabel(intent.updated_at)}` : ''}
                </span>
              </div>
            )}
          </form>
        )}
      </section>

      <section className="panel stack-sm" aria-labelledby="campus-alerts-h">
        <div className="campus-head">
          <h2 id="campus-alerts-h">Alerts <span className="hint num">({list.length})</span></h2>
          {alerts.data && <span className="hint" role="status">{alerts.data.unread_count} not added yet{alerts.loading && <> <Loader2 size={12} className="spin" aria-hidden="true" /></>}</span>}
        </div>
        {alerts.error && <p className="notice notice-bad" role="alert">{alerts.error}</p>}
        {actError && <p className="notice notice-bad" role="alert">{actError}</p>}
        {!alerts.data && !alerts.error && <p className="hint" role="status"><Loader2 size={13} className="spin" aria-hidden="true" /> Loading alerts…</p>}
        {alerts.data && list.length === 0 && (
          <p className="hint">No alerts. Upcoming events (the next 30 days) that match your keywords appear here after you save your interests and after each calendar refresh.</p>
        )}
        {list.length > 0 && (
          <ul className="campus-list">
            {list.map((a) => (
              <EventCard key={a.id} event={a} userId={userId} onChanged={onChanged} saveControl={false} note={a.match_reason || null}>
                {a.is_added
                  ? <span className="status status-ready"><Check size={13} aria-hidden="true" /> Saved</span>
                  : (
                    <button type="button" className="btn btn-primary btn-sm" disabled={acting !== null} aria-label={`Add to saved events: ${a.title}`} onClick={() => act(a, 'add')}>
                      {acting === a.id ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <Check size={14} aria-hidden="true" />} Add
                    </button>
                  )}
                <button type="button" className="btn btn-quiet btn-sm" disabled={acting !== null} aria-label={`Dismiss alert: ${a.title}`} onClick={() => act(a, 'dismiss')}>
                  <X size={14} aria-hidden="true" /> Dismiss
                </button>
              </EventCard>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
