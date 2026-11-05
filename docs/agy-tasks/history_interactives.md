# Task for agy: History lab interactives

Context: `src/components/HistoryLab.jsx` currently has the Class, Courses, All flashcards and Timeline tabs. Its practice types
register through `src/practice/history.jsx` (empty `HISTORY_RENDER` / `HISTORY_LABEL` maps that `registry.js` already
imports), and its MCP tools go in `mcp_tools_history.py` (a `tools()` stub that `mcp_server.py` already merges). Read
`docs/agy-tasks/README.md` first.

Files you may edit:
- `src/components/HistoryLab.jsx`
- `src/practice/history.jsx`
- `mcp_tools_history.py`
- new `src/components/history/*.jsx`
- new `public/maps/*.svg`
- new `tests/test_history.py`
- `server.py`: only the `_np_*` functions, their registrations, the `"history"` entry of `WORKSPACE_EXTRAS`, and part C
- `lab.css`: append `.hist-*` rules only

## A. Practice types (server normalizer + body in `src/practice/history.jsx`)
| type | fields | grading | drop when |
| --- | --- | --- | --- |
| `categorize` | `buckets[2-4]`, `items: [[text, bucket], ...]` (4-12) | every item in its bucket. The student drags items, or taps one and then a bucket | an item's bucket is not in `buckets`; a bucket is empty |
| `cause_effect` | `chain: [event, ...]` (3-6, cause first), `links?: [why, ...]` (len-1) | the student builds the chain from shuffled cards; each `links[i]` is revealed when its join is right | duplicate events |
| `source_analysis` | `source: {text ≤1500, author, date, citation}`, `questions: [{question, options[2-5], answer}]` (2-5) | per question, like `fill_blank`; ok when all are right | no text or no valid question |
| `map_pins` | `map` (`world` \| `europe` \| `mediterranean` \| `americas` \| `asia`), `pins: [{label, x, y, tolerance?}]` (x and y 0-1 on the map, tolerance default 0.06) | the student drags labels onto the map; correct when within tolerance | an unknown map, a coordinate outside 0-1, more than 10 pins |
| `who_am_i` | `clues[3-6]` (hardest first), `answer`, `options[3-5]` | clues are revealed one at a time; fewer clues means more points (shown, not XP) | `answer` not in `options` |
| `date_guess` | `event`, `year` (negative = BCE), `tolerance` (default 5) | a slider or input, with higher/lower hints; up to 3 tries | `year` not a number |
| `roleplay` | `persona`, `era`, `goal` (what the student should find out), `opening` | ungraded: done after 4 student turns, via part C; `onResult(null)` | no persona or goal |

Maps: draw simple offline SVG outlines (public domain, e.g. Natural Earth, simplified to under 150 KB each) in `public/maps/`.
Pins use fractional coordinates of the SVG's viewBox. No tile servers or external URLs.

## B. HistoryLab tabs (keep the existing ones)
- **Map**: every `map_pins` item from the history topics on one map per region. Clicking a pin opens its class.
- **Sources**: all `source_analysis` items, with a reading view and filters by century.
- **Figures**: a list of the `roleplay` personas, each with a chat panel (part C), plus flashcards about people.
- **Games**: a daily mix of `who_am_i`, `date_guess`, `categorize` and the existing timeline ordering challenge, with a score.
- The **Timeline** gains era bands (centuries) and a zoom control.

Report XP via `reportXp('practice_correct', \`hist:${topicId}:${itemId}\`)`, the same as `LanguageLab`.

## C. Persona mode for the tutor (`server.py`, the `/api/tutor/lesson` handler only)
Add `mode: "persona"` with `persona` and `era` in the body:
- Use a fixed system prompt. The model plays the figure in first person, stays in period, corrects false premises and
  says when it doesn't know something.
- It must not invent quotes. Anything it marks "as I recall" must come from the lesson's markdown or timeline.
- Keep it under 120 words and ask the student a question back.
- It reuses the existing rate limits and `SCIEDU_DAILY_MODEL_CALLS`. Test it only with `server.call_gemini` stubbed.

## D. Generation prompt
In `WORKSPACE_EXTRAS["history"]`, ask for 2-3 of the new types per class (always one `categorize` or `cause_effect`,
plus `source_analysis` when the class has a primary source). Use the same compact-example style as the `"language"` entry.

## E. MCP tools (`mcp_tools_history.py`)
- `add_categorize(topic_id, prompt, buckets, items)`
- `add_cause_effect_chain(topic_id, prompt, chain, links?)`
- `add_source_analysis(topic_id, source, questions)`
- `add_map_pins(topic_id, map, pins, prompt?)`
- `add_who_am_i(topic_id, clues, answer, options)`
- `add_date_guess(topic_id, event, year, tolerance?)`
- `add_roleplay_persona(topic_id, persona, era, goal, opening)`

All seven of the above call `POST /api/topics/{id}/practice`.

- `build_history_unit(title, events[], people[], sources?[])`: offline (no model) unit with notes, a timeline, flashcards for
  people, one `categorize` and one `cause_effect`, saved through `POST /api/topics` with `"workspace": "history"`.
  Mirror `mcp_tools_language.unit_topic`.
- `start_history_activity(tab)` posts `SWITCH_STUDIO_MODE {mode: "history", tab}` (map | sources | figures | games | timeline).
- `history_overview()`: history units with counts by type and the timeline span.
- `chat_as_figure(topic_id, persona, message)` calls the persona mode from part C.
- `add_timeline_era(topic_id, start, end, label)` stores eras on the topic via `normalize_timeline` (extend the normalizer
  with an optional `era` field; this is the one exception to the server rule).

## Done when
- Every type has kept/dropped tests in `tests/test_history.py`.
- `tools/list` shows the 12 new tools.
- `build_history_unit` round-trips through the server with nothing dropped.
- Both the tests and the build pass.
- All tabs render in light and dark themes, and on a 375 px wide screen.
