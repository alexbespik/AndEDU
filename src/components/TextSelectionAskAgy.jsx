import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Sparkles, X, Send } from 'lucide-react';

const EXPLANATION_LEVELS = [
  { level: 0, title: 'ELI5' },
  { level: 1, title: 'Beginner' },
  { level: 2, title: 'College' },
  { level: 3, title: 'Advanced' },
  { level: 4, title: 'Grad' },
  { level: 5, title: 'Expert' },
];

/**
 * Wraps text/notes content, monitors text selections within it, freezes the selection coordinates,
 * and displays a floating [Ask AGY] trigger followed by an explanation-level popover.
 */
export default function TextSelectionAskAgy({ children, topicId, courseId }) {
  const containerRef = useRef(null);
  const buttonRef = useRef(null);
  const popoverRef = useRef(null);
  const [selection, setSelection] = useState(null);
  const [isPopoverOpen, setIsPopoverOpen] = useState(false);
  const [selectedLevel, setSelectedLevel] = useState(2);
  const [question, setQuestion] = useState('');
  const isPopoverOpenRef = useRef(isPopoverOpen);
  isPopoverOpenRef.current = isPopoverOpen;

  const handleSelectionChange = useCallback(() => {
    if (isPopoverOpenRef.current) return;
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount) {
      setSelection(null);
      return;
    }
    const text = sel.toString().trim();
    if (text.length < 2) {
      setSelection(null);
      return;
    }
    const anchor = sel.anchorNode;
    const focus = sel.focusNode;
    if (containerRef.current && containerRef.current.contains(anchor) && containerRef.current.contains(focus)) {
      const range = sel.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        setSelection({
          text,
          top: rect.top,
          left: rect.left,
          bottom: rect.bottom,
          right: rect.right,
          width: rect.width,
        });
      }
    } else {
      setSelection(null);
    }
  }, []);

  useEffect(() => {
    document.addEventListener('selectionchange', handleSelectionChange);
    return () => document.removeEventListener('selectionchange', handleSelectionChange);
  }, [handleSelectionChange]);

  useEffect(() => {
    if (!isPopoverOpen && !selection) return undefined;
    const handleOutside = (e) => {
      if (popoverRef.current && popoverRef.current.contains(e.target)) return;
      if (buttonRef.current && buttonRef.current.contains(e.target)) return;
      setIsPopoverOpen(false);
      setSelection(null);
    };
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, [isPopoverOpen, selection]);

  useEffect(() => {
    if (!isPopoverOpen) return undefined;
    const onKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();  // Esc closes this popover only, not the walkthrough under it
        setIsPopoverOpen(false);
        setSelection(null);
      }
    };
    // capture phase: runs before the walkthrough's own window keydown listener, which skips prevented events
    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [isPopoverOpen]);

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!selection?.text) return;
    const lvl = EXPLANATION_LEVELS.find((l) => l.level === selectedLevel) || EXPLANATION_LEVELS[2];
    const qPart = question.trim() ? `${question.trim()}\n\n` : '';
    const formattedPrompt = `[Explanation Level ${lvl.level}: ${lvl.title}]\n${qPart}Regarding this excerpt from the lesson:\n> ${selection.text}\n\nCould you explain this?`;
    window.dispatchEvent(
      new CustomEvent('agy:ask', {
        detail: {
          prompt: formattedPrompt,
          topicId,
          courseId,
          level: lvl.level,
        },
      })
    );
    setIsPopoverOpen(false);
    setSelection(null);
    setQuestion('');
    window.getSelection()?.removeAllRanges();
  };

  // Compute position for floating elements with clamp
  const btnTop = selection ? Math.max(12, selection.top - 40) : 0;
  const btnLeft = selection ? Math.max(12, Math.min(window.innerWidth - 130, selection.left + selection.width / 2 - 50)) : 0;
  const popoverTop = selection ? Math.max(12, Math.min(window.innerHeight - 320, selection.bottom + 8)) : 0;
  const popoverLeft = selection ? Math.max(12, Math.min(window.innerWidth - 340, selection.left + selection.width / 2 - 160)) : 0;

  return (
    <div ref={containerRef} className="selection-ask-container">
      {children}

      {selection && !isPopoverOpen && (
        <button
          ref={buttonRef}
          type="button"
          className="selection-ask-btn btn btn-gold btn-sm"
          style={{ top: `${btnTop}px`, left: `${btnLeft}px` }}
          onMouseDown={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setIsPopoverOpen(true);
          }}
          aria-label="Ask AGY about selected text"
        >
          <Sparkles size={14} aria-hidden="true" />
          <span>Ask AGY</span>
        </button>
      )}

      {selection && isPopoverOpen && (
        <div
          ref={popoverRef}
          className="selection-ask-popover panel stack-sm"
          style={{ top: `${popoverTop}px`, left: `${popoverLeft}px` }}
          onMouseDown={(e) => e.stopPropagation()}
        >
          <div className="selection-popover-head">
            <span className="selection-popover-title">
              <Sparkles size={14} aria-hidden="true" /> Ask AGY
            </span>
            <button
              type="button"
              className="btn btn-quiet btn-sm btn-icon"
              style={{ minHeight: 22, width: 22, border: 0 }}
              onClick={() => {
                setIsPopoverOpen(false);
                setSelection(null);
              }}
              aria-label="Close"
            >
              <X size={14} />
            </button>
          </div>

          <blockquote className="selection-preview">
            &ldquo;{selection.text.length > 140 ? `${selection.text.slice(0, 140)}…` : selection.text}&rdquo;
          </blockquote>

          <div className="level-pills" role="radiogroup" aria-label="Explanation level">
            <span className="level-label">Depth:</span>
            {EXPLANATION_LEVELS.map(({ level, title }) => (
              <button
                key={level}
                type="button"
                className={`level-pill${selectedLevel === level ? ' level-pill-active' : ''}`}
                role="radio"
                aria-checked={selectedLevel === level}
                onClick={() => setSelectedLevel(level)}
              >
                {level}: {title}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="selection-ask-form">
            <input
              type="text"
              className="input input-sm"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a specific question (optional)…"
              autoFocus
            />
            <button type="submit" className="btn btn-primary btn-sm btn-icon" aria-label="Submit question">
              <Send size={14} />
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
