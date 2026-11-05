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
| **Pedagogical Engagement** | `engage.py` | gamified positive engagement loop: XP ledger, daily goals, streak freezes, quests, 12 badges, and Leitner spaced-review scheduler. | `db.py` | Tables: `xp_events`, `engage_prefs`, `freeze_days`, `activity_results`, `review_items`. |
| **Language Acquisition & AI** | `src/components/LanguageLab.jsx`, `src/components/LanguageRoleplay.jsx`, `src/lib/langgrade.js`, `src/practice/language.jsx` | gamified practice drills (translate, word bank, listen, speak), AI roleplay conversational partner with Web Speech API audio, and Socratic explain-answer tutoring. | Web Speech API, `src/lib/speech.js` | Browser localStorage preferences (`andedu_pron_lang`, roleplay history). |
| **Interactive History Engine** | `src/components/HistoryLab.jsx`, `src/components/HistoryCrisisLab.jsx`, `src/components/PrimarySourceLab.jsx` | Branching counterfactual decision dilemmas ("What If?"), primary source document interrogator with SHEG sourcing criteria, and chronological ordering challenges. | React 19, Lucide | Curated crisis decision trees, primary source document library. |
| **Academic Advisor** | `advisor.py` | University course catalog ingest (W&M focus), class section schedules, prerequisite dependency graphing (CNF tree), degree audit (W&M COLL curriculum + proficiencies), and readiness diagnostics. | `db.py` | Tables: `catalog_courses`, `completed_courses`, `catalog_sections`. |
| **Physics & Math Simulation Engine** | `simspec.py`, `src/simulations/SpecSim.jsx`, `src/lib/expr.js` | SimSpec v1 declarative specification validation and execution. Safe expression AST parser, 240Hz substepped physics solver, math widget kit. | Python `ast`, JS Pratt parser | Declarative SimSpec JSON (`kind: "particles"`, `"graph"`, `"math"`). |
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
    "workspace": "math | code | lab | history | language"
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
  `PRACTICE_TYPES` set), client `src/practice/registry.js`, which merges each subject file's map (`src/practice/language.jsx`,
  `src/practice/history.jsx`). Subject bodies take `{item, onResult(ok, given), retry}` (`ok === null` = skipped) so both
  `PracticeDeck` and the Languages session can use them. MCP tools follow the same split: `mcp_tools_<subject>.py` exports
  `tools(call, q, S, STR, OBJ, ARR)` and `mcp_server.py` merges them.
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
   - Multi-curve renderer (color palette rotation from theme tokens) with vertical asymptote/discontinuity detection.
   - Interactive numerical calculus: numerical derivative $f'(x)$, tangent line cursor tracking, definite integration $\int_a^b f(x)\,dx$ (Simpson's rule), root finding (bisection with pole filtering), and local extrema detection.
   - Canvas View Controls Overlay: Quick Zoom In (`+`), Zoom Out (`-`), and Reset Home (`Crosshair`) floating buttons on the graph canvas.
2. **Values Table Tool (`ValuesTable`)**:
   - Bidirectional $x \to y$ table generator for the active curve.
   - Plots discrete scatter probe points directly on the canvas with coordinate tooltips.
3. **On-Screen Math Keypad (`MathKeypad`)**:
   - Multi-tab virtual keypad (`123` basic/algebraic, `Trig` trigonometric/inverse/hyperbolic, `Func` calculus/stats/special).
   - Non-blurring insertion (`onMouseDown={e => e.preventDefault()}`) targeting the active formula input, calculator input, or notebook editor.


### 3.3 Course Advisor & Degree Audit Data Contracts
- **Prerequisite CNF Tree (`prereq_tree`)**: Prerequisites are parsed into Conjunctive Normal Form (AND of OR-choice groups): `List[List[str]]` (e.g. `[["CSCI 141"], ["MATH 111", "MATH 131"]]`). Satisfaction requires at least one course in each inner OR-clause to have a passing grade (`PASSING`).
- **Readiness Contract (`/api/advisor/{user_id}/readiness/{code}`)**:
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
    "status": "met | missing | none | unknown",
    "taken": false
  }
  ```
  - `status: "none"`: Course has no prerequisites (explicit none or introductory level < 300).
  - `status: "unknown"`: 300+ course with empty prerequisite field in catalog data; `met` evaluates to `false` preventing false-positive recommendations.
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

#### 3.5.1 Branching Crisis Decision Simulator (`POST /api/history/generate-crisis` & `src/components/HistoryCrisisLab.jsx`)
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

---

## 4. Workspaces & UI Presentation Architecture

The user interface is structured as seven primary modes rendered through `src/App.jsx`:

1. **My courses (`home`)**: Course setup wizard (materials upload/prompt), active course cards, streak status, daily review launch.
2. **Lab (`physics`)**: Classical mechanics, physics simulations, chemistry kit (`ChemSim.jsx`), and topic library sidebar.
3. **IDE (`code` / `class`)**: Code editing, algorithm challenges, browser WebAssembly execution (Pyodide), and Socratic code mentor.
4. **Math (`math`)**: Class notes, interactive function graphing (interactive sliders for free variables), LaTeX scratchpad, practice problems, and 9-widget Math Sim kit.
5. **History (`history`)**: Five interactive tools rendered via `src/components/HistoryLab.jsx`:
   - `class`: Current sequential class topic and adaptive lesson viewer.
   - `courses`: Subject syllabus progress, enrolled history courses, and historical eras.
   - `crisis`: Branching counterfactual Crisis Simulator ("What If?" decision dilemmas).
   - `sources`: Primary Source Interrogator with document annotations and SHEG analytical framework.
   - `timeline`: Interactive chronology with sorting, era filtering, and drag-and-drop event ordering challenge.
   - `cards`: Merged historical flashcard deck for people, treaties, and key terms.
6. **Languages (`language`)**: Five interactive tools rendered via `src/components/LanguageLab.jsx`:
   - `class`: Current sequential language class with lesson text and activities.
   - `courses`: Enrolled language courses, CEFR proficiency levels (A1 to C2), and syllabus outlines.
   - `practice`: gamified Practice Hub aggregating interactive drills (`translate`, `word_bank`, `listen_type`, `listen_choose`, `speak`).
   - `roleplay`: AI conversational AI partner with real-time speech synthesis/recognition and instant grammar feedback.
   - `cards`: Spaced-repetition vocabulary flashcards read aloud via native Web Speech synthesis.
   - `speech`: Speech Lab & IPA reference chart (`PronounceTab.jsx`) with microphone voice-matching.
7. **Advisor (`advisor`)**: Academic record tracking, prerequisite degree requirements, catalog search, and prerequisite readiness courses.

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
  - Interrupted runs: On backend startup (the app lifespan, `resume_course_generation`), `db.reset_stuck_classes()` resets orphaned `generating` records to `pending`, and `db.interrupted_planning()` reschedules syllabus generation jobs from stored materials.
  - Academic Advisor catalog tables:
    - `catalog_courses`: Master catalog course specifications (`school`, `code` PRIMARY KEY, title, credits, description, prerequisites, prereq_codes, attributes, syllabus, `prereq_tree` JSON CNF representation).
    - `completed_courses`: Student academic records (`user_id`, `code` PRIMARY KEY, title, grade, term).
    - `catalog_sections`: Scheduled course offerings per term (`school`, `term`, `crn` PRIMARY KEY, `code`, section, title, instructor, meeting times, schedule type, seats, status, credits). Indexed on `(school, code)` and `(school, term)` for sub-millisecond section lookups. Raw schedule feeds cached under `content/catalog_cache/classes_<term>.json`.

### 5.2 Background Jobs & Event Processing
- **Queue Architecture**: An in-memory dictionary `JOBS` (capped at 100 entries) runs background coroutines via `asyncio.create_task` or threadsafe dispatch onto `MAIN_LOOP`.
- **Client Synchronization**:
  - Events are assigned monotonic sequence numbers (`_event_seq`).
  - Frontend subscribes via `useAgyEvents` in `src/lib/api.js`, issuing cursor-based requests: `GET /api/agy/events?since=<cursor>`.
  - When `since < 0` (first load), the server returns the latest cursor without replaying past UI events, preventing unwanted tab switches or navigation replays.
  - Multi-user isolation: When `SCIEDU_AUTH=1`, private event types (`COURSE_UPDATED`, `JOB_UPDATE`, `CLASS_ADAPTED`, etc.) are filtered by `owner == CURRENT_USER.id`.

### 5.3 Docker Deployment Configuration
- **Container Strategy**: Single multi-stage container.
  - Stage 1 (`node:22-alpine`): Compiles React 19 frontend into static production assets (`dist/`).
  - Stage 2 (`python:3.12-slim`): Installs backend dependencies from pinned `requirements.txt`, seeds default topics into `/app/seed/topics`, and mounts `/app/dist` directly into FastAPI (`app.mount("/", StaticFiles(directory=DIST_DIR, html=True))`).
- **Isolation**: Runs as unprivileged user `lab` (`uid: 10001`). Data volume `/app/content` preserves SQLite database and generated lessons.
- **Process model (contract)**: exactly one uvicorn process, one worker. `JOBS`, `ui_events_queue`/`_event_seq`, rate buckets (`_rate_hits`) and the agy lock live in process memory, so `--workers N` or several replicas would split jobs and events between processes and multiply every limit by N. Scale up (threads, async) before scaling out; moving that state to SQLite is the prerequisite for more workers.
- **Image contents**: only library lessons belong in the seed; `content/topics/course-*.json` are per-student lessons (git-ignored) and must stay out of the build context (`.dockerignore`).
- **Security Boundaries**: In production, `SCIEDU_AUTH=1` is enforced whenever listening on non-loopback addresses (`0.0.0.0`), preventing unauthenticated access to the sandbox or model endpoints.

---

## 6. Spending Guards & Resource Bounds

| Guard | Default Value | Environment Variable | Enforcement Level |
| :--- | :--- | :--- | :--- |
| **Daily Gemini Model Budget** | 400 requests/day | `SCIEDU_DAILY_MODEL_CALLS` | Global hard ceiling across all model calls and retries. Resets at midnight UTC. |
| **Rate Scale Multiplier** | 1.0 (enabled) | `SCIEDU_RATE_SCALE` | Sliding hourly window per user / IP address: Course creation (10/hr), class generation (40/hr), agy assistant (60/hr), simulation generation (20/hr), uploads (30/hr), IDE (120/hr), chat (240/hr). |
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
| `SCIEDU_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | No | Comma-separated CORS allowed origins. |
| `SCIEDU_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` | No | Comma-separated list of allowed HTTP `Host` headers to prevent DNS-rebinding attacks. |
| `SCIEDU_ADMINS` | `""` | No | Comma-separated user ids (shown in the account menu) with administrative permissions (catalog imports, library topic updates, agent inbox). Names are not accepted. |
| `SCIEDU_RATE_SCALE` | `1.0` | No | Multiplier for hourly rate limits. Set to `0` to disable rate limiting in automated testing. |
| `SCIEDU_DAILY_MODEL_CALLS` | `400` | No | Hard daily request quota across all Gemini models. |
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

---

## 8. Model Context Protocol (MCP) Expanded Tool Suite

`mcp_server.py` implements a zero-dependency JSON-RPC 2.0 interface enabling autonomous agents (agy, Claude Code, Cursor) to author content, execute pedagogical actions, and project interactive learning widgets directly onto the student's screen in real time.

### 8.1 Tool Catalog by Discipline

#### Language Acquisition & gamified Drills
- `add_translate_drill`: Append translation exercises with source text, target language, and alternate acceptable phrasing.
- `add_word_bank_drill`: Append sentence chip scramble puzzles with distractor tokens.
- `add_listening_drill`: Append audio dictation (`listen_type`) or audio multiple-choice (`listen_choose`) comprehension drills with normal and turtle speeds.
- `add_speaking_drill`: Append pronunciation speaking tasks with target text, IPA transcription, and speech-recognition scoring.
- `batch_add_language_unit`: Append a complete language unit including vocabulary, dialogue, and comprehensive drill decks.
- `start_language_practice`: Dispatch `SWITCH_STUDIO_MODE {mode: "language", tab: "practice"}` to launch drills for a specific target language.

#### AI AI Features
- `start_roleplay`: Launch an interactive conversational scenario on the student's screen (`SWITCH_STUDIO_MODE {mode: "language", tab: "roleplay"}`), seeding scenario context, avatar persona, and initial greeting.
- `explain_answer`: Query the Socratic pedagogical tutor (`POST /api/tutor/explain-answer`) for an in-depth breakdown of grammar rules, conjugation tables, or false friends for any problem.

#### Interactive History Engine
- `start_historical_crisis`: Dispatch `SWITCH_STUDIO_MODE {mode: "history", tab: "crisis"}` with a counterfactual dilemma (e.g. Cuban Missile Crisis, Crossing the Rubicon), seeding choices and historical reality notes.
- `add_crisis_scenario`: Attach a branching historical crisis dilemma to a specific lesson topic.
- `open_primary_source`: Dispatch `SWITCH_STUDIO_MODE {mode: "history", tab: "sources"}` to open an annotated historical document (e.g. Magna Carta, Code of Hammurabi) with sourcing analysis questions.
- `add_primary_source_lab`: Attach an authentic annotated primary source with SHEG questions to a history topic.

#### Navigation & Screen Control
- `switch_workspace_tab`: Route the browser UI to any subject workspace (`history`, `language`, `math`, `lab`, `code`, `advisor`) and specific sub-tab (`crisis`, `sources`, `roleplay`, `practice`, `timeline`, `speech`).

