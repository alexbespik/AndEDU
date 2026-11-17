import React, { useRef, useState } from 'react';
import { Check, Eraser } from 'lucide-react';
import { logicCheck, tf, rowText } from './engine';
import '../../styles/philosophy.css';

const SYMBOLS = ['¬', '∧', '∨', '→', '↔', '⊥', '(', ')'];
const MODES = [
  { id: 'table', label: 'Truth table', hint: 'Every row for up to 3 formulas. Or fill the cells yourself and check them.' },
  { id: 'classify', label: 'Classify', hint: 'Is each formula a tautology, a contradiction or contingent?' },
  { id: 'equiv', label: 'Equivalence', hint: 'Do the first two formulas always have the same truth value?' },
];
const KIND = { tautology: 'Tautology: true in every row', contradiction: 'Contradiction: false in every row', contingent: 'Contingent: true in some rows, false in others' };
const EXAMPLES = [['P -> Q', '~P | Q'], ['P | ~P'], ['P & ~P'], ['~(P & Q)', '~P | ~Q'], ['P -> Q', 'Q -> P']];

export default function TruthTableDesk() {
  const [mode, setMode] = useState('table');
  const [formulas, setFormulas] = useState(['P -> Q', '~P | Q']);
  const [out, setOut] = useState(null); // {mode, data} | {error}
  const [busy, setBusy] = useState(false);
  const [practice, setPractice] = useState(false);
  const [guess, setGuess] = useState({});
  const [checked, setChecked] = useState(false);
  const inputs = useRef([]);
  const active = useRef(0);

  const setAt = (i, v) => { setFormulas((f) => f.map((x, j) => (j === i ? v : x))); setOut(null); setChecked(false); };
  const insert = (sym) => {
    const el = inputs.current[active.current];
    const i = active.current;
    const cur = formulas[i] ?? '';
    const at = el?.selectionStart ?? cur.length;
    setAt(i, cur.slice(0, at) + sym + cur.slice(el?.selectionEnd ?? at));
    requestAnimationFrame(() => { el?.focus(); el?.setSelectionRange(at + sym.length, at + sym.length); });
  };
  const filled = formulas.map((f) => f.trim()).filter(Boolean);

  const run = async () => {
    setBusy(true); setGuess({}); setChecked(false);
    let res;
    if (mode === 'table') res = await logicCheck({ op: 'truth_table', formulas: filled });
    else if (mode === 'equiv') res = filled.length < 2 ? { ok: false, error: { message: 'Give two formulas to compare.' } } : await logicCheck({ op: 'equivalence', a: filled[0], b: filled[1] });
    else {
      const all = await Promise.all(filled.map((f) => logicCheck({ op: 'classify', formula: f })));
      const bad = all.find((r) => !r.ok);
      res = bad || { ok: true, result: all.map((r) => r.result) };
    }
    setBusy(false);
    setOut(res.ok ? { mode, data: res.result } : { error: res.error });
  };

  const cycle = (key) => { setChecked(false); setGuess((g) => ({ ...g, [key]: g[key] === undefined ? true : g[key] === true ? false : undefined })); };
  const table = out?.mode === 'table' ? out.data : null;
  const total = table ? table.rows.length * table.formulas.length : 0;
  const right = table ? table.rows.reduce((n, r, ri) => n + r.results.filter((v, ci) => guess[`${ri}:${ci}`] === v).length, 0) : 0;

  return (
    <div className="stack">
      <div className="phx-modes" role="group" aria-label="Truth table mode">
        {MODES.map((m) => (
          <button key={m.id} type="button" className={`btn btn-sm ${mode === m.id ? 'btn-primary' : 'btn-quiet'}`} aria-pressed={mode === m.id}
            onClick={() => { setMode(m.id); setOut(null); }}>{m.label}</button>
        ))}
      </div>
      <p className="hint">{MODES.find((m) => m.id === mode).hint} Write ~ & | -&gt; &lt;-&gt; (or ¬ ∧ ∨ → ↔). Letters start with a capital.</p>
      {formulas.map((f, i) => (
        <div key={i} className="phx-formula-row">
          <input ref={(el) => { inputs.current[i] = el; }} className="input phx-mono" aria-label={`Formula ${i + 1}`} value={f} maxLength={200}
            spellCheck={false} onFocus={() => { active.current = i; }} onChange={(e) => setAt(i, e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && filled.length) run(); }} />
          {formulas.length > 1 && <button type="button" className="btn btn-quiet btn-sm" onClick={() => setFormulas((x) => x.filter((_, j) => j !== i))}>Remove</button>}
        </div>
      ))}
      <div className="btn-row">
        <span className="hint">Insert:</span>
        {SYMBOLS.map((s) => <button key={s} type="button" className="btn btn-quiet btn-sm phx-sym" aria-label={`Insert ${s}`} onClick={() => insert(s)}>{s}</button>)}
        {formulas.length < 3 && <button type="button" className="btn btn-quiet btn-sm" onClick={() => setFormulas((f) => [...f, ''])}>Add a formula</button>}
      </div>
      <div className="btn-row">
        <span className="hint">Examples:</span>
        {EXAMPLES.map((ex) => <button key={ex.join('|')} type="button" className="btn btn-quiet btn-sm phx-mono" onClick={() => { setFormulas(ex); setOut(null); }}>{ex.join('  ,  ')}</button>)}
      </div>
      <div className="btn-row">
        <button type="button" className="btn btn-primary" disabled={!filled.length || busy} onClick={run}>{busy ? 'Checking…' : 'Check'}</button>
      </div>

      {out?.error && <p className="notice notice-bad" role="alert">{out.error.message}</p>}
      <div aria-live="polite" className="stack">
        {out?.mode === 'classify' && out.data.map((d) => (
          <div key={d.formula} className="panel stack-sm">
            <p><code className="phx-mono">{d.formula}</code>: <strong>{KIND[d.kind]}</strong></p>
            {d.true_row && <p className="hint">True when {rowText(d.true_row)}.</p>}
            {d.false_row && <p className="hint">False when {rowText(d.false_row)}.</p>}
          </div>
        ))}
        {out?.mode === 'equiv' && (
          <p className={`notice ${out.data.equivalent ? 'notice-ok' : 'notice-bad'}`}>
            {out.data.equivalent ? 'Equivalent: the two formulas have the same truth value in every row.'
              : `Not equivalent. They differ when ${rowText(out.data.counterexample)}.`}
          </p>
        )}
        {table && (
          <>
            <div className="btn-row">
              <label className="phx-check"><input type="checkbox" checked={practice} onChange={(e) => { setPractice(e.target.checked); setGuess({}); setChecked(false); }} /> Fill the cells myself</label>
              {practice && (
                <>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => setChecked(true)}><Check size={14} aria-hidden="true" /> Check my cells</button>
                  <button type="button" className="btn btn-quiet btn-sm" onClick={() => { setGuess({}); setChecked(false); }}><Eraser size={14} aria-hidden="true" /> Clear</button>
                </>
              )}
              {practice && checked && <span className="hint" role="status">{right} of {total} cells match the engine.</span>}
            </div>
            <div className="phx-table-wrap">
              <table className="phx-table">
                <thead>
                  <tr>
                    {table.vars.map((v) => <th key={v} scope="col" className="phx-mono">{v}</th>)}
                    {table.formulas.map((f) => <th key={f} scope="col" className="phx-mono phx-out">{f}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {table.rows.map((r, ri) => (
                    <tr key={ri}>
                      {table.vars.map((v) => <td key={v}>{tf(r.values[v])}</td>)}
                      {r.results.map((val, ci) => {
                        if (!practice) return <td key={ci} className={`phx-out ${val ? 'phx-t' : 'phx-f'}`}>{tf(val)}</td>;
                        const g = guess[`${ri}:${ci}`];
                        const cls = checked ? (g === val ? 'phx-right' : 'phx-wrong') : '';
                        return (
                          <td key={ci} className={`phx-out ${cls}`}>
                            <button type="button" className="phx-cell" aria-label={`Row ${ri + 1}, ${table.formulas[ci]}: ${g === undefined ? 'blank' : tf(g)}${checked ? (g === val ? ', matches' : ', does not match') : ''}`}
                              onClick={() => cycle(`${ri}:${ci}`)}>{g === undefined ? '·' : tf(g)}</button>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!practice && table.formulas.length > 1 && table.rows.every((r) => r.results.every((v) => v === r.results[0])) && (
              <p className="notice notice-info">All the output columns agree in every row: the formulas are equivalent.</p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
