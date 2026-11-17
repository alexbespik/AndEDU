// Server-graded practice types (the liberal-arts and STEM kits): the answer key never reaches the browser, so a body
// sends the student's submission to POST /api/practice/grade and shows the verdict the server returns.
// Graders answer {ok, score, feedback, details}; see the kit modules (practice_<kit>.py, GRADERS).
import { useCallback, useState } from 'react';
import { api } from '../lib/api';

export async function gradeOnServer(item, submission) {
  if (!item?.topicId || item?.id == null) {
    return { ok: false, score: 0, feedback: 'This exercise cannot be checked here (it is not saved in a lesson).', details: {}, error: true };
  }
  try {
    const r = await api('/api/practice/grade', { method: 'POST', body: { topicId: item.topicId, itemId: String(item.id), submission } });
    return { ok: !!r?.ok, score: typeof r?.score === 'number' ? r.score : (r?.ok ? 1 : 0), feedback: r?.feedback || '', details: r?.details || {} };
  } catch (e) {
    return { ok: false, score: 0, feedback: e?.message || 'Could not check the answer. Try again.', details: {}, error: true };
  }
}

/** useServerGrade(item, onResult) -> {check(submission), result, busy, reset}. Calls onResult(ok, submission) once per check
 * (not on network errors, so a failed request never counts as a wrong answer). */
export function useServerGrade(item, onResult) {
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const check = useCallback(async (submission) => {
    setBusy(true);
    const r = await gradeOnServer(item, submission);
    setBusy(false);
    setResult(r);
    if (!r.error && onResult) onResult(r.ok, submission);
    return r;
  }, [item, onResult]);
  const reset = useCallback(() => setResult(null), []);
  return { check, result, busy, reset };
}
