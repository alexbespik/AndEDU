// STEM kit practice bodies (ee, ai, systems, stats, bio: practice_ee.py, practice_ai.py, practice_systems.py,
// practice_stats.py, practice_bio.py). The answer key never reaches the browser, so every body collects a submission
// and has the server grade it (./serverGrade.js); a body only reads the public fields of its item (givens), never a
// field a grader compares against. Same contract as ./registry.js: each body takes {item, onResult(ok, given), retry}.
import React, { useId, useMemo, useRef, useState } from 'react';
import { Check, Loader2, RotateCcw } from 'lucide-react';
import Md from '../components/Md';
import { useServerGrade } from './serverGrade';
import '../styles/stem_kits.css';

// ---- shared helpers

const arr = (v) => (Array.isArray(v) ? v : []);
const show = (v) => (Array.isArray(v) ? `[${v.map(show).join(', ')}]` : String(v ?? ''));

/** "0.25", "-3", "1/3" -> number, anything else (including empty) -> null. */
function toNum(s) {
  const t = String(s ?? '').trim();
  if (!t) return null;
  const frac = /^(-?\d*\.?\d+)\s*\/\s*(-?\d*\.?\d+)$/.exec(t);
  if (frac) { const d = Number(frac[2]); return d === 0 ? null : Number(frac[1]) / d; }
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}
const toInt = (s) => { const n = toNum(s); return n !== null && Number.isInteger(n) ? n : null; };
const blankGrid = (r, c) => Array.from({ length: r }, () => Array.from({ length: c }, () => ''));
const gridNums = (g) => g.map((row) => row.map(toNum));
const gridReady = (nums) => nums.length > 0 && nums.every((row) => row.length > 0 && row.every((v) => v !== null));

/** The check button, the verdict and Try again around a body's inputs. `submission` is null until the inputs are
 * complete. Inputs are disabled once a check came back (a network error leaves them open). */
function Kit({ item, onResult, retry = true, submission, children }) {
  const { check, result, busy, reset } = useServerGrade(item, onResult);
  const locked = !!result && !result.error && result.ok;
  const partial = result && !result.ok && !result.error && result.score > 0 && result.score < 1;
  return (
    <div className="stack-sm">
      <fieldset className="stk-set" disabled={busy || locked}>{children}</fieldset>
      {!locked && (
        <div className="btn-row">
          <button type="button" className="btn btn-primary btn-sm" disabled={busy || submission === null}
            onClick={() => submission !== null && check(submission)}>
            {busy ? <Loader2 size={14} className="spin" aria-hidden="true" /> : <Check size={14} aria-hidden="true" />}
            {busy ? ' Checking…' : ' Check'}
          </button>
          {submission === null && <span className="hint">Fill in every field to check.</span>}
        </div>
      )}
      {result && (
        <div className={`feedback ${result.ok ? 'ok' : 'bad'}`} aria-live="polite">
          <p style={{ fontWeight: 700, marginBottom: 4 }}>
            {result.ok ? 'Correct.' : result.error ? 'Could not check.' : partial ? 'Partly right.' : 'Not quite.'}
          </p>
          {result.feedback && <p>{result.feedback}</p>}
          {result.ok && item.explanation && <Md>{item.explanation}</Md>}
          {!result.ok && retry && (
            <div className="btn-row" style={{ marginTop: 6 }}>
              <button type="button" className="btn btn-quiet btn-sm" onClick={reset}>
                <RotateCcw size={14} aria-hidden="true" /> Try again
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Given({ rows }) {
  const shown = rows.filter(([, v]) => v !== undefined && v !== null && v !== '');
  if (!shown.length) return null;
  return (
    <dl className="stk-given">
      {shown.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}
    </dl>
  );
}

function NumField({ label, value, onChange, unit, hint, placeholder }) {
  const id = useId();
  return (
    <div className="stk-field">
      <label htmlFor={id}>{label}</label>
      <div className="stk-unit">
        <input id={id} className="input stk-mono" inputMode="decimal" autoComplete="off" spellCheck={false}
          value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} aria-describedby={hint ? `${id}-h` : undefined} />
        {unit && <span>{unit}</span>}
      </div>
      {hint && <span className="hint" id={`${id}-h`}>{hint}</span>}
    </div>
  );
}

function TextField({ label, value, onChange, hint, placeholder, inputRef }) {
  const id = useId();
  return (
    <div className="stk-field" style={{ maxWidth: 420, flexBasis: 260 }}>
      <label htmlFor={id}>{label}</label>
      <input id={id} ref={inputRef} className="input stk-mono" autoComplete="off" autoCapitalize="off" spellCheck={false}
        value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} aria-describedby={hint ? `${id}-h` : undefined} />
      {hint && <span className="hint" id={`${id}-h`}>{hint}</span>}
    </div>
  );
}

/** Read-only matrix with optional row and column labels. */
function StaticMatrix({ caption, rows, rowLabels, colLabels }) {
  return (
    <div className="stk-table-wrap">
      <table className="stk-table">
        {caption && <caption>{caption}</caption>}
        {colLabels && <thead><tr>{rowLabels && <td />}{colLabels.map((c, j) => <th key={j} scope="col">{c}</th>)}</tr></thead>}
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {rowLabels && <th scope="row">{rowLabels[i]}</th>}
              {arr(row).map((v, j) => <td key={j}><span className="stk-static">{String(v)}</span></td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Editable matrix of text cells; `value` is a rows x cols grid of strings. */
function MatrixEditor({ caption, value, onChange, rowLabels, colLabels }) {
  const set = (i, j, v) => onChange(value.map((row, r) => (r === i ? row.map((c, k) => (k === j ? v : c)) : row)));
  return (
    <div className="stk-table-wrap">
      <table className="stk-table">
        {caption && <caption>{caption}</caption>}
        {colLabels && <thead><tr>{rowLabels && <td />}{colLabels.map((c, j) => <th key={j} scope="col">{c}</th>)}</tr></thead>}
        <tbody>
          {value.map((row, i) => (
            <tr key={i}>
              {rowLabels && <th scope="row">{rowLabels[i]}</th>}
              {row.map((cell, j) => (
                <td key={j}>
                  <input className="input stk-cell" inputMode="decimal" autoComplete="off" spellCheck={false} value={cell}
                    aria-label={`${caption || 'Matrix'}, row ${rowLabels ? rowLabels[i] : i + 1}, column ${colLabels ? colLabels[j] : j + 1}`}
                    onChange={(e) => set(i, j, e.target.value)} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const idx = (n, p) => Array.from({ length: n }, (_, i) => `${p}${i + 1}`);

// ---- ee

/** circuit_kcl_kvl: submission {value}. */
function CircuitKclKvl({ item, onResult, retry }) {
  const [v, setV] = useState('');
  const n = toNum(v);
  const diagram = String(item.circuit_diagram || '');
  const isSvg = /^\s*<svg[\s>]/i.test(diagram);  // drawn through <img>, so no script in it can run
  const isPath = /^\/(?!\/)[\w./-]+\.(svg|png|jpe?g|webp)$/i.test(diagram) && !diagram.includes('..');  // offline image in public/
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={n === null ? null : { value: n }}>
      {isSvg
        ? <img className="stk-diagram" alt="Circuit diagram" src={`data:image/svg+xml;utf8,${encodeURIComponent(diagram)}`} />
        : isPath ? <img className="stk-diagram" alt="Circuit diagram" src={diagram} />
          : diagram && <p className="stk-code">{diagram}</p>}
      {arr(item.equations).length > 0 && (
        <ul className="stk-lines" aria-label="Given equations">{item.equations.map((e, i) => <li key={i}>{e}</li>)}</ul>
      )}
      <div className="stk-fields">
        <NumField label={`Value of ${item.target_variable || 'the target'}`} unit={item.unit} value={v} onChange={setV} />
      </div>
    </Kit>
  );
}

/** bode_plot_analyzer: submission {cutoff_rad_s?, gain_margin_db?, phase_margin_deg?}, exactly the metrics in the
 * public item.ask list (older items without it offer all three and send the filled ones). */
const BODE_FIELDS = [
  ['cutoff_rad_s', 'Cutoff frequency', 'rad/s'], ['gain_margin_db', 'Gain margin', 'dB'], ['phase_margin_deg', 'Phase margin', 'degrees'],
];
function BodePlotAnalyzer({ item, onResult, retry }) {
  const asked = arr(item.ask).filter((k) => BODE_FIELDS.some(([key]) => key === k));
  const fields = asked.length ? BODE_FIELDS.filter(([k]) => asked.includes(k)) : BODE_FIELDS;
  const [f, setF] = useState({});
  const set = (k) => (val) => setF((s) => ({ ...s, [k]: val }));
  const sub = {};
  let bad = false;
  for (const [k] of fields) {
    const raw = String(f[k] || '').trim();
    if (!raw) { if (asked.length) bad = true; continue; }
    const n = toNum(raw);
    if (n === null) bad = true; else sub[k] = n;
  }
  const ready = !bad && Object.keys(sub).length > 0;
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={ready ? sub : null}>
      {item.transfer_function && <Given rows={[['H(s)', item.transfer_function]]} />}
      <div className="stk-fields">
        {fields.map(([k, label, unit]) => <NumField key={k} label={label} unit={unit} value={f[k] || ''} onChange={set(k)} />)}
      </div>
      {!asked.length && <p className="hint">Fill in every metric the question asks for; leave the others empty.</p>}
    </Kit>
  );
}

/** boolean_gate_minimization: submission {expression}, a sum of products such as A'B + AB'. */
function BooleanGateMinimization({ item, onResult, retry }) {
  const [expr, setExpr] = useState('');
  const ref = useRef(null);
  const vars = arr(item.variables);
  const insert = (text) => {
    const el = ref.current;
    const a = el?.selectionStart ?? expr.length;
    const b = el?.selectionEnd ?? expr.length;
    setExpr(expr.slice(0, a) + text + expr.slice(b));
    requestAnimationFrame(() => { el?.focus(); el?.setSelectionRange(a + text.length, a + text.length); });
  };
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={expr.trim() ? { expression: expr.trim() } : null}>
      <Given rows={[['Variables', vars.join(', ')], ['Minterms (rows where the output is 1)', arr(item.minterms).join(', ')]]} />
      <div className="stk-fields">
        <TextField label="Minimal sum of products" value={expr} onChange={setExpr} inputRef={ref} placeholder="A'B + AB'"
          hint="Use ' for NOT and + for OR; write the letters of each product in alphabetical order." />
      </div>
      <div className="stk-keys" aria-label="Insert a symbol">
        {[...vars, "'", ' + '].map((k) => (
          <button key={k} type="button" className="btn btn-quiet btn-sm" onClick={() => insert(k)} aria-label={`Insert ${k.trim() || 'space'}`}>{k.trim() || '+'}</button>
        ))}
      </div>
    </Kit>
  );
}

/** opamp_gain_calc: submission {vout}. */
function OpampGainCalc({ item, onResult, retry }) {
  const [v, setV] = useState('');
  const n = toNum(v);
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={n === null ? null : { vout: n }}>
      <Given rows={[
        ['Topology', String(item.topology || '').replace('_', '-')], ['R1', item.R1], ['Rf', item.Rf], ['Vin', item.Vin],
        ['Rails', item.Vsat_pos !== undefined ? `${item.Vsat_neg} V to ${item.Vsat_pos} V` : ''],
      ]} />
      <div className="stk-fields"><NumField label="Output voltage Vout" unit="V" value={v} onChange={setV} hint="The output cannot pass the supply rails." /></div>
    </Kit>
  );
}

// ---- ai

/** backprop_layer_step: submission {grad_W: rows x cols numbers, grad_b: numbers}; rows = len(delta), cols = len(X). */
function BackpropLayerStep({ item, onResult, retry }) {
  const X = arr(item.X), delta = arr(item.delta);
  const [w, setW] = useState(() => blankGrid(delta.length, X.length));
  const [b, setB] = useState(() => blankGrid(1, delta.length));
  const W = gridNums(w), B = gridNums(b)[0];
  const ready = gridReady(W) && B.every((x) => x !== null);
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={ready ? { grad_W: W, grad_b: B } : null}>
      <Given rows={[['x', show(X)], ['dL/dz', show(delta)], ['Activation', item.activation]]} />
      <MatrixEditor caption="dL/dW" value={w} onChange={setW} rowLabels={idx(delta.length, 'out ')} colLabels={idx(X.length, 'in ')} />
      <MatrixEditor caption="dL/db" value={b} onChange={setB} colLabels={idx(delta.length, 'out ')} />
    </Kit>
  );
}

/** attention_score_matrix: submission {weights: len(Q) x len(K) numbers}, each row a softmax of Q.K^T / sqrt(d_k). */
function AttentionScoreMatrix({ item, onResult, retry }) {
  const Q = arr(item.Q), K = arr(item.K);
  const [g, setG] = useState(() => blankGrid(Q.length, K.length));
  const W = gridNums(g);
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={gridReady(W) ? { weights: W } : null}>
      <StaticMatrix caption="Q (queries)" rows={Q} rowLabels={idx(Q.length, 'q')} />
      <StaticMatrix caption="K (keys)" rows={K} rowLabels={idx(K.length, 'k')} />
      <Given rows={[['d_k', item.d_k]]} />
      <MatrixEditor caption="Attention weights" value={g} onChange={setG} rowLabels={idx(Q.length, 'q')} colLabels={idx(K.length, 'k')} />
      <p className="hint">Each row should sum to 1.</p>
    </Kit>
  );
}

/** confusion_matrix_metrics: submission {precision, recall, f1, specificity}. */
function ConfusionMatrixMetrics({ item, onResult, retry }) {
  const [f, setF] = useState({ precision: '', recall: '', f1: '', specificity: '' });
  const set = (k) => (val) => setF((s) => ({ ...s, [k]: val }));
  const sub = Object.fromEntries(Object.entries(f).map(([k, s]) => [k, toNum(s)]));
  const ready = Object.values(sub).every((x) => x !== null);
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={ready ? sub : null}>
      <StaticMatrix caption="Confusion matrix" colLabels={['Predicted positive', 'Predicted negative']} rowLabels={['Actual positive', 'Actual negative']}
        rows={[[`TP = ${item.TP}`, `FN = ${item.FN}`], [`FP = ${item.FP}`, `TN = ${item.TN}`]]} />
      <div className="stk-fields">
        <NumField label="Precision" value={f.precision} onChange={set('precision')} />
        <NumField label="Recall" value={f.recall} onChange={set('recall')} />
        <NumField label="F1" value={f.f1} onChange={set('f1')} />
        <NumField label="Specificity" value={f.specificity} onChange={set('specificity')} />
      </div>
      <p className="hint">Give each as a fraction between 0 and 1 (for example 0.8 or 4/5).</p>
    </Kit>
  );
}

/** loss_gradient_verify: submission {loss, grad}: grad is dL/d(prediction) for mse and dL/d(logit) for cross_entropy
 * (the server's convention: prediction minus y). */
function LossGradientVerify({ item, onResult, retry }) {
  const [loss, setLoss] = useState('');
  const [grad, setGrad] = useState('');
  const l = toNum(loss), g = toNum(grad);
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={l === null || g === null ? null : { loss: l, grad: g }}>
      <Given rows={[['Loss', String(item.loss_type || '').replace('_', ' ')], ['y', item.y_true], ['prediction', item.y_pred]]} />
      <div className="stk-fields">
        <NumField label="Loss L" value={loss} onChange={setLoss} hint="Natural logarithm." />
        {String(item.loss_type || 'cross_entropy') === 'cross_entropy'
          ? <NumField label="Gradient dL/d(logit)" value={grad} onChange={setGrad} hint="With a sigmoid output this is prediction minus y." />
          : <NumField label="Gradient dL/d(prediction)" value={grad} onChange={setGrad} hint="L = ½ (prediction − y)²." />}
      </div>
    </Kit>
  );
}

// ---- systems

const ADDR = /^(0x[0-9a-f]+|\d+)$/i;

/** page_table_walk: submission {physical_address} as 0x hex or decimal. */
function PageTableWalk({ item, onResult, retry }) {
  const [pa, setPa] = useState('');
  const t = pa.trim();
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={ADDR.test(t) ? { physical_address: t } : null}>
      <Given rows={[['Virtual address', item.virtual_address], ['Page size', item.page_size_bytes ? `${item.page_size_bytes} bytes` : ''],
        ['Virtual page number', item.vpn], ['Mapped to physical page', item.ppn]]} />
      <div className="stk-fields">
        <TextField label="Physical address" value={pa} onChange={setPa} placeholder="0x…" hint="Hex with 0x, or decimal. Frame number times page size, plus the offset." />
      </div>
    </Kit>
  );
}

/** cache_tag_index_offset: submission {tag, index, offset}, each a bit count. */
function CacheTagIndexOffset({ item, onResult, retry }) {
  const [f, setF] = useState({ tag: '', index: '', offset: '' });
  const set = (k) => (val) => setF((s) => ({ ...s, [k]: val }));
  const sub = { tag: toInt(f.tag), index: toInt(f.index), offset: toInt(f.offset) };
  const ready = Object.values(sub).every((x) => x !== null && x >= 0);
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={ready ? sub : null}>
      <Given rows={[['Address', `${item.address_bits} bits`], ['Cache', `${item.cache_size_bytes} bytes`], ['Block', `${item.block_size_bytes} bytes`],
        ['Associativity', `${item.associativity_ways}-way`]]} />
      <div className="stk-fields">
        <NumField label="Tag" unit="bits" value={f.tag} onChange={set('tag')} />
        <NumField label="Index" unit="bits" value={f.index} onChange={set('index')} />
        <NumField label="Offset" unit="bits" value={f.offset} onChange={set('offset')} />
      </div>
    </Kit>
  );
}

const REG_OPS = new Set(['add', 'addi', 'addk', 'sub', 'slli', 'xor']);

/** assembly_reg_trace: submission {register: integer} for every register that starts non-empty or is written.
 * The register list is derived from the public instructions and initial_registers (the final state is secret). */
function AssemblyRegTrace({ item, onResult, retry }) {
  const names = useMemo(() => {
    const set = new Set(Object.keys(item.initial_registers || {}));
    for (const line of arr(item.instructions)) {
      const parts = String(line).replace(/,/g, ' ').split(/\s+/).filter(Boolean);
      if (parts.length >= 4 && REG_OPS.has(parts[0].toLowerCase())) set.add(parts[1]);
    }
    return [...set];
  }, [item]);
  const [vals, setVals] = useState({});
  const sub = {};
  let ready = names.length > 0;
  for (const r of names) {
    const n = toInt(vals[r] ?? '');
    if (n === null) ready = false; else sub[r] = n;
  }
  const init = Object.entries(item.initial_registers || {}).map(([k, v]) => `${k} = ${v}`).join(', ');
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={ready ? sub : null}>
      <Given rows={[['Initial registers', init]]} />
      <ol className="stk-lines" aria-label="Instructions">{arr(item.instructions).map((l, i) => <li key={i}>{l}</li>)}</ol>
      <div className="stk-fields">
        {names.map((r) => <NumField key={r} label={`${r} at the end`} value={vals[r] ?? ''} onChange={(v) => setVals((s) => ({ ...s, [r]: v }))} />)}
      </div>
    </Kit>
  );
}

/** deadlock_bankers: submission {is_safe, sequence?}; sequence = process indexes (0-based) in a safe order,
 * sent only when the state is called safe. */
function DeadlockBankers({ item, onResult, retry }) {
  const alloc = arr(item.allocation), maxc = arr(item.max_claim), avail = arr(item.available);
  const [safe, setSafe] = useState(null);
  const [seq, setSeq] = useState([]);
  const need = alloc.map((row, i) => arr(row).map((a, j) => (Number(arr(maxc[i])[j]) || 0) - (Number(a) || 0)));
  const res = idx(avail.length, 'R').map((_, j) => `R${j}`);
  const procs = alloc.map((_, i) => `P${i}`);
  const pick = (i) => setSeq((s) => (s.includes(i) ? s.filter((x) => x !== i) : [...s, i]));
  const sub = safe === null ? null : safe ? (seq.length === alloc.length ? { is_safe: true, sequence: seq } : null) : { is_safe: false };
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={sub}>
      <StaticMatrix caption="Allocation" rows={alloc} rowLabels={procs} colLabels={res} />
      <StaticMatrix caption="Max claim" rows={maxc} rowLabels={procs} colLabels={res} />
      <StaticMatrix caption="Need (max minus allocation)" rows={need} rowLabels={procs} colLabels={res} />
      <Given rows={[['Available', show(avail)]]} />
      <div role="group" aria-label="Is the state safe?" className="stk-choice">
        <button type="button" className="stk-pick" aria-pressed={safe === true} onClick={() => setSafe(true)}>Safe</button>
        <button type="button" className="stk-pick" aria-pressed={safe === false} onClick={() => { setSafe(false); setSeq([]); }}>Unsafe (deadlock possible)</button>
      </div>
      {safe === true && (
        <div className="stack-sm">
          <p className="hint">Tap the processes in a safe finishing order; tap one again to take it out.</p>
          <div role="group" aria-label="Processes" className="stk-choice">
            {procs.map((p, i) => <button key={p} type="button" className="stk-pick" aria-pressed={seq.includes(i)} onClick={() => pick(i)}>{p}</button>)}
          </div>
          <p className="stk-order" aria-live="polite">Order: {seq.length ? seq.map((i) => procs[i]).join(' → ') : 'none yet'}</p>
        </div>
      )}
    </Kit>
  );
}

// ---- stats

/** hypothesis_test_two_sample: submission {test_statistic, reject_null}. */
function HypothesisTestTwoSample({ item, onResult, retry }) {
  const [z, setZ] = useState('');
  const [rej, setRej] = useState(null);
  const n = toNum(z);
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={n === null || rej === null ? null : { test_statistic: n, reject_null: rej }}>
      <StaticMatrix colLabels={['Mean', 'Std dev', 'n']} rowLabels={['Sample 1', 'Sample 2']}
        rows={[[item.mean1, item.std1, item.n1], [item.mean2, item.std2, item.n2]]} />
      <Given rows={[['Test', item.test === 'z' || !item.test ? 'Two-sample z test, two-sided' : item.test],
        ['Significance level', item.alpha], ...(item.critical_value != null ? [['Critical |z|', item.critical_value]] : [])]} />
      <div className="stk-fields">
        <NumField label="Test statistic z" value={z} onChange={setZ} hint="(mean 1 minus mean 2) over the standard error." />
      </div>
      <div role="group" aria-label="Decision" className="stk-choice">
        <button type="button" className="stk-pick" aria-pressed={rej === true} onClick={() => setRej(true)}>Reject the null</button>
        <button type="button" className="stk-pick" aria-pressed={rej === false} onClick={() => setRej(false)}>Fail to reject</button>
      </div>
    </Kit>
  );
}

/** bayes_posterior_update: submission {posterior} in [0, 1]. */
function BayesPosteriorUpdate({ item, onResult, retry }) {
  const [v, setV] = useState('');
  const n = toNum(v);
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={n === null ? null : { posterior: n }}>
      <Given rows={[['Prior P(H)', item.prior], ['P(E | H)', item.sensitivity], ['P(E | not H)', item.false_positive_rate]]} />
      <div className="stk-fields"><NumField label="Posterior P(H | E)" value={v} onChange={setV} hint="A probability between 0 and 1; fractions such as 3/8 work." /></div>
    </Kit>
  );
}

/** mle_parameter_derivation: submission {estimate}. */
function MleParameterDerivation({ item, onResult, retry }) {
  const [v, setV] = useState('');
  const n = toNum(v);
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={n === null ? null : { estimate: n }}>
      <Given rows={[['Distribution', String(item.distribution || '').replace('_', ' ')], ['Samples', arr(item.samples).join(', ')]]} />
      <div className="stk-fields"><NumField label="Maximum likelihood estimate" value={v} onChange={setV} /></div>
    </Kit>
  );
}

/** markov_steady_state: submission {steady_state: [pi_1, ..., pi_n]} (n = size of the transition matrix). */
function MarkovSteadyState({ item, onResult, retry }) {
  const P = arr(item.transition_matrix);
  const n = P.length;
  const [pi, setPi] = useState(() => Array.from({ length: n }, () => ''));
  const nums = pi.map(toNum);
  const states = idx(n, 'S');
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={n > 0 && nums.every((x) => x !== null) ? { steady_state: nums } : null}>
      <StaticMatrix caption="Transition matrix P (row = from, column = to)" rows={P} rowLabels={states} colLabels={states} />
      <div className="stk-fields">
        {pi.map((v, i) => (
          <NumField key={i} label={`Steady state of ${states[i]}`} value={v} onChange={(x) => setPi((s) => s.map((c, k) => (k === i ? x : c)))} />
        ))}
      </div>
      <p className="hint">The vector pi with pi P = pi; its entries sum to 1.</p>
    </Kit>
  );
}

// ---- bio

/** smith_waterman_align: submission {max_score} (integer). A scratch grid is offered for the DP table; it is not sent. */
function SmithWatermanAlign({ item, onResult, retry }) {
  const s1 = String(item.seq1 || ''), s2 = String(item.seq2 || '');
  const [v, setV] = useState('');
  const [grid, setGrid] = useState(() => blankGrid(s1.length, s2.length));
  const [open, setOpen] = useState(false);
  const n = toInt(v);
  const best = gridNums(grid).flat().filter((x) => x !== null);
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={n === null ? null : { max_score: n }}>
      <p className="stk-seq" aria-label={`Sequences ${s1} and ${s2}`}>{s1}<br />{s2}</p>
      <Given rows={[['Match', `+${item.match_score}`], ['Mismatch', `-${item.mismatch_penalty}`], ['Gap', `-${item.gap_penalty}`]]} />
      <div className="btn-row">
        <button type="button" className="btn btn-quiet btn-sm" aria-expanded={open} onClick={() => setOpen((o) => !o)}>{open ? 'Hide' : 'Show'} scratch table</button>
        {open && best.length > 0 && <button type="button" className="btn btn-quiet btn-sm" onClick={() => setV(String(Math.max(...best)))}>Use the largest cell</button>}
      </div>
      {open && s1 && s2 && (
        <MatrixEditor caption="Scratch DP table (not graded)" value={grid} onChange={setGrid} rowLabels={s1.split('')} colLabels={s2.split('')} />
      )}
      <div className="stk-fields"><NumField label="Best local alignment score" value={v} onChange={setV} /></div>
    </Kit>
  );
}

/** orf_finder_translate: submission {protein}, one-letter amino acids of the longest forward ORF (no stop symbol). */
function OrfFinderTranslate({ item, onResult, retry }) {
  const [p, setP] = useState('');
  const t = p.trim().toUpperCase().replace(/\*/g, '');
  const dna = String(item.dna_sequence || '');
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={/^[A-Z]+$/.test(t) ? { protein: t } : null}>
      <p className="stk-seq" aria-label="DNA sequence">{dna.match(/.{1,3}/g)?.join(' ')}</p>
      <div className="stk-fields">
        <TextField label="Protein" value={p} onChange={setP} placeholder="MKV…" hint="One-letter codes for the longest open reading frame on this strand: ATG to the first in-frame stop (leave the stop out)." />
      </div>
    </Kit>
  );
}

/** restriction_digest_mapper: submission {fragments: [integers]} in any order. */
function RestrictionDigestMapper({ item, onResult, retry }) {
  const [txt, setTxt] = useState('');
  const parts = txt.split(/[\s,;]+/).filter(Boolean);
  const ok = parts.length > 0 && parts.every((x) => /^\d+$/.test(x));
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={ok ? { fragments: parts.map(Number) } : null}>
      <Given rows={[['DNA', `${item.circular === false ? 'linear' : 'circular'}, ${item.total_length_bp} bp`], ['Cuts at', arr(item.cleavage_sites).join(', ')]]} />
      <div className="stk-fields">
        <TextField label="Fragment sizes (bp)" value={txt} onChange={setTxt} placeholder="1200, 800, 300" hint="Separate with commas or spaces; any order." />
      </div>
    </Kit>
  );
}

/** phylogenetic_upgma_step: submission {pair: [taxon, taxon]}, the two taxa UPGMA merges first. */
function PhylogeneticUpgmaStep({ item, onResult, retry }) {
  const taxa = arr(item.taxa), M = arr(item.distance_matrix);
  const [pair, setPair] = useState(null);  // [i, j] with i < j
  const choose = (i, j) => setPair((p) => (p && p[0] === i && p[1] === j ? null : [i, j]));
  return (
    <Kit item={item} onResult={onResult} retry={retry} submission={pair ? { pair: [taxa[pair[0]], taxa[pair[1]]] } : null}>
      <p className="hint">Tap the cell of the two taxa UPGMA joins first (the smallest distance).</p>
      <div className="stk-table-wrap">
        <table className="stk-table">
          <caption>Distance matrix</caption>
          <thead><tr><td />{taxa.map((t) => <th key={t} scope="col">{t}</th>)}</tr></thead>
          <tbody>
            {taxa.map((a, i) => (
              <tr key={a}>
                <th scope="row">{a}</th>
                {taxa.map((b, j) => (
                  <td key={b}>
                    {j > i ? (
                      <button type="button" className="stk-pick" aria-pressed={!!pair && pair[0] === i && pair[1] === j}
                        aria-label={`${a} and ${b}, distance ${arr(M[i])[j]}`} onClick={() => choose(i, j)}>{String(arr(M[i])[j])}</button>
                    ) : <span className="stk-static" aria-hidden="true">{i === j ? '0' : ''}</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="stk-order" aria-live="polite">Merge: {pair ? `${taxa[pair[0]]} + ${taxa[pair[1]]}` : 'none chosen'}</p>
    </Kit>
  );
}

export const STEM_KITS_RENDER = {
  circuit_kcl_kvl: CircuitKclKvl, bode_plot_analyzer: BodePlotAnalyzer, boolean_gate_minimization: BooleanGateMinimization, opamp_gain_calc: OpampGainCalc,
  backprop_layer_step: BackpropLayerStep, attention_score_matrix: AttentionScoreMatrix, confusion_matrix_metrics: ConfusionMatrixMetrics, loss_gradient_verify: LossGradientVerify,
  page_table_walk: PageTableWalk, cache_tag_index_offset: CacheTagIndexOffset, assembly_reg_trace: AssemblyRegTrace, deadlock_bankers: DeadlockBankers,
  hypothesis_test_two_sample: HypothesisTestTwoSample, bayes_posterior_update: BayesPosteriorUpdate, mle_parameter_derivation: MleParameterDerivation, markov_steady_state: MarkovSteadyState,
  smith_waterman_align: SmithWatermanAlign, orf_finder_translate: OrfFinderTranslate, restriction_digest_mapper: RestrictionDigestMapper, phylogenetic_upgma_step: PhylogeneticUpgmaStep,
};

export const STEM_KITS_LABEL = {
  circuit_kcl_kvl: 'Circuit analysis (KCL / KVL)', bode_plot_analyzer: 'Bode plot', boolean_gate_minimization: 'Minimize the Boolean expression', opamp_gain_calc: 'Op-amp output',
  backprop_layer_step: 'Backprop step', attention_score_matrix: 'Attention weights', confusion_matrix_metrics: 'Confusion matrix metrics', loss_gradient_verify: 'Loss and gradient',
  page_table_walk: 'Page table walk', cache_tag_index_offset: 'Cache tag, index, offset', assembly_reg_trace: 'Register trace', deadlock_bankers: "Banker's algorithm",
  hypothesis_test_two_sample: 'Two-sample test', bayes_posterior_update: 'Bayes update', mle_parameter_derivation: 'Maximum likelihood', markov_steady_state: 'Markov steady state',
  smith_waterman_align: 'Smith-Waterman score', orf_finder_translate: 'Find the ORF and translate', restriction_digest_mapper: 'Restriction digest', phylogenetic_upgma_step: 'UPGMA merge step',
};
