# AGENTS.md // Autonomous Coding Agent Directives for SciEdu Studio

Welcome to **SciEdu Studio** — an interactive, dynamic scientific notation, derivation, simulation, and assessment platform.

This codebase is specifically architected from the ground up to allow **autonomous coding agents** (e.g. running continuous background loops or `/goal` sessions) to dynamically inject, update, and assess STEM topics without breaking the application or requiring manual developer intervention.

---

## 1. Architecture Overview
- **Frontend:** React 19 + Vite (`/src`), styled with the Monokai Black & Forest Pine theme from `&EDU`.
- **Math & Notation Support:** 
  - Markdown GFM tables, quotes, code blocks via `react-markdown` + `remark-gfm`
  - Inline and block LaTeX math rendering via `remark-math` + `rehype-katex` + `katex`
  - Flowcharts & state diagrams via `mermaid`
  - Interactive Physics Canvas simulations (e.g. `RollingWithoutSlippingSim.jsx`)
- **Backend & Data Layer:**
  - Topic definitions reside as JSON files in `/content/topics/<topic-id>.json`.
  - Python server (`server.py`) provides REST endpoints for dynamic topic ingestion and quiz telemetry.
  - The frontend continuously polls `/api/topics` every 3 seconds, so file additions or edits update the user's browser in real-time.

---

## 2. Topic JSON Schema
To create a new topic or extend an existing one, write a JSON file to `content/topics/<id>.json` following this structure:

```json
{
  "id": "quantum-tunneling",
  "title": "Quantum Tunneling & Barrier Penetration",
  "category": "Quantum Mechanics",
  "difficulty": "Upper Undergraduate",
  "icon": "Zap",
  "summary": "Schrödinger equation solutions for finite potential barriers, transmission coefficients, and STM applications.",
  "simulationType": null,
  "cheatSheet": [
    { "label": "Time-Independent Schrödinger", "formula": "-\\frac{\\hbar^2}{2m} \\frac{d^2\\psi}{dx^2} + V(x)\\psi = E\\psi" },
    { "label": "Transmission Coefficient (T)", "formula": "T \\approx e^{-2 \\kappa a}, \\quad \\kappa = \\frac{\\sqrt{2m(V_0 - E)}}{\\hbar}" }
  ],
  "mermaid": "graph TD;\n  A[\"Incident Wave\"]\n  B[\"Evanescent Wave\"]\n  C[\"Transmitted Wave\"]\n  A-->B-->C;",
  "markdownContent": "# Quantum Tunneling\n\nFull LaTeX derivations...",
  "quiz": [
    {
      "id": "q1",
      "difficulty": "Conceptual",
      "question": "What happens to transmission probability $T$ if barrier width $a$ doubles?",
      "options": [
        "It halves linearly.",
        "It drops exponentially as $e^{-4\\kappa a}$.",
        "It stays constant.",
        "It drops to exactly zero."
      ],
      "correctAnswer": 1,
      "hint": "Check the exponential factor in $T \\approx e^{-2\\kappa a}$.",
      "explanation": "Because $T \\propto e^{-2\\kappa a}$, doubling $a$ squares the attenuation factor, causing an exponential decay."
    }
  ]
}
```

---

## 3. Agent Tooling & Commands
Agents can use the built-in CLI tool:

```bash
# Add or update a topic
python3 scripts/agent_add_topic.py --file my_topic.json

# View the JSON schema template
python3 scripts/agent_add_topic.py --template
```

Or communicate directly via the local REST API:
* `GET http://localhost:8090/api/topics` — List all active topics.
* `POST http://localhost:8090/api/topics` — Save/update a topic JSON payload.
* `GET http://localhost:8090/api/topics/{id}` — Fetch specific topic data.
* `POST http://localhost:8090/api/quiz/submit` — Submit quiz evaluation telemetry.
