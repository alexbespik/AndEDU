import React, { useEffect, useRef, useState } from 'react';
import { MoreHorizontal, Headphones, Download, Square, Loader2 } from 'lucide-react';
import { api, downloadFile } from '../lib/api';
import { pickVoice } from '../lib/speech';

/**
 * Secondary topic actions. The spoken lecture from &EDU lives here, out of the main flow.
 * It uses the browser's built-in voice (free) unless the server enables ElevenLabs (SCIEDU_ELEVENLABS=1).
 */
export default function MoreMenu({ topic, courseTitle }) {
  const [open, setOpen] = useState(false);
  const [lecture, setLecture] = useState('idle'); // idle | loading | playing
  const [error, setError] = useState(null);
  const audioRef = useRef(null);
  const enVoice = useRef(null);  // a real English voice, not whatever the browser defaults to
  useEffect(() => { pickVoice('en').then((v) => { enVoice.current = v; }); }, []);
  const wrapRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (!wrapRef.current?.contains(e.target)) setOpen(false); };
    const esc = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc); };
  }, [open]);

  const stop = () => {
    audioRef.current?.pause();
    audioRef.current = null;
    window.speechSynthesis?.cancel();
    setLecture('idle');
  };
  useEffect(() => stop, [topic.id]);

  const speak = (script) => {
    if (!window.speechSynthesis) throw new Error('This browser cannot read text aloud.');
    const u = new SpeechSynthesisUtterance(script);
    if (enVoice.current) { u.voice = enVoice.current; u.lang = enVoice.current.lang; }
    u.rate = 0.96;
    u.onend = () => setLecture('idle');
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  };

  const listen = async () => {
    setOpen(false);
    setError(null);
    setLecture('loading');
    try {
      const d = await api('/api/elevenlabs-voiceover', {
        method: 'POST',
        body: { chapter_title: topic.title, course_title: courseTitle || topic.category, content_markdown: topic.markdownContent },
      });
      if (d.success && d.audio_base64) {
        const audio = new Audio(`data:audio/mpeg;base64,${d.audio_base64}`);
        audio.onended = () => setLecture('idle');
        audioRef.current = audio;
        await audio.play();
      } else if (d.script) {
        speak(d.script);
      } else {
        throw new Error(d.message || 'No lecture could be prepared.');
      }
      setLecture('playing');
    } catch (e) {
      setError(e.message);
      setLecture('idle');
    }
  };

  return (
    <div className="more" ref={wrapRef}>
      {lecture !== 'idle' && (
        <button type="button" className="btn btn-secondary btn-sm" onClick={stop}>
          {lecture === 'loading' ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <Square size={14} aria-hidden="true" />}
          {lecture === 'loading' ? ' Preparing lecture…' : ' Stop lecture'}
        </button>
      )}
      <button type="button" className="btn btn-quiet btn-sm" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <MoreHorizontal size={14} aria-hidden="true" /> More
      </button>
      {open && (
        <div className="menu" role="menu">
          <button type="button" role="menuitem" onClick={listen} disabled={lecture !== 'idle'}>
            <Headphones size={14} aria-hidden="true" /> Listen to a short lecture
          </button>
          {topic.notesFile && (
            <button type="button" role="menuitem"
              onClick={() => { setOpen(false); downloadFile(`/api/notes/${topic.id}.md`, `${topic.id}.md`).catch((e) => setError(e.message)); }}>
              <Download size={14} aria-hidden="true" /> Download notes (.md)
            </button>
          )}
        </div>
      )}
      {error && <span className="hint" style={{ color: 'var(--bad)' }}>{error}</span>}
    </div>
  );
}
