# Task for agy: Languages, the rest of "AI

Context: `src/components/LanguageLab.jsx` (Claude-owned, do not edit) has these tabs: Learn path, Practice sessions with free
hearts, Words with strength, Flashcards, Pronunciation and Courses, plus "Explain my answer". Practice types translate,
word_bank, listen_type, listen_choose and speak already exist. Read `docs/agy-tasks/README.md` first.

Files you may edit:
- new `src/practice/language_extra.jsx`, registered with one import line in `src/practice/registry.js`
- new `src/components/language/*.jsx`
- new `mcp_tools_language_extra.py`, plus one line in the `mcp_server.py` tuple
- new `tests/test_language_extra.py`
- `server.py`: only `_np_*` functions and their registrations, plus part C

To add a tab to LanguageLab, export `EXTRA_LANGUAGE_TABS = [{id, label, icon, render(topics)}]` from
`src/components/language/index.js`. Claude wires that list into LanguageLab afterwards; leave a note in your summary.

## A. Practice types
| type | fields | grading |
| --- | --- | --- |
| `story` | `title`, `lines: [{speaker, text, translation?}]` (4-16), `questions: [{after (line index), question, options, answer}]` | Lines are read aloud one by one with TTS, each speaker with their own voice and rate. The questions appear inline. OK when all are right. |
| `dialogue` | `persona`, `setting`, `goal`, `lang`, `level` | AI roleplay (part C). Ungraded: `onResult(null)` after the goal or 6 turns, then a recap with corrections. |
| `conjugate` | `verb`, `tense`, `lang`, `forms: [[pronoun, form], ...]` (3-8) | Type each form, graded with `gradeText` from `src/lib/langgrade.js`. |
| `script_match` | `script` (hiragana \| katakana \| cyrillic \| hangul \| greek \| arabic \| devanagari), `pairs: [[glyph, romanization]]` (4-10) | Matching that reads each glyph aloud. Reuse `MatchPairs` from `Activities.jsx`. |

Drop rules: `answer` must be in `options`; `lines` and `forms` must be non-empty; `script` must be from the list; `lang` must match
`server.LANG_RE`.

## B. Extra Languages tabs (via `EXTRA_LANGUAGE_TABS`)
- **Stories**: every `story` item across the language units, with a "listen only" mode.
- **Alphabets**: built-in offline script tables for the seven scripts, each with a tap-to-hear grid and a quick `script_match` drill.
  This is the only built-in content; keep each table under 3 KB.
- **Roleplay**: the `dialogue` items, each one a chat with the part C endpoint.
- **Grammar tips**: the lesson markdown sections whose headings contain "grammar" or "tip", collected per unit.

## C. Language roleplay endpoint (`server.py`)
`POST /api/language/roleplay {topicId, persona, setting, goal, lang, level, history}` returns `{reply, corrections: [{said, better, why}]}`.
- The reply is in the target language, at the student's level. Corrections are in English.
- It uses `gemini_json`, the existing per-user rate limits (add a `language_roleplay` entry to `RATE_LIMITS`) and the daily cap.
- In accounts mode (`SCIEDU_AUTH=1`) it requires the session user, the same as `/api/tutor/lesson`.
- Tests stub `server.call_gemini`.

## D. MCP tools (`mcp_tools_language_extra.py`)
- `add_story(topic_id, title, lang, lines, questions)`
- `add_dialogue(topic_id, persona, setting, goal, lang, level)`
- `add_conjugation(topic_id, verb, tense, lang, forms)`
- `add_script_drill(topic_id, script, pairs)`
- `add_minimal_pairs(topic_id, lang, pairs)`: posts one `listen_choose` item per pair, e.g. ship and sheep.
- `add_dictation(topic_id, lang, sentences)`: posts one `listen_type` item per sentence.
- `import_vocab_csv(topic_id, lang, csv_text)`: parses `word,meaning,ipa` itself and calls the existing flashcards endpoint.
- `translate_drill_from_flashcards(topic_id)`: offline. It turns the topic's cards into `translate` items with
  `answer = front` and `source = meaning`.
- `roleplay_turn(topic_id, persona, message, history)` calls part C.

## Done when
- The types have kept/dropped tests.
- Stories play with TTS, and the endpoint is tested offline.
- `tools/list` shows the 9 new tools.
- The tests and the build pass.
