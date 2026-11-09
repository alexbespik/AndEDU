# Architecture Specification: Semester Planner, Universal Web Search & Reasoning, and Written Notes Awareness

**Status**: Approved Architectural Specification  
**Author**: architect  
**Target Implementation**: coder  
**Related Files**: `advisor.py`, `advisor_chat.py`, `server.py`, `db.py`, `wm_advising.py`, `src/components/AdvisorPage.jsx`, `src/components/AdvisorChat.jsx`, `src/components/MathLab.jsx`, `src/components/AgyBridgeDrawer.jsx`, `src/components/LessonTutor.jsx`, `src/lib/api.js`

---

## 1. Executive Summary & Problem Diagnosis

### 1.1 The Advisor Defect ("Horrible Advisor Output")
When a student asked: *"could you find me some stoic courses"*, the AI Advisor responded:
```
To help you find courses related to Stoicism, I have a few quick clarifying questions about your goals:
What is your academic major or intended field of study? ...
What degree requirements are you hoping to fulfill next semester? ...
While we look for specific philosophy offerings on Stoicism, your completed coursework in MATH 111 and CSCI 141 also makes you well-positioned to continue your foundational requirements or move into gateway courses like CSCI 241...
COLL 150, MATH 111, CSCI 141, CSCI 241, CSCI 243
```
This failure occurred because of three distinct architectural misalignments:
1. **Keyword Extraction & Semantic Blindspot**: In [advisor_chat.py](file://advisor_chat.py#L116-L120), `_keywords` extracted raw words of length $\ge 4$ (`['could', 'find', 'some', 'stoic']`). The catalog search queried these words literally against `catalog_courses`. Courses teaching Stoicism at William & Mary are cataloged under Philosophy (`PHIL 231`: Greek Philosophy, `PHIL 303`: Ethics, `PHIL 205`: Meaning in Life) and Classical Studies (`CLCV 208`: Roman Culture, `CLCV 316`), where descriptions mention Epictetus, Seneca, Marcus Aurelius, or Hellenistic ethics, not necessarily the standalone token "stoic".
2. **Recommendation Bias toward Completed Departments**: In [advisor.py](file://advisor.py#L775-L778), `recommend()` awarded $+3$ points for any course in departments the student already took (`CSCI`, `MATH`), plus $+2$ per satisfied prerequisite. Consequently, `CSCI 241` and `CSCI 243` scored 5.0–7.0, while un-prerequited Philosophy courses scored 0. When injected into prompt context under *"COURSES WHOSE LISTED PREREQUISITES THE STUDENT MEETS"*, the model treated them as primary recommendations.
3. **Bureaucratic Prompt Inversion**: In [advisor_chat.py](file://advisor_chat.py#L17-L23), `SYSTEM_PROMPT` instructed: *"When the student's request is broad or ambiguous... ask thoughtful, targeted clarifying questions... before making specific course recommendations"* and pushed gateway pathways (`CSCI 141 -> 241`). The model treated a specific intellectual inquiry as "ambiguous", interrogating the student and regurgitating their existing STEM pathway.

### 1.2 Missing Universal Internet Grounding & Reasoning
Several AI entry points (`advisor_ask`, `agy_prompt`, `lesson_tutor`) previously invoked Gemini with plain text configurations or incomplete toolsets without live Google Search grounding or reasoning thinking budgets.

### 1.3 Missing Semester Planning Engine & Dynamic Course Launch
The platform lacked a structured semester planning pipeline where students can generate a 14–16 credit schedule balancing degree gaps, major sequences, and elective interests, check schedule conflicts in real time, swap courses, and convert planned courses into active EduStudio study workspaces ("does more as you go").

### 1.4 Isolated Student Notes
The student notes written in `MathLab.jsx` were saved strictly to browser `localStorage` (`andedu_math_notes_${userId}`), isolated from the backend database and invisible to the AI assistants.

---

## 2. End-to-End System Topology

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                           STUDENT WORKSPACES                                          │
│                                                                                                       │
│   ┌────────────────────────┐   ┌───────────────────────────┐   ┌───────────────────────────────────┐  │
│   │ Advisor & Semester Plan│   │ MathLab Notebook          │   │ AGY Companion & Lesson Tutor      │  │
│   │ (AdvisorPage / Chat)   │   │ (MathLab.jsx / Notebook)  │   │ (AgyBridgeDrawer / LessonTutor)   │  │
│   │ - Credit Meter (14-16) │   │ - Live Markdown + LaTeX   │   │ - Socratic dialogue               │  │
│   │ - Conflict Inspector   │   │ - Auto-sync notes (800ms) │   │ - Grounded explanations           │  │
│   │ - "Launch in Studio"   │   │                           │   │                                   │  │
│   └───────────┬────────────┘   └─────────────┬─────────────┘   └─────────────────┬─────────────────┘  │
└───────────────┼──────────────────────────────┼───────────────────────────────────┼────────────────────┘
                │                              │                                   │
                │ HTTP REST                    │ PUT /api/users/{id}/notes         │ HTTP REST
                ▼                              ▼                                   ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       FASTAPI BACKEND (server.py)                                     │
│                                                                                                       │
│  ┌─────────────────────────────────┐ ┌──────────────────────────────┐ ┌────────────────────────────┐  │
│  │ Advisor & Semester Planning     │ │ Notes Management             │ │ Universal Gemini Wrapper   │  │
│  │ - POST /api/advisor/.../plan    │ │ - GET /api/users/.../notes   │ │ - call_gemini / acall_...  │  │
│  │ - POST /swap                    │ │ - PUT /api/users/.../notes   │ │ - Google Search Grounding  │  │
│  │ - POST /launch-course           │ └──────────────┬───────────────┘ │ - Dynamic Thinking Budget  │  │
│  │ - check_schedule_conflicts()    │                │                 │ - MIME/tool conflict guard │  │
│  └────────────────┬────────────────┘                │                 └──────────────┬─────────────┘  │
└───────────────────┼─────────────────────────────────┼────────────────────────────────┼────────────────┘
                    │                                 │                                │
                    ▼                                 ▼                                ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                             STORAGE & DATA                                            │
│                                                                                                       │
│  ┌─────────────────────────────────┐ ┌──────────────────────────────┐ ┌────────────────────────────┐  │
│  │ semester_plans table (advisor)  │ │ student_notes table (db.py)  │ │ Google GenAI Foundation    │  │
│  │ - user_id, term, courses_json   │ │ - user_id (PK), notes_text   │ │ - gemini-3.8-flash         │  │
│  │ - target_credits, status        │ │ - updated_at                 │ │ - GoogleSearch tool        │  │
│  └─────────────────────────────────┘ └──────────────────────────────┘ └────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Contracts & Implementation Details

### 3.1 Component 1: Advisor Semantic Expansion & Direct Answer Routing

#### A. Semantic Topic Expansion Ontology (`advisor_chat.py`)
Introduce `TOPIC_EXPANSIONS` in [advisor_chat.py](file://advisor_chat.py). When keywords in student queries match known intellectual topics, the search engine expands query boundaries to related departments and conceptual terms:

```python
TOPIC_EXPANSIONS = {
    "stoic": {
        "departments": ["PHIL", "CLCV", "RELG", "HIST"],
        "keywords": ["stoic", "stoicism", "epictetus", "seneca", "marcus aurelius", "hellenistic", "ancient", "virtue", "ethics", "moral", "meaning"],
        "target_courses": ["PHIL 231", "PHIL 303", "PHIL 205", "PHIL 252", "CLCV 208", "CLCV 316"],
        "label": "Stoic Philosophy & Hellenistic Thought",
    },
    "stoicism": {
        "departments": ["PHIL", "CLCV", "RELG", "HIST"],
        "keywords": ["stoic", "stoicism", "epictetus", "seneca", "marcus aurelius", "hellenistic", "ancient", "virtue", "ethics", "moral", "meaning"],
        "target_courses": ["PHIL 231", "PHIL 303", "PHIL 205", "PHIL 252", "CLCV 208", "CLCV 316"],
        "label": "Stoic Philosophy & Hellenistic Thought",
    },
    "ai": {
        "departments": ["CSCI", "DATA", "MATH", "LING", "PHIL"],
        "keywords": ["artificial intelligence", "machine learning", "neural", "deep learning", "nlp", "robotics", "data science"],
        "target_courses": ["CSCI 435", "CSCI 444", "DATA 301", "DATA 310", "MATH 351"],
        "label": "Artificial Intelligence & Machine Learning",
    },
    "ethics": {
        "departments": ["PHIL", "PUBP", "INRL"],
        "keywords": ["ethics", "moral", "justice", "bioethics", "applied ethics"],
        "target_courses": ["PHIL 303", "PHIL 305", "PHIL 215"],
        "label": "Ethics & Moral Philosophy",
    },
}
```

#### B. De-biasing Course Recommendations (`advisor.py:recommend`)
In [advisor.py](file://advisor.py#L760-L781):
When the caller provides specific non-empty interest keywords:
- Detect if interest tokens contain academic topics.
- Increase the weight of matched topic words to $+10$ points per keyword.
- If explicit interests are provided, suppress or zero out the $+3$ department bonus for prior completed departments (`depts`), preventing unrelated STEM courses from overwhelming the query.
- Courses with 0 keyword matches should be excluded from the top recommendations when specific interests are requested.

#### C. System Prompt Direct-Answer Refactor (`advisor_chat.py:SYSTEM_PROMPT`)
Replace the evasive preamble in `SYSTEM_PROMPT` with mandatory direct-answer directives:
1. **Direct Answer First**: When a student asks for courses on a topic (e.g. Stoicism, Ethics, AI), immediately present 2–4 concrete courses that fit their request, citing codes, titles, credits, fulfilled COLL/major requirements, and whether sections are scheduled for the next term.
2. **No Evasive Survey Interrogations**: Never withhold course suggestions behind a multi-question questionnaire when a specific topic was asked. Give answers first; follow up with at most 1 brief, relevant clarifying question.
3. **No Unprompted Gateway Dumping**: Do not push standard major sequences (e.g., `CSCI 141 -> 241 -> 243`) unless the student explicitly asks about major progression or general semester balance.

---

### 3.2 Component 2: Universal Web Search Grounding & Reasoning Engine

#### A. Gemini SDK Grounding & MIME Constraints
Official Google GenAI SDK (`google-genai` 2.25.0) rules:
1. `thinking_config = types.ThinkingConfig(thinking_budget=-1)` enables dynamic reasoning.
2. `tools = [types.Tool(google_search=types.GoogleSearch())]` enables live web search grounding.
3. **CRITICAL API INCOMPATIBILITY**: The Gemini API throws HTTP 400 `INVALID_ARGUMENT` if `google_search` is configured when `response_mime_type == "application/json"` or when `tool_config` enforces `mode="ANY"` or `mode="REQUIRED"` on custom function calls.

#### B. Unified Dispatcher in `server.py` (`call_gemini` / `acall_gemini`)
Enhance `call_gemini` with automated, resilient capability negotiation:

```python
def call_gemini(contents, role: Optional[str] = None, track_cooldown: bool = True,
                enable_search: bool = True, enable_thinking: bool = True, **kwargs):
    # 1. Resolve or clone GenerateContentConfig
    config = kwargs.get("config")
    if config is None:
        config = types.GenerateContentConfig()
        kwargs["config"] = config

    # 2. Reasoning Thinking Budget Injection
    if enable_thinking and config.thinking_config is None:
        # Default dynamic thinking (-1) or configured budget
        budget = int(os.environ.get("SCIEDU_THINKING_BUDGET", "-1"))
        config.thinking_config = types.ThinkingConfig(thinking_budget=budget)

    # 3. Web Search Grounding Tool Injection (Safeguarded)
    is_json = getattr(config, "response_mime_type", "") == "application/json"
    tool_cfg = getattr(config, "tool_config", None)
    fn_mode = getattr(getattr(tool_cfg, "function_calling_config", None), "mode", None)
    is_forced_func = fn_mode in ("ANY", "REQUIRED")
    search_paused = time.time() < GROUNDING_PAUSED_UNTIL

    if enable_search and not is_json and not is_forced_func and not search_paused:
        existing_tools = list(config.tools or [])
        has_search = any(getattr(t, "google_search", None) is not None for t in existing_tools)
        if not has_search:
            config.tools = existing_tools + [types.Tool(google_search=types.GoogleSearch())]

    # 4. Resilient Fallback Loop
    for model_id in ready_models:
        spend_model_call()
        try:
            return client.models.generate_content(model=model_id, contents=contents, **kwargs)
        except ClientError as e:
            err_msg = str(e).lower()
            # If search grounding failed or quota exhausted:
            if "google_search" in err_msg or "grounding" in err_msg or "tool use with a response mime type" in err_msg:
                GROUNDING_PAUSED_UNTIL = time.time() + 3600
                config.tools = [t for t in (config.tools or []) if getattr(t, "google_search", None) is None] or None
                return client.models.generate_content(model=model_id, contents=contents, **kwargs)
            # If thinking config is unsupported on this specific model:
            if "thinking" in err_msg:
                config.thinking_config = None
                return client.models.generate_content(model=model_id, contents=contents, **kwargs)
            # Normal model fallback handling (429, 404, 503)
            ...
```

#### C. Applied AI Usage Points
With this enhancement, every AI endpoint automatically inherits internet search and reasoning:
1. `POST /api/advisor/{user_id}/chat` & `/ask`
2. `POST /api/advisor/{user_id}/semester-plan`
3. `POST /api/agy/prompt` (AGY Bridge Drawer)
4. `POST /api/tutor/lesson` (Lesson Tutor)
5. `POST /api/lesson/explain-selection`

---

### 3.3 Component 3: Semester Planning Mode ("does more as you go")

#### A. Database Schema (`advisor.py` / `db.py`)
```sql
CREATE TABLE IF NOT EXISTS semester_plans (
    id             TEXT PRIMARY KEY,
    user_id        TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    term           TEXT NOT NULL,              -- e.g. "202620"
    term_name      TEXT NOT NULL DEFAULT '',   -- e.g. "Spring 2026"
    title          TEXT NOT NULL DEFAULT '',
    target_credits REAL NOT NULL DEFAULT 15.0,
    courses_json   TEXT NOT NULL DEFAULT '[]', -- JSON string of CoursePlanItem
    notes          TEXT NOT NULL DEFAULT '',   -- Advising rationale & degree impact
    status         TEXT NOT NULL DEFAULT 'draft',
    created_at     REAL NOT NULL,
    updated_at     REAL NOT NULL,
    UNIQUE (user_id, term)
);
CREATE INDEX IF NOT EXISTS idx_plans_user ON semester_plans(user_id, term);
```

#### B. Schedule Conflict & Credit Engine
A pure validation module [wm_advising.py](file://wm_advising.py) evaluates planned courses:
1. **Credit Meter**: Sum of credits. Validates against:
   - Minimum full-time: 12.0 credits
   - Standard recommended: 14.0–16.0 credits
   - Registration caps: 16.0 cr (initial carts), 18.0 cr (final add/drop cap; $>18$ requires overload approval)
2. **Schedule Conflict Detector (`check_schedule_conflicts(courses)`)**:
   Parses `meeting_times` or `meets` (e.g. `MWF 10-10:50a`, `TR 11:00-12:20p`). Flags time collisions:
   ```json
   {
     "conflict": true,
     "course_a": "PHIL 231",
     "course_b": "CSCI 241",
     "day": "T",
     "time": "11:00am - 12:20pm"
   }
   ```

#### C. Dynamic Studio Course Launch ("does more as you go")
Endpoint `POST /api/advisor/{user_id}/launch-course`:
- **Inputs**: `{"code": "PHIL 231", "plan_id": "..."}`
- **Execution**:
  1. Retrieves course catalog row `advisor.get_course(code)` (title, description, syllabus).
  2. Synthesizes learning goal: `"Master {code}: {title}"` and materials text from description + syllabus.
  3. Calls `db.create_course(user_id, title=code, goal=..., materials_text=...)`.
  4. Triggers background syllabus & diagnostic worker `start_plan_job(course["id"], n_questions=8, class_count=4)`.
  5. Updates `studio_course_id` on the planned course item inside `semester_plans`.
- **Response**: `{"course_id": course["id"], "job_id": job["id"], "redirect_url": f"/courses?open={course['id']}"}`.
This directly transforms static degree planning into interactive courseware!

#### D. Endpoints Specification
- `POST /api/advisor/{user_id}/semester-plan`: Synthesizes and saves a 4–5 course semester schedule.
- `GET /api/advisor/{user_id}/semester-plan?term={term}`: Retrieves current plan, credit meter, and conflict warnings.
- `POST /api/advisor/{user_id}/semester-plan/swap`: Swaps a course, verifying prerequisites and updating schedule conflicts.
- `POST /api/advisor/{user_id}/launch-course`: Instantiates an active EduStudio course.

---

### 3.4 Component 4: Unified Written Notes Awareness

#### A. Database Schema (`db.py`)
```sql
CREATE TABLE IF NOT EXISTS student_notes (
    user_id     TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    notes_text  TEXT NOT NULL DEFAULT '',
    updated_at  REAL NOT NULL
);
```

#### B. Sync Endpoints (`server.py`)
- `GET /api/users/{user_id}/notes`:
  Returns `{"notes": notes_text, "updated_at": updated_at}`.
- `PUT /api/users/{user_id}/notes`:
  Body `{"notes": str}`. Upserts note text with current timestamp. Returns `{"saved": true, "updated_at": updated_at}`.

#### C. Cross-System AI Context Injection
Whenever any AI endpoint prepares prompt context for a user, it injects their written notes:
1. **Advisor Context (`advisor_chat.py:build_context`)**:
   ```python
   notes = db.get_student_notes(user_id)
   if notes and notes.strip():
       out.append(f"\nSTUDENT'S WRITTEN NOTES & STUDY SCRATCHPAD:\n<<<STUDENT_NOTES\n{notes[:3000].strip()}\nSTUDENT_NOTES>>>")
   ```
2. **AGY Bridge Drawer (`server.py:agy_prompt`)**:
   Appends student notes to `course_context` so that AGY always possesses awareness of the student's personal notes and questions.
3. **Lesson Tutor (`server.py:lesson_tutor`)**:
   Injects student notes into the Socratic briefing context.

#### D. Client Synchronization (`src/components/MathLab.jsx`)
In `NotebookTab`:
- Fetch initial notes from `api(/api/users/${userId}/notes)` on mount, falling back to local storage if offline.
- On user input, debounced (800ms) save to `PUT /api/users/${userId}/notes`.
- Mirror state into `AdvisorChat.jsx` / `AdvisorPage.jsx` via an accessible Notes panel.

---

## 4. Verification & Testing Matrix

| Component | Target Verification | Command / Check |
|---|---|---|
| **Topic Expansion** | `PHIL 231`, `PHIL 303`, `CLCV 208` recommended for "stoic courses" | `PYTHONPATH=tests:.venv/lib/python3.14/site-packages .venv/bin/python -m unittest tests/test_advisor_chat.py` |
| **Direct Answer Prompt** | Advisor answers directly without survey questionnaire | Test with mock Gemini response asserting direct recommendation |
| **Search & Reasoning** | `call_gemini` includes `GoogleSearch` and `ThinkingConfig` | Unit test checking `call_gemini` config decoration and MIME compatibility fallback |
| **Semester Planner** | Plan generates 14–16 credits, detects conflicts, persists in SQLite | Unit tests for `/api/advisor/{user_id}/semester-plan` and conflict detection |
| **Studio Course Launch** | Planned course launches into active EduStudio course with diagnostic | Test `/api/advisor/{user_id}/launch-course` returns valid `course_id` and `job_id` |
| **Written Notes** | Notes sync via `GET/PUT /api/users/{user_id}/notes` and appear in AI prompts | Test notes persistence and context injection in `advisor_chat.build_context` |

---

## 5. Security & Safety Review
- **Zero Secrets Exposure**: Never log raw student transcripts, auth bearer tokens, or Gemini API keys.
- **Access Control**: All `/api/advisor/{user_id}/*` and `/api/users/{user_id}/notes` enforce `require_user(user_id)` and verify session ownership in accounts mode (`SCIEDU_AUTH=1`).
- **Input Sanitization**: Markdown output from Gemini is sanitized through existing React `Md.jsx` components without raw HTML injection.
- **Budget Protection**: Grounding quota errors gracefully pause Google Search for 1 hour (`GROUNDING_PAUSED_UNTIL`) while keeping baseline generation alive.
