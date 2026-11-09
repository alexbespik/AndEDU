# Architecture Specification: Geometry Simulation Kit & Stoic Teacher Engine

**Status**: Approved Architectural Specification  
**Author**: architect  
**Target Implementation**: coder  
**Related Files**: `simspec.py`, `server.py`, `src/simulations/GeometrySim.jsx`, `src/components/Md.jsx`, `src/components/AgyBridgeDrawer.jsx`, `src/simulations/SpecSim.jsx`, `src/components/MathLab.jsx`, `mcp_server.py`, `mcp_tools_studio.py`

---

## 1. Context & Architectural Objectives

This document establishes the system architecture and contracts for two core enhancements to &.edu (SciEdu-Studio):
1. **KaTeX Vector Typography & Stoic Socratic Teacher Prompts**: Resolving KaTeX rendering errors for unit vectors ($\hat{\imath}$, $\hat{\jmath}$, $\hat{k}$), preventing macro crashes, eliminating artificial 1-sentence word choking, and establishing anti-hallucination invariants (dimensional homogeneity, symbolic integrity, grounded verification).
2. **Interactive Geometry & Free-Body Diagram Kit (`kind: "geometry"`)**: A declarative, reactive simulation engine for free-body diagrams, geometric proofs, and statics/dynamics apparatuses, fully embeddable in study notes via markdown code blocks (` ```geometry ` and ` ```fbd `) and controllable through MCP tools.

---

## 2. Component Boundaries & Interaction Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                             STUDENT INTERACTION LAYER                           │
│                                                                                 │
│  ┌──────────────────────────┐  ┌──────────────────────────┐  ┌────────────────┐ │
│  │ Topic Notes & Markdown   │  │ Math Lab / Sim Kit       │  │ AGY Companion  │ │
│  │ (Theory, Notes, Quizzes) │  │ - Parametric widgets     │  │ - Multi-turn   │ │
│  │ - ```geometry / ```fbd   │  │ - Live FBD templates     │  │   chat history │ │
│  └────────────┬─────────────┘  └────────────┬─────────────┘  └───────┬────────┘ │
└───────────────┼─────────────────────────────┼────────────────────────┼──────────┘
                │                             │                        │
                ▼                             ▼                        ▼
┌─────────────────────────────┐ ┌───────────────────────────┐ ┌───────────────────┐
│     src/components/Md.jsx   │ │ src/simulations/SpecSim   │ │ AgyBridgeDrawer   │
│ - rehype-katex macros       │ │ - kind: "geometry" /"fbd" │ │ - sends history[] │
│ - throwOnError: false       │ └─────────────┬─────────────┘ └────────┬──────────┘
│ - regex unit vector repair  │               │                        │
│ - inline GeometrySim mount  │               │                        │
└───────────────┬─────────────┘               ▼                        │
                │              ┌───────────────────────────┐           │
                └─────────────►│ src/simulations/          │           │
                               │ GeometrySim.jsx (SVG)     │           │
                               │ - reactive params/sliders │           │
                               │ - vector arrowheads       │           │
                               │ - KaTeX vector labels     │           │
                               │ - component projections   │           │
                               └───────────────────────────┘           │
                                                                       │
                                 HTTP REST / WebSocket Events          │
                                                                       │
┌──────────────────────────────────────────────────────────────────────┴──────────┐
│                             FASTAPI BACKEND (server.py)                         │
│                                                                                 │
│  ┌────────────────────────────────────┐    ┌──────────────────────────────────┐ │
│  │ Stoic Teacher Prompts & Anti-Hall. │    │ Geometry Endpoints & Bus         │ │
│  │ - SOCRATIC_PROMPT (2-4 paragraphs) │    │ - POST /api/ui/geometry          │ │
│  │ - LESSON_TUTOR_PROMPT (grounded)   │    │ - emit_event("GEOMETRY_PREVIEW") │ │
│  │ - AGY_SYSTEM_PROMPT (multi-turn)   │    │ - repair_latex vector normalizer │ │
│  │ - Dimensional homogeneity guard    │    │ - AgyPromptModel.history parser  │ │
│  └────────────────────────────────────┘    └─────────────────┬────────────────┘ │
│                                                              │                  │
│  ┌────────────────────────────────────┐                      │                  │
│  │ simspec.py Engine                  │◄─────────────────────┘                  │
│  │ - validate_geometry(spec)          │                                         │
│  │ - AST whitelist expression parser  │                                         │
│  │ - GEOMETRY_GUIDE documentation     │                                         │
│  └────────────────────────────────────┘                                         │
└───────────────────────────────────────▲─────────────────────────────────────────┘
                                        │ stdio JSON-RPC
┌───────────────────────────────────────┴─────────────────────────────────────────┐
│                         MCP SERVER (mcp_server.py)                              │
│                                                                                 │
│  - add_drawing_to_notes: Injects ```geometry spec into markdownContent & notes  │
│  - preview_geometry_diagram: Emits GEOMETRY_PREVIEW to show live on screen      │
│  - simulation_guide: Exposes geometry schema to AI agent tool callers           │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Contracts & Specifications

### 3.1 Declarative Geometry Specification (`kind: "geometry"`)

A valid geometry specification is serialized JSON. Expressions must comply with the whitelist grammar defined in `simspec.py` / `src/lib/expr.js`. Cartesian convention: $+x$ is RIGHT, $+y$ is UP.

```json
{
  "version": 1,
  "kind": "geometry",
  "title": "Inclined Plane with Friction & Vector Decomposition",
  "description": "Adjust the incline angle theta and friction coefficient mu to inspect normal force, static/kinetic friction, and component projections.",
  "params": [
    { "name": "theta", "label": "Incline Angle", "min": 5, "max": 60, "value": 30, "step": 1, "unit": "deg" },
    { "name": "m", "label": "Block Mass", "min": 1, "max": 20, "value": 5, "step": 0.5, "unit": "kg" },
    { "name": "mu", "label": "Friction Coeff", "min": 0, "max": 1, "value": 0.35, "step": 0.05, "unit": "" }
  ],
  "view": {
    "xmin": -4,
    "xmax": 6,
    "ymin": -2,
    "ymax": 6,
    "grid": true,
    "axes": true
  },
  "bodies": [
    {
      "id": "ramp",
      "type": "wedge",
      "x": -2,
      "y": 0,
      "width": 6,
      "height": "6 * tan(theta * pi / 180)",
      "color": "muted",
      "fill": "rgba(116, 124, 120, 0.15)"
    },
    {
      "id": "block",
      "type": "box",
      "x": 1,
      "y": "3 * tan(theta * pi / 180) + 0.3",
      "width": 1.2,
      "height": 0.8,
      "angle": "theta",
      "color": "gold",
      "fill": "rgba(229, 184, 92, 0.25)",
      "label": "m"
    }
  ],
  "forces": [
    {
      "id": "fg",
      "body": "block",
      "origin": "center",
      "angle": 270,
      "magnitude": "m * 0.98",
      "label": "m\\vec{g}",
      "color": "pink",
      "projections": false
    },
    {
      "id": "fn",
      "body": "block",
      "origin": "center",
      "angle": "90 + theta",
      "magnitude": "m * 0.98 * cos(theta * pi / 180)",
      "label": "\\vec{F}_N",
      "color": "cyan",
      "projections": false
    },
    {
      "id": "f_friction",
      "body": "block",
      "origin": "center",
      "angle": "180 + theta",
      "magnitude": "min(m * 0.98 * sin(theta * pi / 180), mu * m * 0.98 * cos(theta * pi / 180))",
      "label": "\\vec{f}_s",
      "color": "orange",
      "projections": false
    }
  ],
  "elements": [
    {
      "type": "angle_arc",
      "x": -2,
      "y": 0,
      "radius": 1.5,
      "startAngle": 0,
      "endAngle": "theta",
      "label": "\\theta",
      "color": "gold"
    },
    {
      "type": "right_angle",
      "x": 4,
      "y": 0,
      "size": 0.4,
      "angle": 90,
      "color": "muted"
    }
  ],
  "axes": {
    "x": 1,
    "y": "3 * tan(theta * pi / 180) + 0.3",
    "angle": "theta",
    "xLabel": "x'",
    "yLabel": "y'"
  }
}
```

#### Body Types Whitelist
| Type | Required Fields | Optional Fields | Description |
| :--- | :--- | :--- | :--- |
| `box` | `x, y, width, height` | `angle, color, fill, label` | Oriented rectangle |
| `wedge` / `ramp` | `x, y, width, height` | `angle, color, fill, label` | Right triangle incline |
| `sphere` / `circle`| `x, y, radius` | `color, fill, label` | Mass point or pulley wheel |
| `rod` | `x1, y1, x2, y2` | `thickness, color, label` | Rigid link or beam |
| `wall` / `surface`| `x1, y1, x2, y2` | `hatch, color, label` | Fixed boundary with crosshatch shading |
| `pulley` | `x, y, radius` | `color, label` | Stationary or moving pulley |
| `point` | `x, y` | `color, label` | Geometric vertex or coordinate |

#### Element Types Whitelist
| Type | Fields | Description |
| :--- | :--- | :--- |
| `line` / `segment` | `x1, y1, x2, y2, color?, dashed?, arrow?, label?` | Line segment with optional arrow or dashed style |
| `angle_arc` | `x, y, radius, startAngle, endAngle, label?, color?` | Arc showing angular sweep with label |
| `right_angle` | `x, y, size, angle, color?` | Standard perpendicular square marker |
| `dimension` | `x1, y1, x2, y2, label, offset?` | Dimension arrow (`<--->`) with distance measurement |
| `polygon` | `points: [[x, y], ...], fill?, color?` | Arbitrary closed polygon |

---

### 3.2 KaTeX Vector Typography & Normalization Contract

KaTeX does not bundle LaTeX physics packages by default. Raw carets, combining unicode characters, and undefined macros like `\ihat` trigger parse errors or unrendered text.

#### Macro Configuration (`rehype-katex`)
```javascript
const KATEX_OPTIONS = {
  throwOnError: false,
  errorColor: '#f92672',
  strict: false,
  macros: {
    '\\ihat': '\\hat{\\imath}',
    '\\jhat': '\\hat{\\jmath}',
    '\\khat': '\\hat{k}',
    '\\uvec': '\\mathbf{\\hat{#1}}',
  },
};
```

#### Normalization Transformation Table
Both `src/components/Md.jsx:normalizeMath` and `server.py:repair_latex` must apply identical transformations:

| Raw Input Pattern | Canonical KaTeX Output | Rationale |
| :--- | :--- | :--- |
| `\ihat`, `\hat i`, `\hat{i}`, `\mathbf{\hat{i}}` | `\hat{\imath}` (or `\mathbf{\hat{\imath}}`) | Dotless $\hat{\imath}$ avoids dot-caret collision |
| `\jhat`, `\hat j`, `\hat{j}`, `\mathbf{\hat{j}}` | `\hat{\jmath}` (or `\mathbf{\hat{\jmath}}`) | Dotless $\hat{\jmath}$ avoids dot-caret collision |
| `\khat`, `\hat k`, `\hat{k}` | `\hat{k}` | Standard unit vector |
| `î` (`\u0069\u0302`), `ı̂` (`\u0131\u0302`) | `\hat{\imath}` | Unicode combining circumflex normalization |
| `ĵ` (`\u006a\u0302`), `ȷ̂` (`\u0237\u0302`) | `\hat{\jmath}` | Unicode combining circumflex normalization |
| `k̂` (`\u006b\u0302`) | `\hat{k}` | Unicode combining circumflex normalization |
| `i^`, `j^`, `k^`, `ı^`, `ȷ^` | `\hat{\imath}`, `\hat{\jmath}`, `\hat{k}` | Raw caret shorthand normalization |
| `\uvec{x}` | `\mathbf{\hat{x}}` | Generic unit vector expansion |

`LATEX_NAMES` regex in `Md.jsx` is expanded to include `ihat|jhat|khat|imath|jmath|uvec` so that bare formulas containing unit vectors are automatically detected and wrapped in `$...$`.

---

### 3.3 Stoic Socratic Teacher & Anti-Hallucination Invariants

The Stoic Teacher embodies calm, dignified, first-principles instruction. It rejects both unhelpful one-sentence brush-offs and hallucinated calculations.

#### Structural Rule: 2–4 Substantive Paragraphs + 1 Leading Question
- **Paragraph 1: Physical Invariant & Conservation Law**: Anchor the question in the fundamental theorem (e.g. Newton's 2nd Law, Conservation of Momentum/Energy, Work-Energy Theorem, Gauss's Law).
- **Paragraph 2: Mechanism & Intuition**: Explain the physical interaction through limiting cases (e.g. "What happens as $\theta \to 0$ or $\theta \to 90^\circ$?") or free-body equilibrium.
- **Paragraph 3 (When applicable): Mathematical Derivation**: Formulate the relation in rigorous KaTeX with dotless unit vectors ($\hat{\imath}$, $\hat{\jmath}$, $\hat{k}$) and clear coordinate orientations.
- **Terminal Socratic Question**: Conclude with exactly ONE targeted question that prompts the student to deduce the next step, resolve a balance equation, or determine an unknown component.

#### Anti-Hallucination Invariants
1. **Symbolic Problem Integrity**: For symbolic problems (deriving formulas in terms of $m, g, \theta, \mu$), NEVER invent numbers. Do not substitute arbitrary values unless explicitly given.
2. **Dimensional Homogeneity**: Every equation must pass dimensional inspection ($[M^a L^b T^c]$). Summing terms of mismatched dimensions is strictly forbidden.
3. **No Unverified Arithmetic**: Never state an uncalculated result as ground truth. Propose step-by-step arithmetic or prompt the student to evaluate.
4. **Epistemic Boundaries**: If an initial problem lacks boundary conditions (e.g. friction coefficient, surface angle), explicitly identify the missing degree of freedom rather than assuming a silent default.

---

### 3.4 Multi-Turn Conversational Continuity for AGY

`AgyPromptModel` is updated to support conversational state:
```python
class AgyPromptModel(BaseModel):
    prompt: str
    topicId: Optional[str] = None
    courseId: Optional[str] = None
    level: Optional[int] = None
    history: Optional[List[Dict[str, Any]]] = None  # [{role: "user"|"model", content: str}]
```

In `post_user_prompt`:
1. Truncate `data.history` to the most recent 12 turns.
2. Normalize roles to alternating `user` and `model` sequences expected by Google GenAI SDK.
3. Pass `contents=[...history_turns, current_user_turn]` to `acall_gemini`.
4. `AgyBridgeDrawer.jsx` extracts the last 12 user/model messages and includes them in the POST body.

---

### 3.5 Model Context Protocol (MCP) Additions

#### `add_drawing_to_notes`
- **Purpose**: Appends a validated interactive ````geometry` diagram block directly to a lesson's markdown content and standalone notes file (`content/notes/<id>.md`).
- **Signature**: `(topic_id: str, diagram: dict, caption: Optional[str]) -> dict`
- **Behavior**:
  1. Validates `diagram` with `validate_geometry(diagram)`. Returns detailed AST errors if invalid.
  2. Loads topic JSON and formats the markdown block:
     ```markdown
     ### {caption or diagram.get('title') or 'Geometric Diagram'}
     
     ```geometry
     {json.dumps(diagram, indent=2)}
     ```
     ```
  3. Appends block to `topic["markdownContent"]`.
  4. Calls `save_topic(topic)`, updating `content/topics/<id>.json` and writing `content/notes/<id>.md`.
  5. Emits `TOPIC_UPDATED` event to sync the student's browser live.

#### `preview_geometry_diagram`
- **Purpose**: Projects an interactive geometry or free-body diagram onto the student's screen in real time without modifying persistent files.
- **Signature**: `(spec: dict) -> dict`
- **Behavior**:
  1. Validates `spec` via `validate_geometry(spec)`.
  2. Dispatches `POST /api/ui/geometry`.
  3. Backend emits `GEOMETRY_PREVIEW` event onto `ui_events_queue`.
  4. Frontend pushes `spec` to `MathLab`'s `KitTab` and offers a navigation prompt if on another tab.

---

## 4. Verification & Testing Matrix

| Component | Test File | Target Checks |
| :--- | :--- | :--- |
| Geometry AST Validation | `tests/test_lab.py` | `validate_spec` accepts `geometry` & `fbd`; rejects unwhitelisted functions; rejects malformed coordinates; validates expressions with slider params. |
| Vector Typography | `tests/test_lab.py` | `repair_latex` transforms `\ihat`, `\jhat`, `\khat`, `î`, `ĵ`, `k̂`, `\hat{i}` to `\hat{\imath}`, `\hat{\jmath}`, `\hat{k}`. |
| MCP Studio Tools | `tests/test_mcp_studio.py` | `add_drawing_to_notes` validates spec and appends block; `preview_geometry_diagram` emits `GEOMETRY_PREVIEW`; `simulation_guide` includes geometry schema. |
| Multi-turn Memory | `tests/test_server_extras.py` | `AgyPromptModel` accepts `history`; `post_user_prompt` constructs multi-turn `contents`. |
| Frontend SVG Rendering | Build & Lint check (`npm run build`) | `GeometrySim.jsx` compiles cleanly; `Md.jsx` renders ````geometry` blocks; KaTeX macros resolve without errors. |
