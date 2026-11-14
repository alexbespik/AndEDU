import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Download, ShieldCheck, Trash2, X } from 'lucide-react';
import { api, authFetch, downloadFile } from '../lib/api';
import { useModalFocus } from '../lib/useModalFocus';

/** Plain-language privacy notice (PRIVACY_AND_DEPLOYMENT.md §3). Used at sign-up, sign-in and in the account menu. */
export function PrivacyNotice({ elevenlabs = false, authRequired = false, local = false }) {
  return (
    <div className="privacy-notice">
      <h3>Stored on this server</h3>
      <p>Your profile, your courses with the text of the materials you upload, lessons, quiz answers, XP and streaks,
        review cards, activity results, and the completed courses and grades you add in the advisor.</p>

      <h3>Sent to Google Gemini</h3>
      <ul>
        <li>Course goals and materials, to write your lessons.</li>
        <li>Images and scanned PDFs, to read the text in them (this includes transcript screenshots).</li>
        <li>Tutor, lesson and advisor chats; the advisor also sees your completed courses and grades.</li>
        <li>Drawings you send for checking, and quiz answers you ask to have explained.</li>
        <li>Text you check with PHILIN (Philosophy), and the claims it fact-checks with Google Search.</li>
      </ul>
      <p>Depending on the Gemini plan this server uses, Google may keep and review what it receives.</p>

      {elevenlabs && (
        <>
          <h3>Sent to ElevenLabs</h3>
          <p>Lesson text, when you play a voiceover or an "Explain it to me" walkthrough (its narration lines, written from the
            lesson), and the words and phrases you play in Languages (Listen and Slow).
            Only that text is sent, never your name or answers; each clip is kept on this server (content/tts_cache) and
            reused for everyone, so a phrase is sent once.</p>
        </>
      )}

      <h3>Your controls</h3>
      <p>Export or delete your data any time from the account menu: <b>Privacy and your data…</b></p>

      <h3>What deletion does not reach</h3>
      <ul>
        <li>Server backups and server logs, until the site administrator rotates them.</li>
        <li>Lessons shared in the library.</li>
        <li>Saved copies of lessons from a course you deleted earlier (they are no longer linked to your profile).</li>
        {!authRequired && !local && <li>On this local install (no accounts), the shared assistant message history.</li>}
      </ul>
      {local ? (
        <p><b>Accounts on this computer:</b> each keeps its own courses and Gemini key, and only the admin of this computer can
          delete an account. The data sits in one folder that anyone signed in to this computer as you can read.</p>
      ) : !authRequired && (
        <p><b>This install has no accounts:</b> anyone using this computer can open, export or delete any profile.</p>
      )}

      <h3>Contact</h3>
      <p>Questions or requests: the site administrator.</p>
    </div>
  );
}

const REMOVED = ['Your profile and sign-in', 'Courses, classes and lessons', 'Quiz answers, XP, streaks and review cards',
  'Activity results', 'Completed courses and grades'];
const KEPT = ['Server backups and logs, until the administrator rotates them', 'Lessons shared in the library', 'Lesson copies from courses you deleted earlier'];

/** Removes this browser's saved data for the user: per-user keys, the profile and the session token. */
function clearLocalData(userId) {
  try {
    // profile, token, the user's own API key, and every key tagged with their id. Untagged keys (language
    // progress, layout choices) belong to whoever uses this browser, so they stay.
    const drop = ['andedu_lab_profile', 'andedu_lab_token', 'andedu_elevenlabs_key'];
    for (let i = 0; i < localStorage.length; i += 1) {
      const k = localStorage.key(i);
      if (k && k.startsWith('andedu_') && userId && k.includes(userId)) drop.push(k);
    }
    drop.forEach((k) => localStorage.removeItem(k));
  } catch { /* storage blocked: nothing saved to clear */ }
}

/** Account menu dialog: the notice, "Export my data" and "Delete my account and data". */
export function PrivacyDialog({ open, onClose, user, returnFocus }) {
  const [status, setStatus] = useState(null);
  const [confirmName, setConfirmName] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [passError, setPassError] = useState(null);
  const [hasPassword, setHasPassword] = useState(false);  // accounts on this computer: only then is the password asked
  const panel = useRef(null);
  // accounts on this computer: only the admin deletes accounts, and hands the role on before deleting its own
  const local = Boolean(user?.local);
  const [isAdmin, setIsAdmin] = useState(false);
  const [others, setOthers] = useState([]);  // the admin's list: who can take the role
  const [transferTo, setTransferTo] = useState('');
  useModalFocus(open, panel, onClose, returnFocus);

  useEffect(() => {
    if (!open) return undefined;
    let active = true;
    setConfirmName(''); setPassword(''); setError(null); setPassError(null); setBusy(null); setHasPassword(false);
    setIsAdmin(false); setOthers([]); setTransferTo('');
    api('/api/status').then((st) => { if (active) setStatus(st); }).catch(() => { if (active) setError('The backend is offline.'); });
    if (local) {
      api('/api/auth/me').then((me) => {
        if (!active) return;
        setHasPassword(Boolean(me.hasPassword));
        setIsAdmin(Boolean(me.isAdmin));
        if (me.isAdmin) {
          api('/api/auth/accounts').then((list) => { if (active) setOthers((list || []).filter((a) => a.id !== user?.id)); }).catch(() => {});
        }
      }).catch(() => {});
    }
    return () => { active = false; };
  }, [open, local, user?.id]);

  if (!open || !user) return null;
  const authRequired = Boolean(status?.auth_required);
  const nameOk = confirmName.trim() === (user.name || '').trim() && confirmName.trim() !== '';
  const askPassword = authRequired || (local && hasPassword);
  const needsTransfer = local && others.length > 0;
  const canDelete = Boolean(status) && nameOk && (!askPassword || password) && (!needsTransfer || transferTo) && !busy
    && (!local || isAdmin);

  const exportData = async () => {
    setBusy('export'); setError(null);
    const safe = (user.name || 'profile').replace(/[^\w-]+/g, '_');
    try { await downloadFile(`/api/users/${encodeURIComponent(user.id)}/export`, `andedu-${safe}-data.json`); }
    catch (e) { setError(e.message); }
    setBusy(null);
  };

  const deleteAccount = async (e) => {
    e.preventDefault();
    if (!canDelete) return;
    setBusy('delete'); setError(null); setPassError(null);
    const [path, body] = authRequired || local
      ? ['/api/auth/delete-account', {
        confirmName: confirmName.trim(), ...(askPassword ? { password } : {}), ...(needsTransfer ? { transferTo } : {}),
      }]
      : [`/api/users/${encodeURIComponent(user.id)}/delete`, { confirmName: confirmName.trim() }];
    try {
      const res = await authFetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      let data = null;
      try { data = await res.json(); } catch { /* empty body */ }
      if (!res.ok) {
        const detail = data?.detail;
        const msg = Array.isArray(detail) ? detail.map((d) => d.msg).join('; ') : detail;
        if (res.status === 401 && msg !== 'Wrong password') {  // the session itself expired: sign out like api() does
          window.dispatchEvent(new Event('andedu:signed-out'));
          setBusy(null);
          return;
        }
        if (res.status === 401) { setHasPassword(true); setPassError('Wrong password'); }  // the field shows if it was hidden
        else if (res.status === 422) setError(msg || 'The name you typed does not match this profile.');
        else if (res.status === 409 || res.status === 403) setError(msg || 'Admin accounts cannot be deleted here. Ask the site administrator.');
        else setError(msg || `Delete failed (HTTP ${res.status})`);
        setBusy(null);
        return;
      }
      clearLocalData(user.id);
      window.dispatchEvent(new Event('andedu:signed-out'));
    } catch (err) {
      setError(err.message || 'Delete failed.');
      setBusy(null);
    }
  };

  return createPortal(
    <div className="privacy-scrim" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div ref={panel} className="panel privacy-dialog" role="dialog" aria-modal="true" aria-labelledby="privacy-title" tabIndex={-1}>
        <div className="privacy-head">
          <h2 id="privacy-title"><ShieldCheck size={18} aria-hidden="true" /> Privacy and your data</h2>
          <button type="button" className="btn btn-quiet btn-sm btn-icon" onClick={onClose} aria-label="Close privacy dialog">
            <X size={16} aria-hidden="true" />
          </button>
        </div>

        <PrivacyNotice elevenlabs={Boolean(status?.elevenlabs_enabled)} authRequired={authRequired} local={local} />
        {status?.privacy_version && <p className="hint">Notice version {status.privacy_version}</p>}

        <section className="stack-sm" aria-labelledby="privacy-export-h">
          <h3 id="privacy-export-h">Export my data</h3>
          <p className="hint">Downloads everything this server stores for {user.name} as one JSON file.</p>
          <div className="btn-row">
            <button type="button" className="btn btn-secondary btn-sm" onClick={exportData} disabled={Boolean(busy)}>
              <Download size={14} aria-hidden="true" /> {busy === 'export' ? 'Preparing…' : 'Export my data'}
            </button>
          </div>
        </section>

        {local && !isAdmin ? (
          <section className="privacy-danger stack-sm" aria-labelledby="privacy-delete-h">
            <h3 id="privacy-delete-h">Delete my account and data</h3>
            <p className="hint">Only the admin of this computer can delete accounts. Ask them to delete yours from their account
              menu (Accounts on this computer).</p>
          </section>
        ) : (
        <form className="privacy-danger stack-sm" onSubmit={deleteAccount} aria-labelledby="privacy-delete-h">
          <h3 id="privacy-delete-h">Delete my account and data</h3>
          <div className="privacy-lists">
            <div>
              <span className="label">Removed</span>
              <ul>{REMOVED.map((t) => <li key={t}>{t}</li>)}</ul>
            </div>
            <div>
              <span className="label">Not removed</span>
              <ul>
                {KEPT.map((t) => <li key={t}>{t}</li>)}
                {status && !authRequired && !local && <li>The shared assistant message history on this computer</li>}
              </ul>
            </div>
          </div>
          <p className="hint">This cannot be undone. You will be signed out.</p>
          <div className="field">
            <label htmlFor="privacy-confirm">Type your name, <b>{user.name}</b>, to confirm</label>
            <input id="privacy-confirm" className="input" value={confirmName} onChange={(e) => setConfirmName(e.target.value)} autoComplete="off" />
          </div>
          {askPassword && (
            <div className="field">
              <label htmlFor="privacy-pass">Password</label>
              <input id="privacy-pass" className="input" type="password" value={password} autoComplete="current-password"
                onChange={(e) => { setPassword(e.target.value); setPassError(null); }}
                aria-invalid={Boolean(passError)} aria-describedby={passError ? 'privacy-pass-err' : undefined} />
              {passError && <span id="privacy-pass-err" className="hint err" role="alert">{passError}</span>}
            </div>
          )}
          {needsTransfer && (
            <div className="field">
              <label htmlFor="privacy-transfer">You are the admin of this computer. Hand the role to</label>
              <select id="privacy-transfer" className="select" value={transferTo} onChange={(e) => setTransferTo(e.target.value)}>
                <option value="">Choose an account…</option>
                {others.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
              <span className="hint">They can then delete accounts and change the shared library.</span>
            </div>
          )}
          <div className="btn-row">
            <button type="submit" className="btn btn-danger" disabled={!canDelete}>
              <Trash2 size={14} aria-hidden="true" /> {busy === 'delete' ? 'Deleting…' : 'Delete my account and data'}
            </button>
          </div>
        </form>
        )}

        {error && <p className="notice notice-bad" role="alert">{error}</p>}
      </div>
    </div>,
    document.body,
  );
}
