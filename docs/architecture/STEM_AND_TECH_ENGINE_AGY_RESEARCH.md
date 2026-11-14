# Deep-Dive Technical Blueprint: STEM, Math & Simulation Engines for &.edu
**Target Audience**: Antigravity CLI (agy) / Frontier Systems & Science Subagents  
**System**: &.edu (SciEdu-Studio) Adaptive Learning Platform  
**Purpose**: Comprehensive technical specification, simulation AST grammars, execution sandboxes, deterministic practice engines, and expansion blueprints for Math, IT (Code Studio), Physics, Chemistry, and Engineering.

---

## 1. System Invariants & Core Technical Architecture

### 1.1 Architectural Philosophy: Declarative Data, Zero Arbitrary JavaScript
In &.edu, simulations, interactive diagrams, and coding exercises are **data, never active client-side scripts**:
1. **SimSpec v1 / ChemSpec v1 / Geometry AST**: Simulations authored by agents or AI planners are stored as strict JSON specifications inside topic files (`content/topics/<id>.json`).
2. **Safe Expression Interpreter (`src/lib/expr.js`)**: Client-side expressions (e.g. `bodies[0].x = "2*cos(t*omega)"`, `forces[0].magnitude = "m*g*sin(theta*pi/180)"`) are compiled into safe JavaScript closures without ever using `eval()` or `new Function()`.
3. **Backend AST Mirror (`simspec.py`)**: The server mirrors the exact expression grammar using Python's `ast` module, rejecting invalid names, unsupported functions, or syntax errors *before* files are saved.
4. **Deterministic Evaluation**: All mathematical limits, chemical equilibriums, and code assertions evaluate deterministically without model intervention.

### 1.2 Execution Boundaries & Sandboxing
```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 &.EDU SANDBOX TOPOLOGY                                 │
├──────────────────────────┬─────────────────────────────┬───────────────────────────────┤
│ 1. IN-BROWSER PYODIDE    │ 2. SIMSPEC 240Hz SUBSTEPPED │ 3. FENCED AGY RUNNER          │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────┤
│ • Isolated WebWorker     │ • Semi-implicit Euler       │ • AGY_CLI=1 (15 runs/day max) │
│ • Network stripped       │ • PBD Rod Constraints       │ • Fenced agent directory:     │
│   (no sockets, fetch     │ • Restitution boundaries    │   writes only to              │
│   locked to CDN)         │ • Drag, gravity softening   │   content/agy_drafts/<id>.json│
│ • 8s execution timeout   │ • Zero memory leaks         │ • Read-only page-guard checks │
│ • Memory ceiling guard   │ • Dark/Light canvas tokens  │   injection & answer tampering│
└──────────────────────────┴─────────────────────────────┴───────────────────────────────┘
```

---

## 2. The Baseline: Existing STEM & Tech Infrastructure

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 &.EDU EXISTING STEM WORKSPACES                                    │
├──────────────────────────┬───────────────────────────┬────────────────────────────────────────────┤
│ 1. MATH LAB (`math`)     │ 2. CODE STUDIO (`code`)   │ 3. LAB: PHYSICS & CHEMISTRY (`lab`)        │
├──────────────────────────┼───────────────────────────┼────────────────────────────────────────────┤
│ • 9 Math Widgets:        │ • In-Browser IDE          │ • SimSpec Particles (240 Hz substepping)   │
│   epsilon_delta,         │   (EduStudioIDE.jsx)      │ • SimSpec Dynamic Graph Families y=f(x,t)  │
│   epsilon_n,             │ • Pyodide WebWorker       │ • Free-Body Diagram Kit (kind: "geometry") │
│   secant_tangent,        │   Python runner           │ • ChemSpec v1 Chemistry Kit:               │
│   riemann, series,       │ • Test suite validator    │   Kinetics, Equilibrium, Titration pH,     │
│   unit_circle,           │ • Terminal stdin/stdout   │   van der Waals Gas Laws, Decay Kinetics   │
│   parametric,            │ • Problem Sprint Desk     │ • General Practice: label_diagram (SVG),   │
│   vector_field,          │   (sprint.py reveal &     │   sort_by, odd_one_out, cloze, spot_bug.   │
│   transform2d.           │   check pipeline)         │                                            │
└──────────────────────────┴───────────────────────────┴────────────────────────────────────────────┘
```

---

### 2.1 Math Lab (`MathLab.jsx` & `src/simulations/MathSim.jsx`)
Math classes automatically receive interactive widgets matching the lesson's proof structure:
- `epsilon_delta`:
  - Fields: `f` (in $x$), `a`, `L`, optional `delta_rule` (in $\epsilon$, e.g. `"min(1, eps/5)"` for $x^2$ at $2$, or `"eps/2"` for $2x-1$ at $3$).
  - Mechanics: Plots $\epsilon$-band around $L$ and $\delta$-band around $a$; visualizes points where $f(x)$ escapes; dynamically verifies whether `delta_rule` holds for all $\epsilon > 0$.
- `epsilon_n`:
  - Fields: `term` (in $n$), `L`, optional `nmax`.
  - Mechanics: Sequence convergence visualizer; computes the threshold index $N(\epsilon)$ beyond which $|a_n - L| < \epsilon$.
- `secant_tangent`:
  - Fields: `f`, `a`, slider `h`.
  - Mechanics: Dynamically calculates difference quotient $\frac{f(a+h) - f(a)}{h}$ and illustrates convergence to tangent line $f'(a)$.
- `riemann`:
  - Fields: `f`, `a`, `b`, `method` (`"left"` | `"right"` | `"mid"` | `"trap"`), slider `n`.
  - Mechanics: Computes rectangle partition sum $\sum_{i=1}^n f(x_i^*)\Delta x$ and displays convergence to exact analytical integral $\int_a^b f(x)dx$.
- `series`:
  - Fields: `term` (in $k, x$), optional `target` (in $x$), slider $N$.
  - Mechanics: Taylor/Maclaurin series visualizer plotting partial sum $S_N(x) = \sum_{k=0}^N t(k, x)$ against target function (e.g. $\sum \frac{(-1)^k x^{2k+1}}{(2k+1)!} \to \sin x$).
- `vector_field`:
  - Fields: $P(x, y)$ and $Q(x, y)$ defining $\frac{dy}{dx} = \frac{Q(x,y)}{P(x,y)}$.
  - Mechanics: Renders 2D directional arrow grid; clicking any coordinate drops a real-time Runge-Kutta 4th-order streamline.
- `transform2d`:
  - Fields: Sliders $m_{11}, m_{12}, m_{21}, m_{22}$ for matrix $M = \begin{pmatrix} a & b \\ c & d \end{pmatrix}$.
  - Mechanics: Visualizes transformation of unit basis vectors $\hat{i}, \hat{j}$, Cartesian grid deformation, and computes determinant $\det(M)$ as signed parallelogram area.

---

### 2.2 Physics Simulation Engine (`SpecSim.jsx` & `simspec.py`)
SimSpec v1 executes high-fidelity Newtonian physics in client JavaScript at 240 Hz:

#### 1. Mathematical Integration & Substepping
- Integration Scheme: Semi-implicit Euler (symplectic, conserving phase-space volume):
  $$\mathbf{v}_{t+\Delta t} = \mathbf{v}_t + \frac{\mathbf{F}_t}{m}\Delta t$$
  $$\mathbf{x}_{t+\Delta t} = \mathbf{x}_t + \mathbf{v}_{t+\Delta t}\Delta t$$
- Substepping: Every 60 Hz animation frame ($16.67\text{ ms}$) executes 4 internal integration sub-steps ($\Delta t = \frac{1}{240}\text{ s} \approx 4.167\text{ ms}$) to prevent numerical instability in stiff springs and high-velocity collisions.

#### 2. Force Models
- Linear & Damped Springs:
  $$\mathbf{F}_{\text{spring}} = -k (\|\mathbf{r}_{ij}\| - l_0) \hat{\mathbf{r}}_{ij} - c (\mathbf{v}_{\text{rel}} \cdot \hat{\mathbf{r}}_{ij}) \hat{\mathbf{r}}_{ij}$$
- Aerodynamic Drag:
  $$\mathbf{F}_{\text{drag}} = -\frac{1}{2}\rho C_d A \|\mathbf{v}\|^2 \hat{\mathbf{v}} \quad \text{or linear Stokes drag } \mathbf{F}_d = -b \mathbf{v}$$
- Softened Newtonian Gravitation (N-Body):
  $$\mathbf{F}_g = \frac{G m_1 m_2}{(\|\mathbf{r}_{12}\|^2 + \epsilon^2)^{3/2}} \mathbf{r}_{12}$$
  *(where $\epsilon$ is the softening length parameter preventing infinite force singularities at $r \to 0$)*.

#### 3. Rigid Rod Constraints (Position-Based Dynamics)
- Rigid rods between particles $i$ and $j$ with target length $L$ are resolved via iterative distance relaxation:
  $$\Delta \mathbf{x}_i = -\frac{w_i}{w_i + w_j}(\|\mathbf{x}_i - \mathbf{x}_j\| - L)\frac{\mathbf{x}_i - \mathbf{x}_j}{\|\mathbf{x}_i - \mathbf{x}_j\|}$$
  where $w_i = 1/m_i$ is inverse mass.

#### 4. Declarative FBD & Geometry Kit (`kind: "geometry"`)
- Declarative canvas rendering bodies (`box`, `wedge`/`ramp`, `sphere`, `rod`, `wall`, `pulley`, `point`) with reactive parameters.
- Attached force vectors with automatic normal and tangential component projection lines.

---

### 2.3 Chemistry Simulation Kit (`ChemSim.jsx` & `chemspec.py`)
ChemSpec v1 models aqueous equilibria, reaction kinetics, and thermodynamics:

#### 1. Aqueous Acid-Base Titration Solver
Solves exact equilibrium pH at 25 °C without approximations using the fundamental charge-balance polynomial:
$$[\text{H}^+] + [\text{Na}^+] = [\text{OH}^-] + [\text{A}^-]$$
Substituting $[\text{OH}^-] = \frac{K_w}{[\text{H}^+]}$ and $[\text{A}^-] = c_{a,\text{tot}} \frac{K_a}{[\text{H}^+] + K_a}$ yields:
$$[\text{H}^+] + \frac{C_b V_b}{V_a + V_b} = \frac{K_w}{[\text{H}^+]} + \frac{C_a V_a}{V_a + V_b} \left(\frac{K_a}{[\text{H}^+] + K_a}\right)$$
Solved deterministically via Newton-Raphson / bisection down to $\Delta \text{pH} < 10^{-4}$.

#### 2. Chemical Kinetics & Le Chatelier Shifts
- Evaluates 0th, 1st, and 2nd order rate equations:
  $$[A]_t = [A]_0 - kt \quad (\text{0th}), \quad [A]_t = [A]_0 e^{-kt} \quad (\text{1st}), \quad \frac{1}{[A]_t} = \frac{1}{[A]_0} + kt \quad (\text{2nd})$$
- Reversible equilibria: $aA + bB \rightleftharpoons cC + dD$ with reaction quotient $Q = \frac{[C]^c [D]^d}{[A]^a [B]^b}$ adjusting toward equilibrium constant $K$.

#### 3. Real Gas Law (van der Waals Equation of State)
$$\left(P + \frac{a n^2}{V^2}\right)(V - nb) = nRT$$
Computes deviations from ideal behavior ($Z = \frac{PV}{nRT}$) as pressure and density increase.

---

### 2.4 Code Studio (`EduStudioIDE.jsx` & `src/lib/pyodide.js`)
- **Pyodide WebWorker**: Runs standard Python 3.12+ inside an isolated client WebWorker thread.
- **Security Lockout**: Sockets, `fetch`, and `importScripts` are overridden in `WorkerGlobalScope` to prevent sandbox breakout or API key interception.
- **Problem Runner**: Evaluates student algorithms against private assertion test matrices with timeout protection.

---

## 3. The Expansion: 6 New Advanced STEM & Tech Kits

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    NEW ADVANCED STEM EXPANSION KITS                               │
├──────────────────────────────────┬────────────────────────────────────────────────────────────────┤
│ Kit 1: Circuits & SPICE Engine   │ Nodal analysis (MNA), RLC transients, op-amps, Bode plots.     │
├──────────────────────────────────┼────────────────────────────────────────────────────────────────┤
│ Kit 2: Computer Architecture     │ 16-bit register machine, RISC-V subset ALU, pipeline hazards.  │
├──────────────────────────────────┼────────────────────────────────────────────────────────────────┤
│ Kit 3: Statistics & Data Science │ WASM DataFrame, distribution calculus, p-value power analysis. │
├──────────────────────────────────┼────────────────────────────────────────────────────────────────┤
│ Kit 4: Molecular Organic Chem    │ 2D molecular graph AST, formal charges, arrow-pushing parser.  │
├──────────────────────────────────┼────────────────────────────────────────────────────────────────┤
│ Kit 5: Optics & Wave Physics     │ Ray-tracing Snell matrix, diffraction gratings, thin films.    │
├──────────────────────────────────┼────────────────────────────────────────────────────────────────┤
│ Kit 6: Robotics & Control Systems│ Forward/inverse kinematics, Denavit-Hartenberg, PID loop tuner.│
└──────────────────────────────────┴────────────────────────────────────────────────────────────────┘
```

---

### Kit 1: Electrical Circuits & SPICE Engine (`circuits`)

#### 1. Core Epistemology & Value
Electrical engineering requires transitioning from simple resistor networks to dynamic reactive circuits (inductors, capacitors, semiconductors). This kit embeds an offline Modified Nodal Analysis (MNA) matrix solver directly in the browser.

#### 2. Concrete Interactive Simulator (`CircuitsSim.jsx`)
- **Declarative Netlist AST**:
  ```json
  {
    "kind": "circuits",
    "components": [
      {"id": "V1", "type": "dc_voltage", "nodes": [1, 0], "value": 12.0},
      {"id": "R1", "type": "resistor", "nodes": [1, 2], "value": 1000},
      {"id": "C1", "type": "capacitor", "nodes": [2, 0], "value": 1e-6},
      {"id": "L1", "type": "inductor", "nodes": [2, 3], "value": 0.05}
    ]
  }
  ```
- **Modified Nodal Analysis (MNA) Engine**:
  Solves $\mathbf{A} \mathbf{x} = \mathbf{z}$ where:
  $$\begin{pmatrix} \mathbf{G} & \mathbf{B} \\ \mathbf{C} & \mathbf{D} \end{pmatrix} \begin{pmatrix} \mathbf{v} \\ \mathbf{j} \end{pmatrix} = \begin{pmatrix} \mathbf{i} \\ \mathbf{e} \end{pmatrix}$$
  - Computes DC operating points, AC frequency response (Bode magnitude & phase plots), and transient response (step/impulse).
- **Interactive Oscilloscope**: Scrubbing time controls shows voltage and current waveforms across any two probed circuit nodes.

#### 3. Deterministic Practice Types
- `circuit_dc_analysis`: Calculate branch currents and node voltages using Kirchhoff's laws.
- `thevenin_equivalent`: Calculate equivalent open-circuit voltage $V_{\text{th}}$ and Thevenin resistance $R_{\text{th}}$.
- `bode_cutoff_calc`: Identify 3dB cutoff frequency $f_c$ and filter classification (low-pass, high-pass, band-pass).

---

### Kit 2: Computer Systems & Architecture (`systems`)

#### 1. Core Epistemology & Value
Computer science students must bridge abstract programming with physical hardware. This kit visualizes the von Neumann cycle, micro-architecture data paths, and assembly execution.

#### 2. Concrete Interactive Simulator (`ArchSim.jsx`)
- **RISC-V / MIPS Register Machine**:
  - 16-bit / 32-bit registers (`$zero`, `$t0-$t7`, `$s0-$s7`, `$pc`, `$sp`).
  - Memory: Byte-addressable RAM (text segment, data segment, stack).
  - Micro-operations: Clock-by-clock visualization of Fetch $\to$ Decode $\to$ Execute $\to$ Memory $\to$ Writeback.
- **Pipelining & Hazard Workbench**:
  - 5-stage pipeline (IF, ID, EX, MEM, WB).
  - Demonstrates structural hazards, data hazards (RAW dependency stalls vs forwarding/bypassing), and control hazards (branch prediction flush).
- **Memory Hierarchy & Cache Simulator**:
  - Configurable cache: Direct-mapped vs. 2-way/4-way set-associative.
  - Line replacement policies: LRU (Least Recently Used), FIFO.
  - Live hit/miss rate gauge and memory block address decomposition (Tag, Set Index, Block Offset).

#### 3. Deterministic Practice Types
- `pipeline_hazard_spot`: Given an assembly sequence, identify data hazard clock stalls and insert optimal forwarding paths.
- `cache_address_decode`: Decompose 32-bit hex memory addresses into Tag, Set, and Offset bits based on cache geometry.
- `assembly_step_trace`: Trace register states after executing basic arithmetic, branch, and memory operations.

---

### Kit 3: Statistics & Data Science (`stats`)

#### 1. Core Epistemology & Value
Statistical literacy requires understanding sampling distributions, hypothesis testing errors, and regression modeling without black-box software obscuring the mathematics.

#### 2. Concrete Interactive Simulator (`StatsSim.jsx`)
- **Distribution Calculus Engine**:
  - Interactive PDF/CDF visualizer: Normal $\mathcal{N}(\mu, \sigma^2)$, Student's $t$, Chi-square $\chi^2(k)$, F-distribution, Poisson, and Binomial.
  - Sliders for sample size $n$, degrees of freedom, and effect size Cohen's $d$.
- **Hypothesis Testing & Power Visualizer**:
  - Dual-curve visualizer illustrating null hypothesis $H_0$ vs alternative hypothesis $H_1$.
  - Shaded interactive zones for significance level $\alpha$ (Type I error), critical threshold $z^*$, $\beta$ (Type II error), and statistical power ($1 - \beta$).
- **Ordinary Least Squares (OLS) Regression Sandbox**:
  - Interactive scatter plot: Students drag points to observe real-time recalculation of slope $\hat{\beta}_1$, intercept $\hat{\beta}_0$, residual sum of squares (RSS), $R^2$, and leverage/Cook's distance.

#### 3. Deterministic Practice Types
- `p_value_decision`: Given test statistics, degrees of freedom, and significance level $\alpha$, compute exact $p$-value and reject/fail-to-reject decision.
- `confidence_interval_calc`: Calculate two-sided confidence intervals from sample mean $\bar{x}$, standard error $s/\sqrt{n}$, and critical value $t^*$.
- `regression_residual_audit`: Identify high-leverage outliers and heteroskedasticity patterns on residual plots.

---

### Kit 4: Molecular Organic Chemistry (`organics`)

#### 1. Core Epistemology & Value
Organic chemistry requires spatial 3D visualization and electronic arrow-pushing formalism. This kit provides a deterministic 2D/3D molecular graph engine.

#### 2. Concrete Interactive Simulator (`MolecularSim.jsx`)
- **Declarative Molecular Graph AST**:
  ```json
  {
    "kind": "molecule",
    "atoms": [
      {"id": "C1", "element": "C", "coords": [0, 0, 0]},
      {"id": "O1", "element": "O", "coords": [1.2, 0, 0]}
    ],
    "bonds": [
      {"atoms": ["C1", "O1"], "order": 2}
    ]
  }
  ```
- **Formal Charge & Octet Auditor**:
  - Evaluates valence electrons, lone pairs, and formal charge for every atom:
    $$\text{FC} = V - N_{\text{non-bonding}} - \frac{1}{2} B_{\text{bonding}}$$
  - Automatically flags octet rule violations or unfilled valences.
- **Electron Arrow-Pushing Workbench**:
  - Reactive canvas where students draw curved arrows indicating electron pair transfer from nucleophilic lone pair/$\pi$-bond to electrophilic center.
  - Generates intermediate resonance structures and product geometries automatically.

#### 3. Deterministic Practice Types
- `stereocenter_rs`: Assign Cahn-Ingold-Prelog (CIP) priority rules to four substituents and identify $(R)$ or $(S)$ absolute configuration.
- `formal_charge_assign`: Calculate formal charge across polyatomic ions and resonance hybrids.
- `reaction_mechanism_classify`: Classify aliphatic substitution/elimination pathways ($\text{S}_\text{N}1$, $\text{S}_\text{N}2$, $\text{E}1$, $\text{E}2$) based on substrate hindrance, nucleophile strength, solvent, and temperature.

---

### Kit 5: Classical Optics & Wave Physics (`optics`)

#### 1. Core Epistemology & Value
Optics unifies geometrical ray tracing with physical wave interference. This kit provides an interactive optical bench modeling reflection, refraction, thin lenses, and wave diffraction.

#### 2. Concrete Interactive Simulator (`OpticsSim.jsx`)
- **Geometrical Ray-Tracing Bench**:
  - Optical axis with movable components: Thin convex/concave lenses, planar/curved spherical mirrors, prisms, glass blocks.
  - Real-time ray tracing (parallel ray, focal ray, central ray) computing image distance $d_i$, magnification $m = -d_i/d_o$, and real vs. virtual image inversion.
  - Snell's Law refractor ($n_1 \sin\theta_1 = n_2 \sin\theta_2$) demonstrating total internal reflection and critical angle $\theta_c = \arcsin(n_2/n_1)$.
- **Wave Interference & Diffraction Grating Engine**:
  - Simulates Young's double-slit experiment ($d \sin\theta = m \lambda$) and multiple-slit diffraction gratings.
  - Computes continuous optical intensity pattern $I(\theta) = I_0 \cos^2(\beta) \left(\frac{\sin\alpha}{\alpha}\right)^2$ with real-time wavelength slider ($\lambda = 380\text{ nm} \to 750\text{ nm}$).

#### 3. Deterministic Practice Types
- `thin_lens_equation`: Calculate focal length, object distance, or image distance with proper sign conventions.
- `snell_refraction_calc`: Compute refraction angle and critical angle for dielectric interfaces.
- `diffraction_fringe_spacing`: Calculate linear fringe distance $y_m = \frac{m \lambda L}{d}$ on a distant projection screen.

---

### Kit 6: Control Systems & Robotics Kinematics (`robotics`)

#### 1. Core Epistemology & Value
Modern engineering requires feedback control loops and multi-link kinematic mechanics. This kit provides an interactive 2D/3D robot arm linkage simulator and dynamic PID controller tuning bench.

#### 2. Concrete Interactive Simulator (`RoboticsSim.jsx`)
- **Multi-Link Planar Kinematics Workbench**:
  - $N$-link revolute robotic arm ($L_1, \theta_1, L_2, \theta_2, \dots, L_n, \theta_n$).
  - **Forward Kinematics**: Computes end-effector position $(x_e, y_e)$ via Denavit-Hartenberg transformation matrices.
  - **Inverse Kinematics**: Interactive target dragging with real-time Jacobian pseudoinverse solver ($J^\dagger = J^T (J J^T)^{-1}$) and singularity avoidance damping.
- **Closed-Loop PID Control Simulator**:
  - Feedback control system: $u(t) = K_p e(t) + K_i \int_0^t e(\tau)d\tau + K_d \frac{de(t)}{dt}$.
  - Sliders for proportional gain $K_p$, integral gain $K_i$, and derivative gain $K_d$.
  - Real-time step-response graph displaying rise time $t_r$, overshoot percentage $M_p$, settling time $t_s$, and steady-state error $e_{\text{ss}}$.

#### 3. Deterministic Practice Types
- `forward_kinematics_coord`: Given link lengths and joint angles, calculate Cartesian end-effector coordinates.
- `pid_tuning_diagnosis`: Given a sluggish, oscillating, or unstable step response curve, adjust $K_p, K_i, K_d$ to satisfy transient performance specifications.
- `jacobian_singularity`: Identify joint configurations where the robot arm loses degrees of freedom ($\det(J) = 0$).

---

## 4. Antigravity CLI (agy) Integration & Authoring Directives

When authoring or updating STEM courses via the Antigravity CLI (`agy`), autonomous agents should follow these directives:

### 4.1 Authoring SimSpec Simulations via MCP
1. First call `simulation_guide` to inspect the latest grammar and widget schemas.
2. Formulate the JSON spec conforming to `kind: "particles"`, `kind: "graph"`, `kind: "math"`, `kind: "chem"`, or `kind: "geometry"`.
3. Call `validate_simulation` with the spec payload. Fix any syntax errors reported by `simspec.py`.
4. Call `attach_simulation` with `topic_id` and the validated spec.

### 4.2 Safe Fenced Execution Guidelines
- `andedu-companion` agent (`.agents/agents/`): Runs under fenced execution (`AGY_CLI=1`), restricted from issuing shell commands or accessing network. Writes only to `content/agy_drafts/<id>.json`.
- `page-guard`: Inspects every draft lesson before merging into production topics. Validates:
  - No prompt injections.
  - LaTeX formulas formatted without `$` inside cheat-sheets, and with `$...$` / `$$...$$` in markdown.
  - Quiz answer indices are integers matching `options` indices.
  - Practice puzzle schemas pass normalizers.
