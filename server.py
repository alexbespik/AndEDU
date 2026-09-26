import os
import json
from typing import List, Dict, Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

# Initialize Gemini Client using your specific env variable
client = genai.Client(api_key=os.environ["api_KEY"])

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1. GENERALIZED PUZZLE MCP TOOL ---
universal_puzzle_tool = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="create_universal_puzzle",
            description="Generate an interactive code/math puzzle with a fill-in slot anywhere in the snippet.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "title": types.Schema(type="STRING", description="Short title, e.g. 'Binary Search Invariant'"),
                    "topic": types.Schema(type="STRING", description="Category: Loops, Math, Recursion, Trees, etc."),
                    "guiding_question": types.Schema(type="STRING", description="Pedagogical challenge question"),
                    "code_template": types.Schema(
                        type="STRING", 
                        description="Code or formula containing exactly one '{{SLOT}}' token where the blank goes."
                    ),
                    "variants": types.Schema(
                        type="ARRAY",
                        items=types.Schema(type="STRING"),
                        description="4 plausible options (1 correct, 3 distractors/mutants)"
                    ),
                    "correct_answer": types.Schema(type="STRING", description="The exact correct token"),
                    "explanation": types.Schema(type="STRING", description="Conceptual breakdown of why this works"),
                    "test_cases": types.Schema(
                        type="ARRAY",
                        items=types.Schema(type="STRING"),
                        description="Simulated terminal output demonstrating execution"
                    )
                },
                required=["title", "topic", "guiding_question", "code_template", "variants", "correct_answer", "explanation", "test_cases"]
            )
        )
    ]
)

# --- 2. STRICT SOCRATIC SYSTEM INSTRUCTION ---
SOCRATIC_SYSTEM_PROMPT = """
You are a strict Socratic tutor and mentor for the '&edu' platform. 
Your objective is to help the student understand problems and derive solutions independently without ever doing the work for them.

### Core Operating Rules:
1. Strict No-Spoilers Policy:
   - Never provide the final answer, complete solution, or full code block under any circumstances.
   - Do not complete steps for the student unless they explicitly command: "!reveal".
2. Assess Baseline First:
   - When presented with a problem or student query, first ask what they understand or what their initial approach is.
   - Do not begin lecturing until you identify where their mental model breaks down.
3. Incremental Scaffolding:
   - Break multi-step problems down into single logical checkpoints.
   - Give at most ONE targeted hint, leading question, or foundational concept per reply.
   - If stuck on syntax/math, isolate the underlying rule or invariant rather than pointing out the line or value.
4. Error Handling via Reflection:
   - If the student makes an error, do not immediately say "That is incorrect."
   - Present a counter-example, ask an edge-case question, or guide them to trace their logic until they spot the contradiction.
5. Confirmation Loop:
   - Require the student to answer the current guiding question or confirm the concept before moving forward.
   - Keep replies concise (under 150 words) to maintain an interactive dialogue.
"""

class GenerateRequest(BaseModel):
    notes_or_topic: str

class ChatMessage(BaseModel):
    role: str # "user" or "model"
    content: str

class ChatRequest(BaseModel):
    puzzle_context: Dict[str, Any]
    history: List[ChatMessage]
    message: str

@app.post("/api/generate-puzzle")
async def generate_puzzle(req: GenerateRequest):
    prompt = f"""
    Create an educational puzzle based on these notes or topic:
    {req.notes_or_topic}

    Use the `create_universal_puzzle` tool. The `code_template` can be Python, pseudo-code, math expressions, or algorithms.
    Ensure `code_template` contains the exact token '{{{{SLOT}}}}' where the critical missing piece belongs.
    """

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[universal_puzzle_tool],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="ANY")
            )
        )
    )

    for call in response.function_calls:
        if call.name == "create_universal_puzzle":
            return dict(call.args)

    return {"error": "Failed to call puzzle tool."}

@app.post("/api/tutor-chat")
async def tutor_chat(req: ChatRequest):
    # Prepare chat history with puzzle context
    system_context = f"{SOCRATIC_SYSTEM_PROMPT}\n\nCURRENT PUZZLE CONTEXT:\n{json.dumps(req.puzzle_context, indent=2)}"
    
    contents = []
    for msg in req.history:
        contents.append(types.Content(
            role=msg.role,
            parts=[types.Part.from_text(text=msg.content)]
        ))
    
    # Add current user message
    contents.append(types.Content(
        role="user",
        parts=[types.Part.from_text(text=req.message)]
    ))

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_context,
            temperature=0.3
        )
    )

    return {"reply": response.text}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)