# Architecture Specification: Pedagogical Prompts & Science Labs Elevation

**Status**: Authoritative Architectural Specification  
**Author**: architect  
**Target Implementer**: coder  
**Scope**: Server Pedagogical Prompts, Chemistry Simulation Apparatus (`ChemSim.jsx`), Math Calculus & Vector Geometry (`MathSim.jsx`, `GeometrySim.jsx`), Code Lab Execution Tracer & Socratic Diagnostics (`EduStudioIDE.jsx`).

---

## 1. Executive Summary & Design Invariants

This specification elevates &.edu across four interrelated subsystems:
1. **Pedagogical Prompt Foundations**: Embedding proven learning science principles—Collins' Cognitive Apprenticeship, Sweller's Cognitive Load Theory, and Hattie's feedback taxonomy—into backend system prompts, while fixing audited prompt bugs (Mermaid node quoting, answer key skew, math power operator formatting, brief line structure, alternating message roles, context dumping).
2. **Chemistry Simulation Lab Elevation (`ChemSim.jsx`)**: Transforming the chemistry simulation into a high-fidelity benchtop apparatus matching the physics simulation: real graduated burette with meniscus and rotating stopcock, gravitational droplet emitter with splash ripples, Erlenmeyer flask on magnetic stir plate with spinning stir bar and liquid vortex, digital dip-probe pH meter, continuous phenolphthalein colorimetric gradient, and Maxwell-Boltzmann molecular kinetics with live pressure gauge.
3. **Math & Vector Geometry Elevation (`MathSim.jsx`, `GeometrySim.jsx`)**: Adding interactive slope triangles ($\Delta y / \Delta x$) with live secant-tangent derivative limits, dynamic upper/lower Darboux Riemann sums with error residual fill, and direct SVG pointer-drag handles on force vectors and rigid bodies.
4. **Code Studio Execution Tracer & Diagnostics (`EduStudioIDE.jsx`)**: Introducing a zero-overhead WebAssembly memory and variable inspector capturing local variables and list memory cells, accompanied by a Socratic Error Diagnostic translating assertions and tracebacks into process-level scaffolding (boundary condition, off-by-one, type mismatch).

---

## 2. Pedagogical Framework & Prompt Engineering Architecture

### 2.1 Theoretical Foundations

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    LEARNING SCIENCE THEORETICAL PILLARS                      │
├──────────────────────────┬─────────────────────────┬─────────────────────────┤
│ COGNITIVE APPRENTICESHIP │  COGNITIVE LOAD THEORY  │    HATTIE'S FEEDBACK    │
│ (Collins, Brown, Newman) │     (John Sweller)      │   (Hattie & Timperley)  │
├──────────────────────────┼─────────────────────────┼─────────────────────────┤
│ - Modeling (make visible)│ - Intrinsic load: chunk │ - Task Level (correct/  │
│ - Scaffolding (ZPD)      │   into invariant subgoals  incorrect confirmation)│
│ - Fading (reduce aid)    │ - Extraneous load: ban  │ - Process Level (target │
│ - Coaching (diagnosis)   │   rigid multi-para choke│   underlying strategy)  │
│ - Articulation (student) │ - Germane load: schema  │ - Self-Regulation       │
│ - Reflection & Compare   │   acquisition focus     │   (metacognitive checks)│
└──────────────────────────┴─────────────────────────┴─────────────────────────┘
```

### 2.2 Dynamic Response Sizing Invariant
Previous system prompts rigidly mandated 2–4 paragraphs of boilerplate for every query. This introduced severe extraneous cognitive load during quick student clarification queries. The new architecture enforces a **two-tier dynamic response policy**:
- **Diagnostic Turn (40–80 words)**: Triggered when the student asks a focused question, checks a single assumption, or provides an intermediate step. Directly addresses the conceptual threshold or misconception, gives process-level feedback, and ends with **one leading check question**.
- **Conceptual Scaffolding Turn (100–180 words)**: Triggered when the student encounters a fundamental impasse, derives a new physical/mathematical relationship, or exhibits a persistent misconception. Structures the response around:
  1. The governing invariant / physical law.
  2. The geometric coordinate frame / constraint.
  3. The specific conceptual blocker, diagnosed via a limiting case or dimensional argument.
  4. Exactly **one leading check question**.

### 2.3 Audited Backend Prompt Fixes (`server.py`)

| Prompt Symbol | Location | Audited Bug / Limitation | Architectural Fix |
| :--- | :--- | :--- | :--- |
| `CLASS_PROMPT` | `server.py:4700` | Unquoted Mermaid labels crashing renderer; missing JSON completion guard. | Explicitly mandate quoting every Mermaid node `A["label"]` and edge `-->\|"label"\|`; enforce completion guard: 600–1000 word ceiling, clean JSON closing `}}`. |
| `DIAGNOSTIC_PROMPT` | `server.py:4655` | Strong answer key skew toward index 0 (Option A) due to template example `"correctAnswer": 0`. | Enforce balanced distribution: `correctAnswer` must be evenly distributed among 0, 1, 2, and 3 across the generated question set. |
| `MATH_PRACTICE_PROMPT` | `server.py:3050` | Models emitting caret `^` for powers (which evaluates to BitXor in Python AST, causing verification failure). | Explicitly forbid `^`; mandate Python exponent operator `**` (e.g. `2**3`). Limit functions strictly to `_MATH_NAMES` whitelist. |
| `BRIEF_PROMPT` | `server.py:5421` | Drift into conversational preface or multiline explanations. | Enforce strict 3-line format under 60 words: `**Goal:**`, `**Key idea:**`, `**Check yourself:**`. |
| `AGY_SYSTEM_PROMPT` | `server.py:6192` | Model using `execute_python_code` to bypass student thinking by computing complete answers. | Enforce Socratic tool usage: tools must demonstrate intermediate physical principles or generate diagnostic scaffolds, never solve active student exercises. |
| `tutor_chat` & `SOCRATIC_PROMPT` | `server.py:636`, `2007` | Raw `p_ctx` dump leaks solutions and overflows prompt; non-alternating history turns cause Gemini 400 errors. | Sanitize `p_ctx` via `_sanitize_puzzle_context` (stripping solution/answers); enforce strict alternating message roles (`user` / `model`) and pop non-user heads. |

---

## 3. Chemistry Simulation Kit Elevation (`ChemSim.jsx`)

### 3.1 Component Hierarchy & Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ChemWidget (SimSpec kind: "chem")                     │
│                                                                             │
│  ┌──────────────────────────────────┐  ┌──────────────────────────────────┐ │
│  │   Interactive Benchtop Canvas    │  │    Synchronized Readout Strip    │ │
│  │  ┌─────────────────────────────┐ │  │ - Live pH / Volume / Temp Gauge  │ │
│  │  │ Dual-Pane Apparatus Display │ │  │ - Reaction Quotient Q vs Keq     │ │
│  │  │                             │ │  │ - Half-life & Boltzmann Fraction │ │
│  │  │ [Left] Strip Chart / Curves │ │  └──────────────────────────────────┘ │
│  │  │ [Right] Glassware Apparatus │ │  ┌──────────────────────────────────┐ │
│  │  │   - Burette with Meniscus   │ │  │     Interactive Control Bar      │ │
│  │  │   - Rotating Stopcock Valve │ │  │ - Titrant Flow / Piston Volume   │ │
│  │  │   - Droplet Emitter & Waves │ │  │ - Play / Pause / Reset           │ │
│  │  │   - Flask + Liquid Vortex   │ │  │ - Parameter Sliders with Units   │ │
│  │  │   - Stir Bar + Motor Plate  │ │  └──────────────────────────────────┘ │
│  │  │   - Dip-Probe Digital Meter │ │                                       │
│  │  │   - Gas Chamber + Impulses  │ │                                       │
│  │  └─────────────────────────────┘ │                                       │
│  └──────────────────────────────────┘                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Visual Benchtop Apparatus Specifications

1. **Retort Stand & Clamp Assembly**:
   - Heavy metal base with chamfered edges and dual-rod vertical support.
   - Chrome three-finger clamp securing the graduated burette above the flask center.
2. **Graduated Burette (`titration`)**:
   - Translucent glass tube with accurate volume gradations ($0.0$ to $50.0\text{ mL}$).
   - Liquid column with curved meniscus that depletes as titrant volume $V_b$ increases.
   - Rotatable stopcock valve: aligns vertically when titrant is flowing, rotates horizontally when paused.
3. **Droplet Emitter & Splash Physics**:
   - Dynamic droplet generation when titrant volume increases or simulation runs.
   - Droplets accelerate under gravity ($y = y_0 + \frac{1}{2}gt^2$) into the flask liquid.
   - On surface contact, emits expanding concentric ripples (fading alpha).
4. **Erlenmeyer Reaction Flask & Liquid Vortex**:
   - Authentic conical Erlenmeyer silhouette with narrow neck and sloping body.
   - Solution volume expands ($V_{tot} = V_a + V_b$).
   - Magnetic stir bar: white capsule rotating on the bottom floor.
   - Liquid vortex: central parabolic surface depression formed by fluid angular momentum ($\Delta h \propto \omega^2 r^2$).
5. **Colorimetric Indicator Gradient**:
   - Smooth continuous RGB interpolation for phenolphthalein:
     $$\text{Transition Parameter } \alpha = \operatorname{clamp}\left(\frac{\text{pH} - 8.2}{1.8}, 0, 1\right)$$
     $$\text{Color} = (1 - \alpha) \cdot \text{PaleCyan} + \alpha \cdot \text{MagentaPink}$$
   - Swirl eddies: stir bar rotation draws subtle streaks of pink through the vortex before uniform homogenization.
6. **Benchtop Digital pH Meter**:
   - Submerged glass electrode probe with shielded wire leading to benchtop console.
   - High-contrast 7-segment digital display showing live pH to 2 decimal places.
7. **Gas Law & Kinetics Molecular Engine**:
   - Maxwell-Boltzmann 2D velocity sampling: $v_x, v_y \sim \mathcal{N}(0, k_B T / m)$.
   - Wall collision momentum impulse: instantaneous force calculated as $\sum 2 m v_{\perp} / \Delta t$.
   - Analog dial pressure gauge with needle indicator and collision vibration.
   - Reactive kinetics collisions: particles with relative kinetic energy exceeding $E_a$ trigger chemical transformation with optical emission flash.

---

## 4. Math Simulation & Vector Geometry Elevation

### 4.1 Calculus Secant-Tangent Slope Triangle (`MathSim.jsx`)
In `secant_tangent` mode:
- **Slope Triangle Geometry**:
  - Point $A = (a, f(a))$ and Point $B = (a+h, f(a+h))$.
  - Horizontal leg: $(a, f(a)) \to (a+h, f(a))$ labeled $\Delta x = h$.
  - Vertical leg: $(a+h, f(a)) \to (a+h, f(a+h))$ labeled $\Delta y = f(a+h) - f(a)$.
  - Right-angle glyph rendered at $(a+h, f(a))$.
- **Derivative Limit Convergence Display**:
  - Live readout of secant slope $m_{sec} = \frac{\Delta y}{\Delta x}$ vs exact analytical tangent slope $f'(a)$.
  - Dynamic limit convergence annotation: $\lim_{h \to 0} \frac{\Delta y}{\Delta x} = f'(a)$.

### 4.2 Riemann Sum Darboux Upper/Lower Bounds (`MathSim.jsx`)
In `riemann` mode:
- **Darboux Bounds**:
  - Lower Darboux Sum $L_n = \sum_{i=1}^n \inf_{x \in [x_{i-1}, x_i]} f(x) \cdot \Delta x$ (rendered in translucent cyan).
  - Upper Darboux Sum $U_n = \sum_{i=1}^n \sup_{x \in [x_{i-1}, x_i]} f(x) \cdot \Delta x$ (rendered in translucent gold).
  - Darboux Sandwich Inequality: $L_n \le \int_a^b f(x)\,dx \le U_n$.
- **Error Residual Shading**:
  - Visual hatching/fill between the top of each Riemann rectangle and the exact curve $f(x)$.

### 4.3 Direct SVG Drag Handles on Forces & Bodies (`GeometrySim.jsx`)
- **Force Vector Tips**:
  - Each force vector arrow tip renders an interactive SVG grab circle (halo ring) on hover.
  - Dragging the tip recalculates vector angle $\theta$ and magnitude $F$ relative to origin $(o_x, o_y)$.
  - If a parameter in `spec.params` corresponds to the vector (e.g. `F`, `theta`), the slider state is updated reactively.
- **Body Translation Handles**:
  - Body centers (or vertices for wedges/polygons) expose draggable handles.
  - Dragging moves body position $(x, y)$, immediately updating connected force anchors.
- **Pointer Event Handling**:
  - Uses `onPointerDown`, `onPointerMove`, `onPointerUp` with `setPointerCapture` to support desktop mouse and mobile touch without viewport scrolling conflicts.

---

## 5. Code Studio Execution Tracer & Socratic Diagnostics (`EduStudioIDE.jsx`)

### 5.1 Memory & Variable Inspector Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Pyodide WebAssembly Kernel                            │
│                                                                             │
│  User Python Code ──► Execution ──► Injected Introspection Snippet          │
│                                                   │                         │
│                                                   ▼                         │
│                                     Serialized Memory Snapshot              │
│                                     "__MEM_TRACE__{...}"                    │
└──────────────────────────────────────────────┬──────────────────────────────┘
                                               │
                                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     EduStudioIDE Frontend State                             │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ Variable Inspector Panel (Side-by-side with Terminal Console)         │  │
│  │                                                                       │  │
│  │  NAME       TYPE       VALUE / PREVIEW           DETAILS              │  │
│  │  ───────────────────────────────────────────────────────────────────  │  │
│  │  x          int        42                        Primitive            │  │
│  │  total      float      98.60                     Primitive            │  │
│  │  nums       list       [0: 10, 1: 20, 2: 30]     len = 3 (Memory Grid)│  │
│  │  seen       dict       {"a": 1, "b": 2}          keys = ["a", "b"]    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

1. **Lightweight Python Introspector**:
   After executing user code, Pyodide executes an introspection block:
   ```python
   import json
   __vars__ = {}
   for __k, __v in list(locals().items()):
       if not __k.startswith('_') and not callable(__v) and type(__v).__name__ not in ('module', 'function', 'type'):
           try:
               __vars__[__k] = {
                   "type": type(__v).__name__,
                   "repr": repr(__v)[:120],
                   "is_seq": isinstance(__v, (list, tuple)),
                   "len": len(__v) if isinstance(__v, (list, tuple, dict, set, str)) else None,
                   "items": [repr(x)[:40] for x in __v[:12]] if isinstance(__v, (list, tuple)) else None
               }
           except Exception:
               pass
   print("__MEM_TRACE__" + json.dumps(__vars__))
   ```
2. **Frontend UI Rendering**:
   - `VariableInspector`: Collapsible panel tab positioned above or alongside the Terminal.
   - List and array memory cells displayed as sequential memory boxes with index labels (`[0]`, `[1]`, `[2]`), providing immediate visual insight into sorting and array algorithms.

### 5.2 Socratic Error Diagnostic Engine (`explainError`)
Instead of dumping raw stack traces or unadorned `Failed: assert ...`, the enhanced `explainError` parses errors into structured Socratic guidance:

| Python Error Pattern | Detected Fault Class | Socratic Pedagogical Diagnostic Hint |
| :--- | :--- | :--- |
| `AssertionError: ...` with `== None` | Missing Return | *"Your function completed without returning a value (`None`). Did you compute a result but forget the `return` statement?"* |
| `AssertionError` with off-by-one lengths | Off-by-One Bound | *"The result differs by exactly one element. Check your loop boundaries (`range(...)`): does it include or exclude the endpoint?"* |
| `AssertionError` with empty / 0 inputs | Boundary Condition | *"The failure occurred on a boundary input (e.g. empty list or 0). Does your algorithm include a base condition for empty or zero-sized cases?"* |
| `IndexError: list index out of range` | Index Bound Exceeded | *"You attempted to access an element beyond the list boundary. If a list has $N$ elements, valid indices are $0$ through $N-1$."* |
| `TypeError: can only concatenate str ...` | Type Incompatibility | *"Attempted an operation between text (`str`) and numbers. In Python, convert explicitly using `str(...)` or `int(...)` before combining."* |
| `RecursionError` | Base Case Omission | *"Infinite recursion occurred. Verify that your base case triggers and that each recursive call makes progress toward the base condition."* |

---

## 6. Implementation Plan for `coder`

### 6.1 Changes & File Checklist

1. **`server.py`**:
   - Update `SOCRATIC_PROMPT` and `LESSON_TUTOR_PROMPT`: Replace rigid 2–4 paragraph mandates with dynamic response length policy (diagnostic 40–80 words; conceptual 100–180 words) and grounded pedagogical directives.
   - Update `CLASS_PROMPT`: Enforce Mermaid node label quotes `A["label"]` and edge quotes `-->|"label"|`, plus completion length ceiling.
   - Update `DIAGNOSTIC_PROMPT`: Enforce balanced `correctAnswer` distribution among `0, 1, 2, 3`.
   - Update `MATH_PRACTICE_PROMPT`: Explicitly ban `^` for powers (mandate `**`) and restrict functions to `_MATH_NAMES`.
   - Update `BRIEF_PROMPT`: Enforce strict 3-line format under 60 words.
   - Update `AGY_SYSTEM_PROMPT`: Enforce Socratic tool usage without leaking full solutions.
   - In `tutor_chat`: Add `_sanitize_puzzle_context(p_ctx)` and clean multi-turn role alternating logic (merging consecutive identical roles and ensuring first turn is `user`).
   - *Verification*: `pytest tests/test_server_extras.py tests/test_lab.py`.

2. **`src/simulations/ChemSim.jsx`**:
   - Refactor `titration` widget:
     * Render realistic benchtop glassware: retort stand with clamp, graduated burette with curved meniscus and volume ticks, rotatable stopcock valve.
     * Droplet emitter with gravity acceleration and concentric ripple impact physics.
     * Erlenmeyer flask with rising fluid volume, porcelain magnetic stirrer plate, rotating stir bar capsule, and parabolic fluid vortex depression.
     * Benchtop digital pH meter with glass dip electrode and live numeric display.
     * Smooth phenolphthalein colorimetric gradient with stir eddies.
   - Refactor `gas_law` and `kinetics` widgets:
     * Maxwell-Boltzmann velocity distribution for molecular gas particles.
     * Analog dial pressure gauge with collision impulse vibration.
     * Reactive kinetics collision mechanics with activation energy thresholds and reaction flash bursts.
   - *Verification*: `npm run build`, inspect in browser.

3. **`src/simulations/MathSim.jsx`**:
   - In `secant_tangent`: Render interactive slope triangle ($\Delta x, \Delta y$, right-angle glyph) and live derivative convergence limit readout.
   - In `riemann`: Add Upper and Lower Darboux sum rectangles with Darboux inequality display and shaded error residual fill.
   - *Verification*: `npm run build`, inspect in browser.

4. **`src/simulations/GeometrySim.jsx`**:
   - Add pointer drag handles on force vector tips and body centers.
   - Reactive SVG pointer events updating parameter state and coordinate projections.
   - *Verification*: `npm run build`.

5. **`src/components/EduStudioIDE.jsx`**:
   - Add Pyodide post-execution introspection script to capture `__MEM_TRACE__` variables.
   - Add `VariableInspector` component rendering active variable types, values, and list memory grids.
   - Enhance `explainError` with Socratic error diagnostic taxonomy (missing return, off-by-one, boundary condition, index error, type mismatch).
   - *Verification*: `npm run build`, run Python exercises in IDE.

6. **`tests/test_pedagogy_prompts.py`**:
   - Add automated regression tests verifying prompt invariants:
     * `DIAGNOSTIC_PROMPT` contains answer distribution instruction.
     * `MATH_PRACTICE_PROMPT` contains power operator instructions (`**`, no `^`).
     * `BRIEF_PROMPT` contains 3-line format.
     * `tutor_chat` context sanitizer removes secret/solution fields.
     * `tutor_chat` guarantees alternating message roles.
   - *Verification*: `/opt/homebrew/bin/uv run python -m unittest discover -s tests -v`.

---

## 7. Quality Attributes & Backward Compatibility

- **Backward Compatibility**: All changes adhere 100% to existing `SimSpec v1` and `ChemSpec v1` schemas. No database migrations, API endpoint renames, or breaking contract changes.
- **Performance**: Canvas and SVG operations are optimized for 60fps rendering using `requestAnimationFrame`, hardware-accelerated transforms, and pure memory allocations.
- **Security**: Pyodide runs in a browser-isolated Web Worker sandbox. Python AST evaluation in `server.py` remains strictly gated by the safe math allowlist.
