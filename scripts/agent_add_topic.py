#!/usr/bin/env python3
"""
CLI Helper for Autonomous Coding Agents
Allows never-stopping agents to programmatically add or update scientific topics,
LaTeX derivations, and assessment quizzes.
"""

import sys
import json
import argparse
from pathlib import Path

TOPICS_DIR = Path(__file__).parent.parent / "content" / "topics"
TOPICS_DIR.mkdir(parents=True, exist_ok=True)

def main():
    parser = argparse.ArgumentParser(description="Add or update a SciEdu topic")
    parser.add_argument("--file", help="Path to JSON topic definition file")
    parser.add_argument("--id", help="Topic ID (kebab-case)")
    parser.add_argument("--title", help="Topic Title")
    parser.add_argument("--category", help="Category (e.g. Classical Mechanics)")
    parser.add_argument("--markdown", help="Markdown content string or file path")
    parser.add_argument("--template", action="store_true", help="Print a starter topic template")

    args = parser.parse_args()

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
        if not topic_id:
            print("Error: JSON must contain an 'id' field.")
            sys.exit(1)
        
        target = TOPICS_DIR / f"{topic_id}.json"
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ Topic '{topic_id}' successfully saved to {target}")
        return

    print("Provide --file <path> to add a topic, or --template to view the schema.")

if __name__ == "__main__":
    main()
