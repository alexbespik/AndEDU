import os
import io
import json
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pypdf import PdfReader
import docx
import nbformat

load_dotenv()
client = genai.Client(api_key=os.environ.get("api_KEY", os.environ.get("GEMINI_API_KEY")))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- MULTI-FORMAT DOCUMENT EXTRACTOR -----------------
def extract_document_text(file_bytes: bytes, filename: str) -> str:
    ext = filename.lower().split('.')[-1]
    
    if ext in ["txt", "md", "py", "sh", "json", "csv"]:
        return file_bytes.decode("utf-8", errors="ignore")
    
    elif ext == "pdf":
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)
    
    elif ext == "docx":
        doc = docx.Document(io.BytesIO(file_bytes))
        return "\n".join([p.text for p in doc.paragraphs if p.text])
    
    elif ext == "ipynb":
        notebook = nbformat.reads(file_bytes.decode("utf-8", errors="ignore"), as_version=4)
        cells = []
        for cell in notebook.cells:
            if cell.cell_type in ["code", "markdown"]:
                cells.append(cell.source)
        return "\n\n".join(cells)
    
    else:
        raise ValueError(f"Unsupported file type: .{ext}")

# ----------------- VERSATILE MCP TOOLS -----------------
# 1. Command Line / Bash Tool
cli_tool = types.FunctionDeclaration(
    name="create_cli_puzzle",
    description="For terminal commands, Linux shell scripting, bash pipes, regex, or system tools.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "title": types.Schema(type="STRING", description="e.g. 'Piping grep to sort'"),
            "topic": types.Schema(type="STRING", description="e.g. 'Command Line / Bash'"),
            "guiding_question": types.Schema(type="STRING"),
            "code_template": types.Schema(type="STRING", description="Command snippet with {{SLOT}}, e.g.: cat server.log | {{SLOT}} | sort -u"),
            "variants": types.Schema(type="ARRAY", items=types.Schema(type="STRING"), description="4 plausible flags/commands"),
            "correct_answer": types.Schema(type="STRING"),
            "explanation": types.Schema(type="STRING"),
            "test_cases": types.Schema(type="ARRAY", items=types.Schema(type="STRING"), description="Console output showing command result")
        },
        required=["title", "topic", "guiding_question", "code_template", "variants", "correct_answer", "explanation", "test_cases"]
    )
)

# 2. Math & Discrete Formulas Tool
math_tool = types.FunctionDeclaration(
    name="create_math_puzzle",
    description="For math formulas, calculus, discrete math, probability, algebra, or big-O equations.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "title": types.Schema(type="STRING", description="e.g. 'Derivative Power Rule'"),
            "topic": types.Schema(type="STRING", description="e.g. 'Calculus / Discrete Math'"),
            "guiding_question": types.Schema(type="STRING"),
            "code_template": types.Schema(type="STRING", description="Mathematical equation with {{SLOT}}, e.g.: d/dx(x^n) = {{SLOT}} * x^(n-1)"),
            "variants": types.Schema(type="ARRAY", items=types.Schema(type="STRING"), description="4 mathematical symbols or terms"),
            "correct_answer": types.Schema(type="STRING"),
            "explanation": types.Schema(type="STRING"),
            "test_cases": types.Schema(type="ARRAY", items=types.Schema(type="STRING"), description="Step-by-step verification output")
        },
        required=["title", "topic", "guiding_question", "code_template", "variants", "correct_answer", "explanation", "test_cases"]
    )
)

# 3. Universal Programming Logic Tool
code_tool = types.FunctionDeclaration(
    name="create_code_puzzle",
    description="For Python, C++, Java, algorithms, recursion, data structures, and logic invariants.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "title": types.Schema(type="STRING"),
            "topic": types.Schema(type="STRING"),
            "guiding_question": types.Schema(type="STRING"),
            "code_template": types.Schema(type="STRING", description="Code with {{SLOT}} token"),
            "variants": types.Schema(type="ARRAY", items=types.Schema(type="STRING")),
            "correct_answer": types.Schema(type="STRING"),
            "explanation": types.Schema(type="STRING"),
            "test_cases": types.Schema(type="ARRAY", items=types.Schema(type="STRING"))
        },
        required=["title", "topic", "guiding_question", "code_template", "variants", "correct_answer", "explanation", "test_cases"]
    )
)

all_edu_tools = types.Tool(function_declarations=[cli_tool, math_tool, code_tool])

# ----------------- SOCRATIC TUTOR PROMPT -----------------
SOCRATIC_PROMPT = """
You are a strict Socratic tutor for '&edu'.
Rules:
1. Strict No-Spoilers: Never supply the final answer or code block unless user types '!reveal'.
2. Assess Baseline First: Ask what they understand about the current problem.
3. Incremental Scaffolding: 1 hint or leading question per turn.
4. Error Handling: Use counter-examples or reflection rather than saying "Incorrect".
5. Keep answers under 150 words.
"""

class GeneratePayload(BaseModel):
    user_instruction: str
    document_text: Optional[str] = ""

@app.post("/api/generate-puzzle")
async def generate_puzzle(payload: GeneratePayload):
    doc_context = payload.document_text.strip() if payload.document_text else "No uploaded document."
    
    prompt = f"""
    You are an educational puzzle creator. 
    Analyze this primary document source:
    === DOCUMENT START ===
    {doc_context[:10000]}
    === DOCUMENT END ===

    User Specific Instruction: "{payload.user_instruction}"

    CRITICAL RULES:
    1. If the document is about Linux / CLI / Shell, use `create_cli_puzzle`.
    2. If the document contains equations, calculus, or discrete math, use `create_math_puzzle`.
    3. If the document is general programming, algorithms, or invariants, use `create_code_puzzle`.
    4. Base the puzzle DIRECTLY on the concepts or problems mentioned in the document!
    """

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[all_edu_tools],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="ANY")
            )
        )
    )

    for call in response.function_calls:
        if call.name in ["create_cli_puzzle", "create_math_puzzle", "create_code_puzzle"]:
            return dict(call.args)

    return {"error": "Failed to invoke an educational tool."}

@app.post("/api/upload-document")
async def upload_document(file: UploadFile = File(...)):
    file_bytes = await file.read()
    raw_text = extract_document_text(file_bytes, file.filename)
    return {
        "filename": file.filename,
        "extracted_text": raw_text
    }

class ChatPayload(BaseModel):
    puzzle_context: Dict[str, Any]
    history: List[Dict[str, str]]
    message: str

@app.post("/api/tutor-chat")
async def tutor_chat(payload: ChatPayload):
    system_text = f"{SOCRATIC_PROMPT}\nPUZZLE CONTEXT:\n{json.dumps(payload.puzzle_context)}"
    contents = [
        types.Content(role=m["role"], parts=[types.Part.from_text(text=m["content"])]) 
        for m in payload.history
    ]
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=payload.message)]))

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=system_text, temperature=0.3)
    )
    return {"reply": response.text}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)