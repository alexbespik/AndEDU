import React, { useEffect, useId, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { Bar, DeskCard, Outcome, RunButton, fracValue, pct, toInt, useTool } from './common';

const METHODS = [
  { id: 'dhondt', label: "D'Hondt", what: 'Divides each party\'s votes by 1, 2, 3 ... and gives the next seat to the largest quotient. Favours big parties.' },
  { id: 'sainte_lague', label: 'Sainte-Lague', what: 'Divides by 1, 3, 5 ...: a more even split between large and small parties.' },
  { id: 'fptp', label: 'First past the post', what: 'Each district elects its top candidate; a party\'s seats are the districts it won.' },
  { id: 'droop_stv', label: 'Droop STV', what: 'Ranked ballots, several seats: candidates reaching the Droop quota win; surplus votes pass on at a reduced weight.' },
  { id: 'irv', label: 'Instant runoff', what: 'Ranked ballots, one seat: the last-place candidate is dropped each round and their ballots move to the next choice.' },
];

const DEFAULT_VOTES = [
  { party: 'Conservatives', votes: '38000' }, { party: 'Labour', votes: '31000' }, { party: 'Centre', votes: '17000' },
  { party: 'Greens', votes: '12000' }, { party: 'Liberals', votes: '2000' },
];
const DEFAULT_DISTRICTS = 'Conservatives 40, Labour 35, Greens 25\nConservatives 30, Labour 38, Centre 32\nLabour 45, Conservatives 41, Centre 14\nCentre 36, Conservatives 33, Labour 31\nConservatives 52, Labour 30, Greens 18';
const DEFAULT_BALLOTS = '34: Ana > Ben > Cy\n22: Ben > Cy > Ana\n18: Cy > Ben > Ana\n16: Dee > Ana > Ben\n10: Dee > Cy > Ben';

function parsePairs(text) {
  const out = [];
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
  for (let i = 0; i < lines.length; i += 1) {
    const d = {};
    for (const part of lines[i].split(',')) {
      const m = part.trim().match(/^(.+?)[\s:=]+(\d+)$/);
      if (!m) throw new Error(`District ${i + 1}: write each party as "Name 40", separated by commas.`);
      d[m[1].trim()] = Number(m[2]);
    }
    out.push(d);
  }
  if (!out.length) throw new Error('Add at least one district.');
  return out;
}

function parseBallots(text) {
  const ballots = [];
  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
  for (let i = 0; i < lines.length; i += 1) {
    const m = lines[i].match(/^(\d+)\s*:\s*(.+)$/);
    if (!m) throw new Error(`Ballot line ${i + 1}: write it as "12: Ana > Ben > Cy" (how many voters, then the ranking).`);
    ballots.push({ count: Number(m[1]), ranking: m[2].split('>').map((s) => s.trim()).filter(Boolean) });
  }
  if (!ballots.length) throw new Error('Add at least one ballot line.');
  const candidates = [];
  ballots.forEach((b) => b.ranking.forEach((c) => { if (!candidates.includes(c)) candidates.push(c); }));
  return { ballots, candidates };
}

const fmt = (s) => { const v = fracValue(s); return Number.isInteger(v) ? String(v) : v.toFixed(2); };

function SeatTable({ r }) {
  const parties = Object.keys({ ...(r.shares || {}), ...(r.seats || {}) }).sort((a, b) => (r.seats[b] || 0) - (r.seats[a] || 0) || a.localeCompare(b));
  const total = Object.values(r.seats || {}).reduce((a, b) => a + b, 0) || 1;
  return (
    <>
      <table className="kt-table">
        <caption className="kt-sr">Seats won by each party</caption>
        <thead><tr><th scope="col">Party</th><th scope="col">Votes</th><th scope="col">Seats</th><th scope="col">Seat share</th></tr></thead>
        <tbody>
          {parties.map((p) => (
            <tr key={p}>
              <th scope="row">{p}</th>
              <td>{r.shares?.[p] ? pct(r.shares[p].votes_pct / 100) : '-'}</td>
              <td>{r.seats?.[p] ?? 0}</td>
              <td>{r.shares?.[p] ? pct(r.shares[p].seats_pct / 100) : '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="kt-bars" role="group" aria-label="Votes compared with seats">
        {parties.map((p) => (
          <div key={p} className="kt-pair">
            <strong>{p}</strong>
            <Bar label="votes" value={(r.shares?.[p]?.votes_pct || 0) / 100} text={pct((r.shares?.[p]?.votes_pct || 0) / 100)} tone="kt-soft" />
            <Bar label="seats" value={(r.seats?.[p] || 0) / total} text={pct((r.seats?.[p] || 0) / total)} />
          </div>
        ))}
      </div>
      <p className="hint">Gallagher index: <strong>{r.gallagher}</strong>. It measures how far seat shares drift from vote shares; 0 means a perfect match.</p>
      {r.rounds?.length > 0 && (
        <details>
          <summary>Seat by seat ({r.rounds.length})</summary>
          <ol className="kt-list">
            {r.rounds.map((x) => <li key={x.seat}>Seat {x.seat} goes to <strong>{x.party}</strong> (quotient {fmt(x.quotient)})</li>)}
          </ol>
        </details>
      )}
    </>
  );
}

function StvResult({ r }) {
  return (
    <>
      <p>Quota to win a seat: <strong>{r.quota}</strong> votes. Elected: {r.elected?.length ? r.elected.map((c) => <span key={c} className="kt-chip kt-chip-ok">{c}</span>) : 'nobody'}</p>
      <ol className="kt-list">
        {r.rounds?.map((rd, i) => (
          <li key={i}>
            <strong>{rd.action === 'elect' ? `Elected: ${rd.who}` : `Excluded: ${rd.who}`}</strong>
            <span className="kt-sub"> tally: {Object.entries(rd.tally || {}).map(([c, v]) => `${c} ${fmt(v)}`).join(' | ')}</span>
          </li>
        ))}
      </ol>
    </>
  );
}

function IrvResult({ r }) {
  return (
    <>
      <p>Winner: <span className="kt-chip kt-chip-ok">{r.winner}</span></p>
      {r.rounds?.map((rd, i) => {
        const total = Object.values(rd).reduce((a, b) => a + b, 0) || 1;
        return (
          <div key={i} className="kt-round">
            <strong>Round {i + 1}{r.eliminated?.[i] ? `: ${r.eliminated[i]} drops out` : ''}</strong>
            {Object.entries(rd).sort((a, b) => b[1] - a[1]).map(([c, v]) => <Bar key={c} label={c} value={v / total} text={`${v}`} tone={c === r.eliminated?.[i] ? 'kt-bad' : ''} />)}
          </div>
        );
      })}
    </>
  );
}

function MethodDesk() {
  const [method, setMethod] = useState('dhondt');
  const [seats, setSeats] = useState('8');
  const [rows, setRows] = useState(DEFAULT_VOTES);
  const [districts, setDistricts] = useState(DEFAULT_DISTRICTS);
  const [ballots, setBallots] = useState(DEFAULT_BALLOTS);
  const [localError, setLocalError] = useState('');
  const [state, run] = useTool('polity');
  const id = useId();
  const meta = METHODS.find((m) => m.id === method);
  const ranked = method === 'droop_stv' || method === 'irv';

  const submit = () => {
    setLocalError('');
    try {
      const nSeats = toInt(seats);
      if (method === 'fptp') return run('allocate', { method, seats: parsePairs(districts).length, districts: parsePairs(districts) }, method);
      if (ranked) {
        const { ballots: b, candidates } = parseBallots(ballots);
        if (method === 'irv') return run('irv', { candidates, ballots: b }, method);
        if (nSeats === null) throw new Error('Seats must be a whole number.');
        return run('stv', { candidates, ballots: b, seats: nSeats }, method);
      }
      if (nSeats === null) throw new Error('Seats must be a whole number.');
      const votes = {};
      for (const r of rows) {
        const name = r.party.trim();
        const v = toInt(r.votes);
        if (!name) continue;
        if (v === null || v < 0) throw new Error(`Votes for "${name}" must be a whole number, 0 or more.`);
        votes[name] = v;
      }
      if (!Object.keys(votes).length) throw new Error('Add at least one party.');
      return run('allocate', { method, seats: nSeats, votes }, method);
    } catch (e) {
      setLocalError(e.message);
      return null;
    }
  };
  useEffect(() => { submit(); /* the prefilled example, once */ }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const setRow = (i, patch) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  return (
    <DeskCard title="Seats from votes" what="Turns votes into seats under five real electoral rules, so you can see how the rule, not only the vote, shapes the result.">
      <div className="kt-tabs" role="radiogroup" aria-label="Electoral method">
        {METHODS.map((m) => (
          <button key={m.id} type="button" role="radio" aria-checked={method === m.id} className="kt-seg" onClick={() => setMethod(m.id)}>{m.label}</button>
        ))}
      </div>
      <p className="hint">{meta.what}</p>
      {!ranked && method !== 'fptp' && (
        <fieldset className="kit-fields stack-sm">
          <legend className="label">Votes per party</legend>
          {rows.map((r, i) => (
            <div key={i} className="kt-row">
              <input className="kt-input kt-grow" aria-label={`Party ${i + 1} name`} value={r.party} onChange={(e) => setRow(i, { party: e.target.value })} />
              <input className="kt-input kt-num" aria-label={`Votes for ${r.party || `party ${i + 1}`}`} inputMode="numeric" value={r.votes} onChange={(e) => setRow(i, { votes: e.target.value })} />
              <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label={`Remove ${r.party || `party ${i + 1}`}`} onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))}><Trash2 size={14} aria-hidden="true" /></button>
            </div>
          ))}
          <div><button type="button" className="btn btn-quiet btn-sm" onClick={() => setRows((rs) => [...rs, { party: '', votes: '0' }])}><Plus size={14} aria-hidden="true" /> Add party</button></div>
        </fieldset>
      )}
      {method === 'fptp' && (
        <div className="field">
          <label htmlFor={`${id}-d`}>Districts (one per line: party and its votes, separated by commas)</label>
          <textarea id={`${id}-d`} className="kt-input kt-mono" rows={6} value={districts} onChange={(e) => setDistricts(e.target.value)} />
          <span className="hint">The number of seats equals the number of districts.</span>
        </div>
      )}
      {ranked && (
        <div className="field">
          <label htmlFor={`${id}-b`}>Ballots (one group per line: how many voters, then their ranking, best first)</label>
          <textarea id={`${id}-b`} className="kt-input kt-mono" rows={6} value={ballots} onChange={(e) => setBallots(e.target.value)} />
        </div>
      )}
      {method !== 'fptp' && method !== 'irv' && (
        <div className="field kt-small">
          <label htmlFor={`${id}-s`}>Seats to fill</label>
          <input id={`${id}-s`} className="kt-input kt-num" inputMode="numeric" value={seats} onChange={(e) => setSeats(e.target.value)} />
        </div>
      )}
      <div className="btn-row"><RunButton loading={state.loading} onClick={submit}>Count the seats</RunButton></div>
      {localError && <div className="notice notice-bad" role="alert">{localError}</div>}
      <Outcome state={state} render={(r) => (state.tag === 'droop_stv' ? <StvResult r={r} /> : state.tag === 'irv' ? <IrvResult r={r} /> : <SeatTable r={r} />)} />
    </DeskCard>
  );
}

function PowerDesk() {
  const [rows, setRows] = useState([{ p: 'Party A', w: '45' }, { p: 'Party B', w: '30' }, { p: 'Party C', w: '15' }, { p: 'Party D', w: '10' }]);
  const [quota, setQuota] = useState('');
  const [localError, setLocalError] = useState('');
  const [state, run] = useTool('polity');
  const id = useId();
  const total = rows.reduce((a, r) => a + (toInt(r.w) || 0), 0);

  const submit = () => {
    setLocalError('');
    const weights = {};
    for (const r of rows) {
      const name = r.p.trim();
      const w = toInt(r.w);
      if (!name) continue;
      if (w === null || w < 0) { setLocalError(`Weight for "${name}" must be a whole number, 0 or more.`); return null; }
      weights[name] = w;
    }
    const args = { weights };
    if (quota.trim()) {
      const q = toInt(quota);
      if (q === null) { setLocalError('Quota must be a whole number, or empty for a simple majority.'); return null; }
      args.quota = q;
    }
    return run('power', args);
  };
  useEffect(() => { submit(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const setRow = (i, patch) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  return (
    <DeskCard title="Coalition power" what="Weighted voting: a player's real power is how often they turn a losing coalition into a winning one, which is not the same as their share of the votes.">
      <fieldset className="kit-fields stack-sm">
        <legend className="label">Players and their weights (seats or votes)</legend>
        {rows.map((r, i) => (
          <div key={i} className="kt-row">
            <input className="kt-input kt-grow" aria-label={`Player ${i + 1} name`} value={r.p} onChange={(e) => setRow(i, { p: e.target.value })} />
            <input className="kt-input kt-num" aria-label={`Weight of ${r.p || `player ${i + 1}`}`} inputMode="numeric" value={r.w} onChange={(e) => setRow(i, { w: e.target.value })} />
            <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label={`Remove ${r.p || `player ${i + 1}`}`} onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))}><Trash2 size={14} aria-hidden="true" /></button>
          </div>
        ))}
        <div><button type="button" className="btn btn-quiet btn-sm" onClick={() => setRows((rs) => [...rs, { p: `Party ${String.fromCharCode(65 + rs.length)}`, w: '1' }])}><Plus size={14} aria-hidden="true" /> Add player</button></div>
      </fieldset>
      <div className="field kt-small">
        <label htmlFor={`${id}-q`}>Quota to win (blank = simple majority of {total})</label>
        <input id={`${id}-q`} className="kt-input kt-num" inputMode="numeric" value={quota} onChange={(e) => setQuota(e.target.value)} placeholder={String(Math.floor(total / 2) + 1)} />
      </div>
      <div className="btn-row"><RunButton loading={state.loading} onClick={submit}>Measure power</RunButton></div>
      {localError && <div className="notice notice-bad" role="alert">{localError}</div>}
      <Outcome state={state} render={(r) => {
        const names = Object.keys(r.shapley_shubik || {});
        return (
          <>
            <p>Quota: <strong>{r.quota}</strong>. A coalition wins when its weights add up to the quota or more.</p>
            <div className="kt-bars" role="group" aria-label="Shapley-Shubik power">
              <strong>Shapley-Shubik index</strong>
              <span className="hint">The share of all orderings in which this player is the one who tips a group over the quota.</span>
              {names.map((n) => <Bar key={n} label={n} value={r.shapley_shubik[n].value} text={`${pct(r.shapley_shubik[n].value)} (${r.shapley_shubik[n].exact})`} />)}
            </div>
            <div className="kt-bars" role="group" aria-label="Banzhaf power">
              <strong>Banzhaf index</strong>
              <span className="hint">Swings: coalitions that win with this player but lose without them. Normalized so all players sum to 100%.</span>
              {names.map((n) => <Bar key={n} label={n} value={r.banzhaf?.[n]?.normalized} text={`${pct(r.banzhaf?.[n]?.normalized)} (${r.banzhaf?.[n]?.swings} swings)`} tone="kt-alt" />)}
            </div>
            {r.dummies?.length > 0 && <p className="notice">No power at all (a dummy): {r.dummies.join(', ')}. They can never change the outcome, whatever their weight.</p>}
            <div>
              <strong>Minimal winning coalitions</strong>
              <span className="hint"> (winning, but lose if any member leaves)</span>
              <ul className="kt-tags">
                {r.minimal_winning?.map((c, i) => <li key={i} className="kt-chip">{c.join(' + ')}</li>)}
              </ul>
              {r.truncated && <p className="hint">The list is cut short: there are more than the 200 shown.</p>}
            </div>
          </>
        );
      }} />
    </DeskCard>
  );
}

export default function PolityDesk() {
  return (
    <div className="kt-desk">
      <MethodDesk />
      <PowerDesk />
    </div>
  );
}
