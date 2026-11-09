import React, { useEffect, useState } from 'react';
import { ArrowRight } from 'lucide-react';
import { api, setToken } from '../lib/api';
import ThemeSwitch from './ThemeSwitch';
import { PrivacyNotice } from './PrivacyCenter';

/** Local profiles: a name picks your saved courses. No passwords; the backend only listens on 127.0.0.1. */
export default function LoginPage({ onSignedIn }) {
  const [profiles, setProfiles] = useState([]);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [authRequired, setAuthRequired] = useState(false);
  const [password, setPassword] = useState('');
  const [creating, setCreating] = useState(false);
  const [adult, setAdult] = useState(false);
  const [privacy, setPrivacy] = useState(false);
  const [showNotice, setShowNotice] = useState(false);
  const [elevenlabs, setElevenlabs] = useState(false);
  const [pending, setPending] = useState(null);  // sign-in that still needs privacy consent: {token, user}

  useEffect(() => {
    api('/api/status')
      .then((st) => {
        setAuthRequired(Boolean(st.auth_required));
        setElevenlabs(Boolean(st.elevenlabs_enabled));
        if (!st.auth_required) return api('/api/users').then((d) => setProfiles(d.users || []));
        return null;
      })
      .catch(() => setError('The backend is offline. Start it with scripts/start.sh.'));
  }, []);

  const passwordSignIn = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { token, user, privacyAccepted } = await api(creating ? '/api/auth/register' : '/api/auth/login', {
        method: 'POST', body: { name: name.trim(), password, ...(creating ? { adult, privacy: true } : {}) },
      });
      if (!creating && privacyAccepted === false) {
        setPending({ token, user });  // accounts made before the notice: agree first
        setBusy(false);
        return;
      }
      setToken(token);
      onSignedIn(user);
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  const agree = async () => {
    setBusy(true);
    setError(null);
    setToken(pending.token);
    try {
      await api(`/api/users/${encodeURIComponent(pending.user.id)}/consent`, { method: 'POST', body: { kind: 'privacy' } });
      onSignedIn(pending.user);
    } catch (err) {
      setToken(null);
      setError(err.message);
      setBusy(false);
    }
  };

  const signIn = async (who) => {
    setBusy(true);
    setError(null);
    try {
      const { user } = await api('/api/users', { method: 'POST', body: { name: who } });
      onSignedIn(user);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  };

  return (
    <main className="signin">
      <section className="signin-story">
        <p className="monogram" aria-hidden="true">&amp;</p>
        <h1>Turn your course materials into a course that adapts to you.</h1>
        <p>Upload notes, slides or a problem set. &amp;.edu tests what you already know, then writes your classes in order, each one shaped by how you did on the last.</p>
        <ol className="signin-steps">
          <li><b>1</b><span>Add materials and say what you want to learn.</span></li>
          <li><b>2</b><span>Take a short diagnostic quiz.</span></li>
          <li><b>3</b><span>Work through generated classes: a lesson, a simulation, a quiz and practice puzzles for each.</span></li>
        </ol>
      </section>

      <section className="signin-form" aria-labelledby="signin-h">
        <ThemeSwitch />
        <div className="stack-sm">
          <h2 id="signin-h">Sign in</h2>
          <p className="hint">{authRequired
            ? 'This server keeps an account for each student. Your courses are visible only to you.'
            : 'Your courses and progress are saved on this computer under your name.'}</p>
        </div>

        {authRequired && pending && (
          <div className="stack-sm">
            <p>Before you continue, please read how &amp;.edu handles your data.</p>
            <div className="privacy-inline"><PrivacyNotice elevenlabs={elevenlabs} authRequired /></div>
            <div className="btn-row">
              <button type="button" className="btn btn-primary" disabled={busy} onClick={agree}>{busy ? 'Working…' : 'I agree'}</button>
              <button type="button" className="btn btn-quiet" disabled={busy} onClick={() => {
                // the sign-in already opened a session: close it rather than leave an unused token valid
                fetch('/api/auth/logout', { method: 'POST', headers: { Authorization: `Bearer ${pending.token}` } }).catch(() => {});
                setPending(null); setError(null);
              }}>Cancel</button>
            </div>
          </div>
        )}

        {authRequired && !pending && (
          <form className="stack-sm" onSubmit={passwordSignIn}>
            <div className="field">
              <label htmlFor="acct-name">Name</label>
              <input id="acct-name" className="input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="username" />
            </div>
            <div className="field">
              <label htmlFor="acct-pass">Password</label>
              <input id="acct-pass" className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                autoComplete={creating ? 'new-password' : 'current-password'} minLength={creating ? 8 : undefined} />
              {creating && <span className="hint">At least 8 characters.</span>}
            </div>
            {creating && (
              <label className="check-row" htmlFor="acct-adult">
                <input id="acct-adult" type="checkbox" checked={adult} onChange={(e) => setAdult(e.target.checked)} />
                <span>I am 18 or older (required by the Gemini API terms)</span>
              </label>
            )}
            {creating && (
              <div className="stack-sm">
                <label className="check-row" htmlFor="acct-privacy">
                  <input id="acct-privacy" type="checkbox" required checked={privacy} onChange={(e) => setPrivacy(e.target.checked)} />
                  <span>I have read the privacy notice</span>
                </label>
                <button type="button" className="btn-link" aria-expanded={showNotice} aria-controls="signup-notice" onClick={() => setShowNotice((v) => !v)}>
                  {showNotice ? 'Hide the privacy notice' : 'Read the privacy notice'}
                </button>
                {showNotice && <div id="signup-notice" className="privacy-inline"><PrivacyNotice elevenlabs={elevenlabs} authRequired /></div>}
              </div>
            )}
            <div className="btn-row">
              <button type="submit" className="btn btn-primary" disabled={busy || name.trim().length < 2 || !password || (creating && (!adult || !privacy))}>
                {busy ? 'Working…' : creating ? 'Create account' : 'Sign in'}
              </button>
              <button type="button" className="btn btn-quiet" onClick={() => { setCreating((c) => !c); setError(null); }}>
                {creating ? 'I have an account' : 'Create an account'}
              </button>
            </div>
          </form>
        )}

        {!authRequired && profiles.length > 0 && (
          <div className="stack-sm">
            <span className="label">Continue as</span>
            <div className="profile-list">
              {profiles.map((p) => (
                <button key={p.id} type="button" className="profile" disabled={busy} onClick={() => signIn(p.name)}>
                  <span>
                    <strong>{p.name}</strong>
                    <span className="topic-meta">{p.course_count} {p.course_count === 1 ? 'course' : 'courses'}</span>
                  </span>
                  <ArrowRight size={16} aria-hidden="true" />
                </button>
              ))}
            </div>
          </div>
        )}

        {!authRequired && <form className="stack-sm" onSubmit={(e) => { e.preventDefault(); if (name.trim()) signIn(name.trim()); }}>
          <div className="field">
            <label htmlFor="signin-name">{profiles.length ? 'Or create a new profile' : 'Your name'}</label>
            <input id="signin-name" className="input" value={name} onChange={(e) => setName(e.target.value)}
              autoComplete="name" placeholder="e.g. Alex" minLength={2} maxLength={40} />
          </div>
          <div className="btn-row">
            <button type="submit" className="btn btn-primary" disabled={busy || name.trim().length < 2}>
              {busy ? 'Signing in…' : 'Continue'}
            </button>
          </div>
        </form>}

        {!authRequired && (
          <div className="stack-sm">
            <button type="button" className="btn-link" aria-expanded={showNotice} aria-controls="local-notice" onClick={() => setShowNotice((v) => !v)}>
              {showNotice ? 'Hide the privacy notice' : 'Privacy notice'}
            </button>
            {showNotice && <div id="local-notice" className="privacy-inline"><PrivacyNotice elevenlabs={elevenlabs} authRequired={false} /></div>}
          </div>
        )}

        {error && <p className="notice notice-bad" role="alert">{error}</p>}
        <p className="hint">Your uploaded materials, prompts and quiz answers are sent to Google's Gemini API to write your
          lessons. Don't upload anything confidential or personal.</p>
      </section>
    </main>
  );
}
