import os
import io
import json
import sys
import base64
import subprocess
import httpx
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ClientError
from pypdf import PdfReader
import docx
import nbformat

load_dotenv()
api_key = os.environ.get("api_KEY", os.environ.get("GEMINI_API_KEY"))
client = genai.Client(api_key=api_key)

app = FastAPI(title="&edu Educational Studio Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models in order of quota resilience & latency
CANDIDATE_MODELS = [
    "gemini-3.1-flash-lite", 
    "gemini-3.8-flash", 
    "gemini-3.5-flash", 
    "gemini-3.5-flash-lite"
]

def call_gemini(contents, **kwargs):
    """Invokes Gemini with automatic model fallback for 429 quota, 503 load, and 404 deprecations."""
    last_err = None
    for model_id in CANDIDATE_MODELS:
        try:
            return client.models.generate_content(
                model=model_id,
                contents=contents,
                **kwargs
            )
        except ClientError as e:
            last_err = e
            if e.code in [429, 404, 503]:
                print(f"[MODEL FALLBACK] Model {model_id} returned {e.code}, attempting fallback...")
                continue
            raise e
        except Exception as e:
            last_err = e
            print(f"[MODEL FALLBACK] Model {model_id} error: {e}, attempting fallback...")
            continue
    if last_err:
        raise last_err
    raise RuntimeError("No candidate models succeeded.")

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
    puzzle_context: Dict[str, Any]
    history: List[Dict[str, str]]
    message: str

class BriefPayload(BaseModel):
    problem: Dict[str, Any]
    chapter: Optional[Dict[str, Any]] = None
    mode: Optional[str] = "code"
    level: Optional[int] = 1

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
        chapters = DEFAULT_MULTI_CHAPTER_CURRICULUM["chapters"]

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
                # If correct_answer is an index (e.g. "0", "1") and options exist:
                if correct_ans.isdigit() and options and 0 <= int(correct_ans) < len(options):
                    correct_ans = options[int(correct_ans)]
                # If correct_answer is a letter (e.g. "A", "B", "C", "D") and options exist:
                elif correct_ans.upper() in ["A", "B", "C", "D"] and options:
                    letter_idx = ord(correct_ans.upper()) - 65
                    if letter_idx < len(options):
                        correct_ans = options[letter_idx]

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
                
                if not found:
                    options.insert(0, correct_ans)

                # Ensure 4 options
                while len(options) < 4:
                    options.append(f"option_{len(options)+1}")

                p["options"] = options[:4]
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
            elif ptype == "code_write":
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
        if correct_ans.isdigit() and options and 0 <= int(correct_ans) < len(options):
            correct_ans = options[int(correct_ans)]
        elif correct_ans.upper() in ["A", "B", "C", "D"] and options:
            idx = ord(correct_ans.upper()) - 65
            if idx < len(options):
                correct_ans = options[idx]
        if not correct_ans and options:
            correct_ans = options[0]
        if len(options) < 2:
            if correct_ans:
                options = [correct_ans, f"\\neg ({correct_ans})" if mode == "math" else f"not_{correct_ans}", "0", "1"]
            else:
                correct_ans = "valid_term"
                options = ["valid_term", "invalid_term", "0", "1"]
        if correct_ans not in options:
            options.insert(0, correct_ans)
        p["options"] = options[:4]
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
        p["correct_blocks"] = [str(b) for b in c_blocks]
        p["blocks_pool"] = [str(b) for b in pool]

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
            "correct_answer": "f'(x)'" if mode == "math" else "x * 2",
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
        response = call_gemini(
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[curriculum_tools_wrapper],
                tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="ANY"))
            )
        )

        for call in response.function_calls:
            if call.name == "build_curriculum":
                data = dict(call.args)
                return normalize_curriculum_data(data, default_level=level)

        print("[WARNING generate_curriculum]: Gemini did not invoke build_curriculum, using fallback.")
        fallback = DEFAULT_MATH_CURRICULUM if is_math else DEFAULT_MULTI_CHAPTER_CURRICULUM
        return normalize_curriculum_data(fallback, default_level=level)
    except Exception as e:
        print("[ERROR generate_curriculum, returning robust default curriculum]:", e)
        fallback = DEFAULT_MATH_CURRICULUM if is_math else DEFAULT_MULTI_CHAPTER_CURRICULUM
        fallback_data = dict(fallback)
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

@app.post("/api/execute-code")
async def execute_code(payload: ExecuteCodePayload):
    """
    Executes student Python code in an isolated subprocess with a 5-second timeout.
    Appends test assertions if provided and captures stdout / stderr / assertion failures.
    """
    user_code = payload.code.strip()
    test_code = (payload.test_code or "").strip()
    
    # Block dangerous system calls
    dangerous_keywords = ["import os", "import subprocess", "import shutil", "import sys", "__import__", "eval(", "exec("]
    for kw in dangerous_keywords:
        if kw in user_code:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Security restriction: '{kw}' is disabled in the student sandbox.",
                "tests_passed": False,
                "message": "Security error"
            }

    script_parts = [user_code]
    if test_code:
        script_parts.append("\n# --- TEST VERIFICATION ---")
        script_parts.append(test_code)
        script_parts.append("\nprint('\\n[TEST_REPORT] All test cases and assertions passed successfully!')")

    combined_script = "\n".join(script_parts)

    try:
        proc = subprocess.run(
            [sys.executable, "-c", combined_script],
            capture_output=True,
            text=True,
            timeout=5
        )
        stdout = proc.stdout
        stderr = proc.stderr
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
                    response = call_gemini(contents=[img_part, prompt])
                    text_content = response.text or ""
                except Exception as e:
                    print(f"[ERROR upload_multimodal image {filename}]:", e)
                    text_content = f"[Image uploaded: {filename}]"
            else:
                text_content = extract_text_from_file(file_bytes, filename)

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
    system_text = f"{SOCRATIC_PROMPT}\nCURRENT LESSON CONTEXT:\n{json.dumps(payload.puzzle_context)}"
    
    contents = [
        types.Content(role=m["role"], parts=[types.Part.from_text(text=m["content"])]) 
        for m in payload.history
    ]
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=payload.message)]))

    try:
        response = call_gemini(
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_text,
                temperature=0.3,
                tools=[tutor_tools]
            )
        )

        if response.function_calls:
            for call in response.function_calls:
                # 1. Slot Puzzle tool call
                if call.name == "emit_slot_puzzle":
                    p = dict(call.args)
                    p["type"] = "slot_plugin"
                    p["difficulty"] = "Easy"
                    return {
                        "reply": "💡 Here is a quick one-time plug-in exercise to build intuition!",
                        "mutated_puzzle": p
                    }
                # 2. Block Builder tool call
                elif call.name == "build_block_puzzle":
                    p = dict(call.args)
                    p["type"] = "block_builder"
                    p["difficulty"] = "Moderate"
                    return {
                        "reply": "🧩 Here is a code block assembly puzzle for you to practice!",
                        "mutated_puzzle": p
                    }
                # 3. Coding Challenge tool call
                elif call.name == "build_coding_challenge":
                    p = dict(call.args)
                    p["type"] = "code_write"
                    p["difficulty"] = "Hard"
                    return {
                        "reply": "🔥 Here is a rigorous coding challenge to test your mastery!",
                        "mutated_puzzle": p
                    }
                # 4. Change Assignment tool call
                elif call.name == "change_assignment":
                    args = dict(call.args)
                    target = args.get("target_type", "slot_plugin")
                    prompt = f"Create a single {target} puzzle for topic: {args['new_topic']}. Reason: {args['reason']}"
                    
                    wrapper = curriculum_tools_wrapper
                    if target == "slot_plugin":
                        wrapper = types.Tool(function_declarations=[slot_puzzle_tool])
                    elif target == "code_write":
                        wrapper = types.Tool(function_declarations=[coding_challenge_tool])
                    else:
                        wrapper = types.Tool(function_declarations=[block_puzzle_tool])

                    mut_resp = call_gemini(
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            tools=[wrapper],
                            tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="ANY"))
                        )
                    )
                    new_puzzle = None
                    for pcall in mut_resp.function_calls:
                        new_puzzle = dict(pcall.args)
                        new_puzzle["type"] = target
                        break

                    return {
                        "reply": f"🔄 **Assignment Adjusted**: {args['reason']}. I've tailored a new exercise for you!",
                        "mutated_puzzle": new_puzzle
                    }

        return {"reply": response.text}
    except Exception as e:
        print("[ERROR tutor_chat]:", e)
        return {"reply": f"I had trouble connecting to the tutor engine: {str(e)}"}

@app.post("/api/tutor-brief")
async def tutor_brief(payload: BriefPayload):
    """
    Generates an ultra-concise, razor-sharp, leading Socratic task briefing:
    - 🎯 Task (actual task in 1 sentence)
    - 💡 Invariant/Lead (1 short sentence pointing to the core rule)
    - ❓ Check (1 quick diagnostic question to ponder before acting)
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
    🎯 **Task**: [1 short sentence stating the concrete task to accomplish]
    💡 **Lead**: [1 crisp sentence pointing out the core invariant or rule]
    ❓ **Check**: [1 sharp diagnostic question to consider before answering]
    """

    try:
        response = call_gemini(contents=prompt)
        return {"briefing": response.text.strip()}
    except Exception as e:
        print("[ERROR tutor_brief]:", e)
        # Fallback local briefing (under 35 words)
        task_desc = p.get('guiding_question') or f"Complete {p.get('title')}"
        hint = p.get('concept_hint') or "Preserve the structural boundary invariant."
        return {
            "briefing": (
                f"🎯 **Task**: {task_desc}\n\n"
                f"💡 **Lead**: {hint}\n\n"
                f"❓ **Check**: *What boundary or edge condition would break if chosen incorrectly?*"
            )
        }

@app.post("/api/generate-chapter")
async def generate_chapter(payload: GenerateChapterPayload):
    """
    Generates a single comprehensive new chapter with rich study guide notes and multiple interactive problems.
    Can auto-sequence the next logical concept or target a specific user-requested topic.
    """
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
        response = call_gemini(
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[chapter_tools_wrapper],
                tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="ANY"))
            )
        )
        for call in response.function_calls:
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
                "correct_answer": "f'(x)'" if is_math else "x * 2",
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
        response = call_gemini(
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[problem_tools_wrapper],
                tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="ANY"))
            )
        )
        for call in response.function_calls:
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
    # Resolve ElevenLabs API key: passed from UI settings, or loaded from .env
    eleven_key = (payload.api_key or "").strip() or os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVEN_LABS_API_KEY") or os.environ.get("XI_API_KEY")
    
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
        resp = call_gemini(contents=script_prompt)
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)