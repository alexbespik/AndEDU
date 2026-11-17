import React, { useEffect, useRef, useState } from 'react';
import { Send, Info } from 'lucide-react';
import { api } from '../../lib/api';
import Md from '../Md';
import '../../styles/philosophy.css';

const HISTORY_TURNS = 10;

function friendly(err) {
  if (err.status === 404) return 'The philosopher dialogue is not available on this server yet.';
  if (err.status === 422) return 'That figure or message could not be used. Pick a figure from the list and try again.';
  if (err.status === 429) return 'You are sending messages too quickly, or today\'s limit is used up. Wait a little and try again.';
  return err.message || 'The dialogue failed. Try again.';
}

const safeHref = (url) => { try { return /^https?:$/.test(new URL(url).protocol) ? url : null; } catch { return null; } };

function Quote({ q }) {
  const href = safeHref(q.source_url);
  return (
    <figure className="phx-quote">
      <blockquote>{q.text}</blockquote>
      <figcaption>
        {q.author}, <cite>{q.work}</cite>{q.ref ? `, ${q.ref}` : ''}{q.translator ? ` (translated by ${q.translator})` : ''}
        {href && <> · <a href={href} target="_blank" rel="noopener noreferrer">Source text</a></>}
      </figcaption>
    </figure>
  );
}

export default function PhilosopherDialogue({ topicId }) {
  const [figures, setFigures] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [figureId, setFigureId] = useState('');
  const [chats, setChats] = useState({}); // figure id -> [{role, content, quote?, suggested?}]
  const [text, setText] = useState('');
  const [useLesson, setUseLesson] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const endRef = useRef(null);

  useEffect(() => {
    let live = true;
    api('/api/philosophy/figures')
      .then((list) => { if (live) { setFigures(Array.isArray(list) ? list : []); setFigureId((cur) => cur || list?.[0]?.id || ''); } })
      .catch((err) => { if (live) { setFigures([]); setLoadError(friendly(err)); } });
    return () => { live = false; };
  }, []);

  const figure = figures?.find((f) => f.id === figureId);
  const messages = chats[figureId] || [];
  useEffect(() => { endRef.current?.scrollIntoView?.({ block: 'nearest' }); }, [messages.length, busy]);

  const send = async (raw) => {
    const message = raw.trim();
    if (!message || busy || !figure) return;
    const history = messages.slice(-HISTORY_TURNS).map(({ role, content }) => ({ role, content }));
    const id = figure.id;
    setChats((c) => ({ ...c, [id]: [...(c[id] || []), { role: 'user', content: message }] }));
    setText(''); setError(null); setBusy(true);
    try {
      const body = { figure: id, message, history };
      if (useLesson && topicId) body.topicId = topicId;
      const res = await api('/api/philosophy/dialogue', { method: 'POST', body });
      setChats((c) => ({ ...c, [id]: [...(c[id] || []), { role: 'assistant', content: res.reply || '', quote: res.quote || null, suggested: res.suggested_questions || [] }] }));
    } catch (err) {
      setError(friendly(err));
    }
    setBusy(false);
  };
  const last = messages[messages.length - 1];

  return (
    <div className="stack">
      <p className="notice notice-info" role="note">
        <Info size={14} aria-hidden="true" /> <strong>AI portrayal.</strong> The replies are written by an AI imitating a thinker who is no longer living. They are
        not the philosopher's own words. Only the quotation under a reply comes from a verified public-domain text; check it against the source.
      </p>
      {figures === null && <p className="hint" role="status">Loading the philosophers…</p>}
      {loadError && <p className="notice notice-bad" role="alert">{loadError}</p>}
      {figures && !figures.length && !loadError && <p className="hint">No figures are available yet.</p>}
      {figures?.length > 0 && (
        <>
          <div className="phx-grid">
            <div className="field">
              <label htmlFor="phx-figure">Speak with</label>
              <select id="phx-figure" className="select" value={figureId} onChange={(e) => { setFigureId(e.target.value); setError(null); }}>
                {figures.map((f) => <option key={f.id} value={f.id}>{f.name}{f.era ? ` (${f.era})` : ''}</option>)}
              </select>
            </div>
            {topicId && (
              <label className="phx-check"><input type="checkbox" checked={useLesson} onChange={(e) => setUseLesson(e.target.checked)} /> Ground the talk in the lesson I have open</label>
            )}
          </div>
          {figure && (
            <p className="hint">
              {figure.quote_count} quotation{figure.quote_count === 1 ? '' : 's'} in the bank
              {Array.isArray(figure.collection) && figure.collection.length > 0 && <>: {figure.collection.join('; ')}</>}
            </p>
          )}
          <div className="phx-chat" role="log" aria-live="polite" aria-label={`Conversation with ${figure?.name || 'the philosopher'}`}>
            {!messages.length && <p className="hint">Ask a question to begin. Short, specific questions work best.</p>}
            {messages.map((m, i) => (
              <div key={i} className={`phx-msg phx-${m.role}`}>
                <span className="label">{m.role === 'user' ? 'You' : `${figure?.name} (AI portrayal)`}</span>
                {m.role === 'user' ? <p>{m.content}</p> : <Md>{m.content}</Md>}
                {m.quote && <Quote q={m.quote} />}
              </div>
            ))}
            {busy && <p className="hint" role="status">Thinking…</p>}
            <div ref={endRef} />
          </div>
          {error && <p className="notice notice-bad" role="alert">{error}</p>}
          {last?.role === 'assistant' && last.suggested?.length > 0 && !busy && (
            <div className="btn-row" aria-label="Suggested questions">
              {last.suggested.map((q) => <button key={q} type="button" className="btn btn-quiet btn-sm" onClick={() => send(q)}>{q}</button>)}
            </div>
          )}
          <form className="phx-compose" onSubmit={(e) => { e.preventDefault(); send(text); }}>
            <label htmlFor="phx-msg" className="label">Your message</label>
            <textarea id="phx-msg" className="textarea" rows={2} maxLength={1000} value={text} onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(text); } }} />
            <div className="btn-row">
              <button type="submit" className="btn btn-primary" disabled={!text.trim() || busy}><Send size={14} aria-hidden="true" /> Send</button>
              <span className="hint">Enter sends, Shift+Enter adds a line. Each reply uses one model call.</span>
            </div>
          </form>
        </>
      )}
    </div>
  );
}
