import React, { useEffect, useRef, useState } from 'react';
import { Flame, Snowflake, Award, Target, Trophy, X, Sparkles } from 'lucide-react';

const reducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

/** Daily-goal ring: progress toward today's XP goal. */
export function GoalRing({ value, goal, size = 26, stroke = 3.5, label }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.min(1, goal ? value / goal : 0);
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label || `${value} of ${goal} XP today`} className="goal-ring">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" strokeOpacity="0.22" strokeWidth={stroke} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--gold)" strokeWidth={stroke} strokeLinecap="round"
        strokeDasharray={`${c * pct} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: 'stroke-dasharray 500ms ease' }} />
    </svg>
  );
}

/** Masthead chip: streak flame and today's goal ring. Opens My courses. */
export function StreakChip({ progress, onOpen }) {
  if (!progress || progress.focusMode) return null;
  const { streak, doneToday, xpToday, dailyGoal } = progress;
  return (
    <button type="button" className="streak-chip" onClick={onOpen}
      title={`${streak}-day streak${doneToday ? '' : ' (study today to keep it)'} · ${xpToday}/${dailyGoal} XP today`}>
      <Flame size={16} aria-hidden="true" className={doneToday ? 'flame lit' : 'flame'} />
      <span className="num">{streak}</span>
      <GoalRing value={xpToday} goal={dailyGoal} size={22} stroke={3} />
      <span className="visually-hidden">{streak}-day streak, {xpToday} of {dailyGoal} XP today</span>
    </button>
  );
}

function Confetti() {
  const ref = useRef(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || reducedMotion()) return undefined;
    const ctx = canvas.getContext('2d');
    const W = (canvas.width = window.innerWidth), H = (canvas.height = window.innerHeight);
    const colors = ['#c9a24a', '#e0bb62', '#0e4a37', '#2f7d5c', '#ffffff'];
    const parts = Array.from({ length: 140 }, () => ({
      x: W / 2 + (Math.random() - 0.5) * 200, y: H * 0.35, vx: (Math.random() - 0.5) * 12, vy: -Math.random() * 12 - 4,
      s: 5 + Math.random() * 6, r: Math.random() * Math.PI, vr: (Math.random() - 0.5) * 0.3, c: colors[(Math.random() * colors.length) | 0],
    }));
    let raf, t = 0;
    const tick = () => {
      ctx.clearRect(0, 0, W, H);
      for (const p of parts) {
        p.vy += 0.32; p.x += p.vx; p.y += p.vy; p.r += p.vr; p.vx *= 0.99;
        ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.r); ctx.fillStyle = p.c;
        ctx.fillRect(-p.s / 2, -p.s / 4, p.s, p.s / 2); ctx.restore();
      }
      if (++t < 150) raf = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(raf);
  }, []);
  return <canvas ref={ref} className="confetti" aria-hidden="true" />;
}

/** What deserves a full celebration card (small wins only get the "+XP" pop). */
function headline(r) {
  if (r.newBadges?.length) return { icon: Award, title: `Badge earned: ${r.newBadges[0].name}`, text: r.newBadges[0].description };
  if (r.levelUp) return { icon: Trophy, title: `Level ${r.level}!`, text: 'Your total XP just reached a new level.' };
  if (r.goalReached) return { icon: Target, title: 'Daily goal reached', text: `${r.xpToday} XP today. Anything more is a bonus.` };
  if (r.questsDone) return { icon: Sparkles, title: 'All quests done', text: '+15 bonus XP for finishing today\'s three quests.' };
  if (r.freezeEarned) return { icon: Snowflake, title: 'Streak freeze earned', text: 'It will save your streak if you miss a day.' };
  if (r.streakExtended && r.streak > 1) return { icon: Flame, title: `${r.streak}-day streak`, text: 'You kept it going. See you tomorrow.' };
  if (r.streakExtended) return { icon: Flame, title: 'Day 1', text: 'Your streak starts today. Come back tomorrow to grow it.' };
  return null;
}

/** Listens for rewards anywhere in the app: "+XP" pops for every action, a card and confetti for milestones. */
export default function RewardLayer({ focusMode, onReward }) {
  const [pops, setPops] = useState([]);
  const [card, setCard] = useState(null);

  useEffect(() => {
    const on = (e) => {
      const r = e.detail;
      onReward?.(r);
      if (focusMode) return;
      const id = Math.random().toString(36).slice(2);
      setPops((p) => [...p.slice(-3), { id, xp: r.xp }]);
      setTimeout(() => setPops((p) => p.filter((x) => x.id !== id)), 1600);
      const h = headline(r);
      if (h) setCard({ ...h, big: Boolean(r.goalReached || r.newBadges?.length || r.levelUp || r.questsDone), at: Date.now() });
    };
    window.addEventListener('andedu:reward', on);
    return () => window.removeEventListener('andedu:reward', on);
  }, [focusMode, onReward]);

  useEffect(() => {
    if (!card) return undefined;
    const t = setTimeout(() => setCard(null), card.big ? 5200 : 3200);
    return () => clearTimeout(t);
  }, [card]);

  const Icon = card?.icon;
  return (
    <>
      <div className="xp-pops" aria-live="polite">
        {pops.map((p) => <span key={p.id} className="xp-pop">+{p.xp} XP</span>)}
      </div>
      {card && (
        <>
          {card.big && <Confetti key={card.at} />}
          <div className={`reward-card${card.big ? ' big' : ''}`} role="status">
            <span className="reward-icon"><Icon size={card.big ? 30 : 22} aria-hidden="true" /></span>
            <div>
              <strong>{card.title}</strong>
              <p>{card.text}</p>
            </div>
            <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label="Dismiss" onClick={() => setCard(null)}><X size={14} /></button>
          </div>
        </>
      )}
    </>
  );
}
