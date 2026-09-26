import os
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.genai import types
import os 
load_dotenv()

# Initialize Gemini Client (reads GEMINI_API_KEY from .env or environment)
client = genai.Client(api_key=os.environ["api_KEY"])

app = FastAPI()

# Enable CORS so your React frontend (port 5173/5174) can talk to this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Define the Tool for Gemini
puzzle_tool = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="create_code_puzzle",
            description="Generate a code mutation puzzle with interactive drop-in variants based on lesson materials.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "question": types.Schema(
                        type="STRING", 
                        description="Inquiry question guiding the student to solve the bug or loop safely"
                    ),
                    "code_line_1": types.Schema(type="STRING", description="First line of setup code, e.g. 'i = 1'"),
                    "loop_statement": types.Schema(type="STRING", description="Loop syntax keyword, e.g. 'while'"),
                    "code_body": types.Schema(type="STRING", description="Body of code inside the loop indented with 4 spaces"),
                    "variants": types.Schema(
                        type="ARRAY",
                        items=types.Schema(type="STRING"),
                        description="4 possible choices to place into the condition slot (1 correct, 3 distractors)"
                    ),
                    "correct_answer": types.Schema(type="STRING", description="The exact safe/correct variant"),
                    "explanation": types.Schema(type="STRING", description="Explanation of why this answer is safe and how loops behave"),
                    "safe_terminal_output": types.Schema(
                        type="ARRAY", 
                        items=types.Schema(type="STRING"),
                        description="Terminal log lines demonstrating safe execution"
                    ),
                    "unsafe_terminal_output": types.Schema(
                        type="ARRAY", 
                        items=types.Schema(type="STRING"),
                        description="Terminal log lines demonstrating an infinite crash loop warning"
                    )
                },
                required=["question", "code_line_1", "loop_statement", "code_body", "variants", "correct_answer", "explanation", "safe_terminal_output", "unsafe_terminal_output"]
            )
        )
    ]
)

class MaterialRequest(BaseModel):
    notes: str

@app.post("/api/generate-puzzle")
async def generate_puzzle(req: MaterialRequest):
    prompt = f"""
    You are an AI computer science tutor for the '&edu' platform.
    Analyze the following educational material:
    ---
    {req.notes}
    ---
    Create a practical code mutation puzzle testing whether a loop will run safely or crash the computer.
    You MUST call the `create_code_puzzle` tool.
    """

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[puzzle_tool],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="ANY")
            )
        )
    )

    # Extract the tool arguments that Gemini generated
    for call in response.function_calls:
        if call.name == "create_code_puzzle":
            return dict(call.args)

    return {"error": "Model did not trigger the tool."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)