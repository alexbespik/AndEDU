import React, { useState } from 'react';
import { RotateCcw, Undo2 } from 'lucide-react';
import { THOUGHT_EXPERIMENTS } from './thoughtExperimentsData';
import '../../styles/philosophy.css';

function Echo({ echo }) {
  if (!echo) return null;
  return (
    <p className="phx-echo">
      This line of reasoning resembles the view of <strong>{echo.who}</strong> ({echo.school}), who argued {echo.argued}.
    </p>
  );
}

function Experiment({ exp, onBack }) {
  const [trail, setTrail] = useState([]); // [{nodeId, choice}]
  const nodeId = trail.length ? trail[trail.length - 1].choice.next : exp.root;
  const node = exp.nodes[nodeId];
  const finished = Boolean(node.reflect);
  const choose = (choice) => setTrail((t) => [...t, { nodeId, choice }]);

  return (
    <div className="stack">
      <div className="btn-row">
        <button type="button" className="btn btn-quiet btn-sm" onClick={onBack}>All thought experiments</button>
        <button type="button" className="btn btn-quiet btn-sm" disabled={!trail.length} onClick={() => setTrail((t) => t.slice(0, -1))}><Undo2 size={14} aria-hidden="true" /> One step back</button>
        <button type="button" className="btn btn-quiet btn-sm" disabled={!trail.length} onClick={() => setTrail([])}><RotateCcw size={14} aria-hidden="true" /> Start over</button>
      </div>
      <section className="panel stack" aria-labelledby={`te-${exp.id}`}>
        <h2 id={`te-${exp.id}`}>{exp.title}</h2>
        <p className="hint">{exp.origin}</p>
        <p>{exp.setup}</p>
      </section>
      {trail.length > 0 && (
        <ol className="phx-trail" aria-label="Your path so far">
          {trail.map(({ nodeId: id, choice }, i) => (
            <li key={i} className="stack-sm">
              <p className="hint">{exp.nodes[id].prompt}</p>
              <p><strong>You chose:</strong> {choice.label}</p>
              <Echo echo={choice.echo} />
            </li>
          ))}
        </ol>
      )}
      <section className="panel stack" aria-live="polite" aria-labelledby={`te-${exp.id}-q`}>
        <h3 id={`te-${exp.id}-q`}>{finished ? 'Questions to carry away' : node.prompt}</h3>
        {finished ? (
          <ul className="phx-reflect">{node.reflect.map((q) => <li key={q}>{q}</li>)}</ul>
        ) : (
          <div className="phx-choices">
            {node.choices.map((c) => <button key={c.label} type="button" className="btn btn-secondary phx-choice" onClick={() => choose(c)}>{c.label}</button>)}
          </div>
        )}
      </section>
    </div>
  );
}

export default function ThoughtExperimentsLab() {
  const [open, setOpen] = useState(null);
  const exp = THOUGHT_EXPERIMENTS.find((x) => x.id === open);
  return (
    <div className="stack">
      <p className="notice notice-info">These are for reflection. No choice is right or wrong, nothing is scored or compared with other people, and the notes
        about philosophers are short, simplified summaries: scholars read each thinker differently.</p>
      {exp ? <Experiment key={exp.id} exp={exp} onBack={() => setOpen(null)} /> : (
        <div className="phx-cards">
          {THOUGHT_EXPERIMENTS.map((x) => (
            <article key={x.id} className="panel stack-sm">
              <h2>{x.title}</h2>
              <p className="hint">{x.origin}</p>
              <p>{x.setup}</p>
              <div className="btn-row"><button type="button" className="btn btn-primary btn-sm" onClick={() => setOpen(x.id)}>Think it through</button></div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
