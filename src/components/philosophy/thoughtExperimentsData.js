// Thought experiments as small branching trees for REFLECTION. No scores, rankings or right answers: every choice only
// leads to a follow-up question and, sometimes, a note on a thinker whose line of reasoning resembles it.
// echo: {who, school, argued} renders as "This line of reasoning resembles the view of {who} ({school}), who argued {argued}."
// Attributions are deliberately broad summaries; scholars disagree about the details.
const e = (who, school, argued) => ({ who, school, argued });

export const THOUGHT_EXPERIMENTS = [
  {
    id: 'trolley', title: 'The trolley problem', origin: 'Philippa Foot (1967); Judith Jarvis Thomson (1976)',
    setup: 'A runaway trolley will kill five people on the track ahead. You can do something about it, but every option has a cost.',
    root: 'lever',
    nodes: {
      lever: {
        prompt: 'You stand beside a lever. Pulling it sends the trolley onto a side track where it will kill one person instead of five. Do you pull it?',
        choices: [
          { label: 'Pull the lever', next: 'bridge', echo: e('Jeremy Bentham and John Stuart Mill', 'utilitarianism', 'that the right act is the one that brings about the most good overall') },
          { label: 'Leave the lever alone', next: 'bridge', echo: e('Philippa Foot', 'deontology-influenced ethics', 'that there is a moral difference between doing harm and allowing harm, with a stronger duty not to harm') },
          { label: 'I am not sure what the difference between those options is', next: 'bridge', echo: null },
        ],
      },
      bridge: {
        prompt: 'Now you stand on a bridge above the track. The only way to stop the trolley is to push a stranger off the bridge into its path. Do you push?',
        choices: [
          { label: 'Push the stranger', next: 'compare', echo: e('act utilitarians', 'consequentialism', 'that outcomes alone settle what we ought to do, so how the one person is affected does not change the count') },
          { label: 'Do not push', next: 'compare', echo: e('Immanuel Kant', 'deontology', 'that persons must never be treated merely as a means to an end, however good the result') },
        ],
      },
      compare: {
        prompt: 'If your two answers differ, what could explain it? If they match, what would you say to someone whose answers differ?',
        choices: [
          { label: 'Using someone as a means is different from harming them as a side effect', next: 'end', echo: e('Thomas Aquinas and later natural-law writers', 'the doctrine of double effect', 'that it can matter whether harm is intended as a means or merely foreseen') },
          { label: 'Pushing someone is more personal and direct than pulling a lever', next: 'end', echo: e('Judith Jarvis Thomson', 'contemporary moral philosophy', 'that the lever and the bridge cases differ, and asked what principle could account for the difference') },
          { label: 'My answers should not differ; I would revise one of them', next: 'end', echo: e('John Rawls', 'the method of reflective equilibrium', 'that we adjust our principles and our particular judgments against each other until they fit') },
        ],
      },
      end: {
        prompt: 'You have followed one path through the cases.',
        reflect: ['Which of your answers did you feel most sure of, and did that feeling come from a principle or from a picture?', 'What would a person who answered the opposite way say is missing from your view?', 'Does the doing/allowing distinction hold outside this story, for instance in medicine?'],
      },
    },
  },
  {
    id: 'experience-machine', title: 'The experience machine', origin: 'Robert Nozick, Anarchy, State, and Utopia (1974)',
    setup: 'Scientists can connect you to a machine that gives you any experiences you choose, from now on, and while connected you will believe it is real.',
    root: 'plug',
    nodes: {
      plug: {
        prompt: 'You may plug in for life, with a life full of the experiences you most want. Do you?',
        choices: [
          { label: 'Plug in', next: 'why', echo: e('Epicurus and the later hedonists', 'hedonism', 'that pleasant experience is the good, and that what else matters is only a route to it') },
          { label: 'Stay out', next: 'why', echo: e('Robert Nozick', 'the critique of hedonism', 'that people care about doing and being certain things, not only about how their lives feel from the inside') },
        ],
      },
      why: {
        prompt: 'What mostly decides it for you?',
        choices: [
          { label: 'Contact with real people I care about', next: 'status', echo: e('Aristotle', 'virtue ethics', 'that friendship is among the most necessary goods of a life, and is a matter of actually acting together') },
          { label: 'Actually achieving things, not just feeling that I did', next: 'status', echo: e('Aristotle', 'virtue ethics', 'that a good life (eudaimonia) is an activity of the whole life and not only a state of feeling') },
          { label: 'Being a certain kind of person', next: 'status', echo: e('Robert Nozick', 'the critique of hedonism', 'that we want to be a certain way as well as to feel a certain way') },
          { label: 'Nothing but the quality of the experience', next: 'status', echo: e('Jeremy Bentham', 'hedonistic utilitarianism', 'that the value of a life is the balance of its pleasure and pain') },
        ],
      },
      status: {
        prompt: 'Suppose you were told you are already in such a machine, and may leave to a harder, real life. Would your answer change?',
        choices: [
          { label: 'Yes, I would stay in', next: 'end', echo: null },
          { label: 'No, I would leave', next: 'end', echo: null },
          { label: 'I wonder whether my first answer was about the choice or about change itself', next: 'end', echo: e('Felipe De Brigard', 'experimental philosophy', 'that reluctance to plug in may partly reflect a preference for how things currently are, and tested this by reversing the setup') },
        ],
      },
      end: {
        prompt: 'You have followed one path through the case.',
        reflect: ['Is there something you value that no experience could replace? How would you tell the difference?', 'Would your answer change if the machine were only for a year?', 'What would a hedonist say you are really valuing?'],
      },
    },
  },
  {
    id: 'ship-of-theseus', title: 'The ship of Theseus', origin: 'Plutarch, Life of Theseus; discussed by Thomas Hobbes and John Locke',
    setup: 'Over many years every plank of a ship is replaced with a new one, one at a time, until none of the original wood remains.',
    root: 'same',
    nodes: {
      same: {
        prompt: 'Is it still the same ship?',
        choices: [
          { label: 'Yes: it kept its form and its role through gradual change', next: 'rebuilt', echo: e('John Locke', 'the continuity view of identity', 'that the identity of a living thing or organised whole lies in its continued organisation, not in the same matter') },
          { label: 'No: without the original parts it is a different ship', next: 'rebuilt', echo: e('Thomas Hobbes', 'the view that identity follows matter', 'about this very puzzle, treating the original parts as one candidate for what makes it the same') },
          { label: 'It depends on what we are asking', next: 'rebuilt', echo: e('Peter Geach', 'relative identity', 'that "the same" always needs a sortal, such as "the same ship" or "the same lot of planks"') },
        ],
      },
      rebuilt: {
        prompt: 'Now suppose someone gathered the discarded planks and reassembled them into a ship. Which one is the original?',
        choices: [
          { label: 'The repaired ship', next: 'person', echo: null },
          { label: 'The reassembled ship', next: 'person', echo: e('Thomas Hobbes', 'the view that identity follows matter', 'that the reassembled ship has a good claim to be the original, which makes the puzzle sharper') },
          { label: 'Neither, or both in different senses', next: 'person', echo: null },
        ],
      },
      person: {
        prompt: 'Your body replaces most of its cells over the years. What makes you the same person as the child you were?',
        choices: [
          { label: 'Memory and psychological connection', next: 'end', echo: e('John Locke', 'psychological continuity', 'in his Essay that personal identity consists in consciousness reaching back through memory') },
          { label: 'Being the same living organism', next: 'end', echo: e('Eric Olson and other animalists', 'animalism', 'that we are animals and persist as long as the organism does') },
          { label: 'Perhaps there is no deep fact: what matters is continuity', next: 'end', echo: e('David Hume and Derek Parfit', 'reductionism about the self', 'that the self is a bundle of connected experiences, and that what matters in survival is connection and continuity rather than strict identity') },
        ],
      },
      end: {
        prompt: 'You have followed one path through the cases.',
        reflect: ['Which kinds of change would you say destroy a thing and which only alter it?', 'Does the answer change for a club, a river or a city?', 'Do you want the same answer for ships and for persons? Why?'],
      },
    },
  },
  {
    id: 'chinese-room', title: 'The Chinese room', origin: 'John Searle, "Minds, Brains, and Programs" (1980)',
    setup: 'A person who knows no Chinese sits in a room with a rulebook for matching Chinese symbols to other Chinese symbols. Notes pass in and out, and from outside the answers look fluent.',
    root: 'person',
    nodes: {
      person: {
        prompt: 'Does the person in the room understand Chinese?',
        choices: [
          { label: 'No: following rules is not understanding', next: 'system', echo: e('John Searle', 'the argument against strong AI', 'that manipulating symbols by their shape (syntax) is not enough for meaning (semantics)') },
          { label: 'The person does not, but the room as a whole might', next: 'system', echo: e('critics who offered the systems reply', 'functionalism', 'that understanding belongs to the whole system and not to the part, a reply Searle discusses in his paper') },
          { label: 'If the behaviour is the same, nothing more is needed', next: 'system', echo: e('Alan Turing', 'the imitation game', 'that "can machines think?" is better asked through whether a machine can be told apart from a human in conversation') },
        ],
      },
      system: {
        prompt: 'Now put the same program in a robot with cameras and limbs that interacts with the world. Does that change anything?',
        choices: [
          { label: 'Yes: contact with the world might matter for meaning', next: 'end', echo: e('critics who offered the robot reply', 'embodied accounts of meaning', 'that connecting symbols to perception and action could supply what symbols alone lack, a reply Searle also discusses') },
          { label: 'No: the robot is still moving symbols', next: 'end', echo: e('John Searle', 'the argument against strong AI', 'that adding sensors only adds more symbols for the program to manipulate') },
          { label: 'I am not sure what "understanding" means here', next: 'end', echo: e('Daniel Dennett', 'philosophy of mind', 'that the thought experiment works as an intuition pump, and that its force depends on how we imagine the details') },
        ],
      },
      end: {
        prompt: 'You have followed one path through the case.',
        reflect: ['What would count as evidence that something understands, for a person, an animal or a program?', 'Is there a difference between simulating a storm and a storm? Does the same apply to understanding?', 'What picture of the room did you imagine, and does the answer survive changing it?'],
      },
    },
  },
  {
    id: 'veil-of-ignorance', title: 'The veil of ignorance', origin: 'John Rawls, A Theory of Justice (1971)',
    setup: 'You help choose the basic rules of a society, but you do not know which place in it you will have: your wealth, talents, background or beliefs.',
    root: 'rules',
    nodes: {
      rules: {
        prompt: 'What rule would you most want to be sure of?',
        choices: [
          { label: 'A decent minimum for the worst-off position', next: 'knowing', echo: e('John Rawls', 'justice as fairness', 'that parties behind the veil would arrange inequalities to work to the advantage of the least well-off (the difference principle)') },
          { label: 'The highest average well-being, even if some do badly', next: 'knowing', echo: e('John Harsanyi', 'utilitarianism', 'that rational choosers who do not know their place would maximise expected, or average, well-being') },
          { label: 'Equal basic liberties for everyone before anything else', next: 'knowing', echo: e('John Rawls', 'justice as fairness', 'that equal basic liberties come first and should not be traded for economic gains') },
        ],
      },
      knowing: {
        prompt: 'Suppose you did know your talents and background. Would you choose differently?',
        choices: [
          { label: 'Yes, I would favour rules that help people like me', next: 'limits', echo: e('John Rawls', 'justice as fairness', 'that this is the reason for the veil: it removes this pull of self-interest from fair terms') },
          { label: 'No, fairness should not depend on where I stand', next: 'limits', echo: e('Immanuel Kant', 'moral philosophy', 'that moral principles must be ones every rational person could accept, an idea Rawls says he draws on') },
        ],
      },
      limits: {
        prompt: 'Who should be behind the veil: only today\'s citizens, or also future generations, or other animals?',
        choices: [
          { label: 'Include future generations', next: 'end', echo: e('John Rawls', 'justice as fairness', 'that each generation has duties of a just savings principle to those who come after') },
          { label: 'Include animals', next: 'end', echo: e('Martha Nussbaum', 'the capabilities approach', 'that a theory of justice should extend to non-human animals, a point on which she criticises contract views') },
          { label: 'Only those who can take part in making the agreement', next: 'end', echo: e('social contract theorists', 'contractualism', 'that justice is what free and equal persons could agree to, which limits who counts as a party') },
        ],
      },
      end: {
        prompt: 'You have followed one path through the case.',
        reflect: ['Which of your own advantages did you picture when the veil lifted?', 'Is choosing in ignorance a good way to find fair rules, or does it hide something important about us?', 'What does your answer assume about attitudes to risk?'],
      },
    },
  },
  {
    id: 'ring-of-gyges', title: 'The ring of Gyges', origin: 'Plato, Republic II (359a-360d), Glaucon\'s challenge',
    setup: 'A shepherd finds a ring that makes him invisible. In the story Glaucon tells, he uses it to do whatever he wants without being seen.',
    root: 'ring',
    nodes: {
      ring: {
        prompt: 'You find the ring. No one could ever know what you do. What would you do?',
        choices: [
          { label: 'Behave as I do now', next: 'why', echo: e('Socrates (as Plato writes him)', 'Platonic ethics', 'that justice is good for the soul of the just person, whether or not anyone sees') },
          { label: 'Take what I want', next: 'why', echo: e('Glaucon', 'the challenge in the Republic', 'as a test and not as his own belief, that people are just only because they fear punishment or loss of reputation') },
          { label: 'It depends on what I wanted', next: 'why', echo: null },
        ],
      },
      why: {
        prompt: 'When people can see you, what mainly keeps you acting as you do?',
        choices: [
          { label: 'Fear of punishment or of losing my reputation', next: 'end', echo: e('Thomas Hobbes', 'social contract theory', 'that rules of justice arise from agreement for mutual security and are kept up by enforcement') },
          { label: 'Some acts are wrong whether or not anyone finds out', next: 'end', echo: e('Immanuel Kant', 'deontology', 'that moral worth comes from acting out of duty, not from consequences or reputation') },
          { label: 'It makes me the kind of person I want to be', next: 'end', echo: e('Aristotle', 'virtue ethics', 'that we become good by acting well, and that virtue is part of a flourishing life') },
        ],
      },
      end: {
        prompt: 'You have followed one path through the case.',
        reflect: ['Is acting well only when watched the same as acting well?', 'Would having the ring change who you are, or only what you can get away with?', 'What would the ring show about a person whose conduct you admire?'],
      },
    },
  },
];
