import React, { useState } from 'react';
import { CheckCircle2, XCircle, Lightbulb, ArrowRight, RotateCcw, Flame } from 'lucide-react';
import Md, { MdInline } from './Md';
import { api } from '../lib/api';
import { emitRewards } from '../lib/engage';

/** Older agy topics stored the answer as `correct`; the documented key is `correctAnswer`. */
export function answerIndex(q) {
  const v = q?.correctAnswer ?? q?.correct;
  const n = typeof v === 'string' && /^\d+$/.test(v) ? Number(v) : v;
  return Number.isInteger(n) && n >= 0 && n < (q?.options?.length || 0) ? n : null;
}

const LETTERS = 'ABCDEFGH';

const CHECK_TEXT = {
  verified: 'Answer key verified by a second model',
  corrected: 'Answer key corrected by a second model',
  ambiguous: 'Flagged as unclear by a second model',
  wrong: 'Flagged by a second model',
  'low-confidence': 'Low confidence from the second model',
};

/** Shows the reviewer model's verdict + certainty, so students can judge how reliable a question is. */
export function CheckBadge({ check }) {
  if (!check?.verdict) return null;
  const pct = typeof check.confidence === 'number' ? ` (${Math.round(check.confidence * 100)}% sure)` : '';
  const sources = (check.sources || []).filter((src) => /^https?:\/\//.test(src.uri || ''));
  return (
    <span className="check" data-verdict={check.verdict} title={check.note || undefined}>
      {CHECK_TEXT[check.verdict] || check.verdict}{pct}
      {sources.length > 0 && (
        <>
          , checked against{' '}
          {sources.map((src, i) => (
            <React.Fragment key={src.uri}>
              {i > 0 && ', '}
              <a href={src.uri} target="_blank" rel="noopener noreferrer">{src.title}</a>
            </React.Fragment>
          ))}
        </>
      )}
    </span>
  );
}

/**
 * Graded multiple-choice quiz. Parent passes key={topic.id} so state resets per topic.
 * `onAnswer` is optional; by default answers are recorded through /api/quiz/submit.
 */
export default function QuizEngine({ quiz = [], topicId, userId, onAnswer, onAskTutor, title = 'Quiz' }) {
  const questions = quiz.filter((q) => q && q.question && answerIndex(q) !== null);
  const [idx, setIdx] = useState(0);
  const [selected, setSelected] = useState(null);
  const [answered, setAnswered] = useState(false);
  const [showHint, setShowHint] = useState(false);
  const [results, setResults] = useState({});
  const [done, setDone] = useState(false);
  const [combo, setCombo] = useState(0);

  if (questions.length === 0) {
    return (
      <div className="panel">
        <p>This topic has no quiz questions yet.</p>
        <p className="hint" style={{ marginTop: 8 }}>Ask AGY to write some, or add them through <code>POST /api/topics</code>.</p>
      </div>
    );
  }

  const q = questions[Math.min(idx, questions.length - 1)];
  const correct = answerIndex(q);

  const submit = () => {
    if (selected === null) return;
    const isCorrect = selected === correct;
    setAnswered(true);
    setResults((r) => ({ ...r, [idx]: isCorrect }));
    setCombo((c) => (isCorrect ? c + 1 : 0));
    const record = { userId, topicId, questionId: q.id ?? idx, selected, isCorrect };
    if (onAnswer) onAnswer(record);
    else api('/api/quiz/submit', { method: 'POST', body: record }).then((r) => emitRewards(r?.rewards)).catch(() => {});
  };

  const next = () => {
    if (idx < questions.length - 1) {
      setIdx(idx + 1);
      setSelected(null);
      setAnswered(false);
      setShowHint(false);
    } else {
      setDone(true);
    }
  };

  const restart = () => {
    setIdx(0); setSelected(null); setAnswered(false); setShowHint(false); setResults({}); setDone(false);
  };

  if (done) {
    const right = Object.values(results).filter(Boolean).length;
    const pct = Math.round((right / questions.length) * 100);
    return (
      <section className="panel stack" aria-live="polite">
        <h2>{title} complete</h2>
        <p className="score num">{pct}%</p>
        <p>{right} of {questions.length} correct. {pct >= 80 ? 'Solid. Move on to the next class.' : 'Review the explanations, then try it again.'}</p>
        <div className="btn-row">
          <button type="button" className="btn btn-secondary" onClick={restart}><RotateCcw size={16} aria-hidden="true" /> Retake</button>
        </div>
      </section>
    );
  }

  return (
    <section className="panel stack" aria-labelledby="quiz-q">
      <div className="quiz-progress">
        <span>Question {idx + 1} of {questions.length}{q.difficulty ? `, ${q.difficulty}` : ''}</span>
        {combo >= 2 && <span className="combo" role="status"><Flame size={15} aria-hidden="true" /> {combo} in a row</span>}
        <div className="meter" style={{ width: 160 }} aria-hidden="true">
          <span style={{ width: `${((idx + (answered ? 1 : 0)) / questions.length) * 100}%` }} />
        </div>
      </div>

      <div id="quiz-q" className="question"><Md>{q.question}</Md></div>
      <CheckBadge check={q.check} />

      <div className="choices" role="group" aria-label="Answer options">
        {q.options.map((opt, i) => {
          const result = answered ? (i === correct ? 'correct' : i === selected ? 'wrong' : undefined) : undefined;
          return (
            <button
              key={i}
              type="button"
              className="choice"
              aria-pressed={selected === i}
              data-result={result}
              disabled={answered}
              onClick={() => setSelected(i)}
            >
              <span className="key">{LETTERS[i]}</span>
              <span><MdInline>{opt}</MdInline></span>
              {result === 'correct' && <CheckCircle2 size={18} color="var(--ok)" aria-label="Correct answer" />}
              {result === 'wrong' && <XCircle size={18} color="var(--bad)" aria-label="Your answer" />}
            </button>
          );
        })}
      </div>

      {showHint && q.hint && !answered && (
        <div className="feedback"><Md>{q.hint}</Md></div>
      )}

      {answered && (
        <div className={`feedback ${selected === correct ? 'ok' : 'bad'}`} aria-live="polite">
          <p style={{ fontWeight: 700, marginBottom: 4 }}>{selected === correct ? 'Correct.' : `Not quite. The answer is ${LETTERS[correct]}.`}</p>
          {q.explanation && <Md>{q.explanation}</Md>}
        </div>
      )}

      <div className="btn-row">
        {!answered ? (
          <>
            <button type="button" className="btn btn-primary" onClick={submit} disabled={selected === null}>Check answer</button>
            {q.hint && (
              <button type="button" className="btn btn-quiet" onClick={() => setShowHint((s) => !s)} aria-expanded={showHint}>
                <Lightbulb size={16} aria-hidden="true" /> {showHint ? 'Hide hint' : 'Hint'}
              </button>
            )}
          </>
        ) : (
          <>
            <button type="button" className="btn btn-primary" onClick={next}>
              {idx < questions.length - 1 ? 'Next question' : 'See results'} <ArrowRight size={16} aria-hidden="true" />
            </button>
            {onAskTutor && selected !== correct && (
              <button type="button" className="btn btn-quiet"
                onClick={() => onAskTutor({ question: q.question, options: q.options, selected, correctAnswer: correct })}>
                Talk it through with the tutor
              </button>
            )}
          </>
        )}
      </div>
    </section>
  );
}
