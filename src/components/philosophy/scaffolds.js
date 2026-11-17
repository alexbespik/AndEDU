// Worked proofs for the Fitch desk, in the engine's own format (logic_proof.py, forall x: Calgary rules).
// Each `solution` passes logic_engine.check({op: 'proof', ...}) with complete: true; the desk starts a student with
// the premises and goal only, and offers the solution on request.
const L = (formula, rule, cites = [], depth = 0) => ({ formula, rule, cites, depth });

export const SCAFFOLDS = [
  {
    id: 'modus-ponens', title: 'Modus ponens', rules: 'basic',
    hint: 'Two premises, one rule: ->E needs the conditional and its antecedent.',
    premises: ['P -> Q', 'P'], goal: 'Q',
    solution: [L('P -> Q', 'PR'), L('P', 'PR'), L('Q', '->E', [1, 2])],
  },
  {
    id: 'modus-tollens', title: 'Modus tollens from the basic rules', rules: 'basic',
    hint: 'Assume P, reach a contradiction, then close the subproof with ~I.',
    premises: ['P -> Q', '~Q'], goal: '~P',
    solution: [L('P -> Q', 'PR'), L('~Q', 'PR'), L('P', 'AS', [], 1), L('Q', '->E', [1, 3], 1),
      L('_|_', '~E', [2, 4], 1), L('~P', '~I', ['3-5'])],
  },
  {
    id: 'reductio', title: 'Reductio ad absurdum', rules: 'basic',
    hint: 'If P led to both Q and ~Q, P cannot hold.',
    premises: ['P -> Q', 'P -> ~Q'], goal: '~P',
    solution: [L('P -> Q', 'PR'), L('P -> ~Q', 'PR'), L('P', 'AS', [], 1), L('Q', '->E', [1, 3], 1),
      L('~Q', '->E', [2, 3], 1), L('_|_', '~E', [4, 5], 1), L('~P', '~I', ['3-6'])],
  },
  {
    id: 'de-morgan', title: "De Morgan's law", rules: 'basic',
    hint: 'Prove ~P and ~Q separately, each by assuming it and using |I; then join them with &I.',
    premises: ['~(P | Q)'], goal: '~P & ~Q',
    solution: [L('~(P | Q)', 'PR'), L('P', 'AS', [], 1), L('P | Q', '|I', [2], 1), L('_|_', '~E', [1, 3], 1),
      L('~P', '~I', ['2-4']), L('Q', 'AS', [], 1), L('P | Q', '|I', [6], 1), L('_|_', '~E', [1, 7], 1),
      L('~Q', '~I', ['6-8']), L('~P & ~Q', '&I', [5, 9])],
  },
];
