import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Play, Pause, SkipBack, SkipForward, X, Loader2, RotateCcw } from 'lucide-react';
import { api } from '../lib/api';
import { clipUrl, speak, stopSpeech } from '../lib/speech';
import { collectAnchors } from '../lib/explainAnchors';
import { showStep } from '../lib/explainFx';

const SPEEDS = [0.8, 1, 1.25];
const clip = (text) => clipUrl(text, 'en', { purpose: 'explain' });
// about how long a step is read for, so timed animations (and the no-voice fallback) fit the words
const stepMs = (say, speed) => Math.max(2500, (say.length * 65) / speed);

/** Waits (at most ~1.5 s) for the concept diagram to finish rendering, so the walkthrough can point at it. */
async function diagramSettled(root) {
  for (let i = 0; i < 10; i += 1) {
    const d = root?.querySelector('[data-explain="diagram"]');
    if (!d || d.querySelector('svg')) return;
    await new Promise((r) => setTimeout(r, 150));
  }
}

/**
 * "Explain it to me": a narrated walkthrough of the lesson under rootRef. Fetches the steps
 * (POST /api/topics/{id}/explain), then for each step spotlights its block and reads the line with the recorded voice
 * (its own Audio element: the next step starts only when the clip ends) or, when there is no clip, the browser voice.
 * Every async callback checks playId, so a stale clip can never start after a skip, a pause or closing.
 */
export default function ExplainPlayer({ topic, rootRef, onClose }) {
  const [segments, setSegments] = useState(null);
  const [status, setStatus] = useState('loading'); // loading | playing | paused | done | error
  const [index, setIndex] = useState(0);
  const [speed, setSpeed] = useState(1);
  const [browserVoice, setBrowserVoice] = useState(false);
  const [noVoice, setNoVoice] = useState(false);
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const playId = useRef(0);
  const audioRef = useRef(null);
  const timerRef = useRef(null);
  const fxRef = useRef(null);
  const segsRef = useRef(null);
  const indexRef = useRef(0);
  const statusRef = useRef('loading');
  const speedRef = useRef(1);
  const barRef = useRef(null);
  const playBtn = useRef(null);

  const phase = useCallback((s) => { statusRef.current = s; setStatus(s); }, []);
  const silence = useCallback(() => {
    if (audioRef.current) { audioRef.current.onended = null; audioRef.current.pause(); audioRef.current = null; }
    clearTimeout(timerRef.current);
    window.speechSynthesis?.cancel();
  }, []);
  const clearFx = useCallback(() => { fxRef.current?.(); fxRef.current = null; }, []);

  const play = useCallback(async function step(i) {
    const segs = segsRef.current;
    if (!segs?.length) return;
    const id = ++playId.current;
    const at = Math.max(0, i);
    try {
      silence();
      clearFx();
      if (i >= segs.length) { phase('done'); return; }
      const seg = segs[at];
      indexRef.current = at;
      setIndex(at);
      phase('playing');
      const root = rootRef.current;
      const el = root?.querySelector(`[data-explain="${CSS.escape(seg.anchor)}"]`);
      const ms = stepMs(seg.say, speedRef.current);
      fxRef.current = showStep(el, { highlight: seg.highlight, animation: seg.animation, durationMs: ms });
      segs.slice(at + 1, at + 3).forEach((s) => clip(s.say));  // the next two lines load while this one plays
      const advance = () => { if (playId.current === id) step(at + 1); };

      let fellBack = false;
      const browserRead = async () => {  // no clip (capped, off, failed) for this line: the browser voice reads it
        if (fellBack || playId.current !== id) return;
        fellBack = true;
        setBrowserVoice(true);
        // a failed utterance (or one cut off by another speaker) falls back to the captions' timing, so the tour goes on
        const onerror = () => { if (playId.current === id) { clearTimeout(timerRef.current); timerRef.current = setTimeout(advance, ms); } };
        const r = await speak(seg.say, 'en', { rate: 0.95 * speedRef.current, onend: advance, onerror, isStale: () => playId.current !== id });
        if (playId.current !== id) return;
        if (!r.ok) { setNoVoice(true); timerRef.current = setTimeout(advance, ms); }  // no voice at all: captions only
      };

      const url = await clip(seg.say);
      if (playId.current !== id) return;
      if (!url) { browserRead(); return; }
      const a = new Audio(url);
      a.playbackRate = speedRef.current;
      a.preservesPitch = true;
      a.mozPreservesPitch = true;
      a.webkitPreservesPitch = true;
      a.onended = advance;
      a.onerror = () => { if (audioRef.current === a) { audioRef.current = null; browserRead(); } };
      audioRef.current = a;
      try { await a.play(); } catch (e) {
        // paused (or skipped) before the clip started: play() rejects with AbortError, and the tour must stay quiet
        if (playId.current !== id || statusRef.current === 'paused' || e?.name === 'AbortError') return;
        if (audioRef.current === a) audioRef.current = null;  // autoplay blocked or a broken clip
        browserRead();
      }
    } catch (e) {  // an unexpected error in one step never freezes the tour: move on after a short pause
      console.warn('Walkthrough step failed', e);
      if (playId.current === id) timerRef.current = setTimeout(() => { if (playId.current === id) step(at + 1); }, 2500);
    }
  }, [rootRef, phase, silence, clearFx]);

  // fetch the walkthrough (again on Retry), then start at step 1
  useEffect(() => {
    let alive = true;
    phase('loading');
    setError(null);
    stopSpeech();
    (async () => {
      await diagramSettled(rootRef.current);
      if (!alive) return;
      const anchors = collectAnchors(rootRef.current);
      const d = await api(`/api/topics/${encodeURIComponent(topic.id)}/explain`, { method: 'POST', body: { anchors } });
      if (!alive) return;
      segsRef.current = d.segments || [];
      setSegments(segsRef.current);
      if (d.voice === 'browser') setBrowserVoice(true);
      play(0);
    })().catch((e) => { if (alive) { setError(e.message); phase('error'); } });
    return () => { alive = false; };
  }, [topic.id, attempt, rootRef, play, phase]);

  // stop everything when the player goes away (closed, another tab, another lesson)
  useEffect(() => {
    const root = rootRef.current;
    root?.classList.add('explain-touring');
    return () => {
      playId.current += 1;
      silence();
      clearFx();
      root?.classList.remove('explain-touring');
    };
  }, [rootRef, silence, clearFx]);

  // focus the bar while it loads, then the play button (keyboard users land on the controls)
  const ready = status !== 'loading';
  useEffect(() => {
    const btn = playBtn.current;
    (btn && !btn.disabled ? btn : barRef.current)?.focus({ preventScroll: true });
  }, [ready]);

  const toggle = useCallback(() => {
    const s = statusRef.current;
    if (s === 'playing') {
      if (audioRef.current) audioRef.current.pause();
      else { playId.current += 1; silence(); }  // the browser voice can't pause reliably: the step restarts on resume
      phase('paused');
    } else if (s === 'paused') {
      const a = audioRef.current;
      if (a && !a.ended) { phase('playing'); a.play().catch(() => play(indexRef.current)); }
      else play(indexRef.current);
    } else if (s === 'done') {
      play(0);
    }
  }, [play, phase, silence]);

  const go = useCallback((delta) => {
    const segs = segsRef.current;
    if (!segs?.length || statusRef.current === 'loading') return;
    play(Math.min(segs.length - 1, Math.max(0, indexRef.current + delta)));
  }, [play]);

  const close = useCallback(() => {
    playId.current += 1;
    silence();
    clearFx();
    onClose();
  }, [onClose, silence, clearFx]);

  const changeSpeed = (s) => {
    speedRef.current = s;
    setSpeed(s);
    if (audioRef.current) audioRef.current.playbackRate = s;
  };

  // Space play/pause, arrows previous/next, Esc close (not while typing, and Space leaves focused buttons alone)
  useEffect(() => {
    const onKey = (e) => {
      if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
      const t = e.target;
      if (t?.closest?.('input, textarea, select, [contenteditable="true"], [role="dialog"]')) return;
      if (e.key === 'Escape') { e.preventDefault(); close(); }
      else if (e.key === ' ' && !t?.closest?.('button, a, [role="button"], [role="tab"]')) { e.preventDefault(); toggle(); }
      else if (e.key === 'ArrowRight' && !t?.closest?.('[role="tab"]')) { e.preventDefault(); go(1); }
      else if (e.key === 'ArrowLeft' && !t?.closest?.('[role="tab"]')) { e.preventDefault(); go(-1); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [close, toggle, go]);

  const total = segments?.length || 0;
  const seg = segments?.[index];
  const playing = status === 'playing';

  return (
    <div className="explain-bar" role="region" aria-label="Lesson walkthrough" ref={barRef} tabIndex={-1}>
      {total > 0 && (
        <div className="explain-progress" aria-hidden="true">
          <span style={{ width: `${(status === 'done' ? 1 : (index + 1) / total) * 100}%` }} />
        </div>
      )}
      <div className="explain-body">
        {status === 'loading' && (
          <p className="explain-caption" role="status"><Loader2 size={16} className="spin" aria-hidden="true" /> Preparing your walkthrough…</p>
        )}
        {status === 'error' && <p className="explain-caption err" role="alert">{error}</p>}
        {status === 'done' && <p className="explain-caption" role="status">That's the walkthrough. Replay it, or scroll back to any part.</p>}
        {(playing || status === 'paused') && seg && <p className="explain-caption" aria-live="polite">{seg.say}</p>}
        <div className="explain-meta">
          {total > 0 && status !== 'done' && <span className="explain-step">Step {index + 1} of {total}</span>}
          {status === 'paused' && <span>Paused</span>}
          {browserVoice && status !== 'loading' && status !== 'error' && (
            <span className="hint">{noVoice ? 'No voice available: read along with the captions.' : 'Using your browser voice.'}</span>
          )}
        </div>
      </div>
      <div className="explain-controls">
        {status === 'error' ? (
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => setAttempt((n) => n + 1)}>
            <RotateCcw size={14} aria-hidden="true" /> Try again
          </button>
        ) : (
          <>
            <button type="button" className="btn btn-quiet btn-sm btn-icon" onClick={() => go(-1)} disabled={!total || index === 0 || status === 'done'}
              aria-label="Previous step" title="Previous step (Left arrow)"><SkipBack size={16} aria-hidden="true" /></button>
            <button type="button" ref={playBtn} className="btn btn-primary btn-sm explain-play" onClick={toggle} disabled={!total}
              aria-label={playing ? 'Pause' : status === 'done' ? 'Replay' : 'Play'} title="Play or pause (Space)">
              {playing ? <Pause size={16} aria-hidden="true" /> : status === 'done' ? <RotateCcw size={16} aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
            </button>
            <button type="button" className="btn btn-quiet btn-sm btn-icon" onClick={() => go(1)} disabled={!total || index >= total - 1 || status === 'done'}
              aria-label="Next step" title="Next step (Right arrow)"><SkipForward size={16} aria-hidden="true" /></button>
            <div className="explain-speed" role="group" aria-label="Speed">
              {SPEEDS.map((s) => (
                <button key={s} type="button" className="btn btn-quiet btn-sm" aria-pressed={speed === s} onClick={() => changeSpeed(s)}>{s}×</button>
              ))}
            </div>
          </>
        )}
        <button type="button" className="btn btn-quiet btn-sm btn-icon" onClick={close} aria-label="Close walkthrough" title="Close (Esc)">
          <X size={16} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
