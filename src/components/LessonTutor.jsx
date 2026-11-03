import React, { useEffect, useRef, useState } from 'react';
import { Send, Loader2, RotateCcw } from 'lucide-react';
import Md from './Md';
import { api } from '../lib/api';

const STARTERS = [
  'Explain the key idea another way',
  'I got lost in the worked example',
  'Ask me one question to check I understood',
];

/**
 * Socratic tutor for one lesson (from &EDU's mentor): a short brief, then a conversation that leads with
 * questions instead of answers. `focus` = a quiz question the student just got wrong.
 */
export default function LessonTutor({ topic, focus, onFocusUsed }) {
  const [brief, setBrief] = useState(null);
  const [turns, setTurns] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const logRef = useRef(null);

  useEffect(() => {
    let live = true;
    api('/api/tutor/lesson', { method: 'POST', body: { topicId: topic.id, mode: 'brief' } })
      .then((d) => live && setBrief((d.reply || '').replace(/\n(?!\n)/g, '\n\n')))  // one line per part
      .catch(() => live && setBrief(''));
    return () => { live = false; };
  }, [topic.id]);

  useEffect(() => { logRef.current?.scrollTo({ top: logRef.current.scrollHeight }); }, [turns, busy]);

  const ask = async (text, withFocus = null) => {
    const message = (text ?? input).trim();
    if (!message || busy) return;
    const history = turns.map((t) => ({ role: t.role, content: t.content }));
    setTurns((t) => [...t, { role: 'user', content: message }]);
    setInput('');
    setBusy(true);
    setError(null);
    try {
      const { reply } = await api('/api/tutor/lesson', {
        method: 'POST', body: { topicId: topic.id, message, history, focus: withFocus },
      });
      setTurns((t) => [...t, { role: 'tutor', content: reply }]);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  // Arriving from a wrong quiz answer: open the conversation about that question.
  useEffect(() => {
    if (!focus) return;
    ask(`I chose "${focus.options?.[focus.selected] ?? '?'}" for: ${focus.question} Why is that wrong?`, focus);
    onFocusUsed?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus]);

  return (
    <section className="stack" aria-labelledby="tutor-h">
      <div className="panel stack-sm">
        <h2 id="tutor-h" style={{ fontSize: '1.1rem' }}>Before you start</h2>
        {brief === null && <p className="hint"><Loader2 size={14} className="spin" aria-hidden="true" /> Preparing a brief…</p>}
        {brief && <Md className="prose">{brief}</Md>}
        {brief === '' && <p className="hint">The brief isn't available right now; you can still ask the tutor below.</p>}
      </div>

      <div className="panel tutor">
        <div className="tutor-log" ref={logRef} aria-live="polite">
          {turns.length === 0 && (
            <p className="hint">The tutor answers with questions that lead you to the idea, instead of handing you the answer.
              Start with what confuses you, or pick one of these.</p>
          )}
          {turns.map((t, i) => (
            <div key={i} className={`msg ${t.role === 'user' ? 'msg-user' : 'msg-agy'}`}>
              <span className="who">{t.role === 'user' ? 'You' : 'Tutor'}</span>
              {t.role === 'user' ? <p>{t.content}</p> : <Md>{t.content}</Md>}
            </div>
          ))}
          {busy && <p className="hint"><Loader2 size={14} className="spin" aria-hidden="true" /> Thinking…</p>}
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
          <label htmlFor="tutor-input" className="visually-hidden">Ask the tutor</label>
          <input id="tutor-input" className="input" value={input} onChange={(e) => setInput(e.target.value)}
            placeholder="What's confusing you?" autoComplete="off" />
          <button type="submit" className="btn btn-primary btn-icon" disabled={busy || !input.trim()} aria-label="Send"><Send size={16} /></button>
        </form>
      </div>
    </section>
  );
}
