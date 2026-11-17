import React, { useEffect, useId, useMemo, useState } from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';
import { logicCheck } from './engine';
import { CIRCLES, CENTERS, FIGURES, NAMED, REGIONS, STATEMENT, depicts, drawPremises } from './venn';
import '../../styles/philosophy.css';

const KINDS = ['A', 'E', 'I', 'O'];
const KIND_NAME = { A: 'A: All … are …', E: 'E: No … are …', I: 'I: Some … are …', O: 'O: Some … are not …' };

function Venn({ drawing, labels, uid }) {
  const clip = (t) => `${uid}-c${t}`;
  const region = (r) => {
    const inc = [...r];
    const exc = ['S', 'P', 'M'].filter((t) => !r.includes(t));
    let node = <rect x="0" y="0" width="320" height="320" className={drawing.shaded.has(r) ? 'phx-shade' : 'phx-open'} mask={exc.length ? `url(#${uid}-m${r})` : undefined} />;
    inc.forEach((t) => { node = <g clipPath={`url(#${clip(t)})`}>{node}</g>; });
    return <g key={r}>{node}</g>;
  };
  const pos = (m) => {
    const pts = m.regions.map((r) => CENTERS[r]);
    return [pts.reduce((a, p) => a + p[0], 0) / pts.length, pts.reduce((a, p) => a + p[1], 0) / pts.length];
  };
  return (
    <svg className="phx-venn" viewBox="0 0 320 320" role="img" aria-label="Venn diagram of the premises">
      <defs>
        {Object.entries(CIRCLES).map(([t, c]) => <clipPath key={t} id={clip(t)}><circle cx={c.cx} cy={c.cy} r={c.r} /></clipPath>)}
        {REGIONS.filter((r) => r.length < 3).map((r) => (
          <mask key={r} id={`${uid}-m${r}`}>
            <rect x="0" y="0" width="320" height="320" fill="white" />
            {['S', 'P', 'M'].filter((t) => !r.includes(t)).map((t) => <circle key={t} cx={CIRCLES[t].cx} cy={CIRCLES[t].cy} r={CIRCLES[t].r} fill="black" />)}
          </mask>
        ))}
      </defs>
      {REGIONS.map(region)}
      {Object.entries(CIRCLES).map(([t, c]) => <circle key={t} cx={c.cx} cy={c.cy} r={c.r} className="phx-ring" />)}
      <text x="62" y="40" className="phx-term">{labels.S}</text>
      <text x="258" y="40" className="phx-term" textAnchor="middle">{labels.P}</text>
      <text x="160" y="308" className="phx-term" textAnchor="middle">{labels.M}</text>
      {drawing.marks.map((m, i) => {
        const [x, y] = pos(m);
        return m.kind === 'exist'
          ? <g key={i}><circle cx={x} cy={y} r="11" className="phx-ex-ring" /><text x={x} y={y + 5} textAnchor="middle" className="phx-mark">x</text></g>
          : <text key={i} x={x} y={y + 6} textAnchor="middle" className={`phx-mark ${m.kind === 'line' ? 'phx-line-mark' : ''}`}>X</text>;
      })}
    </svg>
  );
}

export default function SyllogismVennDesk() {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, '');
  const [mood, setMood] = useState(['A', 'A', 'A']);
  const [figure, setFigure] = useState(1);
  const [reading, setReading] = useState('boolean');
  const [names, setNames] = useState({ S: '', P: '', M: '' });
  const [res, setRes] = useState(null);
  const [error, setError] = useState(null);
  const form = `${mood.join('')}-${figure}`;

  useEffect(() => {
    let live = true;
    logicCheck({ op: 'syllogism', form, reading }).then((r) => {
      if (!live) return;
      if (r.ok) { setRes(r.result); setError(null); } else { setRes(null); setError(r.error.message); }
    });
    return () => { live = false; };
  }, [form, reading]);

  const label = (t) => names[t].trim() || t;
  const [majorShape, minorShape] = FIGURES[figure];
  const rows = [
    { title: 'Major premise', kind: mood[0], x: majorShape[0], y: majorShape[1] },
    { title: 'Minor premise', kind: mood[1], x: minorShape[0], y: minorShape[1] },
    { title: 'Conclusion', kind: mood[2], x: 'S', y: 'P' },
  ];
  const sentence = (r) => `${STATEMENT[r.kind][0]} ${label(r.x)} ${STATEMENT[r.kind][1]} ${label(r.y)}`;
  const existential = useMemo(() => (res?.valid && reading === 'aristotelian'
    ? res.needs_existence_of.map((n) => ({ minor: 'S', major: 'P', middle: 'M' })[n.role]) : []), [res, reading]);
  const drawing = useMemo(() => drawPremises(rows.slice(0, 2), existential), [mood, figure, existential]); // eslint-disable-line react-hooks/exhaustive-deps
  const shown = depicts(drawing, rows[2]);
  const setKind = (i, k) => setMood((m) => m.map((x, j) => (j === i ? k : x)));

  return (
    <div className="stack">
      <p className="hint">Pick the mood (the type of each statement) and the figure (where the middle term sits). The engine says whether the form is valid;
        the diagram draws the two premises so you can see why.</p>
      <div className="phx-grid">
        {rows.map((r, i) => (
          <div className="field" key={r.title}>
            <label htmlFor={`${uid}-k${i}`}>{r.title}</label>
            <select id={`${uid}-k${i}`} className="select" value={mood[i]} onChange={(e) => setKind(i, e.target.value)}>
              {KINDS.map((k) => <option key={k} value={k}>{KIND_NAME[k]}</option>)}
            </select>
          </div>
        ))}
        <div className="field">
          <label htmlFor={`${uid}-fig`}>Figure</label>
          <select id={`${uid}-fig`} className="select" value={figure} onChange={(e) => setFigure(Number(e.target.value))}>
            {[1, 2, 3, 4].map((f) => <option key={f} value={f}>Figure {f}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${uid}-read`}>Reading of "All"</label>
          <select id={`${uid}-read`} className="select" value={reading} onChange={(e) => setReading(e.target.value)}>
            <option value="boolean">Boolean (modern): no assumption that terms are non-empty</option>
            <option value="aristotelian">Aristotelian: every term names something</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor={`${uid}-named`}>Jump to a named form</label>
          <select id={`${uid}-named`} className="select" value="" onChange={(e) => {
            const [m, f] = e.target.value.split('-');
            if (m) { setMood([...m]); setFigure(Number(f)); if (NAMED.findIndex(([k]) => k === e.target.value) >= 15) setReading('aristotelian'); }
          }}>
            <option value="">Choose…</option>
            {NAMED.map(([k, n]) => <option key={k} value={k}>{k} {n}</option>)}
          </select>
        </div>
      </div>
      <fieldset className="phx-terms">
        <legend className="label">Your terms (optional, shown in the sentences and the diagram)</legend>
        {[['S', 'Minor term S'], ['P', 'Major term P'], ['M', 'Middle term M']].map(([t, lbl]) => (
          <label key={t} className="hint">{lbl}
            <input className="input" maxLength={24} value={names[t]} placeholder={t} onChange={(e) => setNames((n) => ({ ...n, [t]: e.target.value }))} />
          </label>
        ))}
      </fieldset>

      <div className="phx-venn-wrap">
        <Venn drawing={drawing} labels={{ S: label('S'), P: label('P'), M: label('M') }} uid={uid} />
        <div className="stack-sm" aria-live="polite">
          <ol className="phx-syl">
            {rows.map((r) => <li key={r.title}><span className="label">{r.title}: </span>{sentence(r)}</li>)}
          </ol>
          {error && <p className="notice notice-bad" role="alert">{error}</p>}
          {res && (
            <>
              <p className={`notice ${res.valid ? 'notice-ok' : 'notice-bad'}`}>
                {res.valid ? <CheckCircle2 size={14} aria-hidden="true" /> : <XCircle size={14} aria-hidden="true" />}{' '}
                <strong>{res.form}{res.name ? ` (${res.name})` : ''}</strong> is {res.valid ? 'valid' : 'invalid'} under the {res.reading} reading.
              </p>
              {res.violations.map((v) => <p key={v.rule} className="hint err"><code>{v.rule}</code>: {v.message}</p>)}
              {res.needs_existence_of.map((n) => (
                <p key={n.term} className="hint">This form is valid only if the {n.role} term ({label({ minor: 'S', major: 'P', middle: 'M' }[n.role])}) names something that exists; the circled x marks that assumption.</p>
              ))}
              {drawing.clash && <p className="hint err">The premises clash on the diagram: a mark would fall in a region the other premise empties.</p>}
              <p className="hint">Diagram check: the conclusion {shown ? 'is already drawn' : 'is not drawn'} by the premises. Shaded = empty; X = something is there;
                an X on a circle's edge means it is in one of the two regions it touches.</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
