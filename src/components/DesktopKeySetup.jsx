import React, { useState } from 'react';
import { KeyRound } from 'lucide-react';

// Desktop app only (window.sciedu comes from desktop/preload.cjs): asks once for the student's own Gemini key.
// The key goes to the shell, which keeps it encrypted in the macOS Keychain and restarts the backend with it.
export default function DesktopKeySetup({ activeJobs = 0 }) {
  const [key, setKey] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [hidden, setHidden] = useState(false);
  if (hidden) return null;

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    const res = await window.sciedu.saveKey(key).catch(() => ({ ok: false, error: 'The key could not be saved.' }));
    if (!res?.ok) {
      setError(res?.error || 'The key could not be saved.');
      setSaving(false);
    }
    // on success the shell restarts the backend and reloads this page
  };

  return (
    <aside className="desktop-key-card" aria-labelledby="desktop-key-title">
      <h2 id="desktop-key-title"><KeyRound size={18} aria-hidden="true" /> Add your Gemini API key</h2>
      <p>
        New courses, lessons and the tutor use Google Gemini with your own key. The library lessons and the offline
        German and history units work without one. Get a key at{' '}
        <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer">aistudio.google.com/apikey</a>.
      </p>
      <form onSubmit={save}>
        <input
          className="input"
          type="password"
          autoComplete="off"
          spellCheck={false}
          placeholder="Paste the key"
          aria-label="Gemini API key"
          value={key}
          onChange={(e) => setKey(e.target.value)}
        />
        {activeJobs > 0 && <p className="desktop-key-note">Saving restarts the app's server and stops the {activeJobs} running job(s).</p>}
        {error && <p className="desktop-key-error" role="alert">{error}</p>}
        <div className="desktop-key-actions">
          <button type="submit" className="btn btn-sm btn-primary" disabled={saving || !key.trim()}>{saving ? 'Saving…' : 'Save key'}</button>
          <button type="button" className="btn btn-sm btn-quiet" onClick={() => setHidden(true)}>Later</button>
        </div>
      </form>
      <p className="desktop-key-note">It is stored encrypted in your macOS Keychain on this computer and never sent anywhere except Google.</p>
    </aside>
  );
}
