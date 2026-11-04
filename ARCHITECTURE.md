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
| **Academic Advisor** | `advisor.py` | University course catalog ingest (W&M focus), prerequisite dependency graphing, degree audit, and readiness diagnostics. | `db.py` | Tables: `catalog_courses`, `completed_courses`. |
| **Physics & Math Simulation Engine** | `simspec.py`, `src/simulations/SpecSim.jsx`, `src/lib/expr.js` | SimSpec v1 declarative specification validation and execution. Safe expression AST parser, 240Hz substepped physics solver, math widget kit. | Python `ast`, JS Pratt parser | Declarative SimSpec JSON (`kind: "particles"`, `"graph"`, `"math"`). |
| **Chemistry Simulation Kit** | `chemspec.py`, `src/simulations/ChemSim.jsx` | ChemSpec v1 declarative specification validator and HTML5 Canvas simulations for kinetics, equilibrium, acid-base titration, gas laws, reaction coordinates, and radioactive decay. | `simspec.py` | ChemSpec JSON (`kind: "chem"`). |
| **Frontend Shell & Workspaces** | `src/App.jsx`, `src/components/*` | Seven-tab single page application (`home`, `physics`, `code`, `math`, `history`, `language`, `advisor`), theme provider, unified event poller. | React 19, Vite, KaTeX, Lucide | Local browser state, `localStorage` cached profiles/tokens. |
| **Code Studio & IDE** | `src/components/EduStudioIDE.jsx`, `src/lib/pyodide.js` | In-browser Python environment powered by WebAssembly (Pyodide), interactive coding puzzles, and Socratic mentor integration. | Pyodide, Web Workers | Browser-sandboxed code execution results, scratchpad buffers. |
| **MCP Integration** | `mcp_server.py` | Stdio Model Context Protocol (MCP) server translating agent tool calls to local backend REST calls. | `urllib` (std library) | None (stateless proxy). |

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

### 3.2 SimSpec & ChemSpec Grammar Contract
Mathematical expressions in declarative simulations follow a strict grammar shared between `simspec.py` (AST visitor) and `src/lib/expr.js` (Pratt parser):
- **Operators**: `+`, `-`, `*`, `/`, `%`, `^` (or `**`), unary `+`/`-`, comparisons `<`, `<=`, `>`, `>=`, `==`, `!=`.
- **Functions**: `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `sinh`, `cosh`, `tanh`, `sqrt`, `abs`, `exp`, `log`, `log10`, `min`, `max`, `pow`, `floor`, `ceil`, `round`, `sign`, `hypot`, `clamp`, `if`, `fact`.
- **Constants**: `pi`, `tau`, `E`.
- **Security Constraint**: Zero JavaScript `eval()` or `new Function()`. Expressions parse directly into pure JavaScript closure trees.

---

## 4. Workspaces & UI Presentation Architecture

The user interface is structured as seven primary modes rendered through `src/App.jsx`:

1. **My courses (`home`)**: Course setup wizard (materials upload/prompt), active course cards, streak status, daily review launch.
2. **Lab (`physics`)**: Classical mechanics, physics simulations, chemistry kit (`ChemSim.jsx`), and topic library sidebar.
3. **IDE (`code` / `class`)**: Code editing, algorithm challenges, browser WebAssembly execution (Pyodide), and Socratic code mentor.
4. **Math (`math`)**: Class notes, interactive function graphing (interactive sliders for free variables), LaTeX scratchpad, practice problems, and 9-widget Math Sim kit.
5. **History (`history`)**: Historical timelines with ordering challenges, people/event flashcard decks, and cause/consequence quiz assessments.
6. **Languages (`language`)**: Linguistic and language acquisition workspace: Web Speech API synthesis with target BCP-47 language codes, pronunciation guides, and IPA representations.
7. **Advisor (`advisor`)**: Academic record tracking, prerequisite degree requirements, catalog search, and prerequisite readiness courses.

### Design System & Theme Engine
- **Token Source of Truth**: `src/styles/lab.css` defines CSS custom properties for `:root` (light) and `@media (prefers-color-scheme: dark)` / `[data-theme="dark"]`.
- **William & Mary Academic Palette**: Deep Griffin green (`--accent: #0e4a37`, `--brand: #0b3b2c`), warm Caslon gold (`--gold: #c9a24a`, `--gold-text: #6f5114`), warm stone paper (`--paper: #f1f0ea`, `--surface: #ffffff`), and crisp rule borders.
- **Canvas Bridge**: `src/theme.js` exposes `canvasPalette()`, reading computed style variables once per frame, enabling HTML5 Canvas renderers (`SpecSim`, `ChemSim`, `MathSim`, `BilliardSim`) to switch between light and dark themes with zero visual artifacts.

---

## 5. Storage, Concurrency & Infrastructure

### 5.1 SQLite Persistence Model
- **Database file**: `content/edu_studio.db`
- **Concurrency Mode**: WAL (`PRAGMA journal_mode = WAL`) and strict relational integrity (`PRAGMA foreign_keys = ON`).
- **Connection Management**: `db.conn()` maintains thread-local connection handles. Synchronous FastAPI endpoint invocations run in Starlette's threadpool worker threads.
- **Data Lifecycle**:
  - `courses` rows track the master status: `planning` -> `diagnostic_ready` -> `generating` -> `ready` | `error`.
  - `classes` rows track individual lesson generation status: `pending` -> `generating` -> `ready` | `error`.
  - Interrupted runs: On backend startup (`@app.on_event("startup")`), `db.reset_stuck_classes()` resets orphaned `generating` records to `pending`, and `db.interrupted_planning()` reschedules syllabus generation jobs from stored materials.

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
| `SCIEDU_ADMINS` | `""` | No | Comma-separated usernames with administrative permissions (catalog imports, library topic updates). |
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
