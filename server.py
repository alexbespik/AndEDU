import os
import io
import json
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File
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

MODEL_ID = "gemini-3.1-flash-lite"

# ----------------- MCP TOOLS (CODE BLOCKS & TUTOR MUTATION) -----------------
block_puzzle_tool = types.FunctionDeclaration(
    name="build_block_puzzle",
    description="Generate a gamified block construction puzzle with concept notes and a pool of scrambled code blocks.",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "title": types.Schema(type="STRING", description="Exercise title"),
            "domain": types.Schema(type="STRING", description="e.g. Python, Math, Shell, Logic"),
            "briefing_markdown": types.Schema(type="STRING", description="Theory briefing explaining the concept before starting"),
            "guiding_question": types.Schema(type="STRING", description="What the student must construct"),
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
        required=["title", "domain", "briefing_markdown", "guiding_question", "blocks_pool", "correct_blocks", "explanation", "test_cases"]
    )
)

tutor_tools = types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="change_assignment",
        description="Call this tool when the student asks for another problem, asks to make it easier/harder, or is stuck.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "reason": types.Schema(type="STRING", description="Why the assignment is being changed"),
                "new_topic": types.Schema(type="STRING", description="New topic or easier scaffolding step")
            },
            required=["reason", "new_topic"]
        )
    )
])

generation_tools = types.Tool(function_declarations=[block_puzzle_tool])

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
You are a strict Socratic tutor for '&edu'.
Rules:
1. Strict No-Spoilers: Never give the direct sequence or code unless user types '!reveal'.
2. Ask leading questions and guide via counter-examples. Keep replies under 150 words.
3. Assignment Changes: If the student asks for a new problem, simpler exercise, or changes direction, you MUST call `change_assignment`.
"""

class GeneratePayload(BaseModel):
    user_instruction: str
    document_text: Optional[str] = ""

@app.post("/api/generate-puzzle")
async def generate_puzzle(payload: GeneratePayload):
    doc_context = payload.document_text.strip() if payload.document_text else "No uploaded document."
    
    prompt = f"""
    Create a gamified code/math block assembly challenge.
    === CONTEXT ===
    {doc_context[:10000]}
    === END CONTEXT ===

    User Request: "{payload.user_instruction}"

    REQUIREMENTS:
    - Split code or formulas into 3 to 6 distinct modular blocks (e.g. lines, functions, or pipeline stages).
    - Provide a `blocks_pool` with scrambled blocks and 1-2 plausible distractors.
    - Provide `correct_blocks` in valid execution order.
    - Call the `build_block_puzzle` tool.
    """

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[generation_tools],
            tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="ANY"))
        )
    )

    for call in response.function_calls:
        if call.name == "build_block_puzzle":
            return dict(call.args)

    return {"error": "Failed to create puzzle."}

@app.post("/api/upload-multimodal")
async def upload_multimodal(file: UploadFile = File(...)):
    file_bytes = await file.read()
    filename = file.filename.lower()
    ext = filename.split('.')[-1]

    if ext in ["png", "jpg", "jpeg", "webp"]:
        mime_type = f"image/{ext if ext != 'jpg' else 'jpeg'}"
        img_part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
        prompt = "Analyze this image (equation, code, or document) and create a gamified block construction puzzle from it."
        
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[img_part, prompt],
            config=types.GenerateContentConfig(
                tools=[generation_tools],
                tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="ANY"))
            )
        )
        for call in response.function_calls:
            if call.name == "build_block_puzzle":
                res = dict(call.args)
                res["filename"] = file.filename
                return res

    raw_text = extract_text_from_file(file_bytes, file.filename)
    return {"filename": file.filename, "extracted_text": raw_text}

class ChatPayload(BaseModel):
    puzzle_context: Dict[str, Any]
    history: List[Dict[str, str]]
    message: str

@app.post("/api/tutor-chat")
async def tutor_chat(payload: ChatPayload):
    system_text = f"{SOCRATIC_PROMPT}\nCURRENT ASSIGNMENT:\n{json.dumps(payload.puzzle_context)}"
    
    contents = [
        types.Content(role=m["role"], parts=[types.Part.from_text(text=m["content"])]) 
        for m in payload.history
    ]
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=payload.message)]))

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_text,
            temperature=0.3,
            tools=[tutor_tools]
        )
    )

    if response.function_calls:
        for call in response.function_calls:
            if call.name == "change_assignment":
                args = dict(call.args)
                new_puzzle = await generate_puzzle(GeneratePayload(
                    user_instruction=f"Scaffolding unit: {args['new_topic']}",
                    document_text=""
                ))
                return {
                    "reply": f"🔄 **Assignment Adjusted**: {args['reason']}. I've loaded a new puzzle for you!",
                    "mutated_puzzle": new_puzzle
                }

    return {"reply": response.text}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)