import React, { useEffect, useRef, useState } from 'react';
import { Send, Loader2, RotateCcw, MessageCircle } from 'lucide-react';
import Md from './Md';
import { api } from '../lib/api';

const STARTERS = [
  'What should I take next semester?',
  'Which College Curriculum requirements am I missing?',
  'Am I ready for CSCI 303?',
];

/** Ask the advisor: answers come from the student's record, degree audit, the catalog and the class schedule. */
export default function AdvisorChat({ user, doneCount }) {
  const [turns, setTurns] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const logRef = useRef(null);

  useEffect(() => { logRef.current?.scrollTo({ top: logRef.current.scrollHeight }); }, [turns, busy]);

  const ask = async (text) => {
    const message = (text ?? input).trim();
    if (!message || busy) return;
    const history = turns.map((t) => ({ role: t.role, content: t.content }));
    setTurns((t) => [...t, { role: 'user', content: message }]);
    setInput('');
    setBusy(true);
    setError(null);
    try {
      const res = await api(`/api/advisor/${user.id}/ask`, { method: 'POST', body: { message, history } });
      setTurns((t) => [...t, {
        role: 'advisor',
        content: res.reply,
        suggested_courses: res.suggested_courses || [],
        courses: res.courses || [],
      }]);
    } catch (e) {
      setTurns((t) => t.slice(0, -1));  // drop the unanswered question and give the text back to retry
      setInput(message);
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel tutor stack-sm" aria-labelledby="advisor-chat-h" style={{ marginBottom: 'var(--space-4)' }}>
      <h2 id="advisor-chat-h"><MessageCircle size={18} aria-hidden="true" /> Ask the advisor</h2>
      <div className="tutor-log" ref={logRef} aria-live="polite">
        {turns.length === 0 && (
          <p className="hint">
            Ask about courses, prerequisites, requirements or the schedule. Answers use your {doneCount} recorded course
            {doneCount === 1 ? '' : 's'}, your degree progress and the imported catalog. They're guidance, so confirm your plan with your
            official advisor.
          </p>
        )}
        {turns.map((t, i) => (
          <div key={i} className={`msg ${t.role === 'user' ? 'msg-user' : 'msg-agy'}`}>
            <span className="who">{t.role === 'user' ? 'You' : 'Advisor'}</span>
            {t.role === 'user' ? <p>{t.content}</p> : <Md>{t.content}</Md>}
            {t.role === 'advisor' && ((t.suggested_courses && t.suggested_courses.length > 0) || (t.courses && t.courses.length > 0)) && (
              <div className="btn-row" style={{ marginTop: 'var(--space-2)', gap: '0.4rem', flexWrap: 'wrap' }}>
                {(t.suggested_courses?.length ? t.suggested_courses : (t.courses || []).map((code) => ({ code }))).map((sc) => (
                  <button
                    key={sc.code}
                    type="button"
                    className="chip"
                    style={{
                      cursor: 'pointer',
                      border: '1px solid var(--primary-border, var(--primary))',
                      background: 'var(--surface)',
                      fontSize: '0.8rem',
                      padding: '3px 8px',
                    }}
                    onClick={() => ask(`Tell me more about ${sc.code}${sc.title ? `: ${sc.title}` : ''}`)}
                    title={sc.title ? `${sc.code}: ${sc.title}` : sc.code}
                    disabled={busy}
                  >
                    <strong>{sc.code}</strong>{sc.title ? ` · ${sc.title}` : ''}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <p className="hint"><Loader2 size={14} className="spin" aria-hidden="true" /> Checking your record and the catalog…</p>}
        {error && <p className="notice notice-bad">{error}</p>}
      </div>
      <div className="btn-row">
        {STARTERS.map((s) => (
          <button key={s} type="button" className="btn btn-quiet btn-sm" disabled={busy} onClick={() => ask(s)}>{s}</button>
        ))}
        {turns.length > 0 && (
          <button type="button" className="btn btn-quiet btn-sm" onClick={() => setTurns([])} disabled={busy}>
            <RotateCcw size={14} aria-hidden="true" /> Start over
          </button>
        )}
      </div>
      <form className="agy-form" style={{ padding: 0, border: 0 }} onSubmit={(e) => { e.preventDefault(); ask(); }}>
        <label htmlFor="advisor-chat-input" className="visually-hidden">Ask the advisor</label>
        <input id="advisor-chat-input" className="input" value={input} onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. How do I finish COLL 200 by junior year?" autoComplete="off" maxLength={2000} />
        <button type="submit" className="btn btn-primary btn-icon" disabled={busy || !input.trim()} aria-label="Send"><Send size={16} /></button>
      </form>
    </section>
  );
}
