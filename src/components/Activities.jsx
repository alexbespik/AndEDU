import React, { useEffect, useMemo, useRef, useState } from 'react';
import { RotateCcw, Volume2, Check, X, Zap, Trophy, Timer, ArrowUp, ArrowDown, Shuffle } from 'lucide-react';
import Md, { MdInline } from './Md';
import { reportActivity, reportXp } from '../lib/engage';
import { speak, noVoiceHelp } from '../lib/speech';
import { answerIndex } from './QuizEngine';

const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
};
const shuffle = (a) => { const o = [...a]; for (let i = o.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [o[i], o[j]] = [o[j], o[i]]; } return o; };


/** Flashcards: flip, then "Again" (back into the pile) or "Got it". Cards you miss come back until you know them. */
export function FlashcardDeck({ cards = [], topicId }) {
  const [pile, setPile] = useState(() => shuffle(cards.map((c, i) => ({ ...c, i }))));
  const [flipped, setFlipped] = useState(false);
  const [known, setKnown] = useState(0);
  const [misses, setMisses] = useState(0);
  const [voiceNote, setVoiceNote] = useState(null);
  const card = pile[0];
  const listen = (text, lang) => speak(text, lang).then((r) => setVoiceNote(r.ok ? null : r.reason === 'no-voice' ? noVoiceHelp(r.language) : 'This browser cannot read text aloud.'));
  useEffect(() => { if (!card && cards.length) reportActivity(topicId, 'flashcards', cards.length, cards.length + misses); }, [card]); // eslint-disable-line react-hooks/exhaustive-deps

  const answer = (gotIt) => {
    setFlipped(false);
    if (gotIt) {
      setKnown((k) => k + 1);
      reportXp('practice_correct', `${topicId}:card:${card.i}`);
      setPile((p) => p.slice(1));
    } else {
      setMisses((m) => m + 1);
      setPile((p) => [...p.slice(1, 4), p[0], ...p.slice(4)]);  // comes back in a few cards
    }
  };

  useEffect(() => {
    const onKey = (e) => {
      if (!card || ['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return;
      if (e.key === ' ') { e.preventDefault(); setFlipped((f) => !f); }
      if (flipped && e.key === 'ArrowRight') answer(true);
      if (flipped && e.key === 'ArrowLeft') answer(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  if (!cards.length) return <div className="panel"><p>No flashcards for this lesson yet. New classes come with them, or ask the Assistant to add some.</p></div>;
  if (!card) {
    return (
      <div className="panel stack-sm review-done">
        <Trophy size={32} className="trophy" aria-hidden="true" />
        <h2>Deck complete</h2>
        <p className="hint">{cards.length} cards, {misses} repeat{misses === 1 ? '' : 's'}.</p>
        <div className="btn-row"><button type="button" className="btn btn-primary" onClick={() => { setPile(shuffle(cards.map((c, i) => ({ ...c, i })))); setKnown(0); setMisses(0); }}><RotateCcw size={14} /> Shuffle and go again</button></div>
      </div>
    );
  }
  return (
    <div className="stack">
      <div className="quiz-progress"><span>{known} of {cards.length} known · {pile.length} left</span><span className="hint">Space flips · ← again · → got it</span></div>
      <button type="button" className="flashcard" data-flipped={flipped} onClick={() => setFlipped((f) => !f)} aria-label={flipped ? 'Show the front' : 'Show the answer'}>
        <span className="flash-side">{flipped ? 'Answer' : 'Prompt'}</span>
        <div className="flash-text">{flipped ? <Md>{card.back}</Md> : <Md>{card.front}</Md>}</div>
        {!flipped && card.hint && <span className="hint">Hint: {card.hint}</span>}
      </button>
      {voiceNote && <p className="notice notice-info">{voiceNote}</p>}
      <div className="btn-row">
        {card.lang && (
          <button type="button" className="btn btn-quiet" onClick={() => listen(card.front, card.lang)}><Volume2 size={15} /> Listen</button>
        )}
        {flipped ? (
          <>
            <button type="button" className="btn btn-quiet" onClick={() => answer(false)}><X size={15} /> Again</button>
            <button type="button" className="btn btn-primary" onClick={() => answer(true)}><Check size={15} /> Got it</button>
          </>
        ) : <button type="button" className="btn btn-secondary" onClick={() => setFlipped(true)}>Show answer</button>}
      </div>
    </div>
  );
}

const TILE = ['#c0392b', '#2563a0', '#c99a2e', '#1f7a52'];
const SECONDS = 20;

/** Kahoot-style speed round: 20 s per question, more points for faster answers, streak bonus, personal best. */
export function SpeedRound({ quiz = [], topicId, userId }) {
  const qs = useMemo(() => shuffle(quiz.filter((q) => answerIndex(q) !== null)).slice(0, 10), [quiz]);
  const bestKey = `andedu_speed_best_${userId}_${topicId}`;
  const [phase, setPhase] = useState('ready'); // ready | question | reveal | done
  const [i, setI] = useState(0);
  const [left, setLeft] = useState(SECONDS);
  const [pick, setPick] = useState(null);
  const [score, setScore] = useState(0);
  const [gain, setGain] = useState(0);
  const [streak, setStreak] = useState(0);
  const [right, setRight] = useState(0);
  const started = useRef(0);
  const q = qs[i];

  useEffect(() => {
    if (phase !== 'question') return undefined;
    const t = setInterval(() => {
      const l = Math.max(0, SECONDS - (performance.now() - started.current) / 1000);
      setLeft(l);
      if (l <= 0) reveal(null);
    }, 100);
    return () => clearInterval(t);
  });

  const begin = (k) => { setI(k); setPick(null); setGain(0); started.current = performance.now(); setLeft(SECONDS); setPhase('question'); };
  const reveal = (choice) => {
    if (phase !== 'question') return;
    const ok = choice !== null && choice === answerIndex(q);
    const t = (performance.now() - started.current) / 1000;
    const pts = ok ? Math.round(1000 * (1 - Math.min(t, SECONDS) / SECONDS / 2)) + Math.min(streak, 5) * 100 : 0;
    setPick(choice); setGain(pts); setScore((s) => s + pts); setStreak((s) => (ok ? s + 1 : 0)); setRight((r) => r + (ok ? 1 : 0));
    setPhase('reveal');
    // games never change the class quiz score: XP here, and the round's result goes to the practice & games score
    if (ok) reportXp('practice_correct', `${topicId}:speed:${q.id ?? i}`);
  };
  const next = () => {
    if (i + 1 < qs.length) begin(i + 1);
    else {
      setPhase('done');
      if (score > store.get(bestKey, 0)) store.set(bestKey, score);
      reportActivity(topicId, 'speed', right, qs.length, score);
    }
  };

  if (qs.length < 3) return <div className="panel"><p>A speed round needs at least 3 quiz questions.</p></div>;
  if (phase === 'ready') {
    return (
      <div className="panel stack review-done speed-intro">
        <Zap size={36} className="trophy" aria-hidden="true" />
        <h2>Speed round</h2>
        <p className="hint">{qs.length} questions · {SECONDS} seconds each · faster answers score more · streaks add bonus points.</p>
        <p className="hint">Counts toward your practice &amp; games score, not your quiz score.</p>
        {store.get(bestKey, 0) > 0 && <p>Your best: <b className="num">{store.get(bestKey, 0)}</b></p>}
        <div className="btn-row"><button type="button" className="btn btn-gold" onClick={() => { setScore(0); setStreak(0); setRight(0); begin(0); }}>Start</button></div>
      </div>
    );
  }
  if (phase === 'done') {
    const best = store.get(bestKey, 0);
    return (
      <div className="panel stack review-done">
        <Trophy size={36} className="trophy" aria-hidden="true" />
        <h2>{score >= best ? 'New personal best!' : 'Round over'}</h2>
        <div className="review-stats">
          <div><span className="today-num num">{score}</span><span className="hint">points</span></div>
          <div><span className="today-num num">{right}/{qs.length}</span><span className="hint">correct</span></div>
          <div><span className="today-num num">{best}</span><span className="hint">best</span></div>
        </div>
        <div className="btn-row"><button type="button" className="btn btn-gold" onClick={() => { setScore(0); setStreak(0); setRight(0); begin(0); }}>Play again</button></div>
      </div>
    );
  }
  const key = answerIndex(q);
  return (
    <div className="stack">
      <div className="speed-top">
        <span className="num">Q {i + 1}/{qs.length}</span>
        <div className="meter speed-timer" aria-label={`${Math.ceil(left)} seconds left`}><span style={{ width: `${(left / SECONDS) * 100}%` }} /></div>
        <span className="num"><Timer size={14} aria-hidden="true" /> {Math.ceil(left)}s</span>
        <span className="num speed-score">{score}</span>
        {streak >= 2 && <span className="combo"><Zap size={14} aria-hidden="true" /> {streak} streak</span>}
      </div>
      <div className="question speed-q"><Md>{q.question}</Md></div>
      <div className="speed-grid">
        {q.options.map((opt, k) => (
          <button key={k} type="button" className="speed-tile" style={{ '--tile': TILE[k % 4] }} disabled={phase === 'reveal'}
            data-state={phase === 'reveal' ? (k === key ? 'right' : k === pick ? 'wrong' : 'dim') : undefined} onClick={() => reveal(k)}>
            <MdInline>{opt}</MdInline>
          </button>
        ))}
      </div>
      {phase === 'reveal' && (
        <div className="btn-row" style={{ justifyContent: 'space-between' }}>
          <span className={pick === key ? 'speed-gain' : 'hint'}>{pick === key ? `+${gain} points` : pick === null ? "Time's up" : 'Not this time'}</span>
          <button type="button" className="btn btn-primary" onClick={next}>{i + 1 < qs.length ? 'Next' : 'Results'}</button>
        </div>
      )}
    </div>
  );
}

const fmtYear = (y) => (y < 0 ? `${Math.abs(Math.round(y))} BCE` : String(Math.round(y)));

/** Timeline: the events in order, and a challenge that shuffles them for the student to put back in order. */
export function TimelineView({ events = [], topicId }) {
  const [mode, setMode] = useState('view');
  const [order, setOrder] = useState([]);
  const [checked, setChecked] = useState(false);
  const pool = useMemo(() => shuffle(events).slice(0, 7), [events, mode]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (mode === 'challenge') { setOrder(pool); setChecked(false); } }, [mode, pool]);
  if (!events.length) return <div className="panel"><p>No timeline for this lesson yet.</p></div>;
  const move = (k, d) => setOrder((o) => { const n = [...o]; [n[k], n[k + d]] = [n[k + d], n[k]]; return n; });
  const correct = checked && order.every((e, k) => k === 0 || order[k - 1].year <= e.year);
  return (
    <div className="stack">
      <div className="btn-row">
        <button type="button" className={`btn btn-sm ${mode === 'view' ? 'btn-primary' : 'btn-quiet'}`} onClick={() => setMode('view')}>Timeline</button>
        <button type="button" className={`btn btn-sm ${mode === 'challenge' ? 'btn-primary' : 'btn-quiet'}`} onClick={() => setMode('challenge')}><Shuffle size={14} /> Order the events</button>
      </div>
      {mode === 'view' ? (
        <ol className="timeline">
          {events.map((e, k) => (
            <li key={k}>
              <span className="tl-year num">{e.date || fmtYear(e.year)}</span>
              <div><strong><MdInline>{e.title}</MdInline></strong>{e.detail && <div className="hint"><Md>{e.detail}</Md></div>}</div>
            </li>
          ))}
        </ol>
      ) : (
        <div className="stack-sm">
          <p className="hint">Put these events in chronological order, earliest first.</p>
          <ol className="order-list">
            {order.map((e, k) => (
              <li key={e.title} className="order-item" data-result={checked ? (k === 0 || order[k - 1].year <= e.year ? 'correct' : 'wrong') : undefined}>
                <span className="n">{k + 1}</span>
                <span><MdInline>{e.title}</MdInline>{checked && <span className="hint"> · {e.date || fmtYear(e.year)}</span>}</span>
                <span className="btn-row">
                  <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label="Move up" disabled={k === 0 || checked} onClick={() => move(k, -1)}><ArrowUp size={14} /></button>
                  <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label="Move down" disabled={k === order.length - 1 || checked} onClick={() => move(k, 1)}><ArrowDown size={14} /></button>
                </span>
              </li>
            ))}
          </ol>
          <div className="btn-row">
            {!checked ? <button type="button" className="btn btn-primary" onClick={() => {
              setChecked(true);
              const inPlace = order.filter((e, k) => k === 0 || order[k - 1].year <= e.year).length;
              reportActivity(topicId, 'timeline', inPlace, order.length);
              if (inPlace === order.length) reportXp('practice_correct', `${topicId}:timeline`);
            }}>Check order</button>
              : <button type="button" className="btn btn-quiet" onClick={() => { setMode('view'); setTimeout(() => setMode('challenge'), 0); }}><RotateCcw size={14} /> New set</button>}
            {checked && <span className={correct ? 'speed-gain' : 'hint'}>{correct ? 'All in order.' : 'Some events are out of order: the red ones.'}</span>}
          </div>
        </div>
      )}
    </div>
  );
}

/** Match pairs (practice type "match_pairs"): pick a left item, then its partner on the right. */
export function MatchPairs({ item, onSolved }) {
  const rights = useMemo(() => shuffle(item.pairs.map((p) => p[1])), [item]);
  const [sel, setSel] = useState(null);
  const [matched, setMatched] = useState({});
  const [wrong, setWrong] = useState(null);
  const done = Object.keys(matched).length === item.pairs.length;
  useEffect(() => { if (done) onSolved?.(); }, [done]); // eslint-disable-line react-hooks/exhaustive-deps
  const tryMatch = (r) => {
    if (sel === null) return;
    if (item.pairs[sel][1] === r) { setMatched((m) => ({ ...m, [sel]: r })); setSel(null); }
    else { setWrong(r); setTimeout(() => setWrong(null), 600); }
  };
  return (
    <div className="stack-sm">
      <div className="match-grid">
        <div className="stack-sm">
          {item.pairs.map(([l], k) => (
            <button key={l} type="button" className="choice match-item" aria-pressed={sel === k} disabled={k in matched}
              data-result={k in matched ? 'correct' : undefined} onClick={() => setSel(k)}><span /><span><MdInline>{l}</MdInline></span><span /></button>
          ))}
        </div>
        <div className="stack-sm">
          {rights.map((r) => {
            const used = Object.values(matched).includes(r);
            return (
              <button key={r} type="button" className="choice match-item" disabled={used || sel === null}
                data-result={used ? 'correct' : wrong === r ? 'wrong' : undefined} onClick={() => tryMatch(r)}><span /><span><MdInline>{r}</MdInline></span><span /></button>
            );
          })}
        </div>
      </div>
      {done && <div className="feedback ok"><p style={{ fontWeight: 700 }}>All matched.</p>{item.explanation && <Md>{item.explanation}</Md>}</div>}
    </div>
  );
}

const KIND_LABEL = { speed: 'Speed round', flashcards: 'Flashcards', timeline: 'Timeline', practice: 'Practice' };

/** Quiz score (counts for the class) and the separate practice & games score, side by side. */
export function ScoreStrip({ topicId, userId }) {
  const [s, setS] = useState(null);
  useEffect(() => {
    if (!userId || !topicId) return undefined;
    let live = true;
    import('../lib/api').then(({ api }) => api(`/api/activity/${userId}/topic/${encodeURIComponent(topicId)}`)).then((d) => live && setS(d)).catch(() => {});
    const on = (e) => { if (e.detail?.topicId === topicId) setS(e.detail); };
    window.addEventListener('andedu:activity', on);
    return () => { live = false; window.removeEventListener('andedu:activity', on); };
  }, [topicId, userId]);
  if (!s || (s.quizScore === null && s.activityScore === null && !s.quizCounts)) return null;
  const pct = (v) => (v === null || v === undefined ? '–' : `${Math.round(v * 100)}%`);
  return (
    <div className="score-strip" role="group" aria-label="Scores">
      {s.quizCounts && (
        <div className="score-box">
          <span className="score-val num">{pct(s.quizScore)}</span>
          <span className="hint">Quiz score · counts toward this class and how the next class adapts</span>
        </div>
      )}
      <div className="score-box score-box-alt">
        <span className="score-val num">{pct(s.activityScore)}</span>
        <span className="hint">Practice &amp; games · separate, never changes your quiz score</span>
        {Object.keys(s.activities || {}).length > 0 && (
          <span className="score-kinds">
            {Object.entries(s.activities).map(([k, v]) => (
              <span key={k} className="chip">{KIND_LABEL[k] || k} {pct(v.best)}{k === 'speed' && v.points ? ` · ${v.points} pts` : ''}</span>
            ))}
          </span>
        )}
      </div>
    </div>
  );
}
