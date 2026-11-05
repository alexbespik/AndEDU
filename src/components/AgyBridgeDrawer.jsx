import React, { useEffect, useRef, useState } from 'react';
import { X, Send, Loader2, Play } from 'lucide-react';
import Md from './Md';
import { api, useAgyEvents } from '../lib/api';

const SUGGESTIONS = [
  'Explain this lesson more simply',
  'Make the next class easier',
  'Write 3 harder quiz questions for this lesson',
];

/** Code the assistant wants to run: shown first, and it runs on this computer only when the student clicks Run. */
function CodeProposal({ proposal }) {
  const [state, setState] = useState(null);  // null | 'running' | {output} | {error}
  const run = async () => {
    setState('running');
    try {
      const r = await api('/api/execute-code', { method: 'POST', body: { code: proposal.code } });
      setState({ output: [r.stdout, r.stderr, r.error, r.output].filter(Boolean).join('\n') || 'Finished with no output.' });
    } catch (e) {
      setState({ error: e.message });
    }
  };
  return (
    <div className="msg msg-agy stack-sm">
      <span className="who">AGY wants to run Python on this computer</span>
      {proposal.reason && <p>{proposal.reason}</p>}
      <pre><code>{proposal.code}</code></pre>
      {state === null && <div className="btn-row"><button type="button" className="btn btn-primary btn-sm" onClick={run}><Play size={14} aria-hidden="true" /> Run</button><span className="hint">Read it first: it runs with your permissions.</span></div>}
      {state === 'running' && <p className="hint"><Loader2 size={14} className="spin" aria-hidden="true" /> Running…</p>}
      {state?.output && <pre><code>{state.output}</code></pre>}
      {state?.error && <p className="notice notice-bad">{state.error}</p>}
    </div>
  );
}

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
    if (evt.type === 'CODE_PROPOSAL' && evt.payload?.code) {
      const id = `code-${evt.id ?? evt.seq ?? `${Date.now()}-${Math.random()}`}`;
      setMessages((list) => (list.some((x) => x.id === id) ? list : [...list, { id, sender: 'code', proposal: evt.payload }]));
      return;
    }
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
          {messages.map((m) => (m.sender === 'code' ? <CodeProposal key={m.id} proposal={m.proposal} /> : (
            <div key={m.id} className={`msg ${m.sender === 'user' ? 'msg-user' : 'msg-agy'}`}>
              <span className="who">{m.sender === 'user' ? 'You' : 'AGY'}</span>
              {m.sender === 'user' ? <p>{m.content}</p> : <Md>{m.content}</Md>}
            </div>
          )))}
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
