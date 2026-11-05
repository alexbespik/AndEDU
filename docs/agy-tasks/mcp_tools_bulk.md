# Task for agy: cross-subject MCP tools (no UI)

Read `docs/agy-tasks/README.md` first.

Files you may edit:
- new `mcp_tools_studio.py`, plus one line in the `mcp_server.py` tuple
- new `tests/test_mcp_studio.py`
- `server.py`: only the three small endpoints in section B

Every tool goes through the backend over HTTP, the way the existing tools do, so the existing accounts-mode owner checks
(`require_topic_write`) apply. Tools that change content must return what changed.

## A. Tools built on existing endpoints (no server change)
| tool | does | endpoint(s) |
| --- | --- | --- |
| `quiz_from_flashcards(topic_id, count=5)` | Builds offline multiple-choice questions from the cards, using the other cards' backs as distractors | GET topic, POST `/quiz` |
| `flashcards_from_glossary(topic_id, text, lang?)` | Parses `term: definition` or `term - definition` lines | POST `/flashcards` |
| `match_pairs_from_flashcards(topic_id, count=6)` | Picks 3-8 cards | POST `/practice` |
| `timeline_from_text(topic_id, text)` | Parses `1789 - Storming of the Bastille` lines (BCE allowed) | POST `/timeline` |
| `copy_activities(from_topic, to_topic, kinds)` | Copies practice, flashcards and timeline between lessons, with new ids | GET + POSTs |
| `topic_stats(topic_id)` | Counts by activity type, checks on quiz verification and missing explanations | GET topic |
| `lint_topic(topic_id)` | Reports quiz items without an explanation, duplicate questions, practice items with no hint, empty cheat sheet | GET topic |
| `search_topics(query, workspace?)` | Searches titles and summaries | GET `/api/topics` |
| `course_outline(course_id)` | Lists classes with status, scores and activity counts | GET course + topics |
| `student_dashboard(user_id)` | XP, streak, goal, badges, review due, weakest classes | GET engage, review session, courses |
| `review_queue(user_id)` | Missed questions due today | GET `/api/review/{user}/session` |
| `open_workspace(mode, tab?)` | Puts any workspace and sub-tab on screen | POST event `SWITCH_STUDIO_MODE` |
| `daily_challenge(user_id)` | Builds a 10-item mix from the user's weakest topics and opens it (languages: `start_language_session` mode missed) | GETs + event |

## B. Tools that need one small endpoint each (`server.py`, add next to the practice endpoints, with an owner check through `_load_topic_or_404`)
| tool | endpoint |
| --- | --- |
| `remove_practice_item(topic_id, item_id)` | `DELETE /api/topics/{id}/practice/{item_id}` |
| `replace_practice_item(topic_id, item_id, item)` | `PUT /api/topics/{id}/practice/{item_id}` (normalized, and keeps its id so XP refs stay stable) |
| `remove_flashcard(topic_id, index)` | `DELETE /api/topics/{id}/flashcards/{index}` |

Each endpoint saves through `save_topic`, emits `TOPIC_UPDATED`, and gets tests: one for owner-only in accounts mode and
one for 404 on an unknown id.

## Done when
- `tools/list` shows the 16 new tools with clear one-line descriptions.
- Every pure parsing helper (glossary, timeline text, quiz builder) has unit tests that run offline with `call` stubbed.
- The tests and the build pass.
