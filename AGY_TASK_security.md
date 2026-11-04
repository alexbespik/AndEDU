# Task for agy: independent security review of &.edu

Claude did a first pass (see "Already fixed" below). Your job is a **second, independent** review: find what was
missed and check that the fixes hold. **Report only; do not change code.** Write your findings to
`SECURITY_FINDINGS_AGY.md` (format at the bottom). Don't commit.

## Rules
- Test only against the local backend (`http://127.0.0.1:8090`, start it with `python3 server.py`) and local files.
  Never send requests to other hosts (no W&M sites, no scanning).
- No destructive actions: don't delete data, don't touch `.env`, and never print keys or tokens.
- Accounts mode for testing: run a separate instance with `SCIEDU_AUTH=1 SCIEDU_CONTENT_DIR=/tmp/andedu-sec python3 server.py`
  (its own empty data folder) and register two throwaway users. Delete that folder when done.
- Use the existing tests as examples: `tests/test_lab.py` (`class AccountsSecurity`).

## Threat model
1. **Personal machine** (default, no `SCIEDU_AUTH`): the server listens on 127.0.0.1. Threats: hostile websites in
   the same browser (CSRF, DNS rebinding), hostile uploaded documents (prompt injection into the model or agy),
   and malicious content in topic JSON written by agents.
2. **Shared server** (`SCIEDU_AUTH=1`): any signed-in student is a potential attacker against other students and the
   server: authorization (IDOR), data leaks, code execution, cost abuse (Gemini quota), and denial of service.

## Scope (prioritize in this order)
1. `server.py` authorization: for **every** route, can user B read or change user A's data in accounts mode?
   Routes include topics (+ /simulation /quiz /practice /flashcards /timeline /opened), courses, classes,
   /api/engage/*, /api/review/*, /api/activity/*, /api/advisor/*, /api/draw/check, /api/ui/*, /api/agy/* (prompt,
   events, messages, inbox), /api/jobs, /api/tutor/*, uploads, IDE endpoints (/api/generate-*, /api/tutor-*).
   List each route as OK / ISSUE with a one-line reason.
2. Cost abuse: which routes call Gemini, and are they rate-limited (`rate_limit(...)`) and counted by
   `SCIEDU_DAILY_MODEL_CALLS`? Can one user exhaust the shared quota?
3. Injection: prompt injection from uploads, transcripts and drawings (what can a hostile PDF make the assistant
   or agy do? see `agy_agent_tools` and `_run_agy_process`); path traversal (`topic_path`, catalog cache, uploads);
   SSRF (any server-side fetch of user-given URLs?); JSON/regex DoS (catastrophic regexes in `advisor.py`,
   `simspec.py`, `Md.jsx` `normalizeMath`).
4. Frontend: any route from user/model text to HTML (`dangerouslySetInnerHTML` in `EduStudioIDE.jsx`, Mermaid,
   KaTeX options, Markdown link handling, the SVG drawing export), and anything stored in localStorage that is
   sensitive.
5. `mcp_server.py`: what can a connected model do; is anything destructive exposed; token handling.
6. `engage.py`: XP/score tampering beyond the daily caps; `X-Local-Day` abuse.
7. Your own pending files (`chemspec.py`, `src/simulations/ChemSim.jsx`, IDE changes): review them by the same standard.

## Already fixed by Claude (verify, don't redo)
- Accounts mode: course lessons are writable only by their owner and library lessons only by admins
  (`SCIEDU_ADMINS`); `require_topic_write` guards `POST /api/topics` and the add-quiz/practice/flashcards/
  timeline/simulation routes.
- UI events are owned and delivered only to their owner (`emit_event(..., owner)`, `PRIVATE_EVENT_TYPES`);
  job progress goes to whoever started the job.
- `GET /api/agy/messages` returns nothing in accounts mode (shared history file).
- Catalog import is admin-only in accounts mode.
- `/api/execute-code` and the assistant's `execute_python_code` are refused in accounts mode; rate-limited locally.
- Uploads: at most 12 files, 25 MB each, enforced before reading more into memory.
- Client-reported XP capped at 60 events per source per day.
- `content/agy_messages.json` and `content/quiz_results.json` untracked from git.
- Verified safe: non-JSON cross-site POSTs are rejected (no CSRF on JSON routes); the agy runner passes the
  prompt as one argv element (no shell); KaTeX uses its safe defaults.

## Report format (`SECURITY_FINDINGS_AGY.md`)
For each finding: **ID, severity (Critical/High/Medium/Low), mode affected (personal / shared / both), file:line,
how to reproduce (exact request or steps), impact, suggested fix.** Then the route table from scope item 1.
End with "Checked and fine" listing what you verified without findings.
