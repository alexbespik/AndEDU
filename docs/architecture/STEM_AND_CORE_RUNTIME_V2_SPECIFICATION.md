# STEM & Core Runtime Engine V2: Architectural Specification & Implementation Blueprint

**Document Version**: 2.0.0  
**Status**: APPROVED ARCHITECTURAL SPECIFICATION  
**Author**: Lead Systems Architect  
**Audience**: `coder`, `tester`, `reviewer`, `security`, `overseer`, Frontier AI Agents  

---

## 1. Executive Summary & Audit Resolution Matrix

This specification establishes the unified architecture for the **&.edu STEM & Core Runtime Engine V2 Upgrade**, directly resolving the 6 Mental Opponent Audit findings identified in the STEM blueprint.

| Finding / Component | Root Cause in V1 | Architectural Solution in V2 | Verification Strategy |
| :--- | :--- | :--- | :--- |
| **1. Deterministic FBD Vector Grader** (`fbd_grader.py` & `server.py`) | Multimodal vision LLM dependency in `/api/draw/check`; hallucination on angles and magnitudes; non-deterministic offline failures. | Deterministic vector scene graph evaluator in Python. Extracts arrows & text labels from `DrawingBoard`; validates tail anchor, angle $\theta \pm 5^\circ$, length ratios, and physical equilibrium. LLM strictly opt-in fallback when vectors absent. | Unit tests comparing known FBD vector topologies, inclined planes, and pulley systems against tolerances. |
| **2. XPBD Velocity Projection & Symplectic Integrator** (`SpecSim.jsx`) | Ad-hoc radial velocity subtraction in rod constraint loop causing phantom energy drift and linkage explosion in double pendulums. | Position-Based Dynamics (PBD/XPBD) loop: store $(x_{\text{prev}}, y_{\text{prev}})$, apply position relaxation across rods, project constrained velocity state: $\mathbf{v} = (\mathbf{x} - \mathbf{x}_{\text{prev}}) / \Delta t$. | Energy drift benchmark: double pendulum and 3-link rod chain run for 120s with $\le 0.5\%$ Hamiltonian drift. |
| **3. Dual-Number Jet2 AutoDiff & Even-Pole Detection** (`dual_autodiff.js`, `expr.js`, `MathLab.jsx`) | Central finite-difference $O(\epsilon_{\text{mach}}^{2/3})$ cancellation; GraphTab connects false lines across even poles ($\frac{1}{(x-2)^2}, \sec^2 x$). | Jet2 dual numbers $(v, d_1, d_2)$ on Pratt AST for machine-precision 1st/2nd derivatives; reciprocal-zero $g(x)=1/f(x)$ & curvature divergence pole guards in GraphTab. | Analytical derivative assertions ($\sin x, \ln x, x^4$); rendering test verifying vertical break on even poles without spurious line segments. |
| **4. Polyprotic Titration Charge-Balance Solver** (`chemspec.py`, `ChemSim.jsx`) | Single $K_a$ weak-acid equation; inability to simulate $\text{H}_2\text{SO}_4$, $\text{H}_3\text{PO}_4$, multi-stage buffers, or continuous dilution. | Rigorous $N$-protic polynomial charge-balance solver: $h - \frac{K_w}{h} + C_b - C_{a,\text{tot}} \sum j \alpha_j(h) = 0$ with continuous dilution across burette volume additions. | Titration curves for $\text{H}_3\text{PO}_4$ ($pK_a = [2.15, 7.20, 12.35]$) matching analytical equivalence points at $V_1, 2V_1, 3V_1$. |
| **5. Subprocess Sandbox Hardening & Docker Alignment** (`sandbox_preamble.py`, `server.py`, `Dockerfile`) | Subprocess execution allows arbitrary socket, subprocess, sqlite3, or filesystem traversal to `content/edu_studio.db`; Dockerfile uses outdated Python 3.12. | Injected `sandbox_preamble.py` enforcing PEP 578 `sys.addaudithook` blocking network, child processes, sqlite3, and fs outside scratchpad; Docker base updated to `python:3.14-slim`. | Security test attempting exfiltration of `edu_studio.db` and socket connection raising immediate `PermissionError`. |
| **6. Typed Cardinality & Credit-Pool AST for Advisor** (`advisor_rules.py`, `advisor.py`) | Rigid Conjunctive Normal Form (CNF) lists unable to represent $k$-of-$n$, credit pools, or minimum grade rules. | Typed requirement AST nodes: `all`, `k_of_n`, `credit_pool`, `min_grade`; degree audit templates for W&M CS, Data Science, and Columbia 3+2 Combined Plan. | Audit test validating W&M CS BS (120 cr, 12 cr 300+ CS electives) and Columbia 3+2 foundational pre-engineering suites. |
| **7. 5 New STEM & Engineering Lab Kits** (`practice_ee`, `ai`, `systems`, `stats`, `bio`) | Missing deterministic practice types for upper-division engineering and science disciplines. | 5 flat root modules (20 practice types) with standard library only `NORMALIZERS` and server-side `GRADERS`. | 20 unit test suites validating normalization, valid student answer grading, and bad submission rejection. |

---

## 2. Invariants & System Constraints

1. **Flat-File Root Architecture**: All backend additions MUST be flat `.py` files in the repository root (e.g. `fbd_grader.py`, `sandbox_preamble.py`, `advisor_rules.py`, `practice_ee.py`, etc.). The Electron desktop packager copies only `*.py` from the root directory. Subdirectory packages are strictly prohibited.
2. **Pure Standard Library**: Backend engine modules must import ONLY the Python standard library (`math`, `re`, `typing`, `json`, `dataclasses`, `sys`, `os`, `pathlib`). No external dependencies (`numpy`, `scipy`, `sympy`) are permitted.
3. **Safe Client Expression Grammar**: All interactive simulations remain data-driven JSON specs (SimSpec v1 / ChemSpec v1). Client-side expressions evaluate via `src/lib/expr.js` closures without `eval()` or `new Function()`.
4. **Air-Gapped & Offline Verification**: Every component must function and pass test suites completely offline without an internet connection or Gemini API credentials (`SCIEDU_ELEVENLABS=0`, loopback testing only).

---

## 3. Component Architectural Specifications

### 3.1 Deterministic Free-Body Diagram (FBD) Grader (`fbd_grader.py` & `server.py`)

#### 3.1.1 Problem & Scene Representation
The student constructs drawings on `DrawingBoard.jsx`. When an FBD problem is active, the canvas sends both the raster PNG and the structured vector shapes list:
```json
{
  "image": "data:image/png;base64,...",
  "shapes": [
    { "id": 1, "type": "arrow", "x1": 500, "y1": 300, "x2": 500, "y2": 420, "color": "#1b1f1d" },
    { "id": 2, "type": "text", "x1": 510, "y1": 425, "text": "mg", "size": 16, "color": "#1b1f1d" },
    { "id": 3, "type": "arrow", "x1": 500, "y1": 300, "x2": 500, "y2": 180, "color": "#1b1f1d" },
    { "id": 4, "type": "text", "x1": 510, "y1": 175, "text": "N", "size": 16, "color": "#1b1f1d" }
  ],
  "fbd_spec": {
    "body_origin": [500, 300],
    "origin_tol_px": 40.0,
    "targets": [
      { "name": "gravity", "aliases": ["mg", "w", "fg"], "angle_deg": 270.0, "angle_tol_deg": 5.0, "required": true },
      { "name": "normal", "aliases": ["n", "fn"], "angle_deg": 90.0, "angle_tol_deg": 5.0, "required": true }
    ],
    "magnitude_comparisons": [
      { "vector_a": "normal", "op": "eq", "vector_b": "gravity", "ratio_tol": 0.25 }
    ],
    "forbidden_forces": ["centrifugal", "ma", "motion"]
  }
}
```

#### 3.1.2 Coordinate System & Mathematical Extraction
1. **Screen-to-Cartesian Angle Transformation**:
   In HTML5 SVG/Canvas, $y$ increases downwards. The standard mathematical Cartesian angle $\theta$ (where $0^\circ = \text{right}$, $90^\circ = \text{up}$, $180^\circ = \text{left}$, $270^\circ = \text{down}$) is:
   $$\Delta x = x_2 - x_1, \quad \Delta y_{\text{math}} = -(y_2 - y_1)$$
   $$\theta = \left(\operatorname{atan2}(\Delta y_{\text{math}}, \Delta x) \times \frac{180}{\pi}\right) \pmod{360^\circ}$$
2. **Length**:
   $$L = \sqrt{(x_2 - x_1)^2 + (y_2 - y_1)^2}$$
3. **Text Association**:
   A text shape $(x_t, y_t, \text{text})$ is associated with the arrow if the Euclidean distance from $(x_t, y_t)$ to the arrow tip $(x_2, y_2)$ or midpoint $\left(\frac{x_1+x_2}{2}, \frac{y_1+y_2}{2}\right)$ is $\le 50\text{ px}$.
4. **Origin Attachment**:
   The vector's tail $(x_1, y_1)$ must lie within `origin_tol_px` of `body_origin`.

#### 3.1.3 Evaluator Output Contract
`fbd_grader.grade_fbd(shapes, fbd_spec) -> Dict[str, Any]` returns:
```json
{
  "score": 1.0,
  "passed": true,
  "criteria": [
    { "criterion": "Downward gravitational force (mg)", "met": true, "comment": "Found vector 'mg' at 270.0°" },
    { "criterion": "Upward normal force (N)", "met": true, "comment": "Found vector 'N' at 90.0°" },
    { "criterion": "Normal force equals weight in magnitude", "met": true, "comment": "Magnitudes match within tolerance" }
  ],
  "feedback": "Correct. Gravity acts straight down from the center of mass, and the normal force balances it vertically.",
  "describe": "Free-body diagram showing equal and opposite normal and gravitational forces.",
  "deterministic": true
}
```
If `shapes` contains no arrows or `fbd_spec` is omitted, `server.py` delegates to Gemini Vision LLM.

---

### 3.2 XPBD Velocity Projection & Symplectic Integrator (`src/simulations/SpecSim.jsx`)

#### 3.2.1 Problem Formulation
In previous releases, rod constraints iteratively moved particle positions, then adjusted velocities by projecting out the radial component $v_{\text{rad}}$. In multi-link systems (double pendulums, linkages), this created a mismatch between the velocity state and the constrained position trajectory:
$$\mathbf{x}_{t+\Delta t} - \mathbf{x}_t \neq \mathbf{v}_{t+\Delta t} \Delta t$$
This error accumulated as fictitious kinetic energy, causing unphysical acceleration.

#### 3.2.2 Mathematical XPBD Algorithm
For each substep of duration $\Delta t_{\text{sub}}$:
1. **Pre-step Cache**:
   For each particle $i$:
   $$\mathbf{x}_{\text{prev}, i} = \mathbf{x}_i$$
2. **Explicit Velocity & Position Candidate Integration**:
   $$\mathbf{v}_i \leftarrow \mathbf{v}_i + \frac{\mathbf{F}_{\text{ext}, i}}{m_i} \Delta t_{\text{sub}}$$
   $$\mathbf{x}_i \leftarrow \mathbf{x}_i + \mathbf{v}_i \Delta t_{\text{sub}}$$
3. **Iterative Distance Constraint Relaxation (PBD)**:
   For iteration $k \in \{1, \dots, N_{\text{iter}}\}$ ($N_{\text{iter}} = 8$):
   For each rod link between particles $i$ and $j$ with rest length $L_0$:
   $$\mathbf{d} = \mathbf{x}_j - \mathbf{x}_i, \quad d = \|\mathbf{d}\|$$
   $$\mathbf{n} = \frac{\mathbf{d}}{d}, \quad C = d - L_0$$
   $$\Delta \mathbf{x}_i = +\frac{w_i}{w_i + w_j} C \mathbf{n}, \quad \Delta \mathbf{x}_j = -\frac{w_j}{w_i + w_j} C \mathbf{n}$$
   where inverse mass $w_i = \begin{cases} 0 & \text{if particle } i \text{ is fixed} \\ 1/m_i & \text{otherwise} \end{cases}$.
   *(Note: Velocities are NOT modified in this relaxation loop).*
4. **XPBD Velocity Projection**:
   After all position constraints, wall boundaries, and ground collisions are satisfied:
   $$\mathbf{v}_i \leftarrow \frac{\mathbf{x}_i - \mathbf{x}_{\text{prev}, i}}{\Delta t_{\text{sub}}}$$
This guarantees exact geometric consistency and Hamiltonian conservation across simulation time.

---

### 3.3 Dual-Number Jet2 AutoDiff & Even-Pole Detection (`src/lib/dual_autodiff.js`, `src/lib/expr.js`, `src/components/MathLab.jsx`)

#### 3.3.1 Dual-Number Jet2 Algebra
A second-order Jet (truncated Taylor expansion) is represented as:
$$J = (v, d_1, d_2) \iff v + d_1 \epsilon + \frac{1}{2} d_2 \epsilon^2$$
Algebraic operations are defined without approximation:
- **Sum**: $(u_0 + v_0, u_1 + v_1, u_2 + v_2)$
- **Difference**: $(u_0 - v_0, u_1 - v_1, u_2 - v_2)$
- **Product**: $(u_0 v_0, u_1 v_0 + u_0 v_1, u_2 v_0 + 2 u_1 v_1 + u_0 v_2)$
- **Quotient**:
  $$w_0 = \frac{u_0}{v_0}, \quad w_1 = \frac{u_1 - w_0 v_1}{v_0}, \quad w_2 = \frac{u_2 - 2 w_1 v_1 - w_0 v_2}{v_0}$$
- **Chain Rule for Elementary Function $f(u)$**:
  $$w_0 = f(u_0), \quad w_1 = f'(u_0) u_1, \quad w_2 = f''(u_0) u_1^2 + f'(u_0) u_2$$

#### 3.3.2 Pratt AST Jet2 Compilation
`src/lib/dual_autodiff.js` compiles expressions into Jet2 evaluators. For variable $x$ at $x_0$, the input Jet is seeded as $X = (x_0, 1, 0)$. The resulting evaluation produces $(f(x_0), f'(x_0), f''(x_0))$ with exact machine precision in a single pass.

#### 3.3.3 Even-Order Pole Detection in GraphTab
In `MathLab.jsx`, curves with even-order poles (e.g. $f(x) = \frac{1}{(x-2)^2}$, $f(x) = \sec^2 x$) do not exhibit sign flips because $y \to +\infty$ from both directions.
The GraphTab renderer detects these through a dual-guard criteria:
1. **Reciprocal Zero Test**:
   Evaluate $g(x) = \frac{1}{f(x)}$. A pole in $f(x)$ corresponds to an isolated zero in $g(x)$. If $|g(x_k)| < 10^{-4}$ and $|g(x_{k+1})| < 10^{-4}$, but $|f(x)| > 3H$, an asymptote exists between pixels $k$ and $k+1$.
2. **Second-Difference Curvature Guard**:
   $$\Delta^2 y_k = y_{k+1} - 2y_k + y_{k-1}$$
   If $y_k$ and $y_{k+1}$ are both positive (or both negative) off-screen and $\Delta^2 y_k$ diverges, the path breaks (`pen = false`). The renderer renders the curve discontinously and prevents drawing false horizontal bridges across asymptotes.

---

### 3.4 Polyprotic Titration Charge-Balance Solver (`chemspec.py` & `src/simulations/ChemSim.jsx`)

#### 3.4.1 Equilibrium Chemistry & Charge Balance
For an $N$-protic weak acid $\text{H}_N\text{A}$ titrated with strong base $\text{NaOH}$:
- Initial volume $V_a$, acid concentration $C_a$.
- Titrant added volume $V_b$, titrant concentration $C_b$.
- Total solution volume: $V_{\text{tot}} = V_a + V_b$.
- Analytical total concentrations under continuous dilution:
  $$C_{A,\text{tot}} = \frac{C_a V_a}{V_a + V_b}, \quad [\text{Na}^+] = \frac{C_b V_b}{V_a + V_b}$$
- Dissociation constants: $K_{a,1}, K_{a,2}, \dots, K_{a,N}$.
- Let $h = [\text{H}^+]$. The system species fractions are:
  $$P_0 = h^N, \quad P_j = h^{N-j} \prod_{m=1}^j K_{a,m} \quad (\text{for } j \ge 1)$$
  $$D(h) = \sum_{j=0}^N P_j, \quad \alpha_j(h) = \frac{P_j}{D(h)}$$
- Total negative charge from deprotonated acid:
  $$[\text{Charge}]_{\text{acid}} = C_{A,\text{tot}} \sum_{j=1}^N j \alpha_j(h)$$
- Strict Charge Balance Equation:
  $$F(\log_{10} h) = h - \frac{K_w}{h} + [\text{Na}^+] - C_{A,\text{tot}} \sum_{j=1}^N j \alpha_j(h) = 0$$

#### 3.4.2 Mathematical Properties & Solver
$\frac{\partial F}{\partial h} > 0$ strictly across $(0, \infty)$, guaranteeing unconditional monotonic convergence under bisection on $\log_{10} h \in [-14.0, 1.0]$. 70 iterations yield $\Delta \text{pH} < 10^{-6}$.
For strong first dissociation ($\text{H}_2\text{SO}_4$), $K_{a,1} \to \infty$ sets $P_0 = 0$, $P_1 = h$, $P_2 = K_{a,2}$.

---

### 3.5 Subprocess Sandbox Hardening & Docker Alignment (`sandbox_preamble.py`, `server.py`, `Dockerfile`)

#### 3.5.1 CPython PEP 578 Audit Hook Architecture
`sandbox_preamble.py` installs an immutable audit hook before any user code executes:
```python
import sys, os

_SCRATCHPAD = os.path.realpath(os.environ.get("SCIEDU_SCRATCHPAD", os.getcwd()))

def _audit_hook(event: str, args: tuple) -> None:
    # 1. Block network sockets
    if event.startswith("socket."):
        raise PermissionError(f"[SECURITY] Sandbox network access blocked: {event}")
    # 2. Block child processes
    if event in ("subprocess.Popen", "os.system", "os.posix_spawn", "os.spawn"):
        raise PermissionError(f"[SECURITY] Sandbox subprocess execution blocked: {event}")
    # 3. Block SQLite database engines (prevents reading edu_studio.db)
    if event.startswith("sqlite3."):
        raise PermissionError("[SECURITY] Sandbox database access blocked")
    # 4. Restrict filesystem I/O to scratchpad
    if event in ("open", "os.remove", "os.rename", "os.mkdir", "os.rmdir", "os.scandir", "os.listdir"):
        target = args[0] if args else None
        if isinstance(target, (str, bytes, os.PathLike)):
            try:
                resolved = os.path.realpath(target)
                if not resolved.startswith(_SCRATCHPAD):
                    raise PermissionError(f"[SECURITY] Access outside scratchpad blocked: {target}")
            except Exception:
                raise PermissionError("[SECURITY] Path resolution error")

sys.addaudithook(_audit_hook)
```

#### 3.5.2 Dockerfile Alignment
1. Update base image from `python:3.12-slim` to `python:3.14-slim`.
2. Update flat file `COPY` manifest to include all new core engine modules.

---

### 3.6 Typed Cardinality & Credit-Pool AST for Academic Advisor (`advisor_rules.py`, `advisor.py`)

#### 3.6.1 AST Schema
Requirement rules are expressed as typed JSON AST nodes:
```json
{
  "type": "k_of_n",
  "k": 2,
  "children": [
    { "type": "course", "code": "CSCI 303", "min_grade": "C-" },
    { "type": "course", "code": "CSCI 304", "min_grade": "C-" },
    { "type": "course", "code": "CSCI 312", "min_grade": "C-" }
  ]
}
```
Available node types:
- `course`: `{type: "course", code: str, min_grade: str}`
- `all`: `{type: "all", children: List[Node]}`
- `any`: `{type: "any", children: List[Node]}`
- `k_of_n`: `{type: "k_of_n", k: int, children: List[Node]}`
- `credit_pool`: `{type: "credit_pool", min_credits: float, pool: List[str], dept: str, min_level: int}`
- `min_grade`: `{type: "min_grade", code: str, min_grade: str}`

#### 3.6.2 Degree Audit Templates
1. **William & Mary CS (B.S.)**:
   - Math core: `MATH 111`, `MATH 112`, `MATH 109` (or `MATH 211`).
   - CS core: `CSCI 141`, `CSCI 241`, `CSCI 243` (or `MATH 214`), `CSCI 301`, `CSCI 303`, `CSCI 304`, `CSCI 312`, `CSCI 423`, `CSCI 400`.
   - CS electives: `CreditPoolNode(min_credits=12.0, dept="CSCI", min_level=300)`.
   - General degree: 120 total credits, COLL curriculum.
2. **William & Mary Data Science (B.S.)**:
   - Core: `DATA 101`, `DATA 141`, `DATA 201`, `DATA 301`, `DATA 400`.
   - Math & Probability: `MATH 111`, `MATH 112`, `MATH 109`/`211`, `MATH 351`/`451` / `DATA 302`.
   - Domain electives: 15 credits from `DATA`, `CSCI`, `MATH`, `APSC`, `ECON`.
3. **Columbia University 3+2 Combined Plan Pre-Engineering**:
   - Foundational Coursework:
     - Math: Calculus I, II, Multivariable (`MATH 212`/`213`), Linear Algebra (`MATH 109`/`211`), Differential Equations (`MATH 302`).
     - Physics: Mechanics + Lab (`PHYS 101`/`101L`), E&M + Lab (`PHYS 102`/`102L`).
     - Chemistry: General Chemistry I + Lab (`CHEM 103`/`103L`).
     - Computer Science: Modern Programming Fundamentals (`CSCI 141`).
     - Economics: Intro Economics (`ECON 101` or `ECON 102`).
     - English / Writing: Seminar / Composition (`COLL 150`).
   - Major Track Specific Add-ons (e.g. Electrical Engineering: Modern Physics `PHYS 201`, Electric Circuits).

---

### 3.7 5 New STEM & Engineering Lab Kits (20 Practice Types)

All modules are flat files in the repository root, standard library only, exporting `NORMALIZERS` and `GRADERS`.

```
practice_ee.py       ──► Electrical Engineering (DC, Thevenin, Bode, Op-Amp)
practice_ai.py       ──► Artificial Intelligence (Gradient Descent, Confusion Matrix, Attention, Conv Output)
practice_systems.py  ──► Computer Systems (Pipeline Hazards, Cache Decode, Assembly Trace, Virtual Memory)
practice_stats.py    ──► Statistics & Data Science (P-Value, Confidence Interval, Bayes Posterior, Residuals)
practice_bio.py      ──► Quantitative Biology (DNA Translation, Hardy-Weinberg, Michaelis-Menten, GC-Content)
```

#### Detailed Practice Types Specification:
1. `practice_ee.py`:
   - `circuit_dc_analysis`: Solves linear resistor networks with DC voltage sources using Ohm's Law and KCL. Checks student currents (A) and node voltages (V) within 2% tolerance.
   - `thevenin_equivalent`: Computes open-circuit voltage $V_{\text{th}}$ and equivalent resistance $R_{\text{th}}$ looking into a designated terminal pair.
   - `bode_cutoff_calc`: Solves for 3dB corner frequency $f_c = \frac{1}{2\pi R C}$ or $\frac{R}{2\pi L}$ and classifies filter response (low-pass, high-pass, band-pass).
   - `opamp_gain_calc`: Solves closed-loop voltage gain $A_v = -R_f / R_{\text{in}}$ (inverting) or $1 + R_f / R_1$ (non-inverting).

2. `practice_ai.py`:
   - `gradient_descent_step`: Trace single weight update $w_{t+1} = w_t - \eta \frac{\partial L}{\partial w}$.
   - `confusion_matrix_metrics`: Calculate precision $\frac{\text{TP}}{\text{TP}+\text{FP}}$, recall $\frac{\text{TP}}{\text{TP}+\text{FN}}$, or $F_1 = 2 \frac{P \cdot R}{P + R}$ from raw confusion counts.
   - `attention_score_calc`: Given query and key vectors $q, k$ and dimension $d_k$, compute scaled dot-product $\frac{q \cdot k}{\sqrt{d_k}}$ and softmax weight.
   - `convolution_output_dim`: Compute output spatial dimension $\lfloor \frac{W - K + 2P}{S} \rfloor + 1$.

3. `practice_systems.py`:
   - `pipeline_hazard_spot`: Identifies data hazards (RAW), requires stall cycles or forwarding paths, and identifies control hazard penalties.
   - `cache_address_decode`: Given address $A$, cache size, block size, and associativity $N$, decomposes $A$ into Tag, Set Index, and Offset bit ranges.
   - `assembly_step_trace`: Traces register file contents ($t0, t1, s0$) and memory after executing a 3-5 instruction RISC-V sequence.
   - `virtual_memory_translate`: Calculates Virtual Page Number (VPN), Page Offset, checks page table mapping, and computes Physical Address.

4. `practice_stats.py`:
   - `p_value_decision`: Computes two-sided or one-sided test decision given test statistic, df, and $\alpha$.
   - `confidence_interval_calc`: Computes margin of error $E = z^* \frac{\sigma}{\sqrt{n}}$ or $t^* \frac{s}{\sqrt{n}}$ and interval bounds.
   - `bayes_posterior_calc`: Solves $P(H|E) = \frac{P(E|H)P(H)}{P(E|H)P(H) + P(E|\neg H)P(\neg H)}$ to 3 decimal places.
   - `regression_residual_audit`: Computes residual $e_i = y_i - (\beta_0 + \beta_1 x_i)$ and identifies outlier leverage.

5. `practice_bio.py`:
   - `dna_transcription_translate`: Transcribes DNA ($5' \to 3'$) to mRNA and translates codons into single-letter amino acid sequence using the universal standard genetic code.
   - `hardy_weinberg_calc`: Calculates allele frequencies $p, q$ and homozygous/heterozygous carrier frequencies ($p^2, 2pq, q^2$).
   - `enzyme_michaelis_menten`: Computes initial rate $v_0 = \frac{V_{\max}[S]}{K_m + [S]}$ and Lineweaver-Burk parameters.
   - `genomic_gc_content`: Calculates GC% percentage and estimated primer annealing temperature $T_m = 64.9 + 41 \frac{yG + zC - 16.4}{wA + xT + yG + zC}$.

---

## 4. Integration Map & Registration in `server.py`

### 4.1 Practice Normalizers & Graders
In `server.py`:
```python
import practice_ee
import practice_ai
import practice_systems
import practice_stats
import practice_bio

for _m in (practice_ee, practice_ai, practice_systems, practice_stats, practice_bio):
    PRACTICE_NORMALIZERS.update(_m.NORMALIZERS)

PRACTICE_GRADERS = {
    **getattr(practice_ee, "GRADERS", {}),
    **getattr(practice_ai, "GRADERS", {}),
    **getattr(practice_systems, "GRADERS", {}),
    **getattr(practice_stats, "GRADERS", {}),
    **getattr(practice_bio, "GRADERS", {}),
}
```

### 4.2 Workspace Routing & Classification
In `server.py`:
- `guess_workspace` expands keywords:
  - `code`: additions for `assembly|risc-v|pipeline|cache|hardware|neural net|deep learning|gradient descent|attention`
  - `lab`: additions for `circuit|thevenin|bode|opamp|transcription|codon|enzyme|hardy-weinberg`
  - `math`: additions for `bayes|confidence interval|p-value|hypothesis|regression`

---

## 5. Verification & Testing Strategy

1. **Deterministic Graders**: Unit tests verifying correct calculations, tolerance handling ($\pm 2\%$ for numeric, $\pm 5^\circ$ for vector angles), and malformed payload rejections.
2. **Subprocess Sandbox Security**: Verification test confirming:
   - `socket.socket()` raises `PermissionError`
   - `subprocess.run()` raises `PermissionError`
   - `sqlite3.connect("content/edu_studio.db")` raises `PermissionError`
   - `open("../content/edu_studio.db")` raises `PermissionError`
   - Safe execution inside scratchpad succeeds with return code 0.
3. **Double Pendulum Hamiltonian Energy Conservation**:
   Physics engine test verifying that after 5000 integration steps (at 240 Hz), total energy $E = T + V$ stays within $\pm 0.5\%$ of $E_0$.
4. **Polyprotic Titration Curves**:
   Test that $\text{H}_3\text{PO}_4$ titration with $\text{NaOH}$ exhibits 3 distinct inflection zones with correct pH values at half-equivalence and equivalence points.
5. **Degree Audit Tree Audits**:
   Test that complete transcript satisfies W&M CS B.S., and missing elective credits trigger informative node deficits.
