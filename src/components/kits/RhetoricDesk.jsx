import React, { useEffect, useId, useState } from 'react';
import { Check, Minus, Plus, Trash2 } from 'lucide-react';
import { Bar, DeskCard, Outcome, RunButton, pct, useTool } from './common';

const FIELDS = [
  ['claim', 'Claim', 'What you want the audience to accept.'],
  ['data', 'Data (grounds)', 'The evidence or facts you offer for the claim.'],
  ['warrant', 'Warrant', 'The principle that connects the data to the claim.'],
  ['backing', 'Backing', 'Support for the warrant itself.'],
  ['qualifier', 'Qualifier', 'How strong the claim is: usually, probably, in most cases.'],
  ['rebuttal', 'Rebuttal', 'The exceptions or objections you admit.'],
];
const DEFAULT_TOULMIN = {
  claim: 'Our school should start classes at 9 a.m.',
  data: 'Teenagers\' body clocks shift later during adolescence, so many fall asleep after 11 p.m.',
  warrant: 'Students who have had enough sleep learn and behave better in class.',
  backing: 'Sleep medicine research on adolescents describes this shift in the body clock.',
  qualifier: 'in most cases',
  rebuttal: 'unless bus schedules or after-school sport times cannot move',
};
const APPEALS = [['ethos', 'Ethos', 'credibility'], ['logos', 'Logos', 'reason'], ['pathos', 'Pathos', 'emotion']];
const DEFAULT_SEGMENTS = [
  { text: 'As a teacher for twenty years, I have watched students struggle through first period.', tags: ['ethos'] },
  { text: 'Adolescent sleep research shows the body clock moves later, so an 8 a.m. start asks for more than the body can give.', tags: ['logos'] },
  { text: 'Picture a sixteen-year-old, eyes heavy, trying to follow algebra at 8 in the morning.', tags: ['pathos'] },
  { text: 'We owe our children a school day that fits them.', tags: ['ethos', 'pathos'] },
];

// triangle corners (SVG units): logos on top, ethos bottom left, pathos bottom right
const CORNER = { logos: [150, 20], ethos: [20, 245], pathos: [280, 245] };

function Toulmin() {
  const [vals, setVals] = useState(DEFAULT_TOULMIN);
  const [state, run] = useTool('rhetoric');
  const id = useId();
  const submit = () => run('toulmin', vals);
  useEffect(() => { submit(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <DeskCard title="Toulmin argument" what="Lays an argument out in Toulmin's six parts and shows which are present. It checks the structure only, never whether your argument is good.">
      <div className="kt-two">
        {FIELDS.map(([k, label, help]) => (
          <div key={k} className="field">
            <label htmlFor={`${id}-${k}`}>{label}</label>
            <textarea id={`${id}-${k}`} className="kt-input" rows={2} maxLength={1000} value={vals[k]} aria-describedby={`${id}-${k}-h`} onChange={(e) => setVals((v) => ({ ...v, [k]: e.target.value }))} />
            <span id={`${id}-${k}-h`} className="hint">{help}</span>
          </div>
        ))}
      </div>
      <div className="btn-row"><RunButton loading={state.loading} onClick={submit}>Check the structure</RunButton></div>
      <Outcome state={state} render={(r) => (
        <>
          <p><strong>{!r.missing.length ? 'All six parts are present.'
            : r.complete ? `The core (claim, data, warrant) is there. Optional parts missing: ${r.missing.map((m) => FIELDS.find((f) => f[0] === m)?.[1] || m).join(', ')}.`
              : `Missing: ${r.missing.map((m) => FIELDS.find((f) => f[0] === m)?.[1] || m).join(', ')}.`}</strong></p>
          <ul className="kt-tags" aria-label="Parts present">
            {FIELDS.map(([k, label]) => (
              <li key={k} className={`kt-chip ${r.present?.[k] ? 'kt-chip-ok' : 'kt-chip-warn'}`}>
                {r.present?.[k] ? <Check size={12} aria-hidden="true" /> : <Minus size={12} aria-hidden="true" />} {label}<span className="kt-sr">{r.present?.[k] ? ': present' : ': missing'}</span>
              </li>
            ))}
          </ul>
          {r.notes?.length > 0 && <ul className="kt-list">{r.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
        </>
      )} />
    </DeskCard>
  );
}

function Appeals() {
  const [segs, setSegs] = useState(DEFAULT_SEGMENTS);
  const [state, run] = useTool('rhetoric');
  const submit = () => run('appeals', { segments: segs.filter((s) => s.text.trim()).map((s) => ({ text: s.text, tags: s.tags })) });
  useEffect(() => { submit(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const toggle = (i, tag) => setSegs((ss) => ss.map((s, j) => (j !== i ? s : { ...s, tags: s.tags.includes(tag) ? s.tags.filter((t) => t !== tag) : [...s.tags, tag] })));
  return (
    <DeskCard title="Appeal balancer" what="Split a speech into passages and tag each as ethos (the speaker's credibility), logos (reason and evidence) or pathos (emotion). The triangle shows where the speech leans. A passage with two tags counts half for each.">
      <ol className="kt-formlines">
        {segs.map((s, i) => (
          <li key={i} className="kt-seg-row">
            <textarea className="kt-input kt-grow" rows={2} maxLength={1000} aria-label={`Passage ${i + 1}`} value={s.text} onChange={(e) => setSegs((ss) => ss.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))} />
            <div className="kt-tagbtns" role="group" aria-label={`Appeals in passage ${i + 1}`}>
              {APPEALS.map(([k, label]) => <button key={k} type="button" className="kt-seg" aria-pressed={s.tags.includes(k)} onClick={() => toggle(i, k)}>{label}</button>)}
              <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label={`Remove passage ${i + 1}`} onClick={() => setSegs((ss) => ss.filter((_, j) => j !== i))}><Trash2 size={14} aria-hidden="true" /></button>
            </div>
          </li>
        ))}
      </ol>
      <div className="btn-row">
        <button type="button" className="btn btn-quiet btn-sm" disabled={segs.length >= 100} onClick={() => setSegs((ss) => [...ss, { text: '', tags: [] }])}><Plus size={14} aria-hidden="true" /> Add passage</button>
        <RunButton loading={state.loading} onClick={submit}>Balance the appeals</RunButton>
      </div>
      <Outcome state={state} render={(r) => {
        const sh = r.shares || {};
        const tagged = Object.values(sh).some(Boolean);  // nothing tagged: the dot sits at the centre (equal balance)
        const w = tagged ? sh : { ethos: 1 / 3, logos: 1 / 3, pathos: 1 / 3 };
        const px = (CORNER.ethos[0] * (w.ethos || 0)) + (CORNER.logos[0] * (w.logos || 0)) + (CORNER.pathos[0] * (w.pathos || 0));
        const py = (CORNER.ethos[1] * (w.ethos || 0)) + (CORNER.logos[1] * (w.logos || 0)) + (CORNER.pathos[1] * (w.pathos || 0));
        return (
          <div className="kt-two">
            <svg className="kt-tri" viewBox="0 0 300 275" role="img" aria-label={`Appeal triangle: ethos ${pct(sh.ethos || 0, 0)}, logos ${pct(sh.logos || 0, 0)}, pathos ${pct(sh.pathos || 0, 0)}`}>
              <polygon points={`${CORNER.logos} ${CORNER.pathos} ${CORNER.ethos}`} className="kt-tri-shape" />
              <circle cx="150" cy="170" r="3" className="kt-tri-mid" />
              <text x={CORNER.logos[0]} y="14" textAnchor="middle" className="kt-tri-label">Logos</text>
              <text x={CORNER.ethos[0]} y="266" textAnchor="start" className="kt-tri-label">Ethos</text>
              <text x={CORNER.pathos[0]} y="266" textAnchor="end" className="kt-tri-label">Pathos</text>
              <circle cx={px} cy={py} r="9" className="kt-tri-dot" />
            </svg>
            <div>
              {APPEALS.map(([k, label, gloss]) => <Bar key={k} label={`${label} (${gloss})`} value={sh[k]} text={`${pct(sh[k] || 0, 0)}`} />)}
              {r.untagged_chars > 0 && <p className="hint">{r.untagged_chars} characters carry no tag and are left out.</p>}
              {!tagged && <p className="hint">Tag at least one passage to place a point.</p>}
            </div>
          </div>
        );
      }} />
    </DeskCard>
  );
}

export default function RhetoricDesk() {
  return <div className="kt-desk"><Toulmin /><Appeals /></div>;
}
