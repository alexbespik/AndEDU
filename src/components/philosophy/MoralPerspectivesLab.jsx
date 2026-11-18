import React, { useEffect, useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { api } from '../../lib/api';
import '../../styles/moral.css';

/**
 * Moral perspectives: the student places their own answer on a cautious-to-hard-line axis, then sees where four
 * ethical frameworks tend to land. Reflective only: never scored, no XP, no events (psychology.py, ARCHITECTURE 3.12).
 */
export function MoralAxis({ axis, value, bands, frameworks }) {
  return (
    <div className="mpx-axis" aria-hidden="true">
      <div className="mpx-track">
        {bands && Object.entries(bands).map(([id, b], i) => (
          <div key={id} className={`mpx-band mpx-band-${i}`} style={{ left: `${b.band[0]}%`, width: `${b.band[1] - b.band[0]}%`, top: `${8 + i * 17}px` }}
            title={frameworks?.[id]}>
            <span>{frameworks?.[id]?.split(' (')[0]}</span>
          </div>
        ))}
        {value != null && <div className="mpx-mark" style={{ left: `${value}%` }}><span>You</span></div>}
      </div>
      <div className="mpx-ends"><span>{axis.left}</span><span>{axis.right}</span></div>
    </div>
  );
}

function Dilemma({ d, axis, frameworks }) {
  const [value, setValue] = useState(50);
  const [revealed, setRevealed] = useState(false);
  const lean = value < 40 ? axis.left : value > 60 ? axis.right : 'the middle';
  return (
    <div className="stack">
      <section className="panel stack" aria-labelledby={`mp-${d.id}`}>
        <h2 id={`mp-${d.id}`}>{d.title}</h2>
        <p>{d.setup}</p>
        <p><strong>{d.question}</strong></p>
        <label className="stack-sm">
          <span className="label">Where does your answer sit?</span>
          <input type="range" min="0" max="100" step="1" value={value} className="mpx-slider"
            aria-valuetext={`${value} of 100, leaning toward ${lean}`}
            onChange={(e) => { setValue(Number(e.target.value)); }} />
          <span className="mpx-ends hint"><span>{axis.left}</span><span>{axis.right}</span></span>
        </label>
        <div className="btn-row">
          {!revealed
            ? <button type="button" className="btn btn-primary btn-sm" onClick={() => setRevealed(true)}>Compare with the frameworks</button>
            : <button type="button" className="btn btn-quiet btn-sm" onClick={() => { setRevealed(false); setValue(50); }}><RotateCcw size={14} aria-hidden="true" /> Start over</button>}
        </div>
      </section>
      {revealed && (
        <section className="panel stack" aria-live="polite" aria-labelledby={`mp-${d.id}-f`}>
          <h3 id={`mp-${d.id}-f`}>How the frameworks tend to argue</h3>
          <MoralAxis axis={axis} value={value} bands={d.frameworks} frameworks={frameworks} />
          <p className="hint">{axis.note} The bands are rough tendencies of how each view is often argued, not verdicts, and none of them is the answer.</p>
          <div className="mpx-cards">
            {Object.entries(d.frameworks).map(([id, f], i) => (
              <article key={id} className={`mpx-card mpx-card-${i}`}>
                <h4>{frameworks[id]}</h4>
                <p>{f.argues}</p>
                <p className="hint">
                  {value >= f.band[0] && value <= f.band[1] ? 'Your answer sits inside this band.' : `Your answer sits ${value < f.band[0] ? 'more cautious' : 'more hard-line'} than this band.`}
                </p>
              </article>
            ))}
          </div>
          {d.reflect?.length > 0 && (
            <>
              <h4>Questions to carry away</h4>
              <ul className="phx-reflect">{d.reflect.map((q) => <li key={q}>{q}</li>)}</ul>
            </>
          )}
        </section>
      )}
    </div>
  );
}

export default function MoralPerspectivesLab() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [open, setOpen] = useState(null);
  useEffect(() => {
    let live = true;
    api('/api/philosophy/moral-dilemmas').then((r) => { if (live) setData(r); }).catch((e) => { if (live) setError(e.message || 'Could not load the dilemmas.'); });
    return () => { live = false; };
  }, []);
  if (error) return <p className="notice notice-bad" role="alert">{error}</p>;
  if (!data) return <p className="hint" role="status">Loading…</p>;
  const d = data.dilemmas.find((x) => x.id === open);
  if (d) {
    return (
      <div className="stack">
        <div className="btn-row"><button type="button" className="btn btn-quiet btn-sm" onClick={() => setOpen(null)}>All dilemmas</button></div>
        <Dilemma key={d.id} d={d} axis={data.axis} frameworks={data.frameworks} />
      </div>
    );
  }
  return (
    <div className="stack">
      <p className="notice notice-info">
        Place your answer on a line from <strong>{data.axis.left.toLowerCase()}</strong> to <strong>{data.axis.right.toLowerCase()}</strong>,
        then see how four ethical frameworks tend to argue the same case. Nothing here is scored: the point is to see your own reasoning next to theirs.
      </p>
      <div className="mpx-list">
        {data.dilemmas.map((x) => (
          <button key={x.id} type="button" className="panel mpx-pick" onClick={() => setOpen(x.id)}>
            <strong>{x.title}</strong>
            <span className="hint">{x.question}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
