# Deep-Dive Research & Systems Blueprint: Future Liberal Arts Kits for &.edu
**Target Audience**: Gemini (Frontier AI Model / Curriculum & Systems Researcher)  
**System**: &.edu (SciEdu-Studio) Adaptive Learning Platform  
**Purpose**: Comprehensive technical specification, pedagogical foundations, interactive mechanics, and formal schemas for expanding the Liberal Arts workspace from the initial three disciplines (History, Languages, Philosophy) into six new interactive, tactile domain kits.

---

## 1. System Context & Architectural Invariants of &.edu

### 1.1 What is &.edu?
&.edu is a zero-dependency, local-first adaptive learning platform designed for higher education. It takes unstructured student materials (syllabi, lecture slide PDFs, reading transcripts, problem sets) and turns them into an adaptive course:
1. An initial diagnostic quiz gauging baseline concept mastery.
2. An ordered sequence of generated classes (interactive lesson markdown, declarative simulations, formative quizzes, and tactile practice puzzles).
3. Dynamic adaptation: Finishing a class quiz under 50% automatically rewrites the next unstarted class with more scaffolding; 90%+ increases depth and complexity.
4. Spaced repetition: Every missed quiz question re-enters the student's personal review deck via a 5-box Leitner scheduler (1, 3, 7, 14, 30 days).

### 1.2 Core Architectural Invariants
When designing new kits for &.edu, Gemini must adhere to the following rigid engineering invariants:
1. **Deterministic Offline Verification**:
   - Practice puzzles, symbolic logic, mathematical proofs, prosody checks, voice-leading audits, and voting simulations MUST be graded deterministically in Python standard library or client-side JavaScript.
   - LLMs are utilized for semantic chunking, initial extraction, and Socratic hints, but **never** as the authoritative runtime evaluator for right/wrong verdicts.
2. **Epistemic Neutrality (Zero Normative Bias)**:
   - Evaluative, political, ethical, and religious claims are formally classified as `normative` or `unfalsifiable`. They are never judged as empirically "true" or "false", nor are competing value frameworks ranked.
3. **No Arbitrary Code Execution in Content (SimSpec Data-Only)**:
   - Interactive simulations are declarative data structures (JSON ASTs), interpreted by safe client sandboxes (Canvas/SVG engines, Web Audio API, or expression evaluators in `src/lib/expr.js`). Topics never store or execute arbitrary JavaScript.
4. **Standardized Practice Schema**:
   - Each practice type follows a uniform contract:
     - Normalizer in Python: `practice_<discipline>.py` defines `_np_<type>(p, base) -> dict | None` that cleans inputs and strips any AI-supplied answers.
     - Registered in `server.PRACTICE_NORMALIZERS`.
     - Frontend React 19 renderer in `src/practice/<discipline>.jsx` taking `{item, onResult(ok, given), retry}`.
5. **Offline-First & Zero Trackers**:
   - All maps and architectural diagrams are local SVGs (`public/maps/`, `public/diagrams/`).
   - Audio is generated via Web Speech API or procedurally synthesized via the Web Audio API without remote external CDNs.

---

## 2. The Baseline: Existing Liberal Arts Suite

&.edu currently organizes Liberal Arts under a grouped navigation menu in `src/components/Navbar.jsx`:

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 &.EDU LIBERAL ARTS SUITE BASELINE                                 │
├──────────────────────────┬───────────────────────────┬────────────────────────────────────────────┤
│ 1. HISTORY               │ 2. LANGUAGES              │ 3. PHILOSOPHY (PHILIN)                     │
├──────────────────────────┼───────────────────────────┼────────────────────────────────────────────┤
│ • Interactive SVG Maps   │ • Gamified Learn Path     │ • PHILIN Extraction Pipeline:               │
│   (public/maps/)         │ • 5 Hearts & XP Ledger    │   exact character spans [start, end],      │
│ • Branching Crisis Sims  │ • Word Strength (0-4)     │   30-char negation stripping check,        │
│   (state metrics)        │ • Web Audio & Speech API  │   atomic empirical vs normative split.     │
│ • Historical Figures     │ • Pronunciation Levenshtein│ • Deterministic Logic Engine:              │
│   Persona Chat (≤120 w)  │ • Drills: Translate,      │   Truth tables (≤4 vars), Calgary Fitch    │
│ • Primary Source Lab     │   Word Bank, Listen,      │   natural deduction proofs, categorical    │
│   (SHEG / SOAPS / OPVL)  │   Dialogue, Story,        │   syllogisms (all 256 forms), argmaps,     │
│ • Merged Timeline        │   Conjugation, Script.    │   Hume's Guillotine is-ought gap check.    │
│   (era bands & zoom)     │ • Socratic Roleplay AI    │ • 8 Thought Experiments with gauges.      │
│ • Daily Games Mix        │ • Spaced Leitner Review   │ • Fallacy Lab (formal counterexamples).    │
└──────────────────────────┴───────────────────────────┴────────────────────────────────────────────┘
```

---

## 3. The Expansion: 6 New Liberal Arts Kits

Gemini should examine the blueprints below and conduct deep research into curriculum design, formal algorithms, puzzle schemas, and starter seed courses.

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    NEW LIBERAL ARTS EXPANSION KITS                                │
├──────────────────────────────────┬────────────────────────────────────────────────────────────────┤
│ Kit 1: Literature & Close Reading│ Poetics, scansion meter tapper, syntax forensics, Freytag arc. │
├──────────────────────────────────┼────────────────────────────────────────────────────────────────┤
│ Kit 2: Art History & Visual Cult.│ Formal analysis vector HUD, palette extractor, architectural   │
│                                  │ orders builder, Panofsky 3-tier iconographic decoder.          │
├──────────────────────────────────┼────────────────────────────────────────────────────────────────┤
│ Kit 3: Music Theory & Acoustics  │ Interactive piano roll, Circle of Fifths, Roman numeral/figured│
│                                  │ bass, SATB counterpoint linter, acoustic harmonic series.      │
├──────────────────────────────────┼────────────────────────────────────────────────────────────────┤
│ Kit 4: Classical Civilizations   │ Epigraphic Leiden transcriptions, Harris matrix stratigraphy,  │
│                                  │ Mediterranean vector map, Athenian/Roman constitutional sims.  │
├──────────────────────────────────┼────────────────────────────────────────────────────────────────┤
│ Kit 5: Rhetoric & Speech Forensic│ Aristotelian appeal balancer (Ethos/Pathos/Logos), Dispositio  │
│                                  │ speech structure, Toulmin argument DAGs, stylistic tropes.     │
├──────────────────────────────────┼────────────────────────────────────────────────────────────────┤
│ Kit 6: Political Theory & Polity │ Electoral systems (FPTP, RCV, PR D'Hondt, STV Droop),          │
│                                  │ gerrymandering sandbox, constitutional veto points matrix.     │
└──────────────────────────────────┴────────────────────────────────────────────────────────────────┘
```

---

### Kit 1: Literature & Close Reading (`literature`)

#### 1. Pedagogical Rationale
Literary analysis frequently devolves into superficial plot recaps or impressionistic opinions. This kit grounds literature in textual mechanics, prosody, narrative architecture, and syntactic forensics. Students analyze literary works as engineered systems where form, rhythm, and diction construct meaning.

#### 2. Interactive Tools & Simulators
- **Scansion & Metrical Prosody Tapper (`ProsodyTapper.jsx`)**:
  - *Mechanic*: Audio-rhythmic scansion desk. The student reads a verse line and taps rhythmically to assign syllable stress: ictus (stressed `/'` = 1) and breve (unstressed `˘` = 0).
  - *Foot Segmentation*: Draggable boundaries (`|`) dividing feet into Iambs (`0 1`), Trochees (`1 0`), Anapests (`0 0 1`), Dactyls (`1 0 0`), Spondees (`1 1`), and Pyrrhics (`0 0`). Double bar (`||`) marks caesuras.
  - *Audio Metronome*: Web Audio API pulse emphasizing stressed vs. unstressed syllables with pitch/amplitude contrast.
  - *Automated Anomaly Detection*: Flags metrical substitutions (e.g. headless lines, catalexis, hypercatalexis/feminine endings, initial trochaic inversions in iambic pentameter).
- **Multilayer Syntax Forensics Canvas (`SyntaxForensics.jsx`)**:
  - *Mechanic*: Multilayer text annotator highlighting three tiers:
    1. *Etymological Register*: Anglo-Saxon/Germanic roots (visceral, concrete) vs. Latinate/Norman roots (abstract, legalistic) vs. Hellenic roots (philosophical, technical).
    2. *Figurative Mapping*: Tenor and Vehicle connector lines for metaphors, metonymy, synecdoche, and synesthesia.
    3. *Syntactic Architecture*: Hypotaxis (hierarchical subordinate clauses) vs. Parataxis (flat coordination); visual tracking of enjambment, chiasmus, and anaphora.
- **Narrative Architecture Visualizer (`NarrativeArc.jsx`)**:
  - *Mechanic*: Interactive timeline graphing Story Time (chronological Fabula) vs. Discourse Time (narrative Syuzhet).
  - *Dramatic Tension Curve*: Real-time spline editor mapping narrative arcs against Freytag's Pyramid (Exposition $\to$ Inciting Incident $\to$ Rising Action $\to$ Climax $\to$ Falling Action $\to$ Denouement) and Kishōtenketsu (Introduction $\to$ Development $\to$ Twist $\to$ Reconciliation).
- **Poetic Form Sandbox (`PoeticFormDesk.jsx`)**:
  - *Mechanic*: Structural stanza builder enforcing strict classical constraint checking:
    - *Petrarchan Sonnet*: Octave ($ABBAABBA$) + Volta + Sestet ($CDECDE$ or $CDCDCD$).
    - *Shakespearean Sonnet*: Three quatrains ($ABAB~CDCD~EFEF$) + Heroic couplet ($GG$).
    - *Villanelle*: 19 lines, 5 tercets + 1 quatrain, two repeating refrains ($A_1 b A_2 ~ abA_1 ~ abA_2 ~ abA_1 ~ abA_2 ~ abA_1 A_2$).
    - *Terza Rima*, *Ballad Meter*, *Sestina* (lexical end-word permutation matrix).

#### 3. Deterministic Practice Puzzle Types
- `scansion`: Evaluates student syllable stress vectors and metrical foot boundaries against deterministic metric patterns.
- `volta_spot`: Given a sonnet, identify the exact line index where the structural/thematic pivot occurs, selecting the conceptual warrant.
- `rhyme_scheme_audit`: Given a corrupted stanza, identify the defective rhyme line and select the orthographic/phonetic repair that restores the strict scheme.
- `chronology_unravel`: Unscramble non-linear narrative passages (containing analepsis/flashbacks and prolepsis/flashforwards) into their underlying chronological sequence.

---

### Kit 2: Art History & Visual Culture (`art_history`)

#### 1. Pedagogical Rationale
Visual literacy requires structured observation rather than passive appreciation. This kit teaches students how to parse spatial composition, tonal values, architectural mechanics, and iconographic symbolism through direct geometric and chromatic interrogation.

#### 2. Interactive Tools & Simulators
- **Compositional Vector HUD (`FormalAnalysisHUD.jsx`)**:
  - *Mechanic*: High-resolution canvas with non-destructive vector overlays:
    - *Geometric Armatures*: Toggleable Golden Ratio ($\phi$) spirals, Rule of Thirds grids, pyramidal triangular focal anchors, and dynamic Baroque diagonal vectors.
    - *Contrapposto Anatomical Protractor*: Angle measurement tool measuring the countervailing tilt of hip axis vs. shoulder axis in Classical Greek and Renaissance sculpture.
    - *Chiaroscuro & Tenebrism Luminance Shader*: Image threshold filter isolating darks, midtones, and highlights to reveal the artist's lighting design (e.g. Caravaggio, Rembrandt).
- **Palette Extractor & Color Harmonies Workbench (`PaletteWorkbench.jsx`)**:
  - *Mechanic*: K-means clustering sampling pixels from the artwork to extract a 5-to-8 swatch dominant palette.
  - *Itten Color Contrast Engine*: Evaluates the palette across Johannes Itten's 7 color contrasts (Contrast of Hue, Light-Dark, Cold-Warm, Complementary, Simultaneous, Saturation, Extension).
  - *Varnish Aging Simulator*: Adjustable slider removing yellowed oxidized resin varnishes to display original Renaissance and Baroque color values.
- **Architectural Order & Vault Assembly Builder (`ArchitecturalOrders.jsx`)**:
  - *Mechanic*: Modular drag-and-drop structural assembly puzzle.
  - *Classical Orders*: Assembling Doric, Ionic, Corinthian, Tuscan, and Composite orders with exact constituent parts: Stylobate, Column Shaft (with fluting and entasis), Capital (Echinus/Abacus/Volutes/Acanthus leaves), Architrave, Frieze (Triglyphs and Metopes), Cornice, and Tympanum.
  - *Gothic Engineering*: Structural vault builder contrasting Romanesque semicircular barrel/groin vaults with Gothic pointed ribbed vaults and external flying buttresses.
- **Panofsky 3-Tier Iconographic Decoder (`IconographyDesk.jsx`)**:
  - *Mechanic*: Hotspot discovery tool applying Erwin Panofsky's methodology:
    1. *Level 1 (Pre-iconographical description)*: Primary physical forms (a skull, an open book, a mirror).
    2. *Level 2 (Iconographical analysis)*: Conventional cultural meaning (skull = *memento mori*, dog = marital fidelity/*fides* in Jan van Eyck).
    3. *Level 3 (Iconological interpretation)*: Historical worldview and philosophical synthesis of the cultural era.

#### 3. Deterministic Practice Puzzle Types
- `composition_vector`: Students draw primary orthogonal vanishing lines on perspective paintings (e.g. Masaccio, Piero della Francesca) to locate the vanishing point within pixel tolerance.
- `label_architecture`: Interactive SVG diagram labeling identifying architectural components on temples, cathedrals, and amphitheaters.
- `iconography_decode`: Identify symbolic objects in Northern Renaissance / Baroque paintings and map them to their conventional iconographic meanings.
- `stylistic_taxonomy`: Pairwise classification sorting uncaptioned works into Heinrich Wölfflin's comparative categories (Linear vs. Painterly, Plane vs. Recession, Closed vs. Open Form, Multiplicity vs. Unity, Absolute vs. Relative Clarity).

---

### Kit 3: Music Theory & Acoustics (`music`)

#### 1. Pedagogical Rationale
Music bridges mathematical physics with structured expressive syntax. This kit unifies the acoustics of vibrating strings and air columns with the strict voice-leading rules of Western common-practice harmony and counterpoint.

#### 2. Interactive Tools & Simulators
- **Interactive Piano Roll & Circle of Fifths (`CircleOfFifthsDesk.jsx`)**:
  - *Mechanic*: Reactive SVG Circle of Fifths synchronized with a 49-key virtual keyboard and polyphonic Web Audio procedural synthesizer.
  - *Harmonic Relations*: Selecting any root key displays key signatures (order of sharps and flats), relative minors, closely related keys (dominant, subdominant), and chromatic pitch classes.
  - *Procedural Synthesizer*: Dual-oscillator additive synthesizer with configurable ADSR envelopes and harmonic overtone sliders.
- **Harmonic Progression & Figured Bass Builder (`HarmonicProgression.jsx`)**:
  - *Mechanic*: Interactive score editor for Roman Numeral Analysis:
    - Diatonic triads and seventh chords ($I, ii, iii, IV, V, vi, vii^\circ$, $V^7$).
    - Inversion and figured bass indicators: root ($5/3$), first inversion ($6$), second inversion ($6/4$), third inversion ($4/2$).
    - Chromatic functional harmony: Secondary dominants ($V^7/V, V^7/IV$), Neapolitan sixth ($N^6$), and Augmented Sixth chords (Italian $It^{+6}$, French $Fr^{+6}$, German $Ger^{+6}$).
- **Deterministic SATB Voice-Leading & Counterpoint Linter (`VoiceLeadingLinter.jsx`)**:
  - *Mechanic*: Real-time choral score auditor evaluating four-part (Soprano, Alto, Tenor, Bass) harmony.
  - *Deterministic Rule Checks*:
    - Parallel fifths ($P5 \to P5$) and parallel octaves ($P8 \to P8$) between any pair of voices.
    - Hidden/direct fifths or octaves in outer voices without stepwise soprano motion.
    - Faulty resolution of the leading tone ($7 \to 1$) and dominant seventh ($4 \to 3$).
    - Voice crossing, voice overlap, and voice spacing violations (>1 octave between S-A or A-T).
- **Acoustic Waveform & Tuning System Visualizer (`AcousticsLab.jsx`)**:
  - *Mechanic*: SimSpec declarative physics canvas showing standing waves on a string ($L = n \frac{\lambda}{2}$, $f_n = n \cdot f_0$) with harmonic node/antinode markers.
  - *Tuning Comparison Engine*: Real-time audio comparison of intervals across:
    - *Equal Temperament*: $\sqrt[12]{2}$ semitone ratio (100 cents).
    - *Just Intonation*: Pure rational harmonic ratios ($3:2$ fifth, $5:4$ third).
    - *Pythagorean Tuning*: Compounded $3:2$ fifths.
    - *Syntonic Comma & Acoustic Beating*: Visualizes the $81:80$ ratio discrepancy and audio beat frequency interference patterns.

#### 3. Deterministic Practice Puzzle Types
- `roman_numeral_analysis`: Identify the Roman numeral, chord quality, and inversion of chords displayed on grand staff notation.
- `voice_leading_lint`: Given a 4-measure SATB chorale, find and click the specific measures and voice pairs containing voice-leading errors.
- `ear_interval_id`: Auditory interval recognition synthesized via procedural Web Audio, played harmonically or melodically.
- `figured_bass_realize`: Given a figured bass line, place Soprano, Alto, and Tenor notes that satisfy voice-leading rules.

---

### Kit 4: Classical Civilizations & Ancient Texts (`classics`)

#### 1. Pedagogical Rationale
Classical studies requires students to reconstruct historical reality from fragmentary material culture, broken inscriptions, and developing political institutions. This kit teaches archaeological forensics, epigraphic decoding, and comparative constitutional history.

#### 2. Interactive Tools & Simulators
- **Epigraphic Decipherer & Palaeography Workbench (`EpigraphyDesk.jsx`)**:
  - *Mechanic*: High-resolution inscription reader for archaic Greek and Roman stone monuments (e.g. *Res Gestae Divi Augusti*, Gortyn Law Code).
  - *Boustrophedon Reading Guide*: Dynamic reading path switcher for archaic Greek inscriptions alternating direction every line.
  - *Leiden Epigraphic Conventions Tool*:
    - `[abc]`: Restored lacunae (lost text).
    - `(abc)`: Expanded ancient abbreviations (e.g. `IMP(ERATOR)`).
    - `<abc>`: Editorial correction of ancient lapidary omissions.
    - `{abc}`: Erroneous letters expunged by modern editors.
  - *Palaeographical Morphology Slider*: Visual evolutionary slider showing letterform transitions from Phoenician to Archaic Greek to Classical Attic to Roman Imperial capitals.
- **Archaeological Stratigraphy Matrix (Harris Matrix Engine) (`HarrisMatrix.jsx`)**:
  - *Mechanic*: Cross-sectional excavation trench simulator.
  - *Stratigraphic Laws*: Application of Steno's Law of Superposition, original horizontality, and intrusive cutting features (pits, foundation trenches, robber trenches).
  - *Dating Vectors*: Terminus Post Quem (TPQ - date after which) and Terminus Ante Quem (TAQ - date before which) derived from diagnostic coin hoards and datable terra sigillata stamps.
  - *Interactive DAG*: Students connect excavation context nodes into a directed acyclic stratigraphic graph.
- **Ancient Mediterranean Vector Political Map (`MediterraneanMap.jsx`)**:
  - *Mechanic*: Vector map engine utilizing `public/maps/mediterranean.svg` with layered historical overlays:
    - Peloponnesian League vs. Delian League alliances (431 BCE).
    - Roman Republican expansion phases (post-Punic Wars, Macedonian Wars).
    - Roman Imperial road network (*cursus publicus*) and grain trade shipping routes (Alexandria to Ostia).
- **Classical Constitutional Balance Simulator (`AncientConstitutions.jsx`)**:
  - *Mechanic*: Comparative institutional balance workbench modeling:
    - *Athenian Direct Democracy*: Assembly (*Ekklesia*), Council of 500 (*Boule* chosen by sortition via *kleroterion*), Jury Courts (*Dikasteria*), and Ostracism mechanics.
    - *Roman Republic Cursus Honorum*: Balance of magistrates (Consuls, Praetors, Aediles, Quaestors), Tribunes of the Plebs (possessing sacrosanct veto power), Senate (*auctoritas*), and Centuriate/Tribal Assemblies.

#### 3. Deterministic Practice Puzzle Types
- `epigraphy_transcribe`: Transcribe epigraphic facsimiles, expanding standard abbreviations and filling missing lacunae.
- `harris_matrix_build`: Arrange excavated soil layers and intrusive features into a chronologically valid Harris Matrix.
- `cursus_honorum_order`: Order the offices of the Roman Republic in legal career sequence, matching age qualifications and constitutional powers.
- `athenian_sortition_sim`: Calculate demographic representation across the 10 Cleisthenic tribes using the Athenian allotment machine model.

---

### Kit 5: Rhetoric & Speech Forensics (`rhetoric`)

#### 1. Pedagogical Rationale
While formal logic (PHILIN) assesses deductive validity and empirical truth, rhetoric assesses persuasive architecture, audience psychology, and stylistic force. This kit deconstructs historical and contemporary oratory through classical canons, argument mapping, and rhetorical trope forensics.

#### 2. Interactive Tools & Simulators
- **Aristotelian Persuasive Appeal Balancer (`AppealBalancer.jsx`)**:
  - *Mechanic*: Interactive speech transcript analyzer that segments oratorical delivery into Aristotle's three modes of persuasion:
    - **Ethos**: Establishing authority, moral virtue (*arete*), practical wisdom (*phronesis*), and goodwill (*eunoia*).
    - **Logos**: Deductive syllogisms, enthymemes (arguments with implicit unstated premises), statistical data, and inductive analogies.
    - **Pathos**: Emotional arousal (pity, fear, indignation, civic pride).
  - *Ternary Balance Gauge*: Dynamic barycentric triangle plotting the real-time balance of appeals as the student scrubs through a speech.
- **Classical Oration Blueprint (*Dispositio* Engine) (`DispositioDesk.jsx`)**:
  - *Mechanic*: Structural workbench mapping speeches to the 6 classical parts of an oration:
    1. *Exordium*: Hook, securing audience goodwill (*captatio benevolentiae*).
    2. *Narratio*: Factual exposition and background history.
    3. *Partitio/Divisio*: Clarification of agreed points and contentious pivots.
    4. *Confirmatio*: Positive proof and evidence presentation.
    5. *Refutatio*: Rebuttal and destruction of opposing counterarguments.
    6. *Peroratio*: Emotional synthesis, moral appeal, and climax.
- **Toulmin Argumentation & Rebuttal Workbench (`ToulminDesk.jsx`)**:
  - *Mechanic*: Reactive DAG editor parsing argument structure into Stephen Toulmin's six elements:
    - *Claim*, *Grounds/Data*, *Warrant*, *Backing*, *Modal Qualifier*, and *Rebuttal*.
- **Oratorical Device & Stylistic Trophy Cabinet (`RhetoricalTropes.jsx`)**:
  - *Mechanic*: Regex/AST pattern-matching engine detecting micro-rhetorical devices in speech text:
    - *Syntactic Schemes*: Chiasmus ($ABBA$), Anaphora, Epistrophe, Polysyndeton, Asyndeton, Tricolon crescendo, Zeugma.
    - *Semantic Tropes*: Litotes (understatement by negating the opposite), Hyperbole, Hypophora, Paralipsis/Praeteritio, Irony.

#### 3. Deterministic Practice Puzzle Types
- `appeal_triage`: Classify excerpts of historical speeches into primary and secondary Aristotelian appeals.
- `trope_hunter`: Identify the specific rhetorical device (e.g. chiasmus, zeugma, litotes) in a passage and highlight its paired syntactic anchors.
- `dispositio_sort`: Given scrambled paragraphs of a classical oration, sequence them according to classical *dispositio*.
- `enthymeme_excavator`: Given an abbreviated oratorical argument, identify the unstated implicit premise required to link grounds to conclusion.

---

### Kit 6: Political Theory & Comparative Governments (`polity`)

#### 1. Pedagogical Rationale
Political theory is the architecture of collective human incentives, power distribution, and institutional stability. This kit translates constitutional philosophy (Aristotle, Machiavelli, Hobbes, Locke, Montesquieu, The Federalist Papers, Arrow) into dynamic computational models of voting systems, institutional checks, and regime dynamics.

#### 2. Interactive Tools & Simulators
- **Electoral Systems & Gerrymandering Simulator (`ElectoralSim.jsx`)**:
  - *Mechanic*: Spatial voter distribution simulator comparing electoral outcomes from identical ballots:
    - *First-Past-The-Post (FPTP)*: Demonstrates Duverger's Law, spoiler effects, and wasted votes.
    - *Ranked Choice Voting (RCV / Instant Runoff)*: Round-by-round elimination and ballot transfers.
    - *Proportional Representation (PR)*: Seat allocation using D'Hondt divisors ($1, 2, 3, 4\dots$) vs. Sainte-Laguë ($1, 3, 5, 7\dots$).
    - *Single Transferable Vote (STV)*: Multi-member districts using the Droop Quota:
      $$\text{Quota} = \left\lfloor \frac{\text{Votes}}{\text{Seats} + 1} \right\rfloor + 1$$
  - *Gerrymandering Sandbox*: Interactive district re-districting grid illustrating *packing* (concentrating opposition voters) and *cracking* (diluting opposition voters across multiple districts).
- **Constitutional Checks & Veto Points Matrix (`ConstitutionalVeto.jsx`)**:
  - *Mechanic*: Flowchart modeling legislative traversal through governmental systems:
    - *System Archetypes*: Presidential (US), Parliamentary (UK Westminster), Semi-Presidential (France), and Consociational/Federal (Germany/Switzerland).
    - *Veto Players Theory (Tsebelis)*: Computes the core stability and policy reform grid based on the number of institutional veto players, their ideological distance, and internal cohesion.
- **Anacyclosis & Regime Stability Dynamical System (`RegimeDynamics.jsx`)**:
  - *Mechanic*: SimSpec declarative dynamic phase space modeling Polybius's cycle of regimes:
    $$\text{Monarchy} \xrightarrow{\text{decay}} \text{Tyranny} \xrightarrow{\text{revolt}} \text{Aristocracy} \xrightarrow{\text{decay}} \text{Oligarchy} \xrightarrow{\text{revolt}} \text{Democracy} \xrightarrow{\text{mob rule}} \text{Ochlocracy} \to \text{Monarchy}$$
  - *Sliders*: Economic inequality (Gini coefficient), institutional trust, external geopolitical stress, and demagoguery index.
- **Coalition Builder & Power Index Calculator (`CoalitionBuilder.jsx`)**:
  - *Mechanic*: Interactive parliamentary hemicycle showing party seat allocations.
  - *Power Index Calculations*:
    - Minimal Winning Coalition (MWC) determination.
    - Shapley-Shubik Index and Banzhaf Power Index, demonstrating why small third parties often exert outsized kingmaker leverage.

#### 3. Deterministic Practice Puzzle Types
- `instant_runoff_tally`: Calculate round-by-round candidate eliminations and ballot redistribution in a ranked-choice election.
- `dhondt_apportionment`: Compute legislative seat allocation from popular vote counts using D'Hondt divisors.
- `veto_pipeline`: Trace a proposed bill through institutional veto checkpoints, predicting whether the bill passes, dies, or undergoes presidential veto override.
- `coalition_pivotal_vote`: In a multi-party parliament, identify which minor party holds the pivotal kingmaker position to form a majority coalition.

---

## 4. Deep Research Prompts & Directives for Gemini

Gemini should use the prompts below to conduct deep-dive research into specific technical algorithms, data schemas, public-domain text corpora, and starter curricula:

### Research Directive 1: Formal Algorithms & Mathematical Specifications
1. **SATB Voice-Leading Validator**:
   - Provide the complete mathematical interval matrix formulation between 4 voice parts ($S, A, T, B$). Specify exact pitch-class integer arithmetic checking for parallel fifths ($P5$), parallel octaves ($P8$), voice crossings, and leading-tone resolutions in Python standard library.
2. **Electoral Quotient & Apportionment Algorithms**:
   - Write Python implementations for the D'Hondt method, Sainte-Laguë method, and STV Droop Quota calculation, including edge cases for exact mathematical ties and surplus vote fractional transfers.
3. **Archaeological Harris Matrix Topological Sorting**:
   - Specify the graph algorithm (topological sort with cycle detection) that validates a student's Harris Matrix against stratigraphic constraints, identifying physically impossible stratigraphical paradoxes.
4. **Metrical Scansion Syllabification Engine**:
   - Detail the rules for rule-based English syllabification and prosody stress assignment (sonority sequencing principle, CMUDict lexical stress, and poetic contraction rules like syncope, elision, and synaeresis).

### Research Directive 2: Curated Open-Access Corpora & Source Mapping
1. Identify exact **Project Gutenberg IDs** and stable public-domain editions for:
   - English poetic scansion (Shakespeare Sonnets, Milton's *Paradise Lost*, Keats's Odes, Dickinson).
   - Rhetorical orations (Pericles' Funeral Oration, Cicero's *In Catilinam*, Lincoln's Gettysburg Address, Frederick Douglass's *What to the Slave is the Fourth of July?*).
   - Political philosophy texts (Plato's *Republic*, Aristotle's *Politics*, Machiavelli's *The Prince*, Hobbes's *Leviathan*, Locke's *Second Treatise*, *The Federalist Papers*).
2. Identify **Wikimedia Commons / Open-Access museum collections** (Met, Rijksmuseum, British Museum) with high-resolution public-domain assets suitable for:
   - Compositional formal analysis (linear perspective, chiaroscuro, contrapposto).
   - Architectural orders (Parthenon, Pantheon, Roman Colosseum, Chartres Cathedral).
   - Inscriptions for epigraphy (Arch of Titus, Rosetta Stone, Law Code of Gortyn).

### Research Directive 3: Seed Course Syllabi (4 Classes Per Kit)
Design complete 4-class introductory course outlines for:
1. `LIT 101`: *The Anatomy of Poetry: Meter, Form, and Textual Forensics*.
2. `ART 101`: *How to Look: Formal Analysis, Color Harmonies, and Classical Architecture*.
3. `MUS 101`: *The Architecture of Sound: Acoustics, Harmony, and Counterpoint*.
4. `CLS 101`: *Buried Voices: Epigraphy, Stratigraphy, and Ancient Constitutions*.
5. `RHT 101`: *The Art of Persuasion: Classical Canons, Appeals, and Forensic Debate*.
6. `POL 101`: *Engines of Power: Electoral Systems, Veto Points, and Regime Stability*.

*Each class outline must specify*:
- Class Sequence ($1 \to 4$), Topic Title, Category, Difficulty.
- Summary and Key Concepts.
- Interactive Simulator Mode & Parameters.
- 3 Formative Quiz Questions with explanations.
- 2 Deterministic Practice Items matching the new practice schemas.

### Research Directive 4: Socratic Voice Persona Prompts
Draft `PERSONA_PROMPT` specifications for major historical figures across the six new disciplines (e.g. William Shakespeare, Giorgio Vasari, J.S. Bach, Cicero, Polybius, James Madison):
- Strict historical date horizon (knowledge restricted to their lifetime).
- Authentic linguistic cadence and tone without caricature.
- Strictly $\le 120$ words per response.
- Concluding with exactly one probing Socratic question.
- Verified anchor quote from `content/quotes/*.json`.
