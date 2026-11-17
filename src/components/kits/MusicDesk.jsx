import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Play, Plus, Square, Trash2 } from 'lucide-react';
import { DeskCard, Outcome, RunButton, useTool } from './common';

const VOICES = [['s', 'Soprano'], ['a', 'Alto'], ['t', 'Tenor'], ['b', 'Bass']];
const RULE_WORDS = {
  voice_crossing: 'Voice crossing: a lower voice sings above a higher one.',
  parallel_fifth: 'Parallel fifths: two voices move together a perfect fifth apart.',
  parallel_octave: 'Parallel octaves: two voices move together an octave apart.',
  spacing: 'Spacing: neighbouring upper voices are more than an octave apart.',
  range: 'Range: a note is outside the comfortable range of that voice.',
};
const RANGES = 'Ranges: soprano C4-G5, alto G3-D5, tenor C3-G4, bass E2-C4. Write notes like F#3 or Bb4.';
const VOICE_NAME = Object.fromEntries(VOICES.map(([k, v]) => [k, v]));

const DEFAULT_CHORDS = [
  { s: 'E5', a: 'G4', t: 'C4', b: 'C3' },   // I
  { s: 'F5', a: 'A4', t: 'C4', b: 'F3' },   // IV
  { s: 'D5', a: 'G4', t: 'B3', b: 'G3' },   // V
  { s: 'C5', a: 'G4', t: 'E4', b: 'C3' },   // I
];
const SYSTEM_LABEL = { equal: 'Equal temperament', just: 'Just intonation', pythagorean: 'Pythagorean' };
const ALL_SYSTEMS = ['equal', 'just', 'pythagorean'];

function ChordLint() {
  const [chords, setChords] = useState(DEFAULT_CHORDS);
  const [state, run] = useTool('music');
  const submit = () => run('lint', { chords });
  useEffect(() => { submit(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const setNote = (i, v, value) => setChords((cs) => cs.map((c, j) => (j === i ? { ...c, [v]: value } : c)));
  return (
    <DeskCard title="Four-part writing check" what="Checks a chord progression for the classic part-writing faults: voice crossing, parallel fifths and octaves, wide spacing and notes out of range.">
      <p className="hint">{RANGES}</p>
      <div className="kt-scroll">
        <table className="kt-table kt-grid">
          <caption className="kt-sr">Chords, one column per chord</caption>
          <thead>
            <tr>
              <th scope="col"><span className="kt-sr">Voice</span></th>
              {chords.map((_, i) => (
                <th key={i} scope="col">
                  Chord {i + 1}
                  {chords.length > 2 && <button type="button" className="kt-x" aria-label={`Remove chord ${i + 1}`} onClick={() => setChords((cs) => cs.filter((_c, j) => j !== i))}><Trash2 size={12} aria-hidden="true" /></button>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {VOICES.map(([k, name]) => (
              <tr key={k}>
                <th scope="row">{name}</th>
                {chords.map((c, i) => (
                  <td key={i}><input className="kt-input kt-note kt-mono" aria-label={`${name}, chord ${i + 1}`} value={c[k]} onChange={(e) => setNote(i, k, e.target.value)} /></td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="btn-row">
        <button type="button" className="btn btn-quiet btn-sm" disabled={chords.length >= 32} onClick={() => setChords((cs) => [...cs, { ...cs[cs.length - 1] }])}><Plus size={14} aria-hidden="true" /> Add chord</button>
        <RunButton loading={state.loading} onClick={submit}>Check the progression</RunButton>
      </div>
      <Outcome state={state} render={(r) => (
        r.clean ? <p className="notice notice-ok"><strong>No faults found.</strong> This progression passes every check here (it is not a verdict on musical taste).</p> : (
          <ul className="kt-list">
            {r.issues.map((x, i) => (
              <li key={i}>
                <strong>{RULE_WORDS[x.rule] || x.rule}</strong>
                <span className="kt-sub"> {x.voices?.length ? `${x.voices.map((v) => VOICE_NAME[String(v).toLowerCase()] || v).join(' and ')}; ` : ''}{x.at?.length ? `at chord ${x.at.map((n) => n + 1).join(' to ')}` : ''}</span>
              </li>
            ))}
          </ul>
        )
      )} />
    </DeskCard>
  );
}

/** Plays two sine tones together (the root and the interval above it); the AudioContext is made on the click. */
function useDyad() {
  const ctxRef = useRef(null);
  const stopRef = useRef(null);
  const [playing, setPlaying] = useState('');
  const stop = useCallback(() => {
    if (stopRef.current) { clearTimeout(stopRef.current.timer); stopRef.current.stop(); stopRef.current = null; }
    setPlaying('');
  }, []);
  useEffect(() => () => {
    if (stopRef.current) { clearTimeout(stopRef.current.timer); stopRef.current.stop(); stopRef.current = null; }
    if (ctxRef.current) { ctxRef.current.close().catch(() => {}); ctxRef.current = null; }
  }, []);
  const play = useCallback((key, freqs) => {
    stop();
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return false;
    if (!ctxRef.current || ctxRef.current.state === 'closed') ctxRef.current = new AC();
    const ctx = ctxRef.current;
    if (ctx.state === 'suspended') ctx.resume();
    const gain = ctx.createGain();
    const t0 = ctx.currentTime;
    gain.gain.setValueAtTime(0, t0);
    gain.gain.linearRampToValueAtTime(0.1, t0 + 0.05);
    gain.gain.setValueAtTime(0.1, t0 + 1.95);
    gain.gain.linearRampToValueAtTime(0, t0 + 2.05);
    gain.connect(ctx.destination);
    const oscs = freqs.map((f) => { const o = ctx.createOscillator(); o.type = 'sine'; o.frequency.value = f; o.connect(gain); o.start(t0); o.stop(t0 + 2.1); return o; });
    const cleanup = () => { oscs.forEach((o) => { try { o.stop(); } catch { /* already stopped */ } o.disconnect(); }); gain.disconnect(); };
    const timer = setTimeout(() => { cleanup(); stopRef.current = null; setPlaying(''); }, 2150);
    stopRef.current = { timer, stop: cleanup };
    setPlaying(key);
    return true;
  }, [stop]);
  return { play, stop, playing };
}

function Tuning() {
  const [root, setRoot] = useState('261.63');
  const [systems, setSystems] = useState(ALL_SYSTEMS);
  const [localError, setLocalError] = useState('');
  const [state, run] = useTool('music');
  const [sentRoot, setSentRoot] = useState(261.63);
  const dyad = useDyad();
  const [audioNote, setAudioNote] = useState('');

  const submit = () => {
    setLocalError('');
    const hz = Number(root);
    if (!Number.isFinite(hz) || hz < 20 || hz > 2000) { setLocalError('The root pitch must be a number between 20 and 2000 Hz (middle C is about 261.63).'); return null; }
    if (!systems.length) { setLocalError('Choose at least one tuning system.'); return null; }
    setSentRoot(hz);
    return run('tuning', { root_hz: hz, systems });
  };
  useEffect(() => { submit(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const toggle = (s) => setSystems((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : ALL_SYSTEMS.filter((x) => x === s || cur.includes(x))));
  const onPlay = (key, hz) => { setAudioNote(dyad.play(key, [sentRoot, hz]) ? '' : 'This browser cannot play audio.'); };

  return (
    <DeskCard title="Tuning comparison" what="The same interval is a slightly different pitch in each tuning system. Cents are hundredths of a semitone; beats are the slow wobble you hear when the just interval is played in equal temperament.">
      <div className="kt-row kt-wrap">
        <div className="field kt-small">
          <label htmlFor="kt-root">Root pitch (Hz)</label>
          <input id="kt-root" className="kt-input kt-num" inputMode="decimal" value={root} onChange={(e) => setRoot(e.target.value)} />
        </div>
        <fieldset className="kit-fields kt-row kt-wrap">
          <legend className="label">Systems</legend>
          {ALL_SYSTEMS.map((s) => (
            <label key={s} className="kt-check"><input type="checkbox" checked={systems.includes(s)} onChange={() => toggle(s)} /> {SYSTEM_LABEL[s]}</label>
          ))}
        </fieldset>
      </div>
      <div className="btn-row"><RunButton loading={state.loading} onClick={submit}>Compare</RunButton></div>
      {localError && <div className="notice notice-bad" role="alert">{localError}</div>}
      {audioNote && <div className="notice notice-bad" role="alert">{audioNote}</div>}
      <Outcome state={state} render={(r) => {
        const used = ALL_SYSTEMS.filter((s) => r.rows?.[0]?.systems?.[s]);
        return (
          <div className="kt-scroll">
            <table className="kt-table">
              <caption className="kt-sr">Interval frequencies by tuning system</caption>
              <thead>
                <tr><th scope="col">Interval</th>{used.map((s) => <th key={s} scope="col">{SYSTEM_LABEL[s]}</th>)}</tr>
              </thead>
              <tbody>
                {r.rows.map((row) => (
                  <tr key={row.semitones}>
                    <th scope="row">{row.name} <span className="kt-sub">({row.semitones} st)</span></th>
                    {used.map((s) => {
                      const c = row.systems[s];
                      const key = `${row.semitones}-${s}`;
                      const on = dyad.playing === key;
                      return (
                        <td key={s}>
                          <div className="kt-cell">
                            <span>{c.hz} Hz</span>
                            <span className="kt-sub">{c.cents} c{s !== 'equal' ? `, ${c.vs_equal_cents > 0 ? '+' : ''}${c.vs_equal_cents} vs equal` : ''}{c.beat_hz ? `, beats ${c.beat_hz}/s` : ''}</span>
                            <button type="button" className="btn btn-quiet btn-sm" aria-label={`${on ? 'Stop' : 'Play'} ${row.name}, ${SYSTEM_LABEL[s]}`} onClick={() => (on ? dyad.stop() : onPlay(key, c.hz))}>
                              {on ? <Square size={12} aria-hidden="true" /> : <Play size={12} aria-hidden="true" />} {on ? 'Stop' : 'Play'}
                            </button>
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      }} />
      <p className="hint">Play sounds the root and the interval together for two seconds, quietly. Try the major third in equal temperament and in just intonation and listen for the beating.</p>
    </DeskCard>
  );
}

export default function MusicDesk() {
  return <div className="kt-desk"><ChordLint /><Tuning /></div>;
}
