# Before deployment: privacy, data and compliance

**Status: NOT ready for other students' data.** Today &.edu is fine on one person's own machine. Before anyone
else uses it (a class pilot, a hosted server, a W&M deployment), everything in "Must fix" has to be done.
Logged 2026-11-03.

## Must fix before deployment

### 1. Gemini API: where student data goes
- **What is sent to Google:** uploaded notes and slides, photos and PDFs (read by Gemini for OCR), course goals,
  generated lessons, tutor chats with their history, quiz context, and, through the Advisor, **transcript
  screenshots and PDFs**, and **drawings** from drawing assignments (checked by the vision model).
- **Free-tier risk:** on the free tier, Google may use prompts and responses to improve its products, and people
  may review them. The app runs on a free-tier key now. Student data must not go through it.
- **Required:** move to a paid Gemini API project or Vertex AI with no-training terms and a data processing
  agreement, before any data from other people is sent. Record which terms apply in this file.
- **Region and retention:** check where data is processed and how long Google keeps it; document it for users.
- **Age:** Gemini API terms require users to be 18 or older. The sign-up checkbox exists; keep it, and don't
  deploy to under-18 students without a different provider or agreement.

### 2. Transcripts and grades (FERPA)
- Transcripts, grades and course records are education records. A W&M deployment needs approval from the
  registrar or IT/privacy office before it collects them.
- The Advisor keeps only course codes, titles and grades, but **the whole screenshot or PDF is sent to Gemini for
  OCR**, including name, student ID and GPA. Before deployment: read typed text locally where possible, tell
  users before upload, offer "type my courses" as the default, and redact names and IDs.
- Never log transcript text (see 5).

### 3. Consent, notice and control
- Done 2026-11-07: in-app privacy notice (`src/components/PrivacyCenter.jsx`, account menu → "Privacy and your
  data…", and on the sign-in page): what is stored, what goes to Google Gemini and ElevenLabs (if on), what deletion
  does not reach, contact "the site administrator". Version `PRIVACY_VERSION` in `server.py`; bumping it asks
  accounts to accept again at sign-in. Fill in a real contact before a hosted deployment.
- Done 2026-11-07: consent. Accounts must accept the notice at sign-up (`privacy: true`, else 422). Uploads that
  go to Gemini (images, scanned PDFs, files used to plan a course) ask once per profile; in accounts mode the
  server refuses them with 428 until `POST /api/users/{id}/consent {kind:"upload"}`. Stored in `users`
  (`privacy_version`, `privacy_accepted_at`, `upload_consent_at`).
- Done 2026-11-07: "Export my data" (`GET /api/users/{id}/export`, JSON) and "Delete my account and data"
  (`POST /api/auth/delete-account` with name + password in accounts mode; `POST /api/users/{id}/delete` with the
  name in local mode). `db.USER_DATA_TABLES` lists every per-user table and a test fails if a new one is missed.
  Not reached by delete: backups, `server.log`, shared library lessons, local mode's shared assistant history, and
  lesson snapshots of courses deleted earlier (they keep no owner id; decide whether to record one).
  In local mode anyone at the computer can export or delete any profile (no accounts).
- Still open: Retention. Decide how long uploads, materials text and chat logs are kept, then enforce it.
- Done 2026-11-08: problem sprints (`mode: "problem_sprint"`) are deleted by default once every problem is done.
  Finishing the last part only hides the sprint (status `cleared`: out of My courses, its lessons out of the library
  and the review queue); it can be kept or restored until `SCIEDU_SPRINT_RETAIN_DAYS` (default 7) have passed, then
  a purge at startup and once a day deletes its course row, classes, lesson snapshots, topic files and notes. Courses
  created with "Keep in My courses" (`keep: true`) and every other course mode are never purged. Until the purge a
  cleared sprint is still in "Export my data" and removed by account deletion.
- Still open (not chosen 2026-11-07): read transcripts locally and redact name/ID/GPA before any Gemini call.

### 4. Secrets
- `.env` (Gemini and ElevenLabs keys) was committed in the past (commit 9d30620). **Rotate both keys**, and remove
  it from git history before the repository is pushed anywhere.
- Hosted: keys only in the server environment or a secret manager, never in the frontend or the repo.

### 5. Data files in the repository and in logs
- Done 2026-11-03: `content/agy_messages.json` (assistant chat) and `content/quiz_results.json` (answers) are
  untracked and ignored. (They remain in earlier git history.)
- `server.log` can contain prompts and errors with user content: rotate it, keep it short, and keep it out of backups.
- SQLite (`content/edu_studio.db`) is unencrypted: on a server, use an encrypted disk, restricted file
  permissions and encrypted backups.

### 6. Tools that act with the owner's permissions
- **agy CLI** runs on a personal Antigravity subscription and edits files. It must stay off on any shared server;
  the server already refuses it when `SCIEDU_AUTH=1`.
- **MCP server** (`mcp_server.py`) is local-only and trusts its caller. Never expose it over a network; on an
  accounts server, it needs a per-user token (`ANDEDU_TOKEN`) and only that user's data.
- Done: `/api/execute-code` is refused when `SCIEDU_AUTH=1`. The assistant never runs code itself: it proposes it
  (`CODE_PROPOSAL` event) and it runs only if the student clicks Run.
- Security review: accounts-mode authorization, events, chats, catalog and uploads were reviewed and fixed (tests: `AccountsSecurity` in `tests/test_lab.py`).
- **ElevenLabs** voice is off by default (`SCIEDU_ELEVENLABS=1`); if enabled, lesson text goes to ElevenLabs:
  disclose it (the privacy notice does). Languages also sends the words and phrases a student plays
  (`POST /api/language/tts`, at most 300 characters, text only, never the student's name or answers). Clips are cached in
  `content/tts_cache/` (shared by all users, keyed by a hash of model, voice, language and text; capped at
  `SCIEDU_TTS_CACHE_MB`, oldest removed first) and spending is capped by `SCIEDU_TTS_DAILY_CHARS` per day (an
  in-memory counter that a restart resets) and the `language_tts` hourly rate limit. Only the server's key is used,
  never one from the browser; with accounts on, playing audio requires a signed-in user.
  The lesson walkthrough ("Explain it to me", `explain.py`) sends its narration lines, written by Gemini from the
  lesson text (at most 250 characters each, never the student's name or answers), through the same endpoint with
  `purpose: "explain"`, which has its own daily cap `SCIEDU_EXPLAIN_TTS_CHARS` (default 15000) so it never uses up the
  Languages allowance. The steps themselves are cached per lesson in `content/explain_cache/` (no student data) and
  count against the `explain` hourly rate limit only when a new walkthrough is written.

### 7. Hosting basics
- `SCIEDU_AUTH=1`, HTTPS, the real hostname in the allowed hosts and CORS lists, rate limits kept on
  (`SCIEDU_RATE_SCALE`), and a daily model budget (`SCIEDU_DAILY_MODEL_CALLS`) that matches the paid plan.
- Admins: `SCIEDU_ADMINS` lists user ids (shown in the account menu), not names; the server logs a warning at
  startup for an entry that matches no user. Sign-up never takes over an existing name, even a password-less one.
- Sign-in and sign-up are limited to 10 per minute per client IP. Behind a proxy (Caddy), set uvicorn's
  `FORWARDED_ALLOW_IPS` to the proxy's address so the limit sees the real client instead of the proxy.
- HTTPS: `docker compose --profile tls up -d` runs Caddy in front of the app with automatic certificates
  (copy `Caddyfile.example` to `Caddyfile`, set `SCIEDU_DOMAIN` and add it to `SCIEDU_ALLOWED_HOSTS`). The app
  port itself is bound to 127.0.0.1, so without the tls profile no other machine can reach it.
- W&M names and colors: confirm with W&M before presenting this as a W&M service.

## Course catalog
- W&M's live catalog (catalog.wm.edu), the Open Course List (courselist.wm.edu) and the SWEM archive
  (dspace.swem.wm.edu) refuse automated downloads. The app does not try to get around that protection.
- **What works:** the Internet Archive (web.archive.org) keeps public snapshots of the catalog's course pages.
  `scripts/import_wm_catalog_wayback.py` imports them politely (rate-limited, cached in `content/catalog_cache/`).
  Best coverage: the **2023-2024 undergraduate catalog** (catoid 28, ~836 course pages archived). The 2025-26
  catalog (catoid 34) has only a few archived pages so far.
- The Advisor labels the data with its year and shows a "may be out of date" notice while the catalog is older
  than the current academic year. Students must confirm courses in the live catalog before registering.
- **Class sections are not included.** Term schedules (CRNs, meeting times, instructors, seats) are not shipped
  and the project has no tool that downloads them. Whoever runs an instance must obtain that data themselves, by
  legitimate means (for example an official export from the registrar), and load it with
  `advisor.upsert_sections(rows)`: each row needs `crn`, `term` and `code`, and may add `term_name`, `section`,
  `title`, `instructor`, `meets`, `meeting_times` (list), `schedule_type`, `status`, `seats`, `credits` and `details`
  (dict). Without it, the Advisor's section lists, time conflicts and seat-risk estimates stay empty.
- **Before deployment:** ask W&M (the Registrar or IT) for an official feed or export of the current catalog and
  course list. Modern Campus/Acalog catalogs have an API, with a key the institution issues, which would give
  current data legitimately.
