# AGENTS.md — working on &.edu

&.edu turns a student's materials into an adaptive course: a diagnostic quiz, then a sequence of
generated classes (lesson, simulation, quiz, practice puzzles), each shaped by how the student did so far.
Autonomous agents (agy, Claude Code, background loops) can add lessons and simulations without touching
frontend code.

## Workspaces
Seven tabs: My courses, Lab, IDE, Math, **History** (`HistoryLab.jsx`: Map with pins on offline maps in `public/maps/`, Figures to chat with in persona mode, daily Games, Sources, Crisis simulator, a timeline with era bands and zoom, all flashcards), **Languages** (`LanguageLab.jsx`: Learn path of
units, practice sessions with free hearts, listening and speaking drills, a word list with strength, flashcards, pronunciation, IPA, plus Stories, Alphabets, Dialogues and Grammar tips from `src/components/language/`; German-first: a language picker (default `de`), the offline A1-A2 German course in `language_de.py` (topics `de-*`, written by `scripts/seed_german.py` or `POST /api/language/seed`), an ä/ö/ü/ß letter bar, der/die/das colours from card `gender`), **Advisor** (course record, catalog, readiness, a planning cart per term: primary/backup, credit gauge, time conflicts, launch in Studio; `advisor_cart.py`). Course `workspace` values: math | code | lab | history | language.
Lesson activities (any subject): Flashcards (`flashcards`), Speed round (Kahoot-style, from `quiz`), Timeline (`timeline`,
with an ordering challenge), practice types `match_pairs` and `draw` (a whiteboard in the app;
`POST /api/draw/check` grades the drawing against its `criteria` with the vision model).
More practice types live in per-subject normalizer modules merged into `server.PRACTICE_NORMALIZERS`, with bodies in `src/practice/<subject>.jsx`:
history (`practice_history.py`) `categorize`, `cause_effect`, `source_analysis`, `map_pins`, `who_am_i`, `date_guess`, `roleplay`;
languages (`practice_language_extra.py`) `story`, `dialogue`, `conjugate`, `script_match`; lab, math and code (`practice_general.py`)
`label_diagram` (offline images in `public/diagrams/` or a data-only `svg_spec`), `sort_by`, `odd_one_out`, `cloze`, `spot_the_bug`.
Fields and drop rules: `GET /api/practice/guide` (the normalizers' docstrings). Course advisor data: `advisor.py` (catalog_courses,
completed_courses); catalog.wm.edu blocks scripts, so catalogs come from `scripts/import_wm_catalog_wayback.py`
(Internet Archive snapshots, e.g. the 2023-24 catalog) or are imported from text/PDF/JSON.
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
    { "type": "true_false", "prompt": "Statement", "answer": false, "explanation": "..." },
    { "type": "translate", "prompt": "Translate", "source": "Good night", "answer": "Buenas noches", "accepted": [], "lang": "es" },
    { "type": "word_bank", "prompt": "Build the sentence", "source": "I eat bread", "answer": "Yo como pan", "bank": ["Yo", "como", "pan", "agua"], "lang": "es" },
    { "type": "listen_type", "prompt": "Type what you hear", "audio_text": "Buenos días", "lang": "es" },
    { "type": "listen_choose", "prompt": "What did you hear?", "audio_text": "gato", "options": ["gato", "pato", "rato"], "answer": "gato", "lang": "es" },
    { "type": "speak", "prompt": "Say it", "target": "Buenas noches", "ipa": "ˈbwe.nas ˈno.tʃes", "translation": "Good night", "lang": "es" }
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
  Math classes get these automatically. `kind: "chem"` is the chemistry kit (`chemspec.py`, rendered by `ChemSim.jsx`).
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

## MCP tools (preferred for agents)
`mcp_server.py` is a dependency-free MCP server (stdio) over the running backend, so every change is validated
and shows up live in the UI. Subject tools live in `mcp_tools_<subject>.py` (merged at start). 117 tools, including: `simulation_guide`, `list_topics`, `get_topic`, `save_topic`,
`validate_simulation`, `attach_simulation`, `generate_simulation` (kind auto | math | physics),
`add_quiz_questions`, `add_practice_items`, `list_profiles`, `list_courses`, `get_course`, `regenerate_class`,
`show_on_graph`, `preview_math_simulation`, `open_topic`; activities `add_flashcards`, `add_timeline_events`,
`add_match_pairs`, `start_speed_round`, `start_flashcards`; advisor `catalog_search`, `catalog_import`, `student_record`,
`add_completed_courses`, `recommend_courses`, `get_cart`, `add_to_cart`, `remove_from_cart`, `set_cart_priority`, `research_cart`, `seed_language_course`, `check_readiness`, `create_readiness_course`, `search_sections`, `get_student_degree_audit`, `get_student_readiness`, `list_completed_courses`, `add_completed_course`, `ask_advisor`; languages (gamified)
`add_translation_exercise`, `add_word_bank`, `add_listening_exercise`, `add_speaking_exercise`, `add_language_exercises`,
`add_vocab_set`, `build_language_unit` (a whole unit offline, no quota), `start_language_session`, `open_language_tab`,
`language_overview`; language extras `add_story`, `add_dialogue`, `add_conjugation`, `add_script_drill`, `add_minimal_pairs`,
`add_dictation`, `import_vocab_csv`, `translate_drill_from_flashcards`, `roleplay_turn`; history `add_categorize`, `add_cause_effect_chain`,
`add_source_analysis`, `add_map_pins`, `add_who_am_i`, `add_date_guess`, `add_roleplay_persona`, `build_history_unit` (offline),
`start_history_activity`, `history_overview`, `chat_as_figure`, `add_timeline_era`, plus the crisis, primary-source and history topic tools;
lab/math/code `add_label_diagram`, `add_sort_by`, `add_odd_one_out`, `add_cloze`, `add_spot_the_bug`, `list_diagram_images`,
`practice_type_guide`; studio (any subject) `quiz_from_flashcards`, `flashcards_from_glossary`, `match_pairs_from_flashcards`,
`timeline_from_text`, `copy_activities`, `topic_stats`, `lint_topic`, `search_topics`, `course_outline`, `student_dashboard`,
`review_queue`, `open_workspace`, `daily_challenge`, `remove_practice_item`, `replace_practice_item`, `remove_flashcard`.
The original task specs are in `docs/agy-tasks/`.
Register it with your client (the backend must be running on 127.0.0.1:8090):
```json
{"mcpServers": {"andedu": {"command": "python3", "args": ["/absolute/path/to/SciEdu-Studio/mcp_server.py"]}}}
```
Claude Code (from the repo root): `claude mcp add andedu -- python3 "$PWD/mcp_server.py"`.
Accounts mode: set `ANDEDU_TOKEN` to a session token; another host: `ANDEDU_API`.

### Writing precise math simulations
Call `simulation_guide`, write a `kind: "math"` spec, `validate_simulation`, then `attach_simulation`.
For proofs give the exact rule the lesson uses, e.g. epsilon-delta for f(x) = 2x - 1 at 3:
`{"kind":"math","widget":"epsilon_delta","f":"2*x - 1","a":3,"L":5,"delta_rule":"eps/2"}`; for x^2 at 2:
`"delta_rule":"min(1, eps/5)"`. The player checks the rule for every eps and plots the largest working delta.

## Commands & API
```bash
python3 scripts/agent_add_topic.py --file my_topic.json   # validate + save a topic
python3 scripts/agent_add_topic.py --template             # starter topic
.venv/bin/python -m unittest discover -s tests   # tests: use the project venv (.venv, or a link to it); system python3 may lack httpx
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
| `POST /api/courses` with `"mode": "semester"`, `"weeks"`, `"class_count"` (≤30) | whole-term single course: the full syllabus (weeks, units, review/midterm/final classes in `classes.meta`) is planned upfront; class 1 is written, the rest are `planned` and each is written when the previous class is finished or opened (at most 2 unread ahead) |
| `POST /api/courses` with `"mode": "problem_sprint"` (`"keep"`: false by default) | short course from uploaded problems: a primer of only what's needed, then one class per problem; steps and answers live only in `classes.meta.sprint` (never in topic JSON) and are scrubbed from every serializer; finishing every part soft-clears the course (`status: cleared`, Undo/Keep), purged after `SCIEDU_SPRINT_RETAIN_DAYS` (7) |
| `POST /api/courses/{id}/classes/{seq}/reveal {part, step}` · `/check {part, value, unit}`, `POST /api/courses/{id}/keep` · `/restore` | sprint desk (`sprint.py`): one step per request; a part's answer only after an attempt or the last step |
| `POST /api/courses` with `"mode": "thematic_reference"` | uploads are only a style reference: a learn course with original problems (items copying ≥30% of a 6-gram window from the uploads are dropped) |
| `POST /api/courses/{id}/classes/{seq}/generate` | write the next `planned` class of a semester course now |
| `DELETE /api/courses/{id}` | delete a course and its classes |
| `POST /api/quiz/submit` | record an answer (updates the class score) |
| `GET /api/agy/events?since=<cursor>` | UI events; first call with no `since` returns only the cursor |
| `POST /api/agy/events` | push `SWITCH_TOPIC`, `SWITCH_TAB`, `SET_SIM_CONFIG`, `TOPIC_UPDATED` (the server also emits `GEMINI_KEY_INVALID` when Google rejects the key; `/api/status.gemini_key_invalid` mirrors it, both off with `SCIEDU_AUTH=1`) |
| `GET /api/jobs`, `GET /api/jobs/{id}` | background job status |
| `PUT` · `DELETE /api/topics/{id}/practice/{item_id}`, `DELETE /api/topics/{id}/flashcards/{index}` | edit or remove one activity (PUT without `type` merges into the item; ids stay stable) |
| `GET /api/practice/guide`, `GET /api/diagrams` | practice type fields; offline diagram names |
| `POST /api/tutor/lesson` with `"mode": "persona", "persona", "era"` | chat with a historical figure, grounded in the lesson |
| `GET` · `POST /api/advisor/{user}/cart`, `PATCH` · `DELETE /api/advisor/{user}/cart/{code}` | planning cart (`term`, `cart_type` primary\|backup, optional `crn`); returns items (each with `priority` must\|want\|nice and a seat-`risk` estimate from past terms, `advisor_risk.py`), credits, load meter, conflicts |
| `GET /api/advisor/{user}/cart/research`, `GET` · `PUT /api/advisor/{user}/prefs {class_year}` | registration order: priority first, then the chance of losing the seat (an estimate from imported schedules; window dates not loaded) |
| `POST /api/language/tts {text, lang, voice?}` → `{url, source}`, `GET /api/language/tts/{hash}.mp3` | ElevenLabs audio with a disk cache (`content/tts_cache/`); `source: "browser"` means use the browser voice |
| `POST /api/topics/{id}/explain {anchors, regenerate?}` → `{segments, cached, voice}` | "Explain it to me": a narrated, spotlighted walkthrough of a lesson (`explain.py`); 8-12 steps pointing at real lesson blocks (`data-explain` ids from `src/lib/explainAnchors.js`), cached in `content/explain_cache/`; audio through `/api/language/tts` with `purpose: "explain"` |
| `POST /api/language/roleplay` | roleplay partner; optional `topicId`, `persona`, `setting`, `goal`; returns `corrections: [{said, better, why}]` |

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
- ElevenLabs audio in Languages only when `SCIEDU_ELEVENLABS=1` and a server key are set (never a client key): `SCIEDU_TTS_DAILY_CHARS` (default 20000, in memory, resets on restart), `SCIEDU_TTS_CACHE_MB` (200), `ELEVENLABS_GERMAN_VOICE_ID`. Cached clips cost nothing. "Explain it to me" narration has its own daily budget `SCIEDU_EXPLAIN_TTS_CHARS` (15000) and a model rate limit (`explain`, 20/h); replays are free. Tests force `SCIEDU_ELEVENLABS=0` so they never spend credits.
- `AGY_DAILY_RUNS` (default 15): agy CLI runs per day, one at a time; Gemini answers when capped or busy.
- Accounts mode admins: `SCIEDU_ADMINS` = comma-separated user ids (shown in the account menu), not names.

## Running agy from the in-app assistant
The companion uses Gemini tools by default and receives the course the student has open (`courseId`), so
"make class 2 easier" calls its `adjust_class` tool. To route prompts through the Antigravity CLI instead (personal machine only: agy runs on your own
Antigravity subscription, which is for your own supervised work; the server never runs it when
`SCIEDU_AUTH=1`, and caps it with `AGY_DAILY_RUNS`):
`AGY_CLI=1`. Prompts come from the page (and uploaded documents), so agy runs fenced: the `andedu-companion`
agent (`.agents/agents/`) ignores your global agy rules and agent team, has no commands or web, may write only
`content/agy_drafts/<id>.json` (per-run permission list). The server then runs the read-only `page-guard` agent on
each draft (injection, wrong answer keys, HTML/links, broken JSON/LaTeX, dropped sections; anything but ALLOW is
deleted) and imports the rest through `save_topic`, keeping each lesson's `id` and `source`. `--dangerously-skip-permissions` is never passed.
