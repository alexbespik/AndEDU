// More language exercises: story, dialogue, conjugate, script_match (normalized by practice_language_extra.py).
// Each body takes {item, onResult(ok, given), retry}; ok === null means ungraded (dialogue) or skipped.
// Used by PracticeDeck through registry.js and by the extra Languages tabs (src/components/language/).
import React, { useEffect, useRef, useState } from 'react';
import { Volume2, Play, Pause, RotateCcw, Check, Send, Loader2, Eye, EyeOff, Flag } from 'lucide-react';
import Md, { MdInline } from '../components/Md';
import { MatchPairs } from '../components/Activities';
import { ExplainAnswerButton } from '../components/ExplainDialog';
import { speakAudio, stopSpeech, isSpeaking, noVoiceHelp, languageName } from '../lib/speech';
import { gradeText } from '../lib/langgrade';
import { api } from '../lib/api';
import { SCRIPT_LANG, speakerStyles, correctionsOf } from '../components/language/util';
import '../styles/language_extra.css';

const MAX_TURNS = 6;
const voiceNote = (r) => (r.reason === 'no-voice' ? noVoiceHelp(r.language) : 'This browser cannot read text aloud.');

/** Resolves once the browser has finished speaking (or stop() turns true, or 30 s pass). */
function untilQuiet(stop) {
  const t0 = Date.now();
  return new Promise((resolve) => {
    const tick = () => {
      const quiet = !isSpeaking();
      if (stop() || (quiet && Date.now() - t0 > 300) || Date.now() - t0 > 30000) resolve();
      else setTimeout(tick, 150);
    };
    setTimeout(tick, 150);
  });
}

function Feedback({ ok, title, item, given, answer, onRetry, children }) {
  return (
    <div className={`feedback ${ok ? 'ok' : 'bad'}`} aria-live="polite">
      <p style={{ fontWeight: 700, marginBottom: 4 }}>{title}</p>
      {children}
      {item.explanation && <Md>{item.explanation}</Md>}
      {!ok && (
        <div className="btn-row" style={{ marginTop: 6 }}>
          <ExplainAnswerButton item={item} studentAnswer={given} correctAnswer={answer} lang={item.lang} />
          {onRetry && <button type="button" className="btn btn-quiet btn-sm" onClick={onRetry}><RotateCcw size={14} aria-hidden="true" /> Try again</button>}
        </div>
      )}
    </div>
  );
}

/**
 * A story read aloud line by line, each speaker with their own reading style; questions appear after their line.
 * listenOnly hides the text until the student asks for it.
 */
export function StoryPlayer({ item, onResult, retry = true, listenOnly = false }) {
  const lines = item.lines || [], questions = item.questions || [];
  const styles = speakerStyles(lines);
  const [shown, setShown] = useState(0);
  const [picks, setPicks] = useState({});
  const [playing, setPlaying] = useState(false);
  const [showText, setShowText] = useState(!listenOnly);
  const [openTr, setOpenTr] = useState({});
  const [note, setNote] = useState(null);
  const run = useRef(0), shownRef = useRef(0), auto = useRef(false), reported = useRef(false);
  useEffect(() => () => { clearTimeout(resume.current); run.current++; stopSpeech(); }, []);
  useEffect(() => setShowText(!listenOnly), [listenOnly]);

  const waitingAt = (i) => questions.some((q, k) => q.after === i && !(k in picks));
  const blocked = shown > 0 && waitingAt(shown - 1);
  const say = async (line, stop) => {
    const r = await speakAudio(line.text, item.lang, styles[line.speaker]);
    if (!r.ok) { setNote(voiceNote(r)); return; }
    await untilQuiet(stop);
  };
  const play = async (from = shownRef.current) => {
    const id = ++run.current;
    const stop = () => id !== run.current;
    auto.current = true;
    setPlaying(true);
    for (let i = from; i < lines.length && !stop(); i++) {
      shownRef.current = i + 1;
      setShown(i + 1);
      await say(lines[i], stop);
      if (questions.some((q) => q.after === i)) break;  // wait for the answers to this line's questions
    }
    if (!stop()) setPlaying(false);
  };
  const resume = useRef(null);  // the short pause before playing on after a question
  const pause = () => { clearTimeout(resume.current); run.current++; auto.current = false; setPlaying(false); stopSpeech(); };
  const replay = (line) => { run.current++; setPlaying(false); say(line, () => false); };
  const pick = (k, opt) => {
    if (k in picks) return;
    const next = { ...picks, [k]: opt };
    setPicks(next);
    const after = questions[k].after;
    const blockDone = questions.every((q, j) => q.after !== after || j in next);
    if (Object.keys(next).length === questions.length && !reported.current) {
      reported.current = true;
      onResult?.(questions.every((q, j) => next[j] === q.answer), questions.map((q, j) => next[j]).join(' | '));
    }
    if (blockDone && auto.current && shownRef.current < lines.length) { clearTimeout(resume.current); resume.current = setTimeout(() => play(), 500); }
  };
  const reset = () => { pause(); shownRef.current = 0; reported.current = false; setShown(0); setPicks({}); setOpenTr({}); setNote(null); };

  const answered = Object.keys(picks).length;
  const finished = questions.length > 0 && answered === questions.length;
  const right = questions.filter((q, j) => picks[j] === q.answer).length;
  return (
    <div className="stack-sm lx-story">
      <div className="lx-story-head">
        {item.title && <strong lang={item.lang}>{item.title}</strong>}
        <span className="hint">{languageName(item.lang)} · {Object.keys(styles).length} voices</span>
      </div>
      <div className="btn-row">
        {playing
          ? <button type="button" className="btn btn-quiet btn-sm" onClick={pause}><Pause size={14} aria-hidden="true" /> Pause</button>
          : <button type="button" className="btn btn-primary btn-sm" disabled={blocked || shown >= lines.length} onClick={() => play()}>
            <Play size={14} aria-hidden="true" /> {shown === 0 ? 'Play story' : 'Continue'}</button>}
        {listenOnly && <button type="button" className="btn btn-quiet btn-sm" onClick={() => setShowText((v) => !v)} aria-pressed={showText}>
          {showText ? <EyeOff size={14} aria-hidden="true" /> : <Eye size={14} aria-hidden="true" />} {showText ? 'Hide text' : 'Show text'}</button>}
        {shown > 0 && <button type="button" className="btn btn-quiet btn-sm" onClick={reset}><RotateCcw size={14} aria-hidden="true" /> Start over</button>}
      </div>
      {note && <p className="notice notice-info">{note}</p>}
      <ol className="lx-story-lines">
        {lines.slice(0, shown).map((line, i) => (
          <li key={i} className="lx-story-line">
            <div className="lx-line-row">
              <span className="lx-speaker">{line.speaker || '—'}</span>
              <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label={`Hear line ${i + 1} again`} onClick={() => replay(line)}><Volume2 size={14} aria-hidden="true" /></button>
              {showText ? <span className="lx-line-text" lang={item.lang}>{line.text}</span> : <span className="hint">(listen)</span>}
            </div>
            {showText && line.translation && (
              <button type="button" className="lx-link" onClick={() => setOpenTr((o) => ({ ...o, [i]: !o[i] }))}>
                {openTr[i] ? line.translation : 'Show translation'}</button>
            )}
            {questions.map((q, k) => q.after === i && (
              <div key={k} className="lx-story-q stack-sm">
                <p style={{ fontWeight: 600 }}><MdInline>{q.question}</MdInline></p>
                <div className="choices">
                  {q.options.map((opt, j) => (
                    <button key={opt} type="button" className="choice" disabled={k in picks}
                      data-result={k in picks ? (opt === q.answer ? 'correct' : opt === picks[k] ? 'wrong' : undefined) : undefined}
                      onClick={() => pick(k, opt)}><span className="key">{'ABCDEF'[j]}</span><span><MdInline>{opt}</MdInline></span><span /></button>
                  ))}
                </div>
              </div>
            ))}
          </li>
        ))}
      </ol>
      {finished && (
        <Feedback ok={right === questions.length} title={right === questions.length ? 'All right.' : `${right} of ${questions.length} right.`}
          item={item} given={questions.map((q, j) => picks[j]).join(' | ')} answer={questions.map((q) => q.answer).join(' | ')}
          onRetry={retry ? reset : null} />
      )}
    </div>
  );
}

function Story(props) { return <StoryPlayer {...props} />; }

/**
 * A chat with an AI persona (POST /api/language/roleplay). Ungraded: after the goal or MAX_TURNS student turns it
 * calls onResult(null, transcript) and shows a recap with every correction.
 */
export function DialogueChat({ item, onResult }) {
  const [msgs, setMsgs] = useState([]);       // [{role: 'user'|'model', text, translation?, corrections?, tip?}]
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [offline, setOffline] = useState(false);
  const [done, setDone] = useState(false);
  const [note, setNote] = useState(null);
  const alive = useRef(true), conv = useRef(0);
  useEffect(() => { alive.current = true; return () => { alive.current = false; stopSpeech(); }; }, []);  // StrictMode remounts
  const turns = msgs.filter((m) => m.role === 'user').length;

  const finish = (all) => {
    if (done) return;
    setDone(true);
    onResult?.(null, all.filter((m) => m.role === 'user').map((m) => m.text).join('\n'));
  };
  const send = async (text, before = msgs) => {
    const id = conv.current;
    const prior = before.map((m) => ({ role: m.role, text: m.text }));
    const withUser = text ? [...before, { role: 'user', text }] : before;
    setMsgs(withUser);
    setInput('');
    setBusy(true);
    setError(null);
    try {
      const res = await api('/api/language/roleplay', {
        method: 'POST',
        body: {
          ...(item.topicId ? { topicId: item.topicId } : {}),
          persona: item.persona, setting: item.setting, goal: item.goal, lang: item.lang, level: item.level,
          scenario: item.setting || item.persona, target_lang: item.lang, user_message: text, history: prior,
        },
      });
      if (!alive.current || id !== conv.current) return;
      if (res?.fallback) setOffline(true);
      const corrections = text ? correctionsOf(res) : [];
      const tip = text ? String(res?.feedback?.tip || '') : '';
      const next = [...before, ...(text ? [{ role: 'user', text, corrections, tip }] : []),
        { role: 'model', text: String(res?.reply || ''), translation: res?.translation || '' }];
      setMsgs(next);
      if (text && next.filter((m) => m.role === 'user').length >= MAX_TURNS) finish(next);
    } catch {
      if (alive.current && id === conv.current) setError("Your conversation partner isn't available right now (no connection or the daily model limit was reached). Try again in a moment.");
    } finally {
      if (alive.current && id === conv.current) setBusy(false);
    }
  };
  const retry = () => {  // resend the student's last message, or ask for the opening line again
    const last = msgs[msgs.length - 1];
    if (last?.role === 'user') send(last.text, msgs.slice(0, -1));
    else send('');
  };
  const hear = (text) => speakAudio(text, item.lang).then((r) => setNote(r.ok ? null : voiceNote(r)));
  const restart = () => { conv.current++; setMsgs([]); setDone(false); setOffline(false); setError(null); setBusy(false); };
  const allCorrections = msgs.flatMap((m) => m.corrections || []);

  return (
    <div className="stack-sm lx-dialogue">
      <div className="lang-source lx-dialogue-brief">
        <span><strong>{item.persona}</strong> · {item.setting}</span>
        <span className="hint">Goal: {item.goal} · {languageName(item.lang)} {item.level}</span>
      </div>
      {offline && <p className="notice notice-info">The AI partner is offline, so a scripted partner is answering.</p>}
      {note && <p className="notice notice-info">{note}</p>}
      {!msgs.length && !busy && !error && (
        <div className="btn-row"><button type="button" className="btn btn-primary btn-sm" onClick={() => send('')}><Play size={14} aria-hidden="true" /> Start the conversation</button></div>
      )}
      {msgs.length > 0 && (
        <div className="lx-chat" aria-live="polite">
          {msgs.map((m, i) => (
            <div key={i} className={`lx-msg ${m.role === 'user' ? 'lx-msg-me' : 'lx-msg-them'}`}>
              <div className="lx-bubble">
                <span className="lx-speaker">{m.role === 'user' ? 'You' : item.persona}</span>
                <span lang={m.role === 'user' ? undefined : item.lang}>{m.text}</span>
                {m.role === 'model' && (
                  <span className="btn-row">
                    <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label="Listen" onClick={() => hear(m.text)}><Volume2 size={14} aria-hidden="true" /></button>
                    {m.translation && <details className="lx-tr"><summary>Translation</summary>{m.translation}</details>}
                  </span>
                )}
              </div>
              {m.corrections?.length > 0 && (
                <ul className="lx-corrections">
                  {m.corrections.map((c, k) => <li key={k}><Correction c={c} lang={item.lang} /></li>)}
                </ul>
              )}
              {m.tip && <p className="hint lx-tip">{m.tip}</p>}
            </div>
          ))}
          {busy && <p className="hint"><Loader2 size={14} className="spin" aria-hidden="true" /> {item.persona} is replying…</p>}
        </div>
      )}
      {error && <div className="notice notice-info">{error} <button type="button" className="btn btn-quiet btn-sm" disabled={busy} onClick={retry}>Retry</button></div>}
      {msgs.length > 0 && !done && (
        <form className="lx-chat-input" onSubmit={(e) => { e.preventDefault(); if (input.trim() && !busy) send(input.trim()); }}>
          <input className="input" value={input} lang={item.lang} disabled={busy} onChange={(e) => setInput(e.target.value)}
            placeholder={`Reply in ${languageName(item.lang)} (${turns}/${MAX_TURNS})`} aria-label="Your reply" />
          <button type="submit" className="btn btn-primary btn-icon" disabled={busy || !input.trim()} aria-label="Send"><Send size={16} aria-hidden="true" /></button>
          <button type="button" className="btn btn-quiet btn-sm" disabled={busy || !turns} onClick={() => finish(msgs)}><Flag size={14} aria-hidden="true" /> Goal reached</button>
        </form>
      )}
      {done && (
        <div className="feedback" aria-live="polite">
          <p style={{ fontWeight: 700, marginBottom: 4 }}>Conversation recap · {turns} {turns === 1 ? 'turn' : 'turns'}</p>
          {allCorrections.length
            ? <ul className="lx-corrections">{allCorrections.map((c, k) => <li key={k}><Correction c={c} lang={item.lang} /></li>)}</ul>
            : <p>No corrections: nicely done.</p>}
          {item.explanation && <Md>{item.explanation}</Md>}
          <div className="btn-row" style={{ marginTop: 6 }}>
            <button type="button" className="btn btn-quiet btn-sm" onClick={restart}><RotateCcw size={14} aria-hidden="true" /> Talk again</button>
          </div>
        </div>
      )}
    </div>
  );
}

function Correction({ c, lang }) {
  return (
    <span className="lx-correction">
      {c.said && <s lang={lang}>{c.said}</s>}
      {c.said && c.better && ' → '}
      {c.better && <strong lang={lang}>{c.better}</strong>}
      {c.why && <span className="hint"> {c.why}</span>}
    </span>
  );
}

function Dialogue(props) { return <DialogueChat {...props} />; }

function Conjugate({ item, onResult, retry = true }) {
  const [vals, setVals] = useState(() => item.forms.map(() => ''));
  const [res, setRes] = useState(null);
  const given = vals.join(', ');
  const check = (e) => {
    e.preventDefault();
    if (res || vals.every((v) => !v.trim())) return;
    const rows = item.forms.map(([, form], i) => gradeText(vals[i], [form]));
    setRes(rows);
    onResult?.(rows.every((r) => r.ok), given);
  };
  const right = res ? res.filter((r) => r.ok).length : 0;
  return (
    <form className="stack-sm" onSubmit={check}>
      <div className="lang-source"><strong lang={item.lang}>{item.verb}</strong><span className="hint">{item.tense} · {languageName(item.lang)}</span></div>
      <div className="lx-conj">
        {item.forms.map(([pronoun, form], i) => (
          <label key={pronoun} className="lx-conj-row" data-result={res ? (res[i].ok ? 'correct' : 'wrong') : undefined}>
            <span className="lx-conj-pronoun" lang={item.lang}>{pronoun}</span>
            <input className="input" value={vals[i]} lang={item.lang} readOnly={!!res} autoComplete="off" spellCheck={false}
              onChange={(e) => setVals((v) => v.map((x, k) => (k === i ? e.target.value : x)))} aria-label={`Form for ${pronoun}`} />
            {res && <span className="lx-conj-mark">{res[i].ok ? (res[i].note ? <span className="hint">{res[i].note}</span> : <Check size={16} aria-label="right" />) : <strong lang={item.lang}>{form}</strong>}</span>}
          </label>
        ))}
      </div>
      {!res && <div className="btn-row"><button type="submit" className="btn btn-primary btn-sm" disabled={vals.every((v) => !v.trim())}><Check size={14} aria-hidden="true" /> Check</button></div>}
      {res && (
        <Feedback ok={right === item.forms.length} title={right === item.forms.length ? 'Correct.' : `${right} of ${item.forms.length} right.`}
          item={item} given={given} answer={item.forms.map(([p, f]) => `${p} ${f}`).join(', ')}
          onRetry={retry ? () => { setRes(null); setVals(item.forms.map(() => '')); } : null} />
      )}
    </form>
  );
}

/** Script drill: MatchPairs, reading each glyph aloud when tapped (item.say may map a glyph to what to read). */
export function ScriptMatch({ item, onResult }) {
  const lang = item.lang || SCRIPT_LANG[item.script];
  const [note, setNote] = useState(null);
  const hear = (e) => {
    const btn = e.target.closest?.('.match-item');
    const col = btn?.parentElement;
    if (!btn || !col || col !== col.parentElement?.firstElementChild) return;  // only the glyph column speaks
    const glyph = btn.textContent.trim();
    speakAudio(item.say?.[glyph] || glyph, lang, { slow: true, rate: 0.75 }).then((r) => setNote(r.ok ? null : voiceNote(r)));
  };
  return (
    <div className="stack-sm lx-script" onClickCapture={hear} lang={lang}>
      <p className="hint">Tap a letter to hear it, then tap its sound.</p>
      {note && <p className="notice notice-info">{note}</p>}
      <MatchPairs item={item} onSolved={() => onResult?.(true, '')} />
    </div>
  );
}

export const LANGUAGE_EXTRA_RENDER = { story: Story, dialogue: Dialogue, conjugate: Conjugate, script_match: ScriptMatch };
export const EXTRA_LANGUAGE_RENDER = LANGUAGE_EXTRA_RENDER;

export const LANGUAGE_EXTRA_LABEL = { story: 'Story', dialogue: 'Conversation', conjugate: 'Conjugate', script_match: 'Letters and sounds' };
export const EXTRA_LANGUAGE_LABEL = LANGUAGE_EXTRA_LABEL;

export const EXTRA_LANGUAGE_TYPES = ['story', 'dialogue', 'conjugate', 'script_match'];
export const LANGUAGE_EXTRA_TYPES = EXTRA_LANGUAGE_TYPES;
