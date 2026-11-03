import React, { useEffect, useRef, useState } from 'react';
import { X, Send, Loader2 } from 'lucide-react';
import Md from './Md';
import { api, useAgyEvents } from '../lib/api';

const SUGGESTIONS = [
  'Make a simulation for this topic',
  'Explain this lesson more simply',
  'Make the next class easier',
];

/** AGY companion: its own column on wide screens, a sheet over the page on narrow ones. */
export default function AgyBridgeDrawer({ open, onClose, activeTopicId, courseId, agyCli = false }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const logRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    api('/api/agy/messages')
      .then((list) => Array.isArray(list) && setMessages(list.slice(-60)))
      .catch(() => {});
    inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [messages, open]);

  // Replies written by the backend (Gemini tools or the agy CLI) arrive as NEW_MESSAGE events
  useAgyEvents((evt) => {
    if (evt.type !== 'NEW_MESSAGE' || !evt.payload?.message) return;
    const m = evt.payload.message;
    setMessages((list) => (list.some((x) => x.id === m.id) ? list : [...list, m]));
  });

  const send = async (text) => {
    const prompt = (text ?? input).trim();
    if (!prompt || sending) return;
    setInput('');
    setError(null);
    setSending(true);
    setMessages((list) => [...list, { id: `local-${Date.now()}`, sender: 'user', content: prompt }]);
    try {
      await api('/api/agy/prompt', { method: 'POST', body: { prompt, topicId: activeTopicId, courseId } });
    } catch (e) {
      setError(`AGY didn't answer: ${e.message}`);
    } finally {
      setSending(false);
    }
  };

  if (!open) return null;

  return (
    <>
      <div className="agy-scrim" onClick={onClose} aria-hidden="true" />
      <aside className="agy-panel" aria-label="Assistant">
        <div className="agy-head">
          <div>
            <h2>{agyCli ? 'AGY assistant' : 'Assistant'}</h2>
            <p className="hint" style={{ fontSize: '0.8rem' }}>
              {agyCli ? 'Antigravity CLI on this machine, Gemini when it is busy or capped' : 'Powered by Gemini'}
            </p>
          </div>
          <button type="button" className="btn btn-quiet btn-sm btn-icon" onClick={onClose} aria-label="Close AGY"><X size={16} /></button>
        </div>
        <div className="agy-log" ref={logRef} aria-live="polite">
          {messages.length === 0 && (
            <p className="hint">Ask about the lesson you're on, or have AGY build a simulation, a new lesson or harder questions. Changes show up in the workspace as they land.</p>
          )}
          {messages.map((m) => (
            <div key={m.id} className={`msg ${m.sender === 'user' ? 'msg-user' : 'msg-agy'}`}>
              <span className="who">{m.sender === 'user' ? 'You' : 'AGY'}</span>
              {m.sender === 'user' ? <p>{m.content}</p> : <Md>{m.content}</Md>}
            </div>
          ))}
          {sending && <p className="hint"><Loader2 size={14} className="spin" aria-hidden="true" /> AGY is working…</p>}
          {error && <p className="notice notice-bad">{error}</p>}
        </div>
        <div className="agy-suggest">
          {SUGGESTIONS.map((s) => (
            <button key={s} type="button" className="btn btn-quiet btn-sm" disabled={sending} onClick={() => send(s)}>{s}</button>
          ))}
        </div>
        <form className="agy-form" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <label htmlFor="agy-input" className="visually-hidden">Message AGY</label>
          <input id="agy-input" ref={inputRef} className="input" value={input} onChange={(e) => setInput(e.target.value)}
            placeholder="Ask AGY…" autoComplete="off" />
          <button type="submit" className="btn btn-primary btn-icon" disabled={sending || !input.trim()} aria-label="Send"><Send size={16} /></button>
        </form>
      </aside>
    </>
  );
}
