import React, { useEffect, useId, useState } from 'react';
import { DeskCard, Outcome, RunButton, useTool } from './common';

const DEFAULT_CONTEXTS = 'Topsoil\nWall F\nPit B\nFloor C\nWall A\nPit D\nPacked clay';
const DEFAULT_EDGES = 'Topsoil > Wall F\nTopsoil > Pit B\nWall F > Floor C\nPit B > Floor C\nFloor C > Wall A\nPit D > Wall A\nWall A > Packed clay';
const DEFAULT_LEIDEN = 'Μάρκος [Αὐ]ρήλιος (ἐπ)οίησ[εν] | [---] ἔτους <γ> {δδ} ⟦Νέρων⟧\nvac. ἀγαθῇ τύχῃ [.3] ';

const KIND_WORDS = {
  restored: 'Restored by the editor: [abc]',
  lost: 'Lost text, only its length is known: [---]',
  expansion: 'Abbreviation expanded: (abc)',
  addition: 'Editorial addition: <abc>',
  deletion: 'Editorial deletion: {abc}',
  erasure: 'Erased in antiquity: [[abc]]',
  uncertain: 'Uncertain letter (underdot)',
  vacat: 'Empty space on the stone: vac.',
  text: 'Clear text',
};

const lines = (s) => s.split('\n').map((l) => l.trim()).filter(Boolean);
const slug = (k) => String(k).replace(/[^a-z0-9_-]/gi, '');

function Harris() {
  const [contexts, setContexts] = useState(DEFAULT_CONTEXTS);
  const [edges, setEdges] = useState(DEFAULT_EDGES);
  const [localError, setLocalError] = useState('');
  const [state, run] = useTool('classics');
  const id = useId();

  const submit = () => {
    setLocalError('');
    const names = lines(contexts);
    const pairs = [];
    const rows = lines(edges);
    for (let i = 0; i < rows.length; i += 1) {
      const parts = rows[i].split('>').map((s) => s.trim());
      if (parts.length !== 2 || !parts[0] || !parts[1]) { setLocalError(`Relation ${i + 1}: write it as "later context > earlier context" (the upper layer first).`); return null; }
      const unknown = parts.find((p) => !names.includes(p));
      if (unknown) { setLocalError(`Relation ${i + 1} names "${unknown}", which is not in the list of contexts. Add it there first.`); return null; }
      pairs.push(parts);
    }
    if (!names.length) { setLocalError('List at least one context.'); return null; }
    return run('harris', { contexts: names, edges: pairs });
  };
  useEffect(() => { submit(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <DeskCard title="Harris matrix" what="An excavation is read from the top down: each relation says one deposit lies above another, so it is later. The tool orders the contexts into phases and warns if your relations contradict each other.">
      <div className="kt-two">
        <div className="field">
          <label htmlFor={`${id}-c`}>Contexts (one per line)</label>
          <textarea id={`${id}-c`} className="kt-input kt-mono" rows={8} value={contexts} onChange={(e) => setContexts(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor={`${id}-e`}>Stratigraphic relations (above &gt; below)</label>
          <textarea id={`${id}-e`} className="kt-input kt-mono" rows={8} value={edges} onChange={(e) => setEdges(e.target.value)} />
        </div>
      </div>
      <div className="btn-row"><RunButton loading={state.loading} onClick={submit}>Build the sequence</RunButton></div>
      {localError && <div className="notice notice-bad" role="alert">{localError}</div>}
      <Outcome state={state} render={(r) => (r.cycle ? (
        <div className="notice notice-bad" role="alert">
          <strong>Your relations contradict each other.</strong> A deposit cannot be above itself: {r.cycle.join(' → ')} → {r.cycle[0]}. Check these relations against the section drawings.
        </div>
      ) : (
        <>
          <h3 className="kt-h3">Phases (latest first)</h3>
          <ol className="kt-phases">
            {r.phases.map((ph, i) => (
              <li key={i}><span className="kt-phase-n">Phase {i + 1}</span>{ph.map((c) => <span key={c} className="kt-chip">{c}</span>)}</li>
            ))}
          </ol>
          <p><strong>One valid order, latest to earliest:</strong> {r.order.join(' → ')}</p>
          {r.redundant?.length > 0 && (
            <p className="hint">Not needed (already implied by other relations): {r.redundant.map((p) => p.join(' > ')).join('; ')}.</p>
          )}
          {r.isolated?.length > 0 && <p className="notice">No relation yet for: {r.isolated.join(', ')}. Without one, their date is unknown.</p>}
        </>
      ))} />
    </DeskCard>
  );
}

function Leiden() {
  const [text, setText] = useState(DEFAULT_LEIDEN);
  const [state, run] = useTool('classics');
  const id = useId();
  const submit = () => run('leiden', { text });
  useEffect(() => { submit(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <DeskCard title="Leiden conventions" what="Epigraphers mark what is on the stone and what they restored using brackets. Paste an inscription and see each kind of marking highlighted, plus the diplomatic and edited readings.">
      <div className="field">
        <label htmlFor={`${id}-t`}>Inscription (| or a new line starts a new line of the stone)</label>
        <textarea id={`${id}-t`} className="kt-input kt-mono" rows={4} value={text} onChange={(e) => setText(e.target.value)} />
        <span className="hint">[abc] restored, [---] lost, (abc) expanded, &lt;abc&gt; added, {'{abc}'} deleted, [[abc]] erased.</span>
      </div>
      <div className="btn-row"><RunButton loading={state.loading} onClick={submit}>Read the inscription</RunButton></div>
      <Outcome state={state} render={(r) => {
        const byLine = {};
        (r.tokens || []).forEach((t) => { (byLine[t.line] = byLine[t.line] || []).push(t); });
        const kinds = Object.keys(r.counts || {}).filter((k) => r.counts[k] > 0);
        return (
          <>
            {r.problems?.length > 0 && (
              <div className="notice notice-bad" role="alert">
                {r.problems.map((p, i) => <div key={i}>{p.code === 'nested' ? 'Brackets are nested inside each other' : 'A bracket is not closed or has no partner'} (near character {p.at + 1}).</div>)}
              </div>
            )}
            <div className="kt-inscription">
              {Object.keys(byLine).sort((a, b) => a - b).map((ln) => (
                <div key={ln} className="kt-iline"><span className="kt-lno" aria-hidden="true">{ln}</span>
                  <span>{byLine[ln].map((t, i) => (t.text ? <span key={i} className={`kt-tok kt-k-${slug(t.kind)}`} title={KIND_WORDS[t.kind] || t.kind}>{t.text}</span> : null))}</span>
                </div>
              ))}
            </div>
            <dl className="kt-dl">
              <dt>Diplomatic (only what is on the stone)</dt><dd className="kt-mono">{r.diplomatic}</dd>
              <dt>Edited (with the editor's restorations)</dt><dd className="kt-mono">{r.edited}</dd>
              <dt>Normalized</dt><dd className="kt-mono">{r.normalized}</dd>
            </dl>
            <ul className="kt-tags" aria-label="Legend">
              {kinds.map((k) => <li key={k} className="kt-chip"><span className={`kt-tok kt-k-${slug(k)}`}>{r.counts[k]}</span> {KIND_WORDS[k] || k}</li>)}
            </ul>
          </>
        );
      }} />
    </DeskCard>
  );
}

export default function ClassicsDesk() {
  return <div className="kt-desk"><Harris /><Leiden /></div>;
}
