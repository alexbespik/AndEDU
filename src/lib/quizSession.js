// A quiz-like session (class quiz, speed round, IDE test run) reports its start, its result and an unfinished exit.
// Listeners (Commissar mode) only hear the phase and the score; never questions or answers.
export const WIN_PCT = 80;  // the same bar QuizEngine's result text uses

/** phase: 'start' | 'finish' (with pct 0-100) | 'leave' (left before the end, after at least one answer). */
export function quizSession(phase, pct) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent('andedu:quiz-session', { detail: { phase, pct } }));
}
