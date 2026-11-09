import React, { useEffect, useRef, useState } from 'react';
import { Send, Loader2, RotateCcw, X } from 'lucide-react';
import Md from './Md';
import { api, uploadFiles } from '../lib/api';
import { confirmGeminiUpload, handleUploadConsentError } from '../lib/consent';
import { disambiguateFile } from '../lib/files';

// The brief costs a model call: keep it per lesson for this session instead of refetching on every visit.
const briefCache = new Map();

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
  const [brief, setBrief] = useState(() => briefCache.get(topic.id) ?? null);
  const [turns, setTurns] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [attachedImages, setAttachedImages] = useState([]);
  const [uploadingImage, setUploadingImage] = useState(false);
  const logRef = useRef(null);
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
    if (briefCache.has(topic.id)) return undefined;
    let live = true;
    api('/api/tutor/lesson', { method: 'POST', body: { topicId: topic.id, mode: 'brief' } })
      .then((d) => {
        const text = (d.reply || '').replace(/\n(?!\n)/g, '\n\n');  // one line per part
        briefCache.set(topic.id, text);
        if (live) setBrief(text);
      })
      .catch(() => live && setBrief(''));
    return () => { live = false; };
  }, [topic.id]);

  useEffect(() => { logRef.current?.scrollTo({ top: logRef.current.scrollHeight }); }, [turns, busy]);

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

  const ask = async (text, withFocus = null) => {
    let message = (text ?? input).trim();
    if ((!message && attachedImages.length === 0) || busy) return;

    if (attachedImages.length > 0) {
      const imageDescriptions = attachedImages
        .map((img) => (img.extractedText ? `[Attached Image: ${img.name}]\n${img.extractedText}` : `[Attached Image: ${img.name}]`))
        .join('\n\n');
      message = [message, imageDescriptions].filter(Boolean).join('\n\n');
      attachedImages.forEach((img) => { if (img.previewUrl) URL.revokeObjectURL(img.previewUrl); });
      setAttachedImages([]);
    }

    const history = turns.map((t) => ({ role: t.role, content: t.content }));
    setTurns((t) => [...t, { role: 'user', content: message }]);
    setInput('');
    setBusy(true);
    setError(null);
    try {
      const { reply } = await api('/api/tutor/lesson', {
        method: 'POST', body: { topicId: topic.id, message, history, focus: withFocus ?? focus ?? undefined },
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

      <div className="panel tutor" onPaste={handlePaste}>
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
        {attachedImages.length > 0 && (
          <div className="attached-images" style={{ padding: 'var(--space-2) 0' }}>
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
        {uploadingImage && <p className="hint" style={{ padding: 'var(--space-1) 0' }}><Loader2 size={12} className="spin" aria-hidden="true" /> Reading pasted image…</p>}
        <form className="agy-form" style={{ padding: 0, border: 0 }} onSubmit={(e) => { e.preventDefault(); ask(); }}>
          <label htmlFor="tutor-input" className="visually-hidden">Ask the tutor</label>
          <input id="tutor-input" className="input" value={input} onChange={(e) => setInput(e.target.value)}
            placeholder="What's confusing you? (or paste image Ctrl+V)" autoComplete="off" />
          <button type="submit" className="btn btn-primary btn-icon" disabled={busy || (!input.trim() && attachedImages.length === 0)} aria-label="Send"><Send size={16} /></button>
        </form>
      </div>
    </section>
  );
}
