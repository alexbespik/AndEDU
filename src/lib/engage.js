// Engagement client: report learning actions, and broadcast the rewards the server grants.
import { api, loadProfile } from './api';

/** Shows the celebration for a server reward (RewardLayer listens) and refreshes the streak/goal UI. */
export function emitRewards(rewards) {
  if (rewards && rewards.xp > 0) window.dispatchEvent(new CustomEvent('andedu:reward', { detail: rewards }));
}

/** An action graded in the browser: practice, math, IDE problems, simulations, reading. The server sets the XP. */
export function reportXp(source, ref) {
  const user = loadProfile();
  if (!user?.id) return Promise.resolve(null);
  return api(`/api/engage/${user.id}/xp`, { method: 'POST', body: { source, ref: String(ref ?? '') } })
    .then((r) => { emitRewards(r); return r; })
    .catch(() => null);
}

/** Practice & games result (speed round, flashcards, timeline, practice). Kept apart from the class quiz score. */
export function reportActivity(topicId, kind, correct, total, points = 0) {
  const user = loadProfile();
  if (!user?.id || !topicId || !total) return Promise.resolve(null);
  return api(`/api/activity/${user.id}/result`, { method: 'POST', body: { topicId, kind, correct, total, points } })
    .then((r) => { window.dispatchEvent(new CustomEvent('andedu:activity', { detail: r })); return r; })
    .catch(() => null);
}
