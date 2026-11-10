// Language exercises: translate, word_bank, listen_type, listen_choose, speak.
// Each body takes {item, onResult(ok, given), retry}; ok === null means skipped (no microphone, no voice).
// Used by PracticeDeck (lesson practice) and by the Languages session (LanguageLab).
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Volume2, Snail, Mic, Square, RotateCcw, Check } from 'lucide-react';
import Md, { MdInline } from '../components/Md';
import { speakAudio, stopSpeech, noVoiceHelp, canRecognize, recognize, RECOGNITION_NOTICE } from '../lib/speech';
import { gradeText, similarity, normalizeAnswer } from '../lib/langgrade';
import { ExplainAnswerButton } from '../components/ExplainDialog';
import LangKeyboard from '../components/language/LangKeyboard';

export const LANGUAGE_TYPES = ['translate', 'word_bank', 'listen_type', 'listen_choose', 'speak'];

function seeded(items, seed) {
  const out = [...items];
  let h = 7;
  for (const ch of String(seed)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  for (let i = out.length - 1; i > 0; i--) { h = (h * 1103515245 + 12345) >>> 0; const j = h % (i + 1); [out[i], out[j]] = [out[j], out[i]]; }
  if (out.length > 1 && out.every((v, i) => v === items[i])) out.push(out.shift());  // never in the answer's order
  return out;
}

function Result({ ok, note, answer, item, onRetry, given }) {
  return (
    <div className={`feedback ${ok ? 'ok' : 'bad'}`} aria-live="polite">
      <p style={{ fontWeight: 700, marginBottom: 4 }}>{ok ? 'Correct.' : 'Not quite.'}{note ? ` ${note}` : ''}</p>
      {!ok && answer && <p>Correct answer: <strong lang={item.lang || undefined}>{answer}</strong></p>}
      {item.explanation && <Md>{item.explanation}</Md>}
      {!ok && (
        <div className="btn-row" style={{ marginTop: 6 }}>
          <ExplainAnswerButton
            item={item}
            studentAnswer={given}
            correctAnswer={answer || item.answer || item.target}
            lang={item.lang}
          />
          {onRetry && (
            <button type="button" className="btn btn-quiet btn-sm" onClick={onRetry}>
              <RotateCcw size={14} aria-hidden="true" /> Try again
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/** Play buttons (normal and slow) for text read in a language; shows why when no voice is installed. */
export function ListenButtons({ text, lang, autoPlay = false, label = 'Listen' }) {
  const [note, setNote] = useState(null);
  const play = (slow) => speakAudio(text, lang, { slow }).then((r) => setNote(r.ok ? null : r.reason === 'no-voice' ? noVoiceHelp(r.language) : 'This browser cannot read text aloud.'));
  useEffect(() => {
    if (!autoPlay) return undefined;
    const t = setTimeout(() => play(false), 150);
    return () => clearTimeout(t);
  }, [text, lang]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => stopSpeech(), []);  // nothing keeps talking after the exercise is gone
  return (
    <div className="stack-sm">
      <div className="btn-row">
        <button type="button" className="btn btn-primary lang-play" onClick={() => play(false)} aria-label={label}><Volume2 size={18} aria-hidden="true" /> {label}</button>
        <button type="button" className="btn btn-quiet" onClick={() => play(true)} aria-label="Listen slowly"><Snail size={16} aria-hidden="true" /> Slow</button>
      </div>
      {note && <p className="notice notice-info">{note}</p>}
    </div>
  );
}

function useCheck(onResult) {
  const [res, setRes] = useState(null);
  const done = (r, given) => { setRes(r); onResult?.(r.ok, given); };
  return [res, done, () => setRes(null)];
}

function TypedAnswer({ item, answers, onResult, retry, placeholder, children }) {
  const [value, setValue] = useState('');
  const [res, done, reset] = useCheck(onResult);
  const input = useRef(null);
  const submit = (e) => { e.preventDefault(); if (!res && value.trim()) done(gradeText(value, answers), value); };
  return (
    <form className="stack-sm" onSubmit={submit}>
      {children}
      <textarea ref={input} className="input lang-input" rows={2} value={value} lang={item.lang || undefined} placeholder={placeholder}
        readOnly={!!res} onChange={(e) => setValue(e.target.value)} aria-label="Your answer"
        onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) submit(e); }} />
      {!res && <LangKeyboard lang={item.lang} inputRef={input} value={value} onChange={setValue} />}
      {!res && <div className="btn-row"><button type="submit" className="btn btn-primary btn-sm" disabled={!value.trim()}><Check size={14} aria-hidden="true" /> Check</button></div>}
      {res && <Result ok={res.ok} note={res.note} answer={res.best} item={item} given={value} onRetry={retry ? () => { reset(); setValue(''); } : null} />}
    </form>
  );
}

function Translate({ item, onResult, retry = true }) {
  return (
    <TypedAnswer item={item} answers={[item.answer, ...(item.accepted || [])]} onResult={onResult} retry={retry} placeholder="Type the translation">
      <div className="lang-source">
        <span lang={item.sourceLang || undefined}><MdInline>{item.source}</MdInline></span>
        {item.sourceLang && <ListenButtons text={item.source} lang={item.sourceLang} />}
      </div>
    </TypedAnswer>
  );
}

function ListenType({ item, onResult, retry = true }) {
  return (
    <TypedAnswer item={item} answers={[item.answer, ...(item.accepted || [])]} onResult={onResult} retry={retry} placeholder="Type what you hear">
      <ListenButtons text={item.audio_text} lang={item.lang} autoPlay />
    </TypedAnswer>
  );
}

function ListenChoose({ item, onResult, retry = true }) {
  const [pick, setPick] = useState(null);
  const choose = (opt) => { if (pick !== null) return; setPick(opt); onResult?.(opt === item.answer, opt); };
  return (
    <div className="stack-sm">
      <ListenButtons text={item.audio_text} lang={item.lang} autoPlay />
      <div className="choices">
        {item.options.map((opt, i) => (
          <button key={opt} type="button" className="choice" disabled={pick !== null} lang={item.lang || undefined}
            data-result={pick !== null ? (opt === item.answer ? 'correct' : opt === pick ? 'wrong' : undefined) : undefined} onClick={() => choose(opt)}>
            <span className="key">{'ABCDEF'[i]}</span><span><MdInline>{opt}</MdInline></span><span />
          </button>
        ))}
      </div>
      {pick !== null && <Result ok={pick === item.answer} answer={item.answer} item={item} given={pick} onRetry={retry ? () => setPick(null) : null} />}
    </div>
  );
}

function WordBank({ item, onResult, retry = true }) {
  const tiles = useMemo(() => seeded(item.bank.map((w, i) => ({ w, i })), item.id || item.prompt), [item]);
  const [picked, setPicked] = useState([]);
  const [res, done, reset] = useCheck(onResult);
  const used = new Set(picked);
  const sentence = picked.map((i) => item.bank[i]).join(' ');
  return (
    <div className="stack-sm">
      {item.source && <div className="lang-source"><MdInline>{item.source}</MdInline></div>}
      <div className="lang-answer-line" aria-label="Your sentence" lang={item.lang || undefined}>
        {picked.length ? picked.map((i, k) => (
          <button key={`${i}-${k}`} type="button" className="lang-tile" disabled={!!res} onClick={() => setPicked((p) => p.filter((x) => x !== i))}>{item.bank[i]}</button>
        )) : <span className="hint">Tap the words in order</span>}
      </div>
      <div className="lang-bank" lang={item.lang || undefined}>
        {tiles.map(({ w, i }) => (
          <button key={i} type="button" className="lang-tile" disabled={used.has(i) || !!res} aria-hidden={used.has(i)} onClick={() => setPicked((p) => [...p, i])}>{w}</button>
        ))}
      </div>
      {!res && <div className="btn-row">
        <button type="button" className="btn btn-primary btn-sm" disabled={!picked.length} onClick={() => done({ ok: normalizeAnswer(sentence) === normalizeAnswer(item.answer), best: item.answer }, sentence)}><Check size={14} aria-hidden="true" /> Check</button>
        <button type="button" className="btn btn-quiet btn-sm" onClick={() => setPicked([])} disabled={!picked.length}>Clear</button>
      </div>}
      {res && <Result ok={res.ok} answer={res.best} item={item} given={sentence} onRetry={retry ? () => { reset(); setPicked([]); } : null} />}
    </div>
  );
}

function Speak({ item, onResult, retry = true }) {
  const [state, setState] = useState('idle');   // idle | listening | done
  const [heard, setHeard] = useState('');
  const [res, done, reset] = useCheck(onResult);
  const [err, setErr] = useState(null);
  const handle = useRef(null);
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; handle.current?.stop(); }; }, []);  // close the mic when the item goes away
  const supported = canRecognize();
  const start = async () => {
    const h = recognize(item.lang);
    if (!h) return;
    handle.current = h;
    setState('listening');
    const r = await h.result;
    if (!alive.current) return;
    setState('done');
    if (!r.ok) { setHeard(''); setErr(r.reason); return; }
    const best = r.transcripts.reduce((b, t) => (similarity(t, item.target) > similarity(b, item.target) ? t : b), r.transcripts[0] || '');
    const score = similarity(best, item.target);
    setHeard(best);
    setErr(null);
    done({ ok: score >= 0.8, note: `${Math.round(score * 100)}% match.`, best: item.target }, best);
  };
  return (
    <div className="stack-sm">
      <div className="lang-source">
        <span className="lang-target" lang={item.lang}>{item.target}</span>
        {item.ipa && <span className="ipa-sym lang-ipa">/{item.ipa}/</span>}
        {item.translation && <span className="hint">{item.translation}</span>}
      </div>
      <ListenButtons text={item.target} lang={item.lang} label="Hear it first" />
      {supported ? (
        <>
          {!res && (state === 'listening'
            ? <button type="button" className="btn btn-primary lang-mic" onClick={() => handle.current?.stop()}><Square size={16} aria-hidden="true" /> Listening… tap to stop</button>
            : <button type="button" className="btn btn-primary lang-mic" onClick={start}><Mic size={18} aria-hidden="true" /> Tap and say it</button>)}
          <p className="hint">{RECOGNITION_NOTICE}</p>
          {err && err !== 'skipped' && !res && <p className="notice notice-info">{err === 'not-allowed' ? 'Microphone access was blocked. Allow it in the address bar to use speaking exercises.' : "I didn't catch that. Try again a little closer to the microphone."}</p>}
          {heard && <p>I heard: <em lang={item.lang}>{heard}</em></p>}
          {res && <Result ok={res.ok} note={res.note} answer={res.best} item={item} given={heard} onRetry={retry ? () => { reset(); setHeard(''); setErr(null); setState('idle'); } : null} />}
        </>
      ) : (
        <div className="stack-sm">
          <p className="notice notice-info">This browser can't recognize speech (Chrome, Edge and Safari can). Say it aloud anyway; this one isn't graded.</p>
          {err !== 'skipped' && onResult && <div className="btn-row"><button type="button" className="btn btn-quiet btn-sm" onClick={() => { setErr('skipped'); onResult(null, ''); }}>Skip</button></div>}
        </div>
      )}
    </div>
  );
}

export const LANGUAGE_RENDER = { translate: Translate, word_bank: WordBank, listen_type: ListenType, listen_choose: ListenChoose, speak: Speak };

export const LANGUAGE_LABEL = {
  translate: 'Translate', word_bank: 'Build the sentence', listen_type: 'Type what you hear',
  listen_choose: 'What did you hear?', speak: 'Say it',
};
