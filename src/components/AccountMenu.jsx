import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronDown, KeyRound, Lock, LogOut, ShieldCheck, Users, Wifi, WifiOff } from 'lucide-react';
import ThemeSwitch from './ThemeSwitch';
import { PrivacyDialog } from './PrivacyCenter';
import LocalAccountsDialog from './LocalAccountsDialog';
import { api } from '../lib/api';

/** One button for the account: name, theme, connection and sign out live in its menu. */
export default function AccountMenu({ user, online, onSignOut }) {
  const [open, setOpen] = useState(false);
  const [privacyOpen, setPrivacyOpen] = useState(false);
  const [accountsOpen, setAccountsOpen] = useState(false);  // the admin's accounts on this computer
  // the saved profile is only {id, name}, so the account type comes from the server
  const [authRequired, setAuthRequired] = useState(null);
  const wrap = useRef(null);
  const btn = useRef(null);  // focus returns here when the privacy dialog closes (the menu item is gone by then)
  // accounts on this computer (user.local): /api/auth/me, refreshed each time the menu opens
  const local = Boolean(user?.local);
  const [me, setMe] = useState(null);
  const [pwForm, setPwForm] = useState(null);  // null | 'set' | 'remove'
  const [pw, setPw] = useState({ current: '', next: '', again: '' });
  const [pwBusy, setPwBusy] = useState(false);
  const [pwError, setPwError] = useState(null);
  const [acctNote, setAcctNote] = useState(null);  // the outcome of a password change (e.g. the key was removed)

  useEffect(() => {
    if (!open || authRequired !== null) return;
    api('/api/status').then((st) => setAuthRequired(Boolean(st.auth_required))).catch(() => {});
  }, [open, authRequired]);

  const loadMe = useCallback(() => {
    api('/api/auth/me').then((d) => { if (d.user) setMe(d); }).catch(() => {});
  }, []);
  useEffect(() => { if (open && local) loadMe(); }, [open, local, loadMe]);
  useEffect(() => { if (!open) { setPwForm(null); setPw({ current: '', next: '', again: '' }); setPwError(null); } }, [open]);

  const changed = () => { loadMe(); window.dispatchEvent(new Event('andedu:account-changed')); };

  const submitPassword = async (e) => {
    e.preventDefault();
    setPwBusy(true); setPwError(null); setAcctNote(null);
    const removing = pwForm === 'remove';
    try {
      const res = await api('/api/auth/password', {
        method: 'POST',
        body: { ...(me?.hasPassword ? { current: pw.current } : {}), ...(removing ? {} : { new: pw.next }) },
      });
      setAcctNote(res.keyRemoved ? res.message
        : removing ? 'Password removed. Anyone using this computer can open this account.'
          : me?.hasPassword ? 'Password changed.' : 'Password set. It will be asked for at each sign-in.');
      setPwForm(null); setPw({ current: '', next: '', again: '' });
      changed();
    } catch (err) {
      setPwError(err.message);
    }
    setPwBusy(false);
  };

  const setAutoLock = (minutes) => {
    api('/api/auth/prefs', { method: 'PUT', body: { autoLockMin: minutes } }).then(changed).catch((err) => setAcctNote(err.message));
  };

  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (!wrap.current?.contains(e.target)) setOpen(false); };
    const esc = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc); };
  }, [open]);

  if (!user) return null;
  const initial = (user.name || '?').trim().charAt(0).toUpperCase();
  return (
    <div className="account" ref={wrap}>
      <button ref={btn} type="button" className="account-btn" aria-haspopup="true" aria-expanded={open} onClick={() => setOpen((o) => !o)}
        title={online ? user.name : `${user.name} · backend offline`}>
        <span className="avatar" aria-hidden="true">{initial}<span className="avatar-dot" data-online={online} /></span>
        <span className="account-name">{user.name}</span>
        <ChevronDown size={14} aria-hidden="true" />
      </button>
      {open && (
        <div className="account-menu" role="menu">
          <div className="account-head">
            <span className="avatar avatar-lg" aria-hidden="true">{initial}</span>
            <div>
              <strong>{user.name}</strong>
              <span className="hint">{local ? 'Account on this computer' : authRequired === null ? '' : authRequired ? 'Account' : 'Profile on this computer'}</span>
              {local
                ? me?.isAdmin && <span className="hint">Admin of this computer</span>
                : <span className="hint" title="Put this id in SCIEDU_ADMINS to make this account an admin">id <code>{user.id}</code></span>}
            </div>
          </div>
          <div className="account-row">
            <span className="hint">Theme</span>
            <ThemeSwitch />
          </div>
          <div className="account-row" role="status">
            <span className="hint">Server</span>
            <span className="conn-pill" data-state={online ? 'online' : 'offline'}>
              {online ? <Wifi size={13} aria-hidden="true" /> : <WifiOff size={13} aria-hidden="true" />} {online ? 'Connected' : 'Offline'}
            </span>
          </div>
          {local && me?.modelCallsLeft != null && (
            <div className="account-row" role="status">
              <span className="hint">Model calls left today</span>
              <span>{me.modelCallsLeft}</span>
            </div>
          )}
          {(local || window.sciedu?.isDesktop) && (
            <button type="button" role="menuitem" className="account-item"
              onClick={() => { setOpen(false); window.dispatchEvent(new CustomEvent('sciedu:key-setup')); }}>
              <KeyRound size={15} aria-hidden="true" /> {local ? 'My Gemini key…' : 'Gemini API key…'}
            </button>
          )}
          {local && me && (
            <>
              {me.hasPassword && (
                <button type="button" role="menuitem" className="account-item"
                  onClick={() => { setOpen(false); window.dispatchEvent(new Event('andedu:lock')); }}>
                  <Lock size={15} aria-hidden="true" /> Lock now
                </button>
              )}
              {me.hasPassword && (
                <div className="account-row">
                  <label className="hint" htmlFor="acct-autolock">Lock after</label>
                  <select id="acct-autolock" className="select" value={me.autoLockMin}
                    onChange={(e) => setAutoLock(Number(e.target.value))}>
                    {[...new Set([0, 5, 15, 30, 60, me.autoLockMin])].sort((a, b) => a - b).map((m) => (
                      <option key={m} value={m}>{m === 0 ? 'Never' : `${m} min idle`}</option>
                    ))}
                  </select>
                </div>
              )}
              {!pwForm && (
                <div className="btn-row">
                  <button type="button" className="btn btn-sm btn-quiet" onClick={() => { setPwForm('set'); setAcctNote(null); }}>
                    {me.hasPassword ? 'Change password…' : 'Set a password…'}
                  </button>
                  {me.hasPassword && (
                    <button type="button" className="btn btn-sm btn-quiet" onClick={() => { setPwForm('remove'); setAcctNote(null); }}>Remove password…</button>
                  )}
                </div>
              )}
              {pwForm && (
                <form className="account-form" onSubmit={submitPassword} aria-label={pwForm === 'remove' ? 'Remove password' : 'Password'}>
                  {me.hasPassword && (
                    <div className="field">
                      <label htmlFor="acct-pw-current">Current password</label>
                      <input id="acct-pw-current" className="input" type="password" autoComplete="current-password" value={pw.current}
                        onChange={(e) => setPw((p) => ({ ...p, current: e.target.value }))} />
                    </div>
                  )}
                  {pwForm === 'set' ? (
                    <>
                      <div className="field">
                        <label htmlFor="acct-pw-new">New password</label>
                        <input id="acct-pw-new" className="input" type="password" autoComplete="new-password" minLength={8} value={pw.next}
                          onChange={(e) => setPw((p) => ({ ...p, next: e.target.value }))} />
                      </div>
                      <div className="field">
                        <label htmlFor="acct-pw-again">Repeat it</label>
                        <input id="acct-pw-again" className="input" type="password" autoComplete="new-password" value={pw.again}
                          onChange={(e) => setPw((p) => ({ ...p, again: e.target.value }))} />
                      </div>
                      <p className="account-note">At least 8 characters. A forgotten password cannot be recovered: the admin of this
                        computer can only delete the account and its data.</p>
                    </>
                  ) : (
                    <p className="account-note">Without a password, anyone using this computer can open this account and use its key.</p>
                  )}
                  {pwError && <p className="hint err" role="alert">{pwError}</p>}
                  <div className="btn-row">
                    <button type="submit" className="btn btn-sm btn-primary"
                      disabled={pwBusy || (me.hasPassword && !pw.current)
                        || (pwForm === 'set' && (pw.next.length < 8 || pw.next !== pw.again))}>
                      {pwBusy ? 'Working…' : pwForm === 'remove' ? 'Remove password' : 'Save password'}
                    </button>
                    <button type="button" className="btn btn-sm btn-quiet" disabled={pwBusy}
                      onClick={() => { setPwForm(null); setPwError(null); setPw({ current: '', next: '', again: '' }); }}>Cancel</button>
                  </div>
                </form>
              )}
              {acctNote && <p className="account-note" role="status">{acctNote}</p>}
            </>
          )}
          {local && me?.isAdmin && (
            <button type="button" role="menuitem" className="account-item" onClick={() => { setOpen(false); setAccountsOpen(true); }}>
              <Users size={15} aria-hidden="true" /> Accounts on this computer…
            </button>
          )}
          <button type="button" role="menuitem" className="account-item" onClick={() => { setOpen(false); setPrivacyOpen(true); }}>
            <ShieldCheck size={15} aria-hidden="true" /> Privacy and your data…
          </button>
          <button type="button" role="menuitem" className="account-signout" onClick={() => { setOpen(false); onSignOut(); }}>
            <LogOut size={15} aria-hidden="true" /> Sign out
          </button>
        </div>
      )}
      <PrivacyDialog open={privacyOpen} onClose={() => setPrivacyOpen(false)} user={user} returnFocus={btn} />
      {local && (
        <LocalAccountsDialog open={accountsOpen} onClose={() => setAccountsOpen(false)} user={user}
          hasPassword={Boolean(me?.hasPassword)} returnFocus={btn} />
      )}
    </div>
  );
}
