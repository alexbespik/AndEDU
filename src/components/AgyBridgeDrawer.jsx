import React, { useEffect, useRef, useState } from 'react';
import { X, Send, Loader2, Play } from 'lucide-react';
import Md from './Md';
import { api, uploadFiles, useAgyEvents } from '../lib/api';
import { confirmGeminiUpload, handleUploadConsentError } from '../lib/consent';
import { disambiguateFile } from '../lib/files';

export const EXPLANATION_LEVELS = [
  { level: 0, title: 'ELI5' },
  { level: 1, title: 'Beginner' },
  { level: 2, title: 'College' },
  { level: 3, title: 'Advanced' },
  { level: 4, title: 'Grad' },
  { level: 5, title: 'Expert' },
];

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
export default function AgyBridgeDrawer({ open, onClose, activeTopicId, courseId, agyCli = false, pendingPrompt = null, onClearPendingPrompt = null }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [explanationLevel, setExplanationLevel] = useState(2);
  const [attachedImages, setAttachedImages] = useState([]);
  const [uploadingImage, setUploadingImage] = useState(false);
  const logRef = useRef(null);
  const inputRef = useRef(null);
  const attachedImagesRef = useRef(attachedImages);
  attachedImagesRef.current = attachedImages;

  useEffect(() => {
    return () => {
      attachedImagesRef.current.forEach((img) => {
        if (img.previewUrl) URL.revokeObjectURL(img.previewUrl);
      });
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    api('/api/agy/messages')
      .then((list) => {
        if (!Array.isArray(list)) return;
        setMessages((prev) => {
          const localPending = prev.filter((m) =>
            m.id?.startsWith('local-') && !list.some((serverMsg) => serverMsg.sender === 'user' && serverMsg.content === m.content)
          );
          return [...list.slice(-60), ...localPending];
        });
      })
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

  const send = async (text, levelOverride) => {
    const rawPrompt = (text ?? input).trim();
    if ((!rawPrompt && attachedImages.length === 0) || sending) return;

    const activeLevel = levelOverride !== undefined ? levelOverride : explanationLevel;
    let fullPrompt = rawPrompt;
    if (activeLevel !== null && activeLevel !== undefined && !fullPrompt.includes('[Explanation Level')) {
      const lvl = EXPLANATION_LEVELS.find((l) => l.level === activeLevel);
      if (lvl) {
        fullPrompt = `[Explanation Level ${lvl.level}: ${lvl.title}] ${fullPrompt}`.trim();
      }
    }

    if (attachedImages.length > 0) {
      const imageDescriptions = attachedImages
        .map((img) => (img.extractedText ? `[Attached Image: ${img.name}]\n${img.extractedText}` : `[Attached Image: ${img.name}]`))
        .join('\n\n');
      fullPrompt = [fullPrompt, imageDescriptions].filter(Boolean).join('\n\n');
      attachedImages.forEach((img) => { if (img.previewUrl) URL.revokeObjectURL(img.previewUrl); });
      setAttachedImages([]);
    }

    setInput('');
    setError(null);
    setSending(true);
    const historyPayload = messages.slice(-16).map((m) => ({ role: m.sender === 'user' ? 'user' : 'model', content: m.content || '' }));
    setMessages((list) => [...list, { id: `local-${Date.now()}`, sender: 'user', content: fullPrompt }]);
    try {
      await api('/api/agy/prompt', {
        method: 'POST',
        body: {
          prompt: fullPrompt,
          topicId: activeTopicId,
          courseId,
          level: activeLevel,
          history: historyPayload,
        },
      });
    } catch (e) {
      setError(`AGY didn't answer: ${e.message}`);
    } finally {
      setSending(false);
    }
  };

  useEffect(() => {
    if (pendingPrompt && open) {
      const promptText = typeof pendingPrompt === 'object' ? pendingPrompt.prompt : pendingPrompt;
      const lvl = typeof pendingPrompt === 'object' ? pendingPrompt.level : undefined;
      if (lvl !== undefined && lvl !== null) setExplanationLevel(lvl);
      if (promptText) send(promptText, lvl);
      onClearPendingPrompt?.();
    }
  }, [pendingPrompt, open]); // eslint-disable-line react-hooks/exhaustive-deps

  const handlePaste = async (e) => {
    const clipboardFiles = e.clipboardData?.files ? Array.from(e.clipboardData.files) : [];
    const imageFiles = clipboardFiles.filter((f) => f.type.startsWith('image/'));
    if (imageFiles.length === 0) return;
    e.preventDefault();
    e.stopPropagation();
    const disambiguated = [];
    for (const f of imageFiles) {
      disambiguated.push(disambiguateFile(f, [...attachedImages, ...disambiguated]));
    }
    if (!(await confirmGeminiUpload(disambiguated))) return;
    setUploadingImage(true);
    setError(null);
    try {
      const up = await uploadFiles(disambiguated);
      const newImages = disambiguated.map((f, idx) => {
        const fname = f.name || f._displayName || '';
        const match = up?.files?.find((u) => u.filename?.toLowerCase() === fname.toLowerCase());
        return {
          id: f.uid,
          name: fname || 'screenshot.png',
          previewUrl: URL.createObjectURL(f),
          extractedText: match?.extracted_text ?? (idx === 0 ? up?.extracted_text || '' : ''),
        };
      });
      setAttachedImages((prev) => [...prev, ...newImages]);
    } catch (err) {
      setError(handleUploadConsentError(err));
    } finally {
      setUploadingImage(false);
    }
  };

  const removeAttachedImage = (id) => {
    setAttachedImages((prev) => {
      const target = prev.find((x) => x.id === id);
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl);
      return prev.filter((x) => x.id !== id);
    });
  };

  if (!open) return null;

  return (
    <>
      <div className="agy-scrim" onClick={onClose} aria-hidden="true" />
      <aside className="agy-panel" aria-label="Assistant" onPaste={handlePaste}>
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
        <div className="level-pills" role="radiogroup" aria-label="Explanation level">
          <span className="level-label">Depth:</span>
          {EXPLANATION_LEVELS.map(({ level, title }) => (
            <button
              key={level}
              type="button"
              className={`level-pill${explanationLevel === level ? ' level-pill-active' : ''}`}
              role="radio"
              aria-checked={explanationLevel === level}
              onClick={() => setExplanationLevel(level)}
            >
              {level}: {title}
            </button>
          ))}
        </div>
        {attachedImages.length > 0 && (
          <div className="attached-images">
            {attachedImages.map((img) => (
              <span key={img.id} className="image-chip">
                <img src={img.previewUrl} alt="" className="image-chip-thumb" />
                <span className="image-chip-name">{img.name}</span>
                <button
                  type="button"
                  className="btn btn-quiet btn-sm btn-icon"
                  style={{ minHeight: 20, width: 20, border: 0 }}
                  onClick={() => removeAttachedImage(img.id)}
                  aria-label={`Remove ${img.name}`}
                >
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
        )}
        {uploadingImage && <p className="hint" style={{ padding: '0 var(--space-4) var(--space-2)' }}><Loader2 size={12} className="spin" aria-hidden="true" /> Reading pasted image…</p>}
        <form className="agy-form" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <label htmlFor="agy-input" className="visually-hidden">Message AGY</label>
          <input id="agy-input" ref={inputRef} className="input" value={input} onChange={(e) => setInput(e.target.value)}
            placeholder="Ask AGY (or paste image Ctrl+V)…" autoComplete="off" />
          <button type="submit" className="btn btn-primary btn-icon" disabled={sending || (!input.trim() && attachedImages.length === 0)} aria-label="Send"><Send size={16} /></button>
        </form>
      </aside>
    </>
  );
}
