import React, { useState } from 'react';
import { KeyRound } from 'lucide-react';
import { api } from '../lib/api';

const STORE = {
  darwin: 'your macOS Keychain',
  linux: 'your system keyring (GNOME Keyring or KWallet)',
};

const TITLES = {
  missing: 'Add your Gemini API key',
  rejected: 'Google rejected your Gemini API key',
  locked: "Your Gemini key can't be opened here",
  unreadable: "Your Gemini key couldn't be read",
  manage: 'My Gemini API key',
  legacy: 'Use the key saved on this computer?',
};

// The old desktop app kept one key for the whole computer; the shell deletes that file once the backend has an answer.
// Only right after an answer (adopt or decline): {ok: false} means the file stays, and the offer comes back.
function removeLegacyFile() {
  Promise.resolve(window.sciedu?.removeLegacyKey?.()).catch(() => {});
}

// Accounts on this computer (desktop app, or SCIEDU_LOCAL_ACCOUNTS in a browser): the signed-in account's own key.
// reason: missing (no key yet), rejected (Google turned it down mid-run), locked | unreadable (keyState: the saved key
// can't be opened here), manage (from the account menu: replace or remove), legacy (offer the key an older version
// saved for this computer). The backend checks the key with Google and keeps it sealed; it never comes back to the
// page (only its last 4 characters). account: /api/auth/me. onDone(message): saved or removed, the card closes.
export default function DesktopKeySetup({ reason = 'missing', account, onClose, onDone }) {
  const [view, setView] = useState(reason);
  const [key, setKey] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const hasKey = account?.keyState && account.keyState !== 'none';

  const saved = (res) => {
    const end = res?.hint ? ` (ending in ${res.hint})` : '';
    onDone?.(res?.verified === false
      ? `Key saved${end}, but Google couldn't be reached to check it. If new lessons fail, replace it from the account menu.`
      : `Gemini key saved${end}.`);
  };

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      saved(await api('/api/me/gemini-key', { method: 'PUT', body: { key: key.trim() } }));
    } catch (err) {
      setError(err.message || 'The key could not be saved.');
      setSaving(false);
    }
  };

  const remove = async () => {
    setSaving(true);
    setError('');
    try {
      await api('/api/me/gemini-key', { method: 'DELETE' });
      onDone?.('Gemini key removed from this account.');
    } catch (err) {
      setError(err.message || 'The key could not be removed.');
      setSaving(false);
    }
  };

  const adoptLegacy = async () => {
    setSaving(true);
    setError('');
    try {
      saved(await api('/api/me/gemini-key', { method: 'PUT', body: { adoptLegacy: true } }));
    } catch (err) {
      setError(err.message || 'The saved key could not be used.');
      setView(hasKey ? 'manage' : 'missing');  // paste a key instead
      setSaving(false);
    } finally {
      removeLegacyFile();
    }
  };

  const declineLegacy = async () => {
    setSaving(true);
    setError('');
    try {
      await api('/api/me/legacy-key', { method: 'DELETE' });
      if (hasKey) { onClose?.(); return; }
      setView('missing');
    } catch (err) {
      setError(err.message || 'Try again in a moment.');
    } finally {
      removeLegacyFile();
    }
    setSaving(false);
  };

  const store = STORE[window.sciedu?.platform] || "your system's credential store";
  const getKey = (
    <>Get a key at <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">aistudio.google.com/apikey</a>.</>
  );
  return (
    <aside className="desktop-key-card" data-reason={view} aria-labelledby="desktop-key-title">
      <h2 id="desktop-key-title"><KeyRound size={18} aria-hidden="true" /> {TITLES[view] || TITLES.missing}</h2>
      {view === 'legacy' ? (
        <>
          <p>An older version of &amp;.edu saved a Gemini key for this whole computer. Use it for your account? Either way,
            the computer-wide copy is deleted afterwards, and other accounts add their own key.</p>
          {error && <p className="desktop-key-error" role="alert">{error}</p>}
          <div className="desktop-key-actions">
            <button type="button" className="btn btn-sm btn-primary" disabled={saving} onClick={adoptLegacy}>
              {saving ? 'Checking with Google…' : 'Yes, use it'}
            </button>
            <button type="button" className="btn btn-sm btn-quiet" disabled={saving} onClick={declineLegacy}>No</button>
          </div>
        </>
      ) : (
        <>
          {view === 'rejected' ? (
            <p>New courses, lessons and the tutor stopped because Google no longer accepts your key. It may be mistyped, revoked or limited. Paste a working key, or remove it.</p>
          ) : view === 'locked' ? (
            <p>Your saved key is sealed with something this computer can't open right now (such as {store}). Paste the key again to keep using it. {getKey}</p>
          ) : view === 'unreadable' ? (
            <p>Your saved key is damaged and can't be read. Paste the key again, or remove it. {getKey}</p>
          ) : view === 'manage' ? (
            <p>{hasKey ? 'Your account has a key. Paste a new one to replace it, or remove it.' : 'Your account has no key yet.'} {getKey}</p>
          ) : (
            <p>
              New courses, lessons and the tutor use Google Gemini with your own key. The library lessons and the offline
              German and history units work without one. {getKey}
            </p>
          )}
          <form onSubmit={save}>
            <input
              className="input"
              type="password"
              autoComplete="off"
              spellCheck={false}
              placeholder={hasKey ? 'Paste the new key' : 'Paste the key'}
              aria-label="Gemini API key"
              value={key}
              onChange={(e) => setKey(e.target.value)}
            />
            {error && <p className="desktop-key-error" role="alert">{error}</p>}
            <div className="desktop-key-actions">
              <button type="submit" className="btn btn-sm btn-primary" disabled={saving || !key.trim()}>
                {saving ? 'Checking with Google…' : hasKey ? 'Replace key' : 'Save key'}
              </button>
              {hasKey && !confirmRemove && (
                <button type="button" className="btn btn-sm btn-quiet desktop-key-remove" disabled={saving} onClick={() => setConfirmRemove(true)}>Remove key</button>
              )}
              {hasKey && confirmRemove && (
                <button type="button" className="btn btn-sm desktop-key-remove-confirm" disabled={saving} onClick={remove}>Yes, remove it</button>
              )}
              <button type="button" className="btn btn-sm btn-quiet" disabled={saving} onClick={() => (confirmRemove ? setConfirmRemove(false) : onClose?.())}>
                {confirmRemove ? 'Keep it' : view === 'manage' ? 'Close' : 'Later'}
              </button>
            </div>
          </form>
          <p className="desktop-key-note">
            {account?.hasPassword
              ? 'It is kept encrypted on this computer, locked with your password, and sent only to Google.'
              : `It is kept encrypted on this computer, locked with a key held in ${store}, and sent only to Google.`}
            {' '}Other accounts here can't use it.
          </p>
        </>
      )}
    </aside>
  );
}
