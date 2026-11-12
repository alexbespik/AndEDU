# Known bugs and to do

Open problems found but not fixed yet, then features asked for. Remove an entry when it lands.

## Advisor: prerequisites are per course, not per section

Found 2026-11-11. Different sections of the same course can have different prerequisites (e.g. a section
restricted to majors, an honors section, or a topics course whose sections cover different subjects), but
prerequisites are stored only once per course: `catalog_courses.prereqs` / `prereq_codes` / `prereq_tree`
(`advisor.py:30-34`). `catalog_sections` (`advisor.py:41`) has no prerequisite or restriction column, and
`_compact_section` (`advisor_cart.py:215`) doesn't return one. So readiness (`advisor.readiness`) and the cart's
`prereq_missing` flag (`advisor_cart.py:250`) judge every section by the course-level rule: a student can be told
they're ready for a section they can't register for, or blocked from one they could take.

Suggested fix: import each section's own prerequisites and restrictions into `catalog_sections` (falling back to
the course's when a section has none), show them per section in the cart, and check `prereq_missing` against
the chosen section (`section_crn`) when one is picked.

## Tests may reach ElevenLabs despite SCIEDU_ELEVENLABS=0

Found 2026-11-11 by the tester agent. A full `.venv/bin/python -m unittest discover -s tests` run logs
"[TTS] ElevenLabs answered HTTP 401/500" and "ConnectTimeout", although AGENTS.md says tests force
`SCIEDU_ELEVENLABS=0` so they never spend credits. All tests pass; find which test reaches the network and make
it use the stub (a real key in `.env` would spend credits on every test run).

# To do

Features asked for, not built yet.

## Multiple password-protected accounts, each with its own key and lectures

Asked for 2026-11-11. On a personal machine and in the desktop app, profiles are name-only (no password), and
the app has a single Gemini key (`<userData>/secrets/gemini.key.enc` on desktop, `.env` otherwise) shared by
everyone. Real accounts with passwords exist only in server mode (`SCIEDU_AUTH=1`, `server.py:70-74`, `/api/auth/*`),
and the desktop shell never turns that mode on.

Wanted: several accounts on one install, each behind its own password, each with its own Gemini key (and
ElevenLabs key, if used), and its own courses, lectures, progress and history, none of them visible to the other
accounts. Things to settle: the desktop's single safeStorage key becomes one encrypted key per account; the
backend picks the key per request instead of from `GEMINI_API_KEY`; daily spending caps per account; what
happens to existing name-only profiles (migrate them into password accounts); password reset on an offline
machine.

## Philosophy section

Asked for 2026-11-11. A Philosophy workspace next to History and Languages. Today the workspaces are math, code,
lab, history and language (`server.WORKSPACES`, `server.py:5346`), so a philosophy course is guessed into one
of those. Needs: `philosophy` in `WORKSPACES`, `guess_workspace` and the planner prompt; a tab component; and
activities that fit the subject (argument mapping, premise/conclusion spotting, fallacy finder, thought
experiments, dialogue with a philosopher in persona mode like History's Figures), with normalizers in a
`practice_philosophy.py` and MCP tools in `mcp_tools_philosophy.py`.

### Deterministic logic engine for Philosophy

Asked for 2026-11-11. A checker that never calls a model, so the same input always gives the same verdict, plus
a script to run it from the command line (`scripts/logic_check.py`) and MCP tools over it.
- **Propositional logic:** parse statements (`P -> Q`, `~P`, `P & Q`, `P | Q`, `P <-> Q`), truth tables, and
  validity: an argument is valid exactly when no row makes all premises true and the conclusion false. When an
  argument is invalid, return that row as the counterexample.
- **Categorical syllogisms:** check the standard forms (Barbara, Celarent...) with the distribution rules, and
  name the rule that breaks (undistributed middle, illicit major or minor, two negative premises).
- **Formal fallacies by structure:** affirming the consequent, denying the antecedent, and so on, recognized from
  the logical form, not from wording.
- **Proof checking:** check a natural-deduction proof line by line (modus ponens, modus tollens, disjunctive
  syllogism, conditional proof...), each line citing the rule and the lines it uses.
- **Debate analysis:** deterministic once the debate is an argument map (claims, premises, objections, rebuttals
  as JSON). It can then find unsupported claims, circular support (cycles in the graph), objections nobody
  answered, and invalid inferences. Turning free text into that map is the one step that needs a model; it
  should be a separate, clearly labelled step whose output the student can edit before the engine judges it.
- **Limit to state honestly:** informal fallacies (straw man, ad hominem, slippery slope) depend on meaning, so
  no script detects them 100% reliably. Offer them as student exercises and as "possible" hints, never as
  verdicts.
- **Quotes from Socrates and others:** an offline, curated quote bank (`content/quotes/*.json`) from public-domain
  translations (Plato's dialogues, Epictetus, Marcus Aurelius, Seneca...), each quote with work, section and
  translator, e.g. *Apology* 38a. The app only shows quotes from the bank and never generates one, so nothing
  is misattributed. Persona chats ("ask Socrates") cite bank quotes by id.
- Practice types `truth_table`, `validity`, `syllogism`, `proof_steps`, `argument_map`, graded by the engine.

## Modern loading screens with Stoic quotes and live logs

Asked for 2026-11-11. Today's loading states are plain text:
- the desktop start page is a grey "Starting &.edu…" (`desktop/main.cjs:322`);
- the lazy-loaded tabs show "Loading…", "Loading the IDE…" and similar (`src/App.jsx:24, 423, 432, 460, 471`);
- course and class generation show only the job's current `step` and `progress` (`CoursesHome.jsx`,
  `CourseView.jsx`).

Wanted: one shared loading component in the app's theme (light and dark) with a progress bar, a rotating Stoic
quote from the offline quote bank above (with work and section), and, for generation jobs, a live log of steps
as they happen (e.g. "Diagnostic planned · Lesson written · Quiz checked: 1 answer corrected"). Jobs keep only
the latest `step` today (`server.py:3607-3613`), so the server needs to keep a short step history per job and
send it with `JOB_UPDATE`. The desktop start page can show the backend's startup log lines in the same style.
Respect reduced motion, and keep quotes off in Focus mode if it should stay minimal.

## MCP server ideas (from a Gemini brainstorm, checked against the code)

Asked for 2026-11-11. The brief Gemini received was cut off after the Socratic tutor paragraph, so it never saw
the existing MCP tools or the rules (data only, localhost, offline first, spending caps). These notes add that.
Ordered by value for the effort.

1. **Exact math checking (SymPy)**, small to medium. Today a second model re-solves quiz questions
   (`verify_questions`), and math practice recomputes a `compute` expression. SymPy would make symbolic answers
   exact: `check_equivalence`, `solve_symbolic`, `simplify`, `counterexample`. Offline, no model calls. SymPy
   isn't in `requirements.txt` yet (pure Python, fine for the desktop bundle).
2. **Philosophy logic engine**, medium (above). No dependencies needed; Z3 is unnecessary for propositional logic
   and syllogisms.
3. **German dictionary data (Kaikki / Wiktionary dumps)**, medium. Offline lookups for gender, plurals, cases,
   conjugation tables and IPA, so lessons never invent a noun's gender. Bundle only the German subset (size
   matters for the desktop app). Check the license (CC BY-SA) and give attribution.
4. **Better spaced review (FSRS)**, medium. Replace the fixed Leitner steps `REVIEW_INTERVALS = (1, 3, 7, 14, 30)`
   (`engage.py:93`) with FSRS, which is deterministic and offline. This is mostly an engine change. MCP tools on
   top: `weakest_concepts(student)`, `log_misconception`. Existing review rows need migrating.
5. **Anki / Obsidian / CSV export**, small. Nothing exports today. A `.apkg` or CSV file for flashcards and missed
   questions is simplest; AnkiConnect and Obsidian's local REST API are localhost-only and optional.
6. **Chemistry and units checker**, medium. Balance equations and check stoichiometry with exact linear algebra
   (SymPy), and check units with Pint. Skip RDKit: too heavy for the desktop bundle.
7. **Code grading by structure (Python AST)**, medium. Check structure (loops, recursion, forbidden built-ins),
   generate edge-case tests, and feed `spot_the_bug`. Runs in the existing sandbox; Hypothesis is optional.
8. **Historical borders and places (Pleiades / Wikidata)**, large. Borders by year as offline GeoJSON for the
   History map. Data must be prepared ahead of time and bundled. Live Wikidata queries need network access and
   their text is untrusted (goes through `page-guard`).
9. **LMS sync (Canvas / Moodle)**, large. Deadlines, syllabi and exam dates into semester and test-prep courses.
   Needs a token per student, so it depends on the multi-account item above (keys per account). Privacy review
   needed.
10. **Open sources (arXiv / OpenAlex / Gutenberg / Crossref)**, medium. Readings and citations for thematic and
    philosophy courses. Network access; fetched text is untrusted and goes through the existing draft guard.
11. **Live registrar data**, mostly exists already: `catalog_search`, `check_readiness`, `recommend_courses` and
    seat-risk estimates (`advisor_risk.py`). Live scraping is blocked (catalog.wm.edu blocks scripts; catalogs
    come from Wayback imports). Do the per-section prerequisites bug above first.
12. **Whiteboard handwriting to LaTeX (pix2tex)**, large, low priority. Needs PyTorch, which is far too heavy for
    the desktop bundle. The vision-model grader (`/api/draw/check`) already covers it.
13. **MCP resources and prompts**, small. The server exposes tools only (`mcp_server.py` answers `initialize`,
    `tools/list`, `tools/call`). Adding resources (topic JSON, the SimSpec and practice guides) and prompts
    ("write a class", "check a topic") would make agents more reliable at little cost.

## MCP server ideas, round 2 (Gemini with the full brief, checked against the code)

Asked for 2026-11-11. Gemini's claims about effort and bundle size are its own estimates; the notes after each
dash are what the code says. Ordered by value for the effort.

1. **Statistics and probability engine**, small. Distributions, p-values, hypothesis tests, regression, ANOVA,
   Bayes updates, combinatorics, and seeded synthetic datasets with answer keys, all deterministic. Fills a real
   gap: no statistics checker exists. Pure Python (`statistics`, `math`) plus SymPy from round 1; don't bundle
   SciPy. Plot points must come out as SimSpec `graph` data.
2. **Content auditor**, small. Extends the existing `lint_topic` (`mcp_tools_studio.py:136`, which already flags
   missing explanations, duplicates, missing hints and doubtful answer checks) with: answers leaking into hints,
   distractor giveaways (longest option, grammar cues), reading level, tolerance and significant-figure traps,
   grounding of lesson claims in the uploaded notes (lexical overlap only, so it reports "not found in your
   notes", never "false"), and course coherence (terms used before they're taught). Run it as a gate before
   saving generated classes.
3. **Study scheduler and calendar export**, small. Turns exam dates, semester classes and the review queue into
   a daily plan that rebalances after missed days, with a local `.ics` export. Pairs with FSRS (round 1) for
   review load forecasts and with the Advisor cart for crunch weeks. Never imports calendar text into prompts.
4. **Mastery estimates (Elo / IRT)**, small to medium. Per-concept ability estimates and item quality (which
   questions don't discriminate, which distractors nobody picks). Today adaptation is the fixed under-50% /
   90%+ rule (`adapt_next_class`, `server.py:3541`); keep that rule until there are enough attempts per concept
   (cold start). Concepts need ids on quiz questions first, which they don't have today.
5. **Digital logic and computer architecture**, small. Truth tables, Karnaugh-map minimization, number
   representations (two's complement, IEEE-754), ALU flags, finite-state-machine equivalence with a
   distinguishing input, cache traces. Shares the truth-table core with the Philosophy logic engine, so build
   that one first.
6. **Economics and game theory**, small. Market equilibrium with taxes and surplus, elasticity, multipliers,
   Nash equilibria (pure and mixed), backward induction, comparative advantage. Needs an `economics` home: a
   workspace or the Math tab. Graphs as SimSpec data.
7. **Biology and genetics**, small. Punnett squares, pedigree analysis, DNA to protein translation, sequence
   alignment (cap the length), Hardy-Weinberg, predator-prey models. Fits Lab as a third science next to
   physics and chemistry.
8. **Accessibility**, small to medium. LaTeX to spoken math (for screen readers and the narrated walkthrough),
   colour-blind-safe palettes for simulations and der/die/das colours, shorter chunks for focus, extra time on
   timed rounds, text/table alternatives for graphs and simulations. Run a WCAG audit of the app first.
9. **Offline reference packs**, medium. SQLite full-text packs: physical constants (CODATA), the periodic table,
   SI units, country and place data. A small core pack bundled, larger packs optional. A `verify_claim` tool lets
   lessons check numbers against the pack. Check each source's license.
10. **Music theory**, medium. Chords and Roman numerals, scales and modes, species counterpoint checks (parallel
    fifths and octaves), figured bass, rhythm grids, ear training played in the browser (Web Audio, no ElevenLabs
    cost). Don't bundle music21 (its score corpus is huge). Needs a staff-notation renderer in the app.
11. **Wellbeing and pacing**, small, opt-in only. Fatigue and rapid-guessing signals from answer timing, warm-up
    items, break suggestions, streak-burnout checks. Today there's only Focus mode and streak freezes. Behaviour
    data stays local and never goes into prompts; suggestions are dismissible. Be careful with wording: hints,
    not diagnoses.
12. **Peer study packs and ghost races**, medium. Export and import lesson packs as files and race a friend's
    recorded speed-round run, without a server. Imported packs are untrusted: schema validation, links and
    HTML stripped, and the `page-guard` review before anything is saved, the same as agent drafts.
13. **Teacher tools**, medium, server mode only. Class heatmaps, wrong-answer clusters, tiered problem sets, and
    QTI export/import for Canvas, Moodle and Blackboard. Accounts mode has no teacher role today (no roles in
    `db.py`), so that comes first, and QTI XML must be parsed with `defusedxml`.
14. **Law and legal reasoning**, medium. Statutes as element trees checked against facts (reuses the logic
    engine), IRAC briefs, issue-spotting scores, and a bundled set of landmark cases. Only curated cases, never
    generated citations, and an "educational only, not legal advice" notice.
15. **Art history**, medium. Colour-harmony analysis, composition overlays (perspective, rule of thirds), who-am-I
    attributions, iconography label diagrams. A bundled metadata set; images from CC0 museum APIs (the Met, Art
    Institute of Chicago) fetched on demand, with their text treated as untrusted.

Wild ideas worth keeping:
- **Teach the buggy classmate** (Feynman protégé). The student corrects a simulated peer seeded with known
  misconceptions. The misconception counts as fixed only through a check the engine can verify (a counterexample,
  or picking the wrong step), not because the student persuaded the model. One model call per turn, capped.
- **Find the broken law.** A simulation with one law subtly changed (momentum not conserved, gravity as 1/r³);
  the student measures and names it. Builds on SimSpec with no new code; label the sandbox clearly so nobody
  revises from it.
- **Cross-subject bridges.** A curated map of shared structures (spring ↔ RLC circuit, contrapositive ↔ guard
  clause), each entry with where the analogy breaks.
- **Stump the solver.** Advanced students write a problem that a weak solver gets wrong but the deterministic
  checker confirms, or find the flaws planted in a lab report. Needs the SymPy and logic engines first.
- **Real-world sensor lab.** Microphone and video data fitted against the ideal simulation (pendulum period,
  Doppler shift), and German vowel formants plotted on a vowel chart. The browser captures and reduces the data
  to numbers; the desktop shell already allows microphone access for the app's own pages
  (`desktop/main.cjs:290-293`). No raw audio is saved.
