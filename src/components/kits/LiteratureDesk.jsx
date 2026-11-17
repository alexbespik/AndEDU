import React, { useEffect, useId, useMemo, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Bar, DeskCard, Outcome, RunButton, pct, useTool } from './common';

const METERS = [['auto', 'Best fit (automatic)'], ['iambic', 'Iambic (da-DUM)'], ['trochaic', 'Trochaic (DUM-da)'], ['anapestic', 'Anapestic (da-da-DUM)'], ['dactylic', 'Dactylic (DUM-da-da)']];
const FORMS = [
  ['shakespearean_sonnet', 'Shakespearean sonnet (14 lines, ABAB CDCD EFEF GG)'],
  ['petrarchan_sonnet', 'Petrarchan sonnet (14 lines, ABBAABBA + a sestet)'],
  ['villanelle', 'Villanelle (19 lines, two refrains)'],
  ['limerick', 'Limerick (5 lines, AABBA)'],
  ['terza_rima', 'Terza rima (interlocking ABA BCB CDC ...)'],
];
const SONNET = [
  ["Shall I compare thee to a summer's day?", 'A'], ['Thou art more lovely and more temperate:', 'B'],
  ["Rough winds do shake the darling buds of May,", 'A'], ["And summer's lease hath all too short a date;", 'B'],
  ['Sometime too hot the eye of heaven shines,', 'C'], ["And often is his gold complexion dimm'd;", 'D'],
  ['And every fair from fair sometime declines,', 'C'], ["By chance or nature's changing course untrimm'd;", 'D'],
  ['But thy eternal summer shall not fade,', 'E'], ["Nor lose possession of that fair thou ow'st;", 'F'],
  ["Nor shall death brag thou wander'st in his shade,", 'E'], ["When in eternal lines to time thou grow'st:", 'F'],
  ['So long as men can breathe or eyes can see,', 'G'], ['So long lives this, and this gives life to thee.', 'G'],
].map(([text, rhyme]) => ({ text, rhyme }));

const splitSyllables = (s) => s.trim().split(/[\s-]+/).filter(Boolean).slice(0, 24);
const FOOT_WORDS = { iamb: 'iamb', trochee: 'trochee', spondee: 'spondee', pyrrhic: 'pyrrhic', anapest: 'anapest', dactyl: 'dactyl', amphibrach: 'amphibrach', irregular: 'irregular foot', incomplete: 'incomplete foot (catalexis)' };

function Scansion() {
  const [text, setText] = useState("Shall I com-pare thee to a sum-mer's day");
  const [stress, setStress] = useState({ 1: true, 3: true, 5: true, 7: true, 9: true });
  const [meter, setMeter] = useState('auto');
  const [state, run] = useTool('literature');
  const id = useId();
  const syl = useMemo(() => splitSyllables(text), [text]);
  const pattern = syl.map((_, i) => (stress[i] ? '/' : 'x')).join('');
  const submit = () => (syl.length ? run('scan', { stresses: pattern, meter }) : null);
  useEffect(() => { submit(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <DeskCard title="Scansion tapper" what="Click each syllable to mark it stressed (/) or unstressed (x). The tool divides the line into feet, names the meter and shows where the poet varies the pattern.">
      <div className="field">
        <label htmlFor={`${id}-l`}>Line (separate syllables with a space or a hyphen)</label>
        <input id={`${id}-l`} className="kt-input" value={text} onChange={(e) => setText(e.target.value)} />
        {splitSyllables(text).length === 24 && <span className="hint">At most 24 syllables are used.</span>}
      </div>
      <div className="kt-syls" role="group" aria-label="Syllables: press to toggle stress">
        {syl.map((s, i) => (
          <button key={i} type="button" className="kt-syl" aria-pressed={!!stress[i]} aria-label={`${s}, ${stress[i] ? 'stressed' : 'unstressed'}`} onClick={() => setStress((st) => ({ ...st, [i]: !st[i] }))}>
            <span className="kt-syl-mark" aria-hidden="true">{stress[i] ? '/' : 'x'}</span>
            <span>{s}</span>
          </button>
        ))}
      </div>
      <p className="hint">Pattern: <span className="kt-mono">{pattern || '(no syllables)'}</span></p>
      <div className="field kt-small">
        <label htmlFor={`${id}-m`}>Meter to test</label>
        <select id={`${id}-m`} className="kt-input" value={meter} onChange={(e) => setMeter(e.target.value)}>
          {METERS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>
      <div className="btn-row"><RunButton loading={state.loading} onClick={submit}>Scan the line</RunButton></div>
      <Outcome state={state} render={(r) => (
        <>
          <p><strong>{r.meter} {r.line_name}</strong>{r.feminine_ending ? ', with a feminine ending (an extra unstressed syllable)' : ''}: {r.foot_count} feet.</p>
          <Bar label="Fit to the pure pattern" value={r.fit} text={pct(r.fit, 0)} />
          <ul className="kt-tags" aria-label="Feet">
            {r.feet.map((f, i) => (
              <li key={i} className={`kt-chip ${f.substitution ? 'kt-chip-warn' : ''}`}>
                <span className="kt-mono">{f.pattern}</span> {FOOT_WORDS[f.name] || f.name}{f.substitution ? ' (substitution)' : ''}
              </li>
            ))}
          </ul>
          <p className="hint">A substitution is a foot that differs from the meter's usual one. Poets use them on purpose, so they are not mistakes.</p>
        </>
      )} />
    </DeskCard>
  );
}

function FormCheck() {
  const [form, setForm] = useState('shakespearean_sonnet');
  const [rows, setRows] = useState(SONNET);
  const [state, run] = useTool('literature');
  const submit = () => run('form', { form, rhymes: rows.map((r) => r.rhyme.trim()), lines: rows.map((r) => r.text) });
  useEffect(() => { submit(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const setRow = (i, patch) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  return (
    <DeskCard title="Form checker" what="Type the lines and the rhyme letter you hear at the end of each (same letter = rhymes). The tool compares your pattern with the form's. It never decides what rhymes: that is your ear's job.">
      <div className="field">
        <label htmlFor="kt-form">Form</label>
        <select id="kt-form" className="kt-input" value={form} onChange={(e) => setForm(e.target.value)}>
          {FORMS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>
      <ol className="kt-formlines">
        {rows.map((r, i) => (
          <li key={i} className="kt-row">
            <input className="kt-input kt-grow" aria-label={`Line ${i + 1} text`} value={r.text} onChange={(e) => setRow(i, { text: e.target.value })} />
            <input className="kt-input kt-rhyme kt-mono" aria-label={`Line ${i + 1} rhyme letter`} maxLength={2} value={r.rhyme} onChange={(e) => setRow(i, { rhyme: e.target.value.toUpperCase() })} />
            <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label={`Remove line ${i + 1}`} onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))}><Trash2 size={14} aria-hidden="true" /></button>
          </li>
        ))}
      </ol>
      <div className="btn-row">
        <button type="button" className="btn btn-quiet btn-sm" disabled={rows.length >= 60} onClick={() => setRows((rs) => [...rs, { text: '', rhyme: '' }])}><Plus size={14} aria-hidden="true" /> Add line</button>
        <RunButton loading={state.loading} onClick={submit}>Check the form</RunButton>
      </div>
      <Outcome state={state} render={(r) => (
        <>
          <p>
            <strong>{r.line_count_ok ? 'Line count matches.' : `Line count differs: the form has ${r.expected_lines} lines, you have ${rows.length}.`}</strong>
            {r.mismatches?.length ? ` Rhyme letters differ from the form at line${r.mismatches.length > 1 ? 's' : ''} ${r.mismatches.map((n) => n + 1).join(', ')}.` : ' Your rhyme letters follow the form.'}
          </p>
          <Bar label="Fit to the form" value={r.fit} text={pct(r.fit, 0)} />
          <dl className="kt-dl">
            <dt>Form expects</dt><dd className="kt-mono kt-wrapany">{r.scheme_expected}</dd>
            <dt>You gave</dt><dd className="kt-mono kt-wrapany">{r.scheme_given}</dd>
          </dl>
          {r.refrains?.length > 0 && (
            <ul className="kt-list">
              {r.refrains.map((f, i) => <li key={i}>Refrain line {f.line}: {f.ok ? 'repeats as the form requires.' : 'does not repeat the expected line.'}</li>)}
            </ul>
          )}
        </>
      )} />
    </DeskCard>
  );
}

export default function LiteratureDesk() {
  return <div className="kt-desk"><Scansion /><FormCheck /></div>;
}
