# backend_puzzle.py
from google import genai
from google.genai import types
import json
client = genai.Client(api_key="AIzaSyYourActualKeyHere...")
# 1. Define the tool structure for Gemini
puzzle_tool = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="emit_slot_puzzle",
            description="Create an educational code mutation puzzle with drag-and-drop variants.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "question": types.Schema(type="STRING", description="Guiding pedagogical question"),
                    "code_prefix": types.Schema(type="STRING", description="Code before the blank slot"),
                    "code_suffix": types.Schema(type="STRING", description="Code after the blank slot"),
                    "variants": types.Schema(
                        type="ARRAY", 
                        items=types.Schema(type="STRING"),
                        description="4 possible choices to place in the slot"
                    ),
                    "correct_answer": types.Schema(type="STRING", description="The exact correct token"),
                    "explanation": types.Schema(type="STRING", description="Why this answer is safe/correct")
                },
                required=["question", "code_prefix", "code_suffix", "variants", "correct_answer"]
            )
        )
    ]
)

# 2. Call Gemini with user materials
client = genai.Client()

def generate_puzzle_from_notes(notes_text: str):
    prompt = f"""
    You are an educational tutor. Read these notes:
    {notes_text}
    Create a 'fill-in-the-blank' logic puzzle about loops.
    Call the `emit_slot_puzzle` function.
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[puzzle_tool],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="ANY") # Forces it to call the tool
            )
        )
    )
    
    # Extract the tool arguments that Gemini populated
    for call in response.function_calls:
        if call.name == "emit_slot_puzzle":
            return dict(call.args)