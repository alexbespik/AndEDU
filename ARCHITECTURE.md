# &.edu (SciEdu-Studio) — System Architecture & Infrastructure Map

This document is the authoritative architectural specification and system map for **&.edu (SciEdu-Studio)**. It documents system boundaries, components, contracts, runtime lifecycle, configuration, persistence models, simulation engines, and scalability paths.

---

## 1. System Overview & Top-Level Architecture

&.edu transforms unstructured student materials (notes, syllabi, lecture slides, problem sets, transcripts) into adaptive, interactive learning courses. The platform couples automated pedagogical planning, grounded answer verification, declarative interactive simulations, and browser-sandboxed code execution.

```
                              ┌──────────────────────────────────────────────┐
                              │               STUDENT BROWSER                │
                              │        React 19 + Vite SPA (Port 5173/8090)  │
                              └──────────────────────┬───────────────────────┘
                                                     │
                   HTTP REST API / Auth Token / Polling Event Stream (?since=cursor)
                                                     │
                                                     ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   FASTAPI BACKEND (server.py)                                     │
│                                                                                                   │
│  ┌───────────────────────┐   ┌───────────────────────┐   ┌─────────────────────────────────────┐  │
│  │ Security & Auth       │   │ Ingestion & Prompts   │   │ Simulation Orchestration            │  │
│  │ - Host header check   │   │ - PdfReader, docx     │   │ - author_simulation (Gemini)        │  │
│  │ - Session Bearer auth │   │ - Syllabus planner    │   │ - simspec validator (AST parser)    │  │
│  │ - Rate & budget caps  │   │ - Diagnostic engine   │   │ - chemspec validator                │  │
│  └───────────────────────┘   └───────────────────────┘   └─────────────────────────────────────┘  │
│                                                                                                   │
│  ┌───────────────────────┐   ┌───────────────────────┐   ┌─────────────────────────────────────┐  │
│  │ Background Jobs       │   │ Engagement Engine     │   │ Autonomous Agents                   │  │
│  │ - Job queue / runner  │   │ - XP, streaks, badges │   │ - Gemini Tools                      │  │
│  │ - Async course worker │   │ - Leitner review box  │   │ - Antigravity CLI (fenced agy)      │  │
│  └───────────────────────┘   └───────────────────────┘   └─────────────────────────────────────┘  │
└───────────────────┬───────────────────────────┬──────────────────────────────────┬────────────────┘
                    │                           │                                  │
                    ▼                           ▼                                  ▼
      ┌───────────────────────────┐ ┌───────────────────────────┐   ┌─────────────────────────────┐
      │   SQLite Database (db.py) │ │ Filesystem Content Cache  │   │ External Foundation Models  │
      │   content/edu_studio.db   │ │ content/topics/*.json     │   │ - Google Gemini (GenAI SDK) │
      │   (WAL Mode, Foreign Keys)│ │ content/notes/*.md        │   │ - ElevenLabs TTS (optional) │
      │   Profiles, Courses, Quiz │ │ content/catalog_cache/    │   │ - Google Search Grounding   │
      └───────────────────────────┘ └───────────────────────────┘   └─────────────────────────────┘
```

---

## 2. Component Boundaries & Responsibilities

| Component | Primary File(s) | Role & Responsibilities | Key Dependencies | Data Owned |
| :--- | :--- | :--- | :--- | :--- |
| **API Gateway & Orchestrator** | `server.py` | Request routing, auth verification, model fallback chains, rate limiting, event bus (`ui_events_queue`), and agent tool calling. | `fastapi`, `google-genai`, `uvicorn`, `pydantic` | In-memory event stream, in-memory job status, client rate buckets. |
| **Persistence Engine** | `db.py` | SQLite schema management, WAL journal initialization, profile sessions, courses, sequential classes, topic snapshots, and quiz attempts. | `sqlite3` (std library) | `content/edu_studio.db` tables: `users`, `sessions`, `courses`, `classes`, `lessons`, `quiz_attempts`. |
| **Pedagogical Engagement** | `engage.py` | Gamified positive engagement loop: XP ledger, daily goals, streak freezes, quests, 12 badges, and Leitner spaced-review scheduler. | `db.py` | Tables: `xp_events`, `engage_prefs`, `freeze_days`, `activity_results`, `review_items`. |
| **Language Acquisition & AI** | `src/components/LanguageLab.jsx`, `src/components/LanguageRoleplay.jsx`, `src/lib/langgrade.js`, `src/practice/language.jsx` | Gamified practice drills (translate, word bank, listen, speak), AI roleplay conversational partner with Web Speech API audio, and Socratic explain-answer tutoring. | Web Speech API, `src/lib/speech.js` | Browser localStorage preferences (`andedu_pron_lang`, roleplay history). |
| **Interactive History Engine** | `src/components/HistoryLab.jsx`, `src/components/HistoryCrisisLab.jsx`, `src/components/PrimarySourceLab.jsx` | Branching counterfactual decision dilemmas ("What If?"), primary source document interrogator with SHEG sourcing criteria, and chronological ordering challenges. | React 19, Lucide | Curated crisis decision trees, primary source document library. |
| **Academic Advisor & Semester Planner** | `advisor.py`, `advisor_chat.py`, `wm_advising.py` | University course catalog ingest (W&M focus), class section schedules, prerequisite dependency graphing (CNF tree), degree audit (W&M COLL curriculum + proficiencies), readiness diagnostics, topic expansion ontology, semester course planning with schedule conflict detection, and dynamic Studio course launch. | `db.py`, `server.py` | Tables: `catalog_courses`, `completed_courses`, `catalog_sections`, `semester_plans`. |
| **Student Notes & Scratchpad Engine** | `db.py`, `server.py`, `src/components/MathLab.jsx` | Unified student written notes synchronization across devices and persistent storage in SQLite, automatically injected into prompt context across Advisor, AGY Drawer, and Lesson Tutor. | `db.py` | Table: `student_notes`. |
| **Physics & Math Simulation Engine** | `simspec.py`, `src/simulations/SpecSim.jsx`, `src/lib/expr.js` | SimSpec v1 declarative specification validation and execution. Safe expression AST parser, 240Hz substepped physics solver, math widget kit. | Python `ast`, JS Pratt parser | Declarative SimSpec JSON (`kind: "particles"`, `"graph"`, `"math"`). |
| **Geometry & Free-Body Diagram Kit** | `simspec.py`, `src/simulations/GeometrySim.jsx`, `src/components/Md.jsx` | Declarative 2D geometric and free-body diagram simulation engine. Interactive force vectors with component decomposition, angles, rigid bodies, and inline Markdown notes rendering (` ```geometry ` and ` ```fbd `). | SVG, KaTeX, `expr.js` | Declarative Geometry JSON (`kind: "geometry"`, `"fbd"`). |
| **Chemistry Simulation Kit** | `chemspec.py`, `src/simulations/ChemSim.jsx` | ChemSpec v1 declarative specification validator and HTML5 Canvas simulations for kinetics, equilibrium, acid-base titration, gas laws, reaction coordinates, and radioactive decay. | `simspec.py` | ChemSpec JSON (`kind: "chem"`). |
| **Frontend Shell & Workspaces** | `src/App.jsx`, `src/components/*` | Seven-tab single page application (`home`, `physics`, `code`, `math`, `history`, `language`, `advisor`), theme provider, unified event poller. | React 19, Vite, KaTeX, Lucide | Local browser state, `localStorage` cached profiles/tokens. |
| **Code Studio & IDE** | `src/components/EduStudioIDE.jsx`, `src/lib/pyodide.js` | In-browser Python environment powered by WebAssembly (Pyodide), interactive coding puzzles, and Socratic mentor integration. | Pyodide, Web Workers | Browser-sandboxed code execution results, scratchpad buffers. |
| **MCP Integration** | `mcp_server.py` | Stdio Model Context Protocol (MCP) server translating agent tool calls to local backend REST calls and real-time screen events. | `urllib` (std library) | None (stateless proxy). |

---

## 3. Data Contracts & Schemas

### 3.1 Live Topic Specification (`content/topics/<id>.json`)
Every lesson in &.edu is stored on disk as a single canonical JSON file:
```json
{
  "id": "slug-kebab-case",
  "title": "Clean Lesson Title",
  "category": "Discipline / Domain",
  "difficulty": "Foundations | Intermediate | Advanced",
  "summary": "1-2 sentence overview for the student.",
  "cheatSheet": [
    { "label": "Constraint/Formula", "formula": "\\text{LaTeX without delimiters}" }
  ],
  "mermaid": "graph TD; A[\"State A\"] --> B[\"State B\"];",
  "markdownContent": "# Lesson Derivation\n\nFull text with LaTeX in $...$ and $$...$$.",
  "quiz": [
    {
      "id": "q1",
      "question": "Question prompt with $LaTeX$?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correctAnswer": 1,
      "hint": "Pedagogical hint.",
      "explanation": "Why option B is correct."
    }
  ],
  "practice": [
    { "type": "fill_blank", "prompt": "... ___ ...", "options": ["a", "b"], "answer": "a", "explanation": "..." },
    { "type": "order_steps", "prompt": "...", "steps": ["s1", "s2", "s3"], "explanation": "..." },
    { "type": "numeric", "prompt": "...", "answer": 4.2, "tolerance": 0.02, "unit": "m/s", "explanation": "..." },
    { "type": "true_false", "prompt": "...", "answer": false, "explanation": "..." },
    { "type": "code", "prompt": "...", "starter": "def f():...", "tests": "assert f() == 1", "solution": "...", "explanation": "..." },
    { "type": "draw", "prompt": "...", "criteria": ["criterion 1", "criterion 2"], "reference": "...", "background": "grid|axes|blank" }
  ],
  "simulation": {
    "version": 1,
    "kind": "particles | graph | math | chem",
    "title": "Interactive Simulation Title",
    "params": [
      { "name": "k", "label": "Spring constant", "min": 1, "max": 20, "value": 5, "step": 0.5, "unit": "N/m" }
    ]
  },
  "source": {
    "kind": "course",
    "courseId": "course-id",
    "courseTitle": "Course Title",
    "classSeq": 1,
    "classTotal": 5,
    "workspace": "math | code | lab | history | language | philosophy"
  }
}
```

#### 3.1.1 Practice item contract (all types)
- Every item needs `type`, `prompt` (non-empty: `normalize_practice` drops items without one), `explanation`, and a stable `id`
  (`p<n>`); XP refs are `<topicId>:<itemId>`, so ids must not change once a student has seen the item.
- Unknown or malformed items are dropped and reported as `warnings`; nothing is graded server-side except `draw`.
- Language types: `translate {source, answer, accepted?[<=6], lang, sourceLang?}`, `word_bank {answer, bank[4-14] ⊇ answer words}`,
  `listen_type {audio_text, lang, answer, accepted?}`, `listen_choose {audio_text, lang, options, answer ∈ options}`,
  `speak {target, lang, ipa?, translation?}`. `lang` is a BCP-47 tag from `src/lib/speech.js` `LANGUAGES`.
  `speak` is ungraded when the browser has no SpeechRecognition (skippable, no XP, no heart lost).
- One normalizer and one renderer per type, registered by type name: server `PRACTICE_NORMALIZERS` (server.py, also the
  `PRACTICE_TYPES` set, populated from `practice_general.py`, `practice_history.py`, `practice_language_extra.py`, `practice_philosophy.py`,
  and the 5 STEM kits: `practice_ee.py`, `practice_ai.py`, `practice_systems.py`, `practice_stats.py`, `practice_bio.py`), client `src/practice/registry.js`, which merges each subject file's map (`src/practice/language.jsx`,
  `src/practice/history.jsx`, `src/practice/general.jsx`, `src/practice/language_extra.jsx`, `src/practice/philosophy.jsx`). Server-side `PRACTICE_GRADERS` evaluate student submissions deterministically where physical, mathematical, or algorithmic ground-truth exists. Subject bodies take `{item, onResult(ok, given), retry}` (`ok === null` = skipped) so both
  `PracticeDeck` and subject practice views can use them. MCP tools follow the same split: `mcp_tools_<subject>.py` exports
  `tools(call, q, S, STR, OBJ, ARR)` and `mcp_server.py` merges them. Philosophy types (`truth_table`, `validity`, `syllogism`, `proof_steps`, `argument_map`, `spot_parts`, `fallacy_id`) have AI answers stripped and evaluated deterministically against `logic_engine.py`.
- STEM engineering types:
  - `practice_ee.py` (4 types): `circuit_dc_analysis` (KCL/KVL branch currents/voltages), `thevenin_equivalent` ($V_{\text{th}}, R_{\text{th}}$), `bode_cutoff_calc` ($f_c$, filter type), `opamp_gain_calc` ($A_v$, inverting/non-inverting).
  - `practice_ai.py` (4 types): `gradient_descent_step` ($w_{t+1} = w_t - \eta \nabla L$), `confusion_matrix_metrics` (Precision, Recall, $F_1$), `attention_score_calc` ($\text{softmax}(QK^T/\sqrt{d_k})$), `convolution_output_dim` ($\lfloor(W-K+2P)/S\rfloor+1$).
  - `practice_systems.py` (4 types): `pipeline_hazard_spot` (RAW stalls, forwarding), `cache_address_decode` (Tag, Set, Offset), `assembly_step_trace` (register/memory trace), `virtual_memory_translate` (VPN, offset, PA).
  - `practice_stats.py` (4 types): `p_value_decision` (critical rejection), `confidence_interval_calc` (margin of error), `bayes_posterior_calc` (Bayes rule), `regression_residual_audit` (residuals, leverage).
  - `practice_bio.py` (4 types): `dna_transcription_translate` (transcription/codon translation), `hardy_weinberg_calc` ($p, q, p^2, 2pq, q^2$), `enzyme_michaelis_menten` ($v_0 = V_{\max}[S]/(K_m+[S])$), `genomic_gc_content` (GC%, $T_m$).
- Languages session progress (word strength 0-4, crowns per unit, missed items) is per browser (localStorage keys
  `andedu_lang_*`); XP goes through the existing `practice_correct` source with ref `lang:<topicId>:<itemId>`.

#### 3.1.2 Workspace sub-tab event
`SWITCH_STUDIO_MODE {mode, tab?, sessionMode?, unitId?}` opens a workspace (`history`, `language`, `math`, ...) and optionally one of its sub-tabs.
For `language`, `tab: "session"` starts a practice session (`sessionMode` mixed | missed | listen | speak | new | unit).
`SWITCH_TAB {tab}` stays reserved for the topic viewer's tabs (theory, quiz, simulation, ...) and always lands in Lab.

### 3.2 SimSpec & Math Expression Grammar Contract (Desmos Parity)
Mathematical expressions across declarative simulations (`simspec.py`), the client safe evaluator (`src/lib/expr.js`), and server math practice verification (`server.py:safe_arith`) follow a shared grammar:
- **Operators**: `+`, `-`, `*`, `/`, `%`, `^` (or `**`), unary `+`/`-`, comparisons `<`, `<=`, `>`, `>=`, `==`, `!=`.
- **Constants**: `pi`, `PI`, `tau`, `TAU`, `e`, `E`, `phi`, `PHI` ($1.6180339887...$), `inf`, `infinity`, `Infinity`.
- **Trigonometric & Reciprocal / Inverse**:
  - Direct: `sin`, `cos`, `tan`
  - Reciprocal: `csc`, `sec`, `cot`
  - Inverse: `asin`, `arcsin`, `acos`, `arccos`, `atan`, `arctan`, `atan2`
  - Reciprocal Inverse: `acsc`, `arccsc`, `asec`, `arcsec`, `acot`, `arccot`
- **Hyperbolic & Reciprocal / Inverse**:
  - Direct: `sinh`, `cosh`, `tanh`
  - Reciprocal: `csch`, `sech`, `coth`
  - Inverse: `asinh`, `arcsinh`, `acosh`, `arccosh`, `atanh`, `arctanh`
  - Reciprocal Inverse: `acsch`, `arccsch`, `asech`, `arcsech`, `acoth`, `arccoth`
- **Roots, Powers & Exponentials**:
  - `sqrt`, `cbrt`, `nthroot(x, n)` (real odd roots supported for $x < 0$), `exp`, `pow`
- **Logarithms**:
  - `ln` (natural log), `log10` (common log), `log2` (binary log)
  - `log(x, [b])`: 1 argument yields $\ln(x)$ (backwards compatible with existing topics); 2 arguments yields $\log_b(x) = \frac{\ln x}{\ln b}$
- **Rounding, Clamping & Number Theory**:
  - `abs`, `sign` / `sgn`, `floor`, `ceil`, `trunc`
  - `round(x, [precision])` (rounds to $10^{-\text{precision}}$)
  - `clamp(v, lo, hi)`
  - `mod(a, b)` (Euclidean floored modulo matching math/Desmos)
  - `gcd(a, b)`, `lcm(a, b)`
  - `hypot(a, b)`
- **Combinatorics, Statistics & Special Functions**:
  - `fact(n)` / `factorial(n)` (exact integer factorial up to 170; falls back to $\Gamma(n+1)$ for non-integers)
  - `nPr(n, r)` / `perm(n, r)`, `nCr(n, r)` / `comb(n, r)`
  - `erf(x)` (error function via rational Chebyshev / Abramowitz & Stegun approximation)
  - `gamma(x)` (Lanczos approximation with reflection formula)
  - `sinc(x)` (unnormalized $\frac{\sin x}{x}$, with $\text{sinc}(0) = 1$)
  - `step(x)` / `heaviside(x)` ($0$ for $x < 0$, $1$ for $x \ge 0$)
  - `rect(x)` ($1$ for $|x| \le 0.5$, $0$ otherwise)
  - `if(cond, a, b)` (conditional evaluation helper)
- **Security & Integrity Constraint**: Zero JavaScript `eval()` or `new Function()`. Expressions parse directly into closure trees via a recursive-descent Pratt parser. Server side is validated via Python AST node allowlist.

#### 3.2.1 MathLab Component & Tooling Architecture (`src/components/MathLab.jsx`)
MathLab exposes Desmos-equivalent graphing and analysis tools with three modular components:
1. **Interactive Graph Engine (`GraphTab`)**:
   - Multi-curve renderer (color palette rotation from theme tokens) with vertical asymptote/discontinuity detection and **even-order pole detection**: detects vertical asymptotes where the curve sign does not flip (e.g. $f(x) = \frac{1}{(x-2)^2}$, $\sec^2 x$) via reciprocal-zero test ($g(x) = 1/f(x) \to 0$) and second-difference curvature divergence guards ($\Delta^2 y_k$), preventing spurious canvas-wide bridge lines.
   - Interactive numerical calculus: exact machine-precision derivatives via **Dual-Number Jet2 Automatic Differentiation** (`src/lib/dual_autodiff.js`), computing $f(x)$, $f'(x)$, and $f''(x)$ on Pratt AST closures without finite-difference cancellation. Tangent line cursor tracking, definite integration $\int_a^b f(x)\,dx$ (Simpson's rule), root finding (bisection with pole filtering), and local extrema classification via $f''(x)$ sign.
   - Canvas View Controls Overlay: Quick Zoom In (`+`), Zoom Out (`-`), and Reset Home (`Crosshair`) floating buttons on the graph canvas.
2. **Values Table Tool (`ValuesTable`)**:
   - Bidirectional $x \to y$ table generator for the active curve.
   - Plots discrete scatter probe points directly on the canvas with coordinate tooltips.
3. **On-Screen Math Keypad (`MathKeypad`)**:
   - Multi-tab virtual keypad (`123` basic/algebraic, `Trig` trigonometric/inverse/hyperbolic, `Func` calculus/stats/special).
   - Non-blurring insertion (`onMouseDown={e => e.preventDefault()}`) targeting the active formula input, calculator input, or notebook editor.


### 3.3 Course Advisor & Degree Audit Data Contracts
- **Prerequisite AST & CNF Interop (`advisor_rules.py`)**: While basic course prerequisites maintain legacy Conjunctive Normal Form (AND of OR-choice groups: `List[List[str]]`), full degree audits evaluate typed AST requirement nodes:
  - `course`: `{type: "course", code: str, min_grade: str}` (evaluates passing grade or minimum letter threshold).
  - `all`: `{type: "all", children: List[ReqNode]}` (logical AND: all sub-requirements must be satisfied).
  - `any`: `{type: "any", children: List[ReqNode]}` (logical OR: at least 1 sub-requirement must be satisfied).
  - `k_of_n`: `{type: "k_of_n", k: int, children: List[ReqNode]}` (cardinality: at least $k$ sub-requirements satisfied).
  - `credit_pool`: `{type: "credit_pool", min_credits: float, pool: List[str], dept: str, min_level: int}` (credit accumulation pool, e.g. 12 credits of 300+ CSCI electives).
  - `min_grade`: `{type: "min_grade", code: str, min_grade: str}`.
- **Degree Audit Templates**:
  - `WM_CS_BS_TEMPLATE`: 120 credits total, COLL curriculum, Math core (`MATH 111, 112, 109/211`), CS core (`CSCI 141, 241, 243/MATH 214, 301, 303, 304, 312, 423, 400`), and 12 credits of upper-level CS electives.
  - `WM_DATA_SCIENCE_BS_TEMPLATE`: 120 credits, COLL curriculum, DATA core (`DATA 101, 141, 201, 301, 400`), Math/Stats (`MATH 111, 112, 109/211, 351/451`), and 15 elective credits.
  - `COLUMBIA_32_COMBINED_PLAN_TEMPLATE`: Foundational pre-engineering curriculum spanning Math (Calc I-III, Linear Algebra, ODEs), Physics (Mechanics + Lab, E&M + Lab), Chemistry (Gen Chem + Lab), CS (`CSCI 141`), Economics (`ECON 101/102`), and Writing (`COLL 150`), plus discipline-specific engineering track add-ons.
- **Readiness Contract (`/api/advisor/{user_id}/readiness/{code}?crn=&term=`)**:
  ```json
  {
    "code": "CSCI 241",
    "found": true,
    "title": "Data Structures",
    "prereqs": "CSCI 141 and (MATH 111 or MATH 131)",
    "prereq_codes": ["CSCI 141", "MATH 111", "MATH 131"],
    "prereq_tree": [["CSCI 141"], ["MATH 111", "MATH 131"]],
    "missing": ["MATH 111 or MATH 131"],
    "missing_codes": ["MATH 111", "MATH 131"],
    "met": false,
    "status": "met | missing | check | none | unknown",
    "taken": false,
    "basis": "course | section",
    "crn": "",
    "term": "202720",
    "section_note": "",
    "concurrent_ok": [],
    "concurrent": [],
    "score_options": [{"group": "MATH 111 or MATH 131", "options": [{"test": "AP Calculus BC", "min": 4, "kind": "test"}]}],
    "required_alts": [],
    "term_ignored": false
  }
  ```
  - `status: "none"`: Course has no prerequisites (explicit none or introductory level < 300).
  - `status: "unknown"`: 300+ course with empty prerequisite field in catalog data; `met` evaluates to `false` preventing false-positive recommendations. Only on `basis: "course"`.
  - `status: "check"` (`met: false`): what is missing could only be satisfied by a test score, PATH equivalency/exemption/placement flag or admission, or one of those is required on its own. No student scores are stored, so it is never verified. `score_options` lists, per missing group (`group` = the `missing` string), the options PATH accepts (`kind` test for AP/IB/CLEP/SAT/ACT, admission for "Admitted to ...", else equivalent; the lowest `min` per name); `required_alts` the ones required outside any OR (EDUC 311: "minimum score of 1 in 'Admitted to SOE-Secondary', EDUC 301 and 310"). Status is missing when some missing group has no option. From `advisor.parse_prereq_scores` (cached, immutable), which follows `parse_prereq_cnf`'s groups exactly: `prereq_tree` / `prereq_codes` are unchanged, and when the text's groups don't match the stored tree (or the 64-clause fallback fired) no options are given. `recommend()` keeps only `met: true`, so check courses are left out.
  - Per-section rule (`advisor.prereq_rule` / `section_rule`): PATH lists a section's own prerequisites as the first `details.restrictions` line starting `Prerequisite(s)`, and sections of one course can disagree (DATA 440: DATA 301 vs DATA 201). With `crn`, that line decides when it names a course (`basis: "section"`; `prereqs` / `prereq_codes` / `prereq_tree` are the section's, `course_prereqs` / `course_prereq_tree` the course's). A section without that line uses the course rule; one whose line names no course (e.g. "minimum score of 1 in 'Admitted to SOE-Secondary'") uses the course rule with the line in `section_note`.
  - `concurrent_ok`: codes PATH marks "* May be taken concurrently". They stay in the CNF (before or alongside); the endpoint and the planning cart count one as met when it is in that term's primary cart (`advisor_cart.primary_codes`), listing it in `concurrent`.
  - `term` defaults to the cart's default (next) term and is echoed. With `crn`: 400 for a malformed term or a CRN of another course, 404 for a CRN not listed in that term. Without `crn` a malformed term is ignored: 200 with `term: ""`, `term_ignored: true` and no cart counted.
  - Planning cart (`advisor_cart.get`): each section carries `prereq_basis`, `prereq_status` (same vocabulary), `prereq_missing`, `prereqs` (the section's text only when its CNF differs from the course's), `prereq_note`, `concurrent`, `concurrent_ok`, `score_options`, `required_alts`, `score_alternative` (the text names a score), `grade_minimum`, `consent` (bool), `consent_kind` (Instructor Approval, Department Chair Approval, Dean/Director Approval, any other value as "Approval"; never the raw text); the item carries `course_prereq` (the same fields for the course rule) and `sections_differ`. `prereq_missing` (status missing) or `prereq_check` (status check) in `flags` is judged on the chosen section (else the course rule). Raw `details` never leave the server.
- **Degree Audit Contract (`/api/advisor/{user_id}/degree-audit`)**:
  Computes William & Mary College Curriculum (COLL 100, 150, 200, 300, 400) and Proficiencies (Mathematics, Arts):
  ```json
  {
    "user_id": "u1",
    "school": "wm",
    "total_credits": 28.0,
    "completed_count": 8,
    "coll": {
      "coll100": { "name": "COLL 100", "title": "Big Ideas", "required": 4, "earned": 4.0, "likely": 0.0, "met": true, "courses": ["APSC 100"] },
      "coll150": { "name": "COLL 150", "title": "First-Year Seminar", "required": 4, "earned": 4.0, "likely": 0.0, "met": true, "courses": ["HIST 150W"] },
      "coll200": { "name": "COLL 200", "title": "Exploring Foundations", "required": 12, "earned": 12.0, "likely": 3.0, "alv": 3.0, "csi": 3.0, "nqr": 3.0, "met": true, "courses": [...] },
      "coll300": { "name": "COLL 300", "title": "In the World / Global", "required": 3, "earned": 0, "likely": 0.0, "met": false, "courses": [] },
      "coll400": { "name": "COLL 400", "title": "Capstone in Major", "required": 3, "earned": 0, "likely": 0.0, "met": false, "courses": [] }
    },
    "proficiencies": {
      "math": { "name": "Mathematics", "met": true, "courses": ["MATH 111"] },
      "arts": { "name": "Creative & Performing Arts", "met": false, "courses": [] }
    },
    "all_coll_met": false,
    "overall_met": false
  }
  ```
- **W&M COLL Numbering Rules (`coll_by_number`)**:
  - `CODE_RE` grammar: `\b([A-Z]{2,5})\s?-?\s?([A-Z]?\d{3}[A-Z]{0,2})\b` handles prefix letters (`S150` summer session) and standard suffixes (`150W`, `495`, `496`, `300D`).
  - `100` -> `COLL 100` (Departmental Big Ideas courses).
  - `150`, `150W`, `S150` -> `COLL 150` (Departmental First-Year Seminars).
  - `400`, `495`, `496` -> `COLL 400` (Senior Capstone & Departmental Honors Thesis).
  - *Domain Guard*: Number `300` is **not** an automatic COLL 300 rule because departmental 300-level courses (`MATH 300`, `ECON 300`, `BUAD 300`, `THEA 300`) are standard junior coursework/writing courses. COLL 300 requires explicit cross-cultural/global designation (`COLL 300` prefix, official attribute, or verified classification).
- **Academic Advisor Chat Contract (`POST /api/advisor/{user_id}/chat` & `/ask`)**:
  - Socratic, conversational advising grounded strictly in student record and catalog data.
  - Term and program knowledge (`wm_advising.py`): `next_term()` picks the term a student means by "next semester"
    (the earliest `WM_CALENDAR` term whose add/drop is still open, else the next fall/spring by academic-year code:
    YYYY10 = Fall YYYY-1, YYYY20 = Spring YYYY). `build_context` puts `term_context()` right after the CATALOG line so
    truncation never drops it, and lists that term's sections first. `programs_context()` adds every CS and Data
    Science major/minor with all tracks and how they differ when the question or the student's record involves them.
  - `WM_PROGRAMS` / `WM_CALENDAR` are transcribed by hand from the official catalog (catalog.wm.edu) and the
    registrar's undergraduate calendar; they live inline in `wm_advising.py` so they ship with the Dockerfile's `.py`
    copy. Refresh once per catalog year: update `CATALOG_YEAR`, `CATALOG_AS_OF`, each program, and add the coming
    terms' dates (without them the advisor says dates are not loaded rather than guessing). Tests: `tests/test_wm_programs.py`.
  - Request: `{"message": str (1-2000 chars), "history": [{"role": "user"|"advisor", "content": str}]}`
  - Response:
    ```json
    {
      "reply": "Markdown text with empathetic Socratic guidance, prerequisite check citations, and one guiding next-step question.",
      "courses": ["CSCI 241", "MATH 211"],
      "suggested_courses": [
        {
          "code": "CSCI 241",
          "title": "Data Structures",
          "credits": 3,
          "prereqs_met": true,
          "missing_prereqs": [],
          "attributes": ["NQR"],
          "sections_available": 3
        }
      ]
    }
    ```
- **Catalog Classification Contract (`POST /api/advisor/catalog/classify`)**:
  - Dual-phase classification pipeline:
    1. Deterministic Rule Classifier (`rule_classify_courses`): Department domain mapping (`ALV`, `CSI`, `NQR`), proficiencies (`MATH`, `ARTS`), and catalog text regexes. Zero model cost.
    2. Model Classifier (`ai_classify_courses`): Batches unmarked courses (40/call) using Gemini `role="planner"`. Capped at 20 calls/job run to protect `SCIEDU_DAILY_MODEL_CALLS` (400/day).
  - Content Hash Change Detection: `inferred_hash` = SHA-256 of `f"{title}|{description}|{prereqs}"`. Unchanged courses are skipped automatically.
  - Whitelist: Only valid W&M attributes allowed (`ALV`, `CSI`, `NQR`, `COLL 200`, `COLL 300`, `MATH`, `ARTS`). Confidence clamped to `[0.0, 1.0]`.
  - Academic Integrity: Official catalog `attributes` are immutable. Inferred tags reside in `inferred_attributes` and contribute solely to `likely` credits, never marking degree requirements as `met: true`.

### 3.4 Language Acquisition & AI Specification
The language acquisition system pairs gamified formative drills with AI capabilities (Roleplay conversation partner and Socratic answer explanations).

#### 3.4.1 Practice Drill Contracts
All language drill types are validated server-side by `PRACTICE_NORMALIZERS` and rendered via `src/practice/language.jsx`:
1. `translate`: `{type: "translate", prompt, source, answer, accepted: [alt1, ...], lang, sourceLang, explanation}`. Evaluated via `gradeText` in `src/lib/langgrade.js` with accent leniency and typo tolerance.
2. `word_bank`: `{type: "word_bank", prompt, source?, answer, bank: [w1, w2, ...], lang, explanation}`. Sentence chip scramble where `bank` is a superset of answer tokens (4-14 chips). Evaluated via normalized token order.
3. `listen_type`: `{type: "listen_type", prompt, audio_text, answer, accepted: [...], lang, explanation}`. Native Web Speech synthesis with standard (0.9x) and turtle (0.55x) playback buttons. Evaluated via fuzzy text match.
4. `listen_choose`: `{type: "listen_choose", prompt, audio_text, options: [opt1, ...], answer, lang, explanation}`. Audio comprehension multiple-choice selector.
5. `speak`: `{type: "speak", prompt, target, ipa?, translation?, lang, explanation}`. Speech recognition pronunciation check via Web Speech API; match score computed via normalized Levenshtein similarity (≥80% passing). Skips gracefully on browsers lacking SpeechRecognition.

#### 3.4.2 Roleplay AI Contract (`POST /api/language/roleplay`)
Conversational simulation partner with grammar critique and natural phrasing suggestions:
- **Request**:
  ```json
  {
    "scenario": "Ordering food at a Parisian café",
    "target_lang": "fr",
    "user_message": "Je voudrais un croissant et un café, s'il vous plaît.",
    "history": [
      { "role": "assistant", "content": "Bonjour ! Bienvenue au Café Flore. Que puis-je vous servir ?" }
    ],
    "level": "A2"
  }
  ```
- **Response**:
  ```json
  {
    "reply": "Très bon choix ! Voulez-vous le croissant chaud ?",
    "translation": "Very good choice! Would you like the croissant warmed up?",
    "feedback": {
      "has_corrections": false,
      "corrections": [],
      "tip": "Parfait ! 'Je voudrais' est très poli et naturel."
    },
    "suggested_replies": [
      "Oui, chaud s'il vous plaît.",
      "Non merci, ça va comme ça.",
      "Combien ça coûte en tout ?"
    ]
  }
  ```

#### 3.4.3 Explain My Answer Contract (`POST /api/tutor/explain-answer`)
Detailed linguistic explanation of why a selected answer is right or wrong:
- **Request**: `{"question": str, "student_answer": str, "correct_answer": str, "context": str, "lang": str}`
- **Response**:
  ```json
  {
    "verdict": "incorrect",
    "explanation": "Markdown pedagogical explanation breaking down root grammar rules, verb conjugation patterns, or false friends.",
    "key_rule": "Conjugation of 'aller' in present tense: ils/elles vont (not 'va').",
    "example": "Elles vont au marché le samedi."
  }
  ```

### 3.5 Interactive History Decision Engine & Primary Source Interrogator

#### 3.5.1 Branching Crisis Decision Simulator (`GET`/`POST /api/topics/{topic_id}/crisis` & `src/components/HistoryCrisisLab.jsx`)
Simulates pivotal historical turning points where students make critical policy choices:
- **Schema**:
  ```json
  {
    "id": "cuban-missile-crisis",
    "title": "Cuban Missile Crisis (October 1962)",
    "role": "President John F. Kennedy",
    "setting": "U-2 spy planes discover Soviet nuclear missile sites under construction in Cuba.",
    "state": { "tensions": 80, "allies": 70, "public_support": 85 },
    "options": [
      {
        "id": "quarantine",
        "label": "Impose a Naval Quarantine / Blockade",
        "consequence": "Buys critical diplomatic time while projecting decisive strength.",
        "real_history": "Historically chosen by JFK on October 22, 1962, leading to the secret Jupiter missile compromise.",
        "next_dilemma": "Soviet transport ships approach the quarantine perimeter. Do we board or hold fire?"
      },
      {
        "id": "airstrike",
        "label": "Immediate Tactical Airstrikes on Missile Sites",
        "consequence": "High risk of Soviet casualties triggering a retaliatory strike on West Berlin or tactical nuclear escalation in Cuba.",
        "real_history": "Advocated by the Joint Chiefs of Staff (Gen. LeMay); rejected by Kennedy due to high uncertainty."
      }
    ]
  }
  ```

#### 3.5.2 Primary Source Document Interrogator (`src/components/PrimarySourceLab.jsx`)
Interactive document lab applying the Stanford History Education Group (SHEG) sourcing framework:
- **Schema**:
  ```json
  {
    "id": "magna-carta-1215",
    "title": "Magna Carta (1215), Clause 39",
    "author": "English Barons and King John of England",
    "date": "June 15, 1215",
    "text": "No free man shall be seized or imprisoned... except by the lawful judgment of his equals or by the law of the land.",
    "annotations": [
      { "target": "No free man", "note": "In 1215, 'free men' represented roughly 10-20% of the population; serfs and unfree peasants were excluded." }
    ],
    "sourcing_questions": [
      {
        "criterion": "sourcing",
        "question": "What motivated the barons to demand this clause in 1215?",
        "model_answer": "King John had repeatedly seized lands and extorted feudal dues without customary consultation."
      }
    ]
  }
  ```

### 3.6 Privacy: Consent, Export & Delete Contracts
- `db.USER_DATA_TABLES` is the registry of per-user tables (besides `users`, `courses`, `classes`, `lessons`,
  `sessions`); `tests/test_privacy.py` fails if a table with a `user_id` column is missing from it.
- `GET /api/users/{id}/export` (owner only): `{format:"andedu-export", version:1, exportedAt, user, courses
  (with classes), lessons, tables, consent, topics, notes, quizLog}` as a JSON download. Never includes password
  or session hashes, or rows with no owner.
- `POST /api/auth/delete-account` (accounts: `{confirmName, password}`) / `POST /api/users/{id}/delete` (local:
  `{confirmName}`): 422 name mismatch, 401 wrong password, 409 admin id. Accounts on this computer (5.5): only the
  admin deletes accounts (403 otherwise), any of them (`userId`, or the path id; 400 if they differ), confirmed by
  the account's name and the admin's own password if it has one; the admin deletes itself only with `transferTo`
  (409 without it, unless it is the last account): the role moves first, then the delete runs. Removes the user's course topic files and
  notes, every per-user row (one transaction), their quiz-log lines and in-memory jobs/events.
- `POST /api/users/{id}/consent {kind:"privacy"|"upload"}`; register needs `privacy: true`; login returns
  `privacyAccepted` (against `PRIVACY_VERSION`); `/api/status` returns `privacy_version`.
- Upload consent (accounts mode): 428 before uploaded images or scanned PDFs, or files used to plan a course, go
  to Gemini, until upload consent is recorded. Columns: `users.privacy_version`, `privacy_accepted_at`,
  `upload_consent_at`.

### 3.7 Declarative Geometry & Free-Body Diagram Kit (`kind: "geometry"`)
The geometry simulation kit provides a reactive 2D vector and apparatus engine for mechanics, statics, and geometry. Specs are declarative JSON validated server-side by `simspec.py:validate_geometry` and executed client-side via SVG in `src/simulations/GeometrySim.jsx`.

- **Schema Fields**:
  - `kind`: `"geometry"` or `"fbd"`
  - `title`: Short title (≤100 chars)
  - `description`: Explanatory walkthrough (≤600 chars)
  - `params`: Array of interactive slider objects `[{name, label, min, max, value, step, unit}]`
  - `view`: Coordinate window `{xmin, xmax, ymin, ymax, grid: bool, axes: bool}`. Default `xmin: -5, xmax: 5, ymin: -4, ymax: 4`. $+x$ is right, $+y$ is up.
  - `bodies`: Physical apparatus shapes `[{id, type, x, y, width?, height?, radius?, angle?, color?, fill?, label?}]`. Supported types: `box`, `wedge` / `ramp`, `sphere` / `circle`, `rod`, `wall` / `surface`, `pulley`, `point`.
  - `forces`: Force vectors `[{id, body?, origin: [x, y]|"center", angle, magnitude, label, color?, projections: bool}]`. Dynamic expressions evaluate live with parameter sliders. `projections: true` renders dashed orthogonal components ($F_\parallel$, $F_\perp$ or $F_x$, $F_y$).
  - `elements`: Geometric construction primitives: `line` (with optional arrow/dash), `angle_arc` (with angle label $\theta$), `right_angle` (perpendicular marker), `dimension` (measurement arrows), and `polygon`.
  - `axes`: Optional tilted or local coordinate axes `{x, y, angle, xLabel, yLabel}`.
- **Deterministic FBD Vector Grader (`fbd_grader.py` & `/api/draw/check`)**:
  - `POST /api/draw/check` accepts optional `shapes: List[Dict]` from `DrawingBoard.jsx` and `fbd_spec: Dict` (either in the payload or attached to the practice item).
  - When arrow shapes are present and an `fbd_spec` is defined, `fbd_grader.grade_fbd(...)` grades the drawing deterministically in Python without invoking vision LLMs:
    - Arrow tails verified against `body_origin` within `origin_tol_px` (default $40\text{ px}$).
    - Vector Cartesian angles $\theta = \operatorname{atan2}(-(y_2-y_1), x_2-x_1) \pmod{360^\circ}$ verified within $\pm 5^\circ$.
    - Text shapes within $50\text{ px}$ of the arrow tip or midpoint are deterministically associated as vector labels.
    - Relative magnitude comparisons (e.g. $F_N = mg$, $F_{\text{friction}} < F_{\text{applied}}$) and forbidden forces (e.g. centrifugal force in inertial frames) verified.
  - LLM vision grading (`acall_gemini`) is preserved strictly as an opt-in fallback when vector shapes or FBD physical specifications are absent.
- **Embedded Notes Rendering**: `src/components/Md.jsx` intercepts fenced code blocks marked ````geometry` and ````fbd`, compiling them via `GeometrySim` directly inside student lesson notes.

### 3.8 KaTeX Vector Typography & Normalization Contract
KaTeX math rendering in `src/components/Md.jsx` and server text normalizers in `server.py:repair_latex` adhere to standard mathematical physics vector conventions:
- **KaTeX Options**: `rehype-katex` is configured with `throwOnError: false` and strict macro definitions:
  - `\ihat` -> `\hat{\imath}` (dotless $i$ with circumflex)
  - `\jhat` -> `\hat{\jmath}` (dotless $j$ with circumflex)
  - `\khat` -> `\hat{k}`
  - `\uvec{x}` -> `\mathbf{\hat{x}}`
- **Regex & Unicode Caret Repair**: Combining characters (`î`, `ĵ`, `k̂`, `ı̂`, `ȷ̂`), raw carets (`i^`, `j^`, `k^`), and standard caret forms (`\hat{i}`, `\hat{j}`) are normalized client- and server-side to `\hat{\imath}`, `\hat{\jmath}`, `\hat{k}` to avoid visual dot collisions and parse failures.
- **Formula Auto-Detection**: `LATEX_NAMES` regex in `Md.jsx` includes `ihat`, `jhat`, `khat`, `imath`, `jmath`, `uvec`, ensuring vector formulas without explicit delimiters are recognized as math and wrapped in `$...$`.

### 3.9 Semester Course Planning & Dynamic Studio Launch Contract
The semester planning engine enables multi-course semester schedule synthesis, live credit metering, time conflict analysis, and dynamic studio conversion:
- **Persistence Schema (`semester_plans`)**:
  - `id`: Unique plan identifier (`plan-<uuid>`)
  - `user_id`: Owning student foreign key
  - `term`: Target registration term code (e.g. `202620` for Spring 2026)
  - `term_name`: Human-readable term label (e.g. `Spring 2026`)
  - `title`: Plan title / strategy theme
  - `target_credits`: Planned target credit total (default `15.0`)
  - `courses_json`: Serialized array of `CoursePlanItem` records:
    - `code`: Course code (e.g. `PHIL 231`)
    - `title`: Course title
    - `credits`: Fractional or integer credit count (e.g. `3.0`)
    - `crn`: Section CRN for next-term registration
    - `section`: Section number (e.g. `01`)
    - `meets`: Human readable meeting schedule (e.g. `TR 11:00am - 12:20pm`)
    - `instructor`: Primary instructor name
    - `fulfills`: Degree / interest attribution (e.g. `COLL 200 ALV · Stoic Interest`)
    - `rationale`: Why this course was selected
    - `studio_course_id`: Associated active EduStudio course ID once launched
  - `notes`: High-level strategic rationale and degree impact summary
  - `status`: `draft` | `active`
- **Schedule Conflict Detector**: `wm_advising.py:check_schedule_conflicts(courses)` evaluates section day/time strings, identifying pairwise time overlaps.
- **Dynamic Studio Launch ("does more as you go")**: `POST /api/advisor/{user_id}/launch-course` converts a planned course into an active EduStudio course by populating `materials_text` from catalog descriptions and syllabi, initiating an asynchronous diagnostic and 4-class lesson generation job via `start_plan_job()`.

### 3.10 Student Written Notes & Cross-Agent Synchronization Contract
Ensures student notes from the notebook, IDE, and advisor scratchpads are persistently stored and accessible to all AI agents:
- **Persistence Schema (`student_notes`)**:
  - `user_id`: Owning student primary key
  - `notes_text`: Markdown and LaTeX content
  - `updated_at`: Unix timestamp of last update
- **Sync Endpoints**:
  - `GET /api/users/{user_id}/notes`: Retrieves latest saved notes.
  - `PUT /api/users/{user_id}/notes`: Upserts student notes with debounced client synchronization (800ms).
- **Cross-Agent Injection**:
  - **Advisor Chat**: Injected inside `advisor_chat.py:build_context` under `STUDENT'S WRITTEN NOTES & STUDY SCRATCHPAD`.
  - **AGY Companion**: Injected into `server.py:agy_prompt` context.
  - **Lesson Tutor**: Injected into `server.py:lesson_tutor` system instruction.

### 3.11 Universal Web Search Grounding & Reasoning Engine
All Gemini interactions via `server.py:call_gemini` and `acall_gemini` feature automated capability injection and fallback resilience:
- **Dynamic Reasoning**: `types.ThinkingConfig(thinking_budget=-1)` (or `SCIEDU_THINKING_BUDGET`) enables deep reasoning on complex academic requests.
- **Web Search Grounding**: `types.Tool(google_search=types.GoogleSearch())` provides live web search.
- **MIME & Tool Exclusions**: Grounding is strictly bypassed when `response_mime_type == "application/json"` or when `tool_config` specifies function calling `mode="ANY"`, preventing HTTP 400 API validation errors.
- **Circuit Breaker**: per key (`grounding_paused_until` in the key's model state). Search added automatically by `call_gemini`: a quota or tool error (429, quota, search, tool, grounding, conflict) pauses search for 1800 s and retries the same call without it. `grounded_json(prompt, role="planner")` (answer checks, PHILIN): a quota or tool error (`_grounding_quota_error`) pauses search for 3600 s and the error passes through, with no ungrounded retry; a timeout, a 5xx, the daily budget (`BudgetExhausted`) or a rejected key (`KeyRejected`) does not pause it. While paused, it raises `GroundingPaused`; `grounding_paused()` asks without calling.

### 3.12 PHILIN & Layer 2 Philosophy Engine (`philin.py`, `logic_engine.py`, `practice_philosophy.py`, `logic_ast.py`)
- `POST /api/philin/transcribe {text ≤ 8000}`: structured extraction pipeline (planner model, temperature 0) converting input text into an argument graph with strict epistemic safeguards:
  - **Verbatim Spans & Context Verification (`inspect_quote_context`)**: Extracts verbatim `quote` with character offsets `span: [start, end]` and speaker attribution (`attribution`: `author_assertion` | `quoted_target` | `supposition`). Replaces simple pre-span regex with bidirectional clause-bounded scanning (up to 80 chars left and 45 chars right, respecting clause delimiters `[.;!?\n]`). Accounts for German verb-final negation syntax (`nicht`, `keineswegs`, `nie`, `bestreitet`, `leugnet`) and preserves litotes double negation by evaluating token polarity parity (`count % 2 == 1` flags inverted/severed context; even count preserves affirmative polarity).
  - **Three-Rule Epistemic Firewall for Thick Concepts**: Any sentence containing thick ethical-descriptive concepts (e.g. *exploitation*, *natural function*, *cruel*, *legitimate*, *tyrannical*, *fair*) is decomposed into distinct atomic blocks: an `empirical` block capturing verifiable behavior/state and a `normative` block capturing the value judgment. Each block explicitly extracts `predicates: List[str]`. Descriptive blocks are forbidden from carrying normative predicates; normative blocks are never classified as empirical or logical.
  - **Atomic Claim Decomposition**: Compound sentences mixing empirical assertions and evaluative judgements are split into distinct atomic claim blocks: one `empirical` and one `normative`.
  - **Strict Epistemic Neutrality**: Axioms and values across all moral and political philosophies (humanist, utilitarian, egalitarian, libertarian/property, socialist/labor, divine command/scriptural) are enforced as `normative` or `unfalsifiable`, never `empirical` or `logical`. `empirical` is strictly reserved for statements verifiable by sensory data, records, or scientific observation; `logical` is strictly reserved for tautologies and definitions.
  - **Enthymeme & Bridge Premise Integrity**: The model is forbidden from silently inserting unstated charitable bridge premises into `formal`. If an argument is an enthymeme, stated premises carry only verbatim logical translations, while necessary unstated assumptions are explicitly isolated in `missing_premise`.
- `POST /api/philin/check {argument, source?}`: purely deterministic Python evaluation combining `logic_argmap`, `logic_forms`, `logic_syllogism`, and `logic_ast`:
  - **Unified Predicate-Syllogistic AST (`logic_ast.py`)**: Defines `Term(name, is_singular)` and `CategoricalNode(type, subject, predicate)`. Compiles categorical statements to Calgary First-Order Logic (FOL) via `to_calgary_fol()`. Recognizes individual proper names (e.g. "Sherlock", "Socrates") as carrying existential import ($\exists x (x = a)$), preventing false-positive `existential_fallacy` flags in Boolean syllogism evaluation (e.g. Darapti AAI-3 with singular middle terms).
  - **Categorical Syllogisms**: Evaluates standard-form categorical syllogisms (e.g. AAA-1 Barbara, EAE-1 Celarent) natively in Python via `logic_syllogism.py` under boolean (default) or Aristotelian existential import, reporting rule violations (`undistributed_middle`, `illicit_major`, `illicit_minor`, etc.) without artificial propositional workarounds.
  - **Propositional Forms & Fallacies**: Checks validity via truth-table evaluation; matches named inference rules (Modus Ponens, Disjunctive Syllogism) and formal fallacies (Affirming the Consequent, Denying the Antecedent).
  - **Hume's Guillotine & Prior's Paradox Safeguard (`is_ought_gap`)**: Deterministically traces the directed support dependency graph. Guards against A.N. Prior's Paradox by requiring **Term-Bound Normative Grounding**: a normative conclusion not only requires at least one normative premise in its ancestral support chain, but the normative predicates in the conclusion must have a non-empty intersection with the normative predicates of its ancestral normative premises ($\text{predicates}(C) \cap \bigcup \text{predicates}(A) \neq \emptyset$). Disjoint leaps or vacuous normative premises are flagged with `is_ought_gap: true`.
  - Returns `status` (`valid` | `invalid` | `unchecked`), `inferences`, `findings`, `undecidable`, `quote_problems`, and `context_severed`.
- `POST /api/philin/factcheck {claims ≤ 6: [{id, text, kind}], regenerate?}`: empirical claims only (others return in `skipped`). Dual-pass independent Google Search grounding (planner and lesson roles); agreement combines verdicts at lower confidence; disagreement flags `mixed` or `insufficient`; search failure yields `insufficient` (`reason: search_unavailable`), never model hallucination.
- `POST /api/philin/positions {question ≤ 500, context?}`: balanced position drafting with identical structure and length per side; stable shuffled labels A-D.
- `POST /api/philin/rank {positions: [{label, summary, argument}]}`: fixed deterministic rule (`RANK_RULE`): logic status (valid > unchecked > invalid), then fewer contradicted empirical premises (confidence ≥ 0.6), then more supported premises. Value premises are listed per position and never ranked.
- `POST /api/logic/grade {type, submission, item}` & `GET /api/logic/guide`: deterministic grading endpoint and schema guide powering interactive logic practice.
- `POST /api/practice/grade {type, item, submission}`: deterministic grading endpoint for all practice kits, evaluating student answers against Python graders without model intervention.
- **Client-Side Payload Redaction (`redact_for_client`)**: On `GET /api/topics/{id}` and `GET /api/topics`, practice items are scrubbed of secret grading keys (`expected`, `stress_pattern`, `solution`, `expected_order`, `expected_matrix`, `expected_pipeline`, `expected_winner`, `expected_vectors`, `expected_rhyme`, `expected_volta`) to eliminate client-side answer leakage in network payloads.
- Cache: `content/philin_cache/<scope>/<sha256(PROMPT_VERSION|normalised claim)>.json` (verdicts and sources only; 7-day TTL).

#### 3.12.1 Layer 2 Philosophy Practice Engine (`practice_philosophy.py`)
Deterministic logic and argumentation practice types registered in `server.PRACTICE_NORMALIZERS`:
1. `truth_table`: Truth table completion (≤4 variables). AI-supplied truth values are stripped; reference solutions are computed deterministically via `logic_formula.truth_table`.
2. `validity`: Deductive argument validity and counterexample identification. Truth-table counterexamples generated by `logic_formula.check_validity`.
3. `syllogism`: Categorical syllogism evaluation (mood, figure, validity, traditional names, rule violations) via `logic_syllogism.check_syllogism`.
4. `proof_steps`: Step-by-step natural deduction Fitch proof completion verified line-by-line via `logic_proof.check_proof`.
5. `argument_map`: Argument diagramming with graph diagnostics (cycles, missing links, Hume's is-ought gap, Prior's grounding check) via `logic_argmap.check_map`.
6. `spot_parts`: Argument component identification (premises, conclusions, objections, rebuttals, normative vs empirical claims).
7. `fallacy_id`: Identification of formal and informal fallacies, cross-validated against `logic_forms.identify`.
Authoring tools in `mcp_tools_philosophy.py` validate all items through `logic_engine.check()` before storage. Rendering is implemented in `src/practice/philosophy.jsx` and registered in `src/practice/registry.js`.

#### 3.12.2 Expanded Liberal Arts Practice Engines (6 Modules)
Standard library only, flat modules in root registered in `server.PRACTICE_NORMALIZERS` and `server.PRACTICE_TYPES`:
1. **Literature (`practice_literature.py`)**:
   - `scansion`: Poetic meter analysis (syllables and stress values). Normalized without leaking answer patterns; graded by syllable count and stress array comparison.
   - `volta_spot`: Sonnet thematic turn (volta) identification. Graded against targeted line position.
   - `rhyme_scheme_audit`: Identification of stanzaic rhyme schemes (e.g., ABAB, CDCD). Graded via canonical rhyme equivalence matching.
   - `chronology_unravel`: Reconstruction of chronological fabula from anachronic syuzhet narrative order. Graded via permutation distance.
2. **Music (`practice_music.py`)**:
   - `lint_satb_progression`: Voice-leading rule verification for 4-part SATB harmony (parallel fifths, parallel octaves, voice crossing).
   - `roman_numeral_analysis`: Harmonic analysis of chord progressions in major and minor keys with inversion notation.
   - `ear_interval_id`: Semitone interval distance identification and classification.
   - `figured_bass_realize`: Realization of historical figured bass symbols (`5/3`, `6/3`, `6/4`, `7`) into constituent pitch classes.
3. **Art History (`practice_art_history.py`)**:
   - `composition_vector`: Visual structural vectors and compositional dynamics (golden ratio, pyramidal, diagonal tension).
   - `label_architecture`: Architectural structural component identification on diagrams (clerestory, flying buttress, nave, pediment).
   - `iconography_decode`: Associating classical/religious attributes with iconographic figures.
   - `stylistic_taxonomy`: Taxonomic classification of period styles (Baroque, Rococo, Neoclassical, Impressionist) from visual characteristics.
4. **Classics & Archaeology (`practice_classics.py`)**:
   - `epigraphy_transcribe`: Ancient inscription transcription and lacuna restoration under Leiden conventions (`[text]`, `(text)`).
   - `harris_matrix_build`: Stratigraphic archaeological sequence diagramming verified by topological sort and transitive reduction.
   - `cursus_honorum_order`: Sequential progression of Roman magisterial offices under republican statutory constraints.
   - `athenian_sortition_sim`: Deterministic simulation and validation of democratic lottery allotment (Kleroterion).
5. **Rhetoric (`practice_rhetoric.py`)**:
   - `stasis_classify`: Classification into Hermagoras' four stases: conjectural, definitional, qualitative, translative.
   - `trope_hunter`: Identification of classical rhetorical figures and tropes (chiasmus, anaphora, zeugma, metonymy).
   - `dispositio_sort`: Ordering classical 6-part oratorical discourse (exordium, narratio, partitio, confirmatio, refutatio, peroratio).
   - `enthymeme_excavator`: Unearthing implicit bridge premises in informal rhetorical deductions.
6. **Polity & Political Science (`practice_polity.py`)**:
   - `compute_dhondt`: Deterministic highest-averages quotient seat allocation for proportional representation systems.
   - `compute_shapley_shubik_pivotal`: Permutation-based voting power index measuring pivotal voter probabilities.
   - `veto_pipeline`: Multi-cameral legislative threshold evaluation (veto gates, supermajorities, executive assent).
   - `instant_runoff_tally`: Sequential elimination and preference redistribution for ranked-choice electoral tallies.

#### 3.12.3 Declarative Decision Tree Engine (`decision_tree_engine.py`, `simspec.py`)
- Declarative simulation format (`kind: "decision_tree"`, SimSpec v1 specification):
  - `initial_node`: Root scenario identifier.
  - `nodes`: Dictionary of dilemma/scenario nodes containing `prompt`, `stated_premises`, `choices`, and `fog_of_war_hidden_facts`.
  - `choices`: Options with destination `next_node`, `reveals_facts`, and `axiomatic_weights` (e.g. `{"deontology": 1.0, "utilitarianism": -0.5}`).
- **Strict Epistemic Neutrality**: No choice is assigned normative "correctness" or penalized morally. The engine deterministically tracks:
  1. Accumulated axiomatic affinity vector.
  2. Revealed factual state (clearing fog of war).
  3. Dialectical consistency score: detects if subsequent choices contradict earlier affirmed `stated_premises`.
- Validated via `simspec.validate_spec()` and executed via `decision_tree_engine.step_decision_tree()`.
Authoring tools in `mcp_tools_philosophy.py` validate all items through `logic_engine.check()` before storage. Rendering is implemented in `src/practice/philosophy.jsx` and registered in `src/practice/registry.js`.

---

## 4. Workspaces & UI Presentation Architecture

The user interface is structured as eight primary modes rendered through `src/App.jsx`:

1. **My courses (`home`)**: Course setup wizard (materials upload/prompt), active course cards, streak status, daily review launch.
2. **Lab (`physics`)**: Classical mechanics, physics simulations, chemistry kit (`ChemSim.jsx`), and topic library sidebar.
3. **IDE (`code` / `class`)**: Code editing, algorithm challenges, browser WebAssembly execution (Pyodide), and Socratic code mentor.
4. **Math (`math`)**: Class notes, interactive function graphing (interactive sliders for free variables), LaTeX scratchpad, practice problems, and 9-widget Math Sim kit.
5. **History (`history`)**: Nine interactive tools rendered via `src/components/HistoryLab.jsx`:
   - `class`: Current sequential class topic and adaptive lesson viewer.
   - `courses`: Subject syllabus progress, enrolled history courses, and historical eras.
   - `crisis`: Branching counterfactual Crisis Simulator ("What If?" decision dilemmas).
   - `sources`: Primary Source Interrogator with document annotations and SHEG (Stanford History Education Group) analytical framework.
   - `map`: Interactive offline maps (`public/maps/`) with pin spiderfication and default historical anchors.
   - `figures`: Historical figures persona chat backed by `PERSONA_PROMPT`.
   - `games`: Daily games mix (`who_am_i`, `date_guess`, `categorize`).
   - `timeline`: Interactive chronology with century bands, era filtering, smooth zoom, and drag-and-drop event ordering challenge.
   - `cards`: Merged historical flashcard deck for people, treaties, and key terms.
6. **Languages (`language`)**: Ten interactive tools rendered via `src/components/LanguageLab.jsx`:
   - `class`: Current sequential language class with lesson text and activities.
   - `path`: Pedagogical Learn path of CEFR units with crown mastery.
   - `practice`: Practice Hub aggregating interactive drills (`translate`, `word_bank`, `listen_type`, `listen_choose`, `speak`, `minimal_pairs`, `dictation`).
   - `roleplay`: AI conversational partner with real-time speech synthesis/recognition and instant grammar feedback.
   - `words`: Word list with spaced-repetition decay strength meter (0-4 bars).
   - `cards`: Spaced-repetition vocabulary flashcards read aloud via ElevenLabs/Web Speech.
   - `pronounce`: Speech Lab & IPA reference chart (`PronounceTab.jsx`) with audio samples and voice-matching.
   - `stories`, `alphabets`, `dialogues`, `grammar`: Cultural immersion stories, script drills, dialogues, and contextual grammar tips.
   - `courses`: Enrolled language courses, CEFR proficiency levels (A1 to C2), and syllabus outlines.
7. **Philosophy (`philosophy`)**: Argument analysis, logic workbench, and thought experiment lab rendered via `src/components/PhilosophyLab.jsx` and `src/components/philosophy/`:
   - `class` & `courses`: Current sequential philosophy class topic viewer, course syllabus, and conceptual progress tracking.
   - `workbench`: Interactive Logic Workbench (`LogicWorkbench.jsx`):
     - Interactive Truth Table simulator and row step-checker (`TruthTableDesk.jsx`) with tautology/contingency/equivalence classification.
     - Calgary Natural Deduction Fitch step-checker (`NaturalDeductionDesk.jsx`) with line-by-line verification via `logic_proof.py`.
     - Categorical Syllogism 3-circle SVG Venn/Euler diagram generator (`SyllogismVennDesk.jsx`) across all 256 forms (15 boolean / 24 aristotelian forms).
   - `experiments`: Thought Experiments Lab (`ThoughtExperimentsLab.jsx`) with branching decision trees, moral dilemma simulations, and epistemic consequence tracking across 6 canonical dilemmas: Trolley Problem, Ship of Theseus, Chinese Room, Experience Machine, Brain in a Vat, and Veil of Ignorance.
   - `fallacies`: Fallacy Diagnostic Lab (`FallacyLab.jsx`): formal structural pattern matching (Affirming the Consequent, Denying the Antecedent, Syllogistic rules) vs informal heuristic flags (Ad Hominem, Straw Man, Slippery Slope, Circularity) with interactive argument repair.
   - `dialogue`: Persona Dialogue (`PhilosopherDialogue.jsx`) with historical thinkers (Socrates, Aristotle, Kant, Mill, Hume, Nietzsche) grounded in verified public-domain quote banks (`content/quotes/*.json`).
   - `analyze`: PHILIN text-to-argument block decomposition, Python validity checking, categorical syllogisms, and two-pass grounded fact-checks.
   - `sides`: Balanced multi-position argument synthesis, objection mapping, and deterministic ranking under fixed evidence rules.
   - `practice`: Layer 2 Philosophy interactive practice items (truth tables, validity, syllogisms, Fitch proofs, argument maps, fallacies).
   - `cards`: Concept, argument, and philosopher flashcard deck with spaced review.
8. **Advisor (`advisor`)**: Academic record tracking, prerequisite degree requirements, catalog search, and prerequisite readiness courses.

### Design System & Theme Engine
- **Token Source of Truth**: `src/styles/lab.css` defines CSS custom properties for `:root` (light) and `@media (prefers-color-scheme: dark)` / `[data-theme="dark"]`.
- **William & Mary Academic Palette**: Deep Griffin green (`--accent: #0e4a37`, `--brand: #0b3b2c`), warm Caslon gold (`--gold: #c9a24a`, `--gold-text: #6f5114`), warm stone paper (`--paper: #f1f0ea`, `--surface: #ffffff`), and crisp rule borders.
- **Canvas Bridge**: `src/theme.js` exposes `canvasPalette()`, reading computed style variables once per frame, enabling HTML5 Canvas renderers (`SpecSim`, `ChemSim`, `MathSim`, `BilliardSim`) to switch between light and dark themes with zero visual artifacts.

### Frontend Bundling & Dynamic Code-Splitting
- **Vite 8 & Rolldown**: Configured in `vite.config.js` with `build.rolldownOptions.output.codeSplitting.groups` separating `react`, `katex`, and `markdown` into isolated vendor chunks with high cache affinity across application builds.
- **Dynamic Simulation Splitting**: Interactive simulation runners (`RollingWithoutSlippingSim`, `BilliardSim`, `SpecSim` including nested math and chemistry engines) are lazily loaded on-demand via `React.lazy` and `Suspense` when the Simulation tab is activated in `src/components/TopicViewer.jsx`.
- **Mermaid 11 Diagram Engine**: Diagram rendering is dynamically imported via `import('mermaid')` on the first diagram request in `src/components/MermaidViewer.jsx` (`securityLevel: 'strict'`). External CDN script tags in `index.html` have been eliminated, providing strict privacy and full offline functionality.

---

## 5. Storage, Concurrency & Infrastructure

### 5.1 SQLite Persistence Model
- **Database file**: `content/edu_studio.db`
- **Concurrency Mode**: WAL (`PRAGMA journal_mode = WAL`) and strict relational integrity (`PRAGMA foreign_keys = ON`).
- **Connection Management**: `db.conn()` maintains thread-local connection handles. Synchronous FastAPI endpoint invocations run in Starlette's threadpool worker threads.
- **Data Lifecycle**:
  - `courses` rows track the master status: `planning` -> `diagnostic_ready` -> `generating` -> `ready` | `error`.
  - `classes` rows track individual lesson generation status: `pending` -> `generating` -> `ready` | `error`.
  - **Failure Recovery & Resume Semantics**:
    - *Course planning failure*: If Gemini outputs malformed JSON or times out during syllabus/diagnostic drafting, the course enters `error` with a friendly student-facing notice. `POST /api/courses/{course_id}/resume` detects the missing diagnostic, preserves the original `materials_text` (up to 200k chars) and `goal`, transitions status `error` -> `planning`, and triggers `start_plan_job`.
    - *Class generation failure*: If an individual class generation fails, `POST /api/courses/{course_id}/resume` clears the course error and dispatches `queue_course_generation` for all remaining `pending` classes.
    - *Concurrency & Idempotency*: `resume_course` checks `ACTIVE_COURSE_JOBS` and `JOBS` status to reject concurrent requests if a job is already queued or running for that course.
  - Interrupted runs: On backend startup (the app lifespan, `resume_course_generation`), `db.reset_stuck_classes()` resets orphaned `generating` records to `pending`, and `db.interrupted_planning()` reschedules syllabus generation jobs from stored materials.
  - Academic Advisor catalog tables:
    - `catalog_courses`: Master catalog course specifications (`school`, `code` PRIMARY KEY, title, credits, description, prerequisites, prereq_codes, attributes, syllabus, `prereq_tree` JSON CNF representation).
    - `completed_courses`: Student academic records (`user_id`, `code` PRIMARY KEY, title, grade, term).
    - `catalog_sections`: Scheduled course offerings per term (`school`, `term`, `crn` PRIMARY KEY, `code`, section, title, instructor, meeting times, schedule type, seats, status, credits, `details` JSON from PATH: rooms, dates, seats, `restrictions` (the section's own prerequisite line comes first), `consent`). Indexed on `(school, code)` and `(school, term)` for sub-millisecond section lookups. Raw schedule feeds cached under `content/catalog_cache/sections_<term>.json` (the older `classes_<term>.json` name is still read).

### 5.2 Background Jobs & Event Processing
- **Queue Architecture**: An in-memory dictionary `JOBS` (capped at 100 entries) runs background coroutines via `asyncio.create_task` or threadsafe dispatch onto `MAIN_LOOP`.
- **Client Synchronization**:
  - Events are assigned monotonic sequence numbers (`_event_seq`).
  - Frontend subscribes via `useAgyEvents` in `src/lib/api.js`, issuing cursor-based requests: `GET /api/agy/events?since=<cursor>`.
  - When `since < 0` (first load), the server returns the latest cursor without replaying past UI events, preventing unwanted tab switches or navigation replays.
  - Multi-user isolation: When `SCIEDU_AUTH=1`, private event types (`COURSE_UPDATED`, `JOB_UPDATE`, `CLASS_ADAPTED`, etc.) are filtered by `owner == CURRENT_USER.id`.
- **Live job log**: each job keeps its last `JOB_LOG_MAX` (12) steps as `log: [{at, step}]`. `_job_update` appends when the headline `step` changes; `_job_note(job, text)` adds a sub-step without changing the headline (`build_class(..., on_step)` reports "Lesson written", "Quiz checked: N corrected", "Simulation added"). Entries are fixed labels and counts, never materials or answers. The log travels in `JOB_UPDATE` (a copy), `GET /api/jobs/{id}` and `course.job`; `src/components/LoadingPanel.jsx` shows the last 6.
- **Loading screens**: `LoadingPanel` is the one loading state (bar, live log, and a quote from the offline bank `content/quotes/*.json`, hidden in Focus mode, not rotating with reduced motion). Quotes are public-domain translations checked word for word against their sources by `scripts/verify_quotes.py`; never add one from memory.

### 5.3 Docker Deployment Configuration
- **Container Strategy**: Single multi-stage container.
  - Stage 1 (`node:22-alpine`): Compiles React 19 frontend into static production assets (`dist/`).
  - Stage 2 (`python:3.14-slim`): Aligned to Python 3.14 runtime. Installs backend dependencies from pinned `requirements.txt`, seeds default topics into `/app/seed/topics`, and mounts `/app/dist` directly into FastAPI (`app.mount("/", StaticFiles(directory=DIST_DIR, html=True))`).
- **Subprocess Sandbox Hardening (`sandbox_preamble.py`)**:
  - Python code executed in the IDE sandbox (`POST /api/execute-code`) injects `sandbox_preamble.py` into child interpreter processes.
  - Enforces CPython PEP 578 runtime audit hooks (`sys.addaudithook`):
    - Blocks network sockets (`socket.*`).
    - Blocks child subprocesses (`subprocess.Popen`, `os.system`, `os.posix_spawn`).
    - Blocks SQLite database access (`sqlite3.*`), preventing local exfiltration of `content/edu_studio.db` or credentials.
    - Restricts filesystem I/O (`open`, `os.remove`, etc.) strictly to the ephemeral scratchpad directory.
- **Isolation**: Runs as unprivileged user `lab` (`uid: 10001`). Data volume `/app/content` preserves SQLite database and generated lessons.
- **Process model (contract)**: exactly one uvicorn process, one worker. `JOBS`, `ui_events_queue`/`_event_seq`, rate buckets (`_rate_hits`) and the agy lock live in process memory, so `--workers N` or several replicas would split jobs and events between processes and multiply every limit by N. Scale up (threads, async) before scaling out; moving that state to SQLite is the prerequisite for more workers.
- **Image contents**: only library lessons belong in the seed; `content/topics/course-*.json` are per-student lessons (git-ignored) and must stay out of the build context (`.dockerignore`).
- **Security Boundaries**: In production, `SCIEDU_AUTH=1` is enforced whenever listening on non-loopback addresses (`0.0.0.0`), preventing unauthenticated access to the sandbox or model endpoints.

### 5.4 Desktop app (Electron, macOS and Linux, arm64 + x64, v0.0.0)
One process tree per user: Electron main (`desktop/main.cjs`) -> bundled CPython (python-build-standalone 3.14, one per arch) running `desktop_main.py` -> `server.py` in-process. The window loads `http://127.0.0.1:<port>/`; the backend serves `dist/` exactly as in Docker (same single-process contract as 5.3).
- **Bundle layout** (`Contents/Resources/` on macOS, `resources/` beside the `sciedu-studio` executable on Linux, outside `app.asar`): `python/` (per-arch interpreter, deps pip-installed into its own `lib/python3.14/site-packages`, `.pyc` precompiled), `backend/` (the git-tracked root `*.py` except `mcp_server.py` (`language_de.py` imports `mcp_tools_language`), `dist/`, `public/diagrams/`, `seed/topics/` from `git archive HEAD content/topics` (committed lessons only)). The layout mirrors the repo, so every `Path(__file__).parent` lookup (`DIST_DIR`, `DIAGRAMS_DIR`, `practice_general.DIAGRAMS_DIR`) works unchanged. The bundle is read-only at run time (`python -I -B`): writing `__pycache__` would break the code signature.
- **Data**: `~/Library/Application Support/SciEdu Studio/` on macOS, `~/.config/SciEdu Studio/` on Linux (Electron `userData`; `andedu-lab` under `npm run desktop:dev`): `content/` (= `SCIEDU_CONTENT_DIR`, seeded from `seed/topics` on the first launch only, so a deleted lesson stays deleted), `logs/backend.log` (rotated at 5 MB), `config.json` (`{port, seeded}`), `secrets/device.key.enc` (the device key, safeStorage ciphertext, mode 0600; see 5.5), and `secrets/gemini.key.enc` only on a computer upgraded from a version before accounts, until an account answers its offer. The developer's `content/` is never copied.
- **Gemini keys**: each account keeps its own (5.5); the shell never sees them. Main makes a 32-byte **device key** once (`secrets/device.key.enc`, Electron `safeStorage`: macOS Keychain; on Linux the Secret Service or KWallet; `secureStoreOk()` refuses Linux's `basic_text` fallback, so with no keyring there is no device key and only accounts with a password can store a key). A device key that cannot be opened is never replaced (that would orphan every sealed key). At spawn, main writes one JSON line to the child's stdin, `{"device_key": <base64>, "legacy_gemini_key": <the pre-accounts key, if its file exists>}`; `desktop_main.py` puts both into `userkeys` (never `os.environ`, never argv) and strips any `api_KEY`/`GEMINI_API_KEY`, so no install-wide Gemini client exists. The renderer's bridge is `platform` (wording only) and `removeLegacyKey()`, which deletes `gemini.key.enc` only once the backend's `/api/status` (same `instance_id`) says `legacy_key_pending: false`. The key check with Google is `userkeys.check_key` (`GET https://generativelanguage.googleapis.com/v1beta/models?pageSize=1`, `x-goog-api-key` header, 8 s, nothing logged): invalid (400/401 `API_KEY_INVALID`) or leaked/suspended (403) rejects, 403 `SERVICE_DISABLED` says the project lacks the Gemini API, anything else (offline, quota, 5xx) saves it as unverified. Saving or removing a key restarts nothing.
- **Lifecycle**: single-instance lock (two backends on one SQLite dir would split `JOBS`); port remembered in `config.json` (localStorage is per-origin, so a port change resets UI prefs), a new free port is chosen only if it is taken; readiness = `/api/status` returning this launch's `instance_id`; stdin EOF in the child = parent gone -> exit; quit = SIGTERM, 5 s, SIGKILL.
- **Spawn environment (allowlist, nothing inherited)**: `PATH=/usr/bin:/bin:/usr/sbin:/sbin`, `HOME`, `TMPDIR`, `LANG`, `SCIEDU_HOST=127.0.0.1`, `SCIEDU_PORT`, `SCIEDU_CONTENT_DIR`, `SCIEDU_ENV_FILE=none`, `SCIEDU_INSTANCE_ID`, `SCIEDU_ALLOWED_ORIGINS=http://127.0.0.1:<port>`, `SCIEDU_LOCAL_ACCOUNTS=1`, `AGY_CLI=0`, `SCIEDU_ELEVENLABS=0`. No Gemini key in any form, no `SCIEDU_AUTH`, no MCP, no agy.
- **Start page**: while the backend starts (and again on Restart after a crash) the window shows `desktop/startpage.cjs` `buildStartPage()`, a data: page with no script and a `default-src 'none'` meta CSP: a CSS-only bar and the last 6 `[startup] ` lines of `logs/backend.log` (printed by `desktop_main.py` and the `server.py` lifespan; fixed text only). Main tails the log from the launch's offset each 250 ms and replaces the list through `executeJavaScript` of the self-contained `renderLog` with JSON data (`textContent` only), only while the window is still on the data: page. No quotes: no profile is loaded yet, so Focus mode is unknown.
- **Window**: `contextIsolation`, `sandbox`, no `nodeIntegration`; navigation limited to the backend origin; `window.open`/`_blank` https links go to the system browser; permission requests denied except `media` from the backend origin.
- **Packaging**: electron-builder (`files`: `desktop/main.cjs`, `preload.cjs`, `startpage.cjs`; `tests/test_desktop.py` checks every local `require` is listed; `npm run test:desktop` runs the start-page tests), `mac.target` dmg+zip, `--arm64 --x64` (two separate apps, not universal), `extraResources` `python-${os}-${arch}` -> `python`, ad-hoc signing (`identity: "-"`, `hardenedRuntime: false`). Not notarized: first open needs System Settings > Privacy & Security > Open Anyway; each new ad-hoc build is a new code identity, so macOS asks once again for Keychain access to the device key. Linux: `linux.target` AppImage (static runtime, `toolsets.appimage: "1.0.3"`: no libfuse2 on the user's side, native arm64 macOS tools) + tar.gz, `--x64 --arm64`, built on the Mac without Docker or Rosetta; executable `sciedu-studio`, `desktopName` `sciedu-studio.desktop` (`syncDesktopName`); the x64 AppImage is named `linux-x86_64` (AppImage convention), the tar.gz `linux-x64`; glibc >= 2.28 (manylinux_2_28 wheels); the Chromium sandbox stays on (an AppImage cannot carry a setuid `chrome-sandbox`, so Ubuntu 23.10+ needs the AppArmor `userns` profile in the README). The Linux interpreter is not stripped (no ELF strip on the Mac), which makes it about 160 MB larger before compression.
- **Pinned inputs** (each at least two weeks old when chosen): Electron 44.9.3, electron-builder 26.18.0, python-build-standalone `20261026` CPython 3.14.10 (sha256 in `scripts/desktop_stage.sh`), wheels from `desktop/requirements-<target>.lock` (`mac-arm64`, `mac-x64`, `linux-x64`, `linux-arm64`; hash-locked, `--exclude-newer 2026-10-27`); Linux interpreters `x86_64-unknown-linux-gnu` / `aarch64-unknown-linux-gnu` from the same release (sha256 in `scripts/desktop_stage.sh`, which also checks every ELF file's `e_machine`). The window also gets a CSP (`desktop/main.cjs`); `will-attach-webview` is refused.
- **x64 dependency pin**: cryptography >= 49 ships no macOS x86_64 wheels; the mac x64 build pins `cryptography==48.0.1` (`desktop/constraints-mac-x64.txt`) (a cp311-abi3 universal2 wheel; google-auth needs >= 41.0.5). Its open advisories (PKCS#7 decrypt, X.509 path validation) are in code paths this app does not use (API-key auth only).

### 5.5 Accounts on this computer (`SCIEDU_LOCAL_ACCOUNTS=1`, the desktop app)
Several people on one computer (one OS user), each with their own courses, progress and Gemini key. `local_mode()` = the flag and not `SCIEDU_AUTH` (server accounts win if both are set); `scoped()` = either, and every per-user check uses it. App-level isolation only: the database and files sit in one folder the OS user can read.
- **Sign-in**: `GET /api/auth/profiles` (public, `[{id, name, locked}]`) shows tiles; `POST /api/auth/register {name, password?}` (password optional, at least 8) and `/api/auth/login`. Each launch starts signed out (`db.clear_sessions()`): unlocked keys live in memory only. Wrong passwords back off per name (five free, then 2^n s up to 15 min), shared by login, password change and delete. No recovery: "Forgot password?" tells the user to ask the admin to delete the account.
- **Passwords and keys** (`userkeys.py`): `scrypt2$n$r$p$salt$verifier`, one scrypt run (n=2^17, r=8, 128 MiB, at most 2 at once) then HKDF to a verifier and a KEK. The account's Gemini key (`user_secrets`, AES-256-GCM, AAD `user|kind|mode`) is sealed with the KEK (password accounts) or the device key (open accounts). `PUT /api/me/gemini-key {key}` checks it with Google first; `DELETE` removes it; `/api/auth/me` reports `keyState` (none, ok, locked, unreadable), `keyInvalid`, `modelCallsLeft`, `hasPassword`, `autoLockMin`, `isAdmin`, `legacyKeyOffer`. Setting, changing or removing a password re-seals the key in one transaction (without a device key, removing the password deletes the key and says so).
- **Lock**: `POST /api/auth/lock` and the UI's idle timer (input events only; `PUT /api/auth/prefs {autoLockMin}`, default 30, 0 = never, password accounts only) drop the key from memory and end the account's sessions; the middleware is the backstop (`IDLE_EXEMPT_PATHS`: polls don't count as activity). A running job keeps its lease on the key for `KEY_LEASE_GRACE_S` (30 min); a model call that has no key answers 409 `{code: "gemini_key_missing"}` (the UI opens the key card), one whose lease ran out 401 `{code: "key_locked"}` (sign in again). Interrupted jobs resume per account after sign-in or key save (`resume_for_user`), never at boot.
- **Admin**: one account, `users.is_admin = 1`: the first account created; on a database from before accounts, the account that adopts the old computer-wide key, else the oldest. Whenever no account is admin, the oldest becomes it (not while the old key's offer waits). The admin alone writes the shared library and catalog, runs bulk jobs and the agent inbox, and deletes accounts (3.6): `GET /api/auth/accounts`, `POST /api/auth/admin/transfer {userId, password?}` (one UPDATE; the role moves, it is never shared), and deletes its own account only after handing the role on, unless it is the last one. An admin who forgets their password cannot be deleted or replaced.
- **Budgets**: `SCIEDU_DAILY_MODEL_CALLS` counts per key, not per install; `/api/status` reports no install-wide key state (`gemini_configured` false, `model_calls_left_today` null) and adds `local_accounts`.
- **Upgrade**: before the first migration `db.init_db` writes `content/backups/edu_studio.pre-accounts.db` once. An older build ignores passwords (downgrading exposes every account's courses; keys stay sealed). The pre-accounts key is offered once (`PUT /api/me/gemini-key {adoptLegacy: true}` or `DELETE /api/me/legacy-key`), then the app deletes its file.
- **Not yet**: MCP agent tokens. `mcp_server.py` needs `ANDEDU_TOKEN`, and sessions end with each launch.

---

## 6. Spending Guards & Resource Bounds

| Guard | Default Value | Environment Variable | Enforcement Level |
| :--- | :--- | :--- | :--- |
| **Daily Gemini Model Budget** | 400 requests/day | `SCIEDU_DAILY_MODEL_CALLS` | Global hard ceiling across all model calls and retries (accounts on this computer: per account key, 5.5). Resets at midnight UTC. |
| **Rate Scale Multiplier** | 1.0 (enabled) | `SCIEDU_RATE_SCALE` | Sliding hourly window per user / IP address: Course creation (10/hr), class generation (40/hr), agy assistant (60/hr), simulation generation (20/hr), uploads (30/hr), IDE (120/hr), chat (240/hr), PHILIN transcribe/positions (20/hr) and fact-checked claims (30/hr, two grounded calls each). |
| **Antigravity CLI Guard** | 15 runs/day | `AGY_DAILY_RUNS` | Single execution concurrency lock (`_agy_lock`), gated by daily counter. Disabled automatically when `SCIEDU_AUTH=1`. |
| **Agent Sandbox Fence** | Read/write restricted | `AGY_DRAFTS_DIR` | Companion agent may only output to `content/agy_drafts/<id>.json`. Verified by read-only `page-guard` agent before ingestion. |
| **Client-Reported XP Cap** | 60 events/day | `CLIENT_DAILY_CAP` (`engage.py`)| Limits client-originating XP claims (`sim_explored`, `lesson_read`, `ide_solved`) to prevent gamification farming. |

---

## 7. Configuration Reference (.env)

| Variable Name | Default | Required | Purpose & Constraints |
| :--- | :--- | :--- | :--- |
| `api_KEY` / `GEMINI_API_KEY` | None | **Yes** | Google Gemini API key. Required for lesson generation, syllabus planning, quiz answer verification, and drawings grading. |
| `SCIEDU_HOST` | `127.0.0.1` | No | Host bind address. If set to `0.0.0.0`, `SCIEDU_AUTH=1` is mandatory. |
| `SCIEDU_PORT` | `8090` | No | HTTP port for the FastAPI server. |
| `SCIEDU_AUTH` | `0` | No | Set to `1` to enable multi-user accounts, scrypt password hashing, session tokens, and strict tenant isolation. |
| `SCIEDU_LOCAL_ACCOUNTS` (5.5) | `0` | No | `1`: accounts on this computer (the desktop app sets it): optional passwords, each account's own sealed Gemini key, auto-lock, one admin. Ignored when `SCIEDU_AUTH=1`. No install-wide key is used. |
| `SCIEDU_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | No | Comma-separated CORS allowed origins. |
| `SCIEDU_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` | No | Comma-separated list of allowed HTTP `Host` headers to prevent DNS-rebinding attacks. |
| `SCIEDU_ADMINS` | `""` | No | Comma-separated user ids (shown in the account menu) with administrative permissions (catalog imports, library topic updates, agent inbox). Names are not accepted. |
| `SCIEDU_RATE_SCALE` | `1.0` | No | Multiplier for hourly rate limits. Set to `0` to disable rate limiting in automated testing. |
| `SCIEDU_DAILY_MODEL_CALLS` | `400` | No | Hard daily request quota across all Gemini models. |
| `SCIEDU_USER_DAILY_MODEL_CALLS` | half of `SCIEDU_DAILY_MODEL_CALLS` | No | Per-user daily share of the model budget, so one student cannot use up the whole day. |
| `SCIEDU_PLANNER_MODELS` | Candidate list fallback | No | Comma-separated Gemini model IDs preferred for syllabus planning and answer verification. |
| `SCIEDU_LESSON_MODELS` | Candidate list fallback | No | Comma-separated Gemini model IDs preferred for lesson prose and practice generation. |
| `SCIEDU_AUTHOR_SIMS` | `1` | No | Set to `0` to disable automatic background simulation generation during class building. |
| `SCIEDU_GROUNDED_CHECKS` | `1` | No | Set to `0` to disable Google Search grounding during quiz answer verification. |
| `SCIEDU_ELEVENLABS` | `0` | No | Set to `1` to enable ElevenLabs neural speech synthesis for lesson voiceovers. |
| `ELEVENLABS_API_KEY` | None | Conditional | Required if `SCIEDU_ELEVENLABS=1`. |
| `AGY_CLI` | `0` | No | Set to `1` to route assistant prompts to the local Antigravity CLI binary. Personal machine only. |
| `AGY_BIN` | `/opt/homebrew/bin/agy` | No | Path to the Google Antigravity CLI binary. |
| `AGY_DAILY_RUNS` | `15` | No | Maximum daily runs of the Antigravity CLI. |
| `SCIEDU_CONTENT_DIR` | `./content` | No | Override path for SQLite database, topic JSONs, and cache artifacts. |
| `SCIEDU_ENV_FILE` (5.4) | unset | No | Unset: load `./.env` next to `server.py`, else `load_dotenv()` (walks up from `server.py`'s folder to `/`, so it can pick up e.g. `~/.env`). A path: load only that file. `none`: load no `.env` at all (the desktop app). |
| `SCIEDU_INSTANCE_ID` (5.4) | unset | No | Echoed as `instance_id` by `GET /api/status`, so a launcher can tell its own backend from another server on the same port. Not a secret. |
| `SCIEDU_SPRINT_RETAIN_DAYS`, `SCIEDU_TTS_DAILY_CHARS`, `SCIEDU_TTS_CACHE_MB`, `SCIEDU_EXPLAIN_TTS_CHARS`, `ELEVENLABS_GERMAN_VOICE_ID`, `SCIEDU_DOMAIN` | see `.env.example` | No | Documented in `.env.example` and AGENTS.md. |

---

## 8. Model Context Protocol (MCP) Expanded Tool Suite

`mcp_server.py` implements a zero-dependency JSON-RPC 2.0 interface enabling autonomous agents (agy, Claude Code, Cursor) to author content, execute pedagogical actions, and project interactive learning widgets directly onto the student's screen in real time.

### 8.1 Tool Catalog by Discipline

#### Language Acquisition & Gamified Drills
- `add_translation_exercise`: Append translation exercises with source text, target language, and alternate acceptable phrasing.
- `add_word_bank`: Append sentence chip scramble puzzles with distractor tokens.
- `add_listening_exercise`: Append audio dictation (`listen_type`) or audio multiple-choice (`listen_choose`) comprehension drills with normal and turtle speeds.
- `add_speaking_exercise`: Append pronunciation speaking tasks with target text, IPA transcription, and speech-recognition scoring.
- `build_language_unit`: Append a complete language unit including vocabulary, dialogue, and comprehensive drill decks.
- `start_language_practice`: Dispatch `SWITCH_STUDIO_MODE {mode: "language", tab: "practice"}` to launch drills for a specific target language.

#### AI Features
- `start_roleplay`: Launch an interactive conversational scenario on the student's screen (`SWITCH_STUDIO_MODE {mode: "language", tab: "roleplay"}`), seeding scenario context, avatar persona, and initial greeting.
- `explain_answer`: Query the Socratic pedagogical tutor (`POST /api/tutor/explain-answer`) for an in-depth breakdown of grammar rules, conjugation tables, or false friends for any problem.

#### Interactive History Engine
- `start_historical_crisis`: Dispatch `SWITCH_STUDIO_MODE {mode: "history", tab: "crisis"}` with a counterfactual dilemma (e.g. Cuban Missile Crisis, Crossing the Rubicon), seeding choices and historical reality notes.
- `add_crisis_scenario`: Attach a branching historical crisis dilemma to a specific lesson topic.
- `open_primary_source`: Dispatch `SWITCH_STUDIO_MODE {mode: "history", tab: "sources"}` to open an annotated historical document (e.g. Magna Carta, Code of Hammurabi) with sourcing analysis questions.
- `add_primary_source_lab`: Attach an authentic annotated primary source with SHEG questions to a history topic.

#### Visual Geometry & Free-Body Diagrams
- `add_drawing_to_notes`: Validates and appends an interactive ````geometry` declarative simulation block to a lesson's markdown content and standalone notes file (`content/notes/<id>.md`).
- `preview_geometry_diagram`: Dispatches `GEOMETRY_PREVIEW` to project an interactive geometry or free-body diagram directly into Math Lab / Sim Kit on the student's screen in real time.
- `simulation_guide`: Expanded documentation covering `kind: "geometry"` schemas, bodies (`box`, `wedge`, `sphere`, `rod`, `wall`, `pulley`), forces, elements, and reactive slider parameters.

#### Navigation & Screen Control
- `open_workspace`: Route the browser UI to any subject workspace (`history`, `language`, `philosophy`, `math`, `lab`, `code`, `advisor`) and specific sub-tab (`analyze`, `sides`, `crisis`, `sources`, `roleplay`, `practice`, `timeline`, `speech`).

---

## 9. Socratic Pedagogy & Anti-Hallucination Prompt Architecture

The system's Socratic agents (`SOCRATIC_PROMPT`, `LESSON_TUTOR_PROMPT`, `AGY_SYSTEM_PROMPT`) embody a Stoic, first-principles pedagogical design grounded in learning science (Collins' Cognitive Apprenticeship, Sweller's Cognitive Load Theory, and Hattie's feedback taxonomy):

1. **Two-Tier Dynamic Response Sizing**:
   - Abolishes both artificial one-sentence chokes AND rigid multi-paragraph mandates that induce extraneous cognitive load.
   - **Diagnostic Turns (40–80 words)**: When the student checks a formula, asks a quick clarification, or tests a single hypothesis, provide a concise, laser-focused diagnostic turn addressing the specific threshold concept, ending with **one leading check question**.
   - **Conceptual Scaffolding Turns (100–180 words)**: When the student has a fundamental misconception or begins a new derivation, provide structured scaffolding:
     * Paragraph 1: Governing physical law / mathematical invariant.
     * Paragraph 2: Coordinate geometry / free-body reference frame constraints.
     * Paragraph 3: Direct diagnosis of the conceptual blocker using limiting cases or dimensional reasoning.
     * Conclusion: Exactly **one leading diagnostic check question**.
2. **Anti-Hallucination & Symbolic Invariants**:
   - **Symbolic Problem Integrity**: Forbids inventing numbers on symbolic or algebraic problems. Formulas must remain exact in terms of declared parameters ($m, g, \theta, \mu$).
   - **Dimensional Homogeneity Guard**: Mismatched dimensions across equations ($[M^a L^b T^c]$) are strictly prohibited.
   - **Vector Typography Guard**: Mandates KaTeX dotless unit vectors ($\hat{\imath}$, $\hat{\jmath}$, $\hat{k}$) via `\hat{\imath}`, `\hat{\jmath}`, `\hat{k}`.
   - **Grounded Step-by-Step Verification**: Prohibits stating unverified arithmetic as fact. Numerical evaluation is done explicitly or prompted to the student.
3. **Multi-Turn Continuity & Alternating Sequence Integrity**:
   - Ingests recent user and model conversation turns into Gemini structured turn sequences (`types.Content`).
   - Strict role alternating: Merges consecutive duplicate roles (`user, user` or `model, model`) and guarantees the conversation sequence opens with a `user` turn.
   - Context sanitization: `_sanitize_puzzle_context` strips internal solution/test secrets to prevent answer leakage and prompt injection.

---

## 10. Advanced Laboratory Engines & Code Studio Architecture

Detailed specification: `docs/architecture/PEDAGOGY_AND_LAB_ELEVATION.md`.

### 10.1 Chemistry Simulation Apparatus (`src/simulations/ChemSim.jsx`)
ChemSpec v1 widgets match the visual fidelity and physical realism of the physics simulation kit:
1. **Glassware Benchtop Apparatus & Polyprotic Titration Solver**:
   - Retort stand with heavy base, chrome support rod, and dual-finger clamp.
   - Graduated burette with dynamic fluid meniscus, millimeter volume gradations, and rotating stopcock valve.
   - Gravitational droplet emitter with fluid splash ripples on liquid contact.
   - Erlenmeyer reaction flask with rising fluid volume, porcelain magnetic stirrer plate, rotating Teflon stir bar, and fluid vortex depression.
   - Benchtop digital pH meter with dip electrode probe and live 2-decimal digital readout.
   - Smooth continuous RGB colorimetric indicator gradient for phenolphthalein with fluid swirl eddies.
   - **Polyprotic Charge-Balance Solver**: Implements exact polynomial charge balance $h - \frac{K_w}{h} + [\text{Na}^+] - C_{A,\text{tot}} \sum_{j=1}^N j \alpha_j(h) = 0$ supporting polyprotic acids with `ka_list` (e.g. $\text{H}_2\text{SO}_4$, $\text{H}_3\text{PO}_4$) and continuous dilution across added burette titrant volumes $V_b$. Solves equilibrium pH deterministically via monotonic bisection down to $\Delta \text{pH} < 10^{-6}$.
2. **Molecular Kinetics & Gas Law Chamber**:
   - Maxwell-Boltzmann 2D velocity sampling for molecular gas particles ($v \propto \sqrt{T/m}$).
   - Particle-wall momentum impulse calculation with live analog dial pressure gauge.
   - Reactive collision engine: collisions exceeding activation energy $E_a$ trigger chemical transformation with optical emission flash.

### 10.2 Math & Physics Simulation Kit (`SpecSim.jsx`, `MathSim.jsx`, `GeometrySim.jsx`)
1. **XPBD Velocity Projection & Symplectic Integrator (`SpecSim.jsx`)**:
   - In particle substepping integration loops ($240\text{ Hz}$), pre-step positions $(\mathbf{x}_{\text{prev}, i})$ are stored prior to explicit candidate advances.
   - Distance constraints across rigid links/rods are resolved purely via position-based relaxation (PBD), with velocities left untouched during relaxation iterations.
   - Post-relaxation velocities are projected directly from constrained displacements: $\mathbf{v}_i = (\mathbf{x}_i - \mathbf{x}_{\text{prev}, i}) / \Delta t_{\text{sub}}$, completely eliminating phantom energy creation and stabilizing double pendulums and multi-link chains with $<0.5\%$ Hamiltonian drift.
2. **Secant-Tangent Slope Triangle**: Interactive right triangle connecting $(a, f(a))$ and $(a+h, f(a+h))$ with legs $\Delta x = h$, $\Delta y = f(a+h) - f(a)$, right-angle symbol, and live derivative convergence limit $\lim_{h \to 0} \frac{\Delta y}{\Delta x} = f'(a)$.
3. **Riemann Sum Darboux Visualizer**: Upper and Lower Darboux sums ($L_n \le \int_a^b f(x)\,dx \le U_n$) with shaded error residual fill between rectangles and the exact curve $f(x)$.
4. **Direct Vector Drag Handles**: SVG pointer drag handles on force vector arrowheads and body centers, updating slider parameters and coordinate projections in real time.

### 10.3 Code Studio Memory Inspector & Socratic Diagnostics (`src/components/EduStudioIDE.jsx`)
1. **In-Browser Memory & Variable Inspector**: Lightweight Pyodide post-execution introspection capturing local/global variables, types, sequence lengths, and array memory grid cells.
2. **Socratic Error Diagnostic Engine**: Translates assertion errors and Python tracebacks into process-level Socratic hints (missing return, off-by-one loop boundaries, boundary conditions, index errors, type mismatches).

### 10.4 Advanced STEM & Engineering Practice Kits (20 Deterministic Practice Types)
Five flat root modules (standard library only) providing normalizers and deterministic graders for upper-division engineering and science:
1. **Electrical Engineering (`practice_ee.py`)**:
   - `circuit_dc_analysis`: Branch current and node voltage verification via Ohm's law and Kirchhoff's Current/Voltage Laws.
   - `thevenin_equivalent`: Open-circuit voltage $V_{\text{th}}$ and Thevenin resistance $R_{\text{th}}$ calculation.
   - `bode_cutoff_calc`: 3dB corner frequency $f_c$ and filter topology classification (low-pass, high-pass, band-pass).
   - `opamp_gain_calc`: Closed-loop operational amplifier voltage gain $A_v$ for inverting and non-inverting configurations.
2. **Artificial Intelligence & Machine Learning (`practice_ai.py`)**:
   - `gradient_descent_step`: Trace single weight update $w_{t+1} = w_t - \eta \frac{\partial L}{\partial w}$.
   - `confusion_matrix_metrics`: Exact precision, recall, $F_1$, and specificity calculation from confusion matrix counts.
   - `attention_score_calc`: Scaled dot-product attention calculation $\operatorname{softmax}(QK^T / \sqrt{d_k})$.
   - `convolution_output_dim`: Spatial output dimension $\lfloor (W - K + 2P)/S \rfloor + 1$.
3. **Computer Systems & Architecture (`practice_systems.py`)**:
   - `pipeline_hazard_spot`: Data hazard (RAW) identification, load-use stalls, and branch delay slot flush penalties.
   - `cache_address_decode`: Decomposition of memory address into Tag, Set Index, and Offset bit ranges.
   - `assembly_step_trace`: Tracing RISC-V register file ($t0, t1, s0$) and memory contents after instruction execution.
   - `virtual_memory_translate`: Virtual Page Number (VPN), Page Offset, page table lookup, and physical address calculation.
4. **Statistics & Data Science (`practice_stats.py`)**:
   - `p_value_decision`: Exact $p$-value computation and hypothesis test rejection decision.
   - `confidence_interval_calc`: Sample mean margin of error $E = z^* \frac{\sigma}{\sqrt{n}}$ and two-sided confidence interval.
   - `bayes_posterior_calc`: Exact Bayesian posterior probability $P(H|E)$.
   - `regression_residual_audit`: Residual computation $e_i = y_i - \hat{y}_i$ and leverage/outlier classification.
5. **Quantitative Biology & Bioinformatics (`practice_bio.py`)**:
   - `dna_transcription_translate`: $5' \to 3'$ DNA transcription to mRNA and codon translation into peptide sequence.
   - `hardy_weinberg_calc`: Allele frequencies $p, q$ and genotype frequencies $p^2, 2pq, q^2$.
   - `enzyme_michaelis_menten`: Initial velocity $v_0 = \frac{V_{\max}[S]}{K_m + [S]}$ and Lineweaver-Burk parameters.
   - `genomic_gc_content`: GC-content percentage and primer melting temperature $T_m$ calculation.



