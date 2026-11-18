import { useEffect, useRef } from 'react';
import { say } from './commissar';
import { localDay } from './api';
import { WIN_PCT } from './quizSession';

const RISK_KEY = 'andedu_commissar_risk_day';
const REVIEW_KEY = 'andedu_commissar_review_day';

function saidToday(key) {
  try { return localStorage.getItem(key) === localDay(); } catch { return false; }
}

/** Says `event` at most once per local day: the day is used up only when the line was actually spoken. */
function sayOncePerDay(key, event) {
  if (saidToday(key) || !say(event)) return;
  try { localStorage.setItem(key, localDay()); } catch { /* storage blocked: the throttle still limits it */ }
}

/** Fixed Commissar lines for app events: workspace changes, rewards, quiz answers, quiz start / result / walking out,
 * streak risk, review due.
 * Focus mode (no streaks, XP or celebrations) silences everything but workspace changes and quizzes. */
export function useCommissarEvents({ mode, progress }) {
  const prevMode = useRef(mode);
  useEffect(() => {
    if (prevMode.current === mode) return;  // also skips StrictMode's second mount run
    prevMode.current = mode;
    say('tab');
  }, [mode]);

  const focus = Boolean(progress?.focusMode);
  const focusRef = useRef(focus);
  focusRef.current = focus;
  useEffect(() => {
    const onReward = (e) => { if (!focusRef.current) say(e.detail?.streakExtended ? 'streak' : 'reward'); };
    const onQuiz = (e) => say(e.detail?.correct ? 'quizPass' : 'quizFail');
    const onSession = (e) => {
      const { phase, pct } = e.detail || {};
      if (phase === 'start') say('quizStart');
      else if (phase === 'leave') say('desert');
      else if (phase === 'finish') say(Number(pct) >= WIN_PCT ? 'quizWin' : 'quizLose');
    };
    window.addEventListener('andedu:reward', onReward);
    window.addEventListener('andedu:quiz', onQuiz);
    window.addEventListener('andedu:quiz-session', onSession);
    return () => {
      window.removeEventListener('andedu:reward', onReward);
      window.removeEventListener('andedu:quiz', onQuiz);
      window.removeEventListener('andedu:quiz-session', onSession);
    };
  }, []);

  const streak = progress?.streak, done = progress?.doneToday, due = progress?.reviewDue;
  useEffect(() => {
    if (focus || streak == null) return;
    if (streak > 0 && !done && new Date().getHours() >= 18) sayOncePerDay(RISK_KEY, 'streakRisk');
  }, [streak, done, focus]);
  useEffect(() => {
    if (!focus && mode === 'home' && due > 0) sayOncePerDay(REVIEW_KEY, 'reviewDue');
  }, [mode, due, focus]);
}
