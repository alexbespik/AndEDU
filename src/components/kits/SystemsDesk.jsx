import React, { useEffect, useState } from 'react';
import { Bar, DeskCard, Outcome, RunButton, pct, useTool } from './common';
import { Field, Presets, intRows, nums, num } from './stemCommon';

const CACHE_SIZES = [64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536, 131072, 1048576];
const BLOCK_SIZES = [4, 8, 16, 32, 64, 128];
const sizeLabel = (n) => (n >= 1024 ? `${n / 1024} KiB` : `${n} B`);
const WAYS = [['1', 'Direct-mapped (1)'], ['2', '2-way'], ['4', '4-way'], ['8', '8-way'], ['full', 'Fully associative']];

const CACHE_EXAMPLES = [
  { label: 'Textbook 32 KiB, 4-way', cfg: { bits: '32', size: 32768, block: 64, ways: '4', policy: 'lru', addr: '0x0000A1C0, 0x0000A1C4, 0x0000A200, 0x0000A1C0, 0x00010000' } },
  { label: 'Direct-mapped: conflict misses', cfg: { bits: '16', size: 64, block: 16, ways: '1', policy: 'lru', addr: '0, 64, 0, 64' } },
  { label: 'Same trace, 2-way', cfg: { bits: '16', size: 64, block: 16, ways: '2', policy: 'lru', addr: '0, 64, 0, 64' } },
];

const KIND_WORD = { compulsory: 'compulsory (first touch)', capacity: 'capacity (cache too small)', conflict: 'conflict (set too crowded)' };

function parseAddresses(text) {
  const parts = text.split(/[\s,;]+/).filter(Boolean);
  if (!parts.length) throw new Error('Enter at least one address.');
  if (parts.length > 256) throw new Error('Use at most 256 addresses.');
  parts.forEach((p) => { if (!/^(0[xX][0-9a-fA-F]+|\d+)$/.test(p)) throw new Error(`"${p}" is not an address. Use hex like 0x1A2B or a decimal number.`); });
  return parts;
}

function CacheDesk() {
  const first = CACHE_EXAMPLES[0].cfg;
  const [bits, setBits] = useState(first.bits);
  const [size, setSize] = useState(first.size);
  const [block, setBlock] = useState(first.block);
  const [ways, setWays] = useState(first.ways);
  const [policy, setPolicy] = useState(first.policy);
  const [addr, setAddr] = useState(first.addr);
  const [localError, setLocalError] = useState('');
  const [runKey, setRunKey] = useState(0);
  const [state, run] = useTool('systems');

  const submit = () => {
    setLocalError('');
    try {
      const b = Number(bits);
      if (!Number.isInteger(b) || b < 8 || b > 64) throw new Error('Address bits must be a whole number from 8 to 64.');
      if (block > size) throw new Error('A block cannot be larger than the whole cache.');
      const addresses = parseAddresses(addr);
      return run('cache', { address_bits: b, cache_size_bytes: size, block_size_bytes: block, ways: ways === 'full' ? 'full' : Number(ways), policy, addresses }, addresses);
    } catch (e) {
      setLocalError(e.message);
      return null;
    }
  };
  useEffect(() => { submit(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (runKey) submit(); }, [runKey]); // eslint-disable-line react-hooks/exhaustive-deps
  const load = (c) => { setBits(c.bits); setSize(c.size); setBlock(c.block); setWays(c.ways); setPolicy(c.policy); setAddr(c.addr); setRunKey((k) => k + 1); };

  return (
    <DeskCard title="Cache simulator" what="Splits each memory address into tag, set index and block offset, then replays a list of reads to show which hit the cache, which miss, and why.">
      <Presets items={CACHE_EXAMPLES.map((e) => ({ label: e.label, apply: () => load(e.cfg) }))} />
      <div className="kt-two">
        <Field label="Address width (bits)" className="kt-small">{(i) => <input id={i} className="kt-input kt-num" inputMode="numeric" value={bits} onChange={(e) => setBits(e.target.value)} />}</Field>
        <Field label="Cache size">{(i) => <select id={i} className="kt-input" value={size} onChange={(e) => setSize(Number(e.target.value))}>{CACHE_SIZES.map((n) => <option key={n} value={n}>{sizeLabel(n)}</option>)}</select>}</Field>
        <Field label="Block (line) size">{(i) => <select id={i} className="kt-input" value={block} onChange={(e) => setBlock(Number(e.target.value))}>{BLOCK_SIZES.map((n) => <option key={n} value={n}>{n} B</option>)}</select>}</Field>
        <Field label="Associativity (blocks per set)">{(i) => <select id={i} className="kt-input" value={ways} onChange={(e) => setWays(e.target.value)}>{WAYS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select>}</Field>
        <Field label="When a set is full, evict">{(i) => <select id={i} className="kt-input" value={policy} onChange={(e) => setPolicy(e.target.value)}><option value="lru">Least recently used (LRU)</option><option value="fifo">Oldest first (FIFO)</option></select>}</Field>
      </div>
      <Field label="Addresses read, in order" hint="Hex (0x1A2B) or decimal, separated by spaces or commas.">
        {(i) => <textarea id={i} className="kt-input kt-mono" rows={3} spellCheck={false} value={addr} onChange={(e) => setAddr(e.target.value)} />}
      </Field>
      <div className="btn-row"><RunButton loading={state.loading} onClick={submit}>Run the reads</RunButton></div>
      {localError && <div className="notice notice-bad" role="alert">{localError}</div>}
      <Outcome state={state} render={(r) => {
        const total = (r.bits?.tag || 0) + (r.bits?.index || 0) + (r.bits?.offset || 0) || 1;
        const parts = [['tag', 'Tag'], ['index', 'Index'], ['offset', 'Offset']];
        return (
          <>
            <div role="group" aria-label={`Address split: ${r.bits?.tag} tag bits, ${r.bits?.index} index bits, ${r.bits?.offset} offset bits`}>
              <div className="kt-bitbar">
                {parts.map(([k, name]) => r.bits?.[k] > 0 && <span key={k} className={`kt-bitseg kt-bit-${k}`} style={{ flexGrow: r.bits[k] }}>{name} {r.bits[k]}</span>)}
              </div>
              <p className="hint">{total} address bits: the offset picks the byte inside a block, the index picks one of {r.sets} set{r.sets === 1 ? '' : 's'}, the tag tells blocks that share a set apart.</p>
            </div>
            <Bar label="Hit rate" value={r.hit_rate} text={`${pct(r.hit_rate)} (${r.hits} hit${r.hits === 1 ? '' : 's'}, ${r.misses} miss${r.misses === 1 ? '' : 'es'})`} />
            <div className="kt-scroll">
              <table className="kt-table">
                <caption className="kt-sr">Each read: its tag, index and offset, and whether it hit</caption>
                <thead><tr><th scope="col">#</th><th scope="col">Address</th><th scope="col">Tag</th><th scope="col">Index</th><th scope="col">Offset</th><th scope="col">Result</th><th scope="col">Evicted tag</th></tr></thead>
                <tbody>
                  {(r.steps || []).map((s, i) => (
                    <tr key={i}>
                      <th scope="row">{i + 1}</th>
                      <td className="kt-mono">{state.tag?.[i] ?? s.address}</td>
                      <td className="kt-mono">{s.tag}</td><td className="kt-mono">{s.index}</td><td className="kt-mono">{s.offset}</td>
                      <td><span className={`kt-chip ${s.hit ? 'kt-chip-ok' : 'kt-chip-warn'}`}>{s.hit ? 'Hit' : 'Miss'}</span>{!s.hit && s.miss_kind && <span className="kt-sub"> {KIND_WORD[s.miss_kind] || s.miss_kind}</span>}</td>
                      <td className="kt-mono">{s.evicted_tag ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {r.touched_sets && Object.keys(r.touched_sets).length > 0 && (
              <details>
                <summary>Cache contents afterwards</summary>
                <ul className="kt-list kt-mono">{Object.entries(r.touched_sets).map(([k, tags]) => <li key={k}>set {k}: tags {tags.join(', ') || 'empty'}</li>)}</ul>
              </details>
            )}
          </>
        );
      }} />
    </DeskCard>
  );
}

const REQUEST_WORD = {
  ok: 'Granted: the state stays safe, so the system can hand these resources over.',
  exceeds_need: 'Refused: the process asked for more than it declared it would ever need.',
  must_wait: 'The process must wait: not enough of these resources are free right now.',
  unsafe: 'Refused: granting it would leave the system in an unsafe state, where a deadlock could follow.',
};

const BANKERS = {
  alloc: '0 1 0\n2 0 0\n3 0 2\n2 1 1\n0 0 2',
  max: '7 5 3\n3 2 2\n9 0 2\n2 2 2\n4 3 3',
  avail: '3 3 2',
};

function BankersDesk() {
  const [alloc, setAlloc] = useState(BANKERS.alloc);
  const [max, setMax] = useState(BANKERS.max);
  const [avail, setAvail] = useState(BANKERS.avail);
  const [useReq, setUseReq] = useState(false);
  const [proc, setProc] = useState('1');
  const [vec, setVec] = useState('1 0 2');
  const [localError, setLocalError] = useState('');
  const [runKey, setRunKey] = useState(0);
  const [state, run] = useTool('systems');

  const submit = (withReq = useReq) => {
    setLocalError('');
    try {
      const args = { allocation: intRows(alloc, 'Allocation'), max_claim: intRows(max, 'Maximum claim'), available: nums(avail, 'Available').map((v, i) => { if (!Number.isInteger(v) || v < 0) throw new Error(`Available, value ${i + 1}: use a whole number, 0 or more.`); return v; }) };
      if (args.allocation.length !== args.max_claim.length) throw new Error('Allocation and maximum claim need the same number of processes (rows).');
      if (withReq) {
        const p = num(proc, 'Process number');
        if (!Number.isInteger(p) || p < 0 || p >= args.allocation.length) throw new Error(`Process number must be from 0 to ${args.allocation.length - 1}.`);
        args.request = { process: p, vector: intRows(vec, 'Request')[0] };
      }
      return run('bankers', args, args.request ? { process: args.request.process, vector: args.request.vector } : null);
    } catch (e) {
      setLocalError(e.message);
      return null;
    }
  };
  useEffect(() => { submit(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (runKey) submit(); }, [runKey]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <DeskCard title="Banker's algorithm (deadlock avoidance)" what="Checks whether a resource-allocation state is safe, meaning some order exists in which every process can finish, and whether a new request can be granted without losing that.">
      <Presets items={[
        { label: 'Textbook state (5 processes, 3 resources)', apply: () => { setAlloc(BANKERS.alloc); setMax(BANKERS.max); setAvail(BANKERS.avail); setUseReq(false); setRunKey((k) => k + 1); } },
        { label: 'Then: P1 requests (1, 0, 2)', apply: () => { setAlloc(BANKERS.alloc); setMax(BANKERS.max); setAvail(BANKERS.avail); setUseReq(true); setProc('1'); setVec('1 0 2'); setRunKey((k) => k + 1); } },
      ]} />
      <div className="kt-two">
        <Field label="Allocation (one row per process: resources held now)">{(i) => <textarea id={i} className="kt-input kt-mono" rows={5} spellCheck={false} value={alloc} onChange={(e) => setAlloc(e.target.value)} />}</Field>
        <Field label="Maximum claim (most each process may ever hold)">{(i) => <textarea id={i} className="kt-input kt-mono" rows={5} spellCheck={false} value={max} onChange={(e) => setMax(e.target.value)} />}</Field>
      </div>
      <Field label="Available (free units of each resource)" className="kt-small">{(i) => <input id={i} className="kt-input kt-mono" value={avail} onChange={(e) => setAvail(e.target.value)} />}</Field>
      <label className="kt-check"><input type="checkbox" checked={useReq} onChange={(e) => setUseReq(e.target.checked)} /> Also test one new request</label>
      {useReq && (
        <div className="kt-two">
          <Field label="Process making the request (0 is the first row)" className="kt-small">{(i) => <input id={i} className="kt-input kt-num" inputMode="numeric" value={proc} onChange={(e) => setProc(e.target.value)} />}</Field>
          <Field label="Units requested of each resource">{(i) => <input id={i} className="kt-input kt-mono" value={vec} onChange={(e) => setVec(e.target.value)} />}</Field>
        </div>
      )}
      <div className="btn-row"><RunButton loading={state.loading} onClick={() => submit()}>Check safety</RunButton></div>
      {localError && <div className="notice notice-bad" role="alert">{localError}</div>}
      <Outcome state={state} render={(r) => (
        <>
          {r.safe
            ? <p className="notice notice-ok"><strong>Safe state.</strong> Processes can all finish in this order: {(r.sequence || []).map((p, i) => <span key={i} className="kt-chip kt-chip-ok">P{p}</span>)}</p>
            : <p className="notice notice-bad" role="alert"><strong>Unsafe state.</strong> No order lets every process finish, so a deadlock is possible.</p>}
          <div className="kt-scroll">
            <table className="kt-table kt-matrix">
              <caption className="kt-sr">Remaining need of each process (maximum minus allocation)</caption>
              <thead><tr><th scope="col">Process</th><th scope="col">Need</th></tr></thead>
              <tbody>{(r.need || []).map((row, i) => <tr key={i}><th scope="row">P{i}</th><td className="kt-mono">{row.join(' ')}</td></tr>)}</tbody>
            </table>
          </div>
          {r.steps?.length > 0 && (
            <details open>
              <summary>How the order was found</summary>
              <ol className="kt-list">
                {r.steps.map((s, i) => (
                  <li key={i}><strong>P{s.process}</strong> needs <span className="kt-mono">({(s.need || []).join(', ')})</span>, which fits in the free <span className="kt-mono">({(s.work_before || []).join(', ')})</span>. It finishes and returns its units: free becomes <span className="kt-mono">({(s.work_after || []).join(', ')})</span>.</li>
                ))}
              </ol>
            </details>
          )}
          {r.request_result && (
            <p className={`notice ${r.request_result.granted ? 'notice-ok' : 'notice-bad'}`}>
              <strong>Request P{state.tag?.process} ({(state.tag?.vector || []).join(', ')}):</strong> {REQUEST_WORD[r.request_result.reason] || (r.request_result.granted ? 'Granted.' : 'Refused.')}
              {r.request_result.granted && r.request_result.state_after?.available && <> Free afterwards: <span className="kt-mono">({r.request_result.state_after.available.join(', ')})</span>.</>}
            </p>
          )}
        </>
      )} />
    </DeskCard>
  );
}

export default function SystemsDesk() {
  return (
    <div className="kt-desk">
      <CacheDesk />
      <BankersDesk />
    </div>
  );
}
