import React, { useEffect, useRef, useState } from 'react';
import { Scale, Blocks, Users, Search, CheckCircle2, AlertTriangle, XCircle, Trash2 } from 'lucide-react';
import { api } from '../lib/api';
import WorkspaceShell from './WorkspaceShell';

// PHILIN (philin.py): text -> editable claim blocks -> the Python logic engine -> two-pass web fact-checks -> all
// positions compared by a fixed rule. Everything the model writes is shown as plain text.
const TABS = [
  { id: 'analyze', label: 'Analyze', icon: Blocks },
  { id: 'sides', label: 'All sides', icon: Users },
];
const MAX_TEXT = 8000;
const ROLES = ['conclusion', 'premise', 'objection', 'rebuttal'];
const KINDS = {
  empirical: { label: 'Checkable fact', hint: 'Evidence can settle it: it gets fact-checked.' },
  logical: { label: 'Logic or definition', hint: 'Settled by logic or meaning, not by search.' },
  normative: { label: 'Value claim', hint: 'Says what ought to be or what is good: not decidable by evidence.' },
  unfalsifiable: { label: 'Not testable', hint: 'No possible evidence could settle it.' },
  mixed: { label: 'Fact + value', hint: 'Split it into a fact and a value claim to check the fact.' },
};
const VERDICT_ICON = { supported: CheckCircle2, contradicted: XCircle, mixed: AlertTriangle, insufficient: AlertTriangle };
const STATUS = {
  valid: 'Valid: the conclusions follow from the premises (as translated into logic).',
  invalid: 'Invalid: at least one conclusion does not follow, or the support is circular.',
  unchecked: 'Not fully checked: some claims have no logical form, so their inferences were not tested.',
};

let handledRequest = null;

const host = (uri) => { try { return new URL(uri).hostname; } catch { return uri; } };

function Banner() {
  return (
    <p className="notice notice-info philin-banner">
      PHILIN uses AI to split text into claim blocks, identify premises and conclusions (output), and fact-check empirical claims with search.
      Python deterministically checks logic validity, named forms, and fallacies without AI. Value claims are never ranked.
    </p>
  );
}

function Verdict({ v }) {
  if (!v) return null;
  if (v.pending) return <span className="hint" role="status">Checking…</span>;
  const Icon = VERDICT_ICON[v.verdict] || AlertTriangle;
  return (
    <div className={`philin-verdict verdict-${v.verdict}`}>
      <strong><Icon size={14} aria-hidden="true" /> {v.verdict}</strong>
      <span className="hint"> · confidence {Math.round((v.confidence || 0) * 100)}%
        {v.passes === 1 && ' · one search pass only'}{v.disagreement && ' · the two checks disagreed'}{v.cached && ' · saved result'}</span>
      {v.evidence_for && <p><span className="label">For:</span> {v.evidence_for}</p>}
      {v.evidence_against && <p><span className="label">Against:</span> {v.evidence_against}</p>}
      {v.note && <p className="hint">{v.note}</p>}
      {v.sources?.length > 0 && (
        <ul className="philin-sources">
          {v.sources.map((s) => (
            <li key={s.uri}><a href={s.uri} target="_blank" rel="noopener noreferrer">{s.title}</a> <span className="hint">({host(s.uri)})</span></li>
          ))}
        </ul>
      )}
    </div>
  );
}

function BlockEditor({ arg, onChange, verdicts, readOnly }) {
  const legend = arg.legend || {};
  const setBlock = (id, patch) => onChange({ ...arg, blocks: arg.blocks.map((b) => (b.id === id ? { ...b, ...patch } : b)) });
  const dropBlock = (id) => onChange({
    ...arg, blocks: arg.blocks.filter((b) => b.id !== id),
    edges: arg.edges.map((e) => ({ ...e, from: e.from.filter((f) => f !== id) })).filter((e) => e.to !== id && e.from.length),
  });
  return (
    <div className="stack-sm">
      {Object.keys(legend).length > 0 && (
        <div className="philin-legend">
          <span className="label">Letters</span>
          <ul>{Object.entries(legend).map(([k, v]) => <li key={k}><code>{k}</code> = {v}</li>)}</ul>
        </div>
      )}
      <ol className="philin-blocks">
        {arg.blocks.map((b) => (
          <li key={b.id} className={`philin-block kind-${b.kind}`}>
            <div className="philin-block-head">
              <code>{b.id}</code>
              {readOnly ? <span className="chip">{b.role || 'claim'}</span> : (
                <select className="select" aria-label={`Role of ${b.id}`} value={b.role || ''} onChange={(e) => setBlock(b.id, { role: e.target.value || null })}>
                  <option value="">claim</option>
                  {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              )}
              {readOnly ? <span className="chip" title={KINDS[b.kind]?.hint}>{KINDS[b.kind]?.label}</span> : (
                <select className="select" aria-label={`Kind of ${b.id}`} value={b.kind} title={KINDS[b.kind]?.hint}
                  onChange={(e) => setBlock(b.id, { kind: e.target.value })}>
                  {Object.entries(KINDS).map(([k, { label }]) => <option key={k} value={k}>{label}</option>)}
                </select>
              )}
              {!readOnly && (
                <button type="button" className="btn btn-quiet btn-sm btn-icon" aria-label={`Remove ${b.id}`} onClick={() => dropBlock(b.id)}>
                  <Trash2 size={14} aria-hidden="true" />
                </button>
              )}
            </div>
            {readOnly ? <p>{b.text}</p> : (
              <textarea className="textarea philin-text" aria-label={`Claim ${b.id}`} value={b.text} maxLength={500} rows={2}
                onChange={(e) => setBlock(b.id, { text: e.target.value })} />
            )}
            <div className="philin-meta">
              {readOnly ? (b.formal && <span className="hint">Logic: <code>{b.formal}</code></span>) : (
                <label className="hint">Logic <input className="input philin-formal" value={b.formal || ''} placeholder="e.g. P -> Q"
                  onChange={(e) => setBlock(b.id, { formal: e.target.value })} spellCheck={false} /></label>
              )}
              {b.drafted ? <span className="hint">Drafted (not quoted from a text)</span>
                : b.quote_ok ? <span className="hint ok">Quote found in the text</span>
                  : <span className="hint err">Quote not found in the text: check this block</span>}
            </div>
            {['normative', 'unfalsifiable', 'mixed'].includes(b.kind) && <p className="hint">Not decidable by evidence.</p>}
            <Verdict v={verdicts?.[b.id]} />
          </li>
        ))}
      </ol>
      {arg.edges.length > 0 && (
        <div>
          <span className="label">Links</span>
          <ul className="philin-edges">
            {arg.edges.map((e) => (
              <li key={`${e.from.join('+')}-${e.type}-${e.to}`}>{e.from.join(' + ')} {e.type === 'supports' ? 'support' : 'attack'}{e.from.length === 1 ? 's' : ''} {e.to}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function LogicReport({ check }) {
  if (!check) return null;
  return (
    <div className="stack-sm philin-logic" aria-live="polite">
      <p className={`notice ${check.status === 'valid' ? 'notice-ok' : check.status === 'invalid' ? 'notice-bad' : 'notice-info'}`}>
        <strong>Logic: </strong>{STATUS[check.status]}
      </p>
      {check.inferences.map((i) => (
        <p key={`${i.premises.join('+')}->${i.conclusion}`}>
          {i.premises.join(' + ')} → {i.conclusion}:{' '}
          {!i.checked ? <span className="hint">not checked (missing logical form)</span>
            : i.valid ? <span className="ok">valid</span> : <span className="err">does not follow</span>}
          {i.forms?.map((f) => <span key={f.id} className={`chip philin-form ${f.kind}`}>{f.name}</span>)}
          {i.checked && !i.valid && i.counterexample && (
            <span className="hint"> Counterexample: {Object.entries(i.counterexample).map(([k, v]) => `${k} ${v ? 'true' : 'false'}`).join(', ')}.</span>
          )}
        </p>
      ))}
      {check.findings.filter((f) => f.code !== 'invalid_inference').map((f) => <p key={`${f.code}-${f.ids.join()}`} className="hint">{f.message}</p>)}
    </div>
  );
}

/** Fact-checks the empirical blocks one request at a time (progress per claim, Stop between claims). */
function useFactChecks() {
  const [verdicts, setVerdicts] = useState({});
  const [running, setRunning] = useState(false);
  const stop = useRef(false);
  const run = async (blocks, keyOf = (b) => b.id) => {
    stop.current = false;
    setRunning(true);
    try {
      for (const b of blocks.filter((x) => x.kind === 'empirical')) {
        if (stop.current) break;
        const key = keyOf(b);
        setVerdicts((v) => ({ ...v, [key]: { pending: true } }));
        try {
          const res = await api('/api/philin/factcheck', { method: 'POST', body: { claims: [{ id: b.id, text: b.text, kind: b.kind }] } });
          setVerdicts((v) => ({ ...v, [key]: res.results[b.id] }));
        } catch (err) {
          setVerdicts((v) => ({ ...v, [key]: undefined }));
          throw err;
        }
      }
    } finally {
      setRunning(false);
    }
  };
  return { verdicts, setVerdicts, running, run, stop: () => { stop.current = true; } };
}

function Analyze({ onQuestion }) {
  const [text, setText] = useState('');
  const [arg, setArg] = useState(null);
  const [check, setCheck] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const [dirty, setDirty] = useState(false);
  const facts = useFactChecks();

  const transcribe = async () => {
    setBusy('blocks'); setError(null);
    try {
      const res = await api('/api/philin/transcribe', { method: 'POST', body: { text } });
      setArg(res.argument); setCheck(res.check); setWarnings(res.warnings); setDirty(false); facts.setVerdicts({});
      if (res.argument.question) onQuestion(res.argument.question);
    } catch (err) { setError(err.message); }
    setBusy(null);
  };
  const recheck = async () => {
    setBusy('check'); setError(null);
    try {
      const res = await api('/api/philin/check', { method: 'POST', body: { argument: arg, source: text } });
      setArg(res.argument); setCheck(res.check); setWarnings(res.warnings); if (dirty) facts.setVerdicts({}); setDirty(false);
    } catch (err) { setError(err.message); }
    setBusy(null);
  };
  const factCheck = async () => {
    setError(null);
    try { await facts.run(arg.blocks); } catch (err) { setError(err.message); }
  };
  const empirical = arg ? arg.blocks.filter((b) => b.kind === 'empirical').length : 0;

  return (
    <div className="stack">
      <Banner />
      <div className="field">
        <label htmlFor="philin-text">Argument, essay or debate</label>
        <textarea id="philin-text" className="textarea" rows={8} maxLength={MAX_TEXT} value={text} onChange={(e) => setText(e.target.value)}
          placeholder="Paste the text whose reasoning you want to test." />
        <span className="hint">{text.length}/{MAX_TEXT} characters. The text goes to Google Gemini to be split into claims (1 model call).</span>
      </div>
      <div className="btn-row">
        <button type="button" className="btn btn-primary" disabled={!text.trim() || Boolean(busy) || facts.running} onClick={transcribe}>
          {busy === 'blocks' ? 'Splitting into claims…' : 'Split into claims'}
        </button>
      </div>
      {error && <p className="notice notice-bad" role="alert">{error}</p>}
      {arg && (
        <section className="panel stack" aria-labelledby="philin-blocks-h">
          <h2 id="philin-blocks-h">Claims</h2>
          <p className="hint">Check each block against your text, fix its kind or logic, then check again. Letters in a logical form must be in the
            letter list.</p>
          {warnings.length > 0 && <ul className="hint philin-warnings">{warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
          <BlockEditor arg={arg} onChange={(a) => { setArg(a); setDirty(true); }} verdicts={facts.verdicts} />
          <div className="btn-row">
            <button type="button" className="btn btn-secondary" disabled={Boolean(busy) || facts.running} onClick={recheck}>
              {busy === 'check' ? 'Checking…' : dirty ? 'Check the edited claims' : 'Check the logic again'}
            </button>
            {facts.running ? (
              <button type="button" className="btn btn-quiet" onClick={facts.stop}>Stop after this claim</button>
            ) : (
              <button type="button" className="btn btn-primary" disabled={!empirical || dirty || Boolean(busy)} onClick={factCheck}
                title={dirty ? 'Check the edited claims first' : undefined}>
                <Search size={14} aria-hidden="true" /> Fact-check {empirical} claim{empirical === 1 ? '' : 's'} (up to {empirical * 2} searches)
              </button>
            )}
          </div>
          <LogicReport check={check} />
        </section>
      )}
    </div>
  );
}

function Sides({ question, setQuestion }) {
  const [positions, setPositions] = useState(null);
  const [note, setNote] = useState(null);
  const [ranking, setRanking] = useState(null);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  const facts = useFactChecks();

  const draft = async () => {
    setBusy('draft'); setError(null); setRanking(null); facts.setVerdicts({});
    try {
      const res = await api('/api/philin/positions', { method: 'POST', body: { question } });
      setPositions(res.positions); setNote(res.note);
    } catch (err) { setError(err.message); }
    setBusy(null);
  };
  const checkAll = async () => {
    if (!positions) return;
    setError(null);
    try {
      const allClaims = positions.flatMap((p) =>
        p.argument.blocks
          .filter((b) => b.kind === 'empirical')
          .map((b) => ({ ...b, __posKey: `${p.label}:${b.id}` }))
      );
      await facts.run(allClaims, (b) => b.__posKey);
    } catch (err) { setError(err.message); }
  };
  const compare = async () => {
    setBusy('rank'); setError(null);
    try {
      setRanking(await api('/api/philin/rank', {
        method: 'POST', body: { positions: positions.map((p) => ({ label: p.label, summary: p.summary, argument: p.argument })) },
      }));
    } catch (err) { setError(err.message); }
    setBusy(null);
  };
  const empirical = positions ? positions.reduce((n, p) => n + p.argument.blocks.filter((b) => b.kind === 'empirical').length, 0) : 0;
  const prefixed = (label) => Object.fromEntries(Object.entries(facts.verdicts)
    .filter(([k]) => k.startsWith(`${label}:`)).map(([k, v]) => [k.slice(label.length + 1), v]));

  return (
    <div className="stack">
      <Banner />
      <div className="field">
        <label htmlFor="philin-q">Question</label>
        <input id="philin-q" className="input" maxLength={500} value={question} onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. Does a four-day work week raise productivity?" />
        <span className="hint">The strongest form of each position is drafted with the same template for every side (1 model call).</span>
      </div>
      <div className="btn-row">
        <button type="button" className="btn btn-primary" disabled={!question.trim() || Boolean(busy) || facts.running} onClick={draft}>
          {busy === 'draft' ? 'Drafting positions…' : 'Draft the positions'}
        </button>
      </div>
      {error && <p className="notice notice-bad" role="alert">{error}</p>}
      {positions && (
        <>
          {note && <p className="hint">{note}</p>}
          <div className="btn-row">
            {facts.running ? <button type="button" className="btn btn-quiet" onClick={facts.stop}>Stop after this claim</button> : (
              <button type="button" className="btn btn-secondary" disabled={!empirical || Boolean(busy)} onClick={checkAll}>
                <Search size={14} aria-hidden="true" /> Fact-check every side ({empirical} claims, up to {empirical * 2} searches)
              </button>
            )}
            <button type="button" className="btn btn-primary" disabled={Boolean(busy) || facts.running} onClick={compare}>
              <Scale size={14} aria-hidden="true" /> {busy === 'rank' ? 'Comparing…' : 'Compare the positions'}
            </button>
          </div>
          {ranking && <Ranking ranking={ranking} />}
          {positions.map((p) => (
            <section key={p.label} className="panel stack-sm" aria-labelledby={`pos-${p.label}`}>
              <h2 id={`pos-${p.label}`}>Position {p.label}</h2>
              <p>{p.summary}</p>
              <BlockEditor arg={p.argument} onChange={() => {}} verdicts={prefixed(p.label)} readOnly />
              <LogicReport check={p.check} />
            </section>
          ))}
        </>
      )}
    </div>
  );
}

function Ranking({ ranking }) {
  return (
    <section className="panel stack-sm" aria-labelledby="philin-rank-h" aria-live="polite">
      <h2 id="philin-rank-h">Comparison</h2>
      {ranking.most_supported ? (
        <p className="notice notice-ok">Position {ranking.most_supported} is best supported by logic and the checked facts
          {ranking.decided_by ? ` (decided by: ${ranking.decided_by})` : ''}.</p>
      ) : ranking.no_dominant_position && <p className="notice notice-info">No position dominates. {ranking.no_dominant_position}</p>}
      {ranking.facts_note && <p className="hint">{ranking.facts_note}</p>}
      <div className="philin-table-wrap">
        <table className="philin-table">
          <thead>
            <tr><th scope="col">Position</th><th scope="col">Logic</th><th scope="col">Contradicted</th><th scope="col">Supported</th>
              <th scope="col">Mixed</th><th scope="col">Insufficient</th><th scope="col">Not checked</th><th scope="col">Value premises (not ranked)</th></tr>
          </thead>
          <tbody>
            {ranking.order.map((r) => (
              <tr key={r.label}>
                <th scope="row">{r.label}</th><td>{r.logic}</td><td>{r.contradicted}</td><td>{r.supported}</td><td>{r.mixed}</td>
                <td>{r.insufficient}</td><td>{r.unchecked}</td>
                <td>{r.value_premises.length ? r.value_premises.map((v) => v.text).join('; ') : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {ranking.value_note && <p className="hint">{ranking.value_note}</p>}
      <p className="hint"><span className="label">Rule: </span>{ranking.rule}</p>
    </section>
  );
}

export default function PhilosophyLab({ requestedTab }) {
  const [tab, setTab] = useState('analyze');
  const [question, setQuestion] = useState('');
  useEffect(() => {
    if (!requestedTab?.tab || (requestedTab.mode && requestedTab.mode !== 'philosophy') || requestedTab.at === handledRequest) return;
    handledRequest = requestedTab.at;
    if (TABS.some((t) => t.id === requestedTab.tab)) {
      setTab(requestedTab.tab);
    }
  }, [requestedTab?.at]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <WorkspaceShell kind="Philosophy" title="Philosophy" tabs={TABS} current={tab} onTab={setTab}
      intro="PHILIN uses AI to split text into claim blocks, identify premises and conclusions (output), and fact-check empirical claims with search. Python deterministically checks logic validity, named forms, and fallacies without AI. Value claims are never ranked.">
      {/* both stay mounted so switching tabs keeps the work */}
      <div hidden={tab !== 'analyze'}><Analyze onQuestion={(q) => setQuestion((cur) => cur || q)} /></div>
      <div hidden={tab !== 'sides'}><Sides question={question} setQuestion={setQuestion} /></div>
    </WorkspaceShell>
  );
}
