import React from 'react';

/** Page head plus a tab strip, shared by the History and Languages workspaces. tabs: [{id, label, icon}]. */
export default function WorkspaceShell({ title, intro, kind, tabs, current, onTab, children, footer }) {
  return (
    <div className="page page-wide">
      <div className="page-head"><div><h1>{title}</h1><p>{intro}</p></div></div>
      <div className="tabs" role="tablist" aria-label={`${kind} tools`}>
        {tabs.map(({ id, label, icon: Icon }) => (
          <button key={id} type="button" role="tab" aria-selected={current === id} className="tab" onClick={() => onTab(id)}><Icon size={16} aria-hidden="true" /> {label}</button>
        ))}
      </div>
      <section role="tabpanel">{children}</section>
      {footer}
    </div>
  );
}
