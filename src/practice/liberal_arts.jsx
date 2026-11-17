// Liberal-arts kit bodies: literature, music, art history, classics, rhetoric and polity (24 practice types).
// Same contract as ./general.jsx: each body takes {item, onResult(ok, given), retry}. The answer keys never reach
// the browser (practice_<kit>.py SECRET_FIELDS), so every body sends its submission to the server through
// useServerGrade and shows the verdict it returns. Item fields come from the normalizers' docstrings.
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowUp, ArrowDown, RotateCcw, Check, Loader2, Play, Plus, X, Shuffle } from 'lucide-react';
import Md, { MdInline } from '../components/Md';
import { useServerGrade } from './serverGrade';
import '../styles/kits.css';

// ---- shared helpers

function seeded(items, seed) {
  const out = [...items];
  let h = 7;
  for (const ch of String(seed)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  for (let i = out.length - 1; i > 0; i--) { h = (h * 1103515245 + 12345) >>> 0; const j = h % (i + 1); [out[i], out[j]] = [out[j], out[i]]; }
  if (out.length > 1 && out.every((v, i) => v === items[i])) out.push(out.shift());  // never start in the true order
  return out;
}

const text = (v) => (v == null ? '' : typeof v === 'object' ? Object.values(v).map(text).join(' ') : String(v));
const list = (v) => (Array.isArray(v) ? v : []);
const hasLocalImage = (url) => typeof url === 'string' && /^\/(?!\/)/.test(url);  // never fetch remote images
const fraction = (s) => {  // "0.25", "1/4" or "25%" as a number, else NaN
  const t = String(s).trim().replace(',', '.');
  if (!t) return NaN;
  if (t.endsWith('%')) return Number(t.slice(0, -1)) / 100;
  const m = t.match(/^(-?\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)$/);
  return m ? Number(m[1]) / Number(m[2]) : Number(t);
};

/** One shared frame: the server verdict, a busy check button, locked inputs after a verdict, Try again. */
function Frame({ item, grade, ready = true, submission, retry = true, cta = 'Check', children }) {
  const { result, busy, check, reset } = grade;
  const locked = !!result && !result.error;
  return (
    <form className="stack-sm kit" onSubmit={(e) => { e.preventDefault(); if (ready && !busy && !locked) check(submission); }}>
      <fieldset className="kit-fields stack-sm" disabled={locked || busy}>{children}</fieldset>
      {!locked && (
        <div className="btn-row">
          <button type="submit" className="btn btn-primary btn-sm" disabled={!ready || busy}>
            {busy ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <Check size={14} aria-hidden="true" />} {busy ? 'Checking…' : cta}
          </button>
        </div>
      )}
      <div aria-live="polite">
        {result && (
          <div className={`feedback ${result.ok ? 'ok' : 'bad'}`}>
            <p className="kit-verdict">{result.ok ? 'Correct.' : result.error ? 'Could not check.' : 'Not quite.'}</p>
            {result.feedback && <p>{result.feedback}</p>}
            {!result.ok && !result.error && result.score > 0 && <p className="hint">Partial credit: {Math.round(result.score * 100)}%</p>}
            {!result.error && item.explanation && <Md>{item.explanation}</Md>}
            {!result.ok && !result.error && retry && (
              <div className="btn-row" style={{ marginTop: 6 }}>
                <button type="button" className="btn btn-quiet btn-sm" onClick={reset}><RotateCcw size={14} aria-hidden="true" /> Try again</button>
              </div>
            )}
          </div>
        )}
      </div>
    </form>
  );
}

function Choices({ options, value, onChange, label }) {
  return (
    <div className="choices" role="group" aria-label={label}>
      {options.map((opt, i) => {
        const o = typeof opt === 'string' ? { value: opt, label: opt } : opt;
        return (
          <button key={o.value} type="button" className="choice" aria-pressed={value === o.value} onClick={() => onChange(o.value)}>
            <span className="key">{'ABCDEFGH'[i] || i + 1}</span>
            <span><MdInline>{o.label}</MdInline>{o.hint && <span className="kit-sub"> {o.hint}</span>}</span><span />
          </button>
        );
      })}
    </div>
  );
}

/** Reorder with up/down buttons (works by keyboard); items are {key, label}. */
function OrderList({ items, order, setOrder, name }) {
  const by = Object.fromEntries(items.map((it) => [it.key, it]));
  const move = (i, d) => setOrder((o) => { const n = [...o]; [n[i], n[i + d]] = [n[i + d], n[i]]; return n; });
  return (
    <ol className="kit-order" aria-label={name}>
      {order.map((k, i) => (
        <li key={k} className="kit-order-row">
          <span className="kit-n" aria-hidden="true">{i + 1}</span>
          <span className="kit-order-text"><MdInline>{by[k]?.label ?? k}</MdInline></span>
          <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label={`Move up: ${by[k]?.label ?? k}`} disabled={i === 0} onClick={() => move(i, -1)}><ArrowUp size={14} aria-hidden="true" /></button>
          <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label={`Move down: ${by[k]?.label ?? k}`} disabled={i === order.length - 1} onClick={() => move(i, 1)}><ArrowDown size={14} aria-hidden="true" /></button>
        </li>
      ))}
    </ol>
  );
}

// asGiven: the server already shuffled the list (practice_<kit>._hide_order never leaves it in the true order);
// shuffling again here could put it back in the true order by chance
function useOrder(keys, seed, asGiven = false) {
  const start = useMemo(() => (asGiven ? [...keys] : seeded(keys, seed)), [keys, seed, asGiven]);
  return useState(start);
}

function Plate({ url, alt, children }) {
  if (!url) return <p className="hint">No image is attached to this exercise; work from the description.</p>;
  if (!hasLocalImage(url)) {
    return /^https?:\/\//i.test(url)
      ? <p className="hint">The reference image is hosted elsewhere, so it is not loaded here: <a href={url} target="_blank" rel="noopener noreferrer">open it in a new tab</a>.</p>
      : <p className="hint">The reference image link is not a web address, so it is not shown; work from the description.</p>;
  }
  return <div className="kit-plate"><img src={url} alt={alt} draggable={false} />{children}</div>;
}

// ---- literature

const METER_FEET = { monometer: 1, dimeter: 2, trimeter: 3, tetrameter: 4, pentameter: 5, hexameter: 6, heptameter: 7 };
function guessSyllables(line, meter) {
  const m = Object.entries(METER_FEET).find(([k]) => String(meter).toLowerCase().includes(k));
  if (m && /iamb|troch|anap|dact/i.test(meter)) return m[1] * (/anap|dact/i.test(meter) ? 3 : 2);
  return Math.max(2, Math.min(24, (String(line).toLowerCase().match(/[aeiouy]+/g) || []).length));
}

function Scansion({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const [marks, setMarks] = useState(() => Array(guessSyllables(item.line, item.meter)).fill('0'));
  const flip = (i) => setMarks((m) => m.map((v, j) => (j === i ? (v === '1' ? '0' : '1') : v)));
  const resize = (d) => setMarks((m) => (d > 0 ? [...m, '0'] : m.slice(0, -1)));
  return (
    <Frame item={item} grade={grade} retry={retry} submission={marks.join(' ')} cta="Check scansion">
      <p className="kit-line" lang="en"><MdInline>{item.line}</MdInline></p>
      <p className="hint">Meter: {item.meter}. One slot per syllable: tap to switch between unstressed (u) and stressed (/). Add or remove slots to match the syllable count.</p>
      <div className="kit-slots" role="group" aria-label="Syllable stresses">
        {marks.map((m, i) => (
          <button key={i} type="button" className="kit-slot" aria-pressed={m === '1'} aria-label={`Syllable ${i + 1}: ${m === '1' ? 'stressed' : 'unstressed'}`} onClick={() => flip(i)}>
            {m === '1' ? '/' : 'u'}
          </button>
        ))}
      </div>
      <div className="btn-row">
        <button type="button" className="btn btn-quiet btn-sm" disabled={marks.length <= 2} onClick={() => resize(-1)}>Fewer syllables</button>
        <button type="button" className="btn btn-quiet btn-sm" disabled={marks.length >= 24} onClick={() => resize(1)}>More syllables</button>
        <span className="hint">{marks.length} syllables</span>
      </div>
    </Frame>
  );
}

function VoltaSpot({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const [pick, setPick] = useState(null);
  const lines = list(item.lines);
  return (
    <Frame item={item} grade={grade} retry={retry} ready={pick !== null} submission={pick} cta="Check">
      <p className="hint">Choose the line where the poem turns.</p>
      <ol className="kit-lines">
        {lines.map((l, i) => (
          <li key={i}>
            <button type="button" className="kit-linebtn" aria-pressed={pick === i} onClick={() => setPick(i)}>
              <span className="kit-n" aria-hidden="true">{i + 1}</span><span><MdInline>{l}</MdInline></span>
            </button>
          </li>
        ))}
      </ol>
    </Frame>
  );
}

function RhymeAudit({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const lines = list(item.lines);
  const letters = 'ABCDEFGHIJKL'.slice(0, Math.min(Math.max(lines.length, 2), 12)).split('');
  const [marks, setMarks] = useState(() => lines.map(() => ''));
  return (
    <Frame item={item} grade={grade} retry={retry} ready={marks.every(Boolean)} submission={marks} cta="Check scheme">
      <p className="hint">Give rhyming lines the same letter, starting with A.</p>
      <ol className="kit-lines">
        {lines.map((l, i) => (
          <li key={i} className="kit-rowline">
            <span className="kit-n" aria-hidden="true">{i + 1}</span>
            <span className="kit-grow"><MdInline>{l}</MdInline></span>
            <select className="select kit-mini" aria-label={`Rhyme letter for line ${i + 1}`} value={marks[i]} onChange={(e) => setMarks((m) => m.map((v, j) => (j === i ? e.target.value : v)))}>
              <option value="">–</option>
              {letters.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </li>
        ))}
      </ol>
    </Frame>
  );
}

function ChronologyUnravel({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const events = list(item.events);
  const keys = useMemo(() => events.map((e) => e.id), [events]);
  const [order, setOrder] = useOrder(keys, item.id || 'chron');
  const view = events.map((e) => ({ key: e.id, label: e.text }));
  return (
    <Frame item={item} grade={grade} retry={retry} submission={order} cta="Check order">
      <p className="hint">The events start shuffled. Put them in the order they happened in the story world (the fabula), earliest first, which may differ from the order the text tells them.</p>
      <OrderList items={view} order={order} setOrder={setOrder} name="Events, earliest first" />
    </Frame>
  );
}

// ---- music

const NOTE_SEMI = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
function pitchToMidi(p) {
  if (typeof p === 'number' && Number.isFinite(p)) return p;
  const m = String(p || '').trim().match(/^([A-Ga-g])([#bB♯♭]?)(-?\d)?$/);  // the server accepts "DB4" too (it uppercases)
  if (!m) return null;
  const acc = m[2] === '#' || m[2] === '♯' ? 1 : m[2] ? -1 : 0;
  return 12 * ((m[3] === undefined ? 4 : Number(m[3])) + 1) + NOTE_SEMI[m[1].toUpperCase()] + acc;
}

const INTERVALS = [
  [0, 'Unison'], [1, 'Minor second'], [2, 'Major second'], [3, 'Minor third'], [4, 'Major third'], [5, 'Perfect fourth'],
  [6, 'Tritone'], [7, 'Perfect fifth'], [8, 'Minor sixth'], [9, 'Major sixth'], [10, 'Minor seventh'], [11, 'Major seventh'], [12, 'Octave'],
];

function EarInterval({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const [pick, setPick] = useState(null);
  const ctx = useRef(null);
  const midis = useMemo(() => list(item.notes).map(pitchToMidi), [item.notes]);
  const playable = midis.length === 2 && midis.every((m) => m !== null);
  useEffect(() => () => { ctx.current?.close?.().catch(() => {}); ctx.current = null; }, []);
  const tone = (ac, midi, at, dur) => {
    const osc = ac.createOscillator();
    const gain = ac.createGain();
    osc.type = 'triangle';
    osc.frequency.value = 440 * 2 ** ((midi - 69) / 12);
    gain.gain.setValueAtTime(0.0001, at);
    gain.gain.exponentialRampToValueAtTime(0.25, at + 0.03);
    gain.gain.exponentialRampToValueAtTime(0.0001, at + dur);
    osc.connect(gain).connect(ac.destination);
    osc.start(at);
    osc.stop(at + dur + 0.05);
  };
  const play = (together) => {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC || !playable) return;
    if (!ctx.current) ctx.current = new AC();
    const ac = ctx.current;
    ac.resume?.();
    const t = ac.currentTime + 0.05;
    midis.forEach((m, i) => tone(ac, m, together ? t : t + i * 0.9, together ? 1.6 : 0.8));
  };
  return (
    <Frame item={item} grade={grade} retry={retry} ready={pick !== null} submission={pick} cta="Check interval">
      {playable ? (
        <div className="btn-row">
          <button type="button" className="btn btn-quiet btn-sm" onClick={() => play(false)}><Play size={14} aria-hidden="true" /> Play one after the other</button>
          <button type="button" className="btn btn-quiet btn-sm" onClick={() => play(true)}><Play size={14} aria-hidden="true" /> Play together</button>
        </div>
      ) : <p className="hint">This item has no pitches to play, so the sound is unavailable.</p>}
      <Choices label="Interval" options={INTERVALS.map(([v, l]) => ({ value: v, label: l, hint: `(${v})` }))} value={pick} onChange={setPick} />
    </Frame>
  );
}

const chordCells = (c) => {
  if (Array.isArray(c)) return c.map(text);
  if (c && typeof c === 'object') {
    if ('s' in c || 'b' in c) return ['s', 'a', 't', 'b'].map((v) => text(c[v]));
    return Object.values(c).map(text);
  }
  return [text(c)];
};
const chordName = (c) => (typeof c === 'string' ? c : chordCells(c).join(' '));

function ChordTable({ chords }) {
  return (
    <table className="kit-table">
      <caption className="sr-only">Chords, soprano to bass</caption>
      <thead><tr><th scope="col">Chord</th><th scope="col">S</th><th scope="col">A</th><th scope="col">T</th><th scope="col">B</th></tr></thead>
      <tbody>{chords.map((c, i) => <tr key={i}><th scope="row">{i + 1}</th>{chordCells(c).map((v, j) => <td key={j}>{v}</td>)}</tr>)}</tbody>
    </table>
  );
}

const DEFECTS = [['voice_crossing', 'Voice crossing'], ['parallel_fifth', 'Parallel fifths'], ['parallel_octave', 'Parallel octaves']];
const PAIRS = ['S_A', 'S_T', 'S_B', 'A_T', 'A_B', 'T_B'];

function LintSatb({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const chords = list(item.chords);
  const [found, setFound] = useState([]);   // codes like voice_crossing:chord_2, parallel_fifth:S_A:chord_1_to_2
  const [kind, setKind] = useState('voice_crossing');
  const [pair, setPair] = useState('S_A');
  const [at, setAt] = useState(1);
  const code = kind === 'voice_crossing' ? `${kind}:chord_${at}` : `${kind}:${pair}:chord_${at}_to_${at + 1}`;
  const pretty = (c) => {
    const [k, ...rest] = c.split(':');
    return `${DEFECTS.find((d) => d[0] === k)?.[1] || k}, ${rest.map((r) => r.replace(/_/g, ' ').replace(/^chord /, 'chord ').replace(' to ', ' to chord ')).join(', ')}`;
  };
  const positions = kind === 'voice_crossing' ? chords.length : chords.length - 1;
  return (
    <Frame item={item} grade={grade} retry={retry} submission={found} cta={found.length ? 'Check defects' : 'Check: no defects'}>
      <ChordTable chords={chords} />
      <p className="hint">Add every voice-leading defect you find. If the progression is clean, add nothing and check.</p>
      <div className="kit-builder">
        <label className="kit-lab">Defect
          <select className="select" value={kind} onChange={(e) => { setKind(e.target.value); setAt(1); }}>{DEFECTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        </label>
        {kind !== 'voice_crossing' && (
          <label className="kit-lab">Voices
            <select className="select" value={pair} onChange={(e) => setPair(e.target.value)}>{PAIRS.map((p) => <option key={p} value={p}>{p.replace('_', ' and ')}</option>)}</select>
          </label>
        )}
        <label className="kit-lab">{kind === 'voice_crossing' ? 'In chord' : 'Between'}
          <select className="select" value={at} onChange={(e) => setAt(Number(e.target.value))}>
            {Array.from({ length: Math.max(positions, 1) }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{kind === 'voice_crossing' ? n : `${n} and ${n + 1}`}</option>)}
          </select>
        </label>
        <button type="button" className="btn btn-quiet btn-sm" disabled={found.includes(code) || positions < 1} onClick={() => setFound((f) => [...f, code])}><Plus size={14} aria-hidden="true" /> Add</button>
      </div>
      {found.length > 0 && (
        <ul className="kit-tags" aria-label="Defects you added">
          {found.map((c) => (
            <li key={c} className="kit-tag">{pretty(c)}
              <button type="button" className="kit-x" aria-label={`Remove ${pretty(c)}`} onClick={() => setFound((f) => f.filter((x) => x !== c))}><X size={12} aria-hidden="true" /></button>
            </li>
          ))}
        </ul>
      )}
    </Frame>
  );
}

function RomanNumerals({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const chords = list(item.chords);
  const [vals, setVals] = useState(() => chords.map(() => ''));
  return (
    <Frame item={item} grade={grade} retry={retry} ready={vals.every((v) => v.trim())} submission={vals.map((v) => v.trim())} cta="Check analysis">
      <p className="hint">Key: <strong>{item.key}</strong>. Write a Roman numeral for each chord (for example V7, ii6, vii°).</p>
      <ol className="kit-lines">
        {chords.map((c, i) => (
          <li key={i} className="kit-rowline">
            <span className="kit-n" aria-hidden="true">{i + 1}</span>
            <span className="kit-grow kit-mono">{chordName(c)}</span>
            <input className="input kit-mini" aria-label={`Roman numeral for chord ${i + 1}`} autoCapitalize="off" autoComplete="off" spellCheck={false}
              value={vals[i]} onChange={(e) => setVals((v) => v.map((x, j) => (j === i ? e.target.value : x)))} />
          </li>
        ))}
      </ol>
    </Frame>
  );
}

function FiguredBass({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const [notes, setNotes] = useState(['', '', '']);
  const set = (i, v) => setNotes((n) => n.map((x, j) => (j === i ? v : x)));
  const filled = notes.map((n) => n.trim()).filter(Boolean);
  return (
    <Frame item={item} grade={grade} retry={retry} ready={filled.length > 0} submission={filled} cta="Check realization">
      <p className="hint">Bass note <strong className="kit-mono">{text(item.bass_note)}</strong> with figures <strong className="kit-mono">{item.figures}</strong>. Write the upper-voice notes the figures call for, in the same style as the bass note (for example E4).</p>
      <div className="kit-builder">
        {notes.map((n, i) => (
          <input key={i} className="input kit-mini" aria-label={`Upper voice ${i + 1}`} autoComplete="off" spellCheck={false} value={n} onChange={(e) => set(i, e.target.value)} />
        ))}
        <button type="button" className="btn btn-quiet btn-sm" disabled={notes.length >= 6} onClick={() => setNotes((n) => [...n, ''])}><Plus size={14} aria-hidden="true" /> Voice</button>
        <button type="button" className="btn btn-quiet btn-sm" disabled={notes.length <= 1} onClick={() => setNotes((n) => n.slice(0, -1))}>Remove voice</button>
      </div>
    </Frame>
  );
}

// ---- art history

function CompositionVector({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const [pt, setPt] = useState(null);
  const box = useRef(null);
  const clamp = (v) => Math.min(1, Math.max(0, Math.round(v * 1e4) / 1e4));
  const onClick = (e) => {
    const r = box.current.getBoundingClientRect();
    setPt({ x: clamp((e.clientX - r.left) / r.width), y: clamp((e.clientY - r.top) / r.height) });
  };
  const onKey = (e) => {
    const d = { ArrowLeft: [-0.02, 0], ArrowRight: [0.02, 0], ArrowUp: [0, -0.02], ArrowDown: [0, 0.02] }[e.key];
    if (!d) return;
    e.preventDefault();
    setPt((p) => ({ x: clamp((p?.x ?? 0.5) + d[0]), y: clamp((p?.y ?? 0.5) + d[1]) }));
  };
  const local = hasLocalImage(item.image_url);
  return (
    <Frame item={item} grade={grade} retry={retry} ready={!!pt} submission={pt} cta="Check focal point">
      {item.image_url && !local && <Plate url={item.image_url} />}
      <p className="hint">Click the focal point of the composition, or focus the picture and move the marker with the arrow keys.</p>
      <div ref={box} className="kit-plate kit-pick" tabIndex={0} role="group" aria-label="Picture: choose the focal point"
        onClick={onClick} onKeyDown={onKey}>
        {local ? <img src={item.image_url} alt="Artwork to analyse" draggable={false} /> : <div className="kit-blank" aria-hidden="true" />}
        {pt && <span className="kit-marker" style={{ left: `${pt.x * 100}%`, top: `${pt.y * 100}%` }} aria-hidden="true" />}
      </div>
      {pt && <p className="hint">Marker at {Math.round(pt.x * 100)}% across, {Math.round(pt.y * 100)}% down.</p>}
    </Frame>
  );
}

function MatchSelects({ item, onResult, retry, keys, options, cta, hint, free }) {
  const grade = useServerGrade(item, onResult);
  const [vals, setVals] = useState({});
  const set = (k, v) => setVals((m) => ({ ...m, [k]: v }));
  return (
    <Frame item={item} grade={grade} retry={retry} ready={keys.length > 0 && keys.every((k) => (vals[k] || '').trim())} submission={Object.fromEntries(keys.map((k) => [k, (vals[k] || '').trim()]))} cta={cta}>
      {item.image_url && <Plate url={item.image_url} alt="Image to label" />}
      <p className="hint">{hint}</p>
      <ul className="kit-lines">
        {keys.map((k) => (
          <li key={k} className="kit-rowline">
            <span className="kit-grow"><MdInline>{k}</MdInline></span>
            {free || !options.length
              ? <input className="input kit-wide" aria-label={`Answer for ${k}`} autoComplete="off" value={vals[k] || ''} onChange={(e) => set(k, e.target.value)} />
              : (
                <select className="select kit-wide" aria-label={`Answer for ${k}`} value={vals[k] || ''} onChange={(e) => set(k, e.target.value)}>
                  <option value="">Choose…</option>
                  {options.map((o, i) => <option key={`${o}-${i}`} value={o}>{o}</option>)}
                </select>
              )}
          </li>
        ))}
      </ul>
    </Frame>
  );
}

const LabelArchitecture = (p) => (
  <MatchSelects {...p} keys={list(p.item.labels)} options={seeded([...new Set(list(p.item.elements))], p.item.id || 'arch')}
    cta="Check labels" hint="Match each label to the architectural element it points to." />
);
const IconographyDecode = (p) => (
  <MatchSelects {...p} keys={list(p.item.symbols)} options={[...new Set(list(p.item.options))]}
    cta="Check decoding" hint="Choose the figure, saint or meaning each symbol identifies." />
);

function StylisticTaxonomy({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const options = useMemo(() => seeded(list(item.options), item.id || 'style'), [item]);
  const [val, setVal] = useState('');
  return (
    <Frame item={item} grade={grade} retry={retry} ready={!!val.trim()} submission={val.trim()} cta="Check period">
      <ul className="kit-bullets" aria-label="Stylistic traits">{list(item.traits).map((t, i) => <li key={i}><MdInline>{t}</MdInline></li>)}</ul>
      <p className="hint">Which period or movement shows these traits?</p>
      {options.length > 0
        ? <Choices label="Period" options={options} value={val} onChange={setVal} />
        : <input className="input" aria-label="Period or movement" autoComplete="off" value={val} onChange={(e) => setVal(e.target.value)} />}
    </Frame>
  );
}

// ---- classics

function EpigraphyTranscribe({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const [val, setVal] = useState('');
  return (
    <Frame item={item} grade={grade} retry={retry} ready={!!val.trim()} submission={val} cta="Check transcription">
      <pre className="kit-inscription" lang={item.language === 'greek' ? 'grc' : 'la'}>{item.inscription_raw}</pre>
      <label className="kit-lab" htmlFor={`epi-${item.id}`}>Expand the abbreviations and write the full {item.language || 'Latin'} text (case and punctuation do not matter)</label>
      <textarea id={`epi-${item.id}`} className="textarea" rows={3} spellCheck={false} value={val} onChange={(e) => setVal(e.target.value)} />
    </Frame>
  );
}

function HarrisMatrix({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const strata = list(item.strata);
  const [edges, setEdges] = useState([]);
  const [above, setAbove] = useState('');
  const [below, setBelow] = useState('');
  const dup = edges.some(([a, b]) => a === above && b === below);
  return (
    <Frame item={item} grade={grade} retry={retry} ready={edges.length > 0} submission={edges} cta="Check matrix">
      <p className="hint">A Harris matrix records which layer lies directly above which. Add each relation between neighbouring layers; a layer is later than everything beneath it.</p>
      <ul className="kit-tags" aria-label="Layers">{strata.map((s) => <li key={s} className="kit-tag kit-tag-plain"><MdInline>{s}</MdInline></li>)}</ul>
      <div className="kit-builder">
        <label className="kit-lab">Above
          <select className="select" value={above} onChange={(e) => setAbove(e.target.value)}><option value="">Choose…</option>{strata.map((s) => <option key={s} value={s}>{s}</option>)}</select>
        </label>
        <label className="kit-lab">Directly below
          <select className="select" value={below} onChange={(e) => setBelow(e.target.value)}><option value="">Choose…</option>{strata.map((s) => <option key={s} value={s}>{s}</option>)}</select>
        </label>
        <button type="button" className="btn btn-quiet btn-sm" disabled={!above || !below || above === below || dup} onClick={() => { setEdges((e) => [...e, [above, below]]); setAbove(''); setBelow(''); }}><Plus size={14} aria-hidden="true" /> Add relation</button>
      </div>
      {edges.length > 0 && (
        <ul className="kit-tags" aria-label="Relations you added">
          {edges.map(([a, b]) => (
            <li key={`${a}>${b}`} className="kit-tag">{a} is above {b}
              <button type="button" className="kit-x" aria-label={`Remove: ${a} above ${b}`} onClick={() => setEdges((es) => es.filter(([x, y]) => !(x === a && y === b)))}><X size={12} aria-hidden="true" /></button>
            </li>
          ))}
        </ul>
      )}
    </Frame>
  );
}

function ordered(item, onResult, retry, field, hint, name) {
  const keys = list(item[field]);
  return <OrderBody item={item} onResult={onResult} retry={retry} keys={keys} hint={hint} name={name} />;
}

/** Order bodies for lists the server shuffled (cursus_honorum_order offices, dispositio_sort parts): kept as given. */
function OrderBody({ item, onResult, retry, keys, hint, name, notes }) {
  const grade = useServerGrade(item, onResult);
  const [order, setOrder] = useOrder(keys, item.id || name, true);
  return (
    <Frame item={item} grade={grade} retry={retry} submission={order} cta="Check order">
      <p className="hint">{hint}</p>
      <OrderList items={keys.map((k) => ({ key: k, label: notes?.[k] ? `${k}: ${text(notes[k])}` : k }))} order={order} setOrder={setOrder} name={name} />
    </Frame>
  );
}

const CursusHonorum = ({ item, onResult, retry }) => ordered(item, onResult, retry, 'offices', 'Order the offices as a Roman career ran, lowest first.', 'Offices, lowest first');

function AthenianSortition({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const cands = item.candidates && typeof item.candidates === 'object' ? item.candidates : {};
  const quotas = item.quotas && typeof item.quotas === 'object' ? item.quotas : {};
  const tribes = Object.keys(cands);
  const [chosen, setChosen] = useState(() => Object.fromEntries(tribes.map((t) => [t, []])));
  const toggle = (t, c) => setChosen((m) => ({ ...m, [t]: m[t].includes(c) ? m[t].filter((x) => x !== c) : [...m[t], c] }));
  const draw = () => setChosen(Object.fromEntries(tribes.map((t) => {
    const pool = [...cands[t]];
    for (let i = pool.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [pool[i], pool[j]] = [pool[j], pool[i]]; }
    return [t, pool.slice(0, Number(quotas[t]) || 0)];
  })));
  const known = tribes.every((t) => quotas[t] !== undefined);
  return (
    <Frame item={item} grade={grade} retry={retry} ready={tribes.length > 0 && tribes.every((t) => chosen[t]?.length > 0)} submission={chosen} cta="Check allotment">
      <p className="hint">Each tribe sends citizens chosen by lot (the kleroterion), never by vote. Pick the number of citizens each tribe is owed from its own registered pool{known ? '' : '; the quota is not shown, so use the lesson text'}.</p>
      {known && <div className="btn-row"><button type="button" className="btn btn-quiet btn-sm" onClick={draw}><Shuffle size={14} aria-hidden="true" /> Draw by lot</button></div>}
      {tribes.map((t) => (
        <fieldset key={t} className="kit-tribe">
          <legend>{t} <span className="kit-sub">{chosen[t].length}{known ? ` of ${quotas[t]}` : ''} chosen</span></legend>
          <div className="kit-checks">
            {cands[t].map((c) => (
              <label key={c} className="kit-check"><input type="checkbox" checked={chosen[t].includes(c)} onChange={() => toggle(t, c)} /> {c}</label>
            ))}
          </div>
        </fieldset>
      ))}
    </Frame>
  );
}

// ---- rhetoric

const STASIS_HINTS = {
  conjecture: 'Did it happen?', definition: 'What is it, and what do we call it?', quality: 'How serious, or how justified, is it?', policy: 'What should we do about it?',
};

function StasisClassify({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const [val, setVal] = useState('');
  const opts = list(item.options).map((o) => ({ value: o, label: o.charAt(0).toUpperCase() + o.slice(1), hint: STASIS_HINTS[o] ? `(${STASIS_HINTS[o]})` : '' }));
  return (
    <Frame item={item} grade={grade} retry={retry} ready={!!val} submission={val} cta="Check stasis">
      <blockquote className="kit-quote"><MdInline>{item.case}</MdInline></blockquote>
      <p className="hint">On which question does this dispute turn?</p>
      <Choices label="Stasis" options={opts} value={val} onChange={setVal} />
    </Frame>
  );
}

function TropeHunter({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const options = useMemo(() => seeded(list(item.options), item.id || 'trope'), [item]);
  const [val, setVal] = useState('');
  return (
    <Frame item={item} grade={grade} retry={retry} ready={!!val.trim()} submission={val.trim()} cta="Check trope">
      <blockquote className="kit-quote"><MdInline>{item.passage}</MdInline></blockquote>
      <p className="hint">Which trope or figure of speech does the passage use?</p>
      {options.length > 0
        ? <Choices label="Trope" options={options.map((o) => ({ value: o, label: o.charAt(0).toUpperCase() + o.slice(1) }))} value={val} onChange={setVal} />
        : <input className="input" aria-label="Trope" autoComplete="off" value={val} onChange={(e) => setVal(e.target.value)} />}
    </Frame>
  );
}

function DispositioSort({ item, onResult, retry }) {
  const sections = item.sections && typeof item.sections === 'object' && !Array.isArray(item.sections) ? item.sections : null;
  return <OrderBody item={item} onResult={onResult} retry={retry} keys={list(item.parts)} notes={sections}
    hint="Put the parts of the oration in the classical order, first to last." name="Parts of the oration" />;
}

function Enthymeme({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const [val, setVal] = useState('');
  return (
    <Frame item={item} grade={grade} retry={retry} ready={!!val} submission={val} cta="Check premise">
      <div className="kit-syl">
        <p><span className="kit-sub">Stated premise</span><br /><MdInline>{item.stated_premise}</MdInline></p>
        <p><span className="kit-sub">Unstated premise</span><br /><strong>?</strong></p>
        <p><span className="kit-sub">Conclusion</span><br /><MdInline>{item.conclusion}</MdInline></p>
      </div>
      <p className="hint">Which unstated premise makes the argument valid?</p>
      <Choices label="Unstated premise" options={list(item.options)} value={val} onChange={setVal} />
    </Frame>
  );
}

// ---- polity

function Dhondt({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const parties = Object.keys(item.votes || {});
  const [seats, setSeats] = useState({});
  const given = parties.reduce((n, p) => n + (Number.parseInt(seats[p], 10) || 0), 0);
  return (
    <Frame item={item} grade={grade} retry={retry} ready={parties.every((p) => /^\d+$/.test(String(seats[p] ?? '')))}
      submission={Object.fromEntries(parties.map((p) => [p, Number.parseInt(seats[p], 10) || 0]))} cta="Check seats">
      <p className="hint">Allocate <strong>{item.seats}</strong> seats with the D'Hondt method: repeatedly give a seat to the party with the highest votes / (seats won + 1).</p>
      <table className="kit-table">
        <thead><tr><th scope="col">Party</th><th scope="col">Votes</th><th scope="col">Seats</th></tr></thead>
        <tbody>
          {parties.map((p) => (
            <tr key={p}>
              <th scope="row">{p}</th><td>{Number(item.votes[p]).toLocaleString()}</td>
              <td><input className="input kit-mini" type="number" inputMode="numeric" min="0" step="1" aria-label={`Seats for ${p}`} value={seats[p] ?? ''} onChange={(e) => setSeats((s) => ({ ...s, [p]: e.target.value }))} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="hint" aria-live="polite">{given} of {item.seats} seats given out.</p>
    </Frame>
  );
}

function ShapleyShubik({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const voters = Object.keys(item.weights || {});
  const [vals, setVals] = useState({});
  const nums = voters.map((v) => fraction(vals[v] ?? ''));
  return (
    <Frame item={item} grade={grade} retry={retry} ready={nums.every((n) => Number.isFinite(n))}
      submission={Object.fromEntries(voters.map((v, i) => [v, nums[i]]))} cta="Check indices">
      <p className="hint">A coalition wins with at least <strong>{item.quota}</strong> votes. The pivotal voter in an ordering is the one whose vote first reaches the quota. For each voter, enter the share of all orderings in which they are pivotal (a decimal like 0.25 or a fraction like 1/4; within 0.05 counts).</p>
      <table className="kit-table">
        <thead><tr><th scope="col">Voter</th><th scope="col">Weight</th><th scope="col">Power index</th></tr></thead>
        <tbody>
          {voters.map((v) => (
            <tr key={v}>
              <th scope="row">{v}</th><td>{item.weights[v]}</td>
              <td><input className="input kit-mini" inputMode="decimal" autoComplete="off" aria-label={`Power index for ${v}`} value={vals[v] ?? ''} onChange={(e) => setVals((s) => ({ ...s, [v]: e.target.value }))} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </Frame>
  );
}

const playerName = (p) => (typeof p === 'string' ? p : text(p?.name ?? p?.actor ?? p?.id ?? p?.player ?? ''));
const playerNote = (p) => (p && typeof p === 'object'
  ? Object.entries(p).filter(([k, v]) => !['name', 'actor', 'id', 'player'].includes(k) && v !== null && typeof v !== 'object').map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`).join('; ')
  : '');

function VetoPipeline({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const players = list(item.veto_players);
  const [passes, setPasses] = useState(null);
  const [blocker, setBlocker] = useState('');
  return (
    <Frame item={item} grade={grade} retry={retry} ready={passes !== null && (passes || !!blocker)}
      submission={{ will_pass: passes === true, blocking_actor: passes ? '' : blocker }} cta="Check outcome">
      <p><strong><MdInline>{item.bill}</MdInline></strong></p>
      <ol className="kit-lines" aria-label="Veto players in order">
        {players.map((p, i) => (
          <li key={i} className="kit-rowline">
            <span className="kit-n" aria-hidden="true">{i + 1}</span>
            <span className="kit-grow"><MdInline>{playerName(p)}</MdInline>{playerNote(p) && <span className="kit-sub"> ({playerNote(p)})</span>}</span>
          </li>
        ))}
      </ol>
      <p className="hint">Does the bill clear every veto player?</p>
      <Choices label="Outcome" options={[{ value: 'yes', label: 'It passes' }, { value: 'no', label: 'It is blocked' }]} value={passes === null ? '' : passes ? 'yes' : 'no'} onChange={(v) => setPasses(v === 'yes')} />
      {passes === false && (
        <label className="kit-lab">Who blocks it?
          <select className="select" value={blocker} onChange={(e) => setBlocker(e.target.value)}>
            <option value="">Choose…</option>
            {players.map((p, i) => <option key={i} value={playerName(p)}>{playerName(p)}</option>)}
          </select>
        </label>
      )}
    </Frame>
  );
}

function InstantRunoff({ item, onResult, retry }) {
  const grade = useServerGrade(item, onResult);
  const cands = list(item.candidates);
  const ballots = list(item.ballots);
  const [out, setOut] = useState([]);          // elimination order so far
  const [winner, setWinner] = useState('');
  const groups = useMemo(() => {
    const m = new Map();
    ballots.forEach((b) => { const k = b.join(' > '); m.set(k, (m.get(k) || 0) + 1); });
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [ballots]);
  const alive = cands.filter((c) => !out.includes(c));
  const tally = Object.fromEntries(alive.map((c) => [c, 0]));
  let counted = 0;
  ballots.forEach((b) => { const top = b.find((c) => tally[c] !== undefined); if (top !== undefined) { tally[top] += 1; counted += 1; } });
  const max = Math.max(1, ...Object.values(tally));
  const hasMajority = Object.values(tally).some((n) => n * 2 > counted);  // the count stops here: no more eliminations
  return (
    <Frame item={item} grade={grade} retry={retry} ready={!!winner} submission={{ winner, elimination_order: out }} cta="Check result">
      <details className="kit-ballots">
        <summary>{ballots.length} ballots in {groups.length} patterns</summary>
        <ul className="kit-lines">{groups.map(([k, n]) => <li key={k} className="kit-rowline"><span className="kit-n">{n}&times;</span><span className="kit-grow kit-mono">{k}</span></li>)}</ul>
      </details>
      <p className="hint">Each round every ballot counts for its highest-ranked remaining candidate. If nobody has more than half of the counted ballots, eliminate the candidate with the fewest (ties: alphabetical order). Stop when someone has a majority, or two remain, and name the winner. The winner is not eliminated.</p>
      <ul className="kit-tally" aria-label={`Round ${out.length + 1}, ${counted} ballots counted`}>
        {alive.map((c) => (
          <li key={c} className="kit-rowline">
            <span className="kit-tallyname">{c}</span>
            <span className="kit-bar" aria-hidden="true"><span style={{ width: `${(tally[c] / max) * 100}%` }} /></span>
            <span className="kit-n">{tally[c]}</span>
            <button type="button" className="btn btn-quiet btn-sm" disabled={alive.length <= 2 || hasMajority} onClick={() => { setOut((o) => [...o, c]); setWinner(''); }}>Eliminate</button>
          </li>
        ))}
      </ul>
      <div className="btn-row">
        <span className="hint">Eliminated: {out.length ? out.join(', ') : 'none yet'}</span>
        <button type="button" className="btn btn-quiet btn-sm" disabled={!out.length} onClick={() => { setOut((o) => o.slice(0, -1)); setWinner(''); }}><RotateCcw size={14} aria-hidden="true" /> Undo</button>
      </div>
      <label className="kit-lab">Winner
        <select className="select" value={winner} onChange={(e) => setWinner(e.target.value)}>
          <option value="">Choose…</option>
          {alive.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </label>
    </Frame>
  );
}

// ---- registry maps (same contract as ./registry.js)

export const LIBERAL_ARTS_RENDER = {
  scansion: Scansion, volta_spot: VoltaSpot, rhyme_scheme_audit: RhymeAudit, chronology_unravel: ChronologyUnravel,
  lint_satb_progression: LintSatb, roman_numeral_analysis: RomanNumerals, ear_interval_id: EarInterval, figured_bass_realize: FiguredBass,
  composition_vector: CompositionVector, label_architecture: LabelArchitecture, iconography_decode: IconographyDecode, stylistic_taxonomy: StylisticTaxonomy,
  epigraphy_transcribe: EpigraphyTranscribe, harris_matrix_build: HarrisMatrix, cursus_honorum_order: CursusHonorum, athenian_sortition_sim: AthenianSortition,
  stasis_classify: StasisClassify, trope_hunter: TropeHunter, dispositio_sort: DispositioSort, enthymeme_excavator: Enthymeme,
  compute_dhondt: Dhondt, compute_shapley_shubik_pivotal: ShapleyShubik, veto_pipeline: VetoPipeline, instant_runoff_tally: InstantRunoff,
};

export const LIBERAL_ARTS_LABEL = {
  scansion: 'Scan the line', volta_spot: 'Find the volta', rhyme_scheme_audit: 'Rhyme scheme', chronology_unravel: 'Unravel the chronology',
  lint_satb_progression: 'Check the voice leading', roman_numeral_analysis: 'Roman numeral analysis', ear_interval_id: 'Name the interval', figured_bass_realize: 'Realize the figured bass',
  composition_vector: 'Find the focal point', label_architecture: 'Label the architecture', iconography_decode: 'Decode the iconography', stylistic_taxonomy: 'Name the style',
  epigraphy_transcribe: 'Transcribe the inscription', harris_matrix_build: 'Build the Harris matrix', cursus_honorum_order: 'Order the cursus honorum', athenian_sortition_sim: 'Allot by lot',
  stasis_classify: 'Classify the stasis', trope_hunter: 'Hunt the trope', dispositio_sort: 'Order the oration', enthymeme_excavator: 'Excavate the premise',
  compute_dhondt: "D'Hondt seats", compute_shapley_shubik_pivotal: 'Shapley-Shubik power', veto_pipeline: 'Trace the veto', instant_runoff_tally: 'Instant-runoff tally',
};
