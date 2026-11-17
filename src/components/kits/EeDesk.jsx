import React, { useEffect, useId, useState } from 'react';
import { DeskCard, Outcome, RunButton, useTool } from './common';
import { Choice, Field, Legend, Plot, Presets, fmt, nums, siNum, useAutoRun } from './stemCommon';

const NETLISTS = {
  divider: { label: '10 V divider (1k + 2k)', text: 'V in 0 10\nR in mid 1k\nR mid 0 2k', ground: '0' },
  wheatstone: { label: 'Balanced Wheatstone bridge', text: 'V top 0 10\nR top l 1k\nR top r 1k\nR l 0 1k\nR r 0 1k\nR l r 5k', ground: '0' },
  current: { label: 'Current source into 2 resistors', text: 'I 0 a 2m\nR a 0 1k\nR a b 1k\nR b 0 3k', ground: '0' },
};

const TYPE_WORD = { R: 'Resistor', V: 'Voltage source', I: 'Current source' };

function parseNetlist(text) {
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
  if (!lines.length) throw new Error('Add at least one element.');
  return lines.map((line, i) => {
    const p = line.split(/\s+/);
    const type = (p[0] || '').toUpperCase();
    if (p.length !== 4 || !['R', 'V', 'I'].includes(type)) throw new Error(`Line ${i + 1}: write it as "R node1 node2 value" (R, V or I, two node names, a value such as 4.7k).`);
    return { type, a: p[1], b: p[2], value: siNum(p[3], `Line ${i + 1} value`) };
  });
}

const UNIT = { R: 'ohm', V: 'V', I: 'A' };
const eng = (v, unit) => {
  if (v === null || v === undefined) return '-';
  const a = Math.abs(v);
  if (a === 0) return `0 ${unit}`;
  if (a >= 1) return `${fmt(v)} ${unit}`;
  if (a >= 1e-3) return `${fmt(v * 1e3)} m${unit}`;
  if (a >= 1e-6) return `${fmt(v * 1e6)} u${unit}`;
  return `${fmt(v)} ${unit}`;
};

function CircuitDesk() {
  const [text, setText] = useState(NETLISTS.divider.text);
  const [ground, setGround] = useState('0');
  const [localError, setLocalError] = useState('');
  const [state, run] = useTool('ee');
  const submit = (override) => {
    setLocalError('');
    try {
      const t = override?.text ?? text;
      const g = override?.ground ?? ground;
      const elements = parseNetlist(t);
      const gnd = g.trim() || '0';
      return run('dc_solve', { elements, ground: gnd }, { elements, ground: gnd });
    } catch (e) {
      setLocalError(e.message);
      return null;
    }
  };
  useEffect(() => { submit(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const load = (id) => { const n = NETLISTS[id]; setText(n.text); setGround(n.ground); submit(n); };
  return (
    <DeskCard title="DC circuit solver" what="Finds every node voltage and element current of a resistor network with voltage and current sources (nodal analysis, exact fractions), and checks that the power added up is zero.">
      <Presets items={Object.entries(NETLISTS).map(([id, n]) => ({ label: n.label, apply: () => load(id) }))} />
      <Field label="Netlist: one element per line" hint='Format "type node1 node2 value". R = resistor (ohm). V = voltage source (node1 is +). I = current source (its current flows from node1 to node2 inside the source). Values accept k, M, m, u: 4.7k, 2m.'>
        {(id) => <textarea id={id} className="kt-input kt-mono" rows={7} spellCheck={false} value={text} onChange={(e) => { setText(e.target.value); }} />}
      </Field>
      <Field label="Ground node (0 volts)" className="kt-small">
        {(id) => <input id={id} className="kt-input kt-mono" value={ground} onChange={(e) => setGround(e.target.value)} />}
      </Field>
      <div className="btn-row"><RunButton loading={state.loading} onClick={() => submit()}>Solve the circuit</RunButton></div>
      {localError && <div className="notice notice-bad" role="alert">{localError}</div>}
      <Outcome state={state} render={(r) => {
        if (r.solvable === false) {
          return (
            <div className="notice notice-bad" role="alert">
              {r.reason === 'floating_node'
                ? <>The circuit cannot be solved: {r.nodes_unreached?.length ? <strong>{r.nodes_unreached.join(', ')}</strong> : 'part of it'} is not connected to the ground node by any path.</>
                : 'The circuit cannot be solved: the equations have no single answer (for example, two voltage sources forcing different voltages across the same pair of nodes, or a loop of only voltage sources).'}
            </div>
          );
        }
        const elements = state.tag?.elements || [];
        const gnd = state.tag?.ground || '0';
        const rowsOut = r.elements || [];
        const total = rowsOut.reduce((a, e) => a + (Number(e.power) || 0), 0);
        return (
          <>
            <table className="kt-table">
              <caption className="kt-sr">Node voltages</caption>
              <thead><tr><th scope="col">Node</th><th scope="col">Voltage</th><th scope="col">Exact</th></tr></thead>
              <tbody>
                <tr><th scope="row">{gnd} (ground)</th><td>0 V</td><td>0</td></tr>
                {Object.entries(r.nodes || {}).filter(([n]) => n !== gnd).map(([n, v]) => <tr key={n}><th scope="row">{n}</th><td>{eng(v.value, 'V')}</td><td className="kt-mono">{v.exact}</td></tr>)}
              </tbody>
            </table>
            <div className="kt-scroll">
              <table className="kt-table">
                <caption className="kt-sr">Element currents, voltages and power</caption>
                <thead><tr><th scope="col">#</th><th scope="col">Element</th><th scope="col">Current (a to b)</th><th scope="col">Voltage (a minus b)</th><th scope="col">Power absorbed</th></tr></thead>
                <tbody>
                  {rowsOut.map((e, i) => {
                    const el = elements[i];
                    return (
                      <tr key={i}>
                        <th scope="row">{i + 1}</th>
                        <td>{TYPE_WORD[e.type] || e.type}{el ? ` ${el.a} to ${el.b}, ${fmt(el.value)} ${UNIT[el.type]}` : ''}</td>
                        <td>{eng(e.current, 'A')}</td><td>{eng(e.voltage, 'V')}</td><td>{eng(e.power, 'W')}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="hint">Positive power is absorbed (resistors always are); a source that delivers power shows negative. Sum of all power: <strong>{fmt(Math.abs(total) < 1e-9 ? 0 : total)} W</strong>, which should be 0.</p>
          </>
        );
      }} />
    </DeskCard>
  );
}

const SYSTEMS = {
  rc: { label: 'RC low-pass (cutoff 1000 rad/s)', num: '1', den: '0.001, 1', wMin: '10', wMax: '100000' },
  third: { label: 'Third order, with phase crossover', num: '2', den: '1, 3, 2, 0', wMin: '0.01', wMax: '100' },
  lead: { label: 'Lead compensator', num: '1, 1', den: '0.1, 1', wMin: '0.01', wMax: '1000' },
};

function BodeDesk() {
  const [mode, setMode] = useState('second');
  const [K, setK] = useState(1);
  const [zeta, setZeta] = useState(0.1);
  const [numT, setNumT] = useState(SYSTEMS.rc.num);
  const [denT, setDenT] = useState(SYSTEMS.rc.den);
  const [wMin, setWMin] = useState(SYSTEMS.rc.wMin);
  const [wMax, setWMax] = useState(SYSTEMS.rc.wMax);
  const [localError, setLocalError] = useState('');
  const [state, run] = useTool('ee');
  const id = useId();

  const submit = () => {
    setLocalError('');
    try {
      if (mode === 'second') return run('bode', { num: [K], den: [1, 2 * zeta, 1], w_min: 0.01, w_max: 100, points: 161 }, 'second');
      return run('bode', { num: nums(numT, 'Numerator'), den: nums(denT, 'Denominator'), w_min: siNum(wMin, 'Lowest frequency'), w_max: siNum(wMax, 'Highest frequency'), points: 161 }, 'custom');
    } catch (e) {
      setLocalError(e.message);
      return null;
    }
  };
  // the sliders re-run after a pause; the typed form runs on the button
  useAutoRun(() => { if (mode === 'second') submit(); }, [mode, K, zeta]);
  const loadSystem = (k) => { const s = SYSTEMS[k]; setMode('custom'); setNumT(s.num); setDenT(s.den); setWMin(s.wMin); setWMax(s.wMax); };
  useEffect(() => { if (mode === 'custom' && state.tag !== 'custom') submit(); }, [mode]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <DeskCard title="Bode plot" what="Shows how a transfer function G(s) scales (gain, in dB) and delays (phase, in degrees) a sine of angular frequency w, and finds the -3 dB cutoff, the gain and phase margins.">
      <Choice label="How to define G(s)" value={mode} onChange={setMode} options={[['second', 'Second-order (K and damping)'], ['custom', 'Type the polynomials']]} />
      {mode === 'second' ? (
        <>
          <p className="hint">G(s) = K / (s^2 + 2 zeta s + 1), natural frequency 1 rad/s. Small zeta gives a tall resonance peak; zeta near 0.7 is flat.</p>
          <div className="kt-two">
            <div className="field">
              <label htmlFor={`${id}-k`}>Gain K: {K}</label>
              <input id={`${id}-k`} type="range" min="0.1" max="5" step="0.1" value={K} onChange={(e) => setK(Number(e.target.value))} />
            </div>
            <div className="field">
              <label htmlFor={`${id}-z`}>Damping zeta: {zeta}</label>
              <input id={`${id}-z`} type="range" min="0.05" max="2" step="0.05" value={zeta} onChange={(e) => setZeta(Number(e.target.value))} />
            </div>
          </div>
        </>
      ) : (
        <>
          <Presets items={Object.entries(SYSTEMS).map(([k, s]) => ({ label: s.label, apply: () => loadSystem(k) }))} />
          <div className="kt-two">
            <Field label="Numerator coefficients (highest power of s first)" hint="2 means 2; 1, 1 means s + 1">{(i) => <input id={i} className="kt-input kt-mono" value={numT} onChange={(e) => setNumT(e.target.value)} />}</Field>
            <Field label="Denominator coefficients (highest power of s first)" hint="1, 3, 2, 0 means s^3 + 3s^2 + 2s">{(i) => <input id={i} className="kt-input kt-mono" value={denT} onChange={(e) => setDenT(e.target.value)} />}</Field>
            <Field label="Lowest frequency (rad/s)">{(i) => <input id={i} className="kt-input kt-mono" value={wMin} onChange={(e) => setWMin(e.target.value)} />}</Field>
            <Field label="Highest frequency (rad/s)">{(i) => <input id={i} className="kt-input kt-mono" value={wMax} onChange={(e) => setWMax(e.target.value)} />}</Field>
          </div>
          <div className="btn-row"><RunButton loading={state.loading} onClick={submit}>Draw the Bode plot</RunButton></div>
        </>
      )}
      {localError && <div className="notice notice-bad" role="alert">{localError}</div>}
      <Outcome state={state} render={(r) => {
        const mag = (r.samples || []).map((s) => ({ x: s.w, y: s.mag_db }));
        const ph = (r.samples || []).map((s) => ({ x: s.w, y: s.phase_deg }));
        const mv = [];
        if (r.cutoff_rad_s != null) mv.push({ x: r.cutoff_rad_s, label: `-3 dB at ${fmt(r.cutoff_rad_s)}`, tone: 't1' });
        if (r.gain_crossover != null) mv.push({ x: r.gain_crossover, label: `0 dB at ${fmt(r.gain_crossover)}`, tone: 't2' });
        const pv = [];
        if (r.phase_crossover != null) pv.push({ x: r.phase_crossover, label: `-180 at ${fmt(r.phase_crossover)}`, tone: 't3' });
        if (r.gain_crossover != null) pv.push({ x: r.gain_crossover, label: `PM ${fmt(r.phase_margin_deg)}`, tone: 't2' });
        const stable = r.phase_margin_deg != null && r.phase_margin_deg > 0 && (r.gain_margin_db == null || r.gain_margin_db > 0);
        return (
          <>
            <h3 className="kt-h3">Magnitude (dB)</h3>
            <Plot title="Bode magnitude in dB against angular frequency" xLabel="w (rad/s, log scale)" yLabel="gain (dB)" xLog series={[{ points: mag, tone: 't0' }]} hlines={[{ y: 0, label: '0 dB' }]} vlines={mv} />
            <h3 className="kt-h3">Phase (degrees)</h3>
            <Plot title="Bode phase in degrees against angular frequency" xLabel="w (rad/s, log scale)" yLabel="phase (deg)" xLog series={[{ points: ph, tone: 't1' }]} hlines={[{ y: -180, label: '-180' }]} vlines={pv} />
            <Legend items={[{ tone: 't0', label: 'magnitude' }, { tone: 't1', label: 'phase' }]} />
            <table className="kt-table">
              <caption className="kt-sr">Frequency response summary</caption>
              <tbody>
                <tr><th scope="row">Low-frequency gain</th><td>{r.dc_gain_db == null ? 'none (G(0) is zero or infinite)' : `${fmt(r.dc_gain_db)} dB`}</td></tr>
                <tr><th scope="row">-3 dB cutoff</th><td>{r.cutoff_rad_s == null ? 'not reached in this range' : `${fmt(r.cutoff_rad_s)} rad/s`}</td></tr>
                <tr><th scope="row">Gain crossover (0 dB)</th><td>{r.gain_crossover == null ? 'none in this range' : `${fmt(r.gain_crossover)} rad/s`}</td></tr>
                <tr><th scope="row">Phase margin</th><td>{r.phase_margin_deg == null ? '-' : `${fmt(r.phase_margin_deg)} degrees`}</td></tr>
                <tr><th scope="row">Phase crossover (-180 deg)</th><td>{r.phase_crossover == null ? 'none in this range' : `${fmt(r.phase_crossover)} rad/s`}</td></tr>
                <tr><th scope="row">Gain margin</th><td>{r.gain_margin_db == null ? 'none (phase never reaches -180)' : `${fmt(r.gain_margin_db)} dB`}</td></tr>
              </tbody>
            </table>
            {stable && <p className="notice notice-ok">Both margins are positive: closing a unity-feedback loop around this G(s) is expected to be stable.</p>}
            {r.undefined_at?.length > 0 && <p className="hint">G is undefined at w = {r.undefined_at.map((w) => fmt(w)).join(', ')} (a pole on the imaginary axis); those points are skipped.</p>}
          </>
        );
      }} />
    </DeskCard>
  );
}

export default function EeDesk() {
  return (
    <div className="kt-desk">
      <CircuitDesk />
      <BodeDesk />
    </div>
  );
}
