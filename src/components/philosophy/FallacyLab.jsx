import React, { useEffect, useId, useState } from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';
import { logicCheck, rowText } from './engine';
import { FORMAL_EXAMPLES, INFORMAL } from './fallacyData';
import '../../styles/philosophy.css';

const PROP_PLACEHOLDER = 'One premise per line, e.g.\nP -> Q\nQ';

function ArgumentForms() {
  const uid = useId();
  const [premises, setPremises] = useState(FORMAL_EXAMPLES[0].premises.join('\n'));
  const [conclusion, setConclusion] = useState(FORMAL_EXAMPLES[0].conclusion);
  const [out, setOut] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const list = premises.split('\n').map((p) => p.trim()).filter(Boolean);

  const run = async () => {
    setBusy(true); setError(null);
    const res = await logicCheck({ op: 'forms', premises: list, conclusion });
    setBusy(false);
    if (res.ok) setOut(res.result); else { setOut(null); setError(res.error.message); }
  };
  const load = (ex) => { setPremises(ex.premises.join('\n')); setConclusion(ex.conclusion); setOut(null); setError(null); };

  return (
    <section className="panel stack" aria-labelledby={`${uid}-h`}>
      <h2 id={`${uid}-h`}>Formal fallacies in a conditional or either/or argument</h2>
      <p className="hint">A formal fallacy is a shape that is invalid whatever the statements mean. The engine matches the shape by its form, with any
        letters or whole sentences in place of the letters, and tests validity with a truth table. Write ~ & | -&gt; &lt;-&gt;.</p>
      <div className="btn-row">
        {FORMAL_EXAMPLES.map((ex) => <button key={ex.label} type="button" className="btn btn-quiet btn-sm" onClick={() => load(ex)}>{ex.label}</button>)}
      </div>
      <div className="phx-grid">
        <div className="field">
          <label htmlFor={`${uid}-p`}>Premises</label>
          <textarea id={`${uid}-p`} className="textarea phx-mono" rows={4} spellCheck={false} placeholder={PROP_PLACEHOLDER} value={premises}
            onChange={(e) => { setPremises(e.target.value); setOut(null); }} />
        </div>
        <div className="field">
          <label htmlFor={`${uid}-c`}>Conclusion</label>
          <input id={`${uid}-c`} className="input phx-mono" spellCheck={false} value={conclusion} onChange={(e) => { setConclusion(e.target.value); setOut(null); }} />
        </div>
      </div>
      <div className="btn-row">
        <button type="button" className="btn btn-primary" disabled={!list.length || !conclusion.trim() || busy} onClick={run}>{busy ? 'Checking…' : 'Check the form'}</button>
      </div>
      {error && <p className="notice notice-bad" role="alert">{error}</p>}
      {out && (
        <div className="stack-sm" aria-live="polite">
          <p className={`notice ${out.valid ? 'notice-ok' : 'notice-bad'}`}>
            {out.valid ? <CheckCircle2 size={14} aria-hidden="true" /> : <XCircle size={14} aria-hidden="true" />}{' '}
            {out.valid ? 'Valid: the conclusion is true in every row where the premises are true.'
              : `Invalid: when ${rowText(out.counterexample)}, the premises are true and the conclusion is false.`}
          </p>
          {out.matches.length ? out.matches.map((m) => (
            <p key={m.id}>
              <span className={`chip phx-kind-${m.kind}`}>{m.kind === 'fallacy' ? 'Formal fallacy' : 'Valid form'}</span> <strong>{m.name}</strong>
              <span className="hint"> with {Object.entries(m.binding).map(([k, v]) => `${k} = ${v}`).join(', ')}</span>
              {m.note && <span className="hint"> {m.note}</span>}
            </p>
          )) : <p className="hint">No named form matched. That does not mean the argument is good: the truth-table verdict above still applies.</p>}
        </div>
      )}
    </section>
  );
}

const KINDS = ['A', 'E', 'I', 'O'];

function SyllogismRules() {
  const uid = useId();
  const [mood, setMood] = useState(['A', 'A', 'A']);
  const [figure, setFigure] = useState(2);
  const [reading, setReading] = useState('boolean');
  const [res, setRes] = useState(null);
  const form = `${mood.join('')}-${figure}`;
  useEffect(() => {
    let live = true;
    logicCheck({ op: 'syllogism', form, reading }).then((r) => { if (live) setRes(r.ok ? r.result : null); });
    return () => { live = false; };
  }, [form, reading]);
  return (
    <section className="panel stack" aria-labelledby={`${uid}-h`}>
      <h2 id={`${uid}-h`}>Syllogism rule breaks</h2>
      <p className="hint">Undistributed middle, illicit major or minor, exclusive premises and the existential fallacy are named by the engine for any
        mood and figure. Try AAA-2 or EAO-1 under the boolean reading.</p>
      <div className="phx-grid">
        {['Major premise', 'Minor premise', 'Conclusion'].map((t, i) => (
          <div className="field" key={t}>
            <label htmlFor={`${uid}-k${i}`}>{t}</label>
            <select id={`${uid}-k${i}`} className="select" value={mood[i]} onChange={(e) => setMood((m) => m.map((x, j) => (j === i ? e.target.value : x)))}>
              {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
          </div>
        ))}
        <div className="field">
          <label htmlFor={`${uid}-f`}>Figure</label>
          <select id={`${uid}-f`} className="select" value={figure} onChange={(e) => setFigure(Number(e.target.value))}>
            {[1, 2, 3, 4].map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${uid}-r`}>Reading</label>
          <select id={`${uid}-r`} className="select" value={reading} onChange={(e) => setReading(e.target.value)}>
            <option value="boolean">Boolean</option>
            <option value="aristotelian">Aristotelian</option>
          </select>
        </div>
      </div>
      {res && (
        <div className="stack-sm" aria-live="polite">
          <p className={`notice ${res.valid ? 'notice-ok' : 'notice-bad'}`}><strong>{res.form}{res.name ? ` (${res.name})` : ''}</strong> is {res.valid ? 'valid' : 'invalid'}.</p>
          {res.violations.map((v) => <p key={v.rule}><span className="chip phx-kind-fallacy">Formal fallacy</span> <code>{v.rule}</code> {v.message}</p>)}
        </div>
      )}
    </section>
  );
}

function InformalCatalog() {
  return (
    <section className="stack" aria-labelledby="phx-informal-h">
      <h2 id="phx-informal-h">Informal fallacies: a catalog to think with</h2>
      <p className="notice notice-info">Informal fallacies depend on meaning, context and purpose, so no program (and no checker in this app) can reliably
        say that a text commits one. Treat each entry as a question to ask of an argument, not as a verdict. Every pattern below has fair uses.</p>
      <div className="phx-cards">
        {INFORMAL.map((f) => (
          <details key={f.id} className="panel phx-card">
            <summary><strong>{f.name}</strong></summary>
            <div className="stack-sm">
              <p>{f.definition}</p>
              <p className="phx-example"><span className="label">Example: </span>{f.example}</p>
              <p><span className="label">When the same shape is fair: </span>{f.legitimate}</p>
              <p><span className="label">How to repair it: </span>{f.repair}</p>
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}

export default function FallacyLab() {
  return (
    <div className="stack">
      <ArgumentForms />
      <SyllogismRules />
      <InformalCatalog />
    </div>
  );
}
