import React, { useEffect, useState } from 'react';
import { DeskCard, Outcome, RunButton, pct, useTool } from './common';
import { Choice, Field, Presets, num } from './stemCommon';

const clean = (s) => String(s || '').replace(/\s+/g, '').toUpperCase();

const ALIGN_EXAMPLES = [
  { label: 'Local: TGTTACGG vs GGTTGACTA', s: { seq1: 'TGTTACGG', seq2: 'GGTTGACTA', mode: 'local', match: '3', mismatch: '-3', gap: '-2' } },
  { label: 'Global: GCATGCG vs GATTACA', s: { seq1: 'GCATGCG', seq2: 'GATTACA', mode: 'global', match: '1', mismatch: '-1', gap: '-1' } },
];

const CHUNK = 60;

function AlignmentText({ r }) {
  const a1 = r.aligned1 || ''; const a2 = r.aligned2 || ''; const mid = r.midline || '';
  const chunks = [];
  for (let i = 0; i < a1.length; i += CHUNK) chunks.push(i);
  const cls = (c, top, bottom) => (c === '|' ? 'kt-aln-match' : c === '.' ? 'kt-aln-mis' : top === '-' || bottom === '-' ? 'kt-aln-gap' : '');
  return (
    <div className="kt-scroll">
      <div className="kt-aln" role="group" aria-label="Aligned sequences, top, match line, bottom">
        {chunks.map((i) => (
          <div key={i} className="kt-aln-block">
            {[[a1, 'Sequence 1'], [mid, 'Match'], [a2, 'Sequence 2']].map(([line, name]) => (
              <div key={name} className="kt-aln-row" aria-label={name}>
                {line.slice(i, i + CHUNK).split('').map((ch, k) => <span key={k} className={cls(mid[i + k], a1[i + k], a2[i + k])}>{ch === ' ' ? ' ' : ch}</span>)}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function Grid({ r, seq1, seq2 }) {
  const m = r.matrix;
  const onPath = new Set((r.path || []).map(([i, j]) => `${i},${j}`));
  const okDims = m.length === seq1.length + 1 && m[0]?.length === seq2.length + 1;
  return (
    <div className="kt-scroll">
      <table className="kt-table kt-matrix kt-dp">
        <caption className="kt-sr">Scoring grid; the cells on the traceback path are highlighted</caption>
        <thead>
          <tr><th scope="col"><span className="kt-sr">Row letter</span></th><th scope="col"><span className="kt-sr">start</span></th>{(okDims ? seq2.split('') : (m[0] || []).slice(1).map(() => '')).map((c, j) => <th key={j} scope="col">{c}</th>)}</tr>
        </thead>
        <tbody>
          {m.map((row, i) => (
            <tr key={i}>
              <th scope="row">{i === 0 ? '' : (okDims ? seq1[i - 1] : '')}</th>
              {row.map((v, j) => <td key={j} className={`kt-mono${onPath.has(`${i},${j}`) ? ' kt-onpath' : ''}`}>{v}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PathPlot({ r, n, m }) {
  const pts = r.path || [];
  if (pts.length < 2) return null;
  const W = 300; const H = Math.max(80, Math.min(300, (W * n) / Math.max(m, 1)));
  const sx = (j) => 10 + (j / Math.max(m, 1)) * (W - 20);
  const sy = (i) => 10 + (i / Math.max(n, 1)) * (H - 20);
  return (
    <svg className="kt-plot kt-pathplot" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Traceback path through the scoring grid, from the start corner to the end">
      <rect className="kt-axis" x="10" y="10" width={W - 20} height={H - 20} fill="none" />
      <path className="kt-line t0" d={pts.map(([i, j], k) => `${k ? 'L' : 'M'}${sx(j).toFixed(1)},${sy(i).toFixed(1)}`).join('')} />
      <text className="kt-axis-text" x={W / 2} y={H - 1} textAnchor="middle">sequence 2 (across), sequence 1 (down)</text>
    </svg>
  );
}

function AlignDesk() {
  const [v, setV] = useState(ALIGN_EXAMPLES[0].s);
  const [localError, setLocalError] = useState('');
  const [runKey, setRunKey] = useState(0);
  const [state, run] = useTool('bio');
  const set = (k) => (e) => setV((o) => ({ ...o, [k]: e.target.value }));

  const submit = () => {
    setLocalError('');
    try {
      const seq1 = clean(v.seq1); const seq2 = clean(v.seq2);
      if (!seq1 || !seq2) throw new Error('Enter both sequences.');
      if (!/^[A-Z]+$/.test(seq1 + seq2)) throw new Error('Sequences may only contain letters.');
      if (seq1.length > 300 || seq2.length > 300) throw new Error('Each sequence can be at most 300 letters.');
      const sc = {};
      for (const [k, label] of [['match', 'Match score'], ['mismatch', 'Mismatch score'], ['gap', 'Gap score']]) {
        sc[k] = num(v[k], label);
        if (!Number.isInteger(sc[k]) || sc[k] < -100 || sc[k] > 100) throw new Error(`${label} must be a whole number from -100 to 100.`);
      }
      return run('align', { seq1, seq2, mode: v.mode, ...sc }, JSON.stringify([seq1, seq2]));
    } catch (e) {
      setLocalError(e.message);
      return null;
    }
  };
  useEffect(() => { submit(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (runKey) submit(); }, [runKey]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <DeskCard title="Sequence alignment" what="Lines two sequences up to show where they match. Global alignment (Needleman-Wunsch) matches them end to end; local alignment (Smith-Waterman) finds the best matching stretch.">
      <Presets items={ALIGN_EXAMPLES.map((e) => ({ label: e.label, apply: () => { setV(e.s); setRunKey((k) => k + 1); } }))} />
      <Choice label="Alignment type" value={v.mode} onChange={(mode) => setV((o) => ({ ...o, mode }))} options={[['local', 'Local (best matching stretch)'], ['global', 'Global (end to end)']]} />
      <div className="kt-two">
        <Field label="Sequence 1 (letters, up to 300)">{(i) => <input id={i} className="kt-input kt-mono" spellCheck={false} value={v.seq1} onChange={set('seq1')} />}</Field>
        <Field label="Sequence 2 (letters, up to 300)">{(i) => <input id={i} className="kt-input kt-mono" spellCheck={false} value={v.seq2} onChange={set('seq2')} />}</Field>
      </div>
      <div className="kt-row kt-wrap">
        <Field label="Match score" className="kt-small">{(i) => <input id={i} className="kt-input kt-num" inputMode="numeric" value={v.match} onChange={set('match')} />}</Field>
        <Field label="Mismatch score" className="kt-small">{(i) => <input id={i} className="kt-input kt-num" inputMode="numeric" value={v.mismatch} onChange={set('mismatch')} />}</Field>
        <Field label="Gap score (per gap)" className="kt-small">{(i) => <input id={i} className="kt-input kt-num" inputMode="numeric" value={v.gap} onChange={set('gap')} />}</Field>
      </div>
      <div className="btn-row"><RunButton loading={state.loading} onClick={submit}>Align</RunButton></div>
      {localError && <div className="notice notice-bad" role="alert">{localError}</div>}
      <Outcome state={state} render={(r) => {
        let seqs;
        try { seqs = JSON.parse(state.tag); } catch { seqs = ['', '']; }
        const len = (r.aligned1 || '').length;
        if (!len) return <p className="notice">No alignment scores above 0 with these settings: the sequences share no stretch that beats the mismatch and gap penalties.</p>;
        return (
          <>
            <p>Score <strong>{r.score}</strong>. Identity <strong>{pct(r.identity)}</strong> over {len} columns, <strong>{r.gaps}</strong> gap{r.gaps === 1 ? '' : 's'}.
              {r.start && r.end && <> Covers letters {r.start[0]} to {r.end[0]} of sequence 1 and {r.start[1]} to {r.end[1]} of sequence 2.</>}</p>
            <AlignmentText r={r} />
            <p className="hint">Midline: | match, . mismatch, blank = a gap (a dash in the other row).</p>
            {r.matrix ? <Grid r={r} seq1={seqs[0]} seq2={seqs[1]} /> : <PathPlot r={r} n={seqs[0].length} m={seqs[1].length} />}
          </>
        );
      }} />
    </DeskCard>
  );
}

const FRAMES = ['+1', '+2', '+3', '-1', '-2', '-3'];
const ORF_SAMPLE = `GGC${'ATGGCCAAAGGTGAAGCTTTCGGAACTGGTTAA'}CTA${'TCACTTAAACCCGGGTTTCAT'}GCC`;

function FrameMap({ orfs, length, strands }) {
  const W = 560; const L = 34; const R = 10; const rowH = 22;
  const frames = strands === 'forward' ? FRAMES.slice(0, 3) : FRAMES;
  const H = frames.length * rowH + 28;
  const sx = (p) => L + ((p - 1) / Math.max(length, 1)) * (W - L - R);
  return (
    <svg className="kt-plot" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Open reading frames along a ${length} letter sequence, one track per reading frame`}>
      {frames.map((f, k) => {
        const y = 8 + k * rowH;
        return (
          <g key={f}>
            <text className="kt-axis-text" x={L - 6} y={y + 12} textAnchor="end">{f}</text>
            <line className="kt-gridline" x1={L} x2={W - R} y1={y + 8} y2={y + 8} />
            {orfs.filter((o) => o.frame === f).map((o, i) => {
              const a = Math.min(o.start, o.end); const b = Math.max(o.start, o.end);
              return <rect key={i} className={`kt-orf ${f.startsWith('-') ? 't1' : 't0'}`} x={sx(a)} y={y + 1} width={Math.max(2, sx(b + 1) - sx(a))} height="14" rx="2"><title>{`Frame ${f}: ${a} to ${b} (${o.length_nt} letters)`}</title></rect>;
            })}
          </g>
        );
      })}
      <line className="kt-axis" x1={L} x2={W - R} y1={H - 18} y2={H - 18} />
      <text className="kt-axis-text" x={L} y={H - 5}>1</text>
      <text className="kt-axis-text" x={W - R} y={H - 5} textAnchor="end">{length}</text>
    </svg>
  );
}

function OrfDesk() {
  const [dna, setDna] = useState(ORF_SAMPLE);
  const [minCodons, setMinCodons] = useState('5');
  const [strands, setStrands] = useState('both');
  const [localError, setLocalError] = useState('');
  const [state, run] = useTool('bio');

  const submit = () => {
    setLocalError('');
    try {
      const s = clean(dna).replace(/U/g, 'T');
      if (s.length < 3) throw new Error('Enter at least 3 letters of DNA.');
      if (s.length > 20000) throw new Error('The sequence can be at most 20000 letters.');
      const bad = s.match(/[^ACGT]/);
      if (bad) throw new Error(`"${bad[0]}" is not a DNA letter. Use only A, C, G and T (spaces and line breaks are fine).`);
      const mc = Number(minCodons);
      if (!Number.isInteger(mc) || mc < 1 || mc > 1000) throw new Error('Minimum length must be a whole number of codons from 1 to 1000.');
      return run('orf', { dna: s, min_codons: mc, strands }, `${s.length}:${strands}`);
    } catch (e) {
      setLocalError(e.message);
      return null;
    }
  };
  useEffect(() => { submit(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <DeskCard title="Gene finder (open reading frames)" what="Reads DNA in all six reading frames (three on each strand) and lists the stretches that start with ATG and run to a stop codon, then translates each into a protein.">
      <Presets items={[{ label: 'Sample with one ORF on each strand', apply: () => { setDna(ORF_SAMPLE); setMinCodons('5'); setStrands('both'); } }]} />
      <Field label="DNA sequence (A, C, G, T; spaces and line breaks are ignored)">{(i) => <textarea id={i} className="kt-input kt-mono" rows={4} spellCheck={false} value={dna} onChange={(e) => setDna(e.target.value)} />}</Field>
      <div className="kt-row kt-wrap">
        <Field label="Shortest ORF to show (codons, counting the start)" className="kt-small">{(i) => <input id={i} className="kt-input kt-num" inputMode="numeric" value={minCodons} onChange={(e) => setMinCodons(e.target.value)} />}</Field>
        <div className="field">
          <Choice label="Strands to read" value={strands} onChange={setStrands} options={[['both', 'Both strands'], ['forward', 'Forward only']]} />
        </div>
      </div>
      <div className="btn-row"><RunButton loading={state.loading} onClick={submit}>Find the ORFs</RunButton></div>
      {localError && <div className="notice notice-bad" role="alert">{localError}</div>}
      <Outcome state={state} render={(r) => {
        const [lenText, strandMode] = String(state.tag || '0:both').split(':');
        const length = Number(lenText) || 1;
        const orfs = r.orfs || [];
        return (
          <>
            <h3 className="kt-h3">Six-frame map</h3>
            <FrameMap orfs={orfs} length={length} strands={strandMode} />
            <p className="hint">Each bar is one ORF in its reading frame (+ forward strand, - reverse strand).</p>
            {orfs.length === 0
              ? <p className="notice">No ORF of that length was found. Try a lower minimum or a longer sequence.</p>
              : (
                <div className="kt-scroll">
                  <table className="kt-table">
                    <caption className="kt-sr">Open reading frames, longest first</caption>
                    <thead><tr><th scope="col">Frame</th><th scope="col">From</th><th scope="col">To</th><th scope="col">Length (letters)</th><th scope="col">Protein</th></tr></thead>
                    <tbody>
                      {orfs.map((o, i) => (
                        <tr key={i}><th scope="row">{o.frame}</th><td>{o.start}</td><td>{o.end}</td><td>{o.length_nt}</td><td className="kt-mono kt-wrapany">{o.protein}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            {r.truncated && <p className="hint">The list is cut short: only the 100 longest ORFs are shown.</p>}
            {r.orfs?.some((o) => o.start > o.end) && <p className="hint">On the reverse strand an ORF runs backwards, so its "From" is larger than its "To".</p>}
            {r.frames?.length > 0 && (
              <details>
                <summary>Translation of each frame (stops shown as *)</summary>
                <dl className="kt-dl">
                  {r.frames.map((f) => (<React.Fragment key={f.frame}><dt>Frame {f.frame}</dt><dd className="kt-mono">{f.protein}</dd></React.Fragment>))}
                </dl>
              </details>
            )}
          </>
        );
      }} />
    </DeskCard>
  );
}

export default function BioDesk() {
  return (
    <div className="kt-desk">
      <AlignDesk />
      <OrfDesk />
    </div>
  );
}
