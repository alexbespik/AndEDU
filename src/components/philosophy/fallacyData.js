// Informal fallacies as a TEACHING catalog. They depend on meaning and context, so nothing here (and no script) judges a
// text: each entry says what the pattern is, when the same shape is fine, and how to repair an argument that has it.
export const INFORMAL = [
  {
    id: 'ad-hominem', name: 'Ad hominem',
    definition: 'Rejecting a claim by attacking the person who makes it (their character, circumstances or consistency) instead of the reasons they give.',
    example: '"You say the bridge design is unsafe, but you failed your engineering exam, so ignore it."',
    legitimate: 'Doubting a witness\'s honesty or a paid expert\'s conflict of interest bears on how much to trust their testimony. It stays fair when it only adjusts trust and does not claim the claim is false.',
    repair: 'Set the person aside and ask whether the reasons and evidence hold up. If credibility matters, say so openly and look for independent support.',
  },
  {
    id: 'straw-man', name: 'Straw man',
    definition: 'Answering a weaker or distorted version of an opponent\'s position, then treating the distortion\'s defeat as a win.',
    example: '"She wants to cut the military budget, so she wants the country defenceless."',
    legitimate: 'Summarising an opponent briefly is not a straw man if the summary is one they would accept. Showing what a position would imply is fair when it is labelled as an implication.',
    repair: 'Apply the principle of charity: restate the position so its holder would agree, in its strongest form, then respond to that.',
  },
  {
    id: 'slippery-slope', name: 'Slippery slope',
    definition: 'Claiming that one step will lead through a chain of steps to a terrible result, without showing that each link is likely.',
    example: '"If we allow one exception to the rule, soon there will be no rules at all."',
    legitimate: 'A chain can be sound when each link has evidence behind it: a documented precedent, or a feedback loop such as a bank run or an arms race.',
    repair: 'Spell out each link and give a reason for it. Replace "will inevitably" with an estimate of how likely each step is, or name a point where the chain can be stopped.',
  },
  {
    id: 'begging-the-question', name: 'Begging the question (circular reasoning)',
    definition: 'A premise already assumes the conclusion, so the argument cannot persuade anyone who doubted the conclusion.',
    example: '"The book is reliable because it says so, and a reliable book would not lie."',
    legitimate: 'Every argument rests on some premises; a short argument whose premises restate the thesis is only a problem when the audience was asking for independent grounds.',
    repair: 'Find a premise the other side already accepts that supports the conclusion without presupposing it. The Argument map in PHILIN flags support that loops back on itself.',
  },
  {
    id: 'false-dilemma', name: 'False dilemma',
    definition: 'Presenting two options as the only ones when others exist.',
    example: '"Either we ban the technology completely or we accept every harm it brings."',
    legitimate: 'Sometimes there really are two options (a light is on or off, a vote passes or fails), and a speaker may narrow to the realistic ones if they say so.',
    repair: 'List the options in between and combinations. If you say "either/or", say why nothing else is possible.',
  },
  {
    id: 'inappropriate-authority', name: 'Appeal to inappropriate authority',
    definition: 'Treating someone\'s say-so as evidence when their expertise does not cover the question, or when experts in the field disagree.',
    example: '"A famous actor says this supplement works, so it does."',
    legitimate: 'Relying on real experts speaking within their field is ordinary and often wise, since nobody can check everything. It is weaker when experts split, and it never replaces the evidence that persuaded them.',
    repair: 'Ask what the authority is an authority on, whether there is consensus, and point to the underlying evidence rather than the name.',
  },
  {
    id: 'equivocation', name: 'Equivocation',
    definition: 'Using one word with two meanings in different premises so that the conclusion seems to follow.',
    example: '"Laws require a lawmaker; the laws of physics are laws; so the universe has a lawmaker."',
    legitimate: 'A word may change meaning on purpose in a pun or when the shift is stated openly.',
    repair: 'Fix one meaning for each key term, or split the term in two ("law" as statute, "law" as regularity) and see whether the argument still works.',
  },
  {
    id: 'post-hoc', name: 'Post hoc ergo propter hoc',
    definition: 'Concluding that A caused B because A came first.',
    example: '"I wore my lucky socks and we won, so the socks did it."',
    legitimate: 'Order in time is necessary for a cause and a good clue. Repeated, controlled or mechanistically explained sequences do support causation.',
    repair: 'Ask for a mechanism, comparison cases without A, and whether a third factor (or chance) explains both events.',
  },
  {
    id: 'hasty-generalization', name: 'Hasty generalization',
    definition: 'Drawing a broad conclusion from too few or unrepresentative cases.',
    example: '"Two of my neighbours were rude, so people in this city are rude."',
    legitimate: 'Small samples are fine for modest claims ("some", "in these cases") or when the cases are known to be typical.',
    repair: 'Say how many cases and how they were chosen, and weaken the claim to match, or gather a larger and more varied sample.',
  },
];

// Argument shapes the engine's `forms` op names. Letters stand for whole statements.
export const FORMAL_EXAMPLES = [
  { label: 'Affirming the consequent', premises: ['Rain -> Wet', 'Wet'], conclusion: 'Rain' },
  { label: 'Denying the antecedent', premises: ['Rain -> Wet', '~Rain'], conclusion: '~Wet' },
  { label: 'Affirming a disjunct', premises: ['Tea | Coffee', 'Tea'], conclusion: '~Coffee' },
  { label: 'Converting a conditional', premises: ['P -> Q'], conclusion: 'Q -> P' },
  { label: 'Modus ponens (valid)', premises: ['P -> Q', 'P'], conclusion: 'Q' },
  { label: 'Modus tollens (valid)', premises: ['P -> Q', '~Q'], conclusion: '~P' },
  { label: 'Hypothetical syllogism (valid)', premises: ['P -> Q', 'Q -> R'], conclusion: 'P -> R' },
];
