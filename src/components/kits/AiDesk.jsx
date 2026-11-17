import React, { useEffect, useId, useState } from 'react';
import { Bar, DeskCard, Outcome, RunButton, pct, useTool } from './common';
import { Choice, Field, Legend, Plot, Presets, fmt, intRows, nums, rows, useAutoRun } from './stemCommon';

const MATRIX_EXAMPLES = {
  binary: { label: 'Binary (TP 40, FN 20, FP 10, TN 30)', text: '40 20\n10 30' },
  three: { label: 'Three classes', text: '50 3 2\n5 40 5\n2 8 35' },
};

function ConfusionGrid({ matrix, labels }) {
  const name = (i) => (labels?.[i] ?? i);
  const max = Math.max(1, ...matrix.flat());
  const k = matrix.length;
  return (
    <div className="kt-scroll">
      <table className="kt-table kt-matrix">
        <caption className="kt-sr">Confusion matrix: rows are the actual class, columns the predicted class</caption>
        <thead>
          <tr><th scope="col"><span className="kt-sr">Actual</span></th>{matrix.map((_, j) => <th key={j} scope="col">predicted {name(j)}</th>)}</tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i}>
              <th scope="row">actual {name(i)}</th>
              {row.map((v, j) => (
                <td key={j} className={`kt-heat ${i === j ? 'kt-heat-ok' : 'kt-heat-bad'}`} style={{ '--kt-heat': v / max }}>
                  {v}
                  {k === 2 && <span className="kt-sub"> {['TP', 'FN', 'FP', 'TN'][i * 2 + j]}</span>}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MetricsResult({ r, binary }) {
  return (
    <>
      <ConfusionGrid matrix={r.matrix} labels={r.per_class.map((c) => c.label)} />
      <div className="kt-bars" role="group" aria-label="Summary scores">
        <Bar label="Accuracy" value={r.accuracy} text={pct(r.accuracy)} />
        <Bar label="Macro F1" value={r.macro_f1} text={fmt(r.macro_f1)} tone="kt-alt" />
        <Bar label="Weighted F1" value={r.weighted_f1} text={fmt(r.weighted_f1)} tone="kt-alt" />
        <Bar label="Micro F1" value={r.micro_f1} text={fmt(r.micro_f1)} tone="kt-alt" />
      </div>
      <div className="kt-scroll">
        <table className="kt-table">
          <caption className="kt-sr">Scores per class</caption>
          <thead><tr><th scope="col">Class</th><th scope="col">Precision</th><th scope="col">Recall</th><th scope="col">F1</th><th scope="col">Specificity</th><th scope="col">Support</th></tr></thead>
          <tbody>
            {r.per_class.map((c, i) => (
              <tr key={i}><th scope="row">{c.label ?? i}{binary && i === 0 ? ' (positive)' : ''}</th><td>{fmt(c.precision)}</td><td>{fmt(c.recall)}</td><td>{fmt(c.f1)}</td><td>{fmt(c.specificity)}</td><td>{c.support}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint">Cohen's kappa: <strong>{fmt(r.kappa)}</strong> (agreement beyond chance; 0 = chance, 1 = perfect).{r.mcc != null && <> Matthews correlation: <strong>{fmt(r.mcc)}</strong> (a single balanced score for two classes, -1 to 1).</>}</p>
      <details>
        <summary>What the scores mean</summary>
        <ul className="kt-list">
          <li><strong>Precision</strong>: of everything predicted as this class, how much really is.</li>
          <li><strong>Recall</strong>: of everything that really is this class, how much was found.</li>
          <li><strong>F1</strong>: the harmonic mean of precision and recall.</li>
          <li><strong>Specificity</strong>: of everything that is not this class, how much was correctly left out.</li>
        </ul>
      </details>
    </>
  );
}

const SCORE_EXAMPLE = { labels: '1, 1, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1', scores: '0.92, 0.85, 0.80, 0.74, 0.66, 0.61, 0.52, 0.41, 0.38, 0.30, 0.22, 0.12' };

function MetricsDesk() {
  const [mode, setMode] = useState('matrix');
  const [matrixText, setMatrixText] = useState(MATRIX_EXAMPLES.binary.text);
  const [labels, setLabels] = useState(SCORE_EXAMPLE.labels);
  const [scores, setScores] = useState(SCORE_EXAMPLE.scores);
  const [threshold, setThreshold] = useState(0.5);
  const [localError, setLocalError] = useState('');
  const [runKey, setRunKey] = useState(0);
  const [state, run] = useTool('ai');
  const id = useId();

  const submit = (m = mode) => {
    setLocalError('');
    try {
      if (m === 'matrix') return run('metrics', { matrix: intRows(matrixText, 'Matrix') }, 'matrix');
      const l = nums(labels, 'Labels');
      const s = nums(scores, 'Scores');
      if (l.some((v) => v !== 0 && v !== 1)) throw new Error('Labels must be 0 or 1.');
      if (l.length !== s.length) throw new Error(`There are ${l.length} labels but ${s.length} scores; they must match one for one.`);
      return run('metrics', { labels: l, scores: s, threshold }, 'scores');
    } catch (e) {
      setLocalError(e.message);
      return null;
    }
  };
  useAutoRun(() => submit(), [mode, threshold]);
  useEffect(() => { if (runKey) submit(); }, [runKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // the live point on the ROC curve: positives are scores at or above the threshold
  const livePoint = () => {
    try {
      const l = nums(labels, 'Labels'); const s = nums(scores, 'Scores');
      const P = l.filter((v) => v === 1).length; const N = l.length - P;
      if (!P || !N || l.length !== s.length) return null;
      const tp = l.filter((v, i) => v === 1 && s[i] >= threshold).length;
      const fp = l.filter((v, i) => v === 0 && s[i] >= threshold).length;
      return { x: fp / N, y: tp / P };
    } catch { return null; }
  };

  return (
    <DeskCard title="Classifier scores" what="Judges a classifier from its errors: precision, recall, F1, kappa and more from a confusion matrix, or the ROC curve and AUC from raw scores.">
      <Choice label="Input" value={mode} onChange={setMode} options={[['matrix', 'Confusion matrix'], ['scores', 'Scores and a threshold (ROC)']]} />
      {mode === 'matrix' ? (
        <>
          <Presets items={Object.values(MATRIX_EXAMPLES).map((m) => ({ label: m.label, apply: () => { setMatrixText(m.text); setRunKey((k) => k + 1); } }))} />
          <Field label="Confusion matrix (rows = actual, columns = predicted; one row per line)" hint="For two classes, class 0 is the positive class: the top-left number is the true positives.">
            {(i) => <textarea id={i} className="kt-input kt-mono" rows={4} spellCheck={false} value={matrixText} onChange={(e) => setMatrixText(e.target.value)} />}
          </Field>
          <div className="btn-row"><RunButton loading={state.loading} onClick={() => submit()}>Compute the scores</RunButton></div>
        </>
      ) : (
        <>
          <div className="kt-two">
            <Field label="True labels (1 = positive, 0 = negative)">{(i) => <textarea id={i} className="kt-input kt-mono" rows={3} value={labels} onChange={(e) => setLabels(e.target.value)} />}</Field>
            <Field label="Model scores (higher = more likely positive)">{(i) => <textarea id={i} className="kt-input kt-mono" rows={3} value={scores} onChange={(e) => setScores(e.target.value)} />}</Field>
          </div>
          <div className="field">
            <label htmlFor={`${id}-t`}>Decision threshold: {threshold.toFixed(2)} (a score at or above it is called positive)</label>
            <input id={`${id}-t`} type="range" min="0" max="1" step="0.01" value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} />
          </div>
          <div className="btn-row"><RunButton loading={state.loading} onClick={() => submit()}>Compute</RunButton></div>
        </>
      )}
      {localError && <div className="notice notice-bad" role="alert">{localError}</div>}
      <Outcome state={state} render={(r) => {
        const live = state.tag === 'scores' ? livePoint() : null;
        return (
          <>
            {r.roc && (
              <>
                <h3 className="kt-h3">ROC curve</h3>
                <p className="hint">Each point is one threshold: how many real positives it catches (true positive rate) against how many negatives it wrongly flags (false positive rate). The dashed line is guessing. Area under the curve (AUC): <strong>{fmt(r.auc)}</strong> (1 = perfect ranking, 0.5 = no better than chance).</p>
                <Plot title="ROC curve: true positive rate against false positive rate" xLabel="false positive rate" yLabel="true positive rate" xDomain={[0, 1]} yDomain={[0, 1.02]}
                  series={[{ points: [{ x: 0, y: 0 }, { x: 1, y: 1 }], tone: 't4', dashed: true }, { points: r.roc.map((p) => ({ x: p.fpr, y: p.tpr })), tone: 't0', dots: true }]}
                  marks={live ? [{ ...live, label: `threshold ${threshold.toFixed(2)}`, tone: 't1' }] : []} />
                <Legend items={[{ tone: 't0', label: 'ROC' }, { tone: 't4', label: 'guessing' }, { tone: 't1', label: 'your threshold' }]} />
              </>
            )}
            <MetricsResult r={r} binary={r.matrix.length === 2} />
          </>
        );
      }} />
    </DeskCard>
  );
}

const DESCENT_EXAMPLES = {
  linear: { label: 'Fit y = 2x + 1 (linear)', model: 'linear', X: '1\n2\n3\n4\n5', y: '3, 5, 7, 9, 11', exp: -1.3, steps: '100' },
  logistic: { label: 'Separate two groups (logistic)', model: 'logistic', X: '0.5\n1\n1.5\n2.5\n3\n3.5', y: '0, 0, 0, 1, 1, 1', exp: 0, steps: '200' },
};

function DescentDesk() {
  const ex = DESCENT_EXAMPLES.linear;
  const [runKey, setRunKey] = useState(0);
  const [model, setModel] = useState('linear');
  const [X, setX] = useState(ex.X);
  const [y, setY] = useState(ex.y);
  const [exp, setExp] = useState(ex.exp);
  const [steps, setSteps] = useState(ex.steps);
  const [localError, setLocalError] = useState('');
  const [state, run] = useTool('ai');
  const id = useId();
  const lr = Number((10 ** exp).toPrecision(2));

  const submit = () => {
    setLocalError('');
    try {
      const n = Number(steps);
      if (!Number.isInteger(n) || n < 1 || n > 500) throw new Error('Steps must be a whole number from 1 to 500.');
      const Xr = rows(X, 'Inputs X');
      const yr = nums(y, 'Targets y');
      if (Xr.length !== yr.length) throw new Error(`There are ${Xr.length} input rows but ${yr.length} targets; they must match one for one.`);
      return run('descent', { model, X: Xr, y: yr, b: 0, lr, steps: n }, model);
    } catch (e) {
      setLocalError(e.message);
      return null;
    }
  };
  useAutoRun(() => submit(), [exp]);
  const load = (e) => { setRunKey((k) => k + 1); setModel(e.model); setX(e.X); setY(e.y); setExp(e.exp); setSteps(e.steps); };
  useEffect(() => { if (runKey) submit(); }, [runKey]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <DeskCard title="Gradient descent" what="Trains a one-line model by repeatedly stepping downhill on the loss. Slide the learning rate: too small crawls, too big overshoots and blows up.">
      <Presets items={Object.values(DESCENT_EXAMPLES).map((e) => ({ label: e.label, apply: () => load(e) }))} />
      <Choice label="Model" value={model} onChange={setModel} options={[['linear', 'Linear (squared error)'], ['logistic', 'Logistic (cross-entropy)']]} />
      <div className="kt-two">
        <Field label="Inputs X (one row per example, values separated by spaces)">{(i) => <textarea id={i} className="kt-input kt-mono" rows={5} value={X} onChange={(e) => setX(e.target.value)} />}</Field>
        <Field label="Targets y (one per row; 0 or 1 for logistic)">{(i) => <textarea id={i} className="kt-input kt-mono" rows={5} value={y} onChange={(e) => setY(e.target.value)} />}</Field>
      </div>
      <div className="kt-two">
        <div className="field">
          <label htmlFor={`${id}-lr`}>Learning rate: {lr}</label>
          <input id={`${id}-lr`} type="range" min="-3" max="1" step="0.05" value={exp} onChange={(e) => setExp(Number(e.target.value))} />
          <span className="hint">From 0.001 to 10 on a log scale.</span>
        </div>
        <Field label="Steps (1 to 500)" className="kt-small">{(i) => <input id={i} className="kt-input kt-num" inputMode="numeric" value={steps} onChange={(e) => setSteps(e.target.value)} />}</Field>
      </div>
      <div className="btn-row"><RunButton loading={state.loading} onClick={submit}>Train</RunButton></div>
      {localError && <div className="notice notice-bad" role="alert">{localError}</div>}
      <Outcome state={state} render={(r) => {
        const hist = r.history || [];
        const finalLoss = r.final?.loss;
        return (
          <>
            {r.diverged && <div className="notice notice-bad" role="alert"><strong>The loss blew up.</strong> The steps were too big, so each one overshot the minimum and made things worse. Lower the learning rate.</div>}
            <Plot title="Loss against training step" xLabel="step" yLabel="loss" series={[{ points: hist.map((h) => ({ x: h.step, y: h.loss })), tone: 't0', dots: hist.length <= 60 }]} />
            <p>Started at loss <strong>{fmt(hist[0]?.loss)}</strong>, ended at <strong>{fmt(finalLoss)}</strong> after {hist.length ? hist[hist.length - 1].step : 0} steps.</p>
            <table className="kt-table">
              <caption className="kt-sr">Final parameters</caption>
              <tbody>
                <tr><th scope="row">Weights w</th><td className="kt-mono">{(r.final?.w || []).map((v) => fmt(v)).join(', ')}</td></tr>
                <tr><th scope="row">Bias b</th><td className="kt-mono">{fmt(r.final?.b)}</td></tr>
              </tbody>
            </table>
            {r.final?.predictions?.length > 0 && (
              <details>
                <summary>Predictions after training</summary>
                <ol className="kt-list kt-mono">{r.final.predictions.map((p, i) => <li key={i}>{fmt(p)}</li>)}</ol>
              </details>
            )}
          </>
        );
      }} />
    </DeskCard>
  );
}

export default function AiDesk() {
  return (
    <div className="kt-desk">
      <MetricsDesk />
      <DescentDesk />
    </div>
  );
}
