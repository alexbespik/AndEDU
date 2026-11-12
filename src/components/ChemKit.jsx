import React, { Suspense, lazy, useEffect, useState } from 'react';
import LoadingPanel from './LoadingPanel';

const ChemSim = lazy(() => import('../simulations/ChemSim'));

const store = {
  get(key, fallback) { try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ } },
};

// Ready-made widgets for the Chemistry kit (same format the class generator writes: SimSpec kind "chem").
// Each spec lists its sliders in full because ChemSim renders spec.params as given; all pass chemspec.validate_chem.
const P = (name, min, max, value, label = name, unit = '', step) => ({ name, label, min, max, value, step: step ?? (max - min) / 100, unit });
const KIT = [
  {
    id: 'kinetics', name: 'Reaction rates', caption: 'How fast A turns into B: watch [A] fall and [B] rise, with the half-life marked.',
    spec: { widget: 'kinetics', title: 'First-order kinetics: A → B', description: 'Raise the rate constant k and the half-life shrinks; for a first-order reaction it does not depend on [A]₀.', k: 'k', A0: 'A0', order: 1, reversible: false, params: [P('k', 0.01, 2, 0.5, 'k (rate constant)', '1/s'), P('A0', 0.1, 5, 2, '[A]₀', 'M')] },
  },
  {
    id: 'equilibrium', name: 'Equilibrium', caption: 'A + B ⇌ C + D: compare the reaction quotient Q with K and see which way the mixture shifts.',
    spec: { widget: 'equilibrium', title: 'Equilibrium: A + B ⇌ C + D', description: 'Add reactant or product and watch Le Chatelier at work: the mixture shifts until Q equals K again.', K: 'K', a: 1, b: 1, c: 1, d: 1, params: [P('K', 0.1, 20, 4, 'K'), P('A0', 0, 5, 2, '[A]₀', 'M'), P('B0', 0, 5, 2, '[B]₀', 'M'), P('C0', 0, 5, 0, '[C]₀', 'M'), P('D0', 0, 5, 0, '[D]₀', 'M')] },
  },
  {
    id: 'titration', name: 'Titration', caption: 'Weak acid with strong base: the pH curve, the buffer region and the equivalence point.',
    spec: { widget: 'titration', title: 'Titrating acetic acid with NaOH', description: 'Add base with Vb. At half-equivalence pH equals pKa; at equivalence the solution is basic because acetate is a weak base.', pKa: 'pKa', Va: 'Va', Ca: 'Ca', Cb: 'Cb', strong: false, acid_name: 'CH3COOH', base_name: 'NaOH', params: [P('pKa', 1, 12, 4.75, 'pKa'), P('Va', 10, 100, 25, 'Acid volume Va', 'mL'), P('Ca', 0.02, 1, 0.1, 'Acid concentration Ca', 'M'), P('Cb', 0.02, 1, 0.1, 'Base concentration Cb', 'M'), P('Vb', 0, 60, 0, 'Base added Vb', 'mL')] },
  },
  {
    id: 'gas_law', name: 'Gas laws', caption: 'Particles in a piston: change moles, temperature and volume and compare P = nRT/V with wall hits.',
    spec: { widget: 'gas_law', title: 'Ideal gas in a piston', description: 'Heat the gas and the particles move faster; squeeze the volume and they hit the walls more often. Both raise the pressure.', gas_type: 'ideal', params: [P('n', 0.1, 2, 1, 'Amount n', 'mol'), P('T', 100, 600, 300, 'Temperature T', 'K'), P('V', 5, 30, 15, 'Volume V', 'L')] },
  },
  {
    id: 'energy_diagram', name: 'Energy diagram', caption: 'The energy profile of a reaction: activation energy, enthalpy change and a catalysed path.',
    spec: { widget: 'energy_diagram', title: 'Activation energy and catalysis', description: 'A catalyst lowers the barrier (dashed path) but not ΔH. Raise T or lower Ea to see more molecules clear the barrier.', Ea: 'Ea', deltaH: 'deltaH', Ea_cat: 25, params: [P('Ea', 10, 120, 60, 'Ea', 'kJ/mol', 1), P('deltaH', -35, 35, -20, 'ΔH', 'kJ/mol', 1), P('T', 200, 1000, 298, 'Temperature T', 'K', 1)] },
  },
  {
    id: 'decay', name: 'Radioactive decay', caption: 'Nuclei decay one by one at random, yet together they follow N₀·e^(−λt).',
    spec: { widget: 'decay', title: 'Radioactive decay and half-life', description: 'Each nucleus decays at random; after every half-life about half of those left remain. Compare the grid with the smooth curve.', t_half: 't_half', params: [P('N0', 10, 200, 100, 'Nuclei N₀', '', 1), P('t_half', 1, 30, 5, 'Half-life', 's')] },
  },
].map((k) => ({ ...k, spec: { kind: 'chem', ...k.spec } }));

/** Chemistry kit: a gallery of the six interactive chemistry widgets, one at a time. */
export default function ChemKit() {
  const [pick, setPick] = useState(() => store.get('andedu_chem_kit', KIT[0].id));
  useEffect(() => { store.set('andedu_chem_kit', pick); }, [pick]);
  const item = KIT.find((k) => k.id === pick) || KIT[0];
  return (
    <div className="stack" style={{ marginTop: 'var(--space-4)' }}>
      <div className="btn-row" role="group" aria-label="Chemistry widgets">
        {KIT.map((k) => (
          <button key={k.id} type="button" className={`btn btn-sm ${k.id === item.id ? 'btn-primary' : 'btn-quiet'}`} aria-pressed={k.id === item.id}
            aria-label={`${k.name}: ${k.caption}`} onClick={() => setPick(k.id)}>{k.name}</button>
        ))}
      </div>
      <p className="hint" aria-live="polite">{item.caption} Class simulations in chemistry courses use these same widgets.</p>
      <Suspense fallback={<LoadingPanel compact label="Loading the simulation…" />}>
        <ChemSim key={item.id} spec={item.spec} />
      </Suspense>
    </div>
  );
}
