import React, { useEffect, useState } from 'react';
import { Activity, Eye, Brain, BookOpen } from 'lucide-react';
import { api } from '../lib/api';
import WorkspaceShell from './WorkspaceShell';
import SpecSim from '../simulations/SpecSim';
import '../styles/moral.css';

// Offline units from psychology.py (GET /api/psychology/units). Reflective: nothing here is scored or pays XP,
// and the mini-quiz is checked in the browser only.
const TABS = [
  { id: 'morale', label: 'Morale', icon: Activity },
  { id: 'perspective', label: 'Perspective', icon: Eye },
  { id: 'moral', label: 'Moral psychology', icon: Brain },
];

let handledRequest = null;

function Reflect({ items }) {
  if (!items?.length) return null;
  return (
    <section className="panel stack-sm">
      <h3>Questions to carry away</h3>
      <ul className="phx-reflect">{items.map((q) => <li key={q}>{q}</li>)}</ul>
    </section>
  );
}

function Morale({ unit }) {
  return (
    <div className="stack">
      <section className="panel stack">
        <p>{unit.intro}</p>
        <ul className="psy-points">
          {unit.points.map((p) => <li key={p.title}><strong>{p.title}</strong><p>{p.text}</p></li>)}
        </ul>
      </section>
      {unit.simulation && <SpecSim spec={unit.simulation} />}
      <Reflect items={unit.reflect} />
    </div>
  );
}

function PerspectiveCase({ c }) {
  const [shown, setShown] = useState(() => new Set());
  const toggle = (i) => setShown((s) => { const n = new Set(s); if (n.has(i)) n.delete(i); else n.add(i); return n; });
  return (
    <section className="panel stack">
      <h3>{c.event}</h3>
      <p className="hint">Before opening each view, guess how this looks from there.</p>
      <div className="psy-views">
        {c.views.map((v, i) => (
          <button key={v.who} type="button" className="psy-view" aria-pressed={shown.has(i)} onClick={() => toggle(i)}>
            <strong>{v.who}</strong>
            {shown.has(i) ? <p>“{v.sees}”</p> : <p className="hint">Show this view</p>}
          </button>
        ))}
      </div>
      {shown.size === c.views.length && <p><em>{c.reflect}</em></p>}
    </section>
  );
}

function Perspective({ unit }) {
  return (
    <div className="stack">
      <p className="notice notice-info">{unit.intro}</p>
      {unit.cases.map((c) => <PerspectiveCase key={c.id} c={c} />)}
    </div>
  );
}

function MoralPsychology({ unit }) {
  const [picked, setPicked] = useState({});
  const title = Object.fromEntries(unit.cards.map((c) => [c.id, c.title]));
  return (
    <div className="stack">
      <p className="notice notice-info">{unit.intro}</p>
      <div className="mpx-cards">
        {unit.cards.map((c) => <article key={c.id} className="mpx-card"><h4>{c.title}</h4><p>{c.text}</p></article>)}
      </div>
      <section className="panel stack">
        <h3>Which effect is this?</h3>
        <p className="hint">A practice check: not scored or saved.</p>
        {unit.quiz.map((q) => {
          const got = picked[q.id];
          return (
            <div key={q.id} className="stack-sm">
              <p>{q.scenario}</p>
              <div className="psy-quiz-opts" role="group" aria-label="Choose the effect">
                {q.options.map((o) => (
                  <button key={o} type="button" disabled={Boolean(got)}
                    className={`btn btn-secondary btn-sm ${got && o === q.answer ? 'psy-right' : ''} ${got === o && o !== q.answer ? 'psy-wrong' : ''}`}
                    onClick={() => setPicked((p) => ({ ...p, [q.id]: o }))}>{title[o] || o}</button>
                ))}
              </div>
              {got && <p className="hint" role="status">{got === q.answer ? 'Yes.' : `Closer to: ${title[q.answer]}.`}</p>}
            </div>
          );
        })}
      </section>
      <Reflect items={unit.reflect} />
    </div>
  );
}

export default function PsychologyLab({ classTopic, renderClass, requestedTab }) {
  const hasClass = Boolean(classTopic && renderClass);
  const [tab, setTab] = useState(hasClass ? 'class' : 'morale');
  const [units, setUnits] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let live = true;
    api('/api/psychology/units')
      .then((r) => { if (live) setUnits(Object.fromEntries((r.units || []).map((u) => [u.id, u]))); })
      .catch((e) => { if (live) setError(e.message || 'Could not load the psychology units.'); });
    return () => { live = false; };
  }, []);
  useEffect(() => { if (classTopic && renderClass) setTab('class'); }, [classTopic?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (!hasClass && tab === 'class') setTab('morale'); }, [hasClass, tab]);
  const tabs = [
    ...(hasClass ? [{ id: 'class', label: `Class ${classTopic.source?.classSeq ?? ''}`.trim(), icon: BookOpen }] : []),
    ...TABS,
  ];
  useEffect(() => {
    if (!requestedTab?.tab || (requestedTab.mode && requestedTab.mode !== 'psychology') || requestedTab.at === handledRequest) return;
    handledRequest = requestedTab.at;
    if (tabs.some((t) => t.id === requestedTab.tab)) setTab(requestedTab.tab);
  }, [requestedTab?.at]); // eslint-disable-line react-hooks/exhaustive-deps
  const body = () => {
    if (error) return <p className="notice notice-bad" role="alert">{error}</p>;
    if (!units) return <p className="hint" role="status">Loading…</p>;
    if (tab === 'morale' && units.morale) return <Morale unit={units.morale} />;
    if (tab === 'perspective' && units.perspective) return <Perspective unit={units.perspective} />;
    if (tab === 'moral' && units['moral-psychology']) return <MoralPsychology unit={units['moral-psychology']} />;
    return null;
  };
  return (
    <WorkspaceShell kind="Psychology" title="Psychology" tabs={tabs} current={tab} onTab={setTab}
      intro="How minds and groups work under pressure: what holds morale together, how the same event looks from each side, and how people actually make moral judgments. Reflective: nothing here is scored.">
      {tab === 'class' && hasClass ? renderClass(classTopic) : body()}
    </WorkspaceShell>
  );
}
