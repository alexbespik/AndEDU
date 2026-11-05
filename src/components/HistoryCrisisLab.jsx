import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  AlertTriangle,
  RotateCcw,
  CheckCircle2,
  HelpCircle,
  History,
  Sparkles,
  Users,
  Flame,
  ArrowRight,
  BookOpen,
  Info,
  ChevronDown,
  ChevronUp,
  Scale
} from 'lucide-react';
import { reportXp } from '../lib/engage';

export const BUILTIN_CRISES = [
  {
    id: 'cuban-missile-crisis',
    title: 'Cuban Missile Crisis (October 1962)',
    role: 'President John F. Kennedy',
    roleTitle: 'Commander-in-Chief, United States',
    era: 'Cold War (1962)',
    setting: 'October 16, 1962. Classified U-2 aerial photography reveals Soviet R-12 medium-range ballistic missile launch sites under active construction in San Cristóbal, Cuba — 90 miles from Key West. Within 10 to 14 days, 32 nuclear warheads capable of striking Washington D.C. and killing 80 million Americans will be operational. Soviet Premier Nikita Khrushchev has pledged that weapons in Cuba are purely defensive. Your Executive Committee of the National Security Council (ExComm) gathers in the Cabinet Room, sharply split on four stark alternatives.',
    historicalContext: 'Following the 1961 Bay of Pigs failure and Soviet aggression in Berlin, Kennedy faces extreme pressure. General Curtis LeMay and the Joint Chiefs adamantly advocate preemptive military strikes.',
    initialState: {
      tension: 85,
      allies: 70,
      publicSupport: 80,
    },
    options: [
      {
        id: 'quarantine',
        label: 'Impose a Naval Quarantine / Blockade',
        description: 'Deploy US Navy destroyers and aircraft carriers to establish an 800-nautical-mile perimeter around Cuba. Intercept all Soviet ships and prohibit shipment of offensive military hardware, while leaving diplomatic doors open for negotiations.',
        delta: { tension: -15, allies: +15, publicSupport: +10 },
        consequence: 'Crucial diplomatic maneuvering space achieved. The Organization of American States (OAS) endorses the quarantine unanimously (20-0). Soviet transport vessels approaching the quarantine line stop or reverse course, averting immediate armed collision and granting time for backchannel diplomacy.',
        counterfactual: 'While successful, this path carried hair-raising peril: Soviet submarine B-59, isolated and depth-charged by US warships, almost fired a 15-kiloton nuclear torpedo. Only the courageous veto of Brigade Chief of Staff Vasily Arkhipov prevented atomic warfare.',
        realHistory: 'Historically chosen by President Kennedy on October 22, 1962. Calling it a "quarantine" rather than an act-of-war "blockade" gave the US defensive legal standing under the Rio Treaty. It prevented an immediate firefight and forced Khrushchev to reconsider.',
        isAuthentic: true,
      },
      {
        id: 'airstrike',
        label: 'Preemptive Tactical Airstrikes on Missile Bases',
        description: 'Authorize hundreds of coordinated Air Force and Navy sorties across Cuba to destroy missile sites, SAM air-defense batteries, and MiG airfields before launchers become operational.',
        delta: { tension: +15, allies: -20, publicSupport: +5 },
        consequence: 'Tension surges to 100% (DEFCON 1). CIA reconnaissance admits air strikes cannot guarantee 100% destruction of mobile nuclear launchers. Declassified archives reveal Soviet troops in Cuba possessed 80 tactical nuclear cruise missiles with pre-delegated launch orders to incinerate Guantanamo Bay.',
        counterfactual: 'Advocated fiercely by General Curtis LeMay and the Joint Chiefs. Had Kennedy approved airstrikes, surviving Soviet missiles would have fired upon US staging bases in Florida, and the Red Army would have seized West Berlin, triggering all-out NATO nuclear war.',
        realHistory: 'Firmly rejected by Kennedy after CIA analysts admitted at least several Soviet missiles would likely survive and launch. Kennedy remarked: "They, no more than we, can forecast these things with certainty."',
        isAuthentic: false,
      },
      {
        id: 'invasion',
        label: 'Full-Scale Amphibious & Airborne Invasion of Cuba',
        description: 'Assemble 120,000 US combat troops in Florida for an amphibious landing and airborne drop to seize Cuba, topple Fidel Castro, and eliminate the Soviet installations through direct ground warfare.',
        delta: { tension: +15, allies: -30, publicSupport: -10 },
        consequence: 'Immediate global catastrophe. US troops land directly into 43,000 Soviet combat troops and 270,000 Cuban fighters equipped with battlefield atomic Luna rockets. US war casualties exceed 20,000 in the first week, leading to direct nuclear exchanges between superpowers.',
        counterfactual: 'US intelligence severely underestimated Soviet presence (believing only 10,000 Soviets were in Cuba without nuclear arms). An invasion was a catastrophic intelligence trap that would have caused WWIII.',
        realHistory: 'Prepared as contingency plan OPLAN 312/316, but held in reserve while the quarantine and secret diplomatic channels operated.',
        isAuthentic: false,
      },
      {
        id: 'jupiter-trade',
        label: 'Direct Secret Jupiter Missile Trade with Moscow',
        description: 'Dispatch Attorney General Robert Kennedy to Soviet Ambassador Anatoly Dobrynin with a secret covenant: the United States will remove US Jupiter nuclear missiles from Turkey and Italy within 6 months if Khrushchev publicly removes all missiles from Cuba under UN supervision.',
        delta: { tension: -40, allies: -10, publicSupport: +15 },
        consequence: 'Definitive de-escalation. Khrushchev accepts within 24 hours. The deal is kept strictly secret from NATO allies and the public to maintain American political stature and avoid undermining NATO confidence.',
        counterfactual: 'Had the Turkey swap been leaked immediately, NATO members might have felt Washington was willing to sacrifice European security for its own homeland, threatening the NATO alliance.',
        realHistory: 'This secret pledge was the actual mechanism that ended the crisis on October 27-28, 1962. The existence of the secret Turkey missile concession remained classified for 27 years until confirmed in 1989.',
        isAuthentic: true,
      },
    ],
  },
  {
    id: 'crossing-the-rubicon',
    title: 'Crossing the Rubicon (49 BCE)',
    role: 'Gaius Julius Caesar',
    roleTitle: 'Proconsul of Gaul & Imperator',
    era: 'Roman Republic (49 BCE)',
    setting: 'January 10, 49 BCE. You stand on the northern bank of the shallow Rubicon river with the veterans of Legio XIII Gemina. South of this stream lies Roman civil territory. In Rome, the Senate, driven by Cato the Younger and your former ally Pompey the Great, has passed the Senatus Consultum Ultimum, ordering you to disband your legions and return as a private citizen to face immediate judicial prosecution and exile.',
    historicalContext: 'Ten years of campaigning in Gaul have made you immensely wealthy and beloved by your soldiers and the Roman plebs, but the senatorial nobility (Optimates) view you as a lethal threat to the aristocratic Republic.',
    initialState: {
      tension: 75,
      allies: 55,
      publicSupport: 70,
    },
    options: [
      {
        id: 'cross',
        label: 'Cross the Rubicon in Arms ("Alea iacta est")',
        description: 'March Legio XIII across the Rubicon into Italy. Under Roman law, entering Italy with armed troops without senatorial authority constitutes high treason. March with lightning speed directly toward Rome.',
        delta: { tension: +15, allies: -20, publicSupport: +20 },
        consequence: 'Civil war begins. Overcome by panic and believing you possess multiple legions nearby, Pompey and the Senate flee Rome in haste to Greece, abandoning the state treasury in the Temple of Saturn to your forces.',
        counterfactual: 'Had Pompey held Rome, a protracted siege could have alienated the civilian populace. Caesar’s speed (celeritas) caught the senatorial faction completely unprepared.',
        realHistory: 'Historically chosen by Caesar on January 10, 49 BCE with the famous exclamation "Alea iacta est" (The die is cast). It sparked the Great Roman Civil War, ending in Caesar\'s victory at Pharsalus and the eventual transition from Republic to the Roman Empire.',
        isAuthentic: true,
      },
      {
        id: 'disband',
        label: 'Disband Legions & Return to Stand Trial',
        description: 'Submit to senatorial authority, order your veterans to demobilize, and return to Rome as a private citizen to defend your actions before the Optimates-dominated courts.',
        delta: { tension: -45, allies: +25, publicSupport: -35 },
        consequence: 'Civil war is averted, but your political survival is extinguished. Cato and Pompey indict you under the Lex Julia for illegal warfare in Gaul. Condemned without army protection, you face permanent exile or death.',
        counterfactual: 'Like the brothers Gracchi or Scipio Africanus before him, Caesar would have been neutralized through senatorial legal maneuvers, leaving the aristocratic senatorial oligarchy intact.',
        realHistory: 'Caesar explicitly refused this outcome, knowing that entering Rome without imperium was political and physical suicide.',
        isAuthentic: false,
      },
      {
        id: 'compromise',
        label: 'Propose Mutual Simultaneous Disarmament',
        description: 'Send Tribune Curio to the Senate proposing that both Caesar and Pompey concurrently resign their provincial commands and legions, returning authority equally to the Senate.',
        delta: { tension: -15, allies: +15, publicSupport: +10 },
        consequence: 'Supported by moderate senators (over 370 senators voted in favor of mutual disarmament in December 50 BCE), but violently vetoed and rejected by Consul Lentulus, Scipio, and Cato, who expel your tribunes from Rome.',
        counterfactual: 'Had Pompey agreed, the Republic might have preserved a fragile peace, but fear of Caesar\'s enduring popularity drove the Optimates to reject any equal standing.',
        realHistory: 'Caesar repeatedly offered this compromise; the senatorial hardliners rejected it every time and threatened the lives of Caesar’s tribunes, giving Caesar legal pretext to march.',
        isAuthentic: false,
      },
      {
        id: 'fortify-gaul',
        label: 'Fortify Cisalpine Gaul and Hold Defense',
        description: 'Refuse to cross the Rubicon, fortify the Alpine mountain passes, and remain in Cisalpine Gaul defying the Senate while adopting a strictly defensive posture.',
        delta: { tension: +5, allies: -30, publicSupport: -20 },
        consequence: 'Strategic paralysis. Pompey mobilizes the enormous wealth and legions of Greece, Syria, and Spain. Cut off from Italian supplies and recruitment, your army slowly disintegrates as veteran contracts expire.',
        counterfactual: 'Time worked entirely in Pompey’s favor; passive defense would have allowed the Optimates to assemble crushing overwhelming force against Gaul.',
        realHistory: 'Caesar understood that speed and boldness were his only advantages against the broader resources of the Roman Mediterranean.',
        isAuthentic: false,
      },
    ],
  },
  {
    id: 'berlin-airlift',
    title: 'The Berlin Airlift (1948)',
    role: 'President Harry S. Truman',
    roleTitle: 'Commander-in-Chief, United States',
    era: 'Early Cold War (1948)',
    setting: 'June 24, 1948. Following the introduction of the Deutsche Mark in Western sectors, Soviet military authorities sever all road, rail, and water transport from West Germany through Soviet-occupied East Germany into West Berlin. Over 2.1 million West Berliners and 22,000 Allied garrison troops are cut off from electricity, food, coal, and medicine. Berlin has 36 days of food and 45 days of coal remaining. Soviet Premier Joseph Stalin intends to starve the city to compel the Western Allies to abandon West Berlin.',
    historicalContext: 'World War II concluded only three years prior. Europe is exhausted. A direct military firefight between American and Soviet troops threatens to ignite World War III.',
    initialState: {
      tension: 80,
      allies: 75,
      publicSupport: 65,
    },
    options: [
      {
        id: 'airlift',
        label: 'Launch Operation Vittles: Full-Scale Aerial Resupply',
        description: 'Mobilize the US Air Force and British Royal Air Force to supply the entire metropolis of 2.1 million people exclusively by air transport through the three guaranteed 20-mile-wide flight corridors established in 1945.',
        delta: { tension: -15, allies: +20, publicSupport: +25 },
        consequence: 'Logistical and humanitarian triumph. Organized by Gen. William Tunner, Allied cargo planes land at Tempelhof, Gatow, and newly built Tegel every 30 seconds. Over 2.33 million tons of supplies keep Berlin alive through a freezing winter without firing a single shot.',
        counterfactual: 'Critics argued feeding a major city by air was aerodynamically impossible (requiring 4,500 tons daily). Tunner’s clockwork traffic pattern and German civilian cooperation proved them wrong.',
        realHistory: 'Historically chosen by Truman and British Foreign Secretary Ernest Bevin. On May 12, 1949, seeing the blockade had failed and backfired politically, Stalin lifted the blockade. The airlift catalyzed the formation of NATO and the democratic Federal Republic of Germany.',
        isAuthentic: true,
      },
      {
        id: 'armored-convoy',
        label: 'Force Access with an Armored Military Convoy',
        description: 'Send an armored combat division with heavy engineers along the Helmstedt-Berlin Autobahn to clear Soviet checkpoints and roadblocks by armed military force.',
        delta: { tension: +20, allies: -20, publicSupport: -10 },
        consequence: 'Tension hits 100%. Soviet forces surround the convoy with superior armor and artillery. A firefight at the first barrier ignites open combat in Central Europe, starting World War III.',
        counterfactual: 'Advocated by General Lucius D. Clay. Truman rejected it: "We are going to stay in Berlin, but we will not start World War III over a road barrier."',
        realHistory: 'Firmly vetoed by Truman and European allies due to overwhelming Soviet conventional superiority in East Germany.',
        isAuthentic: false,
      },
      {
        id: 'abandon-berlin',
        label: 'Evacuate Garrison and Concede West Berlin',
        description: 'Evacuate Allied troops and civilian personnel, surrendering West Berlin to Soviet administration to eliminate the flashpoint.',
        delta: { tension: -50, allies: -60, publicSupport: -50 },
        consequence: 'Catastrophic collapse of Western resolve. Western European nations conclude American security guarantees are worthless. The democratic West German movement collapses in disillusionment.',
        counterfactual: 'Truman famously affirmed: "We stay in Berlin, period. We will not be pushed out." Surrender would have handed Stalin dominant psychological control over post-war Europe.',
        realHistory: 'Immediately rejected by Truman and Bevin as an unacceptable strategic and moral capitulation.',
        isAuthentic: false,
      },
      {
        id: 'atomic-ultimatum',
        label: 'Deploy B-29s & Issue Nuclear Ultimatum to Moscow',
        description: 'Deploy nuclear-capable B-29 bombers to Great Britain and issue an immediate ultimatum to Stalin: lift the blockade within 48 hours or face atomic bombardment.',
        delta: { tension: +15, allies: -15, publicSupport: -15 },
        consequence: 'Widespread panic across Europe. While B-29s are indeed sent to the UK as deterrence, issuing an overt nuclear ultimatum triggers protests in allied parliaments and risks unprovoked Soviet preemptive action.',
        counterfactual: 'The B-29s sent to the UK were actually non-atomic bombers without nuclear cores (a strategic bluff). Issuing a rigid ultimatum would have forced either nuclear war or a humiliating American backing down.',
        realHistory: 'Truman deployed B-29s as quiet deterrence, but deliberately refused to issue an ultimatum, betting on the peaceful resilience of the Airlift.',
        isAuthentic: false,
      },
    ],
  },
  {
    id: 'constitutional-convention',
    title: 'Constitutional Convention (1787)',
    role: 'James Madison & The Delegates',
    roleTitle: 'Architect of the Constitution',
    era: 'Early American Republic (1787)',
    setting: 'July 1787, Pennsylvania State House, Philadelphia. Fifty-five delegates have gathered in oppressive heat behind locked doors and drawn curtains. The Convention is on the verge of collapse over legislative representation: Large states argue that proportional representation based on population is the only democratic foundation; small states warn that proportional representation will reduce them to vassalage and declare they would rather dissolve the union or seek foreign alliances than submit.',
    historicalContext: 'Shays\' Rebellion showed the Articles of Confederation were failing, but intense rivalry between large states (VA, PA, MA) and small states (NJ, DE, CT) threatens the birth of the United States.',
    initialState: {
      tension: 70,
      allies: 50,
      publicSupport: 60,
    },
    options: [
      {
        id: 'connecticut-compromise',
        label: 'The Connecticut Compromise (The Great Compromise)',
        description: 'Establish a bicameral legislature: a lower house (House of Representatives) with seats apportioned by population, and an upper house (Senate) with equal representation (two senators per state) chosen by state legislatures.',
        delta: { tension: -35, allies: +40, publicSupport: +25 },
        consequence: 'Historic breakthrough. Small states gain crucial protection in the Senate; large states preserve proportional power over revenue bills in the House. Tension subsides, delegates proceed to draft the Executive and Judiciary.',
        counterfactual: 'Without this compromise, William Paterson\'s faction would have walked out, ending the convention and fracturing the 13 states into vulnerable regional leagues.',
        realHistory: 'Proposed by Roger Sherman and Oliver Ellsworth of Connecticut. On July 16, 1787, it passed by a razor-thin margin (5-4-1 state vote). It became the bedrock compromise of the United States Constitution.',
        isAuthentic: true,
      },
      {
        id: 'virginia-plan',
        label: 'Insist on Pure Proportional Virginia Plan',
        description: 'Insist that representation in BOTH houses of Congress be determined strictly by population, denying equal state voting power.',
        delta: { tension: +20, allies: -30, publicSupport: +10 },
        consequence: 'Small state walkout. Gunning Bedford Jr. of Delaware declares on the convention floor: "The small states will find some foreign ally of more honor and good faith who will take them by the hand and do them justice!" Delaware and New Jersey withdraw.',
        counterfactual: 'Madison and Wilson believed equal state votes were fundamentally unjust. Had they forced the issue, the United States would have broken apart into three regional republics.',
        realHistory: 'Advocated passionately by Madison, but wisely compromised when delegates recognized the union would dissolve without concessions to small states.',
        isAuthentic: false,
      },
      {
        id: 'new-jersey-plan',
        label: 'Adopt the New Jersey Plan (One State, One Vote)',
        description: 'Keep the unicameral congress of the Articles of Confederation where each state has one vote, merely granting Congress limited authority to levy tariffs and regulate commerce.',
        delta: { tension: +15, allies: -20, publicSupport: -15 },
        consequence: 'Large state rejection. Pennsylvania and Virginia, representing nearly half the population, refuse to join a system where a tiny minority can indefinitely veto the majority will.',
        counterfactual: 'Would have perpetuated the chronic weakness of the Articles, likely leading to interstate trade wars and eventual fragmentation.',
        realHistory: 'Introduced by William Paterson on June 15, 1787; voted down 7-3, prompting the compromise that merged both systems.',
        isAuthentic: false,
      },
      {
        id: 'dissolve-convention',
        label: 'Adjourn Sine Die and Report Impasse',
        description: 'Admit irreconcilable differences, dissolve the convention without agreement, and report to the Confederation Congress that a new constitution is impossible.',
        delta: { tension: -20, allies: -40, publicSupport: -40 },
        consequence: 'Catastrophe. The Continental dollar collapses completely, interstate trade disputes turn into armed skirmishes, and European empires move in to exploit American division.',
        counterfactual: 'George Washington and Alexander Hamilton warned this outcome would guarantee civil warfare in North America followed by British or Spanish re-conquest.',
        realHistory: 'The dreaded nightmare scenario; the shared terror of this outcome compelled delegates to stay in Philadelphia and reach agreement.',
        isAuthentic: false,
      },
    ],
  },
];

export default function HistoryCrisisLab({ topic, initialScenarioId }) {
  const allScenarios = React.useMemo(() => {
    if (topic?.crisis && topic.crisis.id && Array.isArray(topic.crisis.options)) {
      const custom = {
        ...topic.crisis,
        initialState: topic.crisis.initialState || topic.crisis.state || { tension: 70, allies: 60, publicSupport: 65 },
        options: topic.crisis.options.map((opt) => ({
          ...opt,
          delta: opt.delta || { tension: -10, allies: +10, publicSupport: +10 },
          isAuthentic: Boolean(opt.isAuthentic ?? opt.is_authentic ?? opt.chosen_in_history),
          realHistory: opt.realHistory || opt.real_history || opt.consequence,
        })),
      };
      return [custom, ...BUILTIN_CRISES.filter((c) => c.id !== custom.id)];
    }
    return BUILTIN_CRISES;
  }, [topic?.crisis]);

  const [scenarioId, setScenarioId] = useState(
    initialScenarioId && allScenarios.some((s) => s.id === initialScenarioId)
      ? initialScenarioId
      : allScenarios[0].id
  );

  useEffect(() => {
    if (initialScenarioId && allScenarios.some((s) => s.id === initialScenarioId)) {
      setScenarioId(initialScenarioId);
      setSelectedOptionId(null);
      setShowHistory(false);
    }
  }, [initialScenarioId, allScenarios]);

  const activeScenario = allScenarios.find((s) => s.id === scenarioId) || allScenarios[0];
  const [selectedOptionId, setSelectedOptionId] = useState(null);
  const [showHistory, setShowHistory] = useState(false);
  const [exploredScenarios, setExploredScenarios] = useState({});

  const selectedOption = activeScenario.options.find((o) => o.id === selectedOptionId) || null;

  // Compute live meters based on selection
  const liveState = React.useMemo(() => {
    const base = activeScenario.initialState || { tension: 70, allies: 60, publicSupport: 65 };
    if (!selectedOption) return { ...base };
    const d = selectedOption.delta || { tension: 0, allies: 0, publicSupport: 0 };
    return {
      tension: Math.max(0, Math.min(100, (base.tension ?? 70) + (d.tension ?? 0))),
      allies: Math.max(0, Math.min(100, (base.allies ?? 60) + (d.allies ?? 0))),
      publicSupport: Math.max(0, Math.min(100, (base.publicSupport ?? base.public_support ?? 65) + (d.publicSupport ?? d.public_support ?? 0))),
    };
  }, [activeScenario, selectedOption]);

  const handleSelectOption = (opt) => {
    setSelectedOptionId(opt.id);
    setShowHistory(true);
    if (!exploredScenarios[activeScenario.id]) {
      setExploredScenarios((prev) => ({ ...prev, [activeScenario.id]: true }));
      reportXp('practice_correct', `crisis:${activeScenario.id}:${opt.id}`);
    }
  };

  const handleReset = () => {
    setSelectedOptionId(null);
    setShowHistory(false);
  };

  const handleSwitchScenario = (id) => {
    setScenarioId(id);
    setSelectedOptionId(null);
    setShowHistory(false);
  };

  const meterColor = (kind, val) => {
    if (kind === 'tension') {
      if (val >= 80) return 'var(--bad)';
      if (val >= 50) return 'var(--gold)';
      return 'var(--ok)';
    }
    if (val >= 70) return 'var(--ok)';
    if (val >= 40) return 'var(--gold)';
    return 'var(--bad)';
  };

  return (
    <div className="history-crisis-lab" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      {/* Scenario Selector Header */}
      <div className="panel" style={{ padding: 'var(--space-3)', display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', alignItems: 'center', justifyContent: 'space-between', borderBottom: '2px solid var(--rule)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <ShieldAlert size={20} style={{ color: 'var(--accent)' }} aria-hidden="true" />
          <span style={{ fontFamily: 'var(--font-mono, monospace)', fontWeight: 600, fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Historical Crisis Simulator
          </span>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-1)' }}>
          {allScenarios.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`choice ${scenarioId === s.id ? 'active' : ''}`}
              style={{
                padding: 'var(--space-1) var(--space-3)',
                fontSize: '0.82rem',
                borderRadius: 'var(--radius-sm, 4px)',
                cursor: 'pointer',
                border: scenarioId === s.id ? '2px solid var(--accent)' : '1px solid var(--rule)',
                background: scenarioId === s.id ? 'var(--accent-tint)' : 'var(--surface)',
                color: scenarioId === s.id ? 'var(--accent-hover)' : 'var(--ink)',
                fontWeight: scenarioId === s.id ? 600 : 400,
              }}
              onClick={() => handleSwitchScenario(s.id)}
            >
              {s.title.split('(')[0].trim()}
            </button>
          ))}
        </div>
      </div>

      {/* Leader & Briefing Banner */}
      <div
        className="panel"
        style={{
          padding: 'var(--space-4)',
          background: 'var(--paper)',
          borderLeft: '4px solid var(--accent)',
          borderRadius: 'var(--radius-md, 6px)',
        }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'flex-start', gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.25rem', fontFamily: 'var(--font-heading, serif)' }}>
              {activeScenario.title}
            </h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginTop: '4px', fontSize: '0.85rem', color: 'var(--muted)' }}>
              <span style={{ fontWeight: 600, color: 'var(--ink)' }}>Leader Persona:</span>
              <span>{activeScenario.role} ({activeScenario.roleTitle})</span>
              <span>•</span>
              <span className="badge" style={{ fontSize: '0.75rem', background: 'var(--sunk)', padding: '1px 6px' }}>{activeScenario.era}</span>
            </div>
          </div>
          {selectedOptionId && (
            <button
              type="button"
              className="button secondary"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', padding: '4px 10px' }}
              onClick={handleReset}
            >
              <RotateCcw size={14} aria-hidden="true" /> Reset Dilemma
            </button>
          )}
        </div>

        <p style={{ margin: 'var(--space-2) 0', fontSize: '0.92rem', lineHeight: 1.5, color: 'var(--ink-soft)' }}>
          {activeScenario.setting}
        </p>

        {activeScenario.historicalContext && (
          <div style={{ marginTop: 'var(--space-2)', padding: 'var(--space-2) var(--space-3)', background: 'var(--surface)', borderRadius: '4px', border: '1px solid var(--rule)', fontSize: '0.82rem', color: 'var(--muted)' }}>
            <strong>Historical Context:</strong> {activeScenario.historicalContext}
          </div>
        )}
      </div>

      {/* Live State Meters */}
      <div
        className="panel"
        style={{
          padding: 'var(--space-3) var(--space-4)',
          background: 'var(--surface)',
          border: '1px solid var(--rule)',
          borderRadius: 'var(--radius-md, 6px)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)' }}>
          <span style={{ fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--muted)' }}>
            State Meters (Dynamic Strategic Balance)
          </span>
          {selectedOption && (
            <span style={{ fontSize: '0.78rem', color: 'var(--accent)', fontWeight: 600 }}>
              Updated by choice: {selectedOption.label}
            </span>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 'var(--space-3)' }}>
          {/* Tension Meter */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 500 }}>
                <Flame size={14} style={{ color: 'var(--bad)' }} aria-hidden="true" /> Crisis Tension
              </span>
              <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono, monospace)', color: meterColor('tension', liveState.tension) }}>
                {liveState.tension}%
                {selectedOption?.delta?.tension !== undefined && (
                  <span style={{ fontSize: '0.75rem', marginLeft: '4px', color: selectedOption.delta.tension > 0 ? 'var(--bad)' : 'var(--ok)' }}>
                    ({selectedOption.delta.tension > 0 ? `+${selectedOption.delta.tension}` : selectedOption.delta.tension}%)
                  </span>
                )}
              </span>
            </div>
            <div style={{ width: '100%', height: '8px', background: 'var(--sunk)', borderRadius: '4px', overflow: 'hidden' }}>
              <div
                style={{
                  width: `${liveState.tension}%`,
                  height: '100%',
                  background: meterColor('tension', liveState.tension),
                  transition: 'width 0.4s ease',
                }}
              />
            </div>
          </div>

          {/* Alliances Meter */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 500 }}>
                <Users size={14} style={{ color: 'var(--accent)' }} aria-hidden="true" /> Alliance Cohesion
              </span>
              <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono, monospace)', color: meterColor('allies', liveState.allies) }}>
                {liveState.allies}%
                {selectedOption?.delta?.allies !== undefined && (
                  <span style={{ fontSize: '0.75rem', marginLeft: '4px', color: selectedOption.delta.allies >= 0 ? 'var(--ok)' : 'var(--bad)' }}>
                    ({selectedOption.delta.allies >= 0 ? `+${selectedOption.delta.allies}` : selectedOption.delta.allies}%)
                  </span>
                )}
              </span>
            </div>
            <div style={{ width: '100%', height: '8px', background: 'var(--sunk)', borderRadius: '4px', overflow: 'hidden' }}>
              <div
                style={{
                  width: `${liveState.allies}%`,
                  height: '100%',
                  background: 'var(--accent)',
                  transition: 'width 0.4s ease',
                }}
              />
            </div>
          </div>

          {/* Public Support Meter */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 500 }}>
                <Scale size={14} style={{ color: 'var(--gold-text)' }} aria-hidden="true" /> Domestic Support
              </span>
              <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono, monospace)', color: meterColor('support', liveState.publicSupport) }}>
                {liveState.publicSupport}%
                {(selectedOption?.delta?.publicSupport ?? selectedOption?.delta?.public_support) !== undefined && (
                  <span style={{ fontSize: '0.75rem', marginLeft: '4px', color: (selectedOption.delta.publicSupport ?? selectedOption.delta.public_support) >= 0 ? 'var(--ok)' : 'var(--bad)' }}>
                    ({(selectedOption.delta.publicSupport ?? selectedOption.delta.public_support) >= 0 ? `+${selectedOption.delta.publicSupport ?? selectedOption.delta.public_support}` : (selectedOption.delta.publicSupport ?? selectedOption.delta.public_support)}%)
                  </span>
                )}
              </span>
            </div>
            <div style={{ width: '100%', height: '8px', background: 'var(--sunk)', borderRadius: '4px', overflow: 'hidden' }}>
              <div
                style={{
                  width: `${liveState.publicSupport}%`,
                  height: '100%',
                  background: 'var(--gold)',
                  transition: 'width 0.4s ease',
                }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Decision Options Grid */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)' }}>
          <h3 style={{ margin: 0, fontSize: '1rem', fontFamily: 'var(--font-mono, monospace)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            {selectedOption ? 'Strategic Outcome & Analysis' : 'Evaluate Leadership Options:'}
          </h3>
          <span style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
            {selectedOption ? 'Click another option to test counterfactual outcomes' : 'Select a path to evaluate consequences'}
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--space-3)' }}>
          {activeScenario.options.map((opt, idx) => {
            const isSelected = selectedOptionId === opt.id;
            return (
              <button
                key={opt.id}
                type="button"
                className="card"
                style={{
                  textAlign: 'left',
                  cursor: 'pointer',
                  padding: 'var(--space-3)',
                  border: isSelected ? '2px solid var(--accent)' : '1px solid var(--rule)',
                  background: isSelected ? 'var(--surface)' : 'var(--paper)',
                  boxShadow: isSelected ? '0 2px 8px rgba(0,0,0,0.08)' : 'none',
                  borderRadius: 'var(--radius-md, 6px)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 'var(--space-2)',
                  transition: 'border-color 0.2s ease, transform 0.1s ease',
                }}
                onClick={() => handleSelectOption(opt)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 'var(--space-1)' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.9rem', color: isSelected ? 'var(--accent)' : 'var(--ink)' }}>
                    Option {idx + 1}: {opt.label}
                  </span>
                  {opt.isAuthentic && (
                    <span
                      className="badge"
                      style={{
                        fontSize: '0.7rem',
                        background: 'var(--gold-tint)',
                        color: 'var(--gold-text)',
                        border: '1px solid var(--gold-rule)',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      Historical Choice
                    </span>
                  )}
                </div>

                <p style={{ margin: 0, fontSize: '0.84rem', color: 'var(--ink-soft)', lineHeight: 1.45 }}>
                  {opt.description}
                </p>

                {isSelected && (
                  <div style={{ marginTop: 'var(--space-2)', paddingTop: 'var(--space-2)', borderTop: '1px solid var(--rule)' }}>
                    <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--ink)', marginBottom: '4px' }}>
                      Immediate Strategic Consequence:
                    </div>
                    <div style={{ fontSize: '0.82rem', color: 'var(--ink-soft)', lineHeight: 1.45, background: 'var(--sunk)', padding: 'var(--space-2)', borderRadius: '4px' }}>
                      {opt.consequence}
                    </div>

                    {opt.counterfactual && (
                      <div style={{ marginTop: 'var(--space-2)', fontSize: '0.8rem', color: 'var(--muted)' }}>
                        <strong>Counterfactual Risk:</strong> {opt.counterfactual}
                      </div>
                    )}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* The Real History Historical Reality Reveal */}
      {selectedOption && (
        <div
          className="panel"
          style={{
            padding: 'var(--space-4)',
            background: 'var(--gold-tint)',
            border: '1px solid var(--gold-rule)',
            borderRadius: 'var(--radius-md, 6px)',
          }}
        >
          <button
            type="button"
            style={{
              width: '100%',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              cursor: 'pointer',
              background: 'transparent',
              border: 'none',
              padding: 0,
              textAlign: 'left',
            }}
            onClick={() => setShowHistory(!showHistory)}
            aria-expanded={showHistory}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
              <History size={18} style={{ color: 'var(--gold-text)' }} aria-hidden="true" />
              <h4 style={{ margin: 0, fontSize: '0.95rem', color: 'var(--gold-text)', fontFamily: 'var(--font-mono, monospace)', textTransform: 'uppercase' }}>
                The Real History: What Actually Happened
              </h4>
            </div>
            <span style={{ color: 'var(--gold-text)', display: 'flex', alignItems: 'center' }}>
              {showHistory ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </span>
          </button>

          {showHistory && (
            <div style={{ marginTop: 'var(--space-3)', fontSize: '0.88rem', color: 'var(--ink)', lineHeight: 1.55 }}>
              <p style={{ margin: '0 0 var(--space-2) 0' }}>
                <strong>Historical Assessment of Selected Path:</strong>
              </p>
              <div style={{ background: 'var(--surface)', padding: 'var(--space-3)', borderRadius: '4px', border: '1px solid var(--gold-rule)' }}>
                {selectedOption.realHistory}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
