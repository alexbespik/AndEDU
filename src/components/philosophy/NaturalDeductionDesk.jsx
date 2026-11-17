import React, { useState } from 'react';
import { CheckCircle2, XCircle, ArrowRight, ArrowLeft, Trash2, Plus, Lightbulb } from 'lucide-react';
import { logicCheck } from './engine';
import { SCAFFOLDS } from './scaffolds';
import '../../styles/philosophy.css';

// The rules of forall x: Calgary (logic_proof.py). Rule names are what the engine reads.
const BASIC = ['PR', 'AS', 'R', '&I', '&E', '|I', '|E', '->I', '->E', '<->I', '<->E', '~I', '~E', 'X', 'IP'];
const DERIVED = ['DS', 'MT', 'DNE', 'LEM', 'DeM'];
const CITE_HELP = 'Line numbers and subproofs, e.g. 1, 3 or 2-4';

const blank = (depth = 0) => ({ formula: '', rule: '', cites: '', depth });
const citesOf = (text) => String(text || '').split(/[,\s]+/).filter(Boolean).map((t) => (/^\d+$/.test(t) ? Number(t) : t));
const citesText = (cites) => (cites || []).join(', ');
const fromScaffold = (s) => s.premises.map((p) => ({ formula: p, rule: 'PR', cites: '', depth: 0 }));

export default function NaturalDeductionDesk() {
  const [scaffoldId, setScaffoldId] = useState(SCAFFOLDS[0].id);
  const [premises, setPremises] = useState(SCAFFOLDS[0].premises.join(', '));
  const [goal, setGoal] = useState(SCAFFOLDS[0].goal);
  const [rules, setRules] = useState(SCAFFOLDS[0].rules);
  const [lines, setLines] = useState(() => [...fromScaffold(SCAFFOLDS[0]), blank()]);
  const [out, setOut] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const scaffold = SCAFFOLDS.find((s) => s.id === scaffoldId);

  const stale = () => { setOut(null); setError(null); };
  const load = (id) => {
    setScaffoldId(id); stale();
    const s = SCAFFOLDS.find((x) => x.id === id);
    if (!s) { setPremises(''); setGoal(''); setRules('derived'); setLines([blank()]); return; }
    setPremises(s.premises.join(', ')); setGoal(s.goal); setRules(s.rules); setLines([...fromScaffold(s), blank()]);
  };
  const showSolution = () => {
    if (!scaffold) return;
    stale();
    setLines(scaffold.solution.map((l) => ({ formula: l.formula, rule: l.rule, cites: citesText(l.cites), depth: l.depth })));
  };
  const patch = (i, p) => { stale(); setLines((ls) => ls.map((l, j) => {
    if (j !== i) return l;
    const next = { ...l, ...p };
    if (p.rule === 'AS' && i > 0 && next.depth <= ls[i - 1].depth) next.depth = ls[i - 1].depth + 1; // an assumption opens a subproof
    return next;
  })); };
  const insertAfter = (i) => { stale(); setLines((ls) => [...ls.slice(0, i + 1), blank(ls[i]?.depth ?? 0), ...ls.slice(i + 1)]); };
  const remove = (i) => { stale(); setLines((ls) => (ls.length > 1 ? ls.filter((_, j) => j !== i) : [blank()])); };
  const indent = (i, d) => patch(i, { depth: Math.max(0, Math.min(lines[i].depth + d, i > 0 ? lines[i - 1].depth + 1 : 0)) });

  const check = async () => {
    setBusy(true); setError(null);
    const req = {
      op: 'proof', rules,
      premises: premises.split(',').map((p) => p.trim()).filter(Boolean),
      lines: lines.map((l) => ({ formula: l.formula, rule: l.rule, cites: citesOf(l.cites), depth: l.depth })),
    };
    if (goal.trim()) req.goal = goal.trim();
    const res = await logicCheck(req);
    setBusy(false);
    if (res.ok) setOut(res.result); else { setOut(null); setError(res.error.message); }
  };

  const rulesList = rules === 'basic' ? BASIC : [...BASIC, ...DERIVED];
  const verdict = (n) => out?.lines?.find((l) => l.n === n);

  return (
    <div className="stack">
      <p className="hint">A Fitch-style proof in the rules of forall x: Calgary. Each line has a formula, a rule and the lines it cites (a subproof is cited as
        its first and last line, like 3-5). The engine judges every line separately; no AI is involved.</p>
      <div className="phx-grid">
        <div className="field">
          <label htmlFor="nd-scaffold">Exercise</label>
          <select id="nd-scaffold" className="select" value={scaffoldId} onChange={(e) => load(e.target.value)}>
            {SCAFFOLDS.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
            <option value="free">My own proof</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="nd-rules">Rules allowed</label>
          <select id="nd-rules" className="select" value={rules} onChange={(e) => { setRules(e.target.value); stale(); }}>
            <option value="basic">Basic rules only</option>
            <option value="derived">Basic and derived (DS, MT, DNE, LEM, DeM)</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="nd-prem">Premises (comma separated)</label>
          <input id="nd-prem" className="input phx-mono" value={premises} spellCheck={false} onChange={(e) => { setPremises(e.target.value); setScaffoldId('free'); stale(); }} />
        </div>
        <div className="field">
          <label htmlFor="nd-goal">Goal</label>
          <input id="nd-goal" className="input phx-mono" value={goal} spellCheck={false} onChange={(e) => { setGoal(e.target.value); setScaffoldId('free'); stale(); }} />
        </div>
      </div>
      {scaffold && <p className="hint"><Lightbulb size={14} aria-hidden="true" /> {scaffold.hint}</p>}

      <ol className="phx-proof" aria-label="Proof lines">
        {lines.map((l, i) => {
          const v = verdict(i + 1);
          return (
            <li key={i} className={`phx-line ${v ? (v.ok ? 'phx-ok' : 'phx-bad') : ''}`}>
              <div className="phx-line-main">
                <span className="phx-num">{i + 1}</span>
                <span className="phx-bars" style={{ '--phx-depth': l.depth }} aria-label={`Subproof depth ${l.depth}`} role="img" />
                <input className="input phx-mono phx-formula" aria-label={`Line ${i + 1} formula`} value={l.formula} spellCheck={false}
                  onChange={(e) => patch(i, { formula: e.target.value })} placeholder="formula" />
                <select className="select phx-rule" aria-label={`Line ${i + 1} rule`} value={l.rule} onChange={(e) => patch(i, { rule: e.target.value })}>
                  <option value="">rule</option>
                  {rulesList.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
                <input className="input phx-mono phx-cites" aria-label={`Line ${i + 1} cites`} title={CITE_HELP} placeholder="cites" value={l.cites}
                  disabled={l.rule === 'PR' || l.rule === 'AS'} onChange={(e) => patch(i, { cites: e.target.value })} />
                <span className="phx-line-tools">
                  <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label={`Move line ${i + 1} out one level`} disabled={l.depth === 0} onClick={() => indent(i, -1)}><ArrowLeft size={14} aria-hidden="true" /></button>
                  <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label={`Move line ${i + 1} in one level`} disabled={i === 0 || l.depth > lines[i - 1].depth} onClick={() => indent(i, 1)}><ArrowRight size={14} aria-hidden="true" /></button>
                  <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label={`Add a line after line ${i + 1}`} onClick={() => insertAfter(i)}><Plus size={14} aria-hidden="true" /></button>
                  <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label={`Delete line ${i + 1}`} onClick={() => remove(i)}><Trash2 size={14} aria-hidden="true" /></button>
                </span>
              </div>
              {v && (
                <p className={`phx-verdict ${v.ok ? 'ok' : 'err'}`}>
                  {v.ok ? <CheckCircle2 size={14} aria-hidden="true" /> : <XCircle size={14} aria-hidden="true" />}{' '}
                  {v.ok ? 'Follows.' : <><code>{v.code}</code> {v.message}{v.pos != null && <span className="hint"> (character {v.pos + 1})</span>}</>}
                </p>
              )}
            </li>
          );
        })}
      </ol>

      <div className="btn-row">
        <button type="button" className="btn btn-primary" disabled={busy || !lines.some((l) => l.formula.trim())} onClick={check}>{busy ? 'Checking…' : 'Check the proof'}</button>
        <button type="button" className="btn btn-quiet" onClick={() => setLines((ls) => [...ls, blank(ls[ls.length - 1]?.depth ?? 0)])}><Plus size={14} aria-hidden="true" /> Add a line</button>
        {scaffold && <button type="button" className="btn btn-quiet" onClick={showSolution}>Show a worked solution</button>}
      </div>
      {error && <p className="notice notice-bad" role="alert">{error}</p>}
      {out && (
        <div aria-live="polite" className="stack-sm">
          <p className={`notice ${out.complete ? 'notice-ok' : out.valid ? 'notice-info' : 'notice-bad'}`}>
            {out.complete ? 'Complete: every line follows and the last line is the goal.'
              : out.valid ? 'Every line follows so far.' : 'Some lines do not follow: see the marks above.'}
            {out.goal_message && out.goal && <> {out.goal_message}</>}
          </p>
        </div>
      )}
    </div>
  );
}
