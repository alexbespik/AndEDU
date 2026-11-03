# AGENTS.md — working on &.edu LAB

&.edu LAB turns a student's materials into an adaptive course: a diagnostic quiz, then a sequence of
generated classes (lesson, simulation, quiz, practice puzzles), each shaped by how the student did so far.
Autonomous agents (agy, Claude Code, background loops) can add lessons and simulations without touching
frontend code.

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
- Or let the server author one: `POST /api/simulations/generate {"topicId": "..."}`, or fill every topic that
  lacks one with `POST /api/simulations/backfill`.

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

## Running agy from the in-app assistant
The companion uses Gemini tools by default and receives the course the student has open (`courseId`), so
"make class 2 easier" calls its `adjust_class` tool. To route prompts through the Antigravity CLI instead:
`AGY_CLI=1` (and only if you accept that it edits files without asking, `AGY_SKIP_PERMISSIONS=1`).
Prompts can come from uploaded documents, so keep skip-permissions off unless you trust every input.
