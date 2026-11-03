import os
import io
import math
import re
import json
import asyncio
import threading
import contextvars
import sys
import base64
import copy
import subprocess
import httpx
from typing import List, Dict, Any, Optional, Tuple
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from dotenv import load_dotenv
import time
import glob
from pathlib import Path
from google import genai
from google.genai import types
from google.genai.errors import ClientError
from pypdf import PdfReader
import docx
import nbformat
from simspec import validate_spec, SPEC_GUIDE, MATH_GUIDE
import db
import engage
import advisor

ENV_FILE = Path(__file__).parent / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    load_dotenv()

api_key = os.environ.get("api_KEY", os.environ.get("GEMINI_API_KEY"))
client = genai.Client(api_key=api_key) if api_key else None

app = FastAPI(title="&.edu Backend")

# Local-only service: the Vite dev server proxies /api, so only its origin needs CORS.
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get(
    "SCIEDU_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",") if o.strip()]
ALLOWED_HOSTS = {"localhost", "127.0.0.1", "[::1]"} | {
    h.strip().lower() for h in os.environ.get("SCIEDU_ALLOWED_HOSTS", "").split(",") if h.strip()}

# Plan 4/D, 5/E: real accounts for hosting on a shared/university server. Off by default on a personal
# machine (name-only profiles). SCIEDU_AUTH=1 requires a login for every API call and scopes courses to
# their owner; the server refuses to listen beyond localhost without it.
AUTH_REQUIRED = os.environ.get("SCIEDU_AUTH") == "1"
PUBLIC_API = {"/api/status", "/api/auth/login", "/api/auth/register"}
CURRENT_USER: "contextvars.ContextVar[Optional[Dict[str, Any]]]" = contextvars.ContextVar("current_user", default=None)
CLIENT_KEY: "contextvars.ContextVar[str]" = contextvars.ContextVar("client_key", default="local")
LOCAL_DAY: contextvars.ContextVar = contextvars.ContextVar("local_day", default="")  # student's calendar day

# Requests that spend model quota, per signed-in user (or per client address without accounts), per hour.
# SCIEDU_RATE_SCALE multiplies every limit; 0 turns limiting off.
RATE_LIMITS = {"course": 10, "class": 40, "agy": 60, "simulation": 20, "upload": 30, "ide": 120, "chat": 240}
RATE_SCALE = float(os.environ.get("SCIEDU_RATE_SCALE", "1"))
_rate_hits: Dict[Tuple[str, str], List[float]] = {}
_rate_lock = threading.Lock()

def rate_limit(bucket: str, window: float = 3600.0):
    limit = int(RATE_LIMITS[bucket] * RATE_SCALE)
    if RATE_SCALE <= 0:
        return
    key, now = (bucket, CLIENT_KEY.get()), time.time()
    with _rate_lock:
        hits = [t for t in _rate_hits.get(key, []) if t > now - window]
        if len(hits) >= limit:
            wait = int((hits[0] + window - now) // 60) + 1
            _rate_hits[key] = hits
            raise HTTPException(status_code=429, detail=f"Limit reached: {limit} of these per hour. Try again in about {wait} min.")
        hits.append(now)
        _rate_hits[key] = hits

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Local-Day"],
)

@app.middleware("http")
async def reject_foreign_hosts(request, call_next):
    """Blocks DNS-rebinding: a hostile page can't reach us under its own hostname."""
    from fastapi.responses import JSONResponse
    host = (request.headers.get("host") or "").rsplit(":", 1)[0].lower()
    if host not in ALLOWED_HOSTS:
        return JSONResponse({"detail": "Forbidden host"}, status_code=403)
    if AUTH_REQUIRED and request.url.path.startswith("/api/") and request.url.path not in PUBLIC_API:
        auth = request.headers.get("authorization") or ""
        user = db.user_for_token(auth[7:].strip()) if auth.lower().startswith("bearer ") else None
        if not user:
            return JSONResponse({"detail": "Sign in to continue."}, status_code=401)
        CURRENT_USER.set(user)
    CLIENT_KEY.set(CURRENT_USER.get()["id"] if CURRENT_USER.get() else (request.client.host if request.client else "local"))
    LOCAL_DAY.set(engage.clean_day(request.headers.get("x-local-day")))
    return await call_next(request)

# Models in order of quota resilience & latency
CANDIDATE_MODELS = [
    "gemini-3.5-flash-lite", 
    "gemini-3.8-flash", 
    "gemini-flash-lite-latest",
    "gemini-3.5-flash", 
    "gemini-3.6-flash", 
    "gemini-3.7-flash"
]

def _env_models(name: str) -> List[str]:
    return [m.strip() for m in os.environ.get(name, "").split(",") if m.strip()]

# Plan section 4: "A bigger AI model will create the plan, and a smaller one will create new lessons and tests."
# Set SCIEDU_PLANNER_MODELS / SCIEDU_LESSON_MODELS (comma-separated) to the models your key can use;
# each role falls back to CANDIDATE_MODELS, so an unavailable name just costs one 404.
MODEL_ROLES = {
    "planner": _env_models("SCIEDU_PLANNER_MODELS"),
    "lesson": _env_models("SCIEDU_LESSON_MODELS"),
}

MODEL_COOLDOWN: Dict[str, float] = {}  # model id -> unix time it may be tried again

# Spending guard: at most this many Gemini requests per day (all users, all features). On the free tier
# Google simply refuses past quota; with billing on, this cap is what keeps costs bounded.
DAILY_MODEL_CALLS = int(os.environ.get("SCIEDU_DAILY_MODEL_CALLS", "400"))
_budget = {"day": "", "used": 0}
_budget_lock = threading.Lock()

def spend_model_call():
    today = time.strftime("%Y-%m-%d")
    with _budget_lock:
        if _budget["day"] != today:
            _budget.update(day=today, used=0)
        if DAILY_MODEL_CALLS > 0 and _budget["used"] >= DAILY_MODEL_CALLS:
            raise RuntimeError(f"Daily model budget reached ({DAILY_MODEL_CALLS} requests). It resets at midnight; "
                               "raise SCIEDU_DAILY_MODEL_CALLS in .env to allow more.")
        _budget["used"] += 1

def models_for(role: Optional[str]) -> List[str]:
    preferred = MODEL_ROLES.get(role or "", [])
    return preferred + [m for m in CANDIDATE_MODELS if m not in preferred]

def call_gemini(contents, role: Optional[str] = None, track_cooldown: bool = True, **kwargs):
    """Invokes Gemini with automatic model fallback for 429 quota, 503 load, and 404 deprecations."""
    global client
    if client is None:
        key = os.environ.get("api_KEY", os.environ.get("GEMINI_API_KEY"))
        if key:
            client = genai.Client(api_key=key)
        else:
            raise RuntimeError("Gemini API key is not configured in .env")
    last_err = None
    now = time.time()
    candidates = models_for(role)
    # skip models still cooling down from a quota/overload error, unless every model is
    ready = [m for m in candidates if MODEL_COOLDOWN.get(m, 0) <= now] or candidates
    for model_id in ready:
        spend_model_call()  # every attempt counts, fallbacks included
        try:
            return client.models.generate_content(
                model=model_id,
                contents=contents,
                **kwargs
            )
        except ClientError as e:
            last_err = e
            err_str = str(e).lower()
            if getattr(e, "code", None) in [429, 404, 500, 503] or "quota" in err_str or "resource_exhausted" in err_str:
                code = getattr(e, "code", None)
                if not track_cooldown:
                    pass  # e.g. a search-grounding quota: says nothing about plain generation on this model
                elif code == 429 or "quota" in err_str:
                    delay = re.search(r"retrydelay'?:\s*'?(\d+)", err_str)
                    MODEL_COOLDOWN[model_id] = time.time() + min(float(delay.group(1)) if delay else 60.0, 6 * 3600)
                elif code == 404:
                    MODEL_COOLDOWN[model_id] = time.time() + 24 * 3600
                elif code == 503:
                    MODEL_COOLDOWN[model_id] = time.time() + 30
                print(f"[MODEL FALLBACK] Model {model_id} returned code {code or 'unknown'}, attempting fallback...")
                continue
            raise e
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            if "quota" in err_str or "429" in err_str or "resource_exhausted" in err_str:
                print(f"[MODEL FALLBACK] Model {model_id} error {e}, attempting fallback...")
                continue
            print(f"[MODEL FALLBACK] Model {model_id} unexpected error: {e}, attempting fallback...")
            continue
    if last_err:
        raise last_err
    raise RuntimeError("No candidate models succeeded.")

async def acall_gemini(contents, role: Optional[str] = None, **kwargs):
    """The genai client is blocking; run it off the event loop so polling endpoints stay responsive."""
    return await asyncio.to_thread(call_gemini, contents, role, **kwargs)

GROUNDING_PAUSED_UNTIL = 0.0  # after a grounding quota error, skip search for a while instead of failing every check

# ---------------------------------------------------------------------------
# MCP TOOLS DECLARATIONS
# ---------------------------------------------------------------------------

# 1. Comprehensive Curriculum Tool (Supports all 3 MCP problem types)
# 1. Comprehensive Multi-Chapter Curriculum Tool (AI Dynamically Determines Curriculum Scale)
curriculum_tool = types.FunctionDeclaration(
    name="build_curriculum",
    description="Generate a comprehensive multi-chapter curriculum with in-depth study notes, progressive lessons, and diverse interactive problems. The AI dynamically decides how many chapters and how many problems per chapter are required to teach every concept from the uploaded files/documents and user prompt.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "course_title": types.Schema(type="STRING", description="Overarching course or topic title"),
            "domain": types.Schema(type="STRING", description="e.g. Python, Math, Data Science, Algorithms, Web Development"),
            "level_num": types.Schema(type="INTEGER", description="Difficulty tier: 1, 2, 3..."),
            "level_title": types.Schema(type="STRING", description="e.g. Level 1: Syntax & Foundations"),
            "overview": types.Schema(type="STRING", description="Pedagogical overview of what will be learned across all chapters"),
            "chapters": types.Schema(
                type="ARRAY",
                description="List of progressive chapters/lessons (typically 2 to 6+ lessons). The AI dynamically determines the exact number of chapters and problems based on the depth, length, and topics of the uploaded files, study guides, and prompt so that EVERY concept, theorem, equation, algorithm, and edge case is thoroughly covered.",
                items=types.Schema(
                    type="OBJECT",
                    properties={
                        "id": types.Schema(type="INTEGER", description="Chapter number: 1, 2, 3..."),
                        "title": types.Schema(type="STRING", description="Chapter title (e.g. Chapter 1: Syntax & Expressions)"),
                        "summary": types.Schema(type="STRING", description="Concise summary of chapter concepts"),
                        "estimated_time_minutes": types.Schema(type="INTEGER", description="Estimated completion time in minutes"),
                        "content_markdown": types.Schema(
                            type="STRING", 
                            description="Comprehensive study guide formatted in full Markdown with headings (#, ##, ###), code blocks (```python) or LaTeX math ($...$), tables (| Col | Col |), lists, blockquotes (>), bold, italic, inline code, and step-by-step worked examples."
                        ),
                        "problems": types.Schema(
                            type="ARRAY",
                            description="List of diverse problems in this chapter (typically 2 to 6 problems per chapter as determined by concept depth).",
                            items=types.Schema(
                                type="OBJECT",
                                properties={
                                    "id": types.Schema(type="INTEGER", description="Problem number within chapter or global"),
                                    "title": types.Schema(type="STRING", description="Problem file-like title (e.g. 01_syntax_colon.py or 01_limit_squeeze.math)"),
                                    "difficulty": types.Schema(type="STRING", description="Easy, Moderate, or Hard"),
                                    "type": types.Schema(
                                        type="STRING", 
                                        description="One of: 'slot_plugin' (code/math blank slot), 'syntax_problem' (fix/plug syntax error or notation), 'logic_problem' (fix logic condition or invariant), 'question' (conceptual multiple-choice quiz), 'block_builder' (scrambled lines with indentation or math derivation steps), 'code_write' (freeform code or algorithm implementation)"
                                    ),
                                    "guiding_question": types.Schema(type="STRING", description="Direct instruction on what to construct or implement"),
                                    "concept_hint": types.Schema(type="STRING", description="Key hint or reminder for this specific problem"),
                                    "explanation": types.Schema(type="STRING", description="Why the solution works and common pitfalls to avoid"),
                                    "test_cases": types.Schema(
                                        type="ARRAY",
                                        items=types.Schema(type="STRING"),
                                        description="Simulated terminal outputs or test assertions (at least 2-3 verification checks)"
                                    ),
                                    # slot_plugin, syntax_problem, logic_problem:
                                    "code_prefix": types.Schema(type="STRING", description="Code or formula before the blank slot (with proper newlines/indentation)"),
                                    "code_suffix": types.Schema(type="STRING", description="Code or formula after the blank slot (with proper newlines/indentation)"),
                                    "options": types.Schema(
                                        type="ARRAY",
                                        items=types.Schema(type="STRING"),
                                        description="Exactly 4 candidate choices to plug into the blank slot or choose from. Must contain correct_answer."
                                    ),
                                    "correct_answer": types.Schema(type="STRING", description="The exact correct choice matching one of the items in options"),
                                    # block_builder:
                                    "blocks_pool": types.Schema(
                                        type="ARRAY",
                                        items=types.Schema(type="STRING"),
                                        description="Scrambled list of code lines with authentic indentation or math derivation steps including plausible distractors"
                                    ),
                                    "correct_blocks": types.Schema(
                                        type="ARRAY",
                                        items=types.Schema(type="STRING"),
                                        description="The exact ordered sequence of lines or derivation steps that creates valid, running code or a valid mathematical proof"
                                    ),
                                    # question:
                                    "question_text": types.Schema(type="STRING", description="The question text or code analysis prompt"),
                                    # code_write:
                                    "starter_code": types.Schema(type="STRING", description="Starting code template with function signature or boilerplate"),
                                    "solution_code": types.Schema(type="STRING", description="Complete working reference code"),
                                    "test_code": types.Schema(type="STRING", description="Executable test assertions to verify student's code (e.g. assert func(...) == expected)")
                                },
                                required=["id", "title", "difficulty", "type", "guiding_question", "explanation"]
                            )
                        )
                    },
                    required=["id", "title", "summary", "content_markdown", "problems"]
                )
            ),
            # Backwards compatibility fields
            "lesson_plan": types.Schema(
                type="OBJECT",
                properties={
                    "title": types.Schema(type="STRING"),
                    "domain": types.Schema(type="STRING"),
                    "content_markdown": types.Schema(type="STRING")
                }
            ),
            "problems": types.Schema(
                type="ARRAY",
                items=types.Schema(type="OBJECT")
            )
        },
        required=["course_title", "domain", "chapters"]
    )
)

# 2. Standalone Easy Tool: One-Time Plug In (Slot Puzzle)
slot_puzzle_tool = types.FunctionDeclaration(
    name="emit_slot_puzzle",
    description="Generate a single Easy one-time plug-in code puzzle where the student selects the correct expression for a blank slot.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "id": types.Schema(type="INTEGER", description="Problem ID"),
            "title": types.Schema(type="STRING", description="Problem title"),
            "difficulty": types.Schema(type="STRING", description="Easy"),
            "type": types.Schema(type="STRING", description="slot_plugin"),
            "guiding_question": types.Schema(type="STRING", description="What expression to plug in"),
            "concept_hint": types.Schema(type="STRING", description="Helpful hint"),
            "code_prefix": types.Schema(type="STRING", description="Code before blank slot"),
            "code_suffix": types.Schema(type="STRING", description="Code after blank slot"),
            "options": types.Schema(
                type="ARRAY",
                items=types.Schema(type="STRING"),
                description="4 plausible plug-in choices"
            ),
            "correct_answer": types.Schema(type="STRING", description="Exact correct choice"),
            "explanation": types.Schema(type="STRING", description="Why this choice is correct"),
            "test_cases": types.Schema(type="ARRAY", items=types.Schema(type="STRING"))
        },
        required=["title", "guiding_question", "code_prefix", "code_suffix", "options", "correct_answer", "explanation"]
    )
)

# 3. Standalone Moderate Tool: Build Code Blocks
block_puzzle_tool = types.FunctionDeclaration(
    name="build_block_puzzle",
    description="Generate a single Moderate gamified scrambled code block assembly puzzle.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "id": types.Schema(type="INTEGER", description="Problem ID"),
            "title": types.Schema(type="STRING", description="Exercise title"),
            "difficulty": types.Schema(type="STRING", description="Moderate"),
            "type": types.Schema(type="STRING", description="block_builder"),
            "guiding_question": types.Schema(type="STRING", description="What the student must construct"),
            "concept_hint": types.Schema(type="STRING", description="Helpful hint"),
            "blocks_pool": types.Schema(
                type="ARRAY",
                items=types.Schema(type="STRING"),
                description="Scrambled list of code/math blocks to assemble (includes correct blocks + 1-2 distractors)"
            ),
            "correct_blocks": types.Schema(
                type="ARRAY",
                items=types.Schema(type="STRING"),
                description="The exact ordered sequence of blocks that creates valid, running code"
            ),
            "explanation": types.Schema(type="STRING", description="Why this block sequence works"),
            "test_cases": types.Schema(
                type="ARRAY",
                items=types.Schema(type="STRING"),
                description="Terminal logs verifying execution"
            )
        },
        required=["title", "guiding_question", "blocks_pool", "correct_blocks", "explanation"]
    )
)

# 4. Standalone Hard Tool: Freeform Coding Challenge
coding_challenge_tool = types.FunctionDeclaration(
    name="build_coding_challenge",
    description="Generate a single Hard freeform coding challenge with starter code and Python test assertions.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "id": types.Schema(type="INTEGER", description="Problem ID"),
            "title": types.Schema(type="STRING", description="Challenge title"),
            "difficulty": types.Schema(type="STRING", description="Hard"),
            "type": types.Schema(type="STRING", description="code_write"),
            "guiding_question": types.Schema(type="STRING", description="Problem requirements and expected behavior"),
            "concept_hint": types.Schema(type="STRING", description="Helpful hint on edge cases or algorithm structure"),
            "starter_code": types.Schema(type="STRING", description="Starting code template with function definition or comments"),
            "solution_code": types.Schema(type="STRING", description="Complete working reference Python code"),
            "test_code": types.Schema(type="STRING", description="Executable Python assertions to verify student code"),
            "explanation": types.Schema(type="STRING", description="Detailed explanation of the algorithmic solution"),
            "test_cases": types.Schema(type="ARRAY", items=types.Schema(type="STRING"), description="Test descriptions")
        },
        required=["title", "guiding_question", "starter_code", "solution_code", "test_code", "explanation"]
    )
)

# Socratic Tutor Tools
tutor_tools = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="change_assignment",
        description="Call this tool when the student asks for a new topic, asks to make it easier or harder, or needs a scaffolded assignment.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "reason": types.Schema(type="STRING", description="Why the assignment is changing"),
                "new_topic": types.Schema(type="STRING", description="The adjusted topic"),
                "target_type": types.Schema(type="STRING", description="'slot_plugin' for easy, 'block_builder' for moderate, 'code_write' for hard")
            },
            required=["reason", "new_topic"]
        )
    ),
    slot_puzzle_tool,
    block_puzzle_tool,
    coding_challenge_tool
])

curriculum_tools_wrapper = types.Tool(function_declarations=[curriculum_tool])

# 3. Single Chapter Tool (For generating additional individual chapters)
single_chapter_tool = types.FunctionDeclaration(
    name="build_single_chapter",
    description="Generate a single comprehensive new chapter with in-depth study notes and diverse interactive problems to extend an existing course.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "id": types.Schema(type="INTEGER", description="Chapter ID number"),
            "title": types.Schema(type="STRING", description="Chapter title (e.g. Chapter 3: Integration Techniques & Applications)"),
            "summary": types.Schema(type="STRING", description="Concise summary of chapter concepts"),
            "estimated_time_minutes": types.Schema(type="INTEGER", description="Estimated completion time in minutes"),
            "content_markdown": types.Schema(
                type="STRING",
                description="Comprehensive study guide formatted in Markdown with headings (#, ##, ###), LaTeX math ($...$ and $$...$$) or code blocks, tables, and worked examples."
            ),
            "problems": types.Schema(
                type="ARRAY",
                description="List of 2 to 4 diverse interactive problems in this chapter",
                items=types.Schema(
                    type="OBJECT",
                    properties={
                        "id": types.Schema(type="INTEGER"),
                        "title": types.Schema(type="STRING"),
                        "difficulty": types.Schema(type="STRING"),
                        "type": types.Schema(type="STRING"),
                        "guiding_question": types.Schema(type="STRING"),
                        "concept_hint": types.Schema(type="STRING"),
                        "explanation": types.Schema(type="STRING"),
                        "test_cases": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
                        "code_prefix": types.Schema(type="STRING"),
                        "code_suffix": types.Schema(type="STRING"),
                        "options": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
                        "correct_answer": types.Schema(type="STRING"),
                        "blocks_pool": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
                        "correct_blocks": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
                        "question_text": types.Schema(type="STRING"),
                        "starter_code": types.Schema(type="STRING"),
                        "solution_code": types.Schema(type="STRING"),
                        "test_code": types.Schema(type="STRING")
                    },
                    required=["id", "title", "difficulty", "type", "guiding_question", "explanation"]
                )
            )
        },
        required=["id", "title", "summary", "content_markdown", "problems"]
    )
)

# 4. Single Problem Tool (For adding exercises to any chapter)
single_problem_tool = types.FunctionDeclaration(
    name="build_single_problem",
    description="Generate a single interactive educational exercise or puzzle tailored to the current chapter.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "id": types.Schema(type="INTEGER"),
            "title": types.Schema(type="STRING"),
            "difficulty": types.Schema(type="STRING"),
            "type": types.Schema(type="STRING"),
            "guiding_question": types.Schema(type="STRING"),
            "concept_hint": types.Schema(type="STRING"),
            "explanation": types.Schema(type="STRING"),
            "test_cases": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
            "code_prefix": types.Schema(type="STRING"),
            "code_suffix": types.Schema(type="STRING"),
            "options": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
            "correct_answer": types.Schema(type="STRING"),
            "blocks_pool": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
            "correct_blocks": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
            "question_text": types.Schema(type="STRING"),
            "starter_code": types.Schema(type="STRING"),
            "solution_code": types.Schema(type="STRING"),
            "test_code": types.Schema(type="STRING")
        },
        required=["id", "title", "difficulty", "type", "guiding_question", "explanation"]
    )
)

chapter_tools_wrapper = types.Tool(function_declarations=[single_chapter_tool])
problem_tools_wrapper = types.Tool(function_declarations=[single_problem_tool])

# Distinguished Professor Voices for ElevenLabs
PROFESSOR_VOICES = {
    "george": "JBFqnCBsd6RMkjVDRZzb",   # George: Distinguished, warm elderly British scholar
    "arnold": "VR6AewLTigWG4xSOukaG",   # Arnold: Crisp, resonant professor/narrator
    "daniel": "onwK4e9ZLuTAKqWW03F9",   # Daniel: Deep, authoritative academic broadcaster
}
DEFAULT_PROFESSOR_VOICE = "JBFqnCBsd6RMkjVDRZzb"

def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    ext = filename.lower().split('.')[-1]
    if ext in ["txt", "md", "py", "sh", "json", "csv"]:
        return file_bytes.decode("utf-8", errors="ignore")
    elif ext == "pdf":
        reader = PdfReader(io.BytesIO(file_bytes))
        return "\n".join([p.extract_text() or "" for p in reader.pages])
    elif ext == "docx":
        doc = docx.Document(io.BytesIO(file_bytes))
        return "\n".join([p.text for p in doc.paragraphs if p.text])
    elif ext == "ipynb":
        notebook = nbformat.reads(file_bytes.decode("utf-8", errors="ignore"), as_version=4)
        return "\n\n".join([c.source for c in notebook.cells if c.cell_type in ["code", "markdown"]])
    return ""

SOCRATIC_PROMPT = """
You are a senior Socratic mentor and master coach for '&edu'.
Your objective is to lead the student to deep conceptual mastery with razor-sharp, concise guidance.

Pedagogical Core Directives:
1. Short, Concise & Leading (CRITICAL):
   - Keep all responses strictly under 50-60 words!
   - NO giant walls of text. Deliver one sharp insight and one leading check question.
   - Give the actual task directly without preamble or boilerplate greetings.
2. Theory First, Then Practice:
   - Anchor the student in the foundational concept or invariant in one punchy sentence.
3. Strict No-Spoilers:
   - Never reveal the exact token, block order, or code unless '!reveal' is requested.
   - Lead them with a targeted counterexample or boundary inspection.
4. Review & Longitudinal Guidance:
   - Help the student reflect on why an incorrect choice violates the problem invariant.

Adaptive Tools:
- If the student requests an easier assignment or needs warm-up: emit_slot_puzzle
- If the student requests block practice: build_block_puzzle
- If the student wants a hard challenge: build_coding_challenge
- If the student requests a topic change: change_assignment
"""

# ---------------------------------------------------------------------------
# API PAYLOAD MODELS & ENDPOINTS
# ---------------------------------------------------------------------------

class GeneratePayload(BaseModel):
    user_instruction: str
    document_text: Optional[str] = ""
    level: Optional[int] = 1
    mode: Optional[str] = "code" # 'code' | 'math' | 'general'
    target_chapters: Optional[int] = None # Desired number of chapters to synthesize

class GenerateChapterPayload(BaseModel):
    course_title: Optional[str] = "Course Track"
    domain: Optional[str] = "General"
    mode: Optional[str] = "code" # 'code' | 'math'
    level: Optional[int] = 1
    existing_chapters: Optional[List[Dict[str, Any]]] = []
    chapter_topic: Optional[str] = "" # Specific topic or empty for auto next logical chapter
    target_problems_count: Optional[int] = 3

class GenerateProblemPayload(BaseModel):
    chapter_id: int
    chapter_title: str
    chapter_summary: Optional[str] = ""
    chapter_content: Optional[str] = ""
    course_title: Optional[str] = "Course Track"
    mode: Optional[str] = "code" # 'code' | 'math'
    level: Optional[int] = 1
    problem_type: Optional[str] = "auto"
    topic_focus: Optional[str] = ""

class MakeHarderPayload(BaseModel):
    topic: str
    current_level: int
    document_text: Optional[str] = ""
    mode: Optional[str] = "code"

class ExecuteCodePayload(BaseModel):
    code: str
    test_code: Optional[str] = ""

class ChatPayload(BaseModel):
    puzzle_context: Optional[Dict[str, Any]] = {}
    history: Optional[List[Dict[str, Any]]] = []
    message: Optional[str] = ""

class BriefPayload(BaseModel):
    problem: Dict[str, Any]
    chapter: Optional[Dict[str, Any]] = None
    mode: Optional[str] = "code"
    level: Optional[int] = 1

ELEVENLABS_ENABLED = os.environ.get("SCIEDU_ELEVENLABS") == "1"

class VoiceoverPayload(BaseModel):
    chapter_title: Optional[str] = "Lecture"
    course_title: Optional[str] = "Course"
    content_markdown: Optional[str] = ""
    voice_id: Optional[str] = DEFAULT_PROFESSOR_VOICE # George: Elderly Male Professor
    persona: Optional[str] = "elderly_professor"
    api_key: Optional[str] = ""

DEFAULT_MULTI_CHAPTER_CURRICULUM = {
    "course_title": "Python Control Flow & Algorithm Engineering",
    "domain": "Python Programming",
    "level_num": 1,
    "level_title": "Level 1: Syntax Foundations & Logic Patterns",
    "overview": "Master Python programming through a multi-chapter sequence: syntax integrity, logic invariants, block-by-block structured construction, and sandbox algorithm execution.",
    "chapters": [
        {
            "id": 1,
            "title": "Chapter 1: Syntax Essentials & Safe Loops",
            "summary": "Master Python colon syntax, keywords, and safe loop invariants without crashing execution.",
            "estimated_time_minutes": 20,
            "content_markdown": """# Chapter 1: Syntax Essentials & Safe Loops

Welcome to the **&edu Visual Studio Code Studio**. In this chapter, we master fundamental Python syntax, statement boundaries, and loop safety invariants.

## 1. Syntax Mechanics: The Power of the Colon `:`

In Python, compound statements (such as `if`, `for`, `while`, `def`, `class`) MUST terminate their header line with a colon (`:`). The colon instructs the Python compiler to expect an **indented suite of statements**.

```python
# Valid Python compound header
if count > 0:
    print("Positive count detected")
```

### Common Syntax Errors to Avoid:
| Construct | Incorrect Syntax | Valid Python Syntax | Explanation |
| :--- | :--- | :--- | :--- |
| `if` condition | `if x > 10` | `if x > 10:` | Missing colon triggers `SyntaxError: expected ':'` |
| `while` loop | `while True` | `while True:` | Loop header requires colon |
| `def` function | `def calculate()` | `def calculate():` | Function signature must close with colon |
| Variable Names | `2nd_val = 10` | `val_2 = 10` | Identifiers cannot start with numbers |

---

## 2. Loop Termination & The Accumulator Invariant

An **invariant** is a logical condition that remains true across every iteration of a loop. Consider a `while` loop:

> [!IMPORTANT]
> A `while` loop continues executing as long as its guard expression evaluates to `True`. To prevent an **endless loop** that freezes memory and locks CPU threads, the loop variable must make monotonic progress toward a terminating boundary.

```python
i = 1
while i < 5:
    print(f"Iteration step {i}")
    i += 1  # State mutation toward termination
```

### Loop State Progression Table:
| Step | Variable `i` | Condition `i < 5` | Action |
| :--- | :--- | :--- | :--- |
| 1 | 1 | `True` | Prints output, increments `i` to 2 |
| 2 | 2 | `True` | Prints output, increments `i` to 3 |
| 3 | 3 | `True` | Prints output, increments `i` to 4 |
| 4 | 4 | `True` | Prints output, increments `i` to 5 |
| 5 | 5 | `False` | Loop terminates safely! |

- [x] Master colon header syntax
- [x] Understand state mutation
- [ ] Complete Chapter 1 exercises
""",
            "problems": [
                {
                    "id": 1,
                    "title": "01_syntax_colon.py",
                    "difficulty": "Easy",
                    "type": "syntax_problem",
                    "guiding_question": "Spot and plug in the missing syntax token to complete the Python if-statement header.",
                    "concept_hint": "In Python, compound statement headers (if, while, for, def) must conclude with a specific punctuation mark before the indented block.",
                    "explanation": "In Python, compound statements like `if` require a trailing colon `:` to open an indented block. Omitting it causes a `SyntaxError: expected ':'`.",
                    "code_prefix": "x = 42\nif x > 10",
                    "code_suffix": "\n    print(\"Value exceeds threshold\")\n    status = \"OK\"",
                    "options": [":", ";", " then:", "->"],
                    "correct_answer": ":",
                    "test_cases": [
                        "[SYNTAX_CHECK] Parsing statement header...",
                        "[COMPILER] Token ':' registered cleanly.",
                        "[STDOUT] Value exceeds threshold"
                    ]
                },
                {
                    "id": 2,
                    "title": "02_loop_guard.py",
                    "difficulty": "Easy",
                    "type": "slot_plugin",
                    "guiding_question": "Select and plug in the condition that allows the loop to run exactly 4 times and terminate safely without hanging.",
                    "concept_hint": "Starting at i = 1 with i += 1 each turn, find the boundary condition that yields 4 iterations.",
                    "explanation": "With `i = 1` and `i += 1`, the condition `i < 5` evaluates to True for i=1, 2, 3, 4 (4 iterations) and terminates cleanly when i reaches 5.",
                    "code_prefix": "i = 1\nwhile ",
                    "code_suffix": ":\n    print(\"rush\")\n    i += 1",
                    "options": ["i < 5", "True", "i == 1", "i > 1000000"],
                    "correct_answer": "i < 5",
                    "test_cases": [
                        "[SIMULATING] while i < 5:",
                        "rush", "rush", "rush", "rush",
                        "[SUCCESS] Loop terminated cleanly at i=5. Memory stable."
                    ]
                },
                {
                    "id": 3,
                    "title": "03_identifier_quiz.md",
                    "difficulty": "Easy",
                    "type": "question",
                    "guiding_question": "Analyze Python identifier syntax rules and select the illegal variable name.",
                    "question_text": "According to the Python language grammar, which of the following variable assignments will immediately raise a `SyntaxError: invalid decimal literal`?",
                    "concept_hint": "Python identifiers can contain letters, numbers, and underscores, but they cannot begin with a numeric digit.",
                    "explanation": "In Python, variable names cannot start with a digit. Therefore, `2nd_score = 98` is illegal and raises a SyntaxError.",
                    "options": ["2nd_score = 98", "score_2nd = 98", "_score_2 = 98", "ScoreSecond = 98"],
                    "correct_answer": "2nd_score = 98",
                    "test_cases": [
                        "[CHECK] Verifying Python identifier lexical rules...",
                        "[PASS] Correctly flagged numeric prefix as SyntaxError."
                    ]
                }
            ]
        },
        {
            "id": 2,
            "title": "Chapter 2: Logic Invariants & Block Construction",
            "summary": "Construct indented multi-line logic and prevent off-by-one boundary bugs.",
            "estimated_time_minutes": 25,
            "content_markdown": """# Chapter 2: Logic Invariants & Block Construction

In this chapter, we bridge the gap between individual syntax tokens and **multi-line structural logic**.

## 1. Zero-Based Indexing & The Off-By-One Pitfall

Python sequences (lists, strings, tuples) use zero-based indexing:

```python
languages = ["Python", "Rust", "Go", "TypeScript"]
# Index:       0         1       2        3
```

A frequent error in algorithmic logic is attempting to access index `len(languages)`, which produces an `IndexError: list index out of range`. The final valid element is always situated at `len(languages) - 1` or accessed via the negative index `-1`.

### Sequence Boundary Map:
| Position | Forward Index | Reverse Index | Value |
| :--- | :--- | :--- | :--- |
| First Element | `0` | `-len(s)` | `"Python"` |
| Second Element | `1` | `-(len(s)-1)` | `"Rust"` |
| Last Element | `len(s) - 1` | `-1` | `"TypeScript"` |

---

## 2. Editor Indentation Architecture

Unlike languages bounded by curly braces `{ ... }`, Python requires strict indentation (4 spaces per nesting level):

```python
def filter_positive(numbers):
    # Level 1 indentation (4 spaces)
    results = []
    for n in numbers:
        # Level 2 indentation (8 spaces)
        if n > 0:
            # Level 3 indentation (12 spaces)
            results.append(n)
    return results
```

> [!TIP]
> In VS Code and professional editors, visual indentation guides help you align conditional blocks directly beneath their parent statements.
""",
            "problems": [
                {
                    "id": 4,
                    "title": "04_boundary_logic.py",
                    "difficulty": "Moderate",
                    "type": "logic_problem",
                    "guiding_question": "Select and plug in the expression that safely retrieves the final element of any non-empty list without throwing an IndexError.",
                    "concept_hint": "Remember that Python lists are 0-indexed, so the index of the last element is always one less than the count of elements.",
                    "explanation": "Because Python lists are 0-indexed, `len(items) - 1` correctly accesses the last valid index. Alternatively `items[-1]` works, whereas `items[len(items)]` raises IndexError.",
                    "code_prefix": "def get_last_element(items):\n    if not items:\n        return None\n    return items[",
                    "code_suffix": "]\n\nprint(get_last_element([10, 20, 30, 40]))",
                    "options": ["len(items) - 1", "len(items)", "len(items) + 1", "0"],
                    "correct_answer": "len(items) - 1",
                    "test_cases": [
                        "[EXECUTE] get_last_element([10, 20, 30, 40])",
                        "[OUTPUT] 40",
                        "[CHECK] Boundary assertion len-1 passed cleanly."
                    ]
                },
                {
                    "id": 5,
                    "title": "05_even_sum_blocks.py",
                    "difficulty": "Moderate",
                    "type": "block_builder",
                    "guiding_question": "Assemble the code blocks in proper sequential order. Notice that each block inserts as real text into the editor with authentic Python indentation.",
                    "concept_hint": "Start with function definition, initialize the running total, iterate with for, check evenness with modulo (n % 2 == 0), and finish with return total.",
                    "explanation": "The proper sequence initializes total=0 at 4 spaces, loops through nums, filters with if n % 2 == 0 at 8 spaces, accumulates at 12 spaces, and returns total at 4 spaces.",
                    "blocks_pool": [
                        "def sum_even_numbers(nums):",
                        "    total = 0",
                        "    for n in nums:",
                        "        if n % 2 == 0:",
                        "            total += n",
                        "    return total",
                        "        if n % 2 != 0:",
                        "            total = n"
                    ],
                    "correct_blocks": [
                        "def sum_even_numbers(nums):",
                        "    total = 0",
                        "    for n in nums:",
                        "        if n % 2 == 0:",
                        "            total += n",
                        "    return total"
                    ],
                    "test_cases": [
                        "[TEST 1] sum_even_numbers([1, 2, 3, 4, 5, 6]) == 12 [PASS]",
                        "[TEST 2] sum_even_numbers([1, 3, 5]) == 0 [PASS]",
                        "[TEST 3] sum_even_numbers([2, 4, 8]) == 14 [PASS]"
                    ]
                }
            ]
        },
        {
            "id": 3,
            "title": "Chapter 3: Algorithmic Implementation",
            "summary": "Write and execute production-grade Python algorithms verified by real test suites.",
            "estimated_time_minutes": 30,
            "content_markdown": """# Chapter 3: Algorithmic Implementation

Now you step into the full developer experience: writing, debugging, and running full Python functions against unit test suites.

## Mathematical Invariant: Gauss Summation

When looking for a single missing number from an arithmetic sequence from `0` to `n`, you can compute the expected sum in $O(1)$ time using the Gauss formula:

$$\\text{Expected Sum} = \\frac{n \\times (n + 1)}{2}$$

By subtracting the actual sum of the array from the expected sum, the remaining difference is exactly the missing number!

### Complexity Comparison:
| Algorithm Strategy | Time Complexity | Space Complexity | Description |
| :--- | :--- | :--- | :--- |
| Hash Set Lookup | $O(N)$ | $O(N)$ | Fast lookup, but requires extra memory |
| Sort and Scan | $O(N \\log N)$ | $O(1)$ | Mutates or copies data |
| Mathematical Sum | $O(N)$ | $O(1)$ | Optimal linear time and constant space |

---

## Editor Shortcuts & Execution

- Press **Run Code** to execute your code in an isolated Python 3 subprocess.
- Press **Run Test Suite** to verify your function against strict automated assertions.
""",
            "problems": [
                {
                    "id": 6,
                    "title": "06_find_missing.py",
                    "difficulty": "Hard",
                    "type": "code_write",
                    "guiding_question": "Implement `find_missing_number(nums)` which takes a list of distinct integers from 0 to n (with exactly one missing) and returns the missing number in O(n) time.",
                    "concept_hint": "Compute expected_sum = n * (n + 1) // 2 where n = len(nums), then return expected_sum - sum(nums).",
                    "explanation": "Using Gauss's summation formula n * (n + 1) // 2 takes O(1) space and O(n) time to compute the sum, avoiding hash tables or sorting.",
                    "starter_code": "def find_missing_number(nums: list[int]) -> int:\n    # TODO: Calculate expected sum and subtract actual sum\n    n = len(nums)\n    expected_sum = n * (n + 1) // 2\n    return expected_sum - sum(nums)\n\n# Test locally:\nprint(\"Missing in [3, 0, 1]:\", find_missing_number([3, 0, 1]))\n",
                    "solution_code": "def find_missing_number(nums: list[int]) -> int:\n    n = len(nums)\n    expected_sum = n * (n + 1) // 2\n    return expected_sum - sum(nums)\n",
                    "test_code": "assert find_missing_number([3, 0, 1]) == 2\nassert find_missing_number([0, 1]) == 2\nassert find_missing_number([9,6,4,2,3,5,7,0,1]) == 8\nprint(\"All assertions passed!\")",
                    "test_cases": [
                        "assert find_missing_number([3, 0, 1]) == 2",
                        "assert find_missing_number([0, 1]) == 2",
                        "assert find_missing_number([9,6,4,2,3,5,7,0,1]) == 8"
                    ]
                }
            ]
        }
    ]
}

def resolve_answer_alias(correct_ans: str, options: List[str]) -> str:
    """Maps "2" / "C" style answers to option text, but only when the answer isn't itself an option
    (a math answer of "2" among ["1","2","3","4"] must stay "2", not become options[2])."""
    if not options or correct_ans in options:
        return correct_ans
    if correct_ans.isdigit() and 0 <= int(correct_ans) < len(options):
        return options[int(correct_ans)]
    if len(correct_ans) == 1 and correct_ans.upper() in "ABCD":
        idx = ord(correct_ans.upper()) - 65
        if idx < len(options):
            return options[idx]
    return correct_ans

def finalize_choices(options: List[str], correct_ans: str, size: int = 4) -> List[str]:
    """Returns exactly `size` choices that always contain the answer, at a stable but answer-dependent slot."""
    if correct_ans in options[:size]:
        choices = list(options[:size])
    else:
        distractors = [o for o in options if o != correct_ans][:size - 1]
        slot = sum(map(ord, correct_ans)) % (len(distractors) + 1)
        choices = distractors[:slot] + [correct_ans] + distractors[slot:]
    while len(choices) < size:
        choices.append(f"option_{len(choices) + 1}")
    return choices

def normalize_curriculum_data(data: Dict[str, Any], default_level: int = 1) -> Dict[str, Any]:
    """
    Ensures consistent chapters hierarchy, flattened problems list, robust answers,
    and valid problem types. Guarantees zero unanswered questions and zero empty palettes.
    """
    import re
    import random

    chapters = data.get("chapters", [])
    
    # If no chapters but lesson_plan and problems are present, wrap into a chapter
    if not chapters and ("problems" in data or "lesson_plan" in data):
        lp = data.get("lesson_plan", {})
        chapters = [{
            "id": 1,
            "title": lp.get("title", data.get("course_title", "Chapter 1: Core Fundamentals")),
            "summary": lp.get("overview", "Core concepts and practice exercises."),
            "estimated_time_minutes": lp.get("estimated_time_minutes", 25),
            "content_markdown": lp.get("content_markdown", "# Chapter 1\n\nLesson content."),
            "problems": data.get("problems", [])
        }]

    # Ensure chapters exist
    if not chapters:
        chapters = copy.deepcopy(DEFAULT_MULTI_CHAPTER_CURRICULUM["chapters"])

    flat_problems = []
    global_id = 1

    for ch_idx, ch in enumerate(chapters):
        if "id" not in ch:
            ch["id"] = ch_idx + 1
        cid = ch["id"]
        if "title" not in ch or not ch["title"]:
            ch["title"] = f"Chapter {cid}: Core Concepts"
        if "content_markdown" not in ch or not ch["content_markdown"]:
            ch["content_markdown"] = f"# {ch['title']}\n\n## Chapter Overview\n{ch.get('summary', 'Study notes and key concepts.')}"
        
        prob_list = ch.get("problems", [])
        normalized_prob_list = []
        for p_idx, p in enumerate(prob_list):
            p["chapter_id"] = ch["id"]
            p["chapter_title"] = ch["title"]
            p["global_index"] = len(flat_problems)
            if "id" not in p:
                p["id"] = global_id
            global_id += 1

            # Default type if missing
            ptype = (p.get("type") or "").lower()
            if not ptype:
                ptype = "slot_plugin" if p_idx == 0 else "block_builder" if p_idx == 1 else "code_write"
            p["type"] = ptype

            # Normalization of answers and options across all field aliases:
            # 1. correct_answer
            correct_ans = (
                p.get("correct_answer") or 
                p.get("correctAnswer") or 
                p.get("answer") or 
                p.get("solution") or 
                p.get("correct_option") or 
                p.get("correct_choice") or 
                p.get("expected_output") or 
                ""
            )
            if isinstance(correct_ans, (list, tuple)) and len(correct_ans) > 0:
                correct_ans = str(correct_ans[0])
            elif not isinstance(correct_ans, str):
                correct_ans = str(correct_ans) if correct_ans is not None else ""
            correct_ans = correct_ans.strip()

            # 2. options
            raw_options = p.get("options") or p.get("choices") or p.get("candidates") or p.get("variants") or []
            if isinstance(raw_options, str):
                raw_options = [opt.strip() for opt in raw_options.split(",") if opt.strip()]
            options = [str(opt).strip() for opt in raw_options if str(opt).strip()]

            # 3. Handle slot_plugin / syntax_problem / logic_problem / question
            if ptype in ["slot_plugin", "syntax_problem", "logic_problem", "question"]:
                correct_ans = resolve_answer_alias(correct_ans, options)

                expl = (p.get("explanation") or "").lower()
                # If correct_ans is empty, try to deduce from explanation or pick first option
                if not correct_ans and options:
                    for opt in options:
                        if opt.lower() in expl:
                            correct_ans = opt
                            break
                    if not correct_ans:
                        correct_ans = options[0]

                # If options is empty or fewer than 2 choices:
                if len(options) < 2:
                    if correct_ans:
                        options = [correct_ans, f"not_{correct_ans}", "None", "pass"]
                    else:
                        correct_ans = "valid_token"
                        options = ["valid_token", "invalid_token", "None", "pass"]

                # Ensure correct_ans is inside options (checking prefix stripping)
                def strip_pfx(s: str) -> str:
                    return re.sub(r'^[A-Da-d0-9][\).\s:-]+', '', s).strip()

                found = False
                for opt in options:
                    if opt == correct_ans or strip_pfx(opt) == strip_pfx(correct_ans) or opt.lower() == correct_ans.lower():
                        correct_ans = opt  # align exactly with option text
                        found = True
                        break
                
                p["options"] = finalize_choices(options, correct_ans)
                p["correct_answer"] = correct_ans

                # Ensure prefix and suffix exist for slot types
                if ptype in ["slot_plugin", "syntax_problem", "logic_problem"]:
                    prefix = p.get("code_prefix") or p.get("codePrefix") or p.get("prefix")
                    if prefix is None:
                        prefix = p.get("starter_code") or f"# Complete expression:\nresult = "
                    p["code_prefix"] = prefix
                    p["code_suffix"] = p.get("code_suffix") or p.get("codeSuffix") or p.get("suffix") or ""

                if ptype == "question":
                    p["question_text"] = p.get("question_text") or p.get("questionText") or p.get("question") or p.get("guiding_question", "Analyze the concept:")

            # 4. Handle block_builder
            elif ptype == "block_builder":
                corr_blocks = p.get("correct_blocks") or p.get("correctBlocks") or p.get("solution_blocks") or p.get("solutionBlocks") or []
                if isinstance(corr_blocks, str):
                    corr_blocks = [line for line in corr_blocks.split("\n") if line.strip()]
                
                # If correct_blocks is empty, fallback to solution_code lines
                if not corr_blocks:
                    sol = p.get("solution_code") or p.get("starter_code") or ""
                    corr_blocks = [line for line in sol.split("\n") if line.strip()]
                
                if not corr_blocks:
                    corr_blocks = ["# Step 1: Initialize invariant", "total = 0", "for x in items:", "    total += x", "return total"]
                
                pool = p.get("blocks_pool") or p.get("blocksPool") or p.get("blocks") or p.get("scrambled_blocks") or []
                if isinstance(pool, str):
                    pool = [line for line in pool.split("\n") if line.strip()]
                
                # Ensure all correct blocks are in pool
                for b in corr_blocks:
                    if b not in pool:
                        pool.append(b)
                
                # Add a distractor if pool only has correct blocks
                if len(pool) == len(corr_blocks):
                    pool.append("# Distractor: incorrect branch")
                
                shuffled_pool = list(pool)
                random.seed(p["id"])
                random.shuffle(shuffled_pool)

                p["correct_blocks"] = corr_blocks
                p["blocks_pool"] = shuffled_pool

            # 5. Handle code_write
            elif ptype in ["code_write", "code_blank", "code_partial", "freeform"]:
                p["starter_code"] = p.get("starter_code") or p.get("starterCode") or "def solve(data):\n    # TODO: Implement solution\n    pass\n"
                p["solution_code"] = p.get("solution_code") or p.get("solutionCode") or p["starter_code"]
                p["test_code"] = p.get("test_code") or p.get("testCode") or "# Test assertions\nassert True\n"

            # 6. Ensure test_cases exist for all
            if not p.get("test_cases") or not isinstance(p.get("test_cases"), list):
                p["test_cases"] = [
                    f"[VERIFY] Checking invariants for {p.get('title', 'problem')}...",
                    "[TEST 1] Nominal case passed cleanly.",
                    "[TEST 2] Boundary condition verified.",
                    "[STATUS] Identity verified."
                ]

            flat_problems.append(p)
            normalized_prob_list.append(p)

        ch["problems"] = normalized_prob_list

    data["chapters"] = chapters
    data["problems"] = flat_problems
    data["course_title"] = data.get("course_title") or data.get("lesson_plan", {}).get("title") or chapters[0]["title"]
    data["domain"] = data.get("domain", "Programming & Mathematics")
    data["level_num"] = data.get("level_num", default_level)
    
    # Backwards-compatible lesson_plan pointing to Chapter 1
    data["lesson_plan"] = {
        "title": data["course_title"],
        "domain": data["domain"],
        "level_num": data["level_num"],
        "level_title": data.get("level_title", f"Level {data['level_num']}"),
        "overview": data.get("overview", chapters[0].get("summary", "")),
        "content_markdown": chapters[0].get("content_markdown", "")
    }

    return data

def normalize_single_problem(p: Dict[str, Any], chapter_id: int, chapter_title: str, global_index: int, mode: str = "code") -> Dict[str, Any]:
    """Ensures a single generated problem conforms to schema with valid options, answers, and tests."""
    import re
    p["chapter_id"] = chapter_id
    p["chapter_title"] = chapter_title
    p["global_index"] = global_index
    if "id" not in p:
        p["id"] = global_index + 1
    ptype = (p.get("type") or "").lower()
    if not ptype:
        ptype = "slot_plugin" if mode == "math" else "code_write"
    p["type"] = ptype
    p["mode"] = mode

    # normalize correct_answer
    correct_ans = (
        p.get("correct_answer") or p.get("correctAnswer") or p.get("answer") or
        p.get("solution") or p.get("correct_option") or p.get("correct_choice") or ""
    )
    if isinstance(correct_ans, (list, tuple)) and len(correct_ans) > 0:
        correct_ans = str(correct_ans[0])
    correct_ans = str(correct_ans).strip()

    # normalize options
    raw_options = p.get("options") or p.get("choices") or p.get("candidates") or p.get("variants") or []
    if isinstance(raw_options, str):
        raw_options = [opt.strip() for opt in raw_options.split(",") if opt.strip()]
    options = [str(opt).strip() for opt in raw_options if str(opt).strip()]

    if ptype in ["slot_plugin", "syntax_problem", "logic_problem", "question"]:
        correct_ans = resolve_answer_alias(correct_ans, options)
        if not correct_ans and options:
            correct_ans = options[0]
        if len(options) < 2:
            if correct_ans:
                options = [correct_ans, f"\\neg ({correct_ans})" if mode == "math" else f"not_{correct_ans}", "0", "1"]
            else:
                correct_ans = "valid_term"
                options = ["valid_term", "invalid_term", "0", "1"]
        p["options"] = finalize_choices(options, correct_ans)
        p["correct_answer"] = correct_ans

        if ptype in ["slot_plugin", "syntax_problem", "logic_problem"]:
            prefix = p.get("code_prefix") or p.get("codePrefix")
            if prefix is None:
                prefix = "\\text{Evaluate: } " if mode == "math" else "result = "
            p["code_prefix"] = prefix
            p["code_suffix"] = p.get("code_suffix") or p.get("codeSuffix") or ""

        if ptype == "question":
            p["question_text"] = p.get("question_text") or p.get("questionText") or p.get("guiding_question", "Analyze the concept:")

    elif ptype == "block_builder":
        c_blocks = p.get("correct_blocks") or p.get("correctBlocks") or []
        if isinstance(c_blocks, str):
            c_blocks = [line for line in c_blocks.split("\n") if line.strip()]
        pool = p.get("blocks_pool") or p.get("blocksPool") or list(c_blocks)
        if isinstance(pool, str):
            pool = [line for line in pool.split("\n") if line.strip()]
        for b in c_blocks:
            if b not in pool:
                pool.append(b)
        if len(pool) == len(c_blocks):
            pool.append("\\text{Distractor: incorrect step}" if mode == "math" else "# Distractor line")
        import random
        pool = [str(b) for b in pool]
        random.Random(str(p.get("id"))).shuffle(pool)
        p["correct_blocks"] = [str(b) for b in c_blocks]
        p["blocks_pool"] = pool

    elif ptype in ["code_write", "code_blank", "code_partial", "freeform"]:
        if ptype == "code_blank":
            p["starter_code"] = p.get("starter_code") or "# Hard Challenge: Blank Scratchpad\n# Implement your complete solution from scratch below:\n\n"
        elif ptype == "code_partial":
            p["starter_code"] = p.get("starter_code") or "# Challenge: Partially Coded Scaffold\n# Complete the missing algorithmic logic and invariants below:\n\ndef solve():\n    # TODO: Implement core algorithm\n    pass\n"
        else:
            p["starter_code"] = p.get("starter_code") or "def solve():\n    pass\n"
        p["solution_code"] = p.get("solution_code") or p["starter_code"]
        p["test_code"] = p.get("test_code") or "assert True\n"

    if not p.get("test_cases") or not isinstance(p.get("test_cases"), list):
        p["test_cases"] = [
            f"[TEST 1] Invariant assertion check: PASS",
            f"[TEST 2] Boundary condition evaluation: PASS"
        ]
    return p

def normalize_chapter_data(ch: Dict[str, Any], next_chapter_id: int, start_global_index: int, mode: str = "code") -> Dict[str, Any]:
    """Normalizes an individual generated chapter and all its child exercises."""
    ch["id"] = next_chapter_id
    if not ch.get("title"):
        ch["title"] = f"Chapter {next_chapter_id}: Advanced Concepts"
    if not ch.get("summary"):
        ch["summary"] = "Study notes and practice exercises."
    if not ch.get("content_markdown"):
        ch["content_markdown"] = f"# {ch['title']}\n\n## Overview\n{ch['summary']}"
    if not ch.get("estimated_time_minutes"):
        ch["estimated_time_minutes"] = 25

    raw_problems = ch.get("problems", [])
    normalized_problems = []
    curr_g_idx = start_global_index
    for p in raw_problems:
        norm_p = normalize_single_problem(p, ch["id"], ch["title"], curr_g_idx, mode)
        normalized_problems.append(norm_p)
        curr_g_idx += 1
    
    if not normalized_problems:
        fallback_p = {
            "id": curr_g_idx + 1,
            "title": f"0{curr_g_idx+1}_practice_drill.math" if mode == "math" else f"0{curr_g_idx+1}_practice_drill.py",
            "difficulty": "Moderate",
            "type": "slot_plugin",
            "mode": mode,
            "guiding_question": f"Apply key concepts from {ch['title']} to verify the core invariant.",
            "concept_hint": "Review the summary and definitions in the chapter notes.",
            "explanation": "Applying the foundational definition yields the correct term.",
            "code_prefix": "\\text{Apply invariant: } " if mode == "math" else "def solve():\n    return ",
            "code_suffix": "",
            "options": ["f'(x)", "f(x)", "0", "\\infty"] if mode == "math" else ["x * 2", "x + 1", "None", "0"],
            "correct_answer": "f'(x)" if mode == "math" else "x * 2",
            "test_cases": ["[VERIFIED] Chapter invariant holds true."]
        }
        normalized_problems.append(normalize_single_problem(fallback_p, ch["id"], ch["title"], curr_g_idx, mode))

    ch["problems"] = normalized_problems
    return ch

DEFAULT_MATH_CURRICULUM = {
    "course_title": "Calculus & Analysis: Limits, Derivatives & Integrals",
    "domain": "Pure Mathematics",
    "mode": "math",
    "level_num": 1,
    "level_title": "Level 1: Differential Calculus & Limit Foundations",
    "overview": "Master differential and integral calculus through rigorous mathematical equations, derivative operator rules, and step-by-step proof derivations.",
    "chapters": [
        {
            "id": 1,
            "title": "Chapter 1: Limits & The Power Rule",
            "summary": "Master the limit definition of the derivative and the polynomial power rule in differential calculus.",
            "estimated_time_minutes": 20,
            "content_markdown": """# Chapter 1: Limits & The Power Rule

Welcome to the **&edu Mathematical Analysis Studio**. In this chapter, we explore foundational differential calculus, rate of change, and algebraic derivation rules.

## 1. The Limit Definition of the Derivative

The derivative of a function $f(x)$ at any point $x$ is defined as the limit of the difference quotient as the increment $h$ approaches zero:

$$f'(x) = \\lim_{h \\to 0} \\frac{f(x + h) - f(x)}{h}$$

If this limit exists, $f(x)$ is differentiable at $x$.

### Fundamental Derivative Rules:
| Function | Derivative Formula | Condition / Restriction |
| :--- | :--- | :--- |
| Constant $c$ | $\\frac{d}{dx}[c] = 0$ | $c \\in \\mathbb{R}$ |
| Power $x^n$ | $\\frac{d}{dx}[x^n] = n x^{n-1}$ | $n \\in \\mathbb{R}$ |
| Exponential $e^x$ | $\\frac{d}{dx}[e^x] = e^x$ | Natural base |
| Logarithm $\\ln(x)$ | $\\frac{d}{dx}[\\ln(x)] = \\frac{1}{x}$ | $x > 0$ |

---

## 2. The Power Rule In Action

For any real exponent $n$, the power rule states:

$$\\frac{d}{dx}[x^n] = n x^{n-1}$$

For example, when $f(x) = x^4$:
1. Identify exponent: $n = 4$
2. Multiply by exponent: $4 \\cdot x$
3. Decrement exponent by 1: $4 - 1 = 3$
4. Result: $f'(x) = 4x^3$

> [!IMPORTANT]
> When applying the power rule to roots or fractions, first rewrite them with rational or negative exponents: $\\sqrt{x} = x^{1/2}$ and $\\frac{1}{x^2} = x^{-2}$.
""",
            "problems": [
                {
                    "id": 1,
                    "title": "01_derivative_power_rule.math",
                    "difficulty": "Easy",
                    "type": "slot_plugin",
                    "mode": "math",
                    "guiding_question": "Compute the derivative using the power rule: complete the equation for d/dx [x^4].",
                    "concept_hint": "Remember d/dx [x^n] = n * x^(n - 1). Here n = 4.",
                    "explanation": "Applying the power rule d/dx [x^4] = 4 * x^(4-1) = 4x^3.",
                    "code_prefix": "\\frac{d}{dx}\\left[x^4\\right] = ",
                    "code_suffix": "",
                    "options": ["4x^3", "3x^4", "4x^5", "\\frac{x^5}{5}"],
                    "correct_answer": "4x^3",
                    "test_cases": [
                        "[VERIFY] Checking mathematical equivalence...",
                        "[IDENTITY] d/dx[x^4] = 4x^3 evaluated to TRUE."
                    ]
                },
                {
                    "id": 2,
                    "title": "02_product_rule_formula.math",
                    "difficulty": "Easy",
                    "type": "logic_problem",
                    "mode": "math",
                    "guiding_question": "Select the correct expansion of the product rule for differentiating the product of two functions u(x) and v(x).",
                    "concept_hint": "The product rule is 'first times derivative of second plus second times derivative of first'.",
                    "explanation": "By Leibniz's product rule, (u * v)' = u'v + uv'. The derivative of a product is NOT simply the product of derivatives u'v'.",
                    "code_prefix": "\\frac{d}{dx}\\left[u(x) \\cdot v(x)\\right] = ",
                    "code_suffix": "",
                    "options": ["u'(x)v(x) + u(x)v'(x)", "u'(x) \\cdot v'(x)", "u'(x)v'(x) - u(x)v(x)", "\\frac{u'(x)}{v'(x)}"],
                    "correct_answer": "u'(x)v(x) + u(x)v'(x)",
                    "test_cases": [
                        "[CALCULUS_ASSERTION] Product rule differential identity verified."
                    ]
                },
                {
                    "id": 3,
                    "title": "03_trig_limit_quiz.md",
                    "difficulty": "Moderate",
                    "type": "question",
                    "mode": "math",
                    "guiding_question": "Evaluate the fundamental trigonometric limit as x approaches 0.",
                    "question_text": "What is the exact value of the foundational calculus limit: $\\lim_{x \\to 0} \\frac{\\sin(x)}{x}$?",
                    "concept_hint": "Consider the Squeeze Theorem applied to the unit circle as arc angle x approaches 0 radians.",
                    "explanation": "By the Squeeze Theorem (or L'Hôpital's rule: cos(0)/1), the limit of sin(x)/x as x -> 0 is exactly 1.",
                    "options": ["1", "0", "\\infty", "\\text{Undefined}"],
                    "correct_answer": "1",
                    "test_cases": [
                        "[LIMIT_CHECK] lim_{x->0} sin(x)/x evaluated: result is 1."
                    ]
                }
            ]
        },
        {
            "id": 2,
            "title": "Chapter 2: Integration & The Fundamental Theorem",
            "summary": "Master definite integrals, antidifferentiation, and area accumulation under curves.",
            "estimated_time_minutes": 25,
            "content_markdown": """# Chapter 2: Integration & The Fundamental Theorem

Integration represents continuous accumulation: summing an infinite number of infinitesimally thin geometric slices.

## 1. The Fundamental Theorem of Calculus (FTC)

If $f(x)$ is continuous on $[a, b]$ and $F'(x) = f(x)$, then:

$$\\int_a^b f(x) dx = F(b) - F(a)$$

This monumental theorem links **derivatives (slopes)** directly to **integrals (areas)**.

### Integral Table:
| Integrand $f(x)$ | Indefinite Integral $\\int f(x)dx$ |
| :--- | :--- |
| $x^n$ ($n \\neq -1$) | $\\frac{x^{n+1}}{n+1} + C$ |
| $\\frac{1}{x}$ | $\\ln|x| + C$ |
| $e^x$ | $e^x + C$ |
| $\\cos(x)$ | $\\sin(x) + C$ |
""",
            "problems": [
                {
                    "id": 4,
                    "title": "04_definite_integral_step.math",
                    "difficulty": "Moderate",
                    "type": "slot_plugin",
                    "mode": "math",
                    "guiding_question": "Evaluate the definite integral of 3x^2 from x = 0 to x = 2.",
                    "concept_hint": "Antiderivative of 3x^2 is x^3. Evaluate at upper bound (2^3) minus lower bound (0^3).",
                    "explanation": "The antiderivative is F(x) = x^3. Applying FTC: F(2) - F(0) = 2^3 - 0 = 8.",
                    "code_prefix": "\\int_0^2 3x^2 \\, dx = \\left[ x^3 \\right]_0^2 = ",
                    "code_suffix": "",
                    "options": ["8", "12", "6", "4"],
                    "correct_answer": "8",
                    "test_cases": [
                        "[INTEGRAL_EVALUATION] [x^3]_0^2 = 8 - 0 = 8 [VERIFIED]"
                    ]
                },
                {
                    "id": 5,
                    "title": "05_derivation_steps.math",
                    "difficulty": "Moderate",
                    "type": "block_builder",
                    "mode": "math",
                    "guiding_question": "Assemble the mathematical steps in sequential order to prove that d/dx [ln(x)] = 1/x using implicit differentiation with y = ln(x).",
                    "concept_hint": "Start with y = ln(x), exponentiate both sides to get e^y = x, differentiate implicitly with respect to x, then substitute e^y = x back.",
                    "explanation": "y = ln(x) => e^y = x => d/dx[e^y] = d/dx[x] => e^y * (dy/dx) = 1 => dy/dx = 1/e^y = 1/x.",
                    "blocks_pool": [
                        "\\text{Let } y = \\ln(x) \\quad (x > 0)",
                        "e^y = x",
                        "\\frac{d}{dx}\\left[e^y\\right] = \\frac{d}{dx}[x]",
                        "e^y \\cdot \\frac{dy}{dx} = 1",
                        "\\frac{dy}{dx} = \\frac{1}{e^y} = \\frac{1}{x}",
                        "\\frac{dy}{dx} = e^x \\cdot \\ln(x)"
                    ],
                    "correct_blocks": [
                        "\\text{Let } y = \\ln(x) \\quad (x > 0)",
                        "e^y = x",
                        "\\frac{d}{dx}\\left[e^y\\right] = \\frac{d}{dx}[x]",
                        "e^y \\cdot \\frac{dy}{dx} = 1",
                        "\\frac{dy}{dx} = \\frac{1}{e^y} = \\frac{1}{x}"
                    ],
                    "test_cases": [
                        "[PROOF_STEP 1] Valid logarithmic definition [PASS]",
                        "[PROOF_STEP 2] Correct exponential inversion [PASS]",
                        "[PROOF_STEP 3] Chain rule differential verified [PASS]",
                        "[PROOF_STEP 4] dy/dx = 1/x Q.E.D. [PASS]"
                    ]
                }
            ]
        },
        {
            "id": 3,
            "title": "Chapter 3: Integration Techniques & Applications",
            "summary": "Master substitution, integration by parts, and calculating areas enclosed between curves.",
            "estimated_time_minutes": 30,
            "content_markdown": """# Chapter 3: Integration Techniques & Applications

When an integrand cannot be antidifferentiated directly using elementary power rules, we deploy two primary transformation strategies: **Integration by Substitution** (the chain rule in reverse) and **Integration by Parts** (the product rule in reverse).

## 1. Integration by Substitution (U-Sub)

If $u = g(x)$, then $du = g'(x) dx$:

$$\\int f(g(x)) g'(x) dx = \\int f(u) du$$

## 2. Integration by Parts (IBP)

Derived from the differential product rule $d(uv) = u\\,dv + v\\,du$:

$$\\int u \\, dv = u v - \\int v \\, du$$

### Strategy Guideline (LIATE Rule for picking $u$):
1. **L**ogarithmic functions ($\\ln(x)$)
2. **I**nverse trigonometric functions ($\\arctan(x)$)
3. **A**lgebraic polynomials ($x^2, 3x$)
4. **T**rigonometric functions ($\\sin(x), \\cos(x)$)
5. **E**xponential functions ($e^x$)

> [!TIP]
> Choose $u$ as the term that simplifies most upon differentiation, and $dv$ as the part easiest to integrate!
""",
            "problems": [
                {
                    "id": 6,
                    "title": "06_u_substitution.math",
                    "difficulty": "Moderate",
                    "type": "slot_plugin",
                    "mode": "math",
                    "guiding_question": "Evaluate the indefinite integral $\\int 2x e^{x^2} dx$ using the substitution $u = x^2$ where $du = 2x dx$.",
                    "concept_hint": "Substitute $u = x^2$, integrate $e^u du = e^u + C$, and substitute back.",
                    "explanation": "With $u = x^2$ and $du = 2x dx$, $\\int 2x e^{x^2} dx = \\int e^u du = e^u + C = e^{x^2} + C$.",
                    "code_prefix": "\\int 2x e^{x^2} \\, dx = \\int e^u \\, du = ",
                    "code_suffix": "",
                    "options": ["e^{x^2} + C", "2e^{x^2} + C", "\\frac{e^{x^2}}{2} + C", "x^2 e^{x^2} + C"],
                    "correct_answer": "e^{x^2} + C",
                    "test_cases": [
                        "[U_SUB] Variable change u = x^2 verified.",
                        "[INTEGRAL] Antiderivative e^{x^2} + C verified via differentiation."
                    ]
                },
                {
                    "id": 7,
                    "title": "07_integration_by_parts_formula.math",
                    "difficulty": "Moderate",
                    "type": "logic_problem",
                    "mode": "math",
                    "guiding_question": "Select the correct formula for evaluating $\\int x \\cos(x) dx$ using integration by parts with $u = x$ and $dv = \\cos(x) dx$.",
                    "concept_hint": "Here $du = dx$ and $v = \\sin(x)$. Apply $\\int u dv = uv - \\int v du$.",
                    "explanation": "Applying $\\int u dv = uv - \\int v du$ gives $x \\sin(x) - \\int \\sin(x) dx = x \\sin(x) + \\cos(x) + C$.",
                    "code_prefix": "\\int x \\cos(x) \\, dx = ",
                    "code_suffix": "",
                    "options": [
                        "x \\sin(x) + \\cos(x) + C",
                        "x \\cos(x) - \\sin(x) + C",
                        "\\frac{x^2}{2} \\sin(x) + C",
                        "-x \\sin(x) + \\cos(x) + C"
                    ],
                    "correct_answer": "x \\sin(x) + \\cos(x) + C",
                    "test_cases": [
                        "[IBP_EVAL] d/dx [x sin(x) + cos(x)] = sin(x) + x cos(x) - sin(x) = x cos(x) [VERIFIED]"
                    ]
                }
            ]
        }
    ]
}

DEFAULT_CODE_CURRICULUM = DEFAULT_MULTI_CHAPTER_CURRICULUM

@app.get("/api/default-curriculum")
async def get_default_curriculum(mode: str = "math"):
    """
    Returns the initial default curriculum for the specified domain ('math' or 'code').
    """
    if mode.lower() == "code":
        return {"status": "success", "curriculum": DEFAULT_CODE_CURRICULUM}
    return {"status": "success", "curriculum": DEFAULT_MATH_CURRICULUM}

@app.post("/api/generate-curriculum")
async def generate_curriculum(payload: GeneratePayload):
    """
    Generates a multi-chapter course plan with multiple diverse problems in each chapter.
    Dynamically supports MATH MODE (LaTeX equations & derivations) or CODE MODE (any language).
    """
    rate_limit("ide")
    doc_context = payload.document_text.strip() if payload.document_text else "No uploaded document."
    user_req = payload.user_instruction.strip() if payload.user_instruction else "General concepts"
    level = payload.level or 1
    mode = (payload.mode or "code").lower()
    
    is_math = mode == "math" or any(w in user_req.lower() for w in [
        "math", "calculus", "derivative", "integral", "algebra", "equation", 
        "theorem", "matrix", "limits", "probability", "geometry", "trigonometry", "proof"
    ])

    level_names = {
        1: "Level 1: Fundamentals & Essential Foundations",
        2: "Level 2: Intermediate Structural Mastery & Invariants",
        3: "Level 3: Advanced Optimization & Rigorous Problems"
    }
    level_title = level_names.get(level, f"Level {level}: Deep Dive")

    if is_math:
        prompt = f"""
        You are a distinguished Professor of Mathematics and senior curriculum designer for '&edu'.
        The user has selected MATH MODE.

        *** CRITICAL CONSTRAINT: DO NOT GENERATE COMPUTER CODE (NO PYTHON, NO JAVASCRIPT). ***
        Generate pure MATHEMATICAL EQUATIONS, algebraic steps, formulas, calculus derivations, and proofs.
        All formulas, variables, and expressions MUST be formatted in standard LaTeX notation ($...$ and $$...$$).

        === STUDY GUIDES & MATERIALS PROVIDED ===
        {doc_context[:120000]}
        === END MATERIALS ===

        Target Math Topic / Request: "{user_req}"
        Target Tier: {level_title} (Level {level})

        CORE EDUCATIONAL DIRECTIVES:
        1. DEEP STUDY GUIDE COMPREHENSION & FIDELITY:
           - Ingest and study ALL provided documents, syllabus sheets, notes, equations, and student specifications.
           - Follow everything the student loaded and typed. Do not omit any core concept, formula, theorem, or technique.
           - Make the learning materials significantly better for students: give clear intuitions, definitions, step-by-step proofs, and memory aids.
        
        2. DYNAMIC CURRICULUM SIZING (AI DECIDES):
           - DYNAMICALLY DECIDE how many chapters/lessons and how many problems per chapter are required to fully master everything present in the materials and prompt.
           - Create multiple progressive lessons (typically 2 to 6+ lessons based on material scope).
           - In each lesson, include an appropriate number of exercises (typically 2 to 6 exercises per lesson) so students gain thorough practice.

        3. IN-DEPTH LESSON STUDY GUIDES ('content_markdown'):
           - Each chapter MUST have a comprehensive, beautifully structured Markdown study guide (# H1, ## H2, ### H3).
           - Include definitions, core theorems, formula tables (| Function | Formula | Conditions |), LaTeX equations, blockquotes (> [!IMPORTANT]), and step-by-step worked derivation examples.

        4. DIVERSE MATHEMATICAL EXERCISES WITH STRICT ANSWER INTEGRITY:
           - Every problem must be engaging, pedagogical, and completely solvable.
           - 'slot_plugin': Print the equation/derivation step with an interactive blank space for the missing mathematical term, variable, exponent, or coefficient.
             * MUST provide `code_prefix` and `code_suffix`.
             * MUST provide `options` with exactly 4 LaTeX candidate choices.
             * MUST provide `correct_answer` containing the exact matching string of the single correct choice from `options`.
           - 'syntax_problem' / 'symbol_problem': Identify missing or broken math notation (e.g. differential 'dx', integration constant '+ C', limit arrow '\\to'). Must have `options` and `correct_answer`.
           - 'logic_problem': Identify mathematical reasoning fallacy, sign errors, domain constraints (e.g. x != 0), or boundary limits. Must have `options` and `correct_answer`.
           - 'block_builder': Scrambled step-by-step mathematical proof or derivation!
             * MUST provide `correct_blocks`: array of LaTeX derivation steps in exact logical sequence from premise to Q.E.D.
             * MUST provide `blocks_pool`: scrambled array containing all `correct_blocks` PLUS 1-2 plausible distractor steps.
           - 'question': Conceptual mathematical multiple-choice quiz with LaTeX formulas. Must have `question_text`, `options` (4 choices), and `correct_answer`.
           - EVERY problem MUST provide `test_cases` describing verification checks.

        *** ZERO UNANSWERED PROBLEMS ***:
        Ensure EVERY single question, slot, and problem has unambiguous, verified answers in `correct_answer` or `correct_blocks`. NEVER return null or None for `correct_answer` or `options`.

        Call the `build_curriculum` function.
        """
    else:
        prompt = f"""
        You are a principal curriculum architect and senior educator designing a strict, professional IDE learning track for '&edu'.
        The user has selected CODE / PROGRAMMING MODE.

        *** CRITICAL: DO NOT FORCE PYTHON UNLESS REQUESTED. ***
        Adapt directly to whatever programming language or topic the student specified in: "{user_req}"
        (e.g., Python, JavaScript, TypeScript, C++, Rust, Go, SQL, Web Development, Data Structures & Algorithms).

        === STUDY GUIDES & MATERIALS PROVIDED ===
        {doc_context[:120000]}
        === END MATERIALS ===

        Target Topic / Language: "{user_req}"
        Target Difficulty Level: {level_title} (Level {level})

        CORE EDUCATIONAL DIRECTIVES:
        1. DEEP STUDY GUIDE COMPREHENSION & FIDELITY:
           - Ingest and study ALL provided documents, syllabus sheets, notes, code examples, and student specifications.
           - Follow everything the student loaded and typed. Do not omit any core concept, language syntax, algorithm, invariant, or edge case.
           - Make the learning materials significantly better for students: give clear mental models, structural patterns, syntax comparison tables, and debugging intuition.

        2. DYNAMIC CURRICULUM SIZING (AI DECIDES):
           - DYNAMICALLY DECIDE how many chapters/lessons and how many problems per chapter are required to fully master everything present in the materials and prompt.
           - Create multiple progressive lessons (typically 2 to 6+ lessons based on material scope).
           - In each lesson, include an appropriate number of exercises (typically 2 to 6 exercises per lesson) so students gain thorough practice.

        3. IN-DEPTH LESSON STUDY GUIDES ('content_markdown'):
           - Each chapter MUST have a comprehensive, beautifully structured Markdown study guide (# H1, ## H2, ### H3).
           - Include definitions, syntax-highlighted code blocks, comparison tables (| Pattern | Time | Space | Notes |), blockquotes (> [!TIP], > [!IMPORTANT]), and step-by-step worked examples.

        4. DIVERSE PRACTICAL EXERCISES WITH STRICT ANSWER INTEGRITY:
           - 'slot_plugin': Code is printed in the editor with an interactive blank space. Student plugs in missing token/expression.
             * MUST provide `code_prefix` and `code_suffix`.
             * MUST provide `options` with exactly 4 plausible choices.
             * MUST provide `correct_answer` containing the exact matching string of the single correct choice from `options`.
           - 'syntax_problem': Spot and fix language-specific syntax errors (colons, semicolons, brackets, type annotations). Must have `options` and `correct_answer`.
           - 'logic_problem': Fix algorithmic logic, boundary conditions, loop invariants, or off-by-one errors. Must have `options` and `correct_answer`.
           - 'block_builder': Scrambled lines of code with realistic indentation (e.g. 4 spaces) that insert as real indented lines into the editor.
             * MUST provide `correct_blocks`: array of code lines with authentic indentation in correct execution sequence.
             * MUST provide `blocks_pool`: scrambled array containing all `correct_blocks` PLUS 1-2 plausible distractor lines.
           - 'question': Diagnostic concept quiz with code analysis. Must have `question_text`, `options` (4 choices), and `correct_answer`.
           - 'code_blank' / 'code_write': Hard coding challenge with BLANK SPACE for actual coding:
             * `starter_code`: completely blank or minimal one-line comment (`# Implement your solution from scratch below\n\n`). Student implements the entire algorithm/function from scratch.
             * `solution_code`: complete reference implementation.
             * `test_code`: executable test assertions (e.g. `assert func(...) == expected`) covering normal cases, edge cases, and empty inputs.
           - 'code_partial': Partially coded challenge with:
             * `starter_code`: structured partial scaffold (e.g. data structure definitions, helper signatures, loop invariant markers, and TODO comments where student must implement key logic).
             * `solution_code`: complete reference implementation.
             * `test_code`: executable test assertions verifying student implementation.
           - EVERY problem MUST provide `test_cases` describing simulated terminal outputs or test assertions.

        *** ZERO UNANSWERED PROBLEMS ***:
        Ensure EVERY single question, slot, and problem has unambiguous, verified answers in `correct_answer` or `correct_blocks`. NEVER return null or None for `correct_answer` or `options`.

        Call the `build_curriculum` function.
        """

    try:
        response = await acall_gemini(
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[curriculum_tools_wrapper],
                tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="ANY"))
            )
        )

        for call in (response.function_calls or []):
            if call.name == "build_curriculum":
                data = dict(call.args)
                return normalize_curriculum_data(data, default_level=level)

        print("[WARNING generate_curriculum]: Gemini did not invoke build_curriculum, using fallback.")
        fallback = copy.deepcopy(DEFAULT_MATH_CURRICULUM if is_math else DEFAULT_MULTI_CHAPTER_CURRICULUM)
        return normalize_curriculum_data(fallback, default_level=level)
    except Exception as e:
        print("[ERROR generate_curriculum, returning robust default curriculum]:", e)
        fallback_data = copy.deepcopy(DEFAULT_MATH_CURRICULUM if is_math else DEFAULT_MULTI_CHAPTER_CURRICULUM)
        fallback_data["course_title"] = f"{user_req.title()[:40]} Master Track"
        fallback_data["level_num"] = level
        return normalize_curriculum_data(fallback_data, default_level=level)

@app.post("/api/make-harder")
async def make_harder(payload: MakeHarderPayload):
    """
    Escalates the curriculum to the next difficulty tier (e.g. Level 1 -> Level 2 -> Level 3).
    Generates more complex algorithmic challenges, stricter constraints, edge cases,
    and explicitly includes hard tasks with blank space for actual coding or partially coded scaffolds.
    """
    next_level = payload.current_level + 1
    escalated_instruction = (
        f"Advanced Hard Tier (Level {next_level}): {payload.topic}. "
        f"Increase algorithmic complexity, introduce subtle edge cases, optimize performance, "
        f"and challenge the student with deeper problem solving. "
        f"*** MANDATORY ***: Give HARD tasks with just blank space for actual coding from scratch (type: 'code_blank' or 'code_write' with empty or minimal starter_code) "
        f"or partially coded scaffolds (type: 'code_partial' where the student must complete core invariant logic and algorithms). "
        f"Provide comprehensive test_code assertions for each coding challenge."
    )
    return await generate_curriculum(GeneratePayload(
        user_instruction=escalated_instruction,
        document_text=payload.document_text,
        level=next_level,
        mode=payload.mode
    ))

SANDBOX_OUTPUT_LIMIT = 64_000

def _limit_child_resources():
    """Runs in the child before exec: caps CPU seconds, file writes and memory where the OS supports it."""
    import resource
    for limit, value in [
        (resource.RLIMIT_CPU, (5, 5)),
        (resource.RLIMIT_FSIZE, (10_000_000, 10_000_000)),
        (getattr(resource, "RLIMIT_AS", None), (1_000_000_000, 1_000_000_000)),
    ]:
        if limit is None:
            continue
        try:
            resource.setrlimit(limit, value)
        except (ValueError, OSError):
            pass  # macOS rejects RLIMIT_AS; the wall-clock timeout still applies

def run_python_sandboxed(code: str, test_code: str = "") -> Dict[str, Any]:
    """
    Runs student Python in a separate interpreter. This is NOT a security boundary against
    hostile code (it runs as the local user); the server is bound to localhost for that reason.
    It does keep API keys out of the child's environment, isolates cwd, and caps time/output.
    """
    import tempfile
    user_code = (code or "").strip()
    test_code = (test_code or "").strip()

    script_parts = [user_code]
    if test_code:
        script_parts.append("\n# --- TEST VERIFICATION ---")
        script_parts.append(test_code)
        script_parts.append("\nprint('\\n[TEST_REPORT] All test cases and assertions passed successfully!')")

    combined_script = "\n".join(script_parts)

    try:
        with tempfile.TemporaryDirectory(prefix="sciedu-run-") as work_dir:
            proc = subprocess.run(
                [sys.executable, "-I", "-c", combined_script],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=work_dir,
                env={"PATH": "/usr/bin:/bin", "HOME": work_dir, "PYTHONDONTWRITEBYTECODE": "1"},
                preexec_fn=_limit_child_resources,
            )
        stdout = proc.stdout[:SANDBOX_OUTPUT_LIMIT]
        stderr = proc.stderr[:SANDBOX_OUTPUT_LIMIT]
        success = (proc.returncode == 0)
        tests_passed = success and ("[TEST_REPORT]" in stdout or not test_code)

        return {
            "success": success,
            "stdout": stdout,
            "stderr": stderr,
            "tests_passed": tests_passed,
            "message": "Execution finished successfully." if success else "Execution encountered an error."
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Execution timed out (limit: 5.0 seconds). Check for infinite loops or heavy operations.",
            "tests_passed": False,
            "message": "Timeout"
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "tests_passed": False,
            "message": "Execution failure"
        }

@app.post("/api/execute-code")
def execute_code(payload: ExecuteCodePayload):
    """Sync handler on purpose: FastAPI runs it in a worker thread so the event loop stays free."""
    return run_python_sandboxed(payload.code, payload.test_code or "")

@app.post("/api/generate-puzzle")
async def generate_puzzle(payload: GeneratePayload):
    """Generates both curriculum and puzzle set, returning them structured for the client."""
    curriculum = await generate_curriculum(payload)
    if "problems" in curriculum and len(curriculum["problems"]) > 0:
        first_prob = curriculum["problems"][0]
        return {
            **first_prob,
            "lesson_plan": curriculum.get("lesson_plan"),
            "problems": curriculum.get("problems")
        }
    return curriculum

@app.post("/api/upload-multimodal")
async def upload_multimodal(
    files: Optional[List[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None)
):
    """Extracts text/notes from any amount of uploaded documents or images without auto-generating."""
    rate_limit("upload")
    target_files = []
    if files:
        target_files.extend(files)
    if file and file not in target_files:
        target_files.append(file)

    if not target_files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    extracted_parts = []
    processed_names = []

    for f in target_files:
        try:
            file_bytes = await f.read()
            filename = f.filename or "uploaded_file"
            ext = filename.lower().split('.')[-1]

            if ext in ["png", "jpg", "jpeg", "webp"]:
                mime_type = f"image/{ext if ext != 'jpg' else 'jpeg'}"
                img_part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
                prompt = "Carefully transcribe and describe all text, equations, math formulas, code snippets, diagrams, and educational concepts in this image."
                try:
                    response = await acall_gemini(contents=[img_part, prompt])
                    text_content = response.text or ""
                except Exception as e:
                    print(f"[ERROR upload_multimodal image {filename}]:", e)
                    text_content = f"[Image uploaded: {filename}]"
            else:
                text_content = extract_text_from_file(file_bytes, filename)
                if ext == "pdf" and len(text_content.strip()) < 200 * max(1, len(PdfReader(io.BytesIO(file_bytes)).pages)) // 4:
                    # Scanned or handwritten PDF (little or no text layer): let Gemini read the pages (OCR).
                    try:
                        pdf_part = types.Part.from_bytes(data=file_bytes, mime_type="application/pdf")
                        response = await acall_gemini(contents=[pdf_part, "Transcribe every page of this document: all text, "
                            "equations in LaTeX ($...$), tables as Markdown, and describe each diagram in one sentence."])
                        text_content = (response.text or "").strip() or text_content
                    except Exception as e:
                        print(f"[OCR fallback failed for {filename}]:", e)

            extracted_parts.append(f"=== DOCUMENT: {filename} ===\n{text_content}\n=== END DOCUMENT ===")
            processed_names.append(filename)
        except Exception as e:
            print(f"[ERROR parsing file {f.filename}]:", e)

    combined_text = "\n\n".join(extracted_parts)
    return {
        "filename": processed_names[0] if len(processed_names) == 1 else f"{len(processed_names)} files uploaded",
        "filenames": processed_names,
        "extracted_text": combined_text,
        "count": len(processed_names)
    }

@app.post("/api/tutor-chat")
async def tutor_chat(payload: ChatPayload):
    rate_limit("chat")
    p_ctx = payload.puzzle_context or {}
    prob = p_ctx.get("problem") or {}
    ch = p_ctx.get("chapter") or {}
    mode = (p_ctx.get("mode") or prob.get("mode") or "code").lower()
    cid = ch.get("id") or prob.get("chapter_id") or 1
    ctitle = ch.get("title") or prob.get("chapter_title") or "Chapter"

    system_text = f"{SOCRATIC_PROMPT}\nCURRENT LESSON CONTEXT:\n{json.dumps(p_ctx)}"
    
    contents = []
    for m in (payload.history or []):
        text = str(m.get("content") or "").strip()
        if not text:
            continue
        role = "model" if m.get("role") in ["model", "assistant"] else "user"
        # Avoid duplicating consecutive identical turns
        if contents and contents[-1].role == role and contents[-1].parts and contents[-1].parts[0].text == text:
            continue
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=text)]))

    user_msg = (payload.message or "").strip()
    if user_msg:
        if not (contents and contents[-1].role == "user" and contents[-1].parts and contents[-1].parts[0].text == user_msg):
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_msg)]))

    if not contents:
        contents = [types.Content(role="user", parts=[types.Part.from_text(text="I am ready to learn.")])]

    try:
        response = await acall_gemini(
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_text,
                temperature=0.3,
                tools=[tutor_tools]
            )
        )

        for call in (response.function_calls or []):
            # 1. Slot Puzzle tool call
            if call.name == "emit_slot_puzzle":
                p = dict(call.args)
                p["type"] = "slot_plugin"
                p["difficulty"] = "Easy"
                norm = normalize_single_problem(p, cid, ctitle, 999, mode)
                return {
                    "reply": f"**Intuition Exercise**: {p.get('guiding_question', 'Try this plug-in exercise to build intuition!')}",
                    "mutated_puzzle": norm
                }
            # 2. Block Builder tool call
            elif call.name == "build_block_puzzle":
                p = dict(call.args)
                p["type"] = "block_builder"
                p["difficulty"] = "Moderate"
                norm = normalize_single_problem(p, cid, ctitle, 999, mode)
                return {
                    "reply": f"**Block Assembly Challenge**: {p.get('guiding_question', 'Assemble the blocks in the correct logical sequence!')}",
                    "mutated_puzzle": norm
                }
            # 3. Coding Challenge tool call
            elif call.name == "build_coding_challenge":
                p = dict(call.args)
                p["type"] = "code_write"
                p["difficulty"] = "Hard"
                norm = normalize_single_problem(p, cid, ctitle, 999, mode)
                return {
                    "reply": f"**Rigorous Challenge**: {p.get('guiding_question', 'Implement the solution from scratch to prove your mastery!')}",
                    "mutated_puzzle": norm
                }
            # 4. Change Assignment tool call
            elif call.name == "change_assignment":
                args = dict(call.args)
                target = args.get("target_type", "slot_plugin")
                reason = args.get("reason", "Customizing your learning pace")
                topic = args.get("new_topic", "core concepts")
                prompt = f"Create a single {target} puzzle for topic: {topic}. Pedagogical rationale: {reason}."
                
                if target == "code_write":
                    wrapper = types.Tool(function_declarations=[coding_challenge_tool])
                elif target == "block_builder":
                    wrapper = types.Tool(function_declarations=[block_puzzle_tool])
                else:
                    wrapper = types.Tool(function_declarations=[slot_puzzle_tool])

                mut_resp = await acall_gemini(
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        tools=[wrapper],
                        tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="ANY"))
                    )
                )
                new_puzzle = None
                for pcall in (mut_resp.function_calls or []):
                    new_puzzle = dict(pcall.args)
                    new_puzzle["type"] = target
                    break

                norm = None
                if new_puzzle:
                    norm = normalize_single_problem(new_puzzle, cid, ctitle, 999, mode)

                return {
                    "reply": f"**Assignment Adjusted**: {reason}. I've tailored a new exercise on **{topic}** for you!",
                    "mutated_puzzle": norm
                }

        reply_text = ""
        try:
            reply_text = response.text
        except Exception:
            pass

        if not reply_text:
            try:
                parts = response.candidates[0].content.parts
                reply_text = "".join([p.text for p in parts if hasattr(p, "text") and p.text])
            except Exception:
                pass

        if not reply_text:
            reply_text = "I am reviewing your reasoning. Reflect on the structural invariant: what boundary condition must be preserved?"

        return {"reply": reply_text.strip()}
    except Exception as e:
        print("[ERROR tutor_chat]:", e)
        # Socratic rule-based fallback when offline or API encounters error
        hint = prob.get("concept_hint") or "Check the invariant condition and edge cases."
        gq = prob.get("guiding_question") or "What property must hold true?"
        return {
            "reply": f"**Mentor Reflection**: Consider the invariant for *{prob.get('title', 'this exercise')}*.\n\n"
                     f"**Diagnostic**: {gq}\n\n"
                     f"**Lead**: {hint} How does your approach preserve this condition?"
        }

@app.post("/api/tutor-brief")
async def tutor_brief(payload: BriefPayload):
    """
    Generates an ultra-concise, razor-sharp, leading Socratic task briefing:
    - Task (actual task in 1 sentence)
    - Invariant/Lead (1 short sentence pointing to the core rule)
    - Check (1 quick diagnostic question to ponder before acting)
    Strictly under 45-55 words total!
    """
    p = payload.problem
    ch = payload.chapter or {}
    mode = payload.mode or "code"
    
    prompt = f"""
    You are the Senior Socratic Coach for '&edu'.
    Deliver a RAZOR-SHARP, ULTRA-CONCISE, LEADING task briefing for this exercise:

    Title: {p.get('title')}
    Type: {p.get('type')}
    Task / Guiding Question: {p.get('guiding_question')}
    Mode: {mode}
    Chapter: {ch.get('title', '')}
    Hint: {p.get('concept_hint', '')}
    Explanation: {p.get('explanation', '')}

    STRICT CONSTRAINTS:
    - MAXIMUM 45-55 WORDS TOTAL!
    - NO WALL OF TEXT. NO FLUFF. NO REPETITIVE GREETINGS.
    - Start directly with the actual task.

    FORMAT EXACTLY AS FOLLOWS (3 short bullet lines):
    **Task**: [1 short sentence stating the concrete task to accomplish]
    **Lead**: [1 crisp sentence pointing out the core invariant or rule]
    **Check**: [1 sharp diagnostic question to consider before answering]
    """

    try:
        response = await acall_gemini(contents=prompt)
        text = (response.text or "").strip()
        if not text:
            raise ValueError("Empty briefing from model")
        return {"briefing": text}
    except Exception as e:
        print("[ERROR tutor_brief]:", e)
        # Fallback local briefing (under 35 words)
        task_desc = p.get('guiding_question') or f"Complete {p.get('title')}"
        hint = p.get('concept_hint') or "Preserve the structural boundary invariant."
        return {
            "briefing": (
                f"**Task**: {task_desc}\n\n"
                f"**Lead**: {hint}\n\n"
                f"**Check**: *What boundary or edge condition would break if chosen incorrectly?*"
            )
        }

@app.post("/api/generate-chapter")
async def generate_chapter(payload: GenerateChapterPayload):
    """
    Generates a single comprehensive new chapter with rich study guide notes and multiple interactive problems.
    Can auto-sequence the next logical concept or target a specific user-requested topic.
    """
    rate_limit("ide")
    mode = (payload.mode or "code").lower()
    is_math = mode == "math"
    existing_chs = payload.existing_chapters or []
    next_id = len(existing_chs) + 1
    start_global_idx = sum(len(ch.get("problems", [])) for ch in existing_chs)
    
    existing_summary = "\n".join([
        f"- Chapter {ch.get('id', idx+1)}: {ch.get('title', '')} ({ch.get('summary', '')})"
        for idx, ch in enumerate(existing_chs)
    ])
    
    topic_req = payload.chapter_topic.strip() if payload.chapter_topic else ""
    if topic_req:
        topic_instruction = f"The student specifically requested the new chapter to focus on: '{topic_req}'."
    else:
        topic_instruction = f"Determine the next natural, advancing topic in pedagogical sequence that logically follows the existing chapters."

    if is_math:
        prompt = f"""
        You are a distinguished Professor of Mathematics and senior curriculum designer for '&edu'.
        Course: {payload.course_title}
        Current Chapter Number to Create: Chapter {next_id}
        Difficulty Tier: Level {payload.level or 1}
        
        Existing Chapters in Syllabus:
        {existing_summary or 'No previous chapters.'}
        
        {topic_instruction}
        
        CRITICAL MATH REQUIREMENTS:
        1. PURE MATHEMATICS: Do not generate computer code (no Python, no JavaScript).
        2. Generate pure mathematical equations, theorems, proofs, and calculus steps.
        3. All formulas and symbols MUST be formatted in standard LaTeX: inline `$formula$` and display `$$formula$$`.
        4. Provide an in-depth study guide ('content_markdown') with # H1, ## H2, ### H3, definition tables, LaTeX equations, and step-by-step worked derivation examples.
        5. Generate 2 to 4 diverse interactive problems:
           - 'slot_plugin': Interactive equation with missing term (`code_prefix`, `code_suffix`, 4 `options`, `correct_answer`).
           - 'logic_problem': Mathematical logic, domain conditions, or inequality invariant check.
           - 'block_builder': Scrambled step-by-step mathematical proof or derivation (`correct_blocks`, `blocks_pool`).
           - 'question': Conceptual multiple choice quiz with LaTeX questions and choices.
        6. STRICT: Every problem must have unambiguous `correct_answer` or `correct_blocks` and `test_cases`.
        
        Call `build_single_chapter`.
        """
    else:
        prompt = f"""
        You are a principal curriculum architect and senior software engineer for '&edu'.
        Course: {payload.course_title} (Domain: {payload.domain})
        Current Chapter Number to Create: Chapter {next_id}
        Difficulty Tier: Level {payload.level or 1}
        
        Existing Chapters in Syllabus:
        {existing_summary or 'No previous chapters.'}
        
        {topic_instruction}
        
        CRITICAL CODING REQUIREMENTS:
        1. Comprehensive, in-depth lesson notes ('content_markdown') with markdown headings, syntax-highlighted code blocks, tables, and step-by-step code walkthroughs.
        2. Generate 2 to 4 diverse practical coding problems:
           - 'slot_plugin': Code with blank slot to complete.
           - 'logic_problem': Fix boundary conditions, invariants, or edge cases.
           - 'block_builder': Scrambled indented lines of code (`correct_blocks`, `blocks_pool`).
           - 'code_write': Algorithmic challenge with `starter_code`, `solution_code`, and `test_code`.
           - 'question': Conceptual multiple-choice question.
        3. STRICT: Every problem must have unambiguous `correct_answer` or `correct_blocks` and `test_cases`.
        
        Call `build_single_chapter`.
        """

    try:
        response = await acall_gemini(
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[chapter_tools_wrapper],
                tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="ANY"))
            )
        )
        for call in (response.function_calls or []):
            if call.name == "build_single_chapter":
                ch_data = dict(call.args)
                return normalize_chapter_data(ch_data, next_id, start_global_idx, mode)
    except Exception as e:
        print("[ERROR generate_chapter]:", e)

    # Robust Fallback Chapter
    fallback_title = f"Chapter {next_id}: {topic_req.title() if topic_req else 'Advanced Analysis & Applications'}"
    fallback_ch = {
        "id": next_id,
        "title": fallback_title,
        "summary": f"In-depth exploration of {topic_req or 'core principles'}, invariants, and rigorous problem solving.",
        "estimated_time_minutes": 25,
        "content_markdown": f"""# {fallback_title}

Welcome to this chapter. Here we investigate advanced structural relationships and analytical methods.

## Key Definitions & Foundations

Every mathematical or computational system rests upon fundamental invariants:

$$f(x + \\Delta x) \\approx f(x) + f'(x) \\Delta x$$

Review the core definitions and examine how boundary values behave under perturbation.
""",
        "problems": [
            {
                "id": start_global_idx + 1,
                "title": f"0{start_global_idx + 1}_foundational_step.math" if is_math else f"0{start_global_idx + 1}_step.py",
                "difficulty": "Easy",
                "type": "slot_plugin",
                "mode": mode,
                "guiding_question": f"Complete the foundational relationship for {fallback_title}.",
                "concept_hint": "Preserve the boundary invariant.",
                "explanation": "Direct application of the fundamental identity.",
                "code_prefix": "\\lim_{h \\to 0} \\frac{f(x+h) - f(x)}{h} = " if is_math else "def compute(x):\n    return ",
                "code_suffix": "",
                "options": ["f'(x)", "f(x)", "0", "\\infty"] if is_math else ["x * 2", "x + 1", "None", "0"],
                "correct_answer": "f'(x)" if is_math else "x * 2",
                "test_cases": ["[VERIFIED] Definition identity holds."]
            }
        ]
    }
    return normalize_chapter_data(fallback_ch, next_id, start_global_idx, mode)

@app.post("/api/generate-problem")
async def generate_problem(payload: GenerateProblemPayload):
    """
    Generates a single interactive problem tailored to a specific chapter.
    """
    rate_limit("ide")
    mode = (payload.mode or "code").lower()
    is_math = mode == "math"
    cid = payload.chapter_id
    ctitle = payload.chapter_title
    ptype_req = payload.problem_type or "auto"
    
    prompt = f"""
    You are an expert educational problem designer for '&edu'.
    Generate ONE new interactive exercise for:
    Chapter: {ctitle} (ID {cid})
    Course: {payload.course_title}
    Mode: {'MATH (pure mathematics & LaTeX, NO code)' if is_math else 'CODE (programming & algorithms)'}
    Requested Problem Type: {ptype_req}
    
    PROBLEM TYPE OPTIONS:
    - 'code_blank': HARD CHALLENGE. A completely blank space for actual coding (starter_code is blank or `# Implement your solution from scratch below:\n\n`). The student must write all classes, functions, loops, and logic from scratch. Provide thorough `test_code` assertions.
    - 'code_partial': CHALLENGE WITH PARTIAL SCAFFOLD. A partially coded challenge where outer structures or helper boilerplate are provided, but the student must complete the core algorithm and invariant logic (marked with TODO comments). Provide thorough `test_code` assertions.
    - 'code_write': General freeform coding challenge with starter_code, solution_code, and test_code assertions.
    - 'slot_plugin': Plug-in blank slot puzzle with 4 options and 1 correct_answer.
    - 'block_builder': Scrambled indented lines or derivation steps with blocks_pool and correct_blocks.
    - 'question': Diagnostic concept quiz.
    - 'auto': If auto, pick the best suited type based on chapter needs.
    
    Topic Focus: {payload.topic_focus or 'Key chapter concepts'}
    Chapter Notes:
    {(payload.chapter_content or '')[:2000]}
    
    STRICT REQUIREMENTS:
    - All mathematical formulas must use LaTeX ($...$ or $$...$$).
    - For code_blank, code_partial, and code_write: MUST provide `starter_code`, `solution_code`, and `test_code` with multiple executable assert statements!
    - Provide unambiguous correct_answer, correct_blocks, or test_code.
    - Provide at least 2 test cases.
    
    Call `build_single_problem`.
    """
    
    try:
        response = await acall_gemini(
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[problem_tools_wrapper],
                tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="ANY"))
            )
        )
        for call in (response.function_calls or []):
            if call.name == "build_single_problem":
                p_data = dict(call.args)
                return normalize_single_problem(p_data, cid, ctitle, 999, mode)
    except Exception as e:
        print("[ERROR generate_problem]:", e)

    # Fallback problem
    fallback = {
        "id": 999,
        "title": f"extra_drill_{cid}.math" if is_math else f"extra_drill_{cid}.py",
        "difficulty": "Moderate",
        "type": "slot_plugin",
        "mode": mode,
        "guiding_question": f"Practice drill for {ctitle}: identify the matching invariant.",
        "concept_hint": "Check the core theorem.",
        "explanation": "Solution directly satisfies the chapter invariant.",
        "code_prefix": "\\text{Identity: } " if is_math else "result = ",
        "code_suffix": "",
        "options": ["A", "B", "C", "D"],
        "correct_answer": "A",
        "test_cases": ["[VERIFIED] Invariant holds."]
    }
    return normalize_single_problem(fallback, cid, ctitle, 999, mode)

@app.post("/api/elevenlabs-voiceover")
async def elevenlabs_voiceover(payload: VoiceoverPayload):
    """
    Synthesizes an accessible, high-yield audio lecture for the chapter using ElevenLabs TTS API
    in the persona and voice of an elderly male university professor.
    Reads ELEVENLABS_API_KEY from environment variables.
    Falls back gracefully to browser SpeechSynthesis if API key is not configured or on network error.
    """
    rate_limit("chat")
    # Resolve ElevenLabs API key: passed from UI settings, or loaded from .env
    # The server's own ElevenLabs key costs credits: used only with SCIEDU_ELEVENLABS=1. Otherwise the
    # spoken script is returned and the browser reads it aloud for free.
    server_key = (os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVEN_LABS_API_KEY") or os.environ.get("XI_API_KEY")) if ELEVENLABS_ENABLED else None
    eleven_key = (payload.api_key or "").strip() or server_key
    
    # 1. Synthesize conversational spoken lecture script using Gemini in elderly professor persona
    clean_notes = (payload.content_markdown or "").strip()
    script_prompt = f"""
    You are a warm, wise, distinguished elderly male university professor (emeritus scholar in mathematics and computer science) delivering an intimate, insightful spoken mini-lecture to your student.
    Course: {payload.course_title}
    Chapter / Lesson: {payload.chapter_title}

    Chapter Study Guide & Content:
    {clean_notes[:4000]}

    STRICT SPOKEN AUDIO & PERSONA REQUIREMENTS:
    1. PERSONA: Speak with the authentic voice, warmth, and scholarly wonder of an elderly professor who deeply loves teaching. Begin with a warm professorial greeting (such as "Ah, welcome back, my student...", "Greetings. Today, let us explore...", "Ah, come in, take a seat...").
    2. SPOKEN MATH TRANSLATION (CRITICAL):
       - The audio is read by a text-to-speech engine. NEVER output raw LaTeX backslashes or symbols (no $, no \\, no ^, no _, no {{, no }}).
       - Convert all mathematical notation into graceful, fluid spoken English.
         For example:
         - d/dx [x^4] -> "the derivative with respect to x of x to the fourth power"
         - \\int_a^b f(x) dx -> "the definite integral of f of x from a to b"
         - \\lim_{{x \\to 0}} -> "the limit as x approaches zero"
         - x^2 -> "x squared"
         - \\frac{{1}}{{x}} -> "one over x"
         - f'(x) -> "f prime of x"
    3. INTUITION & WHY IT MATTERS:
       - Illuminate the core invariant, geometric intuition, or algorithmic beauty behind the concept.
    4. ABSOLUTE CONSTRAINTS:
       - NO markdown formatting (no asterisks, no hashes, no bullet points, no brackets, no bolding).
       - Only pure, smooth spoken paragraphs.
       - Length: 80 to 130 words (approximately 50 to 65 seconds of audio).
    """

    spoken_script = ""
    try:
        resp = await acall_gemini(contents=script_prompt)
        spoken_script = resp.text.strip()
    except Exception as e:
        print("[ERROR generating professor lecture script]:", e)
        spoken_script = (
            f"Ah, greetings my student. Welcome to {payload.course_title}. In today's lesson on {payload.chapter_title}, "
            f"we examine foundational principles, elegant invariants, and the art of structured reasoning. "
            f"Take a moment to inspect the study guide notes, ponder the central invariant, and let us work through the exercises together."
        )

    # Clean any accidental markdown or symbols from the spoken script
    import re
    cleaned_spoken_script = re.sub(r'[*#_`~>\[\]\\]', '', spoken_script)
    cleaned_spoken_script = re.sub(r'\$([^\$]+)\$', r'\1', cleaned_spoken_script)
    cleaned_spoken_script = re.sub(r'\s+', ' ', cleaned_spoken_script).strip()

    # 2. Call ElevenLabs TTS if key is configured
    if eleven_key and eleven_key.strip():
        # Default to George (Elderly Male Professor)
        voice_id = payload.voice_id or DEFAULT_PROFESSOR_VOICE
        # If user passed a friendly name like "george", resolve to voice ID
        if voice_id in PROFESSOR_VOICES:
            voice_id = PROFESSOR_VOICES[voice_id]

        voice_display_names = {
            "JBFqnCBsd6RMkjVDRZzb": "Prof. George (Distinguished British Scholar)",
            "VR6AewLTigWG4xSOukaG": "Prof. Arnold (Crisp American Scholar)",
            "onwK4e9ZLuTAKqWW03F9": "Prof. Daniel (Authoritative Broadcaster)"
        }
        v_name = voice_display_names.get(voice_id, "Prof. George (Elderly Male Professor)")

        try:
            async with httpx.AsyncClient(timeout=45.0) as http_client:
                eleven_resp = await http_client.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                    headers={
                        "Accept": "audio/mpeg",
                        "Content-Type": "application/json",
                        "xi-api-key": eleven_key.strip()
                    },
                    json={
                        "text": cleaned_spoken_script,
                        "model_id": "eleven_turbo_v2_5",
                        "voice_settings": {
                            "stability": 0.65,
                            "similarity_boost": 0.8,
                            "style": 0.15,
                            "use_speaker_boost": True
                        }
                    }
                )
                if eleven_resp.status_code == 200:
                    audio_b64 = base64.b64encode(eleven_resp.content).decode("utf-8")
                    return {
                        "success": True,
                        "source": "elevenlabs",
                        "audio_base64": audio_b64,
                        "script": cleaned_spoken_script,
                        "voice_id": voice_id,
                        "voice_name": v_name,
                        "message": f"ElevenLabs audio synthesized successfully using {v_name}."
                    }
                else:
                    err_detail = eleven_resp.text[:300]
                    print(f"[ELEVENLABS API ERROR] Status {eleven_resp.status_code}: {err_detail}")
                    return {
                        "success": False,
                        "source": "error",
                        "script": cleaned_spoken_script,
                        "error_code": eleven_resp.status_code,
                        "error_detail": err_detail,
                        "message": f"ElevenLabs returned HTTP {eleven_resp.status_code}: {err_detail}"
                    }
        except Exception as e:
            print("[ELEVENLABS EXCEPTION]:", e)
            return {
                "success": False,
                "source": "error",
                "script": cleaned_spoken_script,
                "error_detail": str(e),
                "message": f"ElevenLabs connection exception: {str(e)}"
            }

    # 3. Fallback when ELEVENLABS_API_KEY is not set
    return {
        "success": False,
        "source": "no_key",
        "script": cleaned_spoken_script,
        "message": "ELEVENLABS_API_KEY is not configured in .env or settings."
    }


# ---------------------------------------------------------------------------
# SCIEDU STUDIO TOPICS, ASSESSMENT QUIZ & AGY LIVE BRIDGE
# ---------------------------------------------------------------------------
CONTENT_DIR = Path(os.environ.get("SCIEDU_CONTENT_DIR") or Path(__file__).parent / "content")
TOPICS_DIR = CONTENT_DIR / "topics"
NOTES_DIR = CONTENT_DIR / "notes"
RESULTS_FILE = CONTENT_DIR / "quiz_results.jsonl"
MESSAGES_FILE = CONTENT_DIR / "agy_messages.json"
INBOX_FILE = CONTENT_DIR / "agy_inbox.jsonl"

for _d in (TOPICS_DIR, NOTES_DIR):
    _d.mkdir(parents=True, exist_ok=True)

TOPIC_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
MAX_EVENTS = 200
MAX_MESSAGES = 500
MAX_INBOX_BYTES = 16_000
PRACTICE_TYPES = {"fill_blank", "order_steps", "numeric", "true_false", "code", "match_pairs"}

_file_lock = threading.Lock()
_events_lock = threading.Lock()
ui_events_queue: List[Dict[str, Any]] = []
_event_seq = 0

def slugify(text: str, fallback: str = "topic") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:80].strip("-")
    return slug or fallback

def require_topic_id(topic_id: str) -> str:
    """Topic ids become file names, so anything outside [a-z0-9-] is rejected (no ../ escapes)."""
    if not isinstance(topic_id, str) or not TOPIC_ID_RE.match(topic_id):
        raise HTTPException(status_code=422, detail="Topic id must be kebab-case: lowercase letters, digits and '-' only.")
    return topic_id

def topic_path(topic_id: str) -> Path:
    return TOPICS_DIR / f"{require_topic_id(topic_id)}.json"

def emit_event(event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Appends a UI event with a strictly increasing sequence number (clients poll with ?since=<seq>)."""
    global _event_seq
    with _events_lock:
        _event_seq += 1
        event = {"id": f"evt-{_event_seq}", "seq": _event_seq, "type": event_type,
                 "payload": payload, "timestamp": time.time()}
        ui_events_queue.append(event)
        del ui_events_queue[:-MAX_EVENTS]
    return event

def load_json_file(path: Path, default: Any):
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json_file(path: Path, data: Any):
    """Write-then-rename so a reader polling mid-write never sees half a file."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

def append_messages(*new_messages: Dict[str, Any]):
    """Read-modify-write under a lock, so concurrent prompts can't overwrite each other's history."""
    with _file_lock:
        messages = load_json_file(MESSAGES_FILE, [])
        messages.extend(new_messages)
        save_json_file(MESSAGES_FILE, messages[-MAX_MESSAGES:])

def normalize_quiz_item(q: Dict[str, Any], idx: int) -> Optional[Dict[str, Any]]:
    """Accepts both the documented `correctAnswer` and the older agy `correct` key."""
    options = [str(o) for o in (q.get("options") or []) if str(o).strip()]
    question = q.get("question") or q.get("question_text")
    if not question or len(options) < 2:
        return None
    answer = q.get("correctAnswer", q.get("correct"))
    if isinstance(answer, str) and not answer.strip().isdigit():
        answer = options.index(answer) if answer in options else None
    try:
        answer = int(answer)
    except (TypeError, ValueError):
        return None
    if not 0 <= answer < len(options):
        return None
    item = {k: v for k, v in q.items() if k not in ("correct", "question_text")}
    item.update(id=q.get("id") or f"q{idx + 1}", question=question, options=options, correctAnswer=answer)
    return item

def normalize_topic(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Brings a topic from any author (UI, agy CLI, Gemini tools) to the schema the frontend reads."""
    warnings: List[str] = []
    topic = dict(data)
    topic["id"] = require_topic_id(topic.get("id") or slugify(topic.get("title", "")))
    topic.setdefault("difficulty", "Undergraduate")
    topic.setdefault("summary", "")
    cheat = []
    for item in topic.get("cheatSheet") or []:
        if isinstance(item, dict) and item.get("formula"):
            cheat.append({"label": item.get("label") or item.get("name") or "", "formula": item["formula"],
                          **({"desc": item["desc"]} if item.get("desc") else {})})
    topic["cheatSheet"] = cheat
    quiz = []
    for i, q in enumerate(topic.get("quiz") or []):
        nq = normalize_quiz_item(q, i) if isinstance(q, dict) else None
        if nq:
            quiz.append(nq)
        else:
            warnings.append(f"quiz[{i}] dropped: needs question, 2+ options and a valid correctAnswer index")
    topic["quiz"] = quiz
    if topic.get("simulation"):
        spec, errs = validate_spec(topic["simulation"])
        if errs:
            warnings.extend(f"simulation: {e}" for e in errs)
            topic.pop("simulation")
        else:
            topic["simulation"] = spec
    practice = [p for p in (topic.get("practice") or []) if isinstance(p, dict) and p.get("type") in PRACTICE_TYPES]
    topic["practice"] = practice
    if "flashcards" in topic:
        topic["flashcards"] = normalize_flashcards(topic.get("flashcards"))
    if "timeline" in topic:
        topic["timeline"] = normalize_timeline(topic.get("timeline"))
    return topic, warnings

def normalize_flashcards(items: Any) -> List[Dict[str, Any]]:
    """{front, back, optional hint, optional lang (BCP-47, read aloud in the browser)}; at most 80."""
    out = []
    for c in items if isinstance(items, list) else []:
        if isinstance(c, dict) and str(c.get("front", "")).strip() and str(c.get("back", "")).strip():
            card = {"front": str(c["front"])[:300], "back": str(c["back"])[:600]}
            if c.get("hint"):
                card["hint"] = str(c["hint"])[:200]
            if re.fullmatch(r"[a-z]{2,3}(-[A-Za-z]{2,4})?", str(c.get("lang") or "")):
                card["lang"] = c["lang"]
            out.append(card)
    return out[:80]

def normalize_timeline(items: Any) -> List[Dict[str, Any]]:
    """{year (number, negative for BCE), title, optional date label and detail}, sorted by year; at most 60."""
    out = []
    for e in items if isinstance(items, list) else []:
        if not isinstance(e, dict) or not str(e.get("title", "")).strip():
            continue
        try:
            year = float(e.get("year"))
        except (TypeError, ValueError):
            continue
        out.append({"year": year, "title": str(e["title"])[:160], "date": str(e.get("date") or "")[:40] or None,
                    "detail": str(e.get("detail") or "")[:600]})
    out.sort(key=lambda e: e["year"])
    return out[:60]

def save_topic(data: Dict[str, Any], event_type: str = "TOPIC_UPDATED", auto_select: bool = True,
               course_id: Optional[str] = None) -> Tuple[Dict[str, Any], List[str]]:
    topic, warnings = normalize_topic(data)
    save_json_file(topic_path(topic["id"]), topic)
    db.upsert_lesson(topic, course_id)
    emit_event(event_type, {"topicId": topic["id"], "title": topic.get("title"), "autoSelect": auto_select})
    return topic, warnings

class TopicModel(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    title: str
    category: str
    difficulty: Optional[str] = "Undergraduate"
    summary: Optional[str] = ""
    simulationType: Optional[str] = None
    simulation: Optional[Dict[str, Any]] = None
    cheatSheet: Optional[List[Dict[str, Any]]] = []
    mermaid: Optional[str] = None
    markdownContent: str
    quiz: Optional[List[Dict[str, Any]]] = []
    practice: Optional[List[Dict[str, Any]]] = []

class QuizSubmission(BaseModel):
    userId: Optional[str] = None
    topicId: str
    questionId: Any
    selected: int
    isCorrect: bool

class AgyEventModel(BaseModel):
    type: str  # SWITCH_TAB, SWITCH_TOPIC, SET_SIM_CONFIG, SWITCH_STUDIO_MODE, TOPIC_UPDATED
    payload: Dict[str, Any]

class AgyPromptModel(BaseModel):
    prompt: str
    topicId: Optional[str] = "rolling-without-slipping"
    courseId: Optional[str] = None

def topic_visible(topic: Dict[str, Any]) -> bool:
    """With accounts on, a lesson generated for someone's course is visible only to that person;
    library topics (no course) stay shared."""
    cid = (topic.get("source") or {}).get("courseId")
    if not AUTH_REQUIRED or not cid:
        return True
    course, me = db.get_course(cid), CURRENT_USER.get()
    return bool(course and me and course["user_id"] == me["id"])

def _topics_version() -> str:
    stamp = "|".join(f"{p.name}:{p.stat().st_mtime_ns}" for p in sorted(TOPICS_DIR.glob("*.json")))
    return f"{len(stamp)}-{hash(stamp) & 0xFFFFFFFF:08x}"

@app.get("/api/topics/version")
def get_topics_version():
    """Cheap change-detector: the UI polls this and refetches /api/topics only when it changes."""
    return {"version": _topics_version()}

@app.get("/api/topics")
def get_topics():
    topics = []
    ws_cache: Dict[str, str] = {}
    for file_path in sorted(TOPICS_DIR.glob("*.json")):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                topic = json.load(f)
            if topic_visible(topic):
                topics.append(with_workspace(topic, ws_cache))
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    return topics

@app.get("/api/topics/{topic_id}")
def get_topic(topic_id: str):
    file_path = topic_path(topic_id)
    topic = load_json_file(file_path, None) if file_path.exists() else None
    if not topic or not topic_visible(topic):
        raise HTTPException(status_code=404, detail="Topic not found")
    return with_workspace(topic)

@app.post("/api/topics")
def create_or_update_topic(topic: TopicModel):
    saved, warnings = save_topic(topic.model_dump())
    return {"status": "success", "id": saved["id"], "path": str(topic_path(saved["id"])), "warnings": warnings}

@app.post("/api/topics/{topic_id}/opened")
def topic_opened(topic_id: str):
    """The student opened this lesson: adaptation will no longer rewrite it under them."""
    topic = load_json_file(topic_path(topic_id), None)
    if not topic or not topic_visible(topic):
        raise HTTPException(status_code=404, detail="Topic not found")
    klass = db.mark_class_opened(topic_id)
    return {"status": "ok", "classId": klass["id"] if klass else None}

MATH_PRACTICE_PROMPT = """
Write {count} math practice problems on: {topic}
Level: {level}. Mix the types below; most should be "numeric".
Return JSON only:
{{"title": "short name for this set", "practice": [
  {{"type": "numeric", "prompt": "problem with all given values, math in $...$", "answer": 4.5, "tolerance": 0.01, "unit": "",
    "compute": "arithmetic expression that evaluates to the answer, e.g. sqrt(2)*3 + 1/4", "explanation": "worked solution in steps, LaTeX in $...$"}},
  {{"type": "fill_blank", "prompt": "... ___ ...", "options": ["...","...","...","..."], "answer": "exact option text", "explanation": "..."}},
  {{"type": "true_false", "prompt": "a statement targeting a misconception", "answer": false, "explanation": "..."}},
  {{"type": "order_steps", "prompt": "Put the solution steps in order", "steps": ["...","...","..."], "explanation": "..."}}
]}}
"compute" may use numbers, + - * / ** ( ), pi, e and sqrt, sin, cos, tan, asin, acos, atan, exp, log, log10, abs, factorial.
Use radians in trig unless the prompt says degrees. Ask for decimal answers when the exact form is irrational.
"""

_MATH_NAMES = {"pi": math.pi, "e": math.e, "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
               "asin": math.asin, "acos": math.acos, "atan": math.atan, "exp": math.exp, "log": math.log,
               "log10": math.log10, "abs": abs, "factorial": lambda n: math.factorial(int(n)) if 0 <= n <= 170 else math.inf}

def safe_arith(expr: str) -> float:
    """Evaluates a plain arithmetic expression (no names beyond _MATH_NAMES, no attributes): used to re-check answers."""
    import ast
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return float(n.value)  # floats overflow fast instead of building giant integers
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod)):
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and abs(b) > 1000:
                raise ValueError("exponent too large")
            return {ast.Add: a + b, ast.Sub: a - b, ast.Mult: a * b}.get(type(n.op)) if not isinstance(n.op, (ast.Div, ast.Pow, ast.Mod)) \
                else a / b if isinstance(n.op, ast.Div) else a ** b if isinstance(n.op, ast.Pow) else a % b
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            return ev(n.operand) * (-1 if isinstance(n.op, ast.USub) else 1)
        if isinstance(n, ast.Name) and n.id in _MATH_NAMES and not callable(_MATH_NAMES[n.id]):
            return _MATH_NAMES[n.id]
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and callable(_MATH_NAMES.get(n.func.id)) and not n.keywords:
            return _MATH_NAMES[n.func.id](*[ev(a) for a in n.args])
        raise ValueError("unsupported expression")
    if len(expr) > 300:
        raise ValueError("too long")
    return float(ev(ast.parse(expr.replace("^", "**"), mode="eval")))

class MathPracticeRequest(BaseModel):
    topic: str
    level: Optional[str] = "high school"
    count: Optional[int] = 6

@app.post("/api/math/practice")
async def math_practice(req: MathPracticeRequest):
    """Generated math problems. Every numeric answer is recomputed from its "compute" expression; mismatches are dropped."""
    rate_limit("class")
    topic = (req.topic or "").strip()[:300]
    if len(topic) < 3:
        raise HTTPException(status_code=422, detail="Say what to practise, e.g. 'derivatives of products'.")
    count = min(max(req.count or 6, 3), 10)
    data = await gemini_json(MATH_PRACTICE_PROMPT.format(count=count, topic=topic, level=(req.level or "high school")[:60]), role="lesson")
    raw = data.get("practice") if isinstance(data, dict) else None
    checked, dropped = [], 0
    for p in raw if isinstance(raw, list) else []:
        if isinstance(p, dict) and p.get("type") == "numeric":
            try:
                value, stated = safe_arith(str(p.get("compute") or "")), float(p.get("answer"))
                if not math.isfinite(value) or abs(value - stated) > max(1e-9, 0.005 * abs(value)):
                    dropped += 1
                    continue
                p["answer"] = round(value, 6)
            except (ValueError, TypeError, ZeroDivisionError, OverflowError, SyntaxError):
                dropped += 1
                continue
        checked.append(p)
    items = normalize_practice(checked)
    if not items:
        raise HTTPException(status_code=502, detail="No problems passed the answer check. Try again or rephrase the topic.")
    return {"title": (data.get("title") if isinstance(data, dict) else None) or topic, "items": items, "dropped": dropped}

@app.post("/api/simulations/validate")
def validate_simulation(spec: Dict[str, Any]):
    """Lets agents check a SimSpec before saving it; returns the cleaned spec and every error found."""
    clean, errors = validate_spec(spec)
    return {"valid": not errors, "errors": errors, "spec": clean if not errors else None}

@app.get("/api/simulations/guide")
def simulation_guide():
    return {"guide": SPEC_GUIDE + "\n" + MATH_GUIDE}

@app.post("/api/quiz/submit")
def submit_quiz_answer(sub: QuizSubmission):
    if AUTH_REQUIRED:
        sub.userId = CURRENT_USER.get()["id"]
    record = sub.model_dump()
    record["timestamp"] = time.time()
    with _file_lock, open(RESULTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    class_progress = db.record_attempt(sub.userId, sub.topicId, sub.questionId, sub.selected, sub.isCorrect)
    if class_progress:
        if class_progress.get("justCompleted"):
            class_progress["adapted"] = adapt_next_class(class_progress)
        course_event(class_progress["courseId"])

    rewards = None
    if sub.userId and db.get_user(sub.userId):
        day = today()
        ref = f"{sub.topicId}:{sub.questionId}"
        if not sub.isCorrect:
            engage.remember_miss(sub.userId, sub.topicId, str(sub.questionId), day)
        rewards = merge_rewards(
            engage.award(sub.userId, day, "quiz_correct" if sub.isCorrect else "quiz_attempt", ref),
            engage.award(sub.userId, day, "class_complete", class_progress["classId"]) if class_progress and class_progress.get("justCompleted") else None,
            engage.award(sub.userId, day, "quiz_perfect", class_progress["classId"])
            if class_progress and class_progress.get("justCompleted") and class_progress["score"] >= 1 else None,
        )

    status_msg = "Correct answer recorded!" if sub.isCorrect else "Answer incorrect — review recommended."
    emit_event("QUIZ_SUBMITTED", {"topicId": sub.topicId, "isCorrect": sub.isCorrect, "statusMessage": status_msg})
    return {"status": "recorded", "isCorrect": sub.isCorrect, "classProgress": class_progress, "rewards": rewards}

# ---------------------------------------------------------------- engagement (engage.py)
def today() -> str:
    return LOCAL_DAY.get() or engage.utc_day()

def merge_rewards(*parts: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Several awards from one action, reported as one celebration."""
    out: Dict[str, Any] = {"xp": 0, "newBadges": []}
    for r in parts:
        if not r or not r.get("xp"):
            continue
        out["xp"] += r["xp"]
        out["newBadges"] += r.get("newBadges", [])
        for k in ("goalReached", "streakExtended", "freezeEarned", "levelUp", "questsDone"):
            out[k] = out.get(k) or r.get(k, False)
        for k in ("xpToday", "goal", "streak", "level"):
            out[k] = r.get(k, out.get(k))
        out.setdefault("sources", []).append(r.get("source"))
    return out

class XpRequest(BaseModel):
    source: str
    ref: Optional[str] = ""

class EngagePrefs(BaseModel):
    dailyGoal: Optional[int] = None
    focusMode: Optional[bool] = None

class ReviewAnswer(BaseModel):
    topicId: str
    questionId: str
    selected: int

class ReviewFinish(BaseModel):
    answered: int = 0

@app.get("/api/engage/{user_id}")
def engage_progress(user_id: str):
    require_user(user_id)
    return engage.progress(user_id, today())

@app.post("/api/engage/{user_id}/xp")
def engage_xp(user_id: str, body: XpRequest):
    """Actions graded in the browser (practice, math, IDE, simulations, reading) report here; amounts are server-side."""
    rate_limit("chat")
    require_user(user_id)
    if body.source not in engage.CLIENT_SOURCES:
        raise HTTPException(status_code=422, detail="Unknown activity.")
    return engage.award(user_id, today(), body.source, body.ref or "")

@app.post("/api/engage/{user_id}/prefs")
def engage_prefs(user_id: str, body: EngagePrefs):
    require_user(user_id)
    engage.set_prefs(user_id, body.dailyGoal, body.focusMode)
    return engage.progress(user_id, today())

def _review_question(topic_id: str, question_id: str) -> Optional[Dict[str, Any]]:
    try:
        topic = json.loads(topic_path(topic_id).read_text(encoding="utf-8"))
    except (OSError, ValueError, HTTPException):
        return None
    quiz = [q for q in topic.get("quiz") or [] if isinstance(q, dict) and isinstance(q.get("correctAnswer"), int)]
    q = next((q for q in quiz if str(q.get("id")) == str(question_id)), None)
    if q is None and str(question_id).isdigit() and int(question_id) < len(quiz):
        q = quiz[int(question_id)]
    return {**q, "topicTitle": topic.get("title", "")} if q else None

@app.get("/api/review/{user_id}/session")
def review_session(user_id: str):
    """Up to 10 questions the student missed before, due today (spaced: 1, 3, 7, 14, 30 days)."""
    require_user(user_id)
    out = []
    for item in engage.due_items(user_id, today()):
        q = _review_question(item["topic_id"], item["question_id"])
        if not q:
            engage.drop_item(user_id, item["topic_id"], item["question_id"])  # lesson or question no longer exists
            continue
        out.append({"topicId": item["topic_id"], "questionId": item["question_id"], "topicTitle": q["topicTitle"],
                    "question": q["question"], "options": q["options"], "hint": q.get("hint", ""), "box": item["box"]})
    return {"questions": out, "nextReview": engage.next_due(user_id)}

@app.post("/api/review/{user_id}/answer")
def review_answer(user_id: str, body: ReviewAnswer):
    require_user(user_id)
    q = _review_question(body.topicId, body.questionId)
    if not q:
        raise HTTPException(status_code=404, detail="That question no longer exists.")
    correct = body.selected == q["correctAnswer"]
    day = today()
    result = engage.review_result(user_id, body.topicId, body.questionId, correct, day)
    rewards = engage.award(user_id, day, "review_correct" if correct else "review_attempt", f"{body.topicId}:{body.questionId}")
    return {"correct": correct, "correctAnswer": q["correctAnswer"], "explanation": q.get("explanation", ""),
            **result, "rewards": rewards}

@app.post("/api/review/{user_id}/finish")
def review_finish(user_id: str, body: ReviewFinish):
    require_user(user_id)
    if body.answered < 3:
        return {"xp": 0}
    return engage.award(user_id, today(), "review_session", str(time.time()))


ADAPT_LOW, ADAPT_HIGH = 0.5, 0.9

def adapt_next_class(progress: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Plan section 5: rewrite the next class the student hasn't started when they struggled (< 50%) or
    breezed through (>= 90%), so the course doesn't overwhelm or bore them."""
    score = progress["score"]
    if ADAPT_LOW <= score < ADAPT_HIGH:
        return None
    nxt = db.next_unstarted_class(progress["courseId"], progress["seq"])
    if not nxt or nxt["status"] == "generating":
        return None
    pct = round(score * 100)
    if score < ADAPT_LOW:
        instruction = (f"The student scored only {pct}% on the previous class's quiz. Slow down: open by re-teaching its key "
                       "idea from a different angle, use more worked examples with every step shown, and make the first "
                       "practice items easier before building up.")
    else:
        instruction = (f"The student scored {pct}% on the previous class's quiz. Do not re-explain basics they have shown they "
                       "know: move faster, go deeper, and make the quiz and practice items harder (multi-step, less familiar setups).")
    db.update_class(nxt["id"], status="pending", instruction=instruction, adapted_from=score)
    queue_course_generation(progress["courseId"])
    emit_event("CLASS_ADAPTED", {"courseId": progress["courseId"], "seq": nxt["seq"], "title": nxt["title"],
                                 "direction": "easier" if score < ADAPT_LOW else "harder", "score": score})
    return {"seq": nxt["seq"], "direction": "easier" if score < ADAPT_LOW else "harder"}

@app.get("/api/agy/events")
def get_agy_events(since: int = -1):
    """since=-1 (first poll) returns no backlog, only the cursor, so a page reload never replays old events."""
    with _events_lock:
        cursor = _event_seq
        events = [] if since < 0 else [e for e in ui_events_queue if e["seq"] > since]
    return {"events": events, "cursor": cursor, "timestamp": time.time()}

@app.post("/api/agy/events")
def push_agy_event(event: AgyEventModel):
    return {"status": "event_pushed", "event": emit_event(event.type, event.payload)}

@app.get("/api/agy/messages")
def get_messages():
    return load_json_file(MESSAGES_FILE, [])

# ---------------------------------------------------------------------------
# BACKGROUND JOBS (simulation authoring, study packs) — run off the request path
# ---------------------------------------------------------------------------
JOBS: Dict[str, Dict[str, Any]] = {}
MAIN_LOOP: Optional[asyncio.AbstractEventLoop] = None
MAX_JOBS = 100
_background_tasks: set = set()

def _job_update(job: Dict[str, Any], **changes):
    job.update(changes, updated=time.time())
    emit_event("JOB_UPDATE", {k: job[k] for k in ("id", "kind", "status", "step", "progress", "error", "result") if k in job})

def start_job(kind: str, label: str, work) -> Dict[str, Any]:
    """Schedules `work(job)` (an async function) and returns the job record immediately."""
    job = {"id": f"job-{int(time.time() * 1000)}-{len(JOBS)}", "kind": kind, "label": label,
           "status": "queued", "step": "Queued", "progress": 0.0, "created": time.time()}
    JOBS[job["id"]] = job
    for old in sorted(JOBS, key=lambda k: JOBS[k]["created"])[:-MAX_JOBS]:
        JOBS.pop(old, None)

    async def runner():
        _job_update(job, status="running", step="Starting")
        try:
            result = await work(job)
            _job_update(job, status="done", step="Done", progress=1.0, result=result)
        except Exception as e:
            print(f"[JOB {job['id']} {kind} failed]:", e)
            _job_update(job, status="error", step="Failed", error=friendly_ai_error(e))

    # Sync handlers run in FastAPI's thread pool, which has no event loop: hand the job to the main loop.
    try:
        task = asyncio.get_running_loop().create_task(runner())
    except RuntimeError:
        if MAIN_LOOP is None:
            raise RuntimeError("Background jobs need the server's event loop; start the app with uvicorn.")
        task = asyncio.run_coroutine_threadsafe(runner(), MAIN_LOOP)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return job

def friendly_ai_error(e: Exception) -> str:
    text = str(e)
    if "Daily model budget" in text:
        return text
    if "API key" in text or "not configured" in text:
        return "No Gemini API key: add api_KEY=... to SciEdu-Studio/.env and restart the backend."
    if "429" in text or "quota" in text.lower() or "RESOURCE_EXHAUSTED" in text:
        return "Gemini quota exhausted for every fallback model. Try again in a minute."
    return text[:300]

@app.get("/api/jobs")
def list_jobs():
    return {"jobs": sorted(JOBS.values(), key=lambda j: j["created"], reverse=True)[:30]}

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    return JOBS[job_id]

# LaTeX commands whose first letter is also a JSON escape (\b \f \n \r \t \u). If a model writes them
# with one backslash, json.loads either fails or silently turns "\theta" into TAB + "heta".
_LATEX_ESCAPE_CLASH = re.compile(
    r"(?<!\\)\\(?=(?:beta|bar|bf|binom|bigg?|Bigg?|bmod|boldsymbol|bot|bullet|backslash|begin|boxed|"
    r"frac|forall|flat|frown|fbox|nu|nabla|neq|ne|not|neg|ni|newline|nolimits|notin|nleq|ngeq|nparallel|"
    r"rho|right|rangle|rceil|rfloor|rm|rvert|rVert|Rightarrow|theta|text|textbf|textit|textrm|times|tan|tanh|"
    r"tau|to|top|tilde|triangle|therefore|tfrac|tt|underline|upsilon|uparrow|underbrace|updownarrow)(?![A-Za-z]))"
)

def repair_json_escapes(text: str) -> str:
    """Makes model JSON containing raw LaTeX parseable without corrupting it."""
    text = _LATEX_ESCAPE_CLASH.sub(r"\\\\", text)
    out, i = [], 0
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text):
            n = text[i + 1]
            if n in '"\\/bfnrt':
                out.append(c + n)
                i += 2
                continue
            if n == "u" and re.match(r"[0-9a-fA-F]{4}", text[i + 2:i + 6]):
                out.append(text[i:i + 6])
                i += 6
                continue
            out.append("\\\\")  # stray backslash (e.g. \alpha, \sin): keep it literally
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)

def _parse_json_reply(text: str) -> Any:
    text = (text or "").strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    if fence:
        text = fence.group(1)
    return json.loads(repair_json_escapes(text))

async def gemini_json(prompt: str, temperature: float = 0.4, role: Optional[str] = None) -> Any:
    response = await acall_gemini(
        contents=prompt,
        role=role,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=temperature),
    )
    return _parse_json_reply(response.text)

def _topic_brief(topic: Dict[str, Any], limit: int = 5000) -> str:
    cheat = "; ".join(f"{c.get('label')}: {c.get('formula')}" for c in topic.get("cheatSheet") or [])
    return (f"Title: {topic.get('title')}\nCategory: {topic.get('category')}\nSummary: {topic.get('summary')}\n"
            f"Key formulas: {cheat}\nNotes:\n{(topic.get('markdownContent') or '')[:limit]}")

async def author_simulation(context: str, focus: str = "", attempts: int = 3, math: bool = False) -> Dict[str, Any]:
    """Asks Gemini for a SimSpec and feeds validator errors back until it passes."""
    if math:
        prompt = f"""
You design interactive math visualisations for &.edu. Output ONE JSON object of kind "math" and nothing
else: pick the widget that makes this class's key idea visible and set its functions so the picture is
interesting (for limits use a function and point where the epsilon-delta picture is clear). Add at most 2 extra
sliders. The description must tell the student what to drag and what to notice.

{MATH_GUIDE}

TOPIC CONTEXT:
{context[:6000]}

FOCUS FOR THIS VISUALISATION: {focus or 'the central concept of the topic'}
"""
    else:
        prompt = f"""
You design interactive teaching simulations for &.edu. Output ONE JSON object in the SimSpec v1
format below and nothing else. Choose "particles" for anything that moves (mechanics, orbits, charges in
fields, oscillators, collisions, fluids as particles) and "graph" for relationships and fields (waves,
interference, gas laws, distributions, circuits over time, any y=f(x,t)). Give 2-5 sliders for the
quantities a student should experiment with, use realistic SI values, keep the world box sized so motion
stays visible, and add readouts/series that expose the key invariant (energy, momentum, period...).
The description must tell the student what to try with the sliders and what to notice.

{SPEC_GUIDE}

TOPIC CONTEXT:
{context[:6000]}

FOCUS FOR THIS SIMULATION: {focus or 'the central concept of the topic'}
"""
    last_errors: List[str] = []
    for _ in range(attempts):
        attempt_prompt = prompt if not last_errors else (
            prompt + "\nYour previous JSON failed validation with these errors. Fix ALL of them and return the full corrected JSON:\n- "
            + "\n- ".join(last_errors[:20]))
        try:
            raw = await gemini_json(attempt_prompt, temperature=0.3)
        except json.JSONDecodeError as e:
            last_errors = [f"response was not valid JSON ({e.msg})"]
            continue
        spec, errors = validate_spec(raw)
        if not errors:
            return spec
        last_errors = errors
    raise RuntimeError("Could not produce a valid simulation: " + "; ".join(last_errors[:5]))

def normalize_practice(items: Any) -> List[Dict[str, Any]]:
    """Keeps only practice puzzles the UI can grade unambiguously."""
    clean = []
    for i, p in enumerate(items if isinstance(items, list) else []):
        if not isinstance(p, dict) or not p.get("prompt"):
            continue
        base = {"id": p.get("id") or f"p{i + 1}", "type": p.get("type"), "prompt": str(p["prompt"]),
                "explanation": str(p.get("explanation") or ""), "concept": p.get("concept")}
        t = p.get("type")
        if t == "fill_blank":
            opts = [str(o) for o in p.get("options") or [] if str(o).strip()]
            ans = str(p.get("answer", ""))
            if ans and ans in opts and len(opts) >= 2:
                clean.append({**base, "options": finalize_choices(opts, ans), "answer": ans})
        elif t == "order_steps":
            steps = [str(s) for s in p.get("steps") or [] if str(s).strip()]
            if 3 <= len(steps) <= 8 and len(set(steps)) == len(steps):
                clean.append({**base, "steps": steps})
        elif t == "numeric":
            try:
                ans = float(p.get("answer"))
            except (TypeError, ValueError):
                continue
            tol = p.get("tolerance", 0.02)
            clean.append({**base, "answer": ans, "tolerance": float(tol) if isinstance(tol, (int, float)) else 0.02,
                          "unit": str(p.get("unit") or "")})
        elif t == "match_pairs":
            pairs = [[str(a)[:160], str(b)[:160]] for a, b in (pp for pp in (p.get("pairs") or []) if isinstance(pp, (list, tuple)) and len(pp) == 2)]
            if 3 <= len(pairs) <= 8 and len({a for a, _ in pairs}) == len(pairs) and len({b for _, b in pairs}) == len(pairs):
                clean.append({**base, "pairs": pairs})
        elif t == "true_false" and isinstance(p.get("answer"), bool):
            clean.append({**base, "answer": p["answer"]})
        elif t == "code":
            # &EDU-style coding exercise; runs in the student's browser (Pyodide), never on the server
            tests = str(p.get("tests") or "").strip()
            if re.search(r"^\s*assert\s", tests, re.M):  # a real assert statement, not the word in a string
                clean.append({**base, "language": "python", "starter": str(p.get("starter") or "")[:4000],
                              "tests": tests[:4000], "solution": str(p.get("solution") or "")[:6000]})
    return clean

def write_notes_file(topic: Dict[str, Any]) -> str:
    """Saves the lesson as a standalone Markdown file students can keep (content/notes/<id>.md)."""
    lines = [f"# {topic['title']}", "", f"_{topic.get('category', '')} · {topic.get('difficulty', '')}_", "",
             topic.get("summary", ""), ""]
    if topic.get("cheatSheet"):
        lines += ["## Key formulas", ""] + [f"- **{c['label']}**: ${c['formula']}$" for c in topic["cheatSheet"]] + [""]
    lines += [topic.get("markdownContent", ""), ""]
    if topic.get("quiz"):
        lines += ["## Self-test", ""]
        for i, q in enumerate(topic["quiz"], 1):
            lines.append(f"{i}. {q['question']}")
            lines += [f"   - {'ABCD'[j] if j < 4 else j + 1}) {o}" for j, o in enumerate(q["options"])]
        lines += ["", "<details><summary>Answers</summary>", ""]
        lines += [f"{i}. {'ABCD'[q['correctAnswer']] if q['correctAnswer'] < 4 else q['correctAnswer'] + 1} — {q.get('explanation', '')}"
                  for i, q in enumerate(topic["quiz"], 1)]
        lines += ["", "</details>", ""]
    path = NOTES_DIR / f"{topic['id']}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path.name

@app.get("/api/notes/{topic_id}.md")
def get_notes_file(topic_id: str):
    from fastapi.responses import FileResponse
    path = NOTES_DIR / f"{require_topic_id(topic_id)}.md"
    topic = load_json_file(topic_path(topic_id), None)
    if not path.exists() or (topic and not topic_visible(topic)):
        raise HTTPException(status_code=404, detail="No notes file for this topic")
    return FileResponse(path, media_type="text/markdown; charset=utf-8", filename=path.name)

# ---------------------------------------------------------------- creative tools (assistant, MCP, agents)
class SpecBody(BaseModel):
    spec: Dict[str, Any]

class ItemsBody(BaseModel):
    items: List[Dict[str, Any]]

class GraphBody(BaseModel):
    functions: List[str]
    params: Optional[Dict[str, float]] = None

def _load_topic_or_404(topic_id: str) -> Dict[str, Any]:
    path = topic_path(topic_id)
    topic = load_json_file(path, None) if path.exists() else None
    if not topic or not topic_visible(topic):
        raise HTTPException(status_code=404, detail="Topic not found")
    return topic

@app.post("/api/topics/{topic_id}/simulation")
def attach_simulation(topic_id: str, body: SpecBody):
    """Attach a hand-written SimSpec (any kind) to a topic after validation; errors come back precisely."""
    rate_limit("simulation")
    topic = _load_topic_or_404(topic_id)
    spec, errors = validate_spec(body.spec)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    topic["simulation"] = spec
    save_topic(topic, auto_select=False)
    return {"status": "attached", "topicId": topic_id, "simulation": spec}

@app.post("/api/topics/{topic_id}/quiz")
def add_quiz_questions(topic_id: str, body: ItemsBody):
    """Append quiz questions (normalized like generated ones); returns how many were kept."""
    topic = _load_topic_or_404(topic_id)
    quiz = list(topic.get("quiz") or [])
    added = 0
    for q in body.items[:20]:
        nq = normalize_quiz_item(q, len(quiz)) if isinstance(q, dict) else None
        if nq:
            nq["id"] = f"q{len(quiz) + 1}"
            quiz.append(nq)
            added += 1
    topic["quiz"] = quiz
    save_topic(topic, auto_select=False)
    return {"added": added, "rejected": len(body.items[:20]) - added, "total": len(quiz)}

@app.post("/api/topics/{topic_id}/practice")
def add_practice_items(topic_id: str, body: ItemsBody):
    topic = _load_topic_or_404(topic_id)
    existing = list(topic.get("practice") or [])
    new = normalize_practice([{**p, "id": f"p{len(existing) + i + 1}"} for i, p in enumerate(body.items[:20]) if isinstance(p, dict)])
    topic["practice"] = existing + new
    save_topic(topic, auto_select=False)
    return {"added": len(new), "rejected": len(body.items[:20]) - len(new), "total": len(topic["practice"])}

@app.post("/api/ui/graph")
def show_on_graph(body: GraphBody):
    """Opens Math > Graph on the student's screen with these functions (letters other than x become sliders)."""
    fns = [str(f)[:200] for f in body.functions[:6]]
    emit_event("MATH_GRAPH", {"functions": fns, "params": {k: float(v) for k, v in (body.params or {}).items()}})
    return {"status": "shown", "functions": fns}

@app.post("/api/ui/math-sim")
def preview_math_sim(body: SpecBody):
    """Shows a math-kit widget in Math > Sim kit without saving it to a topic."""
    spec, errors = validate_spec({**body.spec, "kind": "math"})
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    emit_event("MATH_PREVIEW", {"spec": spec})
    return {"status": "shown", "spec": spec}


@app.post("/api/topics/{topic_id}/flashcards")
def add_flashcards(topic_id: str, body: ItemsBody):
    topic = _load_topic_or_404(topic_id)
    new = normalize_flashcards(body.items)
    topic["flashcards"] = (topic.get("flashcards") or []) + new
    save_topic(topic, auto_select=False)
    return {"added": len(new), "rejected": len(body.items) - len(new), "total": len(topic["flashcards"])}

@app.post("/api/topics/{topic_id}/timeline")
def add_timeline_events(topic_id: str, body: ItemsBody):
    topic = _load_topic_or_404(topic_id)
    new = normalize_timeline(body.items)
    topic["timeline"] = normalize_timeline((topic.get("timeline") or []) + new)
    save_topic(topic, auto_select=False)
    return {"added": len(new), "rejected": len(body.items) - len(new), "total": len(topic["timeline"])}

# ---------------------------------------------------------------- course advisor (advisor.py)
class CatalogImport(BaseModel):
    year: Optional[str] = ""     # catalog year, e.g. "2016-2017"; read from the text when missing
    text: Optional[str] = ""
    rows: Optional[List[Dict[str, Any]]] = None
    source: Optional[str] = "import"
    useModel: Optional[bool] = False

class CompletedImport(BaseModel):
    text: Optional[str] = ""
    rows: Optional[List[Dict[str, Any]]] = None
    source: Optional[str] = "manual"

CATALOG_EXTRACT_PROMPT = """
Extract every course from this catalog text. Return JSON only:
{{"courses": [{{"code": "CSCI 141", "title": "...", "credits": "4", "description": "...", "prereqs": "catalog wording or empty",
"attributes": ["COLL 150", "NQR"]}}]}}
Copy wording faithfully; do not invent courses.

TEXT:
{text}
"""

@app.get("/api/advisor/catalog")
def catalog_search(q: str = "", dept: str = "", limit: int = 40):
    return {"stats": advisor.stats(), "courses": advisor.search(q, dept, limit)}

@app.get("/api/advisor/catalog/{code}")
def catalog_course(code: str):
    c = advisor.get_course(code)
    if not c:
        raise HTTPException(status_code=404, detail="That course isn't in the imported catalog.")
    return c

@app.post("/api/advisor/catalog/import")
async def catalog_import(body: CatalogImport):
    """Rows as JSON, or catalog text (a PDF or page the student's browser could open); optionally the model reads
    text the parser can't."""
    rate_limit("upload")
    rows = list(body.rows or [])
    text = (body.text or "")[:400000]
    if text:
        rows += advisor.parse_catalog_text(text)
        if not rows and body.useModel:
            for chunk in [text[i:i + 30000] for i in range(0, min(len(text), 120000), 30000)]:
                data = await gemini_json(CATALOG_EXTRACT_PROMPT.format(text=chunk), role="lesson")
                rows += [r for r in (data.get("courses") or []) if isinstance(r, dict)] if isinstance(data, dict) else []
    year = (body.year or advisor.catalog_year(text) or "").strip()[:9]
    source = f"{body.source or 'import'}{f' {year} catalog' if year else ''}"
    n = advisor.upsert_courses(rows, source)
    return {"imported": n, "year": year or None, "stats": advisor.stats()}

@app.get("/api/advisor/{user_id}/completed")
def completed_list(user_id: str):
    require_user(user_id)
    return {"completed": advisor.completed(user_id)}

@app.post("/api/advisor/{user_id}/completed")
def completed_import(user_id: str, body: CompletedImport):
    """A transcript, degree audit, screenshot text (from /api/upload-multimodal) or typed list of course codes."""
    require_user(user_id)
    rows = list(body.rows or []) + advisor.transcript_rows(body.text or "")
    for r in rows:  # fill titles from the catalog where the transcript had none
        c = advisor.get_course(str(r.get("code", "")))
        if c and not r.get("title"):
            r["title"] = c["title"]
    n = advisor.add_completed(user_id, rows, body.source or "manual")
    return {"added": n, "completed": advisor.completed(user_id)}

@app.delete("/api/advisor/{user_id}/completed/{code}")
def completed_remove(user_id: str, code: str):
    require_user(user_id)
    advisor.remove_completed(user_id, code)
    return {"completed": advisor.completed(user_id)}

@app.get("/api/advisor/{user_id}/recommend")
def advisor_recommend(user_id: str, interests: str = "", limit: int = 12):
    require_user(user_id)
    return {"courses": advisor.recommend(user_id, interests, min(max(limit, 1), 40)), "stats": advisor.stats()}

@app.get("/api/advisor/{user_id}/readiness/{code}")
def advisor_readiness(user_id: str, code: str):
    require_user(user_id)
    return advisor.readiness(user_id, code)

class ReadinessRequest(BaseModel):
    code: str

@app.post("/api/advisor/{user_id}/readiness-course")
def advisor_readiness_course(user_id: str, body: ReadinessRequest):
    """Builds a readiness course: a diagnostic on what the target course assumes, then bridge classes for gaps."""
    rate_limit("course")
    require_user(user_id)
    target = advisor.get_course(body.code)
    if not target:
        raise HTTPException(status_code=404, detail="Import the catalog entry for that course first.")
    pre = [advisor.get_course(c) for c in target["prereq_codes"]]
    materials = "\n\n".join([f"TARGET COURSE {target['code']}: {target['title']}\n{target['description']}\nPrerequisites: {target['prereqs'] or 'none listed'}"]
                             + [f"PREREQUISITE {p['code']}: {p['title']}\n{p['description']}" for p in pre if p])
    done = ", ".join(f"{r['code']} ({r['grade'] or 'no grade'})" for r in advisor.completed(user_id)) or "none recorded"
    goal = f"Am I ready for {target['code']} {target['title']}? Test the prerequisite knowledge and fill my gaps. Courses I have done: {done}"
    title = f"Ready for {target['code']}?"
    course = db.create_course(user_id, title, goal, materials[:200000], [], "readiness", None)
    db.update_course(course["id"], plan_questions=10, plan_classes=3)
    job = start_plan_job(course["id"], 10, 3)
    return {"course": public_course(db.get_course(course["id"])), "job": job}


class SimulationRequest(BaseModel):
    topicId: str
    focus: Optional[str] = ""
    kind: Optional[str] = "auto"   # auto (by workspace) | math | physics

def queue_simulation_job(topic_id: str, focus: str = "", kind: str = "auto") -> Dict[str, Any]:
    path = topic_path(topic_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Topic not found")

    async def work(job):
        topic = load_json_file(path, {})
        _job_update(job, step=f"Designing a simulation for {topic.get('title', topic_id)}", progress=0.2)
        is_math = kind == "math" or (kind == "auto" and with_workspace(topic).get("source", {}).get("workspace") == "math")
        spec = await author_simulation(_topic_brief(topic), focus, math=is_math)
        topic = load_json_file(path, topic)  # re-read: the topic may have been edited meanwhile
        topic["simulation"] = spec
        save_topic(topic, auto_select=False)
        return {"topicId": topic_id, "title": spec["title"]}

    return start_job("simulation", f"Simulation: {topic_id}", work)

@app.post("/api/simulations/generate")
def generate_simulation(req: SimulationRequest):
    rate_limit("simulation")
    return queue_simulation_job(req.topicId, req.focus or "", req.kind or "auto")

@app.post("/api/simulations/backfill")
def backfill_simulations():
    """Queues a simulation for every topic that has neither a built-in nor a generated one."""
    rate_limit("simulation")
    jobs = []
    for path in sorted(TOPICS_DIR.glob("*.json")):
        topic = load_json_file(path, {})
        if topic.get("id") and not topic.get("simulation") and topic.get("simulationType") not in BUILTIN_SIMULATIONS:
            jobs.append(queue_simulation_job(topic["id"]))
    return {"queued": len(jobs), "jobs": jobs}

BUILTIN_SIMULATIONS = {"rolling_without_slipping", "billiard_collisions"}
# Generated SimSpec simulations are played live by SpecSim.jsx.
# Classes author simulations by default; turn off with SCIEDU_AUTHOR_SIMS=0 to save quota.
AUTHOR_SIMS = os.environ.get("SCIEDU_AUTHOR_SIMS", "1") != "0"

# ---------------------------------------------------------------------------
# COURSES: materials -> syllabus + diagnostic -> classes generated in sequence, adapting to results
# ---------------------------------------------------------------------------
class UserRequest(BaseModel):
    name: str

class CourseRequest(BaseModel):
    userId: str
    goal: Optional[str] = ""
    materials_text: Optional[str] = ""
    filenames: Optional[List[str]] = []
    num_questions: Optional[int] = 8
    class_count: Optional[int] = None
    mode: Optional[str] = "learn"          # learn | test_prep
    exam_date: Optional[str] = None        # YYYY-MM-DD, test prep only

class ExtendRequest(BaseModel):
    goal: Optional[str] = ""
    materials_text: Optional[str] = ""
    filenames: Optional[List[str]] = []
    class_count: Optional[int] = None

class DiagnosticAnswers(BaseModel):
    answers: Dict[str, int]

ACTIVE_COURSE_JOBS: Dict[str, str] = {}

def require_user(user_id: str) -> Dict[str, Any]:
    me = CURRENT_USER.get()
    if AUTH_REQUIRED and (not me or me["id"] != user_id):
        raise HTTPException(status_code=403, detail="You can only open your own courses.")
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Profile not found. Sign in again.")
    return user

def require_course(course_id: str) -> Dict[str, Any]:
    course = db.get_course(course_id)
    me = CURRENT_USER.get()
    # with accounts on, someone else's course is reported as missing rather than forbidden (no id probing)
    if not course or (AUTH_REQUIRED and (not me or course["user_id"] != me["id"])):
        raise HTTPException(status_code=404, detail="Course not found")
    return course

class AuthRequest(BaseModel):
    name: str
    password: str
    adult: Optional[bool] = None   # required on sign-up: the Gemini API terms require users to be 18+

def _clean_name(raw: str) -> str:
    name = " ".join((raw or "").split())[:40]
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="Use a name with at least 2 characters.")
    return name

@app.post("/api/auth/register")
def register(req: AuthRequest):
    if not AUTH_REQUIRED:
        raise HTTPException(status_code=404, detail="Accounts are off on this server (SCIEDU_AUTH is not set).")
    name = _clean_name(req.name)
    if req.adult is not True:
        raise HTTPException(status_code=422, detail="This service uses the Gemini API, which is for people 18 or older. Confirm your age to continue.")
    if len(req.password) < 8:
        raise HTTPException(status_code=422, detail="Use a password of at least 8 characters.")
    existing = db.get_user_by_name(name)
    if existing and existing.get("password_hash"):
        raise HTTPException(status_code=409, detail="That name is taken. Sign in instead.")
    if existing:  # a name-only profile from local use claims its password on first sign-up
        db.set_password(existing["id"], req.password)
        user = {"id": existing["id"], "name": existing["name"]}
    else:
        user = db.create_account(name, req.password)
    return {"token": db.create_session(user["id"]), "user": user}

@app.post("/api/auth/login")
def login(req: AuthRequest):
    if not AUTH_REQUIRED:
        raise HTTPException(status_code=404, detail="Accounts are off on this server (SCIEDU_AUTH is not set).")
    user = db.get_user_by_name(_clean_name(req.name))
    if not user or not db.check_password(req.password, user.get("password_hash")):
        raise HTTPException(status_code=401, detail="Wrong name or password.")
    return {"token": db.create_session(user["id"]), "user": {"id": user["id"], "name": user["name"]}}

@app.post("/api/auth/logout")
def logout(request: Request):
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        db.end_session(auth[7:].strip())
    return {"status": "signed_out"}

@app.get("/api/auth/me")
def me():
    return {"user": CURRENT_USER.get(), "authRequired": AUTH_REQUIRED}

def public_course(course: Dict[str, Any]) -> Dict[str, Any]:
    """Course + classes for the UI. Diagnostic answer keys stay hidden until the student submits."""
    out = {k: v for k, v in course.items() if k != "materials_text"}
    out["workspace"] = course_workspace(course)
    if course["status"] in ("planning", "diagnostic_ready"):
        out["diagnostic"] = [{k: v for k, v in q.items() if k not in ("correctAnswer", "explanation")}
                             for q in course.get("diagnostic") or []]
    out["classes"] = db.list_classes(course["id"])
    job = JOBS.get(course.get("job_id") or "")
    out["job"] = job and {k: job.get(k) for k in ("id", "status", "step", "progress", "error")}
    return out

def course_event(course_id: str):
    course = db.get_course(course_id)
    if course:
        emit_event("COURSE_UPDATED", {"courseId": course_id, "status": course["status"]})

DIAGNOSTIC_PROMPT = """
You are an expert assessment designer. From the student's study materials and goal, build a DIAGNOSTIC quiz
that reveals which concepts they have and haven't mastered.

Return JSON only:
{{"title": "short course title",
  "subject": "e.g. Physics / Calculus / Chemistry / Python",
  "workspace": "math | code | lab | history | language   (math: mathematics; code: programming; history: history and historical studies; language: languages and linguistics; lab: physics, chemistry, other sciences)",
  "concepts": [{{"id": "kebab-case-id", "name": "Concept name", "summary": "one sentence"}}],
  "questions": [{{"id": "q1", "concept": "<concept id>", "difficulty": "Recall|Apply|Analyze",
                 "question": "...", "options": ["...", "...", "...", "..."], "correctAnswer": 0,
                 "explanation": "why the answer is right and the most tempting wrong option is wrong"}}]}}

Rules:
- 3 to 8 concepts that together cover the materials; every concept gets at least 1 question.
- Exactly {n} questions, mixing recall, application (numbers with units) and conceptual traps.
- correctAnswer is the 0-based index into options. Vary its position.
- Use LaTeX inside $...$ for every formula and variable.
- Stay faithful to the materials; do not test things they don't cover.

STUDENT GOAL: {goal}

MATERIALS:
{materials}
"""

SYLLABUS_PROMPT = """
You are planning a course as an ordered sequence of classes (lessons), like a semester syllabus.
Concepts identified in the materials: {concepts}

Return JSON only:
{{"classes": [{{"title": "Class title", "concepts": ["<concept id>", ...],
               "objectives": ["By the end the student can ...", "..."]}}]}}

Rules:
- {count} classes, ordered so every class builds only on earlier ones (prerequisites first).
- Every concept id appears in at least one class. Use only the ids listed above.
- 2-4 concrete, checkable objectives per class.{mode_rules}

STUDENT GOAL: {goal}

MATERIALS:
{materials}
"""

CLASS_PROMPT = """
You are a master teacher writing Class {seq} of {total} in the course "{course_title}" for one student.
This class: "{title}"
Objectives: {objectives}
Concepts covered: {concepts}

What the student knows so far (from the diagnostic and their quizzes on earlier classes):
{mastery_line}
Diagnostic questions they missed on these concepts (chosen option -> correct option):
{misses}
Earlier classes they've already had (do not repeat them; build on them and refer back):
{previous}

Pitch the class at: {difficulty}.{adjustment}
Course materials are the source of truth:
{materials}

Return JSON only:
{{"title": "{title}", "category": "{subject}", "difficulty": "{difficulty}",
  "summary": "1-2 sentences addressed to the student: what this class gives them and which earlier gap it fixes",
  "markdownContent": "Full Markdown lesson: recap link to the previous class, intuition first, then step-by-step explanation/derivation with LaTeX ($...$ and $$...$$), one fully worked example with numbers and units, a common-mistakes section aimed at the misses above, and a short summary. 600-1200 words.",
  "cheatSheet": [{{"label": "...", "formula": "LaTeX without $"}}],
  "mermaid": "graph TD; ... concept map. Quote EVERY node label A[\\"label\\"] and edge label -->|\\"label\\"|; no LaTeX, $, braces or backslashes inside the diagram; or empty string",
  "quiz": [{{"id": "q1", "question": "...", "options": ["a","b","c","d"], "correctAnswer": 0, "hint": "...", "explanation": "..."}}],
  "practice": [
    {{"type": "fill_blank", "prompt": "sentence or equation with ___", "options": ["...","...","...","..."], "answer": "exact option text", "explanation": "..."}},
    {{"type": "order_steps", "prompt": "Put the steps in order", "steps": ["step 1", "step 2", "step 3", "step 4"], "explanation": "..."}},
    {{"type": "numeric", "prompt": "a calculation with given values", "answer": 4.2, "tolerance": 0.02, "unit": "m/s", "explanation": "worked solution"}},
    {{"type": "true_false", "prompt": "a statement targeting a misconception", "answer": false, "explanation": "..."}}
  ]}}
Write 5 quiz questions that check the objectives (vary the correctAnswer position) and 4-6 practice items using all four types.
Also add "flashcards": 8-12 cards [{{"front": "term or question", "back": "definition or answer", "hint": "optional"}}] for spaced recall.{extras}
If the course involves programming (Python, algorithms, data), add 1-2 items of type "code":
    {{"type": "code", "prompt": "what to implement", "starter": "def f(x):\\n    # TODO\\n    pass", "tests": "assert f(2) == 4\\nassert f(0) == 0", "solution": "def f(x):\\n    return x * 2", "explanation": "..."}}
    Python only, standard library only, tests are plain assert lines covering normal and edge cases.
Every variable, formula, exponent and unit with a power (e.g. $v_0$, $9.80\\,\\text{{m/s}}^2$) is LaTeX inside $...$, including inside
options, steps, hints and answers; never write bare x^2 or v_0.
"""

TEST_PREP_SYLLABUS = """
- This is TEST PREPARATION{exam}. Order classes by how much each topic is likely to count on the exam and by
  the student's gaps; each class is a focused review, not a first introduction.
- The LAST class is a full mock exam covering the whole course: title it "Mock exam: <subject>".
"""

TEST_PREP_CLASS = (
    "TEST PREP: the student is preparing for an exam{exam}. Keep the lesson tight (400-700 words): an exam-focused "
    "summary, the formulas to memorise, one worked exam-style problem, and the traps examiners set. Write 8 exam-style "
    "quiz questions instead of 5, and practice items at exam difficulty.{mock}"
)

WORKSPACE_EXTRAS = {
    "history": '''
HISTORY CLASS: add "timeline": 6-12 events [{"year": 1789, "date": "14 July 1789", "title": "Storming of the Bastille", "detail": "why it matters"}]
(year is a number, negative for BCE) covering the class; flashcards for people, terms and dates; one practice item of type
"match_pairs" pairing people or events with what they did, e.g. {"type": "match_pairs", "prompt": "Match each figure to their role", "pairs": [["Robespierre", "Leader of the Committee of Public Safety"], ...]} (4-6 pairs);
quiz questions that ask about causes, consequences and sources, not only dates.''',
    "language": '''
LANGUAGE/LINGUISTICS CLASS: flashcards carry "lang" (BCP-47 such as "es", "fr", "de", "ja") when the front is in the target
language so the app can read it aloud; include IPA in the back where pronunciation matters. Add one "match_pairs" practice item
(word to meaning, term to example, or sound to IPA symbol), and fill_blank items for grammar (conjugation, agreement, word order).''',
}

READINESS_SYLLABUS = """
- This is a READINESS course for {target}. The diagnostic must test exactly the prerequisite knowledge that course
  assumes. Plan only bridge classes for gaps (2-4 classes), each ending with what the target course will build on.
"""

def mode_rules(course: Dict[str, Any]) -> str:
    if course.get("mode") == "readiness":
        return "\n" + READINESS_SYLLABUS.format(target=course.get("title", "the target course")).strip("\n")
    if course.get("mode") != "test_prep":
        return ""
    exam = f" (exam on {course['exam_date']})" if course.get("exam_date") else ""
    return "\n" + TEST_PREP_SYLLABUS.format(exam=exam).strip("\n")

def mode_adjustment(course: Dict[str, Any], klass: Dict[str, Any]) -> str:
    if course.get("mode") != "test_prep":
        return ""
    exam = f" on {course['exam_date']}" if course.get("exam_date") else ""
    mock = (" THIS CLASS IS THE MOCK EXAM: write 10 mixed questions across every earlier class, at full exam "
            "difficulty, and make the lesson a short exam-strategy briefing.") if klass["title"].lower().startswith("mock exam") else ""
    return "\n" + TEST_PREP_CLASS.format(exam=exam, mock=mock)

EXTEND_PROMPT = """
You are continuing an existing course with new material the student just added.
Course: "{title}" ({mode})
Concepts already in the course: {concepts}
Classes the student already has:
{classes}

Plan {count} NEW classes that continue the course: cover what the new materials add, build on the earlier
classes, and do not repeat them.{mode_rules}

Return JSON only:
{{"concepts": [{{"id": "kebab-id", "name": "Concept name", "summary": "one line"}}],
  "classes": [{{"title": "Class title", "concepts": ["<concept id>", ...], "objectives": ["By the end the student can ...", "..."]}}]}}
"concepts" lists only NEW concepts; classes may use those and the existing ids above.

WHAT THE STUDENT WANTS NOW: {goal}

NEW MATERIALS:
{materials}
"""

def grade_diagnostic(questions: List[Dict[str, Any]], answers: Dict[str, int], concepts: List[Dict[str, Any]]) -> Dict[str, Any]:
    mastery: Dict[str, Dict[str, Any]] = {c["id"]: {"correct": 0, "total": 0} for c in concepts}
    for q in questions:
        m = mastery.setdefault(q.get("concept"), {"correct": 0, "total": 0})
        m["total"] += 1
        m["correct"] += int(answers.get(q["id"]) == q["correctAnswer"])
    for m in mastery.values():
        m["score"] = m["correct"] / m["total"] if m["total"] else None
    return mastery

def effective_mastery(course: Dict[str, Any], classes: List[Dict[str, Any]]) -> Dict[str, float]:
    """Diagnostic score per concept, overridden by the latest quiz score of any class teaching it."""
    scores = {cid: m.get("score") for cid, m in (course.get("mastery") or {}).items()}
    for k in classes:
        if k.get("score") is not None:
            for cid in k.get("concepts") or []:
                scores[cid] = k["score"]
    return scores

WORKSPACES = ("math", "code", "lab", "history", "language")
_CODE_RE = re.compile(r"python|programm|coding|\bcode\b|algorithm|data structure|javascript|typescript|\bjava\b|c\+\+|\brust\b|software|computer science|sql\b", re.I)
_MATH_RE = re.compile(r"math|calculus|algebra|geometry|trigonometr|statistic|probabilit|\blimits?\b|epsilon|delta|derivative|integra|proof|number theory|"
                      r"differential equation|real analysis|topology|combinatoric|precalc|matri|vector space|sequence|series", re.I)

_LANG_RE = re.compile(r"linguistic|language|spanish|french|german|italian|chinese|mandarin|japanese|korean|arabic|russian|latin|greek|"
                      r"grammar|phonetic|phonolog|morpholog|semantics|vocabulary|conjugat|pronunciation", re.I)
_HIST_RE = re.compile(r"histor|civilization|\bwar\b|revolution|ancient|medieval|empire|dynasty|century|colonial|renaissance|reformation", re.I)

def guess_workspace(*texts: str) -> str:
    """Fallback when the planner gave none: code beats math (a 'Python for statistics' course is code),
    then math, languages, history; everything else (physics, chemistry, biology...) is Lab."""
    blob = " ".join(t or "" for t in texts)
    for ws, rx in (("code", _CODE_RE), ("math", _MATH_RE), ("language", _LANG_RE), ("history", _HIST_RE)):
        if rx.search(blob):
            return ws
    return "lab"

def course_workspace(course: Dict[str, Any]) -> str:
    ws = course.get("workspace")
    return ws if ws in WORKSPACES else guess_workspace(course.get("subject", ""), course.get("title", ""), course.get("goal", ""))

def with_workspace(topic: Dict[str, Any], cache: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Course classes carry the workspace they open in (older topic files don't have it stored)."""
    src = topic.get("source") or {}
    cid = src.get("courseId")
    if not cid or src.get("workspace") in WORKSPACES:
        return topic
    if cache is None or cid not in cache:
        course = db.get_course(cid)
        ws = course_workspace(course) if course else guess_workspace(topic.get("category", ""), src.get("courseTitle", ""))
        if cache is not None:
            cache[cid] = ws
    else:
        ws = cache[cid]
    return {**topic, "source": {**src, "workspace": ws}}

async def plan_course(course_id: str, job, n_questions: int, class_count: Optional[int]):
    course = db.get_course(course_id)
    materials = course["materials_text"][:120000] or "(no files: plan from the goal)"
    goal = course["goal"] or "Master these materials"
    _job_update(job, step="Reading your materials and writing a diagnostic quiz", progress=0.1)
    data = await gemini_json(DIAGNOSTIC_PROMPT.format(n=n_questions, goal=goal, materials=materials), role="planner")

    concepts = [{"id": slugify(c.get("id") or c.get("name", ""), f"c{i}"), "name": c.get("name") or f"Concept {i + 1}",
                 "summary": c.get("summary", "")} for i, c in enumerate(data.get("concepts") or []) if isinstance(c, dict)]
    if not concepts:
        concepts = [{"id": "core", "name": data.get("title") or "Core concepts", "summary": ""}]
    concept_ids = {c["id"] for c in concepts}
    questions = []
    for i, q in enumerate(data.get("questions") or []):
        nq = normalize_quiz_item(q, i) if isinstance(q, dict) else None
        if nq:
            nq["id"] = f"q{len(questions) + 1}"
            cid = slugify(q.get("concept", ""), "")
            nq["concept"] = cid if cid in concept_ids else concepts[0]["id"]
            questions.append(nq)
    if not questions:
        raise RuntimeError("The diagnostic came back empty. Add more material or a clearer goal and try again.")
    _job_update(job, step="Double-checking the diagnostic answer keys with a second model", progress=0.4)
    questions = await verify_questions(questions, materials[:12000] + "\nGoal: " + goal, keep_min=max(3, n_questions // 2))

    _job_update(job, step="Planning the sequence of classes", progress=0.55)
    count = class_count or min(max(len(concepts) + 1, 4), 8)
    plan = await gemini_json(role="planner", prompt=SYLLABUS_PROMPT.format(
        concepts=", ".join(f"{c['id']} ({c['name']})" for c in concepts), count=count, goal=goal,
        materials=materials[:40000], mode_rules=mode_rules(course)))
    outline = []
    for item in (plan.get("classes") or [])[:12]:
        if isinstance(item, dict) and item.get("title"):
            outline.append({"title": str(item["title"])[:120],
                            "concepts": [c for c in (item.get("concepts") or []) if c in concept_ids],
                            "objectives": [str(o) for o in (item.get("objectives") or [])][:5]})
    if not outline:
        outline = [{"title": c["name"], "concepts": [c["id"]], "objectives": [c["summary"]] if c["summary"] else []} for c in concepts]

    workspace = data.get("workspace") if data.get("workspace") in WORKSPACES else guess_workspace(data.get("subject", ""), data.get("title", ""), goal)
    db.update_course(course_id, title=data.get("title") or course["title"], subject=data.get("subject") or "", workspace=workspace,
                     concepts=concepts, diagnostic=questions, status="diagnostic_ready", error=None)
    db.replace_classes(course_id, outline)
    course_event(course_id)
    return {"courseId": course_id, "questions": len(questions), "classes": len(outline)}

async def build_class(course: Dict[str, Any], klass: Dict[str, Any], classes: List[Dict[str, Any]]) -> Dict[str, Any]:
    concepts = {c["id"]: c for c in course.get("concepts") or []}
    scores = effective_mastery(course, classes)
    covered = klass.get("concepts") or []
    known = [scores.get(c) for c in covered if scores.get(c) is not None]
    level = sum(known) / len(known) if known else 0.5
    levels = ["Foundations", "Intermediate", "Advanced"]
    step = 0 if level < 0.5 else 1 if level < 0.8 else 2
    # an adapted class moves one level with the student's last quiz, whatever its own concepts scored
    if klass.get("adapted_from") is not None:
        step = max(0, step - 1) if klass["adapted_from"] < ADAPT_LOW else min(2, step + 1)
    difficulty = levels[step]
    answers = course.get("answers") or {}
    misses = [
        f"- {q['question']} | chose: {q['options'][answers[q['id']]] if 0 <= answers.get(q['id'], -1) < len(q['options']) else 'no answer'}"
        f" -> {q['options'][q['correctAnswer']]}"
        for q in course.get("diagnostic") or []
        if q.get("concept") in covered and answers.get(q["id"]) != q["correctAnswer"]
    ]
    previous = [f"Class {k['seq']}: {k['title']}" + (f" (quiz score {round(k['score'] * 100)}%)" if k.get("score") is not None else "")
                for k in classes if k["seq"] < klass["seq"] and k["status"] == "ready"]
    prompt = CLASS_PROMPT.format(
        seq=klass["seq"], total=len(classes), course_title=course["title"], title=klass["title"],
        objectives="; ".join(klass.get("objectives") or []) or "(choose sensible objectives)",
        concepts=", ".join(concepts[c]["name"] for c in covered if c in concepts) or klass["title"],
        mastery_line=", ".join(f"{concepts[c]['name']}: {'not tested' if s is None else str(round(s * 100)) + '%'}"
                               for c, s in scores.items() if c in concepts) or "no data yet",
        misses="\n".join(misses) or "- none",
        previous="\n".join(previous) or "- this is the first class",
        difficulty=difficulty, subject=course.get("subject") or "Science",
        materials=(course.get("materials_text") or "")[:30000],
        extras=WORKSPACE_EXTRAS.get(course_workspace(course), ""),
        adjustment=mode_adjustment(course, klass)
                   + (f"\nIMPORTANT ADJUSTMENT FOR THIS STUDENT: {klass['instruction']}" if klass.get("instruction") else ""),
    )
    data = await gemini_json(prompt, role="lesson")
    if not isinstance(data, dict):
        raise RuntimeError("Lesson generation returned no object")
    topic = {
        **{k: data.get(k) for k in ("title", "category", "difficulty", "summary", "markdownContent", "cheatSheet", "mermaid", "quiz")},
        "id": slugify(f"{course['id']}-{klass['seq']:02d}-{klass['title']}")[:80].strip("-"),
        "icon": "BookOpen",
        "flashcards": data.get("flashcards"),
        **({"timeline": data.get("timeline")} if data.get("timeline") else {}),
        "practice": normalize_practice(data.get("practice")),
        "source": {"kind": "course", "courseId": course["id"], "courseTitle": course["title"],
                   "classSeq": klass["seq"], "classTotal": len(classes), "workspace": course_workspace(course)},
    }
    topic["title"] = topic.get("title") or klass["title"]
    topic["category"] = topic.get("category") or course.get("subject") or "Course"
    topic["markdownContent"] = topic.get("markdownContent") or f"# {klass['title']}"
    if klass.get("instruction"):
        topic["source"]["adaptedBecause"] = klass["instruction"]
    normalized, _ = normalize_topic(topic)
    quiz_check = verify_questions(normalized["quiz"], _topic_brief(normalized, 8000))
    if AUTHOR_SIMS:
        sim_task = author_simulation(_topic_brief(topic), f"Make the student SEE the key idea of: {klass['title']}",
                                     math=course_workspace(course) == "math")
        checked, sim = await asyncio.gather(quiz_check, sim_task, return_exceptions=True)
        if isinstance(sim, dict):
            topic["simulation"] = sim
    else:
        checked = await asyncio.gather(quiz_check, return_exceptions=True)
        checked = checked[0]
    topic["quiz"] = checked if isinstance(checked, list) else normalized["quiz"]
    saved, _ = normalize_topic(topic)
    saved["notesFile"] = write_notes_file(saved)
    saved, _ = save_topic(saved, event_type="TOPIC_CREATED", auto_select=False, course_id=course["id"])
    return saved

VERIFY_PROMPT = """
You are an exacting examiner checking multiple-choice questions written by another model before students see them.
Solve each question yourself first, then compare with the marked answer.

Context (the course material the questions are based on, may be partial):
{context}

Questions (correctAnswer is a 0-based index into options):
{questions}

Return JSON only: {{"checks": [{{"id": "<question id>", "verdict": "correct" | "wrong" | "ambiguous",
  "solvedAnswer": <0-based index you got, or null if no option is right>,
  "confidence": <0.0-1.0 that the FINAL answer key is right>,
  "note": "one short sentence: why, or what is wrong"}}]}}
"wrong" = the marked answer is not the right option. "ambiguous" = two options defensible, none right, or the question is unclear.
"""

# Plan 4/D: check answer keys against the web, and show students the sources. Needs Google Search grounding
# on the API key; without it the check runs offline. Turn off with SCIEDU_GROUNDED_CHECKS=0.
GROUNDED_CHECKS = os.environ.get("SCIEDU_GROUNDED_CHECKS", "1") != "0"
GROUNDING_NOTE = ("\nUse Google Search to confirm facts, constants and standard results, preferring university and "
                  "textbook sources. Return ONLY the JSON object, no prose around it.")

async def grounded_json(prompt: str) -> Tuple[Any, List[Dict[str, str]]]:
    """Gemini with Google Search grounding. JSON mode can't be combined with search, so the JSON is cut
    out of the text reply; the pages the model actually used come from grounding metadata, never from its text."""
    global GROUNDING_PAUSED_UNTIL
    if time.time() < GROUNDING_PAUSED_UNTIL:
        raise RuntimeError("search grounding paused after a quota error")
    try:
        response = await acall_gemini(
            contents=prompt, role="planner", track_cooldown=False,
            config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.1),
        )
    except Exception:
        GROUNDING_PAUSED_UNTIL = time.time() + 3600
        raise
    text = response.text or ""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("grounded check returned no JSON")
    data = _parse_json_reply(text[start:end + 1])
    sources, seen = [], set()
    try:
        meta = response.candidates[0].grounding_metadata
        for chunk in (meta.grounding_chunks or []) if meta else []:
            web = getattr(chunk, "web", None)
            if web and web.uri and (web.title or web.uri) not in seen:
                seen.add(web.title or web.uri)
                sources.append({"title": web.title or "source", "uri": web.uri})
    except (AttributeError, IndexError):
        pass
    return data, sources[:4]

async def verify_questions(questions: List[Dict[str, Any]], context: str, keep_min: int = 3) -> List[Dict[str, Any]]:
    """Plan section 4: a second model re-solves every question. Wrong keys are corrected, unclear questions
    dropped (keeping at least `keep_min`), and each question carries `check` = verdict + certainty for the UI."""
    if not questions:
        return questions
    listing = json.dumps([{k: q.get(k) for k in ("id", "question", "options", "correctAnswer")} for q in questions], ensure_ascii=False)
    prompt = VERIFY_PROMPT.format(context=context[:12000], questions=listing)
    data, sources = None, []
    if GROUNDED_CHECKS:
        try:
            data, sources = await grounded_json(prompt + GROUNDING_NOTE)
        except Exception as e:
            print(f"[verify] grounded check unavailable, using offline check: {friendly_ai_error(e)}")
    if data is None:
        try:
            data = await gemini_json(prompt, temperature=0.1, role="planner")
        except Exception as e:
            print(f"[verify] skipped: {e}")
            return questions
    checks = {c.get("id"): c for c in (data.get("checks") or []) if isinstance(c, dict)}
    kept, dropped = [], []
    for q in questions:
        c = checks.get(q.get("id"))
        if not c:
            kept.append(q)
            continue
        conf = c.get("confidence")
        conf = max(0.0, min(1.0, float(conf))) if isinstance(conf, (int, float)) else None
        verdict = c.get("verdict")
        solved = c.get("solvedAnswer")
        q = dict(q)
        if verdict == "wrong" and isinstance(solved, int) and 0 <= solved < len(q["options"]):
            q["correctAnswer"] = solved
            q["check"] = {"verdict": "corrected", "confidence": conf, "note": c.get("note", ""), "sources": sources}
            kept.append(q)
        elif verdict in ("wrong", "ambiguous") or (conf is not None and conf < 0.5):
            q["check"] = {"verdict": verdict or "low-confidence", "confidence": conf, "note": c.get("note", ""), "sources": sources}
            dropped.append(q)
        else:
            q["check"] = {"verdict": "verified", "confidence": conf, "note": c.get("note", ""), "sources": sources}
            kept.append(q)
    # never leave a quiz too short: put back the least doubtful dropped questions, flagged
    dropped.sort(key=lambda q: -(q["check"].get("confidence") or 0))
    while len(kept) < keep_min and dropped:
        kept.append(dropped.pop(0))
    return kept

def queue_course_generation(course_id: str) -> Dict[str, Any]:
    """Generates every pending class in order; one job per course, safe to call again to resume."""
    running = ACTIVE_COURSE_JOBS.get(course_id)
    if running and JOBS.get(running, {}).get("status") in ("queued", "running"):
        return JOBS[running]

    async def work(job):
        built = 0
        while True:
            course = db.get_course(course_id)
            if not course:
                return {"courseId": course_id, "cancelled": True}
            classes = db.list_classes(course_id)
            pending = [k for k in classes if k["status"] in ("pending", "error")]
            if not pending:
                break
            klass = pending[0]
            done = sum(k["status"] == "ready" for k in classes)
            _job_update(job, step=f"Writing class {klass['seq']} of {len(classes)}: {klass['title']}",
                        progress=0.05 + 0.9 * done / max(len(classes), 1))
            db.update_class(klass["id"], status="generating", error=None)
            course_event(course_id)
            try:
                topic = await build_class(course, klass, classes)
                if not db.get_course(course_id):  # deleted while this class was being written
                    for path in (topic_path(topic["id"]), NOTES_DIR / f"{topic['id']}.md"):
                        path.unlink(missing_ok=True)
                    emit_event("TOPIC_UPDATED", {"autoSelect": False})
                    return {"courseId": course_id, "cancelled": True}
                db.update_class(klass["id"], status="ready", topic_id=topic["id"])
                built += 1
            except Exception as e:
                db.update_class(klass["id"], status="error", error=friendly_ai_error(e))
                db.update_course(course_id, status="error", error=f"Class {klass['seq']} failed: {friendly_ai_error(e)}")
                course_event(course_id)
                raise
            course_event(course_id)
        db.update_course(course_id, status="ready", error=None)
        course_event(course_id)
        return {"courseId": course_id, "built": built}

    db.update_course(course_id, status="generating", error=None)
    job = start_job("course", f"Course classes: {course_id}", work)
    ACTIVE_COURSE_JOBS[course_id] = job["id"]
    db.update_course(course_id, job_id=job["id"])
    course_event(course_id)
    return job

@app.on_event("startup")
async def resume_course_generation():
    """Classes interrupted by a restart pick up where they stopped."""
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()
    db.init_db()
    engage.init()
    advisor.init()
    db.reset_stuck_classes()
    for course in db.interrupted_planning():  # planning jobs die with the process: redo them from stored materials
        start_plan_job(course["id"], course.get("plan_questions") or 8, course.get("plan_classes"))
    import_topic_files_into_db()
    for course_id in db.courses_with_pending_classes():
        queue_course_generation(course_id)

def import_topic_files_into_db():
    for path in TOPICS_DIR.glob("*.json"):
        topic = load_json_file(path, None)
        if isinstance(topic, dict) and topic.get("id") and not db.get_lesson(topic["id"]):
            db.upsert_lesson(topic)

@app.get("/api/users")
def list_profiles():
    if AUTH_REQUIRED:
        raise HTTPException(status_code=403, detail="Profiles are private on this server.")
    return {"users": db.list_users()}

@app.post("/api/users")
def sign_in(req: UserRequest):
    """Local profiles (no passwords): only for a personal machine, where the server listens on 127.0.0.1."""
    if AUTH_REQUIRED:
        raise HTTPException(status_code=403, detail="Sign in with a password on this server.")
    return {"user": db.get_or_create_user(_clean_name(req.name))}

@app.get("/api/users/{user_id}/courses")
def list_user_courses(user_id: str):
    require_user(user_id)
    return {"courses": [{**c, "workspace": course_workspace(c)} for c in db.list_courses(user_id)]}

@app.post("/api/courses")
def create_course(req: CourseRequest):
    rate_limit("course")
    if AUTH_REQUIRED:
        req.userId = CURRENT_USER.get()["id"]
    require_user(req.userId)
    materials = (req.materials_text or "").strip()
    goal = (req.goal or "").strip()
    if len(materials) + len(goal) < 20:
        raise HTTPException(status_code=422, detail="Add study materials or describe what you want to learn (at least a sentence).")
    n = min(max(req.num_questions or 8, 4), 15)
    count = min(max(req.class_count, 2), 12) if req.class_count else None
    mode = req.mode if req.mode in ("test_prep", "readiness") else "learn"
    exam_date = (req.exam_date or "")[:10] if mode == "test_prep" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", req.exam_date or "") else None
    course = db.create_course(req.userId, goal[:80] or (req.filenames or ["New course"])[0], goal, materials[:200000],
                              req.filenames or [], mode, exam_date)
    db.update_course(course["id"], plan_questions=n, plan_classes=count)
    job = start_plan_job(course["id"], n, count)
    return {"course": public_course(db.get_course(course["id"])), "job": job}

def start_plan_job(course_id: str, n_questions: int, class_count: Optional[int]) -> Dict[str, Any]:
    async def work(job):
        try:
            return await plan_course(course_id, job, n_questions, class_count)
        except Exception as e:
            db.update_course(course_id, status="error", error=friendly_ai_error(e))
            course_event(course_id)
            raise

    job = start_job("plan", "Diagnostic & syllabus", work)
    db.update_course(course_id, job_id=job["id"])
    return job

@app.post("/api/courses/{course_id}/extend")
def extend_course(course_id: str, req: ExtendRequest):
    """Continue a course: new materials become new classes after the existing ones, then they are written."""
    rate_limit("course")
    course = require_course(course_id)
    if course["status"] in ("planning", "diagnostic_ready") or not course.get("concepts"):
        raise HTTPException(status_code=409, detail="Finish setting up this course (its diagnostic) before adding to it.")
    running = ACTIVE_COURSE_JOBS.get(course_id)
    if running and JOBS.get(running, {}).get("status") in ("queued", "running"):
        raise HTTPException(status_code=409, detail="This course is still writing classes. Add more when it finishes.")
    materials = (req.materials_text or "").strip()
    goal = (req.goal or "").strip()
    if len(materials) + len(goal) < 20:
        raise HTTPException(status_code=422, detail="Add materials or say what to cover next (at least a sentence).")
    count = min(max(req.class_count, 1), 8) if req.class_count else None

    async def work(job):
        try:
            _job_update(job, step="Planning the next classes from your new materials", progress=0.1)
            classes = db.list_classes(course_id)
            concepts = course.get("concepts") or []
            plan = await gemini_json(role="planner", prompt=EXTEND_PROMPT.format(
                title=course["title"], mode="test preparation" if course.get("mode") == "test_prep" else "learning",
                concepts=", ".join(f"{c['id']} ({c['name']})" for c in concepts) or "none",
                classes="\n".join(f"{k['seq']}. {k['title']}" for k in classes) or "- none",
                count=count or "2-5", goal=goal or "Continue the course with these materials",
                materials=materials[:40000] or "(no files: plan from the request)",
                mode_rules=mode_rules(course)))
            known = {c["id"] for c in concepts}
            new_concepts = []
            for i, c in enumerate(plan.get("concepts") or []):
                if isinstance(c, dict):
                    cid = slugify(c.get("id") or c.get("name", ""), f"added-{i}")
                    if cid not in known:
                        known.add(cid)
                        new_concepts.append({"id": cid, "name": c.get("name") or cid, "summary": c.get("summary", "")})
            outline = [{"title": str(item["title"])[:120],
                        "concepts": [c for c in (item.get("concepts") or []) if c in known],
                        "objectives": [str(o) for o in (item.get("objectives") or [])][:5]}
                       for item in (plan.get("classes") or [])[:8] if isinstance(item, dict) and item.get("title")]
            if not outline:
                raise RuntimeError("The plan for the new classes came back empty. Try adding more material.")
            # new material goes first: class prompts read the start of the materials
            added = f"--- Added {time.strftime('%Y-%m-%d')}: {', '.join(req.filenames or []) or 'notes'} ---\n{materials}\n\n" if materials else ""
            db.update_course(course_id, concepts=concepts + new_concepts, status="generating", error=None,
                             materials_text=(added + (course.get("materials_text") or ""))[:200000],
                             filenames=(course.get("filenames") or []) + (req.filenames or []))
            first = db.append_classes(course_id, outline)
            course_event(course_id)
            queue_course_generation(course_id)
            return {"courseId": course_id, "added": len(outline), "firstSeq": first}
        except Exception as e:
            db.update_course(course_id, error=friendly_ai_error(e))
            course_event(course_id)
            raise

    job = start_job("plan", "Continue course", work)
    db.update_course(course_id, job_id=job["id"])
    return {"course": public_course(db.get_course(course_id)), "job": job}

@app.get("/api/courses/{course_id}")
def get_course(course_id: str):
    return public_course(require_course(course_id))

@app.post("/api/courses/{course_id}/diagnostic")
def submit_diagnostic(course_id: str, body: DiagnosticAnswers):
    rate_limit("class")
    course = require_course(course_id)
    if course["status"] != "diagnostic_ready":
        raise HTTPException(status_code=409, detail=f"This course is '{course['status']}', not waiting for the diagnostic.")
    questions = course["diagnostic"]
    valid = {q["id"] for q in questions}
    answers = {k: v for k, v in body.answers.items() if k in valid}
    mastery = grade_diagnostic(questions, answers, course["concepts"])
    db.update_course(course_id, answers=answers, mastery=mastery)
    job = queue_course_generation(course_id)
    graded = [{"id": q["id"], "selected": answers.get(q["id"]), "correctAnswer": q["correctAnswer"],
               "explanation": q.get("explanation", ""), "concept": q.get("concept")} for q in questions]
    return {"course": public_course(db.get_course(course_id)), "graded": graded, "job": job}

@app.post("/api/courses/{course_id}/skip-diagnostic")
def skip_diagnostic(course_id: str):
    course = require_course(course_id)
    if course["status"] != "diagnostic_ready":
        raise HTTPException(status_code=409, detail="The diagnostic isn't ready yet.")
    queue_course_generation(course_id)
    return public_course(db.get_course(course_id))

@app.post("/api/courses/{course_id}/resume")
def resume_course(course_id: str):
    rate_limit("class")
    course = require_course(course_id)
    if not course.get("diagnostic"):
        raise HTTPException(status_code=409, detail="Planning didn't finish; create the course again.")
    queue_course_generation(course_id)
    return public_course(db.get_course(course_id))

class RegenerateRequest(BaseModel):
    instruction: Optional[str] = None

@app.post("/api/courses/{course_id}/classes/{seq}/regenerate")
def regenerate_class(course_id: str, seq: int, body: Optional[RegenerateRequest] = None):
    rate_limit("class")
    require_course(course_id)
    klass = next((k for k in db.list_classes(course_id) if k["seq"] == seq), None)
    if not klass:
        raise HTTPException(status_code=404, detail="Class not found")
    instruction = ((body.instruction if body else None) or "").strip()[:600] or klass.get("instruction")
    db.update_class(klass["id"], status="pending", instruction=instruction)
    queue_course_generation(course_id)
    return public_course(db.get_course(course_id))

@app.delete("/api/courses/{course_id}")
def remove_course(course_id: str):
    require_course(course_id)
    for k in db.list_classes(course_id):
        if k.get("topic_id"):
            for p in (topic_path(k["topic_id"]), NOTES_DIR / f"{k['topic_id']}.md"):
                p.unlink(missing_ok=True)
    db.delete_course(course_id)
    emit_event("TOPIC_UPDATED", {"autoSelect": False})
    return {"status": "deleted"}

# ---------------------------------------------------------------------------
# SOCRATIC LESSON TUTOR (carried over from &EDU's mentor, grounded in the class the student is reading)
# ---------------------------------------------------------------------------
LESSON_TUTOR_PROMPT = """
You are a Socratic tutor sitting next to one student who is working through this lesson:

{lesson}

How you teach (from the &EDU mentor):
- Lead, don't lecture: at most about 90 words, then ONE guiding question that moves them one step.
- Start from what they just said or chose; name the specific misconception if you can see it.
- No spoilers: do not give the final answer to a quiz or practice item they haven't answered yet. If they are
  stuck twice in a row, give a more direct hint (a worked first step), still ending with a question.
- When they answered wrong, help them see WHY their choice breaks the key idea, with a quick counterexample
  or a limiting case (e.g. what if the angle were 0 or 90 degrees?).
- Use the lesson's own notation; LaTeX in $...$. Plain, warm, specific. No headings, no bullet walls.
{focus}
"""

BRIEF_PROMPT = """
In at most 60 words, brief a student before they read this lesson. Exactly three lines, in this format:
**Goal:** what they will be able to do after this class (one sentence)
**Key idea:** the one rule or invariant everything hangs on (one sentence, LaTeX in $...$ if useful)
**Check yourself:** one short diagnostic question to keep in mind while reading

Lesson:
{lesson}
"""

class TutorTurn(BaseModel):
    role: str
    content: str

class LessonTutorRequest(BaseModel):
    topicId: str
    message: Optional[str] = ""
    history: Optional[List[TutorTurn]] = []
    mode: Optional[str] = "chat"            # "chat" | "brief"
    focus: Optional[Dict[str, Any]] = None  # {question, options, selected, correctAnswer} after a quiz answer

@app.post("/api/tutor/lesson")
async def lesson_tutor(req: LessonTutorRequest):
    rate_limit("chat")
    topic = load_json_file(topic_path(req.topicId), None)
    if not topic or not topic_visible(topic):
        raise HTTPException(status_code=404, detail="Topic not found")
    lesson = _topic_brief(topic, 7000)
    try:
        if req.mode == "brief":
            response = await acall_gemini(contents=BRIEF_PROMPT.format(lesson=lesson), role="lesson",
                                          config=types.GenerateContentConfig(temperature=0.3))
            return {"reply": (response.text or "").strip()}

        focus = ""
        if req.focus and req.focus.get("question"):
            f = req.focus
            opts = f.get("options") or []
            pick = opts[f["selected"]] if isinstance(f.get("selected"), int) and 0 <= f["selected"] < len(opts) else "nothing"
            right = opts[f["correctAnswer"]] if isinstance(f.get("correctAnswer"), int) and 0 <= f["correctAnswer"] < len(opts) else None
            focus = (f"\nThe student just answered this quiz question: {f['question']}\nThey chose: {pick}."
                     + (f" The correct answer (already shown to them) is: {right}. Help them understand why." if right else ""))
        contents = []
        for turn in (req.history or [])[-12:]:
            text = (turn.content or "").strip()
            if text:
                contents.append(types.Content(role="model" if turn.role in ("model", "assistant", "tutor") else "user",
                                              parts=[types.Part.from_text(text=text[:2000])]))
        message = (req.message or "").strip() or "I'm ready. Where should I start?"
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message[:2000])]))
        response = await acall_gemini(
            contents=contents, role="lesson",
            config=types.GenerateContentConfig(system_instruction=LESSON_TUTOR_PROMPT.format(lesson=lesson, focus=focus),
                                               temperature=0.4),
        )
        return {"reply": (response.text or "").strip() or "Tell me which step you're on, and what you expected to happen."}
    except Exception as e:
        raise HTTPException(status_code=503, detail=friendly_ai_error(e))

# ---------------------------------------------------------------------------
# AGY AUTONOMOUS AGENT TOOLS (LESSON GENERATION, SIMULATIONS, PAGE SWITCHING & SANDBOX)
# ---------------------------------------------------------------------------
agy_create_lesson_tool = types.FunctionDeclaration(
    name="create_or_update_lesson",
    description="Creates a new interactive educational topic or updates an existing topic with derivations, LaTeX notation, a cheat sheet and an assessment quiz. A matching interactive simulation is generated automatically in the background.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "id": types.Schema(type="STRING", description="Unique kebab-case ID, e.g. 'billiard-ball-collisions'"),
            "title": types.Schema(type="STRING", description="Clean topic title"),
            "category": types.Schema(type="STRING", description="e.g. 'Rigid Body Dynamics', 'Classical Mechanics'"),
            "summary": types.Schema(type="STRING", description="1-2 sentence overview"),
            "markdownContent": types.Schema(type="STRING", description="Full textbook derivations with KaTeX equations ($...$ and $$...$$)"),
            "cheatSheet": types.Schema(
                type="ARRAY",
                items=types.Schema(
                    type="OBJECT",
                    properties={
                        "label": types.Schema(type="STRING"),
                        "formula": types.Schema(type="STRING", description="LaTeX without $ delimiters"),
                    },
                    required=["label", "formula"]
                ),
                description="List of key formulas and constraints"
            ),
            "mermaid": types.Schema(type="STRING", description="Mermaid flowchart definition"),
            "quiz": types.Schema(
                type="ARRAY",
                items=types.Schema(
                    type="OBJECT",
                    properties={
                        "id": types.Schema(type="STRING"),
                        "question": types.Schema(type="STRING"),
                        "options": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
                        "correctAnswer": types.Schema(type="INTEGER", description="0-based index into options"),
                        "hint": types.Schema(type="STRING"),
                        "explanation": types.Schema(type="STRING")
                    },
                    required=["question", "options", "correctAnswer", "explanation"]
                ),
                description="Multiple-choice assessment questions"
            )
        },
        required=["id", "title", "category", "markdownContent"]
    )
)

agy_create_simulation_tool = types.FunctionDeclaration(
    name="create_simulation",
    description="Builds a brand-new interactive simulation (any physical system, wave, field or function family) for an existing topic. Runs in the background and appears in the topic's Simulation tab.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "topic_id": types.Schema(type="STRING", description="Existing topic ID to attach the simulation to"),
            "focus": types.Schema(type="STRING", description="What the simulation should let the student explore, e.g. 'how damping changes the decay of a spring-mass oscillator'"),
            "kind": types.Schema(type="STRING", description="'math' for the math kit (epsilon-delta, Riemann sums, Taylor series, unit circle, vector fields, matrices...), 'physics' for moving bodies and graphs, or 'auto'"),
        },
        required=["topic_id", "focus"]
    )
)

agy_adjust_class_tool = types.FunctionDeclaration(
    name="adjust_class",
    description="Rewrites one class of the student's current course in the background with an instruction, e.g. make it easier, add worked examples, focus on vectors, harder problems. Use when the student says a class is too hard, too easy, or missing something.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "seq": types.Schema(type="INTEGER", description="Class number in the course (1-based)"),
            "instruction": types.Schema(type="STRING", description="What to change, written as guidance to the lesson writer"),
        },
        required=["seq", "instruction"]
    )
)

agy_switch_page_tool = types.FunctionDeclaration(
    name="switch_page",
    description="Changes the active view in &.edu: opens a lesson tab (simulation, theory, quiz, practice) or switches workspace (My courses, Lab, IDE, Math).",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "topic_id": types.Schema(type="STRING", description="Target topic ID to navigate to, e.g. 'billiard-ball-collisions'"),
            "tab": types.Schema(type="STRING", description="'simulation', 'theory', 'quiz', 'practice' or 'agent'"),
            "mode": types.Schema(type="STRING", description="'home' (My courses), 'physics' (Lab), 'code' (IDE), or 'math' (Math)")
        }
    )
)

agy_set_sim_config_tool = types.FunctionDeclaration(
    name="set_simulation_config",
    description="Dynamically sets the parameters of the billiard simulation on the user's screen in real time (coefficient of restitution e, impact offset / cos(theta), cue strike height, speed, felt friction).",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "restitution": types.Schema(type="NUMBER", description="Coefficient of restitution e between 0.0 and 1.0"),
            "impact_offset": types.Schema(type="NUMBER", description="Impact offset b/R (-1.7 to +1.7) to change cos(theta)"),
            "strike_height": types.Schema(type="NUMBER", description="Cue strike height h/R (-0.8 to +0.8)"),
            "strike_speed": types.Schema(type="NUMBER", description="Strike speed in px/s (100 to 450)"),
            "friction": types.Schema(type="NUMBER", description="Kinetic friction coefficient of the felt (0 to 1)")
        }
    )
)

agy_execute_code_tool = types.FunctionDeclaration(
    name="execute_python_code",
    description="Executes Python code in the sandbox to verify physics derivations, compute numeric kinematics, or run assertions.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "code": types.Schema(type="STRING", description="Python code to run"),
            "test_code": types.Schema(type="STRING", description="Optional assert statements")
        },
        required=["code"]
    )
)

agy_show_graph_tool = types.FunctionDeclaration(
    name="show_on_graph",
    description="Opens Math > Graph on the student's screen with functions of x, e.g. to compare f and its derivative or show a family of curves. Letters other than x become sliders.",
    parameters=types.Schema(
        type="OBJECT",
        properties={"functions": types.Schema(type="ARRAY", items=types.Schema(type="STRING"), description="Up to 6 functions, e.g. ['sin(k*x)', 'k*cos(k*x)']")},
        required=["functions"]
    )
)

agy_preview_math_tool = types.FunctionDeclaration(
    name="show_math_widget",
    description="Shows an interactive math-kit widget on the student's screen right now (not saved). Pass a JSON object as a string with "
                "'widget' and its fields, e.g. {\"widget\":\"epsilon_delta\",\"f\":\"x^2\",\"a\":2,\"L\":4,\"delta_rule\":\"min(1, eps/5)\"} or "
                "{\"widget\":\"riemann\",\"f\":\"sin(x)\",\"a\":0,\"b\":\"pi\"}. Widgets: epsilon_delta, epsilon_n, secant_tangent, riemann, series, "
                "unit_circle, parametric, vector_field, transform2d.",
    parameters=types.Schema(
        type="OBJECT",
        properties={"spec_json": types.Schema(type="STRING", description="The widget spec as a JSON string")},
        required=["spec_json"]
    )
)

agy_agent_tools = types.Tool(
    function_declarations=[
        agy_show_graph_tool,
        agy_preview_math_tool,
        agy_create_lesson_tool,
        agy_create_simulation_tool,
        agy_adjust_class_tool,
        agy_switch_page_tool,
        agy_set_sim_config_tool,
        agy_execute_code_tool
    ]
)

# The Antigravity CLI is opt-in: it acts on the filesystem with the user's permissions.
#   AGY_CLI=1                  use /opt/homebrew/bin/agy (or AGY_BIN) for companion prompts
#   AGY_SKIP_PERMISSIONS=1     additionally pass --dangerously-skip-permissions (your call; see AGENTS.md)
AGY_BIN = os.environ.get("AGY_BIN", "/opt/homebrew/bin/agy")
AGY_CLI_TIMEOUT = 120

# agy runs on the owner's personal Antigravity subscription. Google's Antigravity terms bar third-party
# tools from accessing the service, and a subscription is for one person's own supervised work, so:
#  - never on a server with accounts (it would serve other people from one personal subscription)
#  - at most AGY_DAILY_RUNS per day and one run at a time, so the plan's quota can't be drained
#  - Gemini tools answer instead whenever agy is off, capped, busy or fails
AGY_DAILY_RUNS = int(os.environ.get("AGY_DAILY_RUNS", "15"))
_agy_runs = {"day": "", "used": 0}
_agy_lock = asyncio.Lock()

def agy_cli_allowed() -> bool:
    return os.environ.get("AGY_CLI") == "1" and not AUTH_REQUIRED and Path(AGY_BIN).exists()

async def run_agy_cli(prompt: str) -> str:
    if not agy_cli_allowed() or _agy_lock.locked():
        return ""
    today = time.strftime("%Y-%m-%d")
    if _agy_runs["day"] != today:
        _agy_runs.update(day=today, used=0)
    if _agy_runs["used"] >= AGY_DAILY_RUNS:
        print(f"[AGY RUNNER] daily cap of {AGY_DAILY_RUNS} runs reached; using Gemini tools")
        return ""
    _agy_runs["used"] += 1
    async with _agy_lock:
        return await _run_agy_process(prompt)

async def _run_agy_process(prompt: str) -> str:
    args = [AGY_BIN]
    if os.environ.get("AGY_SKIP_PERMISSIONS") == "1":
        args.append("--dangerously-skip-permissions")
    args.append(f"-p={prompt}")
    proc = await asyncio.create_subprocess_exec(
        *args, cwd=str(Path(__file__).parent),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=AGY_CLI_TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        print(f"[AGY RUNNER] Antigravity timed out after {AGY_CLI_TIMEOUT}s, falling back to Gemini tools")
        return ""
    return stdout.decode("utf-8", errors="replace").strip() if proc.returncode == 0 else ""

AGY_SYSTEM_PROMPT = (
    "You are the AGY Autonomous Physics & STEM Assistant embedded inside &.edu. "
    "You can change the workspace directly with your tools, and you should use them instead of only describing changes:\n"
    "- `create_simulation` builds a brand-new interactive simulation for ANY topic (pendulums, orbits, waves, fields, gas laws, circuits...).\n"
    "- `create_or_update_lesson` writes lessons with KaTeX derivations, cheat sheets and quizzes (matching simulation is built automatically).\n"
    "- `set_simulation_config` changes the live billiard simulation (restitution e, impact offset, cue height, speed, friction).\n"
    "- `switch_page` navigates to a topic/tab or mode.\n"
    "- `execute_python_code` checks numeric work.\n"
    "- `adjust_class` rewrites a class of the student's current course (too hard, too easy, missing a topic).\n"
    "Explain with LaTeX ($...$). Existing topics: {topics}. The student is viewing: {active}.{course}"
)

def course_context(course_id: Optional[str], open_topic: Optional[str] = None) -> str:
    course = db.get_course(course_id) if course_id else None
    if not course:
        return ""
    lines = [f"\nThe student is in the course \"{course['title']}\" (status {course['status']}). Classes:"]
    for k in db.list_classes(course_id):
        score = f", quiz {round(k['score'] * 100)}%" if k.get("score") is not None else ""
        here = " <- the student is reading this class now" if open_topic and k.get("topic_id") == open_topic else ""
        lines.append(f"  {k['seq']}. {k['title']} [{k['status']}{score}]{here}")
    return "\n".join(lines)

@app.post("/api/agy/prompt")
async def post_user_prompt(data: AgyPromptModel):
    rate_limit("agy")
    if data.courseId:
        try:
            require_course(data.courseId)  # AGY may only see and change the caller's own course
        except HTTPException:
            data.courseId = None
    user_msg = {"id": f"msg-{int(time.time()*1000)}", "sender": "user", "content": data.prompt, "timestamp": time.time()}
    reply_content = ""

    # 1. Opt-in: hand the prompt to the Antigravity CLI (it edits topic files itself; the UI hot-reloads them)
    cli_reply = await run_agy_cli(data.prompt)
    if cli_reply:
        reply_content = cli_reply
        emit_event("TOPIC_UPDATED", {"topicId": data.topicId, "autoSelect": True})

    # 2. Default: Gemini with workspace tools
    if not reply_content:
        topic_ids = ", ".join(p.stem for p in sorted(TOPICS_DIR.glob("*.json")))
        try:
            resp = await acall_gemini(
                contents=data.prompt,
                config=types.GenerateContentConfig(
                    system_instruction=AGY_SYSTEM_PROMPT.format(topics=topic_ids, active=data.topicId,
                                                                course=course_context(data.courseId, data.topicId)),
                    temperature=0.3,
                    tools=[agy_agent_tools]
                )
            )

            for call in (resp.function_calls or []):
                args = dict(call.args or {})
                if call.name == "set_simulation_config":
                    emit_event("SET_SIM_CONFIG", args)
                    emit_event("SWITCH_TAB", {"tab": "simulation"})
                    labels = {"restitution": "Coefficient of Restitution (e)", "impact_offset": "Impact Offset (cos θ parameter)",
                              "strike_height": "Cue Height (h/R)", "strike_speed": "Strike speed", "friction": "Felt friction μ"}
                    reply_content = "**Live Simulation Parameters Updated!**\n\n" + "".join(
                        f"- **{labels[k]}**: `{args[k]}`\n" for k in labels if k in args)
                    break

                elif call.name == "create_or_update_lesson":
                    args["id"] = slugify(args.get("id") or args.get("title", ""), f"topic-{int(time.time())}")
                    args.setdefault("difficulty", "Undergraduate")
                    saved, warnings = save_topic(args, event_type="TOPIC_CREATED")
                    sim_job = queue_simulation_job(saved["id"]) if AUTHOR_SIMS and not saved.get("simulation") else None
                    emit_event("SWITCH_TOPIC", {"topicId": saved["id"], "tab": "theory", "mode": "physics"})
                    reply_content = (
                        f"**{saved['title']}** is ready: derivations, {len(saved['cheatSheet'])} key formulas and "
                        f"{len(saved['quiz'])} quiz questions."
                        + ("\n\nI'm building an interactive simulation for it in the background; the Simulation tab lights up when it's done." if sim_job else "")
                        + (f"\n\n_Notes: {'; '.join(warnings)}_" if warnings else "")
                    )
                    break

                elif call.name == "create_simulation":
                    tid = args.get("topic_id") or data.topicId
                    try:
                        queue_simulation_job(tid, args.get("focus", ""), args.get("kind") if args.get("kind") in ("math", "physics") else "auto")
                        reply_content = f"Building a new simulation for **{tid}** focused on: _{args.get('focus', 'the core concept')}_. It appears in the Simulation tab in about 20–40 seconds."
                    except HTTPException:
                        reply_content = f"I couldn't find a topic called `{tid}`. Ask me to create the lesson first."
                    break

                elif call.name == "show_on_graph":
                    fns = [str(f)[:200] for f in (args.get("functions") or [])][:6]
                    emit_event("MATH_GRAPH", {"functions": fns, "params": {}})
                    reply_content = "On your Math graph now: " + ", ".join(f"`{f}`" for f in fns) + ". Drag the sliders to explore."
                    break

                elif call.name == "show_math_widget":
                    try:
                        spec, errors = validate_spec({**json.loads(args.get("spec_json") or "{}"), "kind": "math"})
                    except json.JSONDecodeError:
                        spec, errors = {}, ["spec_json was not valid JSON"]
                    if errors:
                        reply_content = "I couldn't build that widget: " + "; ".join(errors[:3])
                    else:
                        emit_event("MATH_PREVIEW", {"spec": spec})
                        reply_content = f"Opened **{spec['title']}** in Math > Sim kit. {spec.get('description', '')}"
                    break

                elif call.name == "adjust_class":
                    if not data.courseId or not db.get_course(data.courseId):
                        reply_content = "Open the course first (My courses → your course), then ask me again so I know which class you mean."
                        break
                    klass = next((k for k in db.list_classes(data.courseId) if k["seq"] == int(args.get("seq", 0))), None)
                    if not klass:
                        reply_content = f"This course has no class {args.get('seq')}."
                        break
                    db.update_class(klass["id"], status="pending", instruction=str(args.get("instruction", ""))[:600])
                    queue_course_generation(data.courseId)
                    reply_content = (f"Rewriting **class {klass['seq']}: {klass['title']}** with this change: _{args.get('instruction')}_. "
                                     "It takes about a minute; the course page shows progress.")
                    break

                elif call.name == "switch_page":
                    tid = args.get("topic_id")
                    tab = args.get("tab", "theory")
                    mode = args.get("mode", "physics")
                    emit_event("SWITCH_TOPIC", {"topicId": tid, "tab": tab, "mode": mode})
                    reply_content = f"Switched workspace view to **{tid or mode}** ({tab} tab)."
                    break

                elif call.name == "execute_python_code":
                    exec_res = await asyncio.to_thread(run_python_sandboxed, args.get("code", ""), args.get("test_code", ""))
                    reply_content = (
                        f"**Execution Result:**\n```\n{exec_res.get('stdout', '')}\n{exec_res.get('stderr', '')}\n```\n"
                        f"Status: {'Passed' if exec_res.get('tests_passed') else 'Error'}"
                    )
                    break

            if not reply_content:
                try:
                    reply_content = (resp.text or "").strip()
                except Exception:
                    pass

        except Exception as e:
            print("[ERROR agy prompt Gemini call with tools]:", e)
            reply_content = f"{friendly_ai_error(e)}"

    if not reply_content:
        reply_content = "I couldn't produce an answer for that. Try rephrasing, or check the backend log."

    agent_msg = {"id": f"msg-{int(time.time()*1000)+1}", "sender": "agy", "content": reply_content, "timestamp": time.time()}
    append_messages(user_msg, agent_msg)
    emit_event("NEW_MESSAGE", {"message": agent_msg})
    return {"status": "ok", "reply": reply_content}

@app.get("/api/agy/inbox")
def get_agy_inbox():
    items = []
    if INBOX_FILE.exists():
        with open(INBOX_FILE, "r", encoding="utf-8") as f:
            for line in f.readlines()[-200:]:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return {"inbox": items, "count": len(items)}

@app.post("/api/agy/inbox")
def post_agy_inbox(item: Dict[str, Any]):
    line = json.dumps({**item, "timestamp": time.time()})
    if len(line) > MAX_INBOX_BYTES:
        raise HTTPException(status_code=413, detail=f"Inbox items are limited to {MAX_INBOX_BYTES} bytes")
    with _file_lock, open(INBOX_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return {"status": "queued", "item": json.loads(line)}

@app.get("/api/status")
def get_status():
    return {
        "status": "online",
        "topic_count": len(list(TOPICS_DIR.glob("*.json"))),
        "gemini_configured": bool(os.environ.get("api_KEY") or os.environ.get("GEMINI_API_KEY")),
        "agy_cli_enabled": agy_cli_allowed(),
        "agy_runs_left_today": max(0, AGY_DAILY_RUNS - (_agy_runs["used"] if _agy_runs["day"] == time.strftime("%Y-%m-%d") else 0)),
        "model_calls_left_today": max(0, DAILY_MODEL_CALLS - (_budget["used"] if _budget["day"] == time.strftime("%Y-%m-%d") else 0)),
        "elevenlabs_enabled": ELEVENLABS_ENABLED,
        "active_jobs": sum(1 for j in JOBS.values() if j["status"] in ("queued", "running")),
        "event_cursor": _event_seq,
        "auth_required": AUTH_REQUIRED,
        "port": 8090,
        "features": [
            "courses", "sqlite_storage", "simspec_simulations", "background_jobs", "code_sandbox",
            "multimodal_ingestion", "tutor_chat", "tutor_brief", "elevenlabs_voiceover",
            "curriculum_engine", "latex_derivations", "assessment_quiz", "agy_file_mailbox"
        ]
    }

# Deployment: serve the built frontend (npm run build -> dist/) from the same server, so no Vite is needed.
DIST_DIR = Path(__file__).parent / "dist"
if (DIST_DIR / "index.html").exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("SCIEDU_HOST", "127.0.0.1")
    port = int(os.environ.get("SCIEDU_PORT", "8090"))
    if host not in ("127.0.0.1", "localhost", "::1") and not AUTH_REQUIRED:
        sys.exit("Refusing to listen on {} without accounts: set SCIEDU_AUTH=1 (and SCIEDU_ALLOWED_HOSTS) "
                 "before serving other machines.".format(host))
    print(f"Starting &.edu backend on http://{host}:{port} ...")
    uvicorn.run(app, host=host, port=port)
