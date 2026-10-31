import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { 
  CheckCircle2, XCircle, HelpCircle, ArrowRight, RotateCcw, 
  Award, Lightbulb, Sparkles, AlertCircle, Check 
} from 'lucide-react';
import { theme } from '../theme';

export default function QuizEngine({ quiz = [], topicId, onQuizComplete }) {
  const [currentIdx, setCurrentIdx] = useState(0);
  const [selectedOption, setSelectedOption] = useState(null);
  const [isAnswered, setIsAnswered] = useState(false);
  const [showHint, setShowHint] = useState(false);
  const [userAnswers, setUserAnswers] = useState({});
  const [isCompleted, setIsCompleted] = useState(false);

  if (!quiz || quiz.length === 0) {
    return (
      <div style={{
        background: theme.bgPanel,
        border: `1px solid ${theme.border}`,
        borderRadius: 8,
        padding: 32,
        textAlign: 'center',
        color: theme.textMuted,
        fontFamily: theme.fontMono
      }}>
        <AlertCircle size={32} style={{ margin: '0 auto 12px', color: theme.accentGold }} />
        <p>No assessment questions loaded for this topic yet.</p>
        <p style={{ fontSize: '0.8rem', color: theme.textDim, marginTop: 6 }}>
          Agents can dynamically inject quiz questions via <code>POST /api/topics/{topicId}</code>.
        </p>
      </div>
    );
  }

  const currentQ = quiz[currentIdx];

  const handleSelect = (idx) => {
    if (isAnswered) return;
    setSelectedOption(idx);
  };

  const handleSubmitAnswer = () => {
    if (selectedOption === null) return;
    setIsAnswered(true);
    const isCorrect = selectedOption === currentQ.correctAnswer;
    const newAnswers = {
      ...userAnswers,
      [currentIdx]: {
        selected: selectedOption,
        correct: isCorrect
      }
    };
    setUserAnswers(newAnswers);

    // Save progress to API if available
    try {
      fetch('/api/quiz/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topicId,
          questionId: currentQ.id || currentIdx,
          selected: selectedOption,
          isCorrect
        })
      }).catch(() => {});
    } catch (e) {}
  };

  const handleNext = () => {
    if (currentIdx < quiz.length - 1) {
      setCurrentIdx(currentIdx + 1);
      setSelectedOption(null);
      setIsAnswered(false);
      setShowHint(false);
    } else {
      setIsCompleted(true);
      if (onQuizComplete) {
        onQuizComplete(userAnswers);
      }
    }
  };

  const handleRestart = () => {
    setCurrentIdx(0);
    setSelectedOption(null);
    setIsAnswered(false);
    setShowHint(false);
    setUserAnswers({});
    setIsCompleted(false);
  };

  // Completion screen
  if (isCompleted) {
    const totalQuestions = quiz.length;
    const correctCount = Object.values(userAnswers).filter(a => a.correct).length;
    const scorePct = Math.round((correctCount / totalQuestions) * 100);

    return (
      <div style={{
        background: theme.bgPanel,
        border: `1px solid ${theme.border}`,
        borderRadius: 8,
        padding: 32,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 20
      }}>
        <div style={{
          width: 64,
          height: 64,
          borderRadius: '50%',
          background: scorePct >= 80 ? 'rgba(35, 165, 90, 0.2)' : 'rgba(229, 184, 92, 0.2)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: scorePct >= 80 ? theme.accentGreen : theme.accentGold
        }}>
          <Award size={36} />
        </div>

        <h2 style={{ fontFamily: theme.fontMono, color: theme.textMain, fontSize: '1.4rem' }}>
          Assessment Complete!
        </h2>

        <div style={{
          fontSize: '2.5rem',
          fontWeight: 800,
          fontFamily: theme.fontMono,
          color: scorePct >= 80 ? theme.accentGreen : scorePct >= 60 ? theme.accentGold : theme.accentPink
        }}>
          {scorePct}%
        </div>

        <p style={{ color: theme.textDim, fontSize: '0.95rem' }}>
          You answered <strong>{correctCount}</strong> out of <strong>{totalQuestions}</strong> questions correctly.
        </p>

        <div style={{
          background: theme.bgCard,
          border: `1px solid ${theme.border}`,
          borderRadius: 6,
          padding: 16,
          width: '100%',
          maxWidth: 480,
          fontSize: '0.85rem'
        }}>
          <div style={{ color: theme.accentGold, fontWeight: 700, marginBottom: 8, fontFamily: theme.fontMono }}>
            📊 Mastery Assessment:
          </div>
          <div style={{ color: theme.textMain }}>
            {scorePct === 100 && "Flawless mastery of rolling dynamics and constraint kinematics!"}
            {scorePct >= 80 && scorePct < 100 && "Strong analytical comprehension! You understand the velocity distribution and energy partition."}
            {scorePct >= 50 && scorePct < 80 && "Good foundation. Review instantaneous velocity at the contact point and rotational inertia factors."}
            {scorePct < 50 && "Recommended: review the interactive simulation with vector arrows toggled ON."}
          </div>
        </div>

        <button
          onClick={handleRestart}
          style={{
            background: 'rgba(35, 165, 90, 0.2)',
            border: `1px solid ${theme.accentGreen}`,
            color: theme.accentGreen,
            borderRadius: 6,
            padding: '10px 24px',
            fontFamily: theme.fontMono,
            fontSize: '0.88rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginTop: 8
          }}
        >
          <RotateCcw size={16} /> Retake Assessment
        </button>
      </div>
    );
  }

  const isCurrentCorrect = isAnswered && selectedOption === currentQ.correctAnswer;

  return (
    <div style={{
      background: theme.bgPanel,
      border: `1px solid ${theme.border}`,
      borderRadius: 8,
      padding: 24,
      display: 'flex',
      flexDirection: 'column',
      gap: 20
    }}>
      {/* Quiz Header & Progress */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: `1px solid ${theme.border}`, paddingBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{
            background: 'rgba(229, 184, 92, 0.15)',
            color: theme.accentGold,
            border: `1px solid rgba(229, 184, 92, 0.35)`,
            borderRadius: 4,
            padding: '3px 8px',
            fontSize: '0.74rem',
            fontFamily: theme.fontMono,
            fontWeight: 700
          }}>
            QUESTION {currentIdx + 1} OF {quiz.length}
          </span>
          <span style={{ fontSize: '0.82rem', color: theme.textMuted, fontFamily: theme.fontMono }}>
            {currentQ.difficulty || 'Conceptual Check'}
          </span>
        </div>

        {/* Progress Bar */}
        <div style={{ width: 140, height: 6, background: '#121212', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{
            width: `${((currentIdx + 1) / quiz.length) * 100}%`,
            height: '100%',
            background: theme.accentGreen,
            transition: 'width 0.3s ease'
          }} />
        </div>
      </div>

      {/* Question Text with KaTeX */}
      <div style={{ fontSize: '1.05rem', color: theme.textMain, lineHeight: 1.6 }}>
        <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
          {currentQ.question}
        </ReactMarkdown>
      </div>

      {/* Options List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {currentQ.options.map((opt, oIdx) => {
          let optBorder = theme.border;
          let optBg = theme.bgCard;
          let optColor = theme.textMain;

          if (isAnswered) {
            if (oIdx === currentQ.correctAnswer) {
              optBorder = theme.accentGreen;
              optBg = 'rgba(35, 165, 90, 0.15)';
              optColor = theme.accentGreen;
            } else if (selectedOption === oIdx) {
              optBorder = theme.accentPink;
              optBg = 'rgba(249, 38, 114, 0.15)';
              optColor = theme.accentPink;
            }
          } else if (selectedOption === oIdx) {
            optBorder = theme.accentGold;
            optBg = 'rgba(229, 184, 92, 0.12)';
          }

          return (
            <button
              key={oIdx}
              onClick={() => handleSelect(oIdx)}
              disabled={isAnswered}
              style={{
                background: optBg,
                border: `1px solid ${optBorder}`,
                borderRadius: 6,
                padding: '12px 16px',
                textAlign: 'left',
                color: optColor,
                cursor: isAnswered ? 'default' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                transition: 'border-color 0.2s, background 0.2s',
                fontFamily: 'inherit',
                fontSize: '0.92rem'
              }}
            >
              <span style={{
                width: 24,
                height: 24,
                borderRadius: '50%',
                background: isAnswered && oIdx === currentQ.correctAnswer 
                  ? theme.accentGreen 
                  : selectedOption === oIdx 
                    ? theme.accentGold 
                    : '#141414',
                color: isAnswered && oIdx === currentQ.correctAnswer || selectedOption === oIdx ? '#000' : theme.textDim,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.78rem',
                fontFamily: theme.fontMono,
                fontWeight: 700,
                flexShrink: 0
              }}>
                {String.fromCharCode(65 + oIdx)}
              </span>
              <div style={{ flex: 1 }}>
                <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                  {opt}
                </ReactMarkdown>
              </div>
            </button>
          );
        })}
      </div>

      {/* Answer feedback and derivation */}
      {isAnswered && (
        <div style={{
          background: isCurrentCorrect ? 'rgba(35, 165, 90, 0.08)' : 'rgba(249, 38, 114, 0.08)',
          border: `1px solid ${isCurrentCorrect ? 'rgba(35, 165, 90, 0.4)' : 'rgba(249, 38, 114, 0.4)'}`,
          borderRadius: 6,
          padding: 16,
          display: 'flex',
          flexDirection: 'column',
          gap: 10
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, color: isCurrentCorrect ? theme.accentGreen : theme.accentPink, fontFamily: theme.fontMono }}>
            {isCurrentCorrect ? <CheckCircle2 size={18} /> : <XCircle size={18} />}
            <span>{isCurrentCorrect ? 'CORRECT!' : 'INCORRECT'}</span>
          </div>

          <div style={{ fontSize: '0.88rem', color: theme.textMain, lineHeight: 1.65 }}>
            <div style={{ color: theme.accentGold, fontWeight: 600, fontSize: '0.78rem', fontFamily: theme.fontMono, marginBottom: 4 }}>
              PHYSICAL DERIVATION & EXPLANATION:
            </div>
            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
              {currentQ.explanation}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {/* Hint toggle */}
      {!isAnswered && currentQ.hint && (
        <div>
          <button
            onClick={() => setShowHint(!showHint)}
            style={{
              background: 'transparent',
              border: 'none',
              color: theme.accentGold,
              fontSize: '0.82rem',
              fontFamily: theme.fontMono,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            <Lightbulb size={14} /> {showHint ? 'Hide Hint' : 'Need a Hint?'}
          </button>
          {showHint && (
            <div style={{
              background: 'rgba(229, 184, 92, 0.08)',
              border: `1px solid rgba(229, 184, 92, 0.25)`,
              borderRadius: 6,
              padding: 12,
              marginTop: 8,
              fontSize: '0.84rem',
              color: theme.textDim
            }}>
              <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                {currentQ.hint}
              </ReactMarkdown>
            </div>
          )}
        </div>
      )}

      {/* Action Footer */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, borderTop: `1px solid ${theme.border}`, paddingTop: 14 }}>
        {!isAnswered ? (
          <button
            onClick={handleSubmitAnswer}
            disabled={selectedOption === null}
            style={{
              background: selectedOption === null ? '#1e1e1e' : theme.accentGreen,
              color: selectedOption === null ? theme.textMuted : '#000000',
              fontWeight: 700,
              border: 'none',
              borderRadius: 4,
              padding: '8px 20px',
              fontFamily: theme.fontMono,
              fontSize: '0.84rem',
              cursor: selectedOption === null ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            Check Answer
          </button>
        ) : (
          <button
            onClick={handleNext}
            style={{
              background: theme.accentGold,
              color: '#000000',
              fontWeight: 700,
              border: 'none',
              borderRadius: 4,
              padding: '8px 20px',
              fontFamily: theme.fontMono,
              fontSize: '0.84rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6
            }}
          >
            {currentIdx < quiz.length - 1 ? 'Next Question' : 'Complete Assessment'} <ArrowRight size={14} />
          </button>
        )}
      </div>
    </div>
  );
}
