#!/usr/bin/env python3
"""
CLI Helper for Autonomous Coding Agents
Allows never-stopping agents to programmatically add or update scientific topics,
LaTeX derivations, and assessment quizzes.
"""

import re
import sys
import json
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from simspec import validate_spec, SPEC_GUIDE  # noqa: E402  (same validator the server uses)

TOPICS_DIR = ROOT / "content" / "topics"
TOPIC_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
TOPICS_DIR.mkdir(parents=True, exist_ok=True)

def main():
    parser = argparse.ArgumentParser(description="Add or update a SciEdu topic")
    parser.add_argument("--file", help="Path to JSON topic definition file")
    parser.add_argument("--id", help="Topic ID (kebab-case)")
    parser.add_argument("--title", help="Topic Title")
    parser.add_argument("--category", help="Category (e.g. Classical Mechanics)")
    parser.add_argument("--markdown", help="Markdown content string or file path")
    parser.add_argument("--template", action="store_true", help="Print a starter topic template")
    parser.add_argument("--validate-sim", metavar="SPEC_JSON", help="Check a SimSpec simulation file and print every error")
    parser.add_argument("--sim-guide", action="store_true", help="Print the SimSpec v1 simulation format")

    args = parser.parse_args()

    if args.sim_guide:
        print(SPEC_GUIDE)
        return

    if args.validate_sim:
        spec = json.loads(Path(args.validate_sim).read_text(encoding="utf-8"))
        _, errors = validate_spec(spec)
        if errors:
            print("Simulation is invalid:\n- " + "\n- ".join(errors))
            sys.exit(1)
        print("Simulation is valid.")
        return

    if args.template:
        template = {
            "id": "sample-topic",
            "title": "Sample Topic Title",
            "category": "Physics",
            "difficulty": "Undergraduate",
            "summary": "Brief 1-sentence summary.",
            "simulationType": None,
            "cheatSheet": [
                { "label": "Key Law", "formula": "E = mc^2" }
            ],
            "mermaid": "graph TD;\n  A-->B;",
            "markdownContent": "# Title\n\nExplanation with math: $E = mc^2$",
            "quiz": [
                {
                    "id": "q1",
                    "difficulty": "Conceptual",
                    "question": "What does $c$ represent in $E = mc^2$?",
                    "options": ["Speed of light", "Charge", "Capacitance", "Specific heat"],
                    "correctAnswer": 0,
                    "hint": "Think about electromagnetic waves.",
                    "explanation": "$c$ is the universal speed of light in vacuum."
                }
            ]
        }
        print(json.dumps(template, indent=2))
        return

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File {file_path} not found.")
            sys.exit(1)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        topic_id = data.get("id")
        if not topic_id or not TOPIC_ID_RE.match(topic_id):
            print("Error: 'id' must be kebab-case: lowercase letters, digits and '-' (it becomes the file name).")
            sys.exit(1)
        for i, q in enumerate(data.get("quiz") or []):
            if "correctAnswer" not in q and "correct" in q:
                q["correctAnswer"] = q.pop("correct")
            if not isinstance(q.get("correctAnswer"), int) or not 0 <= q["correctAnswer"] < len(q.get("options") or []):
                print(f"Error: quiz[{i}].correctAnswer must be a 0-based index into its options.")
                sys.exit(1)
        if data.get("simulation"):
            _, errors = validate_spec(data["simulation"])
            if errors:
                print("Error: simulation is invalid:\n- " + "\n- ".join(errors))
                sys.exit(1)
        
        target = TOPICS_DIR / f"{topic_id}.json"
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Saved topic '{topic_id}' to {target}. The app picks it up within a few seconds.")
        return

    print("Provide --file <path> to add a topic, or --template to view the schema.")

if __name__ == "__main__":
    main()
