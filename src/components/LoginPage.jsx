import React, { useEffect, useState } from 'react';
import { ArrowRight, Lock } from 'lucide-react';
import { api, getToken, setToken } from '../lib/api';
import ThemeSwitch from './ThemeSwitch';
import { PrivacyNotice } from './PrivacyCenter';

/**
 * Local profiles: a name picks your saved courses. No passwords; the backend only listens on 127.0.0.1.
 * Accounts on this computer (the desktop app): tiles, an optional password per account, no recovery (only the admin
 * deletes accounts, from the account menu).
 * resume: the account this window was signed in to ({id, name}); an account without a password opens again by
 * itself (sessions end with each launch), one with a password asks for it. notice: why the account was locked.
 */
export default function LoginPage({ onSignedIn, resume = null, notice = null }) {
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
  // accounts on this computer
  const [local, setLocal] = useState(null);  // null until known
  const [tiles, setTiles] = useState([]);  // [{id, name, locked}]
  const [picked, setPicked] = useState(null);  // the locked tile whose password is being typed
  const [forgot, setForgot] = useState(null);  // the tile whose password was forgotten (only the admin can delete it)
  const [password2, setPassword2] = useState('');
  const [resuming, setResuming] = useState(Boolean(resume));
  const [info, setInfo] = useState(notice);
  useEffect(() => { if (notice) setInfo(notice); }, [notice]);  // a lock that lands after this screen mounted

  const localSignIn = async (tile, pass) => {
    setBusy(true);
    setError(null);
    try {
      const { token, user } = await api('/api/auth/login', {
        method: 'POST', body: { name: tile.name, ...(pass ? { password: pass } : {}) },
      });
      setToken(token);
      onSignedIn({ ...user, local: true });
    } catch (err) {
      if (tile.locked) setPicked(tile);
      else api('/api/auth/profiles').then((list) => setTiles(list || [])).catch(() => {});  // it may have a password now
      setError(err.message);  // includes the wait after too many wrong passwords (429)
      setBusy(false);
    }
  };

  useEffect(() => {
    let active = true;
    const openLocal = async () => {
      const list = await api('/api/auth/profiles');
      if (!active) return;
      setTiles(list || []);
      if (!resume) return;
      if (getToken()) {  // a reload within the same launch: the session may still be open
        try {
          const me = await api('/api/auth/me');
          if (active && me.user?.id === resume.id) { onSignedIn({ ...me.user, local: true }); return; }
        } catch { /* ended: sign in again below */ }
        setToken(null);
      }
      const tile = (list || []).find((t) => t.id === resume.id);
      if (!active || !tile) return;
      if (tile.locked) setPicked(tile);
      else await localSignIn(tile);
    };
    api('/api/status')
      .then(async (st) => {
        if (!active) return null;
        setAuthRequired(Boolean(st.auth_required));
        setElevenlabs(Boolean(st.elevenlabs_enabled));
        if (st.auth_required) return null;
        const isLocal = Boolean(st.local_accounts);
        setLocal(isLocal);
        if (isLocal) return openLocal();
        return api('/api/users').then((d) => setProfiles(d.users || []));
      })
      .catch(() => setError('The backend is offline. Start it with scripts/start.sh.'))
      .finally(() => { if (active) setResuming(false); });
    return () => { active = false; };
    // once per sign-in screen: resume and onSignedIn are fixed while it is shown
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const localCreate = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { token, user } = await api('/api/auth/register', {
        method: 'POST', body: { name: name.trim(), ...(password ? { password } : {}) },
      });
      setToken(token);
      onSignedIn({ ...user, local: true });
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  const backToTiles = () => { setPicked(null); setForgot(null); setPassword(''); setPassword2(''); setError(null); };
  const showLocal = !authRequired && local === true;
  const passMismatch = Boolean(password) && password2 !== password;

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
            : showLocal
              ? 'Each account on this computer keeps its own courses, progress and Gemini key. A password is optional.'
              : 'Your courses and progress are saved on this computer under your name.'}</p>
        </div>

        {info && <p className="notice notice-info" role="status">{info}</p>}

        {showLocal && resuming && <p className="hint" role="status">Opening {resume?.name || 'your account'}…</p>}

        {showLocal && !resuming && picked && !forgot && (
          <form className="stack-sm" onSubmit={(e) => { e.preventDefault(); if (password) localSignIn(picked, password); }}>
            <span className="label"><Lock size={13} aria-hidden="true" /> {picked.name}</span>
            <div className="field">
              <label htmlFor="local-pass">Password</label>
              <input id="local-pass" className="input" type="password" value={password} autoFocus
                onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
            </div>
            <div className="btn-row">
              <button type="submit" className="btn btn-primary" disabled={busy || !password}>{busy ? 'Signing in…' : 'Sign in'}</button>
              <button type="button" className="btn btn-quiet" disabled={busy} onClick={backToTiles}>Other account</button>
            </div>
            <button type="button" className="btn-link" onClick={() => { setForgot(picked); setError(null); setInfo(null); }}>Forgot password?</button>
          </form>
        )}

        {showLocal && !resuming && forgot && (
          <div className="stack-sm" role="region" aria-labelledby="forgot-h">
            <h3 id="forgot-h">Forgot the password for {forgot.name}?</h3>
            <p className="notice notice-info">A forgotten password cannot be recovered, by you or anyone else. Ask the admin of
              this computer to delete this account (account menu, Accounts on this computer); its courses, progress and saved
              Gemini key go with it. Then create a new account.</p>
            <div className="btn-row">
              <button type="button" className="btn btn-quiet" onClick={() => { setForgot(null); setError(null); }}>Back</button>
            </div>
          </div>
        )}

        {showLocal && !resuming && !picked && !forgot && tiles.length > 0 && (
          <div className="stack-sm">
            <span className="label">Continue as</span>
            <div className="profile-list">
              {tiles.map((t) => (
                <button key={t.id} type="button" className="profile" disabled={busy}
                  onClick={() => { setInfo(null); if (t.locked) { setPicked(t); setPassword(''); setError(null); } else localSignIn(t); }}>
                  <strong>{t.name}</strong>
                  {t.locked
                    ? <span className="profile-lock"><Lock size={15} aria-hidden="true" /><span className="sr-only">Password required</span></span>
                    : <ArrowRight size={16} aria-hidden="true" />}
                </button>
              ))}
            </div>
          </div>
        )}

        {showLocal && !resuming && !picked && !forgot && (
          <form className="stack-sm" onSubmit={localCreate}>
            <span className="label">{tiles.length ? 'Or create a new account' : 'Create your account'}</span>
            <div className="field">
              <label htmlFor="local-name">Name</label>
              <input id="local-name" className="input" value={name} onChange={(e) => setName(e.target.value)}
                autoComplete="username" placeholder="e.g. Alex" minLength={2} maxLength={40} />
            </div>
            <div className="field">
              <label htmlFor="local-new-pass">Password (optional)</label>
              <input id="local-new-pass" className="input" type="password" value={password} minLength={8}
                onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" aria-describedby="local-pass-hint" />
              <span id="local-pass-hint" className="hint">At least 8 characters, or leave it empty for an account anyone using this computer can open.</span>
            </div>
            {password && (
              <div className="field">
                <label htmlFor="local-new-pass2">Repeat the password</label>
                <input id="local-new-pass2" className="input" type="password" value={password2}
                  onChange={(e) => setPassword2(e.target.value)} autoComplete="new-password"
                  aria-invalid={passMismatch} aria-describedby={passMismatch ? 'local-pass2-err' : undefined} />
                {passMismatch && password2 && <span id="local-pass2-err" className="hint err">The passwords differ.</span>}
              </div>
            )}
            {password && (
              <p className="notice notice-info">A forgotten password cannot be recovered. If you forget it, the admin of this computer
                can only delete the account and its data.</p>
            )}
            <div className="btn-row">
              <button type="submit" className="btn btn-primary"
                disabled={busy || name.trim().length < 2 || Boolean(password && (password.length < 8 || passMismatch))}>
                {busy ? 'Working…' : 'Create account'}
              </button>
            </div>
          </form>
        )}

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

        {!authRequired && local === false && profiles.length > 0 && (
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

        {!authRequired && local === false && <form className="stack-sm" onSubmit={(e) => { e.preventDefault(); if (name.trim()) signIn(name.trim()); }}>
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
            {showNotice && <div id="local-notice" className="privacy-inline"><PrivacyNotice elevenlabs={elevenlabs} authRequired={false} local={showLocal} /></div>}
          </div>
        )}

        {error && <p className="notice notice-bad" role="alert">{error}</p>}
        <p className="hint">Your uploaded materials, prompts and quiz answers are sent to Google's Gemini API to write your
          lessons. Don't upload anything confidential or personal.</p>
      </section>
    </main>
  );
}
