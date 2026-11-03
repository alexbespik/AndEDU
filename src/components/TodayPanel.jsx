import React from 'react';
import { Flame, Snowflake, Play, RotateCcw, Check, Award, Lock, Trophy } from 'lucide-react';
import { GoalRing } from './Rewards';
import { api } from '../lib/api';

const GOAL_NAMES = { 10: 'Casual', 20: 'Regular', 30: 'Serious', 50: 'Intense' };
const DOW = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

function formatDay(iso) {
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}

/** My courses "Today": streak, daily goal, level, quests, what to do next, review queue and badges. */
export default function TodayPanel({ userId, progress, onChange, onContinue, onReview }) {
  if (!progress) return null;
  const p = progress;
  const setPrefs = (body) => api(`/api/engage/${userId}/prefs`, { method: 'POST', body }).then(onChange).catch(() => {});
  const atRisk = p.streak > 0 && !p.doneToday && new Date().getHours() >= 18;
  const levelPct = Math.round(((p.totalXp - p.levelStart) / Math.max(1, p.nextLevel - p.levelStart)) * 100);
  const earned = p.badges.filter((b) => b.earned).length;

  const next = (
    <div className="today-next">
      {p.continue ? (
        <button type="button" className="next-card" onClick={() => onContinue(p.continue.topic_id)}>
          <span className="next-icon"><Play size={18} aria-hidden="true" /></span>
          <span className="stack-sm">
            <span className="hint">Continue · {p.continue.course_title}</span>
            <strong>Class {p.continue.seq}: {p.continue.title}</strong>
          </span>
        </button>
      ) : (
        <div className="next-card next-card-empty">
          <span className="next-icon"><Check size={18} aria-hidden="true" /></span>
          <span className="hint">No unfinished classes. Start a new course or explore the Lab.</span>
        </div>
      )}
      <button type="button" className="next-card" onClick={onReview} disabled={!p.reviewDue}>
        <span className="next-icon review"><RotateCcw size={18} aria-hidden="true" /></span>
        <span className="stack-sm">
          <span className="hint">Review your mistakes</span>
          <strong>{p.reviewDue ? `${p.reviewDue} question${p.reviewDue > 1 ? 's' : ''} due` : p.nextReview ? `Next review ${formatDay(p.nextReview)}` : 'Nothing to review yet'}</strong>
        </span>
      </button>
    </div>
  );

  if (p.focusMode) {
    return (
      <section className="today stack-sm" aria-label="Today">
        {next}
        <label className="check-row hint"><input type="checkbox" checked onChange={() => setPrefs({ focusMode: false })} /> Focus mode (streaks, XP and celebrations hidden)</label>
      </section>
    );
  }

  return (
    <section className="today stack" aria-label="Today">
      {atRisk && (
        <div className="notice notice-info btn-row" style={{ justifyContent: 'space-between' }}>
          <span><Flame size={15} aria-hidden="true" /> Your {p.streak}-day streak needs one activity today. A review takes about two minutes.</span>
          <button type="button" className="btn btn-gold btn-sm" onClick={p.reviewDue ? onReview : () => p.continue && onContinue(p.continue.topic_id)}>
            {p.reviewDue ? 'Quick review' : 'Continue'}
          </button>
        </div>
      )}

      <div className="today-grid">
        <div className="today-card">
          <div className="today-big">
            <Flame size={34} aria-hidden="true" className={p.doneToday ? 'flame lit' : 'flame'} />
            <div>
              <div className="today-num num">{p.streak}</div>
              <div className="hint">day streak{p.longestStreak > p.streak ? ` · best ${p.longestStreak}` : ''}</div>
            </div>
          </div>
          <div className="week" aria-label="Last 7 days">
            {p.week.map((d) => {
              const dow = DOW[new Date(`${d.day}T12:00:00`).getDay()];
              return (
                <span key={d.day} className="week-day" data-state={d.frozen ? 'frozen' : d.active ? 'active' : 'idle'} data-today={d.day === p.day}
                  title={`${formatDay(d.day)}: ${d.frozen ? 'saved by a streak freeze' : `${d.xp} XP`}`}>
                  <span className="dot">{d.frozen ? <Snowflake size={11} /> : d.active ? <Check size={11} /> : null}</span>
                  {dow}
                </span>
              );
            })}
          </div>
          <p className="hint"><Snowflake size={13} aria-hidden="true" /> {p.freezes} streak freeze{p.freezes === 1 ? '' : 's'} · earn one every 7 days</p>
        </div>

        <div className="today-card">
          <div className="today-big">
            <GoalRing value={p.xpToday} goal={p.dailyGoal} size={58} stroke={6} />
            <div>
              <div className="today-num num">{p.xpToday}<span className="today-of">/{p.dailyGoal} XP</span></div>
              <div className="hint">{p.xpToday >= p.dailyGoal ? 'Daily goal reached' : `${p.dailyGoal - p.xpToday} XP to today's goal`}</div>
            </div>
          </div>
          <div className="field">
            <label htmlFor="goal-sel" className="hint">Daily goal</label>
            <select id="goal-sel" className="input" value={p.dailyGoal} onChange={(e) => setPrefs({ dailyGoal: Number(e.target.value) })}>
              {p.goals.map((g) => <option key={g} value={g}>{GOAL_NAMES[g] || g}: {g} XP a day</option>)}
            </select>
          </div>
        </div>

        <div className="today-card">
          <div className="today-big">
            <Trophy size={32} aria-hidden="true" className="trophy" />
            <div>
              <div className="today-num num">Level {p.level}</div>
              <div className="hint">{p.totalXp} XP total · {p.nextLevel - p.totalXp} to level {p.level + 1}</div>
            </div>
          </div>
          <div className="meter" aria-hidden="true"><span style={{ width: `${levelPct}%` }} /></div>
          <p className="hint">Badges: {earned} of {p.badges.length}</p>
        </div>
      </div>

      <div className="split">
        <div className="today-card">
          <h2 className="today-h">Daily quests</h2>
          <ul className="quests">
            {p.quests.map((q) => (
              <li key={q.id} data-done={q.done}>
                <span className="quest-check" aria-hidden="true">{q.done ? <Check size={13} /> : null}</span>
                <span className="stack-sm" style={{ flex: 1 }}>
                  <span>{q.title}</span>
                  <span className="meter" aria-hidden="true"><span style={{ width: `${(q.progress / q.target) * 100}%` }} /></span>
                </span>
                <span className="num hint">{q.progress}/{q.target}</span>
              </li>
            ))}
          </ul>
          <p className="hint">Finish all three for 15 bonus XP. New quests at midnight.</p>
        </div>
        <div className="stack-sm">
          <h2 className="today-h">Next up</h2>
          {next}
        </div>
      </div>

      <details className="badges-box">
        <summary>Badges ({earned}/{p.badges.length})</summary>
        <div className="badges">
          {p.badges.map((b) => (
            <div key={b.id} className="badge" data-earned={b.earned} title={b.description}>
              <span className="badge-icon">{b.earned ? <Award size={20} aria-hidden="true" /> : <Lock size={16} aria-hidden="true" />}</span>
              <strong>{b.name}</strong>
              <span className="hint">{b.description}</span>
            </div>
          ))}
        </div>
      </details>
      <label className="check-row hint">
        <input type="checkbox" checked={false} onChange={() => setPrefs({ focusMode: true })} /> Focus mode: hide streaks, XP and celebrations
      </label>
    </section>
  );
}
