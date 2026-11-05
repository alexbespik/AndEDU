// History practice types: categorize, cause_effect, source_analysis, map_pins, who_am_i, date_guess, roleplay
// (docs/agy-tasks/history_interactives.md). Same contract as ./language.jsx: each body takes
// {item, onResult(ok, given), retry}; ok === null means ungraded (roleplay) or skipped. Everything that can be
// dragged can also be tapped (pick, then tap where it goes), which is also how keyboards use it.
import React, { useMemo, useRef, useState } from 'react';
import { RotateCcw, Check, Lightbulb, Send, ArrowUp, ArrowDown } from 'lucide-react';
import Md, { MdInline } from '../components/Md';
import { ExplainAnswerButton } from '../components/ExplainDialog';
import { OutlineMap } from '../components/history/OutlineMap';
import { MAP_LABEL, fmtYear, pointToFraction, whoPoints } from '../components/history/historyUtil';
import { api } from '../lib/api';
import '../styles/history.css';

export const HISTORY_TYPES = ['categorize', 'cause_effect', 'source_analysis', 'map_pins', 'who_am_i', 'date_guess', 'roleplay'];

function seeded(items, seed, keepAnswerOrder = false) {
  const out = [...items];
  let h = 7;
  for (const ch of String(seed)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  for (let i = out.length - 1; i > 0; i--) { h = (h * 1103515245 + 12345) >>> 0; const j = h % (i + 1); [out[i], out[j]] = [out[j], out[i]]; }
  if (!keepAnswerOrder && out.length > 1 && out.every((v, i) => v === items[i])) out.push(out.shift());  // never already solved
  return out;
}

function Result({ ok, note, answer, item, given, onRetry }) {
  return (
    <div className={`feedback ${ok ? 'ok' : 'bad'}`} aria-live="polite">
      <p style={{ fontWeight: 700, marginBottom: 4 }}>{ok ? 'Correct.' : 'Not quite.'}{note ? ` ${note}` : ''}</p>
      {!ok && answer && <p>Correct answer: <strong>{answer}</strong></p>}
      {item.explanation && <Md>{item.explanation}</Md>}
      {!ok && (
        <div className="btn-row" style={{ marginTop: 6 }}>
          <ExplainAnswerButton item={item} studentAnswer={given} correctAnswer={answer || ''} />
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

function useCheck(onResult) {
  const [res, setRes] = useState(null);
  const done = (r, given) => { setRes(r); onResult?.(r.ok, given); };
  return [res, done, () => setRes(null)];
}

/** HTML drag-and-drop helpers; the tap path (select, then tap the target) does the same job without a mouse. */
const dragProps = (payload, onStart) => ({
  draggable: true,
  onDragStart: (e) => { e.dataTransfer.setData('text/plain', String(payload)); e.dataTransfer.effectAllowed = 'move'; onStart?.(); },
});
function useDropZone(onDrop) {
  const [over, setOver] = useState(false);
  return [over, {
    onDragOver: (e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; },
    onDragEnter: () => setOver(true),
    onDragLeave: (e) => { if (!e.currentTarget.contains(e.relatedTarget)) setOver(false); },
    onDrop: (e) => { e.preventDefault(); setOver(false); onDrop(e.dataTransfer.getData('text/plain'), e); },
  }];
}

// ---- categorize ------------------------------------------------------------------------------------------------

function Bucket({ name, children, onPlace, onDropItem, selected, disabled }) {
  const [over, zone] = useDropZone(onDropItem);
  return (
    <div className={`hist-zone stack-sm${over ? ' is-over' : ''}`} {...(disabled ? {} : zone)}>
      <button type="button" className="btn btn-quiet btn-sm hist-zone-head" disabled={disabled || selected === null} onClick={onPlace}
        aria-label={name ? `Put the selected item in ${name}` : 'Put the selected item back'}>
        <strong>{name || 'Not sorted yet'}</strong>{!disabled && selected !== null && <span aria-hidden="true">+</span>}
      </button>
      <div className="hist-chips">{children}</div>
    </div>
  );
}

function Categorize({ item, onResult, retry = true }) {
  const order = useMemo(() => seeded(item.items.map((_, i) => i), item.id || item.prompt), [item]);
  const [where, setWhere] = useState({});   // item index -> bucket
  const [sel, setSel] = useState(null);
  const [res, done, reset] = useCheck(onResult);
  const place = (i, bucket) => { if (res || i === null || Number.isNaN(i)) return; setWhere((w) => ({ ...w, [i]: bucket })); setSel(null); };
  const chip = (i) => {
    const [text, bucket] = item.items[i];
    const result = res ? (where[i] === bucket ? 'correct' : 'wrong') : undefined;
    return (
      <button key={i} type="button" className="hist-chip" aria-pressed={sel === i} data-result={result} disabled={!!res}
        onClick={() => setSel(sel === i ? null : i)} {...(res ? {} : dragProps(i, () => setSel(i)))}>
        <MdInline>{text}</MdInline>
      </button>
    );
  };
  const placed = Object.values(where).filter(Boolean).length;
  const check = () => {
    const right = item.items.filter(([, b], i) => where[i] === b).length;
    const given = item.buckets.map((b) => `${b}: ${item.items.filter((_, i) => where[i] === b).map(([t]) => t).join(', ')}`).join('; ');
    const answer = item.buckets.map((b) => `${b}: ${item.items.filter(([, bb]) => bb === b).map(([t]) => t).join(', ')}`).join('; ');
    done({ ok: right === item.items.length, note: `${right} of ${item.items.length} in the right group.`, answer }, given);
  };
  return (
    <div className="stack-sm">
      <p className="hint">Drag each item into a group, or tap an item and then the group's name.</p>
      <Bucket name="" selected={sel} disabled={!!res} onPlace={() => place(sel, undefined)} onDropItem={(v) => place(Number(v), undefined)}>
        {order.filter((i) => !where[i]).map(chip)}
      </Bucket>
      <div className="hist-buckets">
        {item.buckets.map((b) => (
          <Bucket key={b} name={b} selected={sel} disabled={!!res} onPlace={() => place(sel, b)} onDropItem={(v) => place(Number(v), b)}>
            {order.filter((i) => where[i] === b).map(chip)}
          </Bucket>
        ))}
      </div>
      {!res && <div className="btn-row">
        <button type="button" className="btn btn-primary btn-sm" disabled={placed < item.items.length} onClick={check}><Check size={14} aria-hidden="true" /> Check</button>
        {placed > 0 && <button type="button" className="btn btn-quiet btn-sm" onClick={() => { setWhere({}); setSel(null); }}>Clear</button>}
      </div>}
      {res && <Result ok={res.ok} note={res.note} answer={res.ok ? null : res.answer} item={item} given="" onRetry={retry ? () => { reset(); setWhere({}); } : null} />}
    </div>
  );
}

// ---- cause_effect ----------------------------------------------------------------------------------------------

function ChainSlot({ children, onDropCard }) {
  const [over, zone] = useDropZone(onDropCard);
  return <li className={`hist-slot${over ? ' hist-zone is-over' : ''}`} {...zone}>{children}</li>;
}

function CauseEffect({ item, onResult, retry = true }) {
  const cards = useMemo(() => seeded(item.chain.map((_, i) => i), item.id || item.prompt), [item]);
  const [chain, setChain] = useState([]);   // indices into item.chain, in the student's order
  const [res, done, reset] = useCheck(onResult);
  const [poolOver, poolZone] = useDropZone((v) => setChain((c) => c.filter((x) => x !== Number(v))));
  const insert = (i, at) => setChain((c) => { const n = c.filter((x) => x !== i); n.splice(Math.min(at, n.length), 0, i); return n; });
  const move = (k, d) => setChain((c) => { const n = [...c]; [n[k], n[k + d]] = [n[k + d], n[k]]; return n; });
  const joinRight = (k) => chain[k + 1] === chain[k] + 1;
  const check = () => {
    const ok = chain.every((v, k) => v === k);
    done({ ok, answer: item.chain.join(' → ') }, chain.map((i) => item.chain[i]).join(' → '));
  };
  return (
    <div className="stack-sm">
      <p className="hint">Build the chain, cause first: tap the cards in order (tap a placed card to take it back), or drag them into place.</p>
      <div className={`hist-zone${poolOver ? ' is-over' : ''}`} {...poolZone} aria-label="Cards">
        <div className="hist-chips">
          {cards.filter((i) => !chain.includes(i)).map((i) => (
            <button key={i} type="button" className="hist-chip" disabled={!!res} onClick={() => insert(i, chain.length)} {...dragProps(i)}>
              <MdInline>{item.chain[i]}</MdInline>
            </button>
          ))}
          {chain.length === item.chain.length && <span className="hint">All cards placed.</span>}
        </div>
      </div>
      <ol className="hist-chain" aria-label="Your chain">
        {chain.map((i, k) => (
          <React.Fragment key={i}>
            <ChainSlot onDropCard={(v) => !res && insert(Number(v), k)}>
              <div className="order-item" style={{ width: '100%' }} data-result={res ? (i === k ? 'correct' : 'wrong') : undefined}>
                <span className="n">{k + 1}</span>
                <button type="button" className="hist-chip" style={{ border: 'none', background: 'none', padding: 0 }} disabled={!!res}
                  onClick={() => setChain((c) => c.filter((x) => x !== i))} aria-label={`Take back: ${item.chain[i]}`} {...dragProps(i)}>
                  <MdInline>{item.chain[i]}</MdInline>
                </button>
                <span className="btn-row">
                  <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label="Move up" disabled={k === 0 || !!res} onClick={() => move(k, -1)}><ArrowUp size={14} /></button>
                  <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label="Move down" disabled={k === chain.length - 1 || !!res} onClick={() => move(k, 1)}><ArrowDown size={14} /></button>
                </span>
              </div>
            </ChainSlot>
            {k < chain.length - 1 && (
              <li className={`hist-chain-link${joinRight(k) ? ' is-right' : ''}`} aria-hidden={!joinRight(k)}>
                <span aria-hidden="true">↓</span>
                {joinRight(k) && item.links?.[i] ? <MdInline>{item.links[i]}</MdInline> : <span>{joinRight(k) ? 'led to' : ''}</span>}
              </li>
            )}
          </React.Fragment>
        ))}
        {!res && chain.length < item.chain.length && (
          <ChainSlot onDropCard={(v) => insert(Number(v), chain.length)}>
            <span className="hint">{chain.length ? 'Drop here to add at the end' : 'Drop the first cause here'}</span>
          </ChainSlot>
        )}
      </ol>
      {!res && <div className="btn-row">
        <button type="button" className="btn btn-primary btn-sm" disabled={chain.length < item.chain.length} onClick={check}><Check size={14} aria-hidden="true" /> Check</button>
        {chain.length > 0 && <button type="button" className="btn btn-quiet btn-sm" onClick={() => setChain([])}>Clear</button>}
      </div>}
      {res && <Result ok={res.ok} answer={res.ok ? null : res.answer} item={item} given="" onRetry={retry ? () => { reset(); setChain([]); } : null} />}
    </div>
  );
}

// ---- source_analysis -------------------------------------------------------------------------------------------

export function SourceBlock({ source }) {
  return (
    <figure className="hist-source" style={{ margin: 0 }}>
      <blockquote className="hist-source-text" style={{ margin: 0 }}>{source.text}</blockquote>
      <figcaption className="hist-source-meta">
        {[source.author, source.date].filter(Boolean).join(', ')}
        {source.citation && <div><cite>{source.citation}</cite></div>}
      </figcaption>
    </figure>
  );
}

function SourceAnalysis({ item, onResult, retry = true }) {
  const [picks, setPicks] = useState({});
  const [res, done, reset] = useCheck(onResult);
  const pick = (qi, o) => {
    if (qi in picks) return;
    const next = { ...picks, [qi]: o };
    setPicks(next);
    if (Object.keys(next).length === item.questions.length) {
      const right = item.questions.filter((q, k) => next[k] === q.answer).length;
      done({ ok: right === item.questions.length, note: `${right} of ${item.questions.length} right.` },
        item.questions.map((q, k) => `${q.question} ${next[k]}`).join('; '));
    }
  };
  return (
    <div className="stack-sm">
      <SourceBlock source={item.source} />
      {item.questions.map((q, qi) => (
        <fieldset key={qi} className="stack-sm" style={{ border: 'none', padding: 0, margin: 0 }}>
          <legend style={{ fontWeight: 600, marginBottom: 'var(--space-2)' }}><MdInline>{q.question}</MdInline></legend>
          {q.options.map((o, k) => {
            const chosen = picks[qi] === o;
            const shown = qi in picks;
            return (
              <button key={o} type="button" className="choice" aria-pressed={chosen} disabled={shown}
                data-result={shown && o === q.answer ? 'correct' : chosen ? 'wrong' : undefined} onClick={() => pick(qi, o)}>
                <span className="key">{'ABCDE'[k]}</span><span><MdInline>{o}</MdInline></span><span />
              </button>
            );
          })}
        </fieldset>
      ))}
      {res && <Result ok={res.ok} note={res.note} item={item} given="" onRetry={retry ? () => { reset(); setPicks({}); } : null} />}
    </div>
  );
}

// ---- map_pins --------------------------------------------------------------------------------------------------

const near = (pin, at, w, h) => Math.hypot(pin.x - at.x, (pin.y - at.y) * (h / w)) <= (pin.tolerance ?? 0.06);  // tolerance in map widths

function MapPins({ item, onResult, retry = true }) {
  const labels = useMemo(() => seeded(item.pins.map((p) => p.label), item.id || item.prompt, true), [item]);
  const [placed, setPlaced] = useState({});   // label -> {x, y}
  const [sel, setSel] = useState(null);
  const [cursor, setCursor] = useState({ x: 0.5, y: 0.5 });
  const [focused, setFocused] = useState(false);
  const [res, done, reset] = useCheck(onResult);
  const svg = useRef(null);
  const dims = useRef({ w: 1000, h: 500 });
  const put = (label, at) => { if (!res && label && at && labels.includes(label)) { setPlaced((p) => ({ ...p, [label]: at })); setSel(null); } };
  const at = (e) => pointToFraction(svg.current, e.clientX, e.clientY, dims.current.w, dims.current.h);
  const onKey = (e) => {
    if (!sel || res) return;
    const step = e.shiftKey ? 0.05 : 0.015;
    const d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
    if (d) { e.preventDefault(); setCursor((c) => ({ x: Math.min(1, Math.max(0, c.x + d[0])), y: Math.min(1, Math.max(0, c.y + d[1])) })); }
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); put(sel, cursor); }
  };
  const check = () => {
    const { w, h } = dims.current;
    const right = item.pins.filter((p) => placed[p.label] && near(p, placed[p.label], w, h)).length;
    done({ ok: right === item.pins.length, note: `${right} of ${item.pins.length} close enough. The dashed circles show where they belong.` },
      item.pins.map((p) => `${p.label} at (${placed[p.label]?.x.toFixed(2)}, ${placed[p.label]?.y.toFixed(2)})`).join('; '));
  };
  return (
    <div className="stack-sm">
      <p className="hint">Drag each label onto the {MAP_LABEL[item.map] || ''} map, or tap a label and then tap the map. With a keyboard: pick a label, focus the map, move with the arrow keys and press Enter.</p>
      <div className="hist-chips" role="group" aria-label="Labels">
        {labels.map((l) => (
          <button key={l} type="button" className={`hist-chip${placed[l] ? ' is-placed' : ''}`} aria-pressed={sel === l} disabled={!!res}
            data-result={res ? (near(item.pins.find((p) => p.label === l), placed[l] || { x: -9, y: -9 }, dims.current.w, dims.current.h) ? 'correct' : 'wrong') : undefined}
            onClick={() => setSel(sel === l ? null : l)} {...(res ? {} : dragProps(l, () => setSel(l)))}>
            {l}{placed[l] && !res ? ' ✓' : ''}
          </button>
        ))}
      </div>
      <OutlineMap ref={svg} name={item.map} className={sel && !res ? 'is-placing' : ''} tabIndex={0} role="group"
        label={`Map: ${MAP_LABEL[item.map] || item.map}. ${sel ? `Placing ${sel}.` : 'Pick a label first.'}`}
        onClick={(e) => sel && put(sel, at(e))} onKeyDown={onKey} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
        onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); put(e.dataTransfer.getData('text/plain'), at(e)); }}>
        {(w, h) => {
          dims.current = { w, h };
          const r = w * 0.009, fs = w * 0.022;
          return (
            <>
              {res && item.pins.map((p) => <circle key={`t-${p.label}`} className="hist-target" cx={p.x * w} cy={p.y * h} r={(p.tolerance ?? 0.06) * w} />)}
              {Object.entries(placed).map(([l, pt]) => {
                const pin = item.pins.find((p) => p.label === l);
                const cls = res ? (near(pin, pt, w, h) ? ' is-ok' : ' is-bad') : sel === l ? ' is-selected' : '';
                return (
                  <g key={l} className={`hist-pin${cls}`} onClick={(e) => { if (!res) { e.stopPropagation(); setSel(l); } }}>
                    <circle cx={pt.x * w} cy={pt.y * h} r={r} />
                    <text x={pt.x * w + r * 1.4} y={pt.y * h + fs * 0.35} fontSize={fs} strokeWidth={fs * 0.25}>{l}</text>
                  </g>
                );
              })}
              {focused && sel && !res && <circle className="hist-cursor" cx={cursor.x * w} cy={cursor.y * h} r={r * 2.2} />}
            </>
          );
        }}
      </OutlineMap>
      {!res && <div className="btn-row">
        <button type="button" className="btn btn-primary btn-sm" disabled={Object.keys(placed).length < labels.length} onClick={check}><Check size={14} aria-hidden="true" /> Check</button>
        {Object.keys(placed).length > 0 && <button type="button" className="btn btn-quiet btn-sm" onClick={() => setPlaced({})}>Clear</button>}
      </div>}
      {res && <Result ok={res.ok} note={res.note} item={item} given="" onRetry={retry ? () => { reset(); setPlaced({}); } : null} />}
    </div>
  );
}

// ---- who_am_i --------------------------------------------------------------------------------------------------

function WhoAmI({ item, onResult, retry = true }) {
  const opts = useMemo(() => seeded(item.options, item.id || item.prompt, true), [item]);
  const [shown, setShown] = useState(1);
  const [wrong, setWrong] = useState([]);
  const [res, done, reset] = useCheck(onResult);
  const guess = (o) => {
    if (o === item.answer) { done({ ok: true, note: `${whoPoints(item, shown)} points (${shown} clue${shown > 1 ? 's' : ''}).` }, o); return; }
    setWrong((w) => [...w, o]);
    if (shown < item.clues.length) setShown(shown + 1);
    else done({ ok: false, answer: item.answer }, o);
  };
  return (
    <div className="stack-sm">
      <ol className="hist-clues" aria-live="polite">
        {item.clues.slice(0, res ? item.clues.length : shown).map((c, k) => <li key={k}><MdInline>{c}</MdInline></li>)}
      </ol>
      {!res && <p className="hist-points">Worth {whoPoints(item, shown)} points now</p>}
      {opts.map((o, k) => (
        <button key={o} type="button" className="choice" disabled={!!res || wrong.includes(o)} onClick={() => guess(o)}
          data-result={wrong.includes(o) ? 'wrong' : res && o === item.answer ? 'correct' : undefined}>
          <span className="key">{'ABCDE'[k]}</span><span><MdInline>{o}</MdInline></span><span />
        </button>
      ))}
      {!res && shown < item.clues.length && (
        <div className="btn-row"><button type="button" className="btn btn-quiet btn-sm" onClick={() => setShown(shown + 1)}><Lightbulb size={14} aria-hidden="true" /> Another clue</button></div>
      )}
      {res && <Result ok={res.ok} note={res.note} answer={res.answer} item={item} given={wrong.at(-1) || ''} onRetry={retry ? () => { reset(); setShown(1); setWrong([]); } : null} />}
    </div>
  );
}

// ---- date_guess ------------------------------------------------------------------------------------------------

function DateGuess({ item, onResult, retry = true }) {
  const lo = Math.min(-3000, Math.floor((item.year - 600) / 1000) * 1000);
  const hi = Math.max(new Date().getFullYear(), item.year + 50);
  const [value, setValue] = useState(String(Math.round((lo + hi) / 2 / 100) * 100));
  const [tries, setTries] = useState([]);   // [{year, hint}]
  const [res, done, reset] = useCheck(onResult);
  const year = Number(value);
  const valid = value.trim() !== '' && Number.isFinite(year);
  const submit = (e) => {
    e.preventDefault();
    if (res || !valid) return;
    const y = Math.round(year);
    const off = y - item.year;
    if (Math.abs(off) <= item.tolerance) { done({ ok: true, note: `${fmtYear(item.year)}${off ? ` (you were ${Math.abs(off)} years off)` : ''}.` }, fmtYear(y)); return; }
    const next = [...tries, { year: y, hint: off > 0 ? 'Earlier than that.' : 'Later than that.' }];
    setTries(next);
    if (next.length >= 3) done({ ok: false, answer: fmtYear(item.year) }, fmtYear(y));
  };
  return (
    <form className="stack-sm" onSubmit={submit}>
      <p className="question" style={{ fontSize: '1.02rem' }}><MdInline>{item.event}</MdInline></p>
      <input type="range" className="hist-range" min={lo} max={hi} step={1} value={valid ? Math.min(hi, Math.max(lo, year)) : lo}
        onChange={(e) => setValue(e.target.value)} disabled={!!res} aria-label="Year slider" />
      <div className="hist-year-row">
        <input className="input num" type="number" inputMode="numeric" value={value} onChange={(e) => setValue(e.target.value)} readOnly={!!res}
          aria-label="Year (negative for BCE)" />
        <span className="hint">{valid ? `= ${fmtYear(year)}` : 'Type a year; negative for BCE'}</span>
        {!res && <button type="submit" className="btn btn-primary btn-sm" disabled={!valid}><Check size={14} aria-hidden="true" /> Guess ({3 - tries.length} left)</button>}
      </div>
      {tries.length > 0 && !res && (
        <ul className="hint" aria-live="polite" style={{ margin: 0, paddingLeft: 'var(--space-5)' }}>
          {tries.map((t, k) => <li key={k}>{fmtYear(t.year)}: {t.hint}</li>)}
        </ul>
      )}
      {item.tolerance > 0 && !res && <p className="hint">Within {item.tolerance} year{item.tolerance > 1 ? 's' : ''} counts.</p>}
      {res && <Result ok={res.ok} note={res.note} answer={res.answer} item={item} given={fmtYear(Math.round(year))} onRetry={retry ? () => { reset(); setTries([]); } : null} />}
    </form>
  );
}

// ---- roleplay --------------------------------------------------------------------------------------------------

const TURNS_TO_FINISH = 4;

export function Roleplay({ item, onResult, topicId }) {
  const tid = topicId || item.topicId;
  const [msgs, setMsgs] = useState(() => (item.opening ? [{ role: 'assistant', content: item.opening }] : []));
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const finished = useRef(false);
  const turns = msgs.filter((m) => m.role === 'user').length;
  const send = async (e) => {
    e.preventDefault();
    const message = text.trim();
    if (!message || busy || !tid) return;
    const history = msgs;
    setMsgs([...history, { role: 'user', content: message }]);
    setText('');
    setBusy(true);
    setErr(null);
    try {
      const r = await api('/api/tutor/lesson', { method: 'POST', body: { topicId: tid, mode: 'persona', persona: item.persona, era: item.era || '', message, history } });
      setMsgs((m) => [...m, { role: 'assistant', content: r?.reply || '…' }]);
      if (turns + 1 >= TURNS_TO_FINISH && !finished.current) { finished.current = true; onResult?.(null, ''); }
    } catch (ex) {
      setErr(ex.message);
      setMsgs(history);
      setText(message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="stack-sm">
      <p className="hist-goal"><strong>{item.persona}</strong>{item.era ? ` · ${item.era}` : ''}</p>
      <p className="hint">Your goal: <MdInline>{item.goal}</MdInline></p>
      {!tid ? (
        <div className="stack-sm">
          <p className="notice notice-info">Open this lesson in History &gt; Figures to talk with {item.persona}.</p>
          {onResult && <div className="btn-row"><button type="button" className="btn btn-quiet btn-sm" onClick={() => onResult(null, '')}>Skip</button></div>}
        </div>
      ) : (
        <>
          <div className="hist-chat" aria-live="polite">
            {msgs.length === 0 && <p className="hint">Ask {item.persona} your first question.</p>}
            {msgs.map((m, k) => (
              <div key={k} className={`hist-msg${m.role === 'user' ? ' is-me' : ''}`}>
                <span className="who">{m.role === 'user' ? 'You' : item.persona}</span>
                {m.role === 'user' ? m.content : <Md>{m.content}</Md>}
              </div>
            ))}
            {busy && <p className="hint">{item.persona} is thinking…</p>}
          </div>
          {err && <p className="notice notice-bad">{err}</p>}
          <form className="hist-chat-form" onSubmit={send}>
            <input className="input" value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} placeholder={`Ask ${item.persona}…`} aria-label="Your question" disabled={busy} />
            <button type="submit" className="btn btn-primary btn-sm" disabled={busy || !text.trim()}><Send size={14} aria-hidden="true" /> Ask</button>
          </form>
          <p className="hint">{turns >= TURNS_TO_FINISH ? 'Done: you can keep talking.' : `${TURNS_TO_FINISH - turns} more question${TURNS_TO_FINISH - turns > 1 ? 's' : ''} to finish.`} The figure answers from the lesson and won't invent quotes; check what it says against your sources.</p>
        </>
      )}
    </div>
  );
}

export const HISTORY_RENDER = {
  categorize: Categorize, cause_effect: CauseEffect, source_analysis: SourceAnalysis, map_pins: MapPins,
  who_am_i: WhoAmI, date_guess: DateGuess, roleplay: Roleplay, hist_roleplay: Roleplay,
};

export const HISTORY_LABEL = {
  categorize: 'Sort into groups', cause_effect: 'Cause and effect', source_analysis: 'Read the source',
  map_pins: 'Place on the map', who_am_i: 'Who am I?', date_guess: 'When did it happen?', roleplay: 'Talk to a figure',
  hist_roleplay: 'Talk to a figure',
};
