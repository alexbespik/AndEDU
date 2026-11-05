import React, { useState, useEffect } from 'react';
import {
  FileText,
  Search,
  BookOpen,
  CheckCircle2,
  HelpCircle,
  Sparkles,
  Info,
  ChevronRight,
  Eye,
  MessageSquare,
  Compass,
  Layers,
  ArrowRight
} from 'lucide-react';
import { reportXp } from '../lib/engage';

export const BUILTIN_DOCUMENTS = [
  {
    id: 'magna-carta-1215',
    title: 'Magna Carta (1215), Clause 39',
    subtitle: 'The Great Charter of English Liberties',
    author: 'King John of England & The 25 Rebel Barons',
    date: 'June 15, 1215',
    location: 'Runnymede meadow near Windsor, England',
    language: 'Medieval Latin',
    significance: 'Bedrock origin of statutory due process, habeas corpus, and trial by peers in Anglo-American jurisprudence.',
    paragraphs: [
      {
        text: 'No free man shall be seized or imprisoned, or stripped of his rights or possessions, or outlawed or exiled, or deprived of his standing in any way, nor will we proceed with force against him, or send others to do so, except by the lawful judgment of his equals or by the law of the land.',
        annotationKeys: ['free-man', 'stripped-possessions', 'force-against-him', 'lawful-judgment', 'law-of-land'],
      },
    ],
    annotations: {
      'free-man': {
        target: 'No free man',
        type: 'context',
        title: 'Who was a "Free Man" (Liber Homo)?',
        note: 'In 1215 England, "free men" represented only roughly 10% to 20% of the population — primarily feudal barons, knights, and burgesses. The vast majority were unfree villeins (serfs) bound to manorial land, who possessed no legal standing under this clause.',
      },
      'stripped-possessions': {
        target: 'stripped of his rights or possessions',
        type: 'archaic',
        title: 'Disseisin in Feudal Law',
        note: 'The original Latin is "disseisiatur" (disseised). Under King John, the Crown arbitrarily confiscated baronial castles, ancestral manors, and inheritances whenever a lord balked at excessive feudal dues (scutage).',
      },
      'force-against-him': {
        target: 'nor will we proceed with force against him',
        type: 'bias',
        title: 'Restraining Royal Mercenary Warfare',
        note: 'King John routinely employed ruthless foreign mercenary companies (led by captains like Fawkes de Breauté) to besiege and burn castles of recalcitrant nobles without judicial summons. The clause explicitly forbids armed executive force prior to judgment.',
      },
      'lawful-judgment': {
        target: 'lawful judgment of his equals',
        type: 'bias',
        title: 'Judicium Parium (Trial by Peers)',
        note: 'The rebel barons were not inventing trial by jury for commoners. Rather, they demanded that the King could not send royal judges to condemn high nobles; only fellow earls and barons could judge their feudal crimes.',
      },
      'law-of-land': {
        target: 'law of the land',
        type: 'context',
        title: 'Per Legem Terrae & Due Process',
        note: 'In 1354, King Edward III’s Parliament statutory translation rendered "legem terrae" as "due process of law." This exact phrasing was later incorporated directly into the Fifth and Fourteenth Amendments to the United States Constitution.',
      },
    },
    shegSteps: [
      {
        step: 1,
        name: 'Sourcing',
        subtitle: 'Who created this, when, and for what purpose?',
        question: 'Who drafted Clause 39, and what immediate crisis forced King John to grant it at Runnymede?',
        hint: 'Consider the military situation of the rebel barons and King John after the Battle of Bouvines (1214).',
        modelAnswer: 'The clause was forced upon King John by an armed confederation of rebel barons led by Robert Fitzwalter. After John suffered disastrous military defeat in Normandy and extorted illegal taxes to fund the war, the barons captured London and compelled John to affix his Great Seal to prevent civil war.',
      },
      {
        step: 2,
        name: 'Contextualization',
        subtitle: 'How did the historical environment shape the document?',
        question: 'Why did the barons insist on limiting judicial decisions to "the lawful judgment of his equals"?',
        hint: 'Reflect on how King John had used royal courts to punish political rivals.',
        modelAnswer: 'John had corrupted royal courts by auctioning judicial writs to the highest bidder ("selling justice") and using compliant crown judges to seize estates of political rivals. Demanding judgment by social equals prevented the monarch from weaponizing the judiciary.',
      },
      {
        step: 3,
        name: 'Corroboration',
        subtitle: 'Comparing this with other historical accounts',
        question: 'How does Clause 39 corroborate the earlier Coronation Charter of Henry I (1100)?',
        hint: 'Henry I had promised to end unlawful exactions; what made Magna Carta different?',
        modelAnswer: 'Both documents list identical baronial grievances regarding abusive royal taxation and arbitrary confiscations. However, Magna Carta went further by creating an explicit enforcement council of 25 barons (Clause 61) authorized to seize royal property if the King violated the charter.',
      },
      {
        step: 4,
        name: 'Close Reading',
        subtitle: 'Analyzing specific words, phrasing, and rhetorical claims',
        question: 'Why is the phrase "or in any way destroyed" (or deprived of his standing) phrased so expansively?',
        hint: 'Look at the sequence of verbs: seized, imprisoned, stripped, outlawed, exiled, deprived.',
        modelAnswer: 'The comprehensive catalogue of legal penalties was designed to close every legal loophole. The barons anticipated that an autocratic king might avoid outright imprisonment while still destroying a rival through outlawry, confiscation of goods, or banishment.',
      },
    ],
  },
  {
    id: 'hammurabi-code',
    title: 'The Code of Hammurabi (c. 1750 BCE)',
    subtitle: 'Laws 196–200: Lex Talionis and Social Stratification',
    author: 'Hammurabi, King of the Babylonian Empire',
    date: 'c. 1750 BCE',
    location: 'Babylon (Mesopotamia) — inscribed on black diorite stele',
    language: 'Akkadian (cuneiform)',
    significance: 'Earliest surviving comprehensive legal code, demonstrating the emergence of written statutory law and class hierarchy.',
    paragraphs: [
      {
        text: '196. If a nobleman has destroyed the eye of a member of the aristocracy, they shall destroy his eye.',
        annotationKeys: ['aristocracy', 'eye-for-eye'],
      },
      {
        text: '197. If he has broken a nobleman’s bone, they shall break his bone.',
        annotationKeys: ['broken-bone'],
      },
      {
        text: '198. If he has destroyed the eye of a commoner or broken the bone of a commoner, he shall pay one mina of silver.',
        annotationKeys: ['commoner-fine'],
      },
      {
        text: '199. If he has destroyed the eye of a nobleman’s slave or broken the bone of a nobleman’s slave, he shall pay half the slave’s purchase value.',
        annotationKeys: ['slave-value'],
      },
      {
        text: '200. If a man has knocked out the teeth of a man of his own rank, they shall knock out his teeth.',
        annotationKeys: ['teeth-equal'],
      },
    ],
    annotations: {
      aristocracy: {
        target: 'member of the aristocracy',
        type: 'context',
        title: 'The Awilu Class (Patricians)',
        note: 'Babylonian society was legally segmented into three distinct castes: the "awilu" (free upper-class nobles and landowners), "mushkenu" (free commoners), and "wardu" (chattel slaves). Legal rights were completely dependent on social rank.',
      },
      'eye-for-eye': {
        target: 'destroy his eye',
        type: 'archaic',
        title: 'Lex Talionis (Law of Retaliation)',
        note: 'The principle of exact proportional physical retribution. Far from being primitive barbarism, Hammurabi framed this as judicial modernization: it capped feuds by preventing a victim’s family from killing the offender, limiting punishment strictly to the injury suffered.',
      },
      'broken-bone': {
        target: 'break his bone',
        type: 'archaic',
        title: 'Mirroring Penalties Among Equals',
        note: 'Physical symmetry in punishments applied exclusively when both the perpetrator and the victim belonged to the same social stratum (awilu vs awilu).',
      },
      'commoner-fine': {
        target: 'pay one mina of silver',
        type: 'context',
        title: 'The Mushkenu (Commoners) and Fines',
        note: 'A commoner’s body was not protected by physical retaliation. If an aristocrat blinded a commoner, no eye was destroyed; instead, the nobleman paid a financial fine (60 shekels/1 mina of silver), treating the commoner’s injury as economic damage.',
      },
      'slave-value': {
        target: 'half the slave’s purchase value',
        type: 'bias',
        title: 'The Wardu (Enslaved Persons) as Chattel',
        note: 'Under Babylonian law, slaves had no personal bodily integrity. The payment was not made to the injured slave, but to the slave’s owner to compensate for the diminished market and labor value of the property.',
      },
      'teeth-equal': {
        target: 'man of his own rank',
        type: 'bias',
        title: 'Strict Caste Equality Verification',
        note: 'Law 200 explicitly specifies "a man of his own rank." If a man struck the tooth of an elder or superior, Law 202 mandated sixty strikes with an ox-whip in public assembly.',
      },
    },
    shegSteps: [
      {
        step: 1,
        name: 'Sourcing',
        subtitle: 'Author, perspective, and authority',
        question: 'How does King Hammurabi justify his legal code in the monument’s prologue?',
        hint: 'Notice the top carving depicting Shamash, the sun god and patron of justice.',
        modelAnswer: 'Hammurabi claims divine mandate: the monument’s relief shows Shamash handing Hammurabi the scepter and ring of kingly law. Hammurabi presents himself as the shepherd appointed by the gods "to bring about the rule of righteousness in the land and prevent the strong from oppressing the weak."',
      },
      {
        step: 2,
        name: 'Contextualization',
        subtitle: 'Social structure of Bronze Age Mesopotamia',
        question: 'What do Laws 196–199 reveal about social equality in 18th-century BCE Babylonia?',
        hint: 'Compare the consequences for injuring an aristocrat vs a commoner vs a slave.',
        modelAnswer: 'They demonstrate that Babylonian justice was explicitly unequal and hierarchically stratified. Retaliation in kind ("lex talionis") applied only within the elite awilu class; harm to commoners was resolved with financial fines, and harm to slaves was reimbursed to the slave’s owner as property damage.',
      },
      {
        step: 3,
        name: 'Corroboration',
        subtitle: 'Comparing ancient legal systems',
        question: 'How do Laws 196–200 compare with the Mosaic Law recorded in the Book of Exodus (Exodus 21:23–25)?',
        hint: 'Exodus also states "eye for eye, tooth for tooth"; consider differences in class distinctions.',
        modelAnswer: 'Both codes employ the exact formulation of lex talionis ("eye for eye, tooth for tooth"). However, the Mosaic code applied physical penalties across classes without distinguishing between aristocrats and commoners, although both systems permitted slavery.',
      },
      {
        step: 4,
        name: 'Close Reading',
        subtitle: 'Linguistic patterns and legal certainty',
        question: 'Notice the conditional "If... then..." (casuistic) structure of every law. Why did Mesopotamian scribes use this structure?',
        hint: 'Think about how judges in local city courts would consult the stele.',
        modelAnswer: 'Casuistic legal formulation ("If a person commits X, then Y shall be done") established predictable, standardized case law. By inscribing clear cause-and-effect penalties in stone in public city squares, the code reduced arbitrary verdicts by local village elders.',
      },
    ],
  },
  {
    id: 'rights-of-man-1789',
    title: 'Declaration of the Rights of Man and of the Citizen (1789)',
    subtitle: 'The Ideological Manifesto of the French Revolution',
    author: 'National Constituent Assembly of France (Marquis de Lafayette with Thomas Jefferson)',
    date: 'August 26, 1789',
    location: 'Versailles / Paris, France',
    language: 'French',
    significance: 'Universalized the Enlightenment principles of civil equality, individual liberty, popular sovereignty, and rule of law.',
    paragraphs: [
      {
        text: 'Article 1. Men are born and remain free and equal in rights. Social distinctions may be founded only upon the general good.',
        annotationKeys: ['born-equal', 'general-good'],
      },
      {
        text: 'Article 2. The aim of all political association is the preservation of the natural and imprescriptible rights of man. These rights are liberty, property, security, and resistance to oppression.',
        annotationKeys: ['natural-rights', 'resistance-oppression'],
      },
      {
        text: 'Article 3. The principle of all sovereignty resides essentially in the nation. No body nor individual may exercise any authority which does not proceed directly from the nation.',
        annotationKeys: ['sovereignty-nation'],
      },
      {
        text: 'Article 6. Law is the expression of the general will. Every citizen has a right to participate personally, or through his representative, in its foundation. It must be the same for all, whether it protects or punishes.',
        annotationKeys: ['general-will', 'same-for-all'],
      },
    ],
    annotations: {
      'born-equal': {
        target: 'Men are born and remain free and equal in rights',
        type: 'context',
        title: 'Abolition of Feudal Estates',
        note: 'This was an explosive rejection of the Ancien Régime’s Three Estates. Prior to 1789, French aristocrats and higher clergy held hereditary tax exemptions, monopoly on military commissions, and separate lordly courts.',
      },
      'general-good': {
        target: 'Social distinctions may be founded only upon the general good',
        type: 'bias',
        title: 'Meritocracy vs Hereditary Privilege',
        note: 'Does not mandate economic equality, but establishes that social differences must be justified by utility to the public (e.g. holding public office through merit) rather than inherited bloodlines.',
      },
      'natural-rights': {
        target: 'natural and imprescriptible rights of man',
        type: 'context',
        title: 'Lockean Natural Rights Philosophy',
        note: 'Rights are not gifts granted by the Crown (as in Magna Carta); they are inherent in human nature and cannot be taken away or surrendered ("imprescriptible").',
      },
      'resistance-oppression': {
        target: 'resistance to oppression',
        type: 'context',
        title: 'Legitimizing the Bastille Uprising',
        note: 'Drafted just weeks after the storming of the Bastille (July 14, 1789). By defining resistance to tyranny as a sacred natural right, the Assembly retroactively legitimized the armed insurrection of the Parisian populace.',
      },
      'sovereignty-nation': {
        target: 'sovereignty resides essentially in the nation',
        type: 'archaic',
        title: 'Overthrow of Divine Right Absolutism',
        note: 'Louis XVI claimed to rule as God’s direct representative on earth. Article 3 shifted absolute sovereignty from the physical person of the monarch to the abstract collective body of "the nation."',
      },
      'general-will': {
        target: 'expression of the general will',
        type: 'archaic',
        title: 'Rousseau’s Volonté Générale',
        note: 'Directly cites Jean-Jacques Rousseau’s Social Contract (1762): law must reflect the common collective interest of the whole society rather than the private wills of factions or monarchs.',
      },
      'same-for-all': {
        target: 'must be the same for all',
        type: 'bias',
        title: 'Equality Before Criminal Law',
        note: 'Under the old regime, nobles convicted of murder were beheaded by sword, whereas commoners were brutally broken on the wheel or hanged. This clause mandated identical judicial processes and penalties.',
      },
    },
    shegSteps: [
      {
        step: 1,
        name: 'Sourcing',
        subtitle: 'Authorship, allies, and revolutionary context',
        question: 'Who drafted the initial version of this Declaration, and who advised him on its philosophy?',
        hint: 'Consider the French hero of the American Revolution and his American diplomat friend in Paris.',
        modelAnswer: 'The Marquis de Lafayette drafted the initial text, consulting closely with his close friend Thomas Jefferson, who was serving as United States Minister to France. Lafayette was inspired directly by the Virginia Declaration of Rights (1776).',
      },
      {
        step: 2,
        name: 'Contextualization',
        subtitle: 'Summer of 1789 and the Great Fear',
        question: 'What events in France during July and August 1789 forced the Assembly to issue this declaration so quickly?',
        hint: 'Think about peasant revolts in the countryside and the storming of the Bastille.',
        modelAnswer: 'The storming of the Bastille on July 14 and the widespread peasant uprisings ("The Great Fear") across the countryside, where peasants burned manorial rolls, created acute panic. The Assembly needed an authoritative philosophical statement to stabilize the revolution and formalize the abolition of feudalism (Night of August 4).',
      },
      {
        step: 3,
        name: 'Corroboration',
        subtitle: 'Comparing with the US Declaration of Independence',
        question: 'How does Article 2 compare with the "Life, Liberty and the pursuit of Happiness" in the 1776 American Declaration?',
        hint: 'Note what word replaced "pursuit of Happiness".',
        modelAnswer: 'While Jefferson wrote "Life, Liberty and the pursuit of Happiness", the French Declaration reverted to John Locke’s classical triad: "liberty, property, security, and resistance to oppression." French bourgeois deputies were especially anxious to safeguard private property against radical agrarian leveling.',
      },
      {
        step: 4,
        name: 'Close Reading',
        subtitle: 'Who was included, and who was omitted?',
        question: 'How did Olympe de Gouges in 1791 challenge the universal claims of the word "Men" (les hommes)?',
        hint: 'Did the Declaration grant political voting rights to women or enslaved people in French colonies?',
        modelAnswer: 'De Gouges published the "Declaration of the Rights of Woman and of the Female Citizen" (1791), demonstrating that "men" in practice meant biological males with property. Women, unpropertied "passive citizens," and enslaved people in Saint-Domingue (Haiti) were initially excluded from the franchise and civil rights.',
      },
    ],
  },
  {
    id: 'douglass-fourth-july',
    title: 'Frederick Douglass: "What to the Slave Is the Fourth of July?" (1852)',
    subtitle: 'The Rochester Anti-Slavery Address',
    author: 'Frederick Douglass',
    date: 'July 5, 1852',
    location: 'Corinthian Hall, Rochester, New York',
    language: 'English',
    significance: 'Arguably the greatest abolitionist oration in American history, exposing the moral hypocrisy of celebrating liberty in a slave-holding republic.',
    paragraphs: [
      {
        text: 'Fellow-citizens, pardon me, allow me to ask, why am I called upon to speak here today? What have I, or those I represent, to do with your national independence? Are the great principles of political freedom and of natural justice, embodied in that Declaration of Independence, extended to us?',
        annotationKeys: ['your-independence', 'extended-to-us'],
      },
      {
        text: 'What, to the American slave, is your 4th of July? I answer; a day that reveals to him, more than all other days in the year, the gross injustice and cruelty to which he is the constant victim. To him, your celebration is a sham; your boasted liberty, an unholy license; your national greatness, swelling vanity; your sounds of rejoicing are empty and heartless; your denunciations of tyrants, brass fronted impudence; your shouts of liberty and equality, hollow mockery; your prayers and hymns, your sermons and thanksgivings, with all your religious parade and solemnity, are, to Him, mere bombast, fraud, deception, impiety, and hypocrisy — a thin veil to cover up crimes which would disgrace a nation of savages.',
        annotationKeys: ['sham-liberty', 'hollow-mockery', 'religious-parade', 'crimes-savages'],
      },
    ],
    annotations: {
      'your-independence': {
        target: 'your national independence',
        type: 'bias',
        title: 'The Rhetorical Strategy of "Your" vs "Our"',
        note: 'Douglass pointedly uses the second-person pronoun "your" instead of "our". By refusing to falsely include himself and four million enslaved African Americans in the celebratory patriotic narrative, he forces the white audience to confront their separate, unequal realities.',
      },
      'extended-to-us': {
        target: 'extended to us',
        type: 'context',
        title: 'The Fugitive Slave Act of 1850',
        note: 'Delivered two years after the Compromise of 1850. The federal Fugitive Slave Law commanded Northern marshals and citizens to capture escaped slaves without jury trial or testimony, denying fundamental constitutional protections to all Black Americans in free states.',
      },
      'sham-liberty': {
        target: 'your celebration is a sham; your boasted liberty, an unholy license',
        type: 'archaic',
        title: 'Prophetic Antithesis & Scorching Irony',
        note: 'Douglass deliberately adopts the cadence of Old Testament prophets (like Isaiah or Jeremiah), balancing paired opposites: celebration/sham, liberty/unholy license. Douglass declared: "At a time like this, scorching irony, not convincing argument, is needed."',
      },
      'hollow-mockery': {
        target: 'shouts of liberty and equality, hollow mockery',
        type: 'bias',
        title: 'Exposing American Cognitive Dissonance',
        note: 'American politicians routinely gave Fourth of July speeches boasting of America as the asylum of the oppressed while maintaining the largest internal domestic slave market in the Western hemisphere.',
      },
      'religious-parade': {
        target: 'prayers and hymns, your sermons and thanksgivings',
        type: 'context',
        title: 'Indictment of Northern Church Complicity',
        note: 'Douglass reserves his fiercest outrage for mainstream Christian denominations that used biblical passages to sanction slaveholding and refused to support abolitionist fugitive aid.',
      },
      'crimes-savages': {
        target: 'disgrace a nation of savages',
        type: 'archaic',
        title: 'Inverting the "Civilization" Trope',
        note: 'Southern apologists defended chattel slavery as a paternalistic institution bringing Christian "civilization" to Africans. Douglass flips this trope completely, demonstrating that American slave auctions and lashings represent barbaric brutality.',
      },
    },
    shegSteps: [
      {
        step: 1,
        name: 'Sourcing',
        subtitle: 'Speaker, audience, and the chosen date',
        question: 'Who invited Frederick Douglass to speak, and why did he deliberately deliver the speech on July 5th instead of July 4th?',
        hint: 'Think about what July 4th represented to an escaped slave.',
        modelAnswer: 'Douglass was invited by the Rochester Ladies’ Anti-Slavery Society to an audience of 500-600 white abolitionists. He intentionally chose to speak on July 5th rather than July 4th to emphasize that the Fourth of July was a day of national freedom in which enslaved Americans had no share.',
      },
      {
        step: 2,
        name: 'Contextualization',
        subtitle: 'The antebellum crisis and national expansion of slavery',
        question: 'Why was the abolitionist movement in a state of fury and despair in the summer of 1852?',
        hint: 'Consider the Compromise of 1850 and the trial of fugitive slaves in Boston.',
        modelAnswer: 'The Fugitive Slave Act of 1850 had nationalized slavery: slave catchers roamed Northern cities with federal warrants, and Northern citizens could be fined $1,000 and imprisoned for aiding runaways. For Douglass and free Black Northerners, constitutional liberty was being actively obliterated.',
      },
      {
        step: 3,
        name: 'Corroboration',
        subtitle: 'Douglass’s interpretation of the US Constitution',
        question: 'How did Douglass’s reading of the US Constitution differ from William Lloyd Garrison’s Garrisonian abolitionism?',
        hint: 'Garrison called the Constitution a "covenant with death and an agreement with hell."',
        modelAnswer: 'Garrison believed the US Constitution was inherently pro-slavery and advocated Northern secession ("No Union with Slaveholders"). Douglass broke with Garrison, arguing that properly interpreted, the Constitution is a "GLORIOUS LIBERTY DOCUMENT" containing no mention of slave property.',
      },
      {
        step: 4,
        name: 'Close Reading',
        subtitle: 'Rhetorical accumulation and crescendo',
        question: 'Examine the crescendo of terms: "mere bombast, fraud, deception, impiety, and hypocrisy". How does Douglass’s rhythm build moral authority?',
        hint: 'Trace the progression from intellectual error ("bombast") to moral corruption ("fraud") to spiritual corruption ("impiety, hypocrisy").',
        modelAnswer: 'The rapid succession of five damning nouns elevates the critique from minor political inconsistency to profound spiritual corruption. By placing "impiety" and "hypocrisy" last, he strips away the religious and moral self-satisfaction of antebellum America.',
      },
    ],
  },
];

export default function PrimarySourceLab({ topic, initialDocId }) {
  const allDocs = React.useMemo(() => {
    if (topic?.primary_source && topic.primary_source.id && topic.primary_source.text) {
      const custom = {
        ...topic.primary_source,
        subtitle: topic.primary_source.subtitle || 'Annotated Primary Source Document',
        paragraphs: topic.primary_source.paragraphs || [
          {
            text: topic.primary_source.text,
            annotationKeys: Object.keys(topic.primary_source.annotations || {}),
          },
        ],
        annotations: topic.primary_source.annotations || {},
        shegSteps: topic.primary_source.shegSteps || topic.primary_source.sourcing_questions || [],
      };
      return [custom, ...BUILTIN_DOCUMENTS.filter((d) => d.id !== custom.id)];
    }
    return BUILTIN_DOCUMENTS;
  }, [topic?.primary_source]);

  const [docId, setDocId] = useState(
    initialDocId && allDocs.some((d) => d.id === initialDocId) ? initialDocId : allDocs[0].id
  );

  useEffect(() => {
    if (initialDocId && allDocs.some((d) => d.id === initialDocId)) {
      setDocId(initialDocId);
      setActiveAnnotationKey(null);
      setCurrentShegStep(1);
      setShowAnswers({});
    }
  }, [initialDocId, allDocs]);

  const activeDoc = allDocs.find((d) => d.id === docId) || allDocs[0];
  const [activeAnnotationKey, setActiveAnnotationKey] = useState(null);
  const [currentShegStep, setCurrentShegStep] = useState(1);
  const [studentAnswers, setStudentAnswers] = useState({});
  const [showAnswers, setShowAnswers] = useState({});
  const [completedSteps, setCompletedSteps] = useState({});

  const activeAnnotation = activeAnnotationKey ? activeDoc.annotations[activeAnnotationKey] : null;

  const handleSelectDoc = (id) => {
    setDocId(id);
    setActiveAnnotationKey(null);
    setCurrentShegStep(1);
    setShowAnswers({});
  };

  const handleRevealAnswer = (stepIndex) => {
    setShowAnswers((prev) => ({ ...prev, [stepIndex]: !prev[stepIndex] }));
    if (!completedSteps[`${activeDoc.id}:${stepIndex}`]) {
      setCompletedSteps((prev) => ({ ...prev, [`${activeDoc.id}:${stepIndex}`]: true }));
      reportXp('practice_correct', `primary_source:${activeDoc.id}:step${stepIndex}`);
    }
  };

  const currentStepData = (activeDoc.shegSteps || []).find((s) => s.step === currentShegStep) || activeDoc.shegSteps?.[0];

  return (
    <div className="primary-source-lab" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      {/* Top Document Selector */}
      <div className="panel" style={{ padding: 'var(--space-3)', display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', alignItems: 'center', justifyContent: 'space-between', borderBottom: '2px solid var(--rule)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <FileText size={20} style={{ color: 'var(--accent)' }} aria-hidden="true" />
          <span style={{ fontFamily: 'var(--font-mono, monospace)', fontWeight: 600, fontSize: '0.9rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Primary Source Interrogator (SHEG Framework)
          </span>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-1)' }}>
          {allDocs.map((d) => (
            <button
              key={d.id}
              type="button"
              className={`choice ${docId === d.id ? 'active' : ''}`}
              style={{
                padding: 'var(--space-1) var(--space-3)',
                fontSize: '0.82rem',
                borderRadius: 'var(--radius-sm, 4px)',
                cursor: 'pointer',
                border: docId === d.id ? '2px solid var(--accent)' : '1px solid var(--rule)',
                background: docId === d.id ? 'var(--accent-tint)' : 'var(--surface)',
                color: docId === d.id ? 'var(--accent-hover)' : 'var(--ink)',
                fontWeight: docId === d.id ? 600 : 400,
              }}
              onClick={() => handleSelectDoc(d.id)}
            >
              {d.title.split('(')[0].trim()}
            </button>
          ))}
        </div>
      </div>

      {/* Document Metadata Banner */}
      <div
        className="panel"
        style={{
          padding: 'var(--space-4)',
          background: 'var(--paper)',
          borderLeft: '4px solid var(--gold)',
          borderRadius: 'var(--radius-md, 6px)',
        }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'flex-start', gap: 'var(--space-2)' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.3rem', fontFamily: 'var(--font-heading, serif)' }}>
              {activeDoc.title}
            </h2>
            <div style={{ fontSize: '0.9rem', color: 'var(--gold-text)', fontStyle: 'italic', marginTop: '2px' }}>
              {activeDoc.subtitle}
            </div>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-1)' }}>
            <span className="badge" style={{ fontSize: '0.75rem', background: 'var(--surface)', padding: '2px 8px' }}>
              {activeDoc.date}
            </span>
            <span className="badge" style={{ fontSize: '0.75rem', background: 'var(--surface)', padding: '2px 8px' }}>
              {activeDoc.location}
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-3)', marginTop: 'var(--space-2)', fontSize: '0.84rem', color: 'var(--muted)' }}>
          <div><strong>Author:</strong> {activeDoc.author}</div>
          {activeDoc.language && <div><strong>Original:</strong> {activeDoc.language}</div>}
        </div>

        {activeDoc.significance && (
          <p style={{ margin: 'var(--space-2) 0 0 0', fontSize: '0.85rem', color: 'var(--ink-soft)', lineHeight: 1.45 }}>
            <strong>Historical Significance:</strong> {activeDoc.significance}
          </p>
        )}
      </div>

      {/* Main Grid: Document Reader on Left, SHEG Framework & Annotation Inspector on Right */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 'var(--space-4)' }}>
        {/* Left: Document Reader with interactive annotated text */}
        <div
          className="panel"
          style={{
            padding: 'var(--space-4)',
            background: 'var(--surface)',
            border: '1px solid var(--rule)',
            borderRadius: 'var(--radius-md, 6px)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-3)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--rule)', paddingBottom: 'var(--space-2)' }}>
            <span style={{ fontSize: '0.82rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--muted)' }}>
              Original Historical Text
            </span>
            <span style={{ fontSize: '0.78rem', color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Eye size={13} aria-hidden="true" /> Tap gold highlights to inspect annotations
            </span>
          </div>

          <div style={{ lineHeight: 1.8, fontSize: '0.96rem', color: 'var(--ink)', fontFamily: 'var(--font-reading, serif)' }}>
            {activeDoc.paragraphs.map((p, pIdx) => {
              // Highlight annotated phrases in this paragraph
              let renderedContent = p.text;
              return (
                <p key={pIdx} style={{ margin: '0 0 var(--space-3) 0', position: 'relative' }}>
                  {(() => {
                    // Collect all active annotations for this paragraph
                    const text = p.text;
                    const items = (p.annotationKeys || [])
                      .map((k) => ({ key: k, data: activeDoc.annotations[k] }))
                      .filter((item) => item.data && text.includes(item.data.target));

                    if (!items.length) return text;

                    // Sort annotations by index in text
                    const matches = items
                      .map((item) => ({ ...item, idx: text.indexOf(item.data.target) }))
                      .sort((a, b) => a.idx - b.idx);

                    const parts = [];
                    let cursor = 0;
                    matches.forEach((m) => {
                      if (m.idx < cursor) return; // skip overlapping matches to prevent duplication
                      if (m.idx > cursor) {
                        parts.push(text.slice(cursor, m.idx));
                      }
                      const isSelected = activeAnnotationKey === m.key;
                      parts.push(
                        <button
                          key={m.key}
                          type="button"
                          onClick={() => setActiveAnnotationKey(isSelected ? null : m.key)}
                          style={{
                            background: isSelected ? 'var(--gold)' : 'var(--gold-tint)',
                            color: isSelected ? 'var(--on-gold)' : 'var(--gold-text)',
                            border: '1px solid var(--gold-rule)',
                            borderRadius: '3px',
                            padding: '1px 4px',
                            cursor: 'pointer',
                            fontFamily: 'inherit',
                            fontSize: 'inherit',
                            textDecoration: 'underline dotted var(--gold-rule)',
                            transition: 'all 0.15s ease',
                          }}
                          title={`Click to inspect: ${m.data.title}`}
                        >
                          {m.data.target}
                        </button>
                      );
                      cursor = m.idx + m.data.target.length;
                    });
                    if (cursor < text.length) {
                      parts.push(text.slice(cursor));
                    }
                    return parts;
                  })()}
                </p>
              );
            })}
          </div>

          {/* Annotation Inspector Panel */}
          {activeAnnotation ? (
            <div
              style={{
                marginTop: 'var(--space-2)',
                padding: 'var(--space-3)',
                background: 'var(--gold-tint)',
                border: '1px solid var(--gold-rule)',
                borderRadius: 'var(--radius-sm, 4px)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--space-1)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--gold-text)' }}>
                  Annotation: {activeAnnotation.title}
                </span>
                <span
                  className="badge"
                  style={{
                    fontSize: '0.7rem',
                    textTransform: 'uppercase',
                    background: 'var(--surface)',
                    color: 'var(--ink)',
                  }}
                >
                  {activeAnnotation.type}
                </span>
              </div>
              <p style={{ margin: 0, fontSize: '0.84rem', color: 'var(--ink)', lineHeight: 1.5 }}>
                {activeAnnotation.note}
              </p>
            </div>
          ) : (
            <div style={{ padding: 'var(--space-2)', background: 'var(--sunk)', borderRadius: '4px', fontSize: '0.8rem', color: 'var(--muted)', textAlign: 'center' }}>
              Tap any highlighted phrase above to view historical context, linguistic shifts, and biases.
            </div>
          )}
        </div>

        {/* Right: Stanford History Education Group (SHEG) 4-Step Analytical Framework */}
        <div
          className="panel"
          style={{
            padding: 'var(--space-4)',
            background: 'var(--surface)',
            border: '1px solid var(--rule)',
            borderRadius: 'var(--radius-md, 6px)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-3)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--rule)', paddingBottom: 'var(--space-2)' }}>
            <span style={{ fontSize: '0.82rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--accent)' }}>
              Stanford SHEG 4-Step Framework
            </span>
            <span style={{ fontSize: '0.78rem', color: 'var(--muted)' }}>
              Historical Thinking Protocol
            </span>
          </div>

          {/* Stepper Buttons */}
          <div style={{ display: 'flex', gap: '4px', overflowX: 'auto', paddingBottom: '4px' }}>
            {(activeDoc.shegSteps || []).map((s) => {
              const isActive = currentShegStep === s.step;
              const isDone = completedSteps[`${activeDoc.id}:${s.step}`];
              return (
                <button
                  key={s.step}
                  type="button"
                  style={{
                    flex: 1,
                    minWidth: '70px',
                    padding: '6px 4px',
                    fontSize: '0.78rem',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    border: isActive ? '2px solid var(--accent)' : '1px solid var(--rule)',
                    background: isActive ? 'var(--accent-tint)' : isDone ? 'var(--ok-tint)' : 'var(--paper)',
                    color: isActive ? 'var(--accent-hover)' : isDone ? 'var(--ok-ink)' : 'var(--ink)',
                    fontWeight: isActive ? 600 : 400,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '2px',
                  }}
                  onClick={() => setCurrentShegStep(s.step)}
                >
                  <span style={{ fontFamily: 'var(--font-mono, monospace)', fontSize: '0.7rem' }}>
                    Step {s.step}
                  </span>
                  <span>{s.name}</span>
                </button>
              );
            })}
          </div>

          {/* Current Step Content */}
          {currentStepData && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
              <div>
                <h4 style={{ margin: 0, fontSize: '0.95rem', color: 'var(--ink)' }}>
                  Step {currentStepData.step}: {currentStepData.name}
                </h4>
                <div style={{ fontSize: '0.8rem', color: 'var(--muted)', marginTop: '2px' }}>
                  {currentStepData.subtitle}
                </div>
              </div>

              {/* Guided Analytical Question */}
              <div style={{ padding: 'var(--space-3)', background: 'var(--paper)', borderRadius: '6px', border: '1px solid var(--rule)' }}>
                <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--accent)', marginBottom: '4px' }}>
                  Guided Question:
                </div>
                <div style={{ fontSize: '0.9rem', color: 'var(--ink)', lineHeight: 1.45 }}>
                  {currentStepData.question}
                </div>
                {currentStepData.hint && (
                  <div style={{ marginTop: 'var(--space-2)', fontSize: '0.78rem', color: 'var(--muted)', fontStyle: 'italic' }}>
                    <HelpCircle size={12} style={{ display: 'inline', marginRight: '4px' }} aria-hidden="true" />
                    Hint: {currentStepData.hint}
                  </div>
                )}
              </div>

              {/* Student Response Text Area */}
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--ink-soft)', marginBottom: '4px' }}>
                  Your Historical Hypothesis / Analysis:
                </label>
                <textarea
                  rows={3}
                  placeholder="Record your thoughts based on the document text..."
                  value={studentAnswers[`${activeDoc.id}:${currentStepData.step}`] || ''}
                  onChange={(e) => setStudentAnswers({ ...studentAnswers, [`${activeDoc.id}:${currentStepData.step}`]: e.target.value })}
                  style={{
                    width: '100%',
                    padding: 'var(--space-2)',
                    fontSize: '0.86rem',
                    borderRadius: '4px',
                    border: '1px solid var(--rule)',
                    background: 'var(--surface)',
                    color: 'var(--ink)',
                    boxSizing: 'border-box',
                    fontFamily: 'inherit',
                  }}
                />
              </div>

              {/* Reveal Model Answer Button */}
              <div>
                <button
                  type="button"
                  className="button secondary"
                  style={{ width: '100%', fontSize: '0.82rem', padding: '6px 12px' }}
                  onClick={() => handleRevealAnswer(currentStepData.step)}
                >
                  <Sparkles size={14} aria-hidden="true" />
                  {showAnswers[currentStepData.step] ? 'Hide Expert Analysis' : 'Inspect Model Answer & Historical Evidence (+XP)'}
                </button>
              </div>

              {/* Model Answer Box */}
              {showAnswers[currentStepData.step] && (
                <div
                  style={{
                    padding: 'var(--space-3)',
                    background: 'var(--accent-tint)',
                    border: '1px solid var(--accent-tint-2)',
                    borderRadius: '6px',
                    fontSize: '0.85rem',
                    color: 'var(--ink)',
                    lineHeight: 1.5,
                  }}
                >
                  <div style={{ fontWeight: 600, color: 'var(--accent-hover)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <CheckCircle2 size={16} aria-hidden="true" /> Expert Historical Sourcing & Evidence:
                  </div>
                  <div>{currentStepData.modelAnswer}</div>
                </div>
              )}
            </div>
          )}
          {!currentStepData && (
            <div style={{ padding: 'var(--space-3)', background: 'var(--paper)', borderRadius: '6px', border: '1px solid var(--rule)', color: 'var(--muted)', fontSize: '0.85rem' }}>
              No guided interrogation steps defined for this document yet.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
