import React, { useEffect, useId, useRef, useState } from 'react';
import { DeskCard } from './common';

const MAX_BYTES = 25 * 1024 * 1024;
// offline images shipped in public/diagrams (never a remote address)
const BUILTIN = [
  { id: 'atom', label: 'Atom diagram', src: '/diagrams/atom.svg' },
  { id: 'cell', label: 'Cell diagram', src: '/diagrams/cell.svg' },
  { id: 'circuit', label: 'Circuit diagram', src: '/diagrams/circuit.svg' },
];
const PHI = 0.381966; // 1 - 1/golden ratio

const GUIDES = [
  { id: 'thirds', label: 'Rule of thirds', note: 'Two lines each way at 1/3 and 2/3. Subjects on the lines or crossings feel balanced.' },
  { id: 'golden', label: 'Golden section', note: 'Lines at about 38.2% and 61.8%, a proportion painters have long used for placing the focus.' },
  { id: 'diagonals', label: 'Diagonals', note: 'Corner to corner. Strong compositions often run a main line of movement along one.' },
];

function Overlay({ on }) {
  const common = { vectorEffect: 'non-scaling-stroke' };
  return (
    <svg className="kt-overlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true" focusable="false">
      {on.thirds && [100 / 3, 200 / 3].flatMap((v) => [
        <line key={`tv${v}`} x1={v} y1="0" x2={v} y2="100" className="kt-g-thirds" {...common} />,
        <line key={`th${v}`} x1="0" y1={v} x2="100" y2={v} className="kt-g-thirds" {...common} />,
      ])}
      {on.golden && [PHI * 100, (1 - PHI) * 100].flatMap((v) => [
        <line key={`gv${v}`} x1={v} y1="0" x2={v} y2="100" className="kt-g-golden" {...common} />,
        <line key={`gh${v}`} x1="0" y1={v} x2="100" y2={v} className="kt-g-golden" {...common} />,
      ])}
      {on.diagonals && (
        <>
          <line x1="0" y1="0" x2="100" y2="100" className="kt-g-diag" {...common} />
          <line x1="100" y1="0" x2="0" y2="100" className="kt-g-diag" {...common} />
        </>
      )}
    </svg>
  );
}

export default function ArtHistoryDesk() {
  const [source, setSource] = useState({ kind: 'blank', src: '', name: '' });
  const [on, setOn] = useState({ thirds: true, golden: false, diagonals: false });
  const [error, setError] = useState('');
  const urlRef = useRef('');
  const id = useId();

  const revoke = () => { if (urlRef.current) { URL.revokeObjectURL(urlRef.current); urlRef.current = ''; } };
  useEffect(() => revoke, []);

  const onFile = (e) => {
    const f = e.target.files?.[0];
    e.target.value = '';
    if (!f) return;
    if (!f.type.startsWith('image/')) { setError('Please choose an image file (PNG, JPEG, WebP, GIF or SVG).'); return; }
    if (f.size > MAX_BYTES) { setError('That image is larger than 25 MB. Choose a smaller one.'); return; }
    setError('');
    revoke();
    urlRef.current = URL.createObjectURL(f);
    setSource({ kind: 'file', src: urlRef.current, name: f.name });
  };
  const pick = (v) => {
    setError('');
    revoke();
    const b = BUILTIN.find((x) => x.id === v);
    setSource(b ? { kind: 'builtin', src: b.src, name: b.label } : { kind: 'blank', src: '', name: '' });
  };
  const toggle = (k) => setOn((o) => ({ ...o, [k]: !o[k] }));

  return (
    <div className="kt-desk">
      <DeskCard title="Composition guides" what="Lay classic composition guides over a picture to see how a painter may have placed the figures and the horizon. The image stays on your computer: it is not uploaded and nothing is fetched.">
        <div className="kt-two">
          <div className="field">
            <label htmlFor={`${id}-f`}>Your own image (from this device)</label>
            <input id={`${id}-f`} type="file" accept="image/*" className="kt-input" onChange={onFile} />
          </div>
          <div className="field">
            <label htmlFor={`${id}-b`}>Or a built-in image</label>
            <select id={`${id}-b`} className="kt-input" value={source.kind === 'builtin' ? BUILTIN.find((b) => b.src === source.src)?.id : source.kind === 'file' ? 'file' : ''} onChange={(e) => pick(e.target.value)}>
              <option value="">Blank grid (no image)</option>
              {source.kind === 'file' && <option value="file" disabled>{source.name}</option>}
              {BUILTIN.map((b) => <option key={b.id} value={b.id}>{b.label}</option>)}
            </select>
          </div>
        </div>
        {error && <div className="notice notice-bad" role="alert">{error}</div>}
        <fieldset className="kit-fields stack-sm">
          <legend className="label">Guides</legend>
          {GUIDES.map((g) => (
            <label key={g.id} className="kt-check kt-check-block">
              <input type="checkbox" checked={on[g.id]} onChange={() => toggle(g.id)} />
              <span><strong>{g.label}.</strong> <span className="hint">{g.note}</span></span>
            </label>
          ))}
        </fieldset>
        <div className="kt-plate" role="group" aria-label="Image with composition guides">
          {source.src
            ? <img src={source.src} alt={source.name ? `Your image: ${source.name}` : 'Selected image'} />
            : <div className="kt-blank" role="img" aria-label="Empty grid" />}
          <Overlay on={on} />
        </div>
        <ul className="kt-legend" aria-label="Legend">
          <li><svg width="28" height="8" aria-hidden="true"><line x1="0" y1="4" x2="28" y2="4" className="kt-g-thirds" /></svg> Thirds</li>
          <li><svg width="28" height="8" aria-hidden="true"><line x1="0" y1="4" x2="28" y2="4" className="kt-g-golden" /></svg> Golden section</li>
          <li><svg width="28" height="8" aria-hidden="true"><line x1="0" y1="4" x2="28" y2="4" className="kt-g-diag" /></svg> Diagonals</li>
        </ul>
        <p className="hint">Not every picture follows a rule. Ask what the guide shows and what the artist did instead.</p>
      </DeskCard>
    </div>
  );
}
