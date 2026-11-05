# Task for agy: interactive activities for Lab, Math and IDE classes

Read `docs/agy-tasks/README.md` first.

Files you may edit:
- new `src/practice/general.jsx`, plus one import line in `src/practice/registry.js`
- new `mcp_tools_general.py`, plus one line in the `mcp_server.py` tuple
- new `tests/test_general_activities.py`
- `server.py`: only `_np_*` functions, their registrations, and the `"lab"`, `"math"` and `"code"` prompt extras where they exist

Topic viewers already show every registered type through `PracticeDeck`.

## Practice types
| type | fields | grading |
| --- | --- | --- |
| `label_diagram` | `image` (a path under `public/diagrams/`, an offline SVG) or `svg_spec` (rects, circles, lines and text only, validated server-side with no script and no href), `labels: [{text, x, y}]` (3-8, fractions of the image) | Drag each label onto its spot, within 0.06. |
| `sort_by` | `property` (e.g. "density", "boiling point"), `items: [{text, value}]` (3-7) | Order from low to high. Reveal the values afterwards. |
| `odd_one_out` | `options[4]`, `answer`, `why` | Pick the one that does not belong. |
| `cloze` | `text` with `[[answer]]` or `[[answer\|alt]]` gaps (1-6), `bank?` | Type into or drag into each gap, graded with `gradeText`. |
| `spot_the_bug` | `code`, `language: "python"`, `bug_line` (1-based), `fix?` | Click the buggy line, then optionally run the fix in Pyodide (`src/lib/pyodide.js`). |

Drop rules: coordinates must be in 0-1; values must be numbers; `answer` must be in `options`; the gap count must be 1-6;
`bug_line` must be within the code's line count. An `svg_spec` containing any `<script`, `on*=` or `href` is dropped.

## MCP tools (`mcp_tools_general.py`)
- `add_label_diagram(topic_id, prompt, image | svg_spec, labels)`
- `add_sort_by(topic_id, property, items)`
- `add_odd_one_out(topic_id, options, answer, why)`
- `add_cloze(topic_id, text, bank?)`
- `add_spot_the_bug(topic_id, code, bug_line, fix?)`
- `list_diagram_images()`: lists `public/diagrams/` through a new read-only `GET /api/diagrams` endpoint. This is the one
  allowed new endpoint. It returns names only and must reject path traversal.
- `practice_type_guide()`: returns every practice type's fields and drop rules. Build it from `PRACTICE_NORMALIZERS`
  docstrings via a new `GET /api/practice/guide`. Add a docstring to each new `_np_*`; don't edit the existing ones.

## Done when
- Every type has tests.
- `GET /api/diagrams` is covered by a traversal test (`../server.py` is rejected).
- `tools/list` shows the 7 new tools.
- The tests and the build pass.
