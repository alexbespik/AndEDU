# Known bugs

Open problems found but not fixed yet. Remove an entry when its fix lands.

## Desktop app: Gemini key setup

Found 2026-11-11 while reading the key flow (`src/components/DesktopKeySetup.jsx`, `desktop/preload.cjs`,
`desktop/main.cjs`, `desktop_main.py`).

1. **No way to change or remove a saved key.** `window.sciedu.clearKey` is exposed by `desktop/preload.cjs`
   but nothing in the UI calls it, and the setup card (`src/App.jsx:98`) only shows when no key is stored.
   Replacing a key means deleting `<userData>/secrets/gemini.key.enc` by hand
   (macOS: `~/Library/Application Support/SciEdu Studio/`, Linux: `~/.config/SciEdu Studio/`).
2. **A wrong but well-formed key leaves the user stuck.** `sciedu:saveKey` (`desktop/main.cjs:233`) checks only
   the shape (`/^[A-Za-z0-9_-]{30,100}$/`). A mistyped or revoked key is saved, `/api/status` then reports
   `gemini_configured: true`, the card never returns, and generation fails with no path to fix it in the app.
3. **Linux build says "macOS Keychain".** The card's footer in `DesktopKeySetup.jsx` is hard-coded to macOS;
   on Linux the key is in GNOME Keyring / KWallet.
4. **"Later" can't be undone in the session.** Dismissing the card hides it until the next launch with no
   other way to open it (minor).

Suggested fix: a "Gemini key" entry in Settings or the account menu with Replace and Remove (wired to the
existing `saveKey` / `clearKey`), a test call to Gemini before saving (or an "invalid key" state from the
backend that brings the card back), and OS-aware footer text.

## Advisor: prerequisites are per course, not per section

Found 2026-11-11. Different sections of the same course can have different prerequisites (e.g. a section
restricted to majors, an honors section, or a topics course whose sections cover different subjects), but
prerequisites are stored only once per course: `catalog_courses.prereqs` / `prereq_codes` / `prereq_tree`
(`advisor.py:30-34`). `catalog_sections` (`advisor.py:41`) has no prerequisite or restriction column, and
`_compact_section` (`advisor_cart.py:215`) doesn't return one. So readiness (`advisor.readiness`) and the cart's
`prereq_missing` flag (`advisor_cart.py:250`) judge every section by the course-level rule: a student can be told
they're ready for a section they can't register for, or blocked from one they could take.

Suggested fix: import each section's own prerequisites and restrictions into `catalog_sections` (falling back to
the course's when a section has none), show them per section in the cart, and check `prereq_missing` against
the chosen section (`section_crn`) when one is picked.
