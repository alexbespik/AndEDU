> **Historical document.** This guide describes the earlier SciEdu Studio version. For running, hosting and the agent contract, see `README.md` and `AGENTS.md`.

# &.edu LAB — Complete Project Architecture & Technical Guide

Welcome to **&.edu LAB**, a next-generation interactive scientific education environment, derivation laboratory, and physics simulation studio with native **Google Antigravity (AGY)** autonomous agent integration.

---

## 1. Executive Summary & Vision

SciEdu Studio merges rigorous academic STEM learning with interactive, real-time computational laboratories. Instead of static textbook PDFs or passive videos, students and researchers interact with:

1. **Rigorous KaTeX Derivations**: Step-by-step mathematical proofs with custom KaTeX equation theming.
2. **Interactive 2D Physics Canvases**: Responsive mechanical simulations that visually compute vectors, forces, rotational moments of inertia, friction, and restitution in real time.
3. **Embedded Python Code IDE**: A full multi-panel programming IDE with syntax highlighting, file explorer, sandbox execution, and Socratic mentor dialog.
4. **Autonomous AGY AI Pairing**: Native bidirectional integration with Google Antigravity (`agy`), enabling the AI agent to dynamically control parameters on screen, navigate views, and author new lessons on the fly.

---

## 2. System Architecture

```
                             ┌──────────────────────────────────────────────┐
                             │               USER BROWSER                   │
                             │         http://localhost:5173/               │
                             └──────────────────────┬───────────────────────┘
                                                    │
                 ┌──────────────────────────────────┴──────────────────────────────────┐
                 │                                                                     │
                 ▼                                                                     ▼
    ┌─────────────────────────┐                                           ┌─────────────────────────┐
    │     Vite Dev Server     │                                           │     FastAPI Backend     │
    │        Port 5173        │                                           │        Port 8090        │
    │  - React 19 Engine      │                                           │  - REST API Endpoints   │
    │  - Tailwind / CSS       │                                           │  - Live Event Queue     │
    │  - Hot Module Reload    │                                           │  - Topic JSON Ingestion │
    └────────────┬────────────┘                                           │  - Python Execution     │
                 │                                                        └────────────┬────────────┘
                 ▼                                                                     │
    ┌─────────────────────────┐                                                        │
    │  SciEdu Studio Client   │◄─────────────── Polling /api/agy/events ───────────────┤
    │  - Physics Mode         │◄─────────────── Polling /api/topics ───────────────────┤
    │  - Code IDE Mode        │                                                        │
    │  - Math Mode            │                                                        │
    │  - Canvas Simulations   │                                                        │
    │  - KaTeX & Mermaid      │                                                        │
    └─────────────────────────┘                                                        ▼
                                                                          ┌─────────────────────────┐
                                                                          │   Google Antigravity    │
                                                                          │     CLI / Agent Bus     │
                                                                          │   /opt/homebrew/bin/agy │
                                                                          │  - Autonomous Execution │
                                                                          │  - Real-Time Tool Calls │
                                                                          └─────────────────────────┘
```

---

## 3. The Three Studio Modes

SciEdu Studio features three core operational modes selectable from the global Navbar:

### 🌌 Mode 1: Physics Studio
- **Theory & Derivations Tab**: Full-length scientific derivations rendered in KaTeX and Markdown, accompanied by key formula cheat-sheets.
- **Physics Simulation Tab**: Fullscreen interactive 2D simulation canvas with real-time controls, telemetry HUDs, vector visualizers, and state indicators.
- **Assessment Quiz Tab**: Interactive multiple-choice problem sets with immediate scoring, KaTeX step-by-step explanations, and contextual hints.
- **Agent Hub Tab**: Real-time companion hub for conversing with the AGY tutor, requesting derivations, or asking for on-the-fly simulation modifications.

### ⚡ Mode 2: Code IDE (&EDU Studio)
- **Editor Workspace**: Full-featured code editor with syntax highlighting, line numbers, and file tabs.
- **File System Tree**: Collapsible project directory explorer supporting multiple files and scratch scripts.
- **Interactive Terminal**: Execution console showing `stdout`, `stderr`, runtime assertions, and test pass/fail states.
- **Socratic Mentor**: Intelligent embedded dialogue panel providing guided hints, code reviews, and reasoning prompts.

### ∑ Mode 3: Math Studio
- Formal mathematical derivation workspace for Lagrangian mechanics, variational calculus, Hamiltonian dynamics, and vector calculus proofs.

---

## 4. Physics Simulations Catalog

### 1. Billiard Ball Collisions & Restitution (`BilliardSim.jsx`)
Models the full 2D kinematics and rotational dynamics of pool/billiard ball collisions:
- **Coefficient of Restitution ($e$)**: Continuously adjustable slider and presets:
  - $e = 1.0$: Perfectly elastic collision (kinetic energy conserved).
  - $e = 0.92$: Billiard phenolic resin (standard table physics).
  - $e = 0.50$: Soft inelastic impact.
  - $e = 0.0$: Completely inelastic impact (balls stick together along the impact axis).
- **Collision Normal & Impact Angle ($\cos\theta$)**:
  - Impact offset parameter $b/R \in [-1.7, 1.7]$.
  - Presets for Head-on ($\cos\theta = 1.0$), $30^\circ$ Cut ($\cos\theta = 0.866$), $45^\circ$ Cut ($\cos\theta = 0.707$), and $60^\circ$ Thin Cut ($\cos\theta = 0.500$).
- **Felt Cloth Friction ($\mu_k$)**:
  - Kinetic friction slider ($\mu_k \in [0.0, 1.0]$) and active ON/OFF toggle.
  - Presets for Standard Felt ($\mu_k = 0.28$), Slick Speed Cloth ($\mu_k = 0.12$), and Zero Friction Air Table ($\mu_k = 0.0$).
  - Dynamic kinetic friction vector ($\vec{f}_k$) drawn at the cloth contact patch showing sliding deceleration until pure rolling $v = R\omega$ is established.
- **Impulsive Cue Strike Dynamics ($h/R$)**:
  - Off-center strike height slider $h \in [-0.85R, 0.85R]$.
  - Sweet spot $h = 0.4R$: Ball rolls without slipping instantly with zero sliding friction.
  - Stun shot ($h = 0$): Ball slides with initial pure translation before sliding friction generates rotation.
  - Draw shot ($h < 0.4R$): Kinetic friction accelerates rotation and decelerates translation.
  - Follow shot ($h > 0.4R$): Topspin induces forward friction.
- **Energy Dissipation Telemetry**:
  - Displays real-time linear speed $v_1, v_2$, angular velocity $\omega_1, \omega_2$, impact angle $\theta$, and dissipated kinetic energy $\Delta K = K_{\text{before}} - K_{\text{after}}$.

### 2. Rolling Without Slipping (`RollingWithoutSlippingSim.jsx`)
- Demonstrates the transition from translational slipping to pure rolling $v_{\text{cm}} = R\omega$.
- **Rotational Inertia Factors ($I = \beta M R^2$)**:
  - Solid Sphere: $\beta = 0.4$ ($\frac{2}{5}$)
  - Solid Cylinder / Disc: $\beta = 0.5$ ($\frac{1}{2}$)
  - Thin Spherical Shell / Hoop: $\beta = 1.0$ ($1$)
- **Cycloid Tracing**: Plots the parametric cycloid curve traced by a point on the wheel rim.
- **Vector Overlays**: Instantaneous center of rotation (zero velocity point at ground contact), velocity vectors across the disc diameter, and force diagrams.

---

## 5. Google Antigravity (AGY) Integration

SciEdu Studio contains a native bridge to **Google Antigravity CLI (`agy`)**:

### Bidirectional Real-Time Event Bus
The FastAPI backend maintains a persistent in-memory FIFO queue (`ui_events_queue`). The client polls `/api/agy/events` every 800ms to process events:

| Event Type | Payload | Client Action |
| :--- | :--- | :--- |
| `SET_SIM_CONFIG` | `{ restitution, impact_offset, strike_height, friction, enableFriction }` | Dynamically updates the running simulation sliders, canvas vectors, and resets rack in real time. |
| `SWITCH_TOPIC` | `{ topicId, tab, mode }` | Navigates the workspace to the specified lesson and activates the simulation/quiz. |
| `SWITCH_TAB` | `{ tab: "simulation" \| "theory" \| "quiz" \| "agent" }` | Switches active tab without reloading. |
| `SWITCH_STUDIO_MODE` | `{ mode: "physics" \| "code" \| "math" }` | Switches between Physics, Code IDE, and Math studio. |
| `TOPIC_CREATED` | `{ topicId, title }` | Hot-reloads curriculum and automatically selects the newly created lesson. |

### Autonomous Tool Declarations (`server.py`)
When a user asks the AGY companion in chat (e.g. *"remove the friction"*, *"set restitution to 0.7"*, *"give ability to change cos of collision"*), the agent invokes structured tool declarations:
- `set_simulation_config(restitution, impact_offset, strike_height, strike_speed)`
- `create_or_update_lesson(id, title, category, simulationType, summary, cheatSheet, mermaid, markdownContent, quiz)`
- `switch_page(topic_id, tab, mode)`
- `execute_python_code(code, test_code)`

---

## 6. Directory Structure & File Map

```
SciEdu-Studio/
├── index.html                  # HTML entry point, KaTeX CSS, Mermaid script, Inter/JetBrains fonts
├── package.json                # Dependencies: React 19, Lucide, KaTeX, ReactMarkdown, Remark, Rehype
├── vite.config.js              # Vite bundler configuration (dev server on port 5173)
├── server.py                   # FastAPI backend server (port 8090) with AGY runner & event queue
├── backend_puzzles.py          # Coding puzzle test runner and verification harness
├── PROJECT_GUIDE.md            # Complete project documentation and architectural specification
├── AGENTS.md                   # Autonomous coding agent directives and schema reference
│
├── content/                    # Curriculum & runtime storage
│   ├── agy_messages.json       # Live companion chat history
│   └── topics/                 # Modular lesson definitions (JSON)
│       ├── billiard-ball-collisions.json
│       ├── rolling-without-slipping.json
│       ├── lagrangian-mechanics.json
│       └── ball-hitting-rod.json
│
├── src/                        # React Frontend Source Code
│   ├── main.jsx                # Application root mounter
│   ├── App.jsx                 # Main application controller & AGY event queue listener
│   ├── theme.js                # Monokai Black & Forest Pine styling tokens
│   │
│   ├── components/             # Reusable UI Components
│   │   ├── Navbar.jsx          # Studio mode switcher, breadcrumb navigation, agent status
│   │   ├── Sidebar.jsx         # Curriculum explorer grouped by category with search
│   │   ├── TopicViewer.jsx     # Tabbed lesson renderer (Theory, Sim, Quiz, Agent)
│   │   ├── EduStudioIDE.jsx    # Complete multi-panel Python IDE with terminal and mentor
│   │   ├── QuizEngine.jsx      # Assessment quiz engine with KaTeX explanations
│   │   ├── AgyBridgeDrawer.jsx # Floating real-time AGY companion bridge
│   │   └── MermaidViewer.jsx   # Scientific flowchart and state diagram renderer
│   │
│   └── simulations/            # Interactive Physics Simulation Engines
│       ├── BilliardSim.jsx     # 2D billiard collisions with restitution, cos θ, and felt friction
│       └── RollingWithoutSlippingSim.jsx # Pure rolling vs slipping with cycloid tracing
```

---

## 7. Visual Design System

SciEdu Studio uses the signature **Monokai Black & Forest Pine** theme:

| Token | Value | Purpose |
| :--- | :--- | :--- |
| `bgApp` | `#121212` | Monokai Black canvas ground |
| `bgPanel` | `#1a1a1a` | Elevated dark charcoal panels |
| `bgSidebar` | `#161616` | Sleek navigation sidebar |
| `bgCard` | `#1e1e1e` | Card surfaces |
| `border` | `#282828` | Subtle boundary lines |
| `borderActive` | `#e5b85c` | Collegiate Pine Gold active border |
| `textMain` | `#f8f8f2` | Monokai text white |
| `textDim` | `#a8a8a2` | Secondary text |
| `textMuted` | `#7e8a82` | Balanced sage muted text |
| `accent` / `accentGreen` | `#23a55a` | Deep Forest Green primary accent |
| `accentGold` | `#e5b85c` | Luminous Collegiate Gold highlight |
| `accentPink` | `#f92672` | Monokai pink / friction indicator |
| `accentBlue` / `accentCyan` | `#66d9ef` | Monokai cyan / velocity vectors |
| `fontMono` | `JetBrains Mono` | Telemetry, numbers, and code |
| `fontSans` | `Inter` | Headings and descriptive prose |

---

## 8. Getting Started & Running the Project

### Prerequisites
- Node.js $\ge 18$
- Python $\ge 3.10$ with `fastapi`, `uvicorn`, `pydantic`
- Google Antigravity CLI (`agy`) installed at `/opt/homebrew/bin/agy`

### Starting the Servers

1. **Start the Frontend (Vite Dev Server)**:
   ```bash
   cd SciEdu-Studio
   npx vite --port 5173
   ```
   Access in browser: `http://localhost:5173/`

2. **Start the Backend Server (FastAPI)**:
   ```bash
   .venv/bin/python server.py
   ```
   API runs at: `http://localhost:8090/`
   Interactive docs: `http://localhost:8090/docs`

---

## 9. Creating New Lessons Dynamically

Any coding agent or script can create a new lesson by dropping a JSON file into `content/topics/<topic-id>.json`. The application detects the new file within 2.5 seconds, registers it in the sidebar, and hot-swaps the view without a page reload.
