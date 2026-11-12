import React, { useEffect, useState } from 'react';
import { KeyRound } from 'lucide-react';

export const KEY_NOTE = 'sciedu-key-note';  // a message for after the reload that follows a save

const STORE = {
  darwin: 'your macOS Keychain',
  linux: 'your system keyring (GNOME Keyring or KWallet)',
};

const TITLES = {
  missing: 'Add your Gemini API key',
  rejected: 'Google rejected your Gemini API key',
  manage: 'Gemini API key',
};

// Desktop app only (window.sciedu comes from desktop/preload.cjs). reason: missing (no key yet), rejected (Google
// turned the saved key down mid-run) or manage (opened from the account menu: replace or remove the key).
// The key goes to the shell, which checks it with Google, keeps it encrypted and restarts the backend with it;
// the key never comes back to the page.
export default function DesktopKeySetup({ reason = 'missing', activeJobs = 0, onClose }) {
  const [key, setKey] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [hasKey, setHasKey] = useState(reason === 'rejected');
  const [confirmRemove, setConfirmRemove] = useState(false);

  useEffect(() => {
    if (reason !== 'manage') return;
    window.sciedu.hasKey().then((v) => setHasKey(Boolean(v))).catch(() => {});
  }, [reason]);

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    const res = await window.sciedu.saveKey(key).catch(() => ({ ok: false, error: 'The key could not be saved.' }));
    if (!res?.ok) {
      setError(res?.error || 'The key could not be saved.');
      setSaving(false);
      return;
    }
    if (res.unverified) {
      try {
        sessionStorage.setItem(KEY_NOTE, "Key saved, but Google couldn't be reached to check it. If new lessons fail, replace it from the account menu.");
      } catch { /* the note is only a courtesy */ }
    }
    // on success the shell restarts the backend and reloads this page
  };

  const remove = async () => {
    setSaving(true);
    const res = await window.sciedu.clearKey().catch(() => ({ ok: false }));
    if (!res?.ok) {
      setError('The key could not be removed.');
      setSaving(false);
    }
  };

  const store = STORE[window.sciedu?.platform] || "your system's credential store";
  const jobsNote = activeJobs > 0 && `Saving or removing restarts the app's server and stops the ${activeJobs} running job(s).`;
  return (
    <aside className="desktop-key-card" data-reason={reason} aria-labelledby="desktop-key-title">
      <h2 id="desktop-key-title"><KeyRound size={18} aria-hidden="true" /> {TITLES[reason] || TITLES.missing}</h2>
      {reason === 'rejected' ? (
        <p>New courses, lessons and the tutor stopped because Google no longer accepts the saved key. It may be mistyped, revoked or limited. Paste a working key, or remove it.</p>
      ) : reason === 'manage' ? (
        <p>{hasKey ? 'A key is saved on this computer. Paste a new one to replace it, or remove it.' : 'No key is saved yet.'} Get a key at{' '}
          <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">aistudio.google.com/apikey</a>.</p>
      ) : (
        <p>
          New courses, lessons and the tutor use Google Gemini with your own key. The library lessons and the offline
          German and history units work without one. Get a key at{' '}
          <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">aistudio.google.com/apikey</a>.
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
        {jobsNote && <p className="desktop-key-note">{jobsNote}</p>}
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
            {confirmRemove ? 'Keep it' : reason === 'manage' ? 'Close' : 'Later'}
          </button>
        </div>
      </form>
      <p className="desktop-key-note">It is stored encrypted in {store} on this computer and never sent anywhere except Google.</p>
    </aside>
  );
}
