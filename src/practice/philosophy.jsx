// Philosophy practice types: truth_table, validity, syllogism, proof_steps, argument_map, spot_parts, fallacy_id.
// Each renderer conforms to { item, onResult(ok, given), retry }.
import React, { useEffect, useMemo, useState } from 'react';
import { Check, RotateCcw, AlertCircle, ShieldCheck } from 'lucide-react';
import Md, { MdInline } from '../components/Md';
import { ExplainAnswerButton } from '../components/ExplainDialog';

export const PHILOSOPHY_TYPES = [
  'truth_table',
  'validity',
  'syllogism',
  'proof_steps',
  'argument_map',
  'spot_parts',
  'fallacy_id',
];

export const PHILOSOPHY_LABEL = {
  truth_table: 'Truth Table',
  validity: 'Argument Validity',
  syllogism: 'Categorical Syllogism',
  proof_steps: 'Fitch Proof',
  argument_map: 'Argument Map',
  spot_parts: 'Argument Structure',
  fallacy_id: 'Fallacy Identification',
};

function useCheck(onResult) {
  const [res, setRes] = useState(null);
  const done = (r, given) => {
    setRes(r);
    onResult?.(r.ok, given);
  };
  return [res, done, () => setRes(null)];
}

function Result({ ok, note, answer, item, onRetry, given, detail }) {
  return (
    <div className={`feedback ${ok ? 'ok' : 'bad'}`} aria-live="polite">
      <p style={{ fontWeight: 700, marginBottom: 4 }}>
        {ok ? 'Correct.' : 'Not quite.'}
        {note ? ` ${note}` : ''}
      </p>
      {!ok && answer && (
        <p>
          Correct answer: <strong><MdInline>{String(answer)}</MdInline></strong>
        </p>
      )}
      {detail && <Md>{detail}</Md>}
      {item.explanation && item.explanation !== detail && <Md>{item.explanation}</Md>}
      {!ok && (
        <div className="btn-row" style={{ marginTop: 6 }}>
          <ExplainAnswerButton
            item={item}
            studentAnswer={given}
            correctAnswer={answer || item.answer}
            question={item.prompt}
          />
          {onRetry && (
            <button type="button" className="btn btn-quiet btn-sm" onClick={onRetry}>
              <RotateCcw size={14} aria-hidden="true" /> Try again
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// 1. TruthTablePractice
export function TruthTablePractice({ item, onResult, retry = true }) {
  const [res, done, reset] = useCheck(onResult);
  const rows = item.rows || [];
  const formulas = item.formulas || [];
  const letters = item.letters || item.vars || [];

  // State: grid of user values for each row and formula: answers[rowIndex][formulaIndex]
  const [answers, setAnswers] = useState(() =>
    rows.map(() => formulas.map(() => null))
  );

  useEffect(() => {
    setAnswers(rows.map(() => formulas.map(() => null)));
    reset();
  }, [item]);

  const toggleVal = (rIdx, fIdx) => {
    if (res) return;
    setAnswers((prev) => {
      const next = prev.map((row) => [...row]);
      if (!next[rIdx]) next[rIdx] = formulas.map(() => null);
      const cur = next[rIdx][fIdx];
      next[rIdx][fIdx] = cur === true ? false : cur === false ? null : true;
      return next;
    });
  };

  const check = () => {
    let allOk = true;
    for (let r = 0; r < rows.length; r++) {
      const expectedVals = Array.isArray(rows[r].values) ? rows[r].values : rows[r].results || [];
      for (let f = 0; f < formulas.length; f++) {
        if (answers[r]?.[f] !== expectedVals[f]) {
          allOk = false;
          break;
        }
      }
      if (!allOk) break;
    }
    const givenSummary = answers
      .map((row) => row.map((v) => (v === true ? 'T' : v === false ? 'F' : '?')).join(' '))
      .join(' | ');
    done({ ok: allOk }, givenSummary);
  };

  return (
    <div className="stack-sm">
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'center', fontSize: '0.9rem' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid var(--border)' }}>
              {letters.map((l) => (
                <th key={l} style={{ padding: '6px 10px', background: 'var(--panel-subtle)' }}>
                  {l}
                </th>
              ))}
              {formulas.map((f) => (
                <th key={f} style={{ padding: '6px 12px', background: 'var(--panel-subtle)', fontWeight: 600 }}>
                  <MdInline>{f}</MdInline>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rIdx) => {
              const expectedVals = Array.isArray(row.values) ? row.values : row.results || [];
              const assign = row.assignment || (typeof row.values === 'object' && !Array.isArray(row.values) ? row.values : {});
              return (
                <tr key={rIdx} style={{ borderBottom: '1px solid var(--border)' }}>
                  {letters.map((l) => (
                    <td key={l} style={{ padding: '6px 10px', color: 'var(--muted)' }}>
                      {assign[l] ? 'T' : 'F'}
                    </td>
                  ))}
                  {formulas.map((f, fIdx) => {
                    const studentVal = answers[rIdx]?.[fIdx];
                    const expectedVal = expectedVals[fIdx];
                    const isCorrect = res ? studentVal === expectedVal : null;
                    return (
                      <td key={f} style={{ padding: '4px' }}>
                        <button
                          type="button"
                          className="btn btn-sm"
                          disabled={!!res}
                          onClick={() => toggleVal(rIdx, fIdx)}
                          style={{
                            minWidth: 38,
                            fontWeight: 700,
                            color:
                              studentVal === true
                                ? 'var(--ok)'
                                : studentVal === false
                                ? 'var(--bad)'
                                : 'var(--muted)',
                            background:
                              isCorrect === true
                                ? 'rgba(var(--ok-rgb, 34, 197, 94), 0.15)'
                                : isCorrect === false
                                ? 'rgba(var(--bad-rgb, 239, 68, 68), 0.15)'
                                : 'var(--panel)',
                            borderColor:
                              isCorrect === true
                                ? 'var(--ok)'
                                : isCorrect === false
                                ? 'var(--bad)'
                                : 'var(--border)',
                          }}
                        >
                          {studentVal === true ? 'T' : studentVal === false ? 'F' : '—'}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {!res && (
        <div className="btn-row" style={{ marginTop: 8 }}>
          <button type="button" className="btn btn-primary btn-sm" onClick={check}>
            <Check size={14} aria-hidden="true" /> Check truth table
          </button>
        </div>
      )}
      {res && (
        <Result
          ok={res.ok}
          item={item}
          given="Completed table"
          answer={res.ok ? undefined : 'See standard truth conditions for logical connectives.'}
          onRetry={
            retry
              ? () => {
                  reset();
                  setAnswers(rows.map(() => formulas.map(() => null)));
                }
              : null
          }
        />
      )}
    </div>
  );
}

// 2. ValidityPractice
export function ValidityPractice({ item, onResult, retry = true }) {
  const [res, done, reset] = useCheck(onResult);
  const [selected, setSelected] = useState(null);

  const check = (val) => {
    setSelected(val);
    const ok = val === item.valid;
    const given = val ? 'Valid' : 'Invalid';
    done({ ok }, given);
  };

  const ce = item.counterexample;
  const ceStr =
    ce && typeof ce === 'object'
      ? Object.entries(ce)
          .map(([k, v]) => `${k} = ${v ? 'T' : 'F'}`)
          .join(', ')
      : null;

  return (
    <div className="stack-sm">
      <div className="panel" style={{ padding: '12px 16px', background: 'var(--panel-subtle)', borderRadius: 8 }}>
        <p style={{ fontWeight: 600, marginBottom: 6 }}>Argument:</p>
        <ol style={{ paddingLeft: 20, margin: 0 }}>
          {item.premises?.map((p, idx) => (
            <li key={idx}>
              <MdInline>{p}</MdInline>
            </li>
          ))}
        </ol>
        <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid var(--border)', fontWeight: 600 }}>
          Conclusion: <MdInline>{item.conclusion}</MdInline>
        </div>
      </div>

      <div className="choices">
        <button
          type="button"
          className="choice"
          disabled={selected !== null}
          aria-pressed={selected === true}
          data-result={selected !== null ? (item.valid ? 'correct' : selected === true ? 'wrong' : undefined) : undefined}
          onClick={() => check(true)}
        >
          <span className="key">V</span>
          <span>Valid (No row with all true premises and false conclusion)</span>
        </button>
        <button
          type="button"
          className="choice"
          disabled={selected !== null}
          aria-pressed={selected === false}
          data-result={selected !== null ? (!item.valid ? 'correct' : selected === false ? 'wrong' : undefined) : undefined}
          onClick={() => check(false)}
        >
          <span className="key">I</span>
          <span>Invalid (There is a counterexample truth assignment)</span>
        </button>
      </div>

      {res && (
        <Result
          ok={res.ok}
          item={item}
          given={selected ? 'Valid' : 'Invalid'}
          answer={item.valid ? 'Valid' : `Invalid${ceStr ? ` (Counterexample: ${ceStr})` : ''}`}
          detail={!item.valid && ceStr ? `Counterexample: ${ceStr}` : undefined}
          onRetry={retry ? () => { reset(); setSelected(null); } : null}
        />
      )}
    </div>
  );
}

// 3. SyllogismPractice
export function SyllogismPractice({ item, onResult, retry = true }) {
  const [res, done, reset] = useCheck(onResult);
  const [choice, setChoice] = useState(null);

  const opts = useMemo(() => {
    if (item.valid) {
      return [
        { label: `Valid — ${item.name || item.form}`, isCorrect: true },
        { label: 'Invalid — Undistributed Middle', isCorrect: false },
        { label: 'Invalid — Illicit Major or Minor', isCorrect: false },
        { label: 'Invalid — Exclusive Premises', isCorrect: false },
      ];
    }
    const broken = item.violations?.[0]?.message || 'Formal fallacy';
    const brokenRule = item.violations?.[0]?.rule || '';
    const distractors = [
      { rule: 'undistributed_middle', label: 'Invalid — Undistributed Middle' },
      { rule: 'illicit_major', label: 'Invalid — Illicit Major' },
      { rule: 'illicit_minor', label: 'Invalid — Illicit Minor' },
      { rule: 'exclusive_premises', label: 'Invalid — Exclusive Premises' },
      { rule: 'affirmative_from_negative', label: 'Invalid — Affirmative conclusion from negative premise' },
      { rule: 'existential_fallacy', label: 'Invalid — Existential Fallacy' },
    ];
    const filteredDistractors = distractors
      .filter((d) => d.rule !== brokenRule)
      .slice(0, 2)
      .map((d) => ({ label: d.label, isCorrect: false }));
    return [
      { label: `Invalid — ${broken}`, isCorrect: true },
      { label: 'Valid — Follows from modern categorical rules', isCorrect: false },
      ...filteredDistractors,
    ];
  }, [item]);

  const onPick = (opt) => {
    setChoice(opt);
    done({ ok: opt.isCorrect }, opt.label);
  };

  return (
    <div className="stack-sm">
      <div className="panel" style={{ padding: '12px 16px', background: 'var(--panel-subtle)', borderRadius: 8 }}>
        <p style={{ fontWeight: 600, marginBottom: 4 }}>Standard Form Syllogism:</p>
        {item.major ? (
          <div style={{ fontSize: '0.95rem' }}>
            <p style={{ margin: '2px 0' }}>Major premise: [{item.major.type}] {item.major.subject} — {item.major.predicate}</p>
            <p style={{ margin: '2px 0' }}>Minor premise: [{item.minor.type}] {item.minor.subject} — {item.minor.predicate}</p>
            <p style={{ margin: '4px 0 0 0', fontWeight: 600 }}>Conclusion: [{item.conclusion.type}] {item.conclusion.subject} — {item.conclusion.predicate}</p>
          </div>
        ) : (
          <p style={{ margin: 0, fontWeight: 700 }}>Form: {item.form} ({item.reading} reading)</p>
        )}
      </div>

      <div className="choices">
        {opts.map((opt, i) => (
          <button
            key={opt.label}
            type="button"
            className="choice"
            disabled={choice !== null}
            data-result={choice !== null ? (opt.isCorrect ? 'correct' : choice.label === opt.label ? 'wrong' : undefined) : undefined}
            onClick={() => onPick(opt)}
          >
            <span className="key">{'ABCD'[i]}</span>
            <span>{opt.label}</span>
          </button>
        ))}
      </div>

      {res && (
        <Result
          ok={res.ok}
          item={item}
          given={choice?.label}
          answer={item.valid ? `Valid (${item.name || item.form})` : `Invalid: ${item.violations?.map((v) => v.message).join('; ') || item.form}`}
          onRetry={retry ? () => { reset(); setChoice(null); } : null}
        />
      )}
    </div>
  );
}

// 4. ProofStepsPractice
export function ProofStepsPractice({ item, onResult, retry = true }) {
  const [res, done, reset] = useCheck(onResult);
  const [selected, setSelected] = useState(null);
  const lines = item.lines || [];
  const verdicts = item.verdicts || [];
  const isProven = Boolean(item.proven);

  const choose = (val) => {
    setSelected(val);
    const ok = val === isProven;
    done({ ok }, val ? 'Valid Proof' : 'Invalid / Incomplete Proof');
  };

  return (
    <div className="stack-sm">
      <div className="panel" style={{ padding: '12px 16px', background: 'var(--panel-subtle)', borderRadius: 8 }}>
        {item.premises?.length > 0 && (
          <p style={{ margin: '0 0 4px 0' }}>
            <strong>Premises:</strong> {item.premises.join(', ')}
          </p>
        )}
        {item.goal && (
          <p style={{ margin: 0 }}>
            <strong>Goal:</strong> <MdInline>{item.goal}</MdInline>
          </p>
        )}
      </div>

      <div style={{ fontFamily: 'monospace', fontSize: '0.9rem', overflowX: 'auto', background: 'var(--panel)', padding: 10, borderRadius: 6, border: '1px solid var(--border)' }}>
        {lines.map((ln, idx) => {
          const depth = ln.depth || 0;
          const v = verdicts[idx] || {};
          const isError = v.verdict && v.verdict !== 'ok';
          return (
            <div
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'center',
                padding: '2px 0',
                paddingLeft: depth * 16,
                borderLeft: depth > 0 ? '2px solid var(--accent)' : 'none',
                marginLeft: depth > 0 ? 4 : 0,
                color: isError ? 'var(--bad)' : 'inherit',
              }}
            >
              <span style={{ width: 30, color: 'var(--muted)', userSelect: 'none' }}>{idx + 1}.</span>
              <span style={{ flex: 1, fontWeight: 600 }}>{ln.formula}</span>
              <span style={{ color: 'var(--muted)', marginLeft: 12 }}>{ln.rule}</span>
              {ln.cites && ln.cites.length > 0 && (
                <span style={{ color: 'var(--muted)', marginLeft: 8 }}>[{Array.isArray(ln.cites) ? ln.cites.join(', ') : ln.cites}]</span>
              )}
              {res && isError && (
                <span style={{ color: 'var(--bad)', fontSize: '0.8rem', marginLeft: 8 }}>({v.verdict})</span>
              )}
            </div>
          );
        })}
      </div>

      <div className="choices">
        <button
          type="button"
          className="choice"
          disabled={selected !== null}
          aria-pressed={selected === true}
          data-result={selected !== null ? (isProven ? 'correct' : selected === true ? 'wrong' : undefined) : undefined}
          onClick={() => choose(true)}
        >
          <span className="key">V</span>
          <span>Valid & Complete Proof (all lines justified, goal reached)</span>
        </button>
        <button
          type="button"
          className="choice"
          disabled={selected !== null}
          aria-pressed={selected === false}
          data-result={selected !== null ? (!isProven ? 'correct' : selected === false ? 'wrong' : undefined) : undefined}
          onClick={() => choose(false)}
        >
          <span className="key">I</span>
          <span>Invalid or Incomplete Proof (contains justification errors or open subproofs)</span>
        </button>
      </div>

      {res && (
        <Result
          ok={res.ok}
          item={item}
          given={selected ? 'Valid Proof' : 'Invalid / Incomplete Proof'}
          answer={isProven ? 'Valid & Complete Proof' : 'Invalid or Incomplete Proof'}
          detail={!isProven ? 'One or more lines break Calgary Fitch derivation rules or goal remains unreached.' : undefined}
          onRetry={retry ? () => { reset(); setSelected(null); } : null}
        />
      )}
    </div>
  );
}

// 5. ArgumentMapPractice
export function ArgumentMapPractice({ item, onResult, retry = true }) {
  const [res, done, reset] = useCheck(onResult);
  const findings = item.findings || [];
  const mapData = item.map || {};
  const [pick, setPick] = useState(null);

  const hasFlaw = findings.length > 0;
  const flawType = findings[0]?.code;

  const matchesFlaw = (optId) => {
    if (!hasFlaw) return optId === 'valid';
    if (optId === flawType) return true;
    if (optId === 'unsupported_claim' && (flawType === 'disconnected_claim' || flawType === 'unsupported_claim')) {
      return true;
    }
    return false;
  };

  const options = useMemo(() => {
    return [
      { id: 'valid', label: 'Sound and logically connected structure' },
      { id: 'circular_support', label: 'Circular reasoning (claims support each other in a loop)' },
      { id: 'invalid_inference', label: 'Invalid inference (premises fail to formally entail conclusion)' },
      { id: 'unsupported_claim', label: 'Unsupported conclusion or disconnected claim' },
    ];
  }, []);

  const onChoose = (opt) => {
    setPick(opt.id);
    const ok = matchesFlaw(opt.id);
    done({ ok }, opt.label);
  };

  return (
    <div className="stack-sm">
      <div className="panel" style={{ padding: '12px 16px', background: 'var(--panel-subtle)', borderRadius: 8 }}>
        <p style={{ fontWeight: 600, marginBottom: 6 }}>Argument Claims & Links:</p>
        <ul style={{ paddingLeft: 20, margin: '0 0 8px 0', fontSize: '0.9rem' }}>
          {mapData.claims?.map((c) => (
            <li key={c.id}>
              <strong>[{c.id}]</strong> {c.text} {c.formal ? `(${c.formal})` : ''}
            </li>
          ))}
        </ul>
        <p style={{ fontWeight: 600, margin: '6px 0 2px 0', fontSize: '0.85rem' }}>Edges:</p>
        <div style={{ fontSize: '0.85rem', color: 'var(--muted)' }}>
          {mapData.edges?.map((e, idx) => (
            <span key={idx} style={{ marginRight: 12 }}>
              {e.from.join(' + ')} —({e.type})→ {e.to}
            </span>
          ))}
        </div>
      </div>

      <div className="choices">
        {options.map((opt, i) => {
          const isCorrect = matchesFlaw(opt.id);
          return (
            <button
              key={opt.id}
              type="button"
              className="choice"
              disabled={pick !== null}
              data-result={pick !== null ? (isCorrect ? 'correct' : pick === opt.id ? 'wrong' : undefined) : undefined}
              onClick={() => onChoose(opt)}
            >
              <span className="key">{'ABCD'[i]}</span>
              <span>{opt.label}</span>
            </button>
          );
        })}
      </div>

      {res && (
        <Result
          ok={res.ok}
          item={item}
          given={options.find((o) => o.id === pick)?.label}
          answer={hasFlaw ? findings[0]?.message : 'Valid and properly supported argument map.'}
          onRetry={retry ? () => { reset(); setPick(null); } : null}
        />
      )}
    </div>
  );
}

// 6. SpotPartsPractice
export function SpotPartsPractice({ item, onResult, retry = true }) {
  const [pick, setPick] = useState(null);
  const opts = item.options || [];

  const choose = (opt) => {
    if (pick !== null) return;
    setPick(opt);
    onResult?.(opt === item.answer, opt);
  };

  return (
    <div className="stack-sm">
      <div className="panel" style={{ padding: '12px 16px', background: 'var(--panel-subtle)', borderRadius: 8 }}>
        <p style={{ fontStyle: 'italic', margin: 0, fontSize: '0.95rem' }}>"{item.text}"</p>
        {item.target && (
          <p style={{ margin: '8px 0 0 0', fontWeight: 600, color: 'var(--accent)' }}>{item.target}</p>
        )}
      </div>

      <div className="choices">
        {opts.map((opt, i) => (
          <button
            key={opt}
            type="button"
            className="choice"
            disabled={pick !== null}
            aria-pressed={pick === opt}
            data-result={pick !== null ? (opt === item.answer ? 'correct' : opt === pick ? 'wrong' : undefined) : undefined}
            onClick={() => choose(opt)}
          >
            <span className="key">{'ABCD'[i]}</span>
            <span><MdInline>{opt}</MdInline></span>
          </button>
        ))}
      </div>

      {pick !== null && (
        <Result
          ok={pick === item.answer}
          answer={item.answer}
          item={item}
          given={pick}
          onRetry={retry ? () => setPick(null) : null}
        />
      )}
    </div>
  );
}

// 7. FallacyIdPractice
export function FallacyIdPractice({ item, onResult, retry = true }) {
  const [pick, setPick] = useState(null);
  const opts = item.options || [];

  const choose = (opt) => {
    if (pick !== null) return;
    setPick(opt);
    onResult?.(opt === item.answer, opt);
  };

  return (
    <div className="stack-sm">
      <div className="panel" style={{ padding: '12px 16px', background: 'var(--panel-subtle)', borderRadius: 8 }}>
        <p style={{ fontStyle: 'italic', margin: 0, fontSize: '0.95rem' }}>"{item.argument}"</p>
      </div>

      <div className="choices">
        {opts.map((opt, i) => (
          <button
            key={opt}
            type="button"
            className="choice"
            disabled={pick !== null}
            aria-pressed={pick === opt}
            data-result={pick !== null ? (opt === item.answer ? 'correct' : opt === pick ? 'wrong' : undefined) : undefined}
            onClick={() => choose(opt)}
          >
            <span className="key">{'ABCD'[i]}</span>
            <span><MdInline>{opt}</MdInline></span>
          </button>
        ))}
      </div>

      {pick !== null && (
        <Result
          ok={pick === item.answer}
          answer={item.answer}
          item={item}
          given={pick}
          detail={item.why}
          onRetry={retry ? () => setPick(null) : null}
        />
      )}
    </div>
  );
}

export const PHILOSOPHY_RENDER = {
  truth_table: TruthTablePractice,
  validity: ValidityPractice,
  syllogism: SyllogismPractice,
  proof_steps: ProofStepsPractice,
  argument_map: ArgumentMapPractice,
  spot_parts: SpotPartsPractice,
  fallacy_id: FallacyIdPractice,
};
