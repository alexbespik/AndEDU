# Architectural Refactoring & Scaling Plan

This document outlines the concrete refactoring targets, module decomposition blueprints, and scalability pathways for &.edu (SciEdu-Studio).

---

## 1. Modularization of `server.py`

### 1.1 Problem Statement
`server.py` is currently a monolithic file (252 KB, 4,844 lines). It conflates:
1. HTTP Middleware (DNS rebinding rejection, session extraction, local day normalization).
2. Rate limiting and daily quota spending guards.
3. Model call orchestration, automatic fallbacks, and search grounding.
4. Multimodal document ingestion and file parsing (`PdfReader`, `docx`, `nbformat`).
5. Legacy curriculum and puzzle generation code (1,500+ lines of fallback data and old endpoints).
6. Course lifecycle management (diagnostics, syllabus planning, sequential class generation).
7. Topic normalization, validation, and storage.
8. Engagement, activity tracking, and Leitner spaced repetition.
9. Academic course advisor and prerequisite analysis.
10. Declarative simulation authoring (`SimSpec`, `ChemSpec`, `MathSim`).
11. Antigravity CLI process execution and security guard agent pipeline.
12. Background job execution and in-memory event queues.

### 1.2 Target Modular Blueprint

```
server.py (Entry point & FastAPI application instantiation)
├── core/
│   ├── config.py           # Environment variables, candidate models, rate limits
│   ├── security.py         # Auth validation, session extraction, foreign host middleware
│   ├── quota.py            # Model call spending guards & rate limit tracking
│   ├── ai_client.py        # Gemini client wrapper, retry logic, cooldown tracking
│   └── events.py           # In-memory event sequence, owner filtering, event emitting
├── routers/
│   ├── auth.py             # /api/auth/*, /api/users
│   ├── courses.py          # /api/courses/*, diagnostics, extend, resume, regenerate
│   ├── topics.py           # /api/topics/*, /api/draw/check, /api/math/practice
│   ├── simulations.py      # /api/simulations/*, /api/ui/*
│   ├── engage.py           # /api/engage/*, /api/activity/*, /api/review/*
│   ├── advisor.py          # /api/advisor/*
│   ├── assistant.py        # /api/agy/*, /api/tutor/*
│   ├── jobs.py             # /api/jobs/*
│   └── legacy.py           # /api/default-curriculum, /api/generate-curriculum, /api/execute-code
├── services/
│   ├── course_planner.py   # Syllabus planning, diagnostic generation, question verification
│   ├── class_builder.py    # Sequential lesson generation, adaptation rules
│   ├── sim_author.py       # SimSpec/ChemSpec/Math authoring loop with validation feedback
│   ├── ingestion.py        # PDF, DOCX, IPYNB text extraction
│   └── agy_runner.py       # Fenced Antigravity CLI sub-process & page-guard verification
└── schemas/
    ├── common.py           # Base models, event models
    ├── course.py           # CourseRequest, ExtendRequest, DiagnosticAnswers
    ├── topic.py            # TopicModel, QuizItem, PracticeItem, DrawingCheck
    ├── sim.py              # SimulationRequest, SimSpecModel
    └── advisor.py          # ReadinessRequest, CatalogImportModel
```

---

## 2. Simulation Engine Extension Architecture

### 2.1 Unified Simulation Registry Pattern
Currently, simulation validation and execution are split across `simspec.py`, `chemspec.py`, `SpecSim.jsx`, `ChemSim.jsx`, and `MathSim.jsx`.

To enable new scientific simulation domains (e.g., biological cell automata, optics ray tracing, quantum circuits) without editing core switch statements, adopt a **Domain Registry**:

```
[SimSpec JSON Spec]
         │
         ▼
[Simulation Engine Registry]
   ├── kind == "particles" ──► ParticlePhysicsEngine (Euler integrator, constraints)
   ├── kind == "graph"     ──► FunctionFamilyEngine (Parametric / time-varying curves)
   ├── kind == "math"      ──► MathWidgetRegistry (9 interactive calculus/algebra widgets)
   └── kind == "chem"      ──► ChemWidgetRegistry (6 kinetics/equilibrium/titration widgets)
```

### 2.2 Immediate Action for Chemistry Authoring
In `server.py:author_simulation`, add a chemistry generation branch utilizing `chemspec.CHEM_GUIDE`:
- Detect chemistry context via course workspace (`lab`), category/title keywords (`chemistry`, `kinetics`, `titration`, `equilibrium`, `gas law`), or explicit parameter `kind="chem"`.
- Output declarative JSON adhering to `kind: "chem"` and validated via `chemspec.validate_chem`.

---

## 3. Storage & Concurrency Scaling

### 3.1 SQLite Connection Pooling & Lifecycle
- **Issue**: `sqlite3.connect` stored in `threading.local` causes `ResourceWarning: unclosed database` when threads terminate in Starlette's threadpool.
- **Done 2026-11-07 (different fix):** the real cause was that `close_all()` could not close other threads'
  connections (`check_same_thread` raised, the error was swallowed) and dead worker threads kept theirs. `db.py` now
  opens with `check_same_thread=False` (still one connection per thread), prunes connections of dead threads in
  `conn()`, and `close_all()` runs at lifespan shutdown. Test-suite warnings went from 151 to 0. The context-manager
  design below was not needed.
- **Original proposal**:
  - Implement a scoped connection manager with automatic cleanup upon request completion.
  - Or wrap database operations in context managers:
    ```python
    @contextmanager
    def get_db():
        conn = sqlite3.connect(DB_PATH, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    ```

### 3.2 Persistent Job & Daily Quota State
- **Issue**: Background jobs and daily Gemini quota counters are purely in-memory. Container restarts cause active jobs to become 404s and reset quota counters.
- **Resolution**:
  - Add `jobs` table to SQLite:
    ```sql
    CREATE TABLE IF NOT EXISTS background_jobs (
        id         TEXT PRIMARY KEY,
        kind       TEXT NOT NULL,
        label      TEXT NOT NULL,
        status     TEXT NOT NULL,
        step       TEXT NOT NULL,
        progress   REAL NOT NULL,
        owner      TEXT,
        result     TEXT,
        error      TEXT,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    );
    ```
  - Store model quota usage in `daily_model_usage(date TEXT PRIMARY KEY, call_count INTEGER)`.

---

## 4. Frontend Performance & Bundle Optimization

### 4.1 Chunk Splitting Strategy
The main bundle chunk (`dist/assets/index-*.js`) is 898 kB due to eager imports of `TopicViewer`, `katex`, `react-markdown`, and sample topic JSONs.

**Optimization Plan**:
1. In `vite.config.js`, configure `build.rollupOptions.output.manualChunks`:
   ```javascript
   manualChunks: {
     vendor_katex: ['katex', 'rehype-katex', 'remark-math'],
     vendor_markdown: ['react-markdown', 'remark-gfm'],
     vendor_lucide: ['lucide-react']
   }
   ```
2. Dynamically import fallback topics (`rollingTopic`, etc.) on demand rather than statically bundling them into `App.jsx`.
3. Lazy-load `TopicViewer.jsx` alongside `EduStudioIDE.jsx` and `MathLab.jsx`.

**Status 2026-11-07:** items 2 and 3 are done (`App.jsx`: the sample topics load only when the server has none or
is offline; `TopicViewer` is lazy inside a local `LessonView` Suspense so MathLab keeps its state). The main chunk
went from 231 kB to 92.5 kB. Item 1 is done for katex and markdown through rolldown `codeSplitting` groups in
`vite.config.js` (not `manualChunks`); a lucide group was not added (open, low value).
