import React, { useEffect, useId, useState } from 'react';
import { Bar, DeskCard, Outcome, RunButton, pct, useTool } from './common';
import { Choice, Field, Legend, Plot, Presets, fmt, nums, num, rows } from './stemCommon';

const TESTS = [['z', 'z-test (known spread)'], ['welch', 'Welch t (unequal spreads)'], ['pooled', 'Pooled t (equal spreads)']];
const ALTS = [['two_sided', 'Two-sided (different)'], ['greater', 'Greater (group 1 higher)'], ['less', 'Less (group 1 lower)']];
const TEST_WHAT = {
  z: 'Treats the standard deviations as exactly known and compares the difference of means with the normal curve.',
  welch: "Estimates each group's spread separately and compares with a t curve; the safe default when the spreads may differ.",
  pooled: 'Assumes both groups share one spread, pools it, and compares with a t curve.',
};

/** Part of a density curve between lo and hi (data units), as a closed polygon down to y = 0. */
function slice(curve, lo, hi) {
  const at = (x) => {
    for (let i = 1; i < curve.length; i += 1) {
      if (curve[i].x >= x) {
        const a = curve[i - 1]; const b = curve[i];
        return { x, y: a.y + ((b.y - a.y) * (x - a.x)) / ((b.x - a.x) || 1) };
      }
    }
    return { x, y: curve[curve.length - 1].y };
  };
  const a = Math.max(lo, curve[0].x); const b = Math.min(hi, curve[curve.length - 1].x);
  if (!(b > a)) return null;
  const pts = [at(a), ...curve.filter((p) => p.x > a && p.x < b), at(b)];
  return [{ x: a, y: 0 }, ...pts, { x: b, y: 0 }];
}

function NullCurve({ r, alternative }) {
  const curve = r.curve || [];
  if (curve.length < 2) return null;
  const s = r.statistic;
  const lo = curve[0].x; const hi = curve[curve.length - 1].x;
  const areas = [];
  const tails = alternative === 'two_sided' ? [[-Infinity, -Math.abs(s)], [Math.abs(s), Infinity]] : alternative === 'greater' ? [[s, Infinity]] : [[-Infinity, s]];
  tails.forEach(([a, b]) => { const p = slice(curve, a, b); if (p) areas.push({ points: p, tone: 't2' }); });
  const c = Math.abs(r.critical ?? 0);
  const crit = alternative === 'two_sided' ? [-c, c] : alternative === 'greater' ? [c] : [-c];
  const clamped = Math.max(lo, Math.min(hi, s));
  return (
    <>
      <Plot title="Distribution of the test statistic if there is no real difference, with the p-value area shaded" xLabel="test statistic" yLabel="density" xDomain={[lo, hi]}
        series={[{ points: curve, tone: 't0' }]} areas={areas}
        vlines={[{ x: clamped, label: `observed ${fmt(s)}`, tone: 't1' }, ...crit.map((x) => ({ x, tone: 't4' }))]} />
      <Legend items={[{ tone: 't0', label: 'if the groups truly match' }, { tone: 't2', label: 'p-value: this extreme or more' }, { tone: 't1', label: 'what you observed' }, { tone: 't4', label: 'rejection boundary' }]} />
      {clamped !== s && <p className="hint">The observed statistic is beyond the edge of the plot.</p>}
    </>
  );
}

const TEXTBOOK = { mean1: '52', sd1: '8', n1: '40', mean2: '48', sd2: '6', n2: '50' };

function TwoSampleDesk() {
  const [input, setInput] = useState('summary');
  const [test, setTest] = useState('z');
  const [alt, setAlt] = useState('two_sided');
  const [alpha, setAlpha] = useState('0.05');
  const [f, setF] = useState(TEXTBOOK);
  const [xs, setXs] = useState('12.1, 11.4, 13.0, 12.7, 11.9, 12.5, 13.2, 12.0');
  const [ys, setYs] = useState('11.2, 10.9, 11.8, 12.0, 10.5, 11.1, 11.6, 11.3');
  const [localError, setLocalError] = useState('');
  const [runKey, setRunKey] = useState(0);
  const [state, run] = useTool('stats');
  const set = (k) => (e) => setF((o) => ({ ...o, [k]: e.target.value }));

  const submit = () => {
    setLocalError('');
    try {
      const a = num(alpha, 'Significance level');
      if (!(a > 0 && a <= 0.5)) throw new Error('Significance level must be above 0 and at most 0.5 (usually 0.05).');
      const base = { test, alternative: alt, alpha: a };
      if (input === 'raw') {
        const x = nums(xs, 'Group 1'); const y = nums(ys, 'Group 2');
        if (x.length < 2 || y.length < 2) throw new Error('Each group needs at least 2 values.');
        return run('two_sample', { ...base, x, y }, alt);
      }
      const v = {};
      for (const [k, label] of [['mean1', 'Mean of group 1'], ['sd1', 'Spread of group 1'], ['n1', 'Size of group 1'], ['mean2', 'Mean of group 2'], ['sd2', 'Spread of group 2'], ['n2', 'Size of group 2']]) v[k] = num(f[k], label);
      if (!Number.isInteger(v.n1) || !Number.isInteger(v.n2) || v.n1 < 2 || v.n2 < 2) throw new Error('Group sizes must be whole numbers, at least 2.');
      if (v.sd1 < 0 || v.sd2 < 0) throw new Error('A standard deviation cannot be negative.');
      return run('two_sample', { ...base, ...v }, alt);
    } catch (e) {
      setLocalError(e.message);
      return null;
    }
  };
  useEffect(() => { submit(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (runKey) submit(); }, [runKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const field = (k, label) => <Field label={label} className="kt-small">{(i) => <input id={i} className="kt-input kt-num" inputMode="decimal" value={f[k]} onChange={set(k)} />}</Field>;
  const preset = (t) => () => { setInput('summary'); setTest(t); setAlt('two_sided'); setF(TEXTBOOK); setRunKey((k) => k + 1); };

  return (
    <DeskCard title="Compare two groups" what="Tests whether two group averages differ by more than chance explains. The p-value is the chance of a gap this big if the groups truly had the same mean.">
      <Presets items={[
        { label: 'Textbook z-test (52 vs 48)', apply: preset('z') },
        { label: 'Welch t-test, same numbers', apply: preset('welch') },
      ]} />
      <Choice label="Data format" value={input} onChange={setInput} options={[['summary', 'Means and spreads'], ['raw', 'Raw measurements']]} />
      <Choice label="Test" value={test} onChange={setTest} options={TESTS} />
      <p className="hint">{TEST_WHAT[test]}</p>
      <Choice label="Alternative hypothesis" value={alt} onChange={setAlt} options={ALTS} />
      {input === 'summary' ? (
        <div className="kt-two">
          <fieldset className="kit-fields stack-sm"><legend className="label">Group 1</legend>{field('mean1', 'Mean of group 1')}{field('sd1', 'Standard deviation of group 1')}{field('n1', 'Size of group 1')}</fieldset>
          <fieldset className="kit-fields stack-sm"><legend className="label">Group 2</legend>{field('mean2', 'Mean of group 2')}{field('sd2', 'Standard deviation of group 2')}{field('n2', 'Size of group 2')}</fieldset>
        </div>
      ) : (
        <div className="kt-two">
          <Field label="Group 1 measurements">{(i) => <textarea id={i} className="kt-input kt-mono" rows={3} value={xs} onChange={(e) => setXs(e.target.value)} />}</Field>
          <Field label="Group 2 measurements">{(i) => <textarea id={i} className="kt-input kt-mono" rows={3} value={ys} onChange={(e) => setYs(e.target.value)} />}</Field>
        </div>
      )}
      <Field label="Significance level (alpha)" className="kt-small">{(i) => <input id={i} className="kt-input kt-num" inputMode="decimal" value={alpha} onChange={(e) => setAlpha(e.target.value)} />}</Field>
      <div className="btn-row"><RunButton loading={state.loading} onClick={submit}>Run the test</RunButton></div>
      {localError && <div className="notice notice-bad" role="alert">{localError}</div>}
      <Outcome state={state} render={(r) => (
        <>
          <p className={`notice ${r.reject ? 'notice-ok' : ''}`}>
            <strong>{r.reject ? 'Reject the "no difference" hypothesis.' : 'Not enough evidence of a difference.'}</strong>{' '}
            p = {fmt(r.p_value)} {r.reject ? 'is below' : 'is not below'} alpha = {alpha}.
          </p>
          <NullCurve r={r} alternative={state.tag || alt} />
          <table className="kt-table">
            <caption className="kt-sr">Test results</caption>
            <tbody>
              <tr><th scope="row">Test statistic</th><td>{fmt(r.statistic)}</td></tr>
              {r.df != null && <tr><th scope="row">Degrees of freedom</th><td>{fmt(r.df)}</td></tr>}
              <tr><th scope="row">p-value</th><td>{fmt(r.p_value)}</td></tr>
              <tr><th scope="row">Critical value</th><td>{fmt(r.critical)}</td></tr>
              <tr><th scope="row">Standard error of the difference</th><td>{fmt(r.se)}</td></tr>
              {r.ci && <tr><th scope="row">{pct(1 - (Number(alpha) || 0.05), 0)} confidence interval for the difference (group 1 minus group 2)</th><td>{fmt(r.ci[0])} to {fmt(r.ci[1])}</td></tr>}
            </tbody>
          </table>
        </>
      )} />
    </DeskCard>
  );
}

const CHAINS = {
  two: { label: 'Two states (alpha 0.3, beta 0.1)', P: '0.7 0.3\n0.1 0.9', start: '1 0' },
  three: { label: 'Three states, random walk', P: '0.5 0.5 0\n0.25 0.5 0.25\n0 0.5 0.5', start: '1 0 0' },
  periodic: { label: 'Flip-flop (period 2)', P: '0 1\n1 0', start: '1 0' },
  absorbing: { label: 'Two absorbing states', P: '1 0\n0 1', start: '0.5 0.5' },
};

function ChainGraph({ P }) {
  const n = P.length;
  const W = 320; const cx = W / 2; const cy = 150; const R = n === 2 ? 90 : 100;
  const pos = P.map((_, i) => {
    const a = (2 * Math.PI * i) / n - Math.PI / 2;
    return n === 2 ? { x: i ? cx + R : cx - R, y: cy } : { x: cx + R * Math.cos(a), y: cy + R * Math.sin(a) };
  });
  const rad = 17;
  const labels = n <= 5;
  const edges = [];
  P.forEach((row, i) => row.forEach((p, j) => { if (p > 0) edges.push({ i, j, p }); }));
  return (
    <svg className="kt-plot kt-chain" viewBox={`0 0 ${W} 300`} role="img" aria-label={`State graph of the chain with ${n} states; arrows are transitions with their probability`}>
      <defs><marker id="kt-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" className="kt-arrow" /></marker></defs>
      {edges.map(({ i, j, p }) => {
        const a = pos[i]; const b = pos[j];
        if (i === j) {
          const ox = a.x - cx; const oy = a.y - cy; const d = Math.hypot(ox, oy) || 1;
          const ux = n === 2 ? 0 : ox / d; const uy = n === 2 ? -1 : oy / d;
          return (
            <g key={`${i}-${j}`}>
              <circle className="kt-edge" cx={a.x + ux * (rad + 8)} cy={a.y + uy * (rad + 8)} r="10" fill="none" />
              {labels && <text className="kt-axis-text" x={a.x + ux * (rad + 28)} y={a.y + uy * (rad + 28) + 3} textAnchor="middle">{fmt(p, 2)}</text>}
            </g>
          );
        }
        const dx = b.x - a.x; const dy = b.y - a.y; const d = Math.hypot(dx, dy) || 1;
        const nx = -dy / d; const ny = dx / d; const bend = 18;
        const sx = a.x + (dx / d) * rad + nx * 6; const sy = a.y + (dy / d) * rad + ny * 6;
        const ex = b.x - (dx / d) * (rad + 5) + nx * 6; const ey = b.y - (dy / d) * (rad + 5) + ny * 6;
        const mx = (a.x + b.x) / 2 + nx * bend; const my = (a.y + b.y) / 2 + ny * bend;
        return (
          <g key={`${i}-${j}`}>
            <path className="kt-edge" d={`M${sx},${sy} Q${mx},${my} ${ex},${ey}`} fill="none" markerEnd="url(#kt-arrow)" />
            {labels && <text className="kt-axis-text" x={mx + nx * 6} y={my + ny * 6 + 3} textAnchor="middle">{fmt(p, 2)}</text>}
          </g>
        );
      })}
      {pos.map((p, i) => (
        <g key={i}>
          <circle className={`kt-node t${i % 7}`} cx={p.x} cy={p.y} r={rad} />
          <text className="kt-node-text" x={p.x} y={p.y + 4} textAnchor="middle">S{i}</text>
        </g>
      ))}
    </svg>
  );
}

function MarkovDesk() {
  const [P, setP] = useState(CHAINS.two.P);
  const [start, setStart] = useState(CHAINS.two.start);
  const [steps, setSteps] = useState('20');
  const [localError, setLocalError] = useState('');
  const [runKey, setRunKey] = useState(0);
  const [state, run] = useTool('stats');
  const id = useId();

  const submit = () => {
    setLocalError('');
    try {
      const m = rows(P, 'Transition matrix');
      if (m.length !== m[0].length) throw new Error('The transition matrix must be square (as many columns as rows).');
      m.forEach((r, i) => {
        const sum = r.reduce((a, b) => a + b, 0);
        if (r.some((v) => v < 0 || v > 1)) throw new Error(`Row ${i + 1} of the matrix: every probability must be between 0 and 1.`);
        if (Math.abs(sum - 1) > 1e-9) throw new Error(`Row ${i + 1} of the matrix must add up to 1 (it adds up to ${fmt(sum)}).`);
      });
      const n = Number(steps);
      if (!Number.isInteger(n) || n < 0 || n > 100) throw new Error('Steps must be a whole number from 0 to 100.');
      const args = { P: m, steps: n };
      if (start.trim()) {
        const s = nums(start, 'Start distribution');
        if (s.length !== m.length) throw new Error(`The start distribution needs ${m.length} numbers, one per state.`);
        args.start = s;
      }
      return run('markov', args, JSON.stringify(m));
    } catch (e) {
      setLocalError(e.message);
      return null;
    }
  };
  useEffect(() => { submit(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (runKey) submit(); }, [runKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const load = (c) => { setP(c.P); setStart(c.start); setRunKey((k) => k + 1); };

  return (
    <DeskCard title="Markov chain" what="A chain hops between states with fixed probabilities. See where it settles in the long run (the stationary distribution), how it gets there, and how its states are connected.">
      <Presets items={Object.values(CHAINS).map((c) => ({ label: c.label, apply: () => load(c) }))} />
      <div className="kt-two">
        <Field label="Transition matrix (row i = chance of moving from state i to each state; rows add up to 1)">{(i) => <textarea id={i} className="kt-input kt-mono" rows={4} spellCheck={false} value={P} onChange={(e) => setP(e.target.value)} />}</Field>
        <div className="stack-sm">
          <Field label="Start distribution (blank = start in state 0)">{(i) => <input id={i} className="kt-input kt-mono" value={start} onChange={(e) => setStart(e.target.value)} />}</Field>
          <div className="field kt-small">
            <label htmlFor={`${id}-n`}>Steps to simulate (0 to 100)</label>
            <input id={`${id}-n`} className="kt-input kt-num" inputMode="numeric" value={steps} onChange={(e) => setSteps(e.target.value)} />
          </div>
        </div>
      </div>
      <div className="btn-row"><RunButton loading={state.loading} onClick={submit}>Analyze the chain</RunButton></div>
      {localError && <div className="notice notice-bad" role="alert">{localError}</div>}
      <Outcome state={state} render={(r) => {
        let m;
        try { m = state.tag ? JSON.parse(state.tag) : null; } catch { m = null; }
        const dist = r.distribution || [];
        const n = dist[0]?.length || m?.length || 0;
        const series = Array.from({ length: n }, (_, k) => ({ points: dist.map((d, t) => ({ x: t, y: d[k] })), tone: `t${k % 7}`, dashed: k >= 7 }));
        const flags = [
          [r.irreducible, 'irreducible: every state can reach every other', 'not irreducible: some states cannot be reached from others'],
          [r.aperiodic, 'aperiodic: no fixed rhythm of returns', 'periodic: returns come only at multiples of a fixed period'],
        ];
        return (
          <>
            {m && <ChainGraph P={m} />}
            {r.stationary
              ? (
                <div className="kt-bars" role="group" aria-label="Stationary distribution">
                  <strong>{r.unique ? 'Long-run (stationary) distribution' : 'One stationary distribution (there are many)'}</strong>
                  {r.stationary.map((s, i) => <Bar key={i} label={`S${i}`} value={s.value} text={`${pct(s.value)} (${s.exact})`} />)}
                </div>
              )
              : <p className="notice">{r.unique ? 'No stationary distribution could be computed.' : 'There is no single long-run distribution: the chain has several closed groups of states, each with its own stationary distribution.'}</p>}
            {!r.unique && <p className="hint">Where the chain ends up depends on which closed group it starts in.</p>}
            <ul className="kt-tags">
              {flags.map(([ok, yes, no], i) => <li key={i} className={`kt-chip ${ok ? 'kt-chip-ok' : 'kt-chip-warn'}`}>{ok ? yes : no}</li>)}
              {r.absorbing?.length > 0 && <li className="kt-chip kt-chip-warn">absorbing: {r.absorbing.map((s) => `S${s}`).join(', ')} (once in, never out)</li>}
            </ul>
            {r.classes?.length > 0 && (
              <details>
                <summary>Communicating classes ({r.classes.length})</summary>
                <ul className="kt-list">
                  {r.classes.map((c, i) => <li key={i}>{c.map((s) => `S${s}`).join(', ')}: {r.recurrent?.[i] ? 'recurrent (the chain keeps returning)' : 'transient (the chain eventually leaves for good)'}{r.period?.[i] ? `, period ${r.period[i]}` : ''}</li>)}
                </ul>
              </details>
            )}
            {dist.length > 1 && (
              <>
                <h3 className="kt-h3">Distribution over time</h3>
                <Plot title="Probability of being in each state at each step" xLabel="step" yLabel="probability" yDomain={[0, 1.02]} series={series} />
                <Legend items={Array.from({ length: n }, (_, k) => ({ tone: `t${k % 7}`, label: `S${k}` }))} />
              </>
            )}
          </>
        );
      }} />
    </DeskCard>
  );
}

export default function StatsDesk() {
  return (
    <div className="kt-desk">
      <TwoSampleDesk />
      <MarkovDesk />
    </div>
  );
}
