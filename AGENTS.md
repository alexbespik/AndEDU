# AGENTS.md — working on &.edu LAB

&.edu LAB turns a student's materials into an adaptive course: a diagnostic quiz, then a sequence of
generated classes (lesson, simulation, quiz, practice puzzles), each shaped by how the student did so far.
Autonomous agents (agy, Claude Code, background loops) can add lessons and simulations without touching
frontend code.

## Workspaces
My courses (one place to add materials: learn, test prep, continue a course, coding practice) ·
**Lab** (physics and chemistry library and lab-course classes; internal mode id `physics`) ·
**IDE** (code, `EduStudioIDE.jsx`) · **Math** (`MathLab.jsx`: Class, Courses, Graph, Notebook, Practice, Sim kit).
Every course has `workspace` = `math` | `code` | `lab` (planner sets it; `server.guess_workspace` is the
fallback) and its class topics carry it in `source.workspace`; `src/App.jsx` opens each class there.

## Architecture
- **Frontend:** React 19 + Vite (`src/`). Styling lives in `src/styles/lab.css` (light, dark and system
  themes from one token set); `src/theme.js` maps inline styles to the same CSS variables.
- **Backend:** FastAPI `server.py` on **127.0.0.1:8090** only (Vite proxies `/api`). Do not bind it to
  `0.0.0.0`: its code sandbox and agy runner act with the user's permissions.
- **Storage:** topic JSON files in `content/topics/<id>.json` (the live format agents write) plus SQLite
  `content/edu_studio.db` (`db.py`): profiles, courses, ordered classes, lesson snapshots, quiz attempts.
- **Simulations:** built-in canvases (`simulationType`: `rolling_without_slipping`, `billiard_collisions`)
  or declarative **SimSpec v1** JSON in a topic's `simulation` field, validated by `simspec.py`.
- **Background jobs:** course planning, class generation and simulation authoring run as jobs
  (`GET /api/jobs`); the UI follows them through `/api/agy/events`.

## Topic JSON
```json
{
  "id": "quantum-tunneling",
  "title": "Quantum Tunneling",
  "category": "Quantum Mechanics",
  "difficulty": "Upper Undergraduate",
  "summary": "One or two sentences.",
  "cheatSheet": [{ "label": "Transmission", "formula": "T \\approx e^{-2\\kappa a}" }],
  "mermaid": "graph TD; A[\"Incident\"] --> B[\"Evanescent\"]",
  "markdownContent": "# Quantum Tunneling\n\nDerivation with $LaTeX$ ...",
  "quiz": [{
    "id": "q1", "question": "If width $a$ doubles, $T$ ...",
    "options": ["halves", "drops as $e^{-4\\kappa a}$", "is unchanged", "is zero"],
    "correctAnswer": 1, "hint": "...", "explanation": "..."
  }],
  "practice": [
    { "type": "fill_blank", "prompt": "... ___ ...", "options": ["a", "b", "c", "d"], "answer": "b", "explanation": "..." },
    { "type": "order_steps", "prompt": "Order the steps", "steps": ["first", "second", "third"], "explanation": "..." },
    { "type": "numeric", "prompt": "Compute ...", "answer": 4.2, "tolerance": 0.02, "unit": "m/s", "explanation": "..." },
    { "type": "true_false", "prompt": "Statement", "answer": false, "explanation": "..." }
  ],
  "simulation": { "kind": "graph", "...": "see SimSpec below" }
}
```
Rules:
- `id` is kebab-case (`^[a-z0-9][a-z0-9-]*$`); it becomes the file name. Anything else is rejected.
- `correctAnswer` is a 0-based index into `options` (older files used `correct`; the server converts it).
- Cheat-sheet formulas are LaTeX **without** `$` delimiters; everything else uses `$...$` / `$$...$$`.
- The server normalizes and returns `warnings` for anything it had to drop.

## SimSpec v1 (simulations for any topic)
Data only, never code: the browser evaluates expressions with its own small interpreter.
- Print the full format: `python3 scripts/agent_add_topic.py --sim-guide` or `GET /api/simulations/guide`.
- Check a spec before saving: `python3 scripts/agent_add_topic.py --validate-sim spec.json` or
  `POST /api/simulations/validate` (returns every error with its location).
- `kind: "particles"` for anything that moves (projectiles, pendulums via `links: rod`, springs, orbits via
  `gravitation`, charges via `custom` forces); `kind: "graph"` for y = f(x, t) families (waves, gas laws,
  distributions). Give 2–5 sliders and a `description` that tells the student what to try.
- `kind: "math"`: one of 9 widgets (epsilon_delta, epsilon_n, secant_tangent, riemann, series, unit_circle,
  parametric, vector_field, transform2d), see `simspec.MATH_GUIDE`; played by `src/simulations/MathSim.jsx`.
  Math classes get these automatically. `kind: "chem"` is reserved for the chemistry kit (`chemspec.py`).
- Or let the server author one: `POST /api/simulations/generate {"topicId": "..."}`, or fill every topic that
  lacks one with `POST /api/simulations/backfill`.

## SimSpec Player (built & verified)
`src/simulations/SpecSim.jsx` plays both `kind: "particles"` and `kind: "graph"` SimSpec v1 declarative simulations.
- Reuses `src/lib/expr.js` (safe math closures) and `src/theme.js` (`canvasPalette()` for dark/light theme tokens).
- Integrated with 240 Hz substepped semi-implicit Euler integration, spring/damping forces, drag, mutual gravitation with softening, custom forces, rigid rod distance constraints (relaxation), world boundaries (ground & walls with restitution), trails, vectors, and live rolling series charts.
- `src/components/TopicViewer.jsx` automatically shows the Simulation tab whenever `topic.simulation` is present.
- `server.py`: `AUTHOR_SIMS` defaults to ON, `agy_create_simulation_tool` is active in `agy_agent_tools`, and prompt instructions are restored.
- All 24 unit tests pass cleanly.
- Done when: a pendulum (rod), a spring with damping, a two-body orbit and an animated standing wave render
  and respond to sliders in both themes, and `python -m unittest discover -s tests` still passes.

## Commands & API
```bash
python3 scripts/agent_add_topic.py --file my_topic.json   # validate + save a topic
python3 scripts/agent_add_topic.py --template             # starter topic
```
| Method & path | Purpose |
| --- | --- |
| `GET /api/topics`, `GET /api/topics/{id}`, `GET /api/topics/version` | read topics / cheap change check |
| `POST /api/topics` | create or update a topic (normalized, validated) |
| `POST /api/simulations/validate` · `generate` · `backfill`, `GET /api/simulations/guide` | simulations |
| `POST /api/users {name}`, `GET /api/users/{id}/courses` | local profiles and their courses |
| `POST /api/courses`, `GET /api/courses/{id}` | create a course (diagnostic + syllabus job) / read it |
| `POST /api/courses/{id}/diagnostic` · `skip-diagnostic` · `resume` | start or resume class generation |
| `POST /api/courses/{id}/classes/{seq}/regenerate {"instruction": "..."}` | rewrite one class with guidance |
| `POST /api/courses` with `"mode": "test_prep"`, `"exam_date"` | exam review classes, 8-question exam-style quizzes, final mock exam |
| `POST /api/courses/{id}/extend {"materials_text", "goal", "class_count"}` | continue a course: new materials become the next classes |
| `POST /api/math/practice {"topic", "level", "count"}` | math problems; numeric answers recomputed from a `compute` expression, mismatches dropped |
| `DELETE /api/courses/{id}` | delete a course and its classes |
| `POST /api/quiz/submit` | record an answer (updates the class score) |
| `GET /api/agy/events?since=<cursor>` | UI events; first call with no `since` returns only the cursor |
| `POST /api/agy/events` | push `SWITCH_TOPIC`, `SWITCH_TAB`, `SET_SIM_CONFIG`, `TOPIC_UPDATED` |
| `GET /api/jobs`, `GET /api/jobs/{id}` | background job status |

## Adaptation and answer checking
- Finishing a class quiz under 50% rewrites the next unstarted class one level easier with more support;
  90% or more makes it harder (`adapt_next_class`). The class row stores the `instruction` and `adapted_from` score.
- Every diagnostic and class quiz is re-solved by a second model (`verify_questions`). Questions carry
  `check: {verdict: verified|corrected|ambiguous|low-confidence, confidence, note}`; keep it when editing a topic.
- Model roles: `SCIEDU_PLANNER_MODELS` (diagnostic, syllabus, answer checks) and `SCIEDU_LESSON_MODELS`
  (lessons, quizzes, practice), comma-separated, in `.env`. Both fall back to the built-in model list.

## Socratic tutor (from &EDU)
`POST /api/tutor/lesson {"topicId", "message", "history": [{role, content}], "mode": "chat"|"brief", "focus"?}`
answers in the &EDU mentor style: short, one leading question, no spoilers for unanswered items. `mode: "brief"`
returns Goal / Key idea / Check yourself. The spoken lecture (`/api/elevenlabs-voiceover`) sits in each topic's
"More" menu; it uses the browser's voice unless `SCIEDU_ELEVENLABS=1`.

## Engagement (engage.py)
XP for real learning actions, a daily goal (10/20/30/50), streaks with freezes (one earned every 7 days,
max 2), three daily quests, 12 badges, and spaced review: every missed quiz question returns after
1, 3, 7, 14 and 30 days (`/api/review/{user}/session|answer|finish`). The server sets every amount and
pays each (source, ref) once per day or once ever; browsers only report what happened via
`POST /api/engage/{user}/xp` (practice, math, IDE, simulations, reading). Days follow the browser's
`X-Local-Day` header (accepted within a day of UTC). Focus mode hides streaks, XP and celebrations.

## Spending guards
- `SCIEDU_DAILY_MODEL_CALLS` (default 400): Gemini requests per day across all features, fallbacks included.
- `SCIEDU_RATE_SCALE`: per-user hourly limits on generation (see `RATE_LIMITS` in server.py).
- `AGY_DAILY_RUNS` (default 15): agy CLI runs per day, one at a time; Gemini answers when capped or busy.

## Running agy from the in-app assistant
The companion uses Gemini tools by default and receives the course the student has open (`courseId`), so
"make class 2 easier" calls its `adjust_class` tool. To route prompts through the Antigravity CLI instead (personal machine only: agy runs on your own
Antigravity subscription, which is for your own supervised work; the server never runs it when
`SCIEDU_AUTH=1`, and caps it with `AGY_DAILY_RUNS`):
`AGY_CLI=1` (and only if you accept that it edits files without asking, `AGY_SKIP_PERMISSIONS=1`).
Prompts can come from uploaded documents, so keep skip-permissions off unless you trust every input.
