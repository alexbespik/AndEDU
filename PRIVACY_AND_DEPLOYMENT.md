# Before deployment: privacy, data and compliance

**Status: NOT ready for other students' data.** Today &.edu is fine on one person's own machine. Before anyone
else uses it (a class pilot, a hosted server, a W&M deployment), everything in "Must fix" has to be done.
Logged 2026-11-03.

## Must fix before deployment

### 1. Gemini API: where student data goes
- **What is sent to Google:** uploaded notes and slides, photos and PDFs (read by Gemini for OCR), course goals,
  generated lessons, tutor chats with their history, quiz context, and, through the Advisor, **transcript
  screenshots and PDFs**.
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
- Add a privacy notice in the app: what is collected, which services receive it (Google Gemini; ElevenLabs if
  enabled), retention, and contacts.
- Ask for consent at sign-up and before the first upload.
- **Missing feature:** "Delete my account and data" (users, courses, classes, lessons, quiz attempts, XP, review
  items, completed courses, notes) and "Export my data". Only course deletion exists today.
- Retention: decide how long uploads, materials text and chat logs are kept, then enforce it.

### 4. Secrets
- `.env` (Gemini and ElevenLabs keys) was committed in the past (commit 9d30620). **Rotate both keys**, and remove
  it from git history before the repository is pushed anywhere.
- Hosted: keys only in the server environment or a secret manager, never in the frontend or the repo.

### 5. Data files in the repository and in logs
- `content/agy_messages.json` (assistant chat) and `content/quiz_results.json` (answers) are **tracked by git**:
  untrack them and add them to `.gitignore`.
- `server.log` can contain prompts and errors with user content: rotate it, keep it short, and keep it out of backups.
- SQLite (`content/edu_studio.db`) is unencrypted: on a server, use an encrypted disk, restricted file
  permissions and encrypted backups.

### 6. Tools that act with the owner's permissions
- **agy CLI** runs on a personal Antigravity subscription and edits files. It must stay off on any shared server;
  the server already refuses it when `SCIEDU_AUTH=1`.
- **MCP server** (`mcp_server.py`) is local-only and trusts its caller. Never expose it over a network; on an
  accounts server, it needs a per-user token (`ANDEDU_TOKEN`) and only that user's data.
- `/api/execute-code` (assistant's server-side Python) must be disabled when `SCIEDU_AUTH=1`; exercises already
  run in the browser.
- **ElevenLabs** voice is off by default (`SCIEDU_ELEVENLABS=1`); if enabled, lesson text goes to ElevenLabs:
  disclose it.

### 7. Hosting basics
- `SCIEDU_AUTH=1`, HTTPS, the real hostname in the allowed hosts and CORS lists, rate limits kept on
  (`SCIEDU_RATE_SCALE`), and a daily model budget (`SCIEDU_DAILY_MODEL_CALLS`) that matches the paid plan.
- W&M names and colors: confirm with W&M before presenting this as a W&M service.

## Course catalog
- W&M's current catalog (catalog.wm.edu), the Open Course List (courselist.wm.edu) and the SWEM archive
  (dspace.swem.wm.edu) all refuse automated downloads: challenge pages, 405 responses or connection resets, from
  both the app's server and a regular Mac. No catalog was downloaded or bundled.
- The Advisor works on whatever catalog a user imports. It records the catalog year and shows a "may be out of
  date" notice whenever the catalog is older than the current academic year, or its year is unknown.
- **Before deployment:** ask W&M (the Registrar or IT) for an official feed or export of the current catalog and
  course list. Until then, the Advisor is a planning aid, not advice to rely on for registration.
