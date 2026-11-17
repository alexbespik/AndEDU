import React, { useState } from 'react';
import TruthTableDesk from './TruthTableDesk';
import NaturalDeductionDesk from './NaturalDeductionDesk';
import SyllogismVennDesk from './SyllogismVennDesk';
import '../../styles/philosophy.css';

const DESKS = [
  { id: 'table', label: 'Truth tables', Desk: TruthTableDesk },
  { id: 'proof', label: 'Natural deduction', Desk: NaturalDeductionDesk },
  { id: 'syllogism', label: 'Syllogisms and Venn diagrams', Desk: SyllogismVennDesk },
];

/** Three desks over the deterministic logic engine (POST /api/logic/grade): same input, same verdict, no model. */
export default function LogicWorkbench() {
  const [desk, setDesk] = useState('table');
  return (
    <div className="stack">
      <p className="notice notice-info">Every verdict here comes from a Python logic engine, not from AI, so the same input always gets the same answer.</p>
      <div className="phx-modes" role="group" aria-label="Logic desks">
        {DESKS.map((d) => (
          <button key={d.id} type="button" className={`btn btn-sm ${desk === d.id ? 'btn-primary' : 'btn-quiet'}`} aria-pressed={desk === d.id}
            onClick={() => setDesk(d.id)}>{d.label}</button>
        ))}
      </div>
      {/* all stay mounted so switching desks keeps the work */}
      {DESKS.map(({ id, Desk }) => <div key={id} hidden={desk !== id}><Desk /></div>)}
    </div>
  );
}
