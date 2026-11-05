# Tasks for agy (supervised development)

Hand-off tasks for the Antigravity CLI working **on this repo** under supervision. They are development work, not
anything the app runs: never wire them into the runtime `andedu-companion` / `page-guard` agents (`.agents/agents/`).
Nothing here starts on its own; run one task at a time and review its diff.

| File | What it builds | New practice types | New MCP tools |
| --- | --- | --- | --- |
| `history_interactives.md` | History lab: map, sources, figures, games | categorize, cause_effect, source_analysis, map_pins, who_am_i, date_guess, roleplay | 12 |
| `language_extras.md` | Stories, roleplay, conjugation, scripts | story, conjugate, script_match, dialogue | 9 |
| `other_subject_activities.md` | Lab, code and math activities | label_diagram, sort_by, odd_one_out, cloze, spot_the_bug | 7 |
| `mcp_tools_bulk.md` | Cross-subject authoring and progress tools | none | 16 |

Suggested order: `mcp_tools_bulk.md` (no UI), then `history_interactives.md`, `language_extras.md`, `other_subject_activities.md`.

## Rules for every task
- **Read first:** `AGENTS.md`, `ARCHITECTURE.md` §3.1.1–3.1.2, `src/practice/language.jsx` and `mcp_tools_language.py`, which are
  the reference implementation of the contract.
- **Adding a practice type:**
  1. In `server.py`, add one `_np_<type>(p, base)` function next to the others. It returns the cleaned item, or `None` to drop it.
  2. Add it to `PRACTICE_NORMALIZERS` and to `PRACTICE_TYPES`.
  3. Add a body to the task's `src/practice/<subject>.jsx` map. Each body takes `{item, onResult(ok, given), retry}`.
  4. Add a test that a valid item is kept and each malformed shape is dropped.
- **Adding MCP tools:** put them in the task's `mcp_tools_<name>.py`, as `tools(call, q, S, STR, OBJ, ARR) -> [(name, description, schema, fn)]`.
  If the module is new, add it to the tuple in `mcp_server.py` (one line). Every tool calls a backend endpoint. Tools never
  write files and never call models directly.
- **Off limits:** do not edit these files except for the one-line registrations named above:
  - Claude-owned: `src/components/LanguageLab.jsx`, `src/components/PronounceTab.jsx`, `src/practice/language.jsx`,
    `src/practice/registry.js`, `src/components/PracticeDeck.jsx`, `src/lib/langgrade.js`, `src/lib/speech.js`,
    `mcp_tools_language.py`, `tests/test_language.py`, `src/App.jsx`.
  - Uncommitted advisor work: `advisor.py`, `advisor_chat.py`, `advisor_classifier.py`, `wm_advising.py`,
    `src/components/AdvisorPage.jsx`, `src/components/AdvisorChat.jsx`, `scripts/import_wm_*.py`, `scripts/classify_wm_courses.py`.
  - In `server.py`, change only your own `_np_*` functions, the two registrations, and anything the task names explicitly.
    Never rewrite or reorder existing branches.
- **Safety:**
  - No new dependencies (npm or pip).
  - No `eval` or `new Function`.
  - No external network assets: maps and images are offline files under `public/`.
  - The server stays on 127.0.0.1.
  - No `--dangerously-skip-permissions`.
- **Tests:** offline only, no Gemini calls (the tests stub `server.call_gemini`). Import the shared setup with
  `from test_lab import LOCAL, TMP, TestClient, server, topic`, as `tests/test_language.py` does.
- **Styling:** use existing CSS tokens in `src/styles/lab.css` (add `.hist-*`, `.lx-*` or `.act-*` classes at the end) so the
  light, dark and system themes keep working. Colors on canvases come from `canvasPalette()` in `src/theme.js`.
- **Done when:** both `.venv/bin/python -m unittest discover -s tests` and `npx vite build` pass, and every new type renders in
  both themes with no console errors. Update the tool count and list in `AGENTS.md` at the end of the task.
