import React, { useEffect, useState } from 'react';
import { Sparkles, X, Loader2, RotateCcw, Lightbulb, CheckCircle2 } from 'lucide-react';
import Md from './Md';
import { api } from '../lib/api';

/**
 * AI "Explain My Answer" modal dialog.
 * Calls /api/tutor/explain-answer and presents verdict, explanation, key rule, and example.
 */
export function ExplainAnswerModal({
  open,
  onClose,
  question = '',
  studentAnswer = '',
  correctAnswer = '',
  context = '',
  lang = '',
}) {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const fetchExplanation = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api('/api/tutor/explain-answer', {
        method: 'POST',
        body: {
          question: String(question || ''),
          student_answer: String(studentAnswer || ''),
          correct_answer: String(correctAnswer || ''),
          context: String(context || ''),
          lang: String(lang || ''),
        },
      });
      setData(res);
    } catch (err) {
      setError(err.message || 'Could not load explanation. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open) {
      setData(null);
      setError(null);
      return undefined;
    }
    let active = true;
    setLoading(true);
    setError(null);

    api('/api/tutor/explain-answer', {
      method: 'POST',
      body: {
        question: String(question || ''),
        student_answer: String(studentAnswer || ''),
        correct_answer: String(correctAnswer || ''),
        context: String(context || ''),
        lang: String(lang || ''),
      },
    })
      .then((res) => {
        if (active) setData(res);
      })
      .catch((err) => {
        if (active) setError(err.message || 'Could not load explanation. Please try again.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    const handleKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => {
      active = false;
      window.removeEventListener('keydown', handleKey);
    };
  }, [open, question, studentAnswer, correctAnswer, context, lang]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="explain-title"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'var(--scrim)',
        zIndex: 100,
        display: 'grid',
        placeItems: 'center',
        padding: 'var(--space-4)',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="panel"
        style={{
          maxWidth: '560px',
          width: '100%',
          maxHeight: '90vh',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-4)',
          position: 'relative',
          boxShadow: 'var(--shadow-raised)',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 'var(--space-3)',
            borderBottom: '1px solid var(--rule)',
            paddingBottom: 'var(--space-3)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <Sparkles size={18} style={{ color: 'var(--gold-text)' }} aria-hidden="true" />
            <h3 id="explain-title" style={{ margin: 0, fontSize: '1.15rem' }}>
              Explain My Answer
            </h3>
          </div>
          <button
            type="button"
            className="btn btn-quiet btn-sm btn-icon"
            onClick={onClose}
            aria-label="Close explanation"
          >
            <X size={16} />
          </button>
        </div>

        {/* Answer comparison */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 'var(--space-3)',
            padding: 'var(--space-3)',
            background: 'var(--sunk)',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--rule)',
          }}
        >
          <div>
            <span className="hint" style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Your Answer
            </span>
            <div style={{ fontWeight: 600, color: 'var(--bad)', marginTop: 2, wordBreak: 'break-word' }}>
              {studentAnswer || <span className="hint">(No answer given)</span>}
            </div>
          </div>
          <div>
            <span className="hint" style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Expected Answer
            </span>
            <div style={{ fontWeight: 600, color: 'var(--ok)', marginTop: 2, wordBreak: 'break-word' }}>
              {correctAnswer || <span className="hint">—</span>}
            </div>
          </div>
        </div>

        {/* Body content */}
        {loading && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 'var(--space-3)',
              padding: 'var(--space-6) 0',
              color: 'var(--muted)',
            }}
          >
            <Loader2 size={20} className="spin" aria-hidden="true" />
            <span>Analyzing your response…</span>
          </div>
        )}

        {error && (
          <div className="stack-sm">
            <p className="notice notice-bad">{error}</p>
            <div className="btn-row">
              <button type="button" className="btn btn-quiet btn-sm" onClick={fetchExplanation}>
                <RotateCcw size={14} aria-hidden="true" /> Try again
              </button>
            </div>
          </div>
        )}

        {data && !loading && (
          <div className="stack-sm">
            {/* Verdict */}
            {data.verdict && (
              <div
                style={{
                  background: 'var(--accent-tint)',
                  borderLeft: '4px solid var(--accent)',
                  padding: 'var(--space-2) var(--space-3)',
                  borderRadius: 'var(--radius-sm)',
                  fontWeight: 600,
                  fontSize: '0.95rem',
                }}
              >
                {data.verdict}
              </div>
            )}

            {/* Explanation */}
            {data.explanation && (
              <div style={{ lineHeight: 1.6, fontSize: '0.95rem' }}>
                <Md>{data.explanation}</Md>
              </div>
            )}

            {/* Key rule */}
            {data.key_rule && (
              <div
                style={{
                  background: 'var(--sunk)',
                  border: '1px solid var(--rule)',
                  borderRadius: 'var(--radius-sm)',
                  padding: 'var(--space-3)',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-2)',
                    color: 'var(--gold-text)',
                    fontWeight: 700,
                    fontSize: '0.82rem',
                    marginBottom: 4,
                  }}
                >
                  <Lightbulb size={14} aria-hidden="true" /> Key Rule
                </div>
                <div style={{ fontSize: '0.9rem' }}>{data.key_rule}</div>
              </div>
            )}

            {/* Example */}
            {data.example && (
              <div
                style={{
                  background: 'var(--sunk)',
                  border: '1px solid var(--rule)',
                  borderRadius: 'var(--radius-sm)',
                  padding: 'var(--space-3)',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-2)',
                    color: 'var(--ok)',
                    fontWeight: 700,
                    fontSize: '0.82rem',
                    marginBottom: 4,
                  }}
                >
                  <CheckCircle2 size={14} aria-hidden="true" /> Example in Context
                </div>
                <div style={{ fontSize: '0.9rem', fontStyle: 'italic' }}>{data.example}</div>
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            paddingTop: 'var(--space-2)',
            borderTop: '1px solid var(--rule)',
          }}
        >
          <button type="button" className="btn btn-primary btn-sm" onClick={onClose}>
            Got it
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Reusable button that triggers the ExplainAnswerModal.
 */
export function ExplainAnswerButton({
  item,
  studentAnswer = '',
  correctAnswer = '',
  question = '',
  context = '',
  lang = '',
}) {
  const [open, setOpen] = useState(false);

  const q = question || item?.prompt || item?.source || item?.front || item?.audio_text || item?.target || '';
  const a = correctAnswer || item?.answer || item?.target || '';
  const c = context || item?.source || item?.translation || item?.summary || '';
  const l = lang || item?.lang || '';

  return (
    <>
      <button
        type="button"
        className="btn btn-quiet btn-sm"
        onClick={() => setOpen(true)}
        aria-label="Explain my answer"
      >
        <Sparkles size={14} style={{ color: 'var(--gold-text)' }} aria-hidden="true" />
        <span>Explain my answer</span>
      </button>
      <ExplainAnswerModal
        open={open}
        onClose={() => setOpen(false)}
        question={q}
        studentAnswer={studentAnswer}
        correctAnswer={a}
        context={c}
        lang={l}
      />
    </>
  );
}
