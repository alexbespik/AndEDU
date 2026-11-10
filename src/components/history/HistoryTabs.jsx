// History workspace tabs built on the history practice types: Map, Sources (source_analysis), Figures (roleplay)
// and Games (a daily mix with a score). Practice items come from the history topics' `practice` lists.
import React, { useEffect, useMemo, useState } from 'react';
import { MapPin, Play, RotateCcw, Trophy, ArrowRight } from 'lucide-react';
import { FlashcardDeck, TimelineView } from '../Activities';
import { HISTORY_RENDER, HISTORY_LABEL } from '../../practice/history';
import { OutlineMap } from './OutlineMap';
import { MAP_NAMES, MAP_LABEL, collect, centuryOf } from './historyUtil';
import { reportXp, reportActivity } from '../../lib/engage';
import { localDay } from '../../lib/api';
import '../../styles/history.css';

const xpFor = (item) => (ok) => { if (ok) reportXp('practice_correct', `hist:${item.topicId}:${item.id}`); };

function PracticePanel({ item, onResult, retry = true }) {
  const Body = HISTORY_RENDER[item.type];
  return (
    <section className="panel stack-sm" aria-label={HISTORY_LABEL[item.type]}>
      <p className="hint">{HISTORY_LABEL[item.type]}{item.topicTitle ? ` · ${item.topicTitle}` : ''}</p>
      {item.prompt && <div className="question">{item.prompt}</div>}
      <Body item={item} topicId={item.topicId} retry={retry} onResult={(ok, given) => { xpFor(item)(ok); onResult?.(ok, given); }} />
    </section>
  );
}

// ---- Map -------------------------------------------------------------------------------------------------------

export function MapTab({ topics, onOpenTopic }) {
  const items = useMemo(() => collect(topics, 'map_pins'), [topics]);
  const regions = MAP_NAMES.filter((m) => m === 'world' || items.some((i) => i.map === m));
  const [region, setRegion] = useState(() => (items[0]?.map || 'world'));
  const [playing, setPlaying] = useState(null);
  const here = items.filter((i) => i.map === region);
  const pins = here.flatMap((i) => i.pins.map((p) => ({ ...p, topicId: i.topicId, topicTitle: i.topicTitle })));
  return (
    <div className="stack">
      <div className="btn-row" role="group" aria-label="Region">
        {regions.map((m) => (
          <button key={m} type="button" className={`btn btn-sm ${m === region ? 'btn-primary' : 'btn-quiet'}`} aria-pressed={m === region}
            onClick={() => { setRegion(m); setPlaying(null); }}>{MAP_LABEL[m]}</button>
        ))}
      </div>
      <OutlineMap name={region} role="group" label={`${MAP_LABEL[region]} map with ${pins.length} places from your classes`}>
        {(w, h) => pins.map((p, k) => (
          <g key={`${p.topicId}-${p.label}-${k}`} className="hist-pin hist-pin-btn" role="button" tabIndex={0}
            aria-label={`${p.label}, open ${p.topicTitle}`} onClick={() => onOpenTopic?.(p.topicId)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpenTopic?.(p.topicId); } }}>
            <title>{`${p.label} · ${p.topicTitle}`}</title>
            <circle cx={p.x * w} cy={p.y * h} r={w * 0.009} />
            <text x={p.x * w + w * 0.013} y={p.y * h + w * 0.008} fontSize={w * 0.02} strokeWidth={w * 0.005}>{p.label}</text>
          </g>
        ))}
      </OutlineMap>
      {!items.length && <p className="hint">No map games yet. History classes that place events on a map add them here; click a place to open its class.</p>}
      {here.length > 0 && (
        <div className="stack-sm">
          <p className="hint"><MapPin size={13} aria-hidden="true" /> Click a place to open its class, or play a map game:</p>
          <div className="hist-list">
            {here.map((i) => (
              <button key={`${i.topicId}-${i.id}`} type="button" className="hist-card" aria-pressed={playing === i}
                onClick={() => setPlaying(playing === i ? null : i)}>
                <strong>{i.prompt}</strong><span className="hint">{i.topicTitle} · {i.pins.length} places</span>
              </button>
            ))}
          </div>
          {playing && <PracticePanel key={`${playing.topicId}-${playing.id}`} item={playing} />}
        </div>
      )}
    </div>
  );
}

// ---- Sources ---------------------------------------------------------------------------------------------------

const centuryLabel = (c) => {
  const n = Math.abs(c);
  const suf = n % 100 >= 11 && n % 100 <= 13 ? 'th' : { 1: 'st', 2: 'nd', 3: 'rd' }[n % 10] || 'th';
  return `${n}${suf} century${c < 0 ? ' BCE' : ''}`;
};

export function SourcesTab({ topics }) {
  const items = useMemo(() => collect(topics, 'source_analysis'), [topics]);
  const centuries = useMemo(() => [...new Set(items.map((i) => centuryOf(i.source?.date)).filter((c) => c !== null))].sort((a, b) => a - b), [items]);
  const [filter, setFilter] = useState('all');
  const [open, setOpen] = useState(null);
  if (!items.length) return null;
  const shown = items.filter((i) => filter === 'all' || (filter === 'undated' ? centuryOf(i.source?.date) === null : centuryOf(i.source?.date) === filter));
  return (
    <section className="stack" aria-label="Source questions from your classes">
      <h3 style={{ margin: 0 }}>Source questions from your classes</h3>
      <div className="btn-row" role="group" aria-label="Filter by century">
        {['all', ...centuries, ...(items.some((i) => centuryOf(i.source?.date) === null) ? ['undated'] : [])].map((c) => (
          <button key={c} type="button" className={`btn btn-sm ${filter === c ? 'btn-primary' : 'btn-quiet'}`} aria-pressed={filter === c}
            onClick={() => { setFilter(c); setOpen(null); }}>{c === 'all' ? 'All' : c === 'undated' ? 'Undated' : centuryLabel(c)}</button>
        ))}
      </div>
      <div className="hist-list">
        {shown.map((i) => (
          <button key={`${i.topicId}-${i.id}`} type="button" className="hist-card" aria-pressed={open === i} onClick={() => setOpen(open === i ? null : i)}>
            <strong>{i.source.author || 'Unknown author'}{i.source.date ? `, ${i.source.date}` : ''}</strong>
            <span className="hint">{i.source.text.slice(0, 90)}{i.source.text.length > 90 ? '…' : ''}</span>
            <span className="hint"> · {i.topicTitle}</span>
          </button>
        ))}
      </div>
      {open && <PracticePanel key={`${open.topicId}-${open.id}`} item={open} />}
    </section>
  );
}

// ---- Figures ---------------------------------------------------------------------------------------------------

const looksLikeName = (s) => /^(\p{Lu}[\p{L}'’.-]*)(\s+(of|the|de|da|von|van|al|ibn|bin|le|la|\p{Lu}[\p{L}'’.-]*|[IVX]+)){0,4}$/u.test(String(s || '').trim());

export function FiguresTab({ topics }) {
  const figures = useMemo(() => collect(topics, 'roleplay'), [topics]);
  const [open, setOpen] = useState(null);
  const names = figures.map((f) => f.persona.split(',')[0].trim().toLowerCase());
  const cards = useMemo(() => topics.flatMap((t) => (t.flashcards || []).map((c) => ({ ...c, _t: t.id })))
    .filter((c) => names.some((n) => n && String(c.front).toLowerCase().includes(n)) || looksLikeName(c.front)), [topics, names.join('|')]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="stack">
      <p className="hint">Only historical figures who have died, or fictional characters: impersonating living people is not allowed.</p>
      {figures.length ? (
        <>
          <div className="hist-list">
            {figures.map((f) => (
              <button key={`${f.topicId}-${f.id}`} type="button" className="hist-card" aria-pressed={open === f} onClick={() => setOpen(open === f ? null : f)}>
                <strong>{f.persona}</strong><span className="hint">{f.era || f.topicTitle}</span>
              </button>
            ))}
          </div>
          {open && (
            <section className="panel stack-sm" aria-label={`Conversation with ${open.persona}`}>
              <HISTORY_RENDER.roleplay key={`${open.topicId}-${open.id}`} item={open} topicId={open.topicId} />
            </section>
          )}
        </>
      ) : (
        <p className="hint">No historical figures to talk to yet. History classes add them, or an agent can with add_roleplay_persona.</p>
      )}
      {cards.length > 0 && (
        <section className="stack-sm" aria-label="Flashcards about people">
          <h3 style={{ margin: 0 }}>People flashcards ({cards.length})</h3>
          <FlashcardDeck key={cards.length} cards={cards} topicId="history-figures" />
        </section>
      )}
    </div>
  );
}

// ---- Games -----------------------------------------------------------------------------------------------------

const GAME_TYPES = ['who_am_i', 'date_guess', 'categorize'];
const ROUNDS = 5;
const gameKey = (day) => `andedu_hist_games_${day}`;
const readBest = (day) => { try { return JSON.parse(localStorage.getItem(gameKey(day)) || 'null'); } catch { return null; } };

function dailyPick(items, day, n) {
  let h = 17;
  for (const ch of day) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) { h = (h * 1103515245 + 12345) >>> 0; const j = h % (i + 1); [out[i], out[j]] = [out[j], out[i]]; }
  // one of each type first, then the rest, so the mix stays mixed
  const firsts = GAME_TYPES.map((t) => out.find((i) => i.type === t)).filter(Boolean);
  return [...firsts, ...out.filter((i) => !firsts.includes(i))].slice(0, n);
}

export function GamesTab({ topics, events = [] }) {
  const day = localDay();
  const rounds = useMemo(() => {
    const picks = dailyPick(collect(topics, ...GAME_TYPES), day, events.length >= 3 ? ROUNDS - 1 : ROUNDS);
    return events.length >= 3 ? [...picks, { type: 'timeline', id: 'timeline' }] : picks;
  }, [topics, events.length, day]);
  const [at, setAt] = useState(0);
  const [results, setResults] = useState([]);   // true | false per finished round
  const [best, setBest] = useState(() => readBest(day));
  const score = results.filter(Boolean).length;
  const over = rounds.length > 0 && at >= rounds.length;
  useEffect(() => {
    if (!over) return;
    if (!best || score > best.score) {
      const b = { score, of: rounds.length };
      setBest(b);
      try { localStorage.setItem(gameKey(day), JSON.stringify(b)); } catch { /* private mode */ }
    }
    reportActivity('history-games', 'practice', score, rounds.length);
  }, [over]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!rounds.length) {
    return <p className="hint">No games yet. History classes with Who am I?, date and sorting games (or 3+ timeline events) fill a daily mix here.</p>;
  }
  const finish = (ok) => setResults((r) => (r.length > at ? r : [...r, !!ok]));
  const round = rounds[at];
  return (
    <div className="stack">
      <div className="hist-score" aria-live="polite">
        <Trophy size={18} aria-hidden="true" /><span className="num">{score}</span><span className="hint">of {rounds.length} · today's mix</span>
        {best && <span className="chip" style={{ paddingRight: 'var(--space-2)' }}>Best today {best.score}/{best.of}</span>}
        <span className="hist-dots" aria-hidden="true">
          {rounds.map((_, k) => <span key={k} className={`hist-dot${k < results.length ? (results[k] ? ' is-ok' : ' is-bad') : ''}${k === at && !over ? ' is-now' : ''}`} />)}
        </span>
      </div>
      {over ? (
        <div className="panel stack-sm">
          <p className="question">You scored {score} of {rounds.length}.</p>
          <p className="hint">A new mix comes tomorrow. Missed rounds are worth another look in their classes.</p>
          <div className="btn-row"><button type="button" className="btn btn-quiet btn-sm" onClick={() => { setAt(0); setResults([]); }}><RotateCcw size={14} aria-hidden="true" /> Play again</button></div>
        </div>
      ) : (
        <>
          <p className="hint">Round {at + 1} of {rounds.length}</p>
          {round.type === 'timeline' ? (
            <section className="panel stack-sm" aria-label="Timeline challenge">
              <p className="hint">Timeline challenge</p>
              <TimelineView events={events} topicId="history-all" initialMode="challenge" onChecked={(right, total) => finish(right === total)} />
            </section>
          ) : (
            <PracticePanel key={`${at}-${round.topicId}-${round.id}`} item={round} retry={false} onResult={(ok) => finish(ok)} />
          )}
          {results.length > at && (
            <div className="btn-row">
              <button type="button" className="btn btn-primary btn-sm" onClick={() => setAt(at + 1)}>
                {at + 1 < rounds.length ? <>Next round <ArrowRight size={14} aria-hidden="true" /></> : <><Play size={14} aria-hidden="true" /> See your score</>}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
