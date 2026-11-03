import React, { useEffect, useState } from 'react';
import { Flame, RotateCcw, ArrowRight, Loader2, Check, X } from 'lucide-react';
import { api } from '../lib/api';
import { emitRewards } from '../lib/engage';
import Md, { MdInline } from './Md';

const LETTERS = 'ABCDEFGH';

/**
 * Spaced review of questions the student missed before. Answers are checked on the server (the key never
 * reaches the browser before answering); a missed question returns at the end of the session once.
 */
export default function ReviewSession({ userId, onDone }) {
  const [queue, setQueue] = useState(null);
  const [i, setI] = useState(0);
  const [pick, setPick] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [combo, setCombo] = useState(0);
  const [stats, setStats] = useState({ right: 0, answered: 0, mastered: 0, xp: 0 });
  const [finished, setFinished] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api(`/api/review/${userId}/session`).then((d) => setQueue(d.questions)).catch((e) => setError(e.message));
  }, [userId]);

  const q = queue?.[i];

  const check = async () => {
    if (pick === null || busy) return;
    if (q.retry) {  // practice only: graded locally, the server already scheduled it for tomorrow
      const ok = pick === q.key;
      setResult({ correct: ok, correctAnswer: q.key, explanation: q.explanation, retry: true });
      setCombo((c) => (ok ? c + 1 : 0));
      return;
    }
    setBusy(true);
    try {
      const r = await api(`/api/review/${userId}/answer`, { method: 'POST', body: { topicId: q.topicId, questionId: q.questionId, selected: pick } });
      setResult(r);
      emitRewards(r.rewards);
      setCombo((c) => (r.correct ? c + 1 : 0));
      setStats((s) => ({ right: s.right + (r.correct ? 1 : 0), answered: s.answered + 1, mastered: s.mastered + (r.mastered ? 1 : 0), xp: s.xp + (r.rewards?.xp || 0) }));
      // one more try at the end of this session for a miss (gamified), without scoring it twice
      if (!r.correct) setQueue((list) => [...list, { ...q, retry: true, key: r.correctAnswer, explanation: r.explanation }]);
    } catch (e) { setError(e.message); }
    setBusy(false);
  };

  const next = async () => {
    if (i + 1 < queue.length) {
      setI(i + 1); setPick(null); setResult(null);
      return;
    }
    const bonus = await api(`/api/review/${userId}/finish`, { method: 'POST', body: { answered: stats.answered } }).catch(() => null);
    emitRewards(bonus);
    setFinished({ ...stats, xp: stats.xp + (bonus?.xp || 0) });
  };

  if (error) return <div className="page"><p className="notice notice-bad">{error}</p></div>;
  if (!queue) return <div className="page"><p className="hint"><Loader2 size={14} className="spin" /> Gathering your review…</p></div>;

  if (!queue.length || finished) {
    const f = finished;
    return (
      <div className="page">
        <div className="panel stack review-done">
          <RotateCcw size={36} aria-hidden="true" className="trophy" />
          <h1>{f ? 'Review complete' : 'Nothing due right now'}</h1>
          {f ? (
            <div className="review-stats">
              <div><span className="today-num num">{Math.round((f.right / Math.max(1, f.answered)) * 100)}%</span><span className="hint">accuracy</span></div>
              <div><span className="today-num num">+{f.xp}</span><span className="hint">XP</span></div>
              <div><span className="today-num num">{f.mastered}</span><span className="hint">mastered</span></div>
            </div>
          ) : (
            <p className="hint">Questions you miss in quizzes come back here after 1, 3, 7, 14 and 30 days until you know them.</p>
          )}
          <div className="btn-row"><button type="button" className="btn btn-primary" onClick={onDone}>Back to My courses</button></div>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="review-top">
        <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label="End review" onClick={onDone}><X size={16} /></button>
        <div className="meter review-meter" aria-label={`Question ${i + 1} of ${queue.length}`}><span style={{ width: `${(i / queue.length) * 100}%` }} /></div>
        {combo >= 2 && <span className="combo"><Flame size={15} aria-hidden="true" /> {combo} in a row</span>}
      </div>

      <div className="panel stack">
        <p className="hint">{q.retry ? 'One more try · ' : ''}From {q.topicTitle}</p>
        <div className="question"><Md>{q.question}</Md></div>
        <div className="choices" role="radiogroup">
          {q.options.map((opt, k) => {
            const state = result ? (k === result.correctAnswer ? 'correct' : k === pick ? 'wrong' : undefined) : undefined;
            return (
              <button key={k} type="button" className="choice" role="radio" aria-checked={pick === k} aria-pressed={pick === k}
                data-result={state} disabled={Boolean(result)} onClick={() => setPick(k)}>
                <span className="key">{LETTERS[k]}</span><span><MdInline>{opt}</MdInline></span>
                <span>{state === 'correct' ? <Check size={16} /> : state === 'wrong' ? <X size={16} /> : null}</span>
              </button>
            );
          })}
        </div>
        {result && (
          <div className={`feedback ${result.correct ? 'ok' : 'bad'}`} aria-live="polite">
            <p style={{ fontWeight: 700, marginBottom: 4 }}>
              {result.retry ? (result.correct ? 'Got it this time. It still comes back tomorrow to make it stick.' : 'Not yet. It comes back tomorrow.')
                : result.correct ? (result.mastered ? 'Correct, and mastered: it leaves your review queue.' : 'Correct.')
                : 'Not quite. It will come back at the end, and again tomorrow.'}
            </p>
            {result.explanation && <Md>{result.explanation}</Md>}
          </div>
        )}
        <div className="btn-row">
          {!result ? (
            <button type="button" className="btn btn-primary" disabled={pick === null || busy} onClick={check}>
              {busy ? <Loader2 size={14} className="spin" /> : null} Check
            </button>
          ) : (
            <button type="button" className="btn btn-primary" onClick={next}>
              {i + 1 < queue.length ? 'Continue' : 'Finish'} <ArrowRight size={14} aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
