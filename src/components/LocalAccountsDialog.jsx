import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Crown, Lock, Trash2, Users, X } from 'lucide-react';
import { api } from '../lib/api';
import { useModalFocus } from '../lib/useModalFocus';

const sameName = (typed, name) => {  // the server's rule: spaces collapsed, case ignored
  const norm = (v) => (v || '').split(/\s+/).filter(Boolean).join(' ').toLowerCase();
  return norm(typed) !== '' && norm(typed) === norm(name);
};

/**
 * Accounts on this computer, for its admin (account menu): every account, "Make admin" (the admin role moves, it is
 * not shared) and "Delete…" (the account's name typed, plus the admin's own password if it has one). Only the admin
 * deletes accounts; someone who forgot their password asks for this. The admin's own account is deleted from
 * Privacy and your data, after handing the role on.
 */
export default function LocalAccountsDialog({ open, onClose, user, hasPassword, returnFocus }) {
  const panel = useRef(null);
  const [accounts, setAccounts] = useState(null);
  const [action, setAction] = useState(null);  // {kind: 'delete' | 'admin', account}
  const [confirmName, setConfirmName] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [note, setNote] = useState(null);
  useModalFocus(open, panel, onClose, returnFocus);

  const load = useCallback(() => {
    api('/api/auth/accounts').then(setAccounts).catch((err) => setError(err.message));
  }, []);
  useEffect(() => {
    if (!open) return;
    setAccounts(null); setAction(null); setError(null); setNote(null); setBusy(false);
    load();
  }, [open, load]);

  const start = (kind, account) => { setAction({ kind, account }); setConfirmName(''); setPassword(''); setError(null); setNote(null); };

  const submit = async (e) => {
    e.preventDefault();
    const { kind, account } = action;
    setBusy(true); setError(null);
    try {
      if (kind === 'delete') {
        await api('/api/auth/delete-account', {
          method: 'POST',
          body: { userId: account.id, confirmName: confirmName.trim(), ...(hasPassword ? { password } : {}) },
        });
        setNote(`${account.name} and everything saved for it were deleted from this computer.`);
        setAction(null);
        load();
      } else {
        await api('/api/auth/admin/transfer', { method: 'POST', body: { userId: account.id, ...(hasPassword ? { password } : {}) } });
        window.dispatchEvent(new Event('andedu:account-changed'));
        onClose();  // no longer the admin: this list is theirs now
        return;
      }
    } catch (err) {
      setError(err.message);
    }
    setBusy(false);
  };

  if (!open) return null;
  const others = (accounts || []).filter((a) => a.id !== user?.id);
  const ready = action && (!hasPassword || password) && (action.kind !== 'delete' || sameName(confirmName, action.account.name));

  return createPortal(
    <div className="privacy-scrim" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div ref={panel} className="panel privacy-dialog" role="dialog" aria-modal="true" aria-labelledby="accounts-title" tabIndex={-1}>
        <div className="privacy-head">
          <h2 id="accounts-title"><Users size={18} aria-hidden="true" /> Accounts on this computer</h2>
          <button type="button" className="btn btn-quiet btn-sm btn-icon" onClick={onClose} aria-label="Close accounts dialog">
            <X size={16} aria-hidden="true" />
          </button>
        </div>
        <p className="hint">You are the admin: only you can delete accounts, and the role moves to one other account at a time.
          Your own account is deleted from Privacy and your data, after you hand the role on.</p>

        {accounts === null && !error && <p className="hint" role="status">Loading…</p>}
        {accounts && !others.length && <p className="hint">No other accounts on this computer.</p>}
        {others.length > 0 && (
          <ul className="accounts-list">
            {others.map((a) => (
              <li key={a.id} className="accounts-row">
                <span className="accounts-name">
                  <strong>{a.name}</strong>
                  {a.locked && <span className="profile-lock" title="Has a password"><Lock size={13} aria-hidden="true" /><span className="sr-only">Has a password</span></span>}
                </span>
                <span className="btn-row">
                  <button type="button" className="btn btn-sm btn-quiet" disabled={busy} onClick={() => start('admin', a)}>
                    <Crown size={14} aria-hidden="true" /> Make admin
                  </button>
                  <button type="button" className="btn btn-sm btn-quiet" disabled={busy} onClick={() => start('delete', a)}>
                    <Trash2 size={14} aria-hidden="true" /> Delete…
                  </button>
                </span>
              </li>
            ))}
          </ul>
        )}

        {action && (
          <form className={`${action.kind === 'delete' ? 'privacy-danger ' : ''}stack-sm`} onSubmit={submit} aria-labelledby="accounts-action-h">
            <h3 id="accounts-action-h">{action.kind === 'delete' ? `Delete ${action.account.name}?` : `Make ${action.account.name} the admin?`}</h3>
            <p className="hint">{action.kind === 'delete'
              ? 'Its courses, lessons, progress and saved Gemini key are removed from this computer for good. This cannot be undone.'
              : 'You stop being the admin: they will manage accounts and the shared library instead of you.'}</p>
            {action.kind === 'delete' && (
              <div className="field">
                <label htmlFor="accounts-confirm">Type the account's name, <b>{action.account.name}</b>, to confirm</label>
                <input id="accounts-confirm" className="input" value={confirmName} autoComplete="off"
                  onChange={(e) => setConfirmName(e.target.value)} />
              </div>
            )}
            {hasPassword && (
              <div className="field">
                <label htmlFor="accounts-pass">Your password</label>
                <input id="accounts-pass" className="input" type="password" value={password} autoComplete="current-password"
                  onChange={(e) => setPassword(e.target.value)} />
              </div>
            )}
            <div className="btn-row">
              <button type="submit" className={`btn ${action.kind === 'delete' ? 'btn-danger' : 'btn-primary'}`} disabled={busy || !ready}>
                {busy ? 'Working…' : action.kind === 'delete' ? 'Delete this account and its data' : 'Hand over the admin role'}
              </button>
              <button type="button" className="btn btn-quiet" disabled={busy} onClick={() => { setAction(null); setError(null); }}>Cancel</button>
            </div>
          </form>
        )}

        {note && <p className="notice notice-info" role="status">{note}</p>}
        {error && <p className="notice notice-bad" role="alert">{error}</p>}
      </div>
    </div>,
    document.body,
  );
}
