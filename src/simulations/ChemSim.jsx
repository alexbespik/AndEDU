import React from 'react';

// Chemistry kit (SimSpec kind "chem"). Placeholder: agy builds the widgets here, see AGY_TASK_workspaces.md.
export default function ChemSim({ spec }) {
  return (
    <div className="panel">
      <p className="hint">The chemistry simulation kit ("{spec?.widget || 'chem'}") isn't installed yet.</p>
    </div>
  );
}
