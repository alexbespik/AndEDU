# Claude Handoff — &.edu remaining tasks

> Generated 2026-11-05. All work below is **not yet committed**. Run the test suite
> first, fix any failures, then `git add -A && git commit`.

---

## What's already done (on disk, not committed)

| Area | File(s) | Status |
|------|---------|--------|
| Desmos math parity | `src/lib/expr.js`, `simspec.py`, `server.py`, `MathLab.jsx` | ✅ 253 tests pass |
| Advisor AI chat | `advisor_chat.py`, `AdvisorChat.jsx`, `AdvisorPage.jsx` | ✅ |
| W&M advising KB | `wm_advising.py` — 16 majors, all policies | ✅ |
| Advisor context | `advisor_chat.py` MAX_CONTEXT = 60 000 | ✅ |
| XP rebalance | `engage.py` — capped practice/lesson/sim farming | ✅ |
| History practice types | `src/practice/history.jsx` — 7 types | ✅ 28 tests pass |
| History MCP tools | `mcp_tools_history.py` — 12 tools | ✅ |
| History Lab tabs | `HistoryLab.jsx` — Crisis, Sources, Figures, Games, Timeline | ✅ |
| History CSS | `src/styles/lab.css` — `.hist-*` classes appended | ✅ |
| Map SVGs | `public/maps/{world,europe,mediterranean,americas,asia}.svg` | ✅ |
| Diagram SVGs | `public/diagrams/{atom,cell,circuit}.svg` | ✅ |
| General practice types | `src/practice/general.jsx` — odd_one_out, sort_by, cloze, spot_the_bug, label_diagram | ✅ |
| General MCP tools | `mcp_tools_general.py` — 7 tools | ✅ |
| Language extra types | `src/practice/language_extra.jsx` — story, dialogue, conjugate, script_match | ✅ |
| Language extra MCP | `mcp_tools_language_extra.py` — 9 tools | ✅ |
| Studio MCP bulk | `mcp_tools_studio.py` — 16 tools | ✅ |
| MCP registration | `mcp_server.py` — all 5 modules registered | ✅ |
| Practice registry | `src/practice/registry.js` — all new types imported | ✅ |

---

## What still needs doing

### 1. Run the full test suite and fix failures

```bash
.venv/bin/python -m unittest discover -s tests
npm run lint
npm run build
```

The history coder reported **253/253** passing. But the advisor, general, language-extra,
and studio coders were killed mid-QA. Some tests in the new files may fail or the
server.py edits may conflict. Fix anything broken before proceeding.

**Known risk areas:**
- `server.py` had edits from 4 separate coders running nearly concurrently —
  check for duplicate `_np_*` registrations in `PRACTICE_NORMALIZERS` and duplicate
  route definitions (FastAPI silently uses the first match).
- `src/practice/registry.js` — confirm it imports and merges all of:
  `HISTORY_RENDER/LABEL/TYPES`, `GENERAL_RENDER/LABEL/TYPES`,
  `EXTRA_LANGUAGE_RENDER/LABEL/TYPES`, plus `EXTRA_LANGUAGE_TABS`.
- `mcp_server.py` line 194 — the `for _mod in (...)` tuple should include all 5 modules:
  `mcp_tools_language, mcp_tools_history, mcp_tools_language_extra, mcp_tools_general, mcp_tools_studio`

---

### 2. Advisor MCP tools — verify they exist in `mcp_server.py`

The advisor coder was killed before confirming. Check that these 6 tools exist:
- `search_sections` — `GET /api/advisor/sections?q=...&limit=...`
- `get_student_degree_audit` — `GET /api/advisor/{id}/degree-audit`
- `get_student_readiness` — `GET /api/advisor/{id}/readiness/{code}`
- `list_completed_courses` — `GET /api/advisor/{id}/completed`
- `add_completed_course` — `POST /api/advisor/{id}/completed`
- `ask_advisor` — `POST /api/advisor/{id}/ask`

If missing, add them to `mcp_server.py` in the advisor tools section.

---

### 3. Backend endpoints — verify these exist in `server.py`

The history-backends coder was also killed. Check for and add if missing:

```python
GET  /api/topics/{id}/crisis          # returns topic["crisis"] list
POST /api/topics/{id}/crisis          # appends/replaces a scenario by id
GET  /api/topics/{id}/primary-source  # returns topic["primarySources"] list
POST /api/topics/{id}/primary-source  # appends/replaces a source by id
DELETE /api/topics/{id}/practice/{item_id}  # remove practice item
PUT    /api/topics/{id}/practice/{item_id}  # replace practice item (keep id stable)
DELETE /api/topics/{id}/flashcards/{index}  # remove flashcard at index
GET    /api/diagrams                        # lists public/diagrams/*.svg names only
GET    /api/practice/guide                  # returns PRACTICE_NORMALIZERS docstrings
POST   /api/language/roleplay               # dialogue practice endpoint
```

Also add `q` and `limit` query params to the existing `GET /api/advisor/sections`
endpoint so agents can filter by department code, term, or instructor name.

---

### 4. LanguageLab extra tabs wiring

Check `src/components/LanguageLab.jsx` — it should pick up `EXTRA_LANGUAGE_TABS`
from `src/components/language/index.js` (or directly from `language_extra.jsx`).
If the file `src/components/language/index.js` doesn't exist, create it:

```js
// src/components/language/index.js
export { EXTRA_LANGUAGE_TABS } from '../practice/language_extra';
```

Then in `LanguageLab.jsx`, find where tabs are assembled and add:
```js
import { EXTRA_LANGUAGE_TABS } from './language/index';
// merge EXTRA_LANGUAGE_TABS into the tabs array
```

The docs/agy-tasks/language_extras.md says:
> "To add a tab to LanguageLab, export `EXTRA_LANGUAGE_TABS = [{id, label, icon, render(topics)}]`
> from `src/components/language/index.js`. Claude wires that list into LanguageLab afterwards."

**This is explicitly your job** (LanguageLab.jsx is Claude-owned).

---

### 5. Syllabus injection in advisor context

In `advisor_chat.py`, the `_course_line()` function — after the `if full and c.get("description"):` block,
also append syllabus when available:

```python
if full and c.get("syllabus"):
    line += f"\n  syllabus: {c['syllabus'][:400]}"
```

Check if the advisor coder already added this. If not, add it.

---

### 6. `WORKSPACE_EXTRAS["history"]` in `server.py`

Confirm the history entry exists in `WORKSPACE_EXTRAS` (the dict that shapes lesson generation
prompts). It should include guidance to generate `categorize`, `cause_effect`, `source_analysis`,
`who_am_i`, `date_guess`, and `roleplay` practice items. If missing:

```python
"history": (
    "For each class include 2-3 history practice items. Always include one 'categorize' "
    "(group events, people or ideas into 2–3 named buckets) or 'cause_effect' (3–5 step causal chain). "
    "Add 'source_analysis' when the topic has a primary source. Add 'who_am_i' (clue-based guessing) "
    "or 'date_guess' (slider) for memorisation. Use 'roleplay' for one key historical figure per topic."
),
```

---

### 7. Persona mode in `/api/tutor/lesson`

History coder added this. Verify it exists: when `req.mode == "persona"` and `req.persona` is set,
the endpoint should use a fixed system prompt playing that persona in first person, ≤120 words,
ends with a question. Test: `POST /api/tutor/lesson {"topicId":"...", "mode":"persona", "persona":"Napoleon", "era":"1815", "message":"What happened at Waterloo?"}`.

---

### 8. Update `AGENTS.md` tool count

At the top of `AGENTS.md` there's a tool count. After verifying everything works,
update the MCP tool count. New totals:
- **mcp_tools_language.py**: 12 tools (unchanged)
- **mcp_tools_history.py**: 12 tools (was 5)
- **mcp_tools_language_extra.py**: 9 tools (new)
- **mcp_tools_general.py**: 7 tools (new)
- **mcp_tools_studio.py**: 16 tools (new)
- **+ advisor tools in mcp_server.py**: +6 tools
- **Total**: ~109 → ~153 tools

---

### 9. Git commit

Once all tests pass:
```bash
git add -A
git commit -m "feat: History interactives, Language, general activities, Advisor AI, Desmos parity

- 7 history practice types (categorize, cause_effect, source_analysis, map_pins, who_am_i, date_guess, roleplay)
- 4 language extra types (story, dialogue, conjugate, script_match)  
- 5 general practice types (odd_one_out, sort_by, cloze, spot_the_bug, label_diagram)
- History Lab: Crisis, Sources, Figures, Games, Map, Timeline tabs
- Language Lab: Stories, Alphabets, Grammar extra tabs
- 44 new MCP tools across 4 new modules
- Advisor AI chat with 60k context, 16 major roadmaps, all W&M policies
- Desmos math parity: pi, tau, phi, all trig/hyperbolic/special functions
- XP rebalance: cap passive farming, reward real learning"
```

---

## Test commands

```bash
# Python tests (the .venv is a symlink — works from the repo root)
.venv/bin/python -m unittest discover -s tests

# Individual suites
.venv/bin/python -m unittest tests.test_history -v
.venv/bin/python -m unittest tests.test_general_activities -v
.venv/bin/python -m unittest tests.test_language_extra -v
.venv/bin/python -m unittest tests.test_mcp_studio -v
.venv/bin/python -m unittest tests.test_advisor_chat -v

# Frontend
npm run lint    # expect 0 errors
npm run build   # expect success
```

## Key files to reference

- `docs/agy-tasks/README.md` — rules for all tasks
- `docs/agy-tasks/language_extras.md` — language extras spec (LanguageLab wiring is yours)
- `docs/agy-tasks/history_interactives.md` — history spec (fully implemented)
- `docs/agy-tasks/mcp_tools_bulk.md` — studio MCP spec (implemented)
- `docs/agy-tasks/other_subject_activities.md` — general activities spec (implemented)
- `src/practice/language.jsx` — reference implementation for practice type pattern
- `mcp_tools_language.py` — reference implementation for MCP tool pattern
