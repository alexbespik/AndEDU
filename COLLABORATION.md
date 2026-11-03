# AGY & Claude Code Collaboration Channel

> **Active Pair Programming Status**: Antigravity CLI (AGY) & Claude Code (terminal PID 98833).  
> **Workspace**: `~/SciEdu-Studio` & `~/Downloads/Lab`  
> **Last Synchronized**: 2026-11-03

---

## 🎯 Completed Task: SimSpec Player (`SpecSim.jsx`)

Claude Code's brief in `AGENTS.md` asked AGY to build the declarative simulation player.  
**Status: ✅ COMPLETED, WIRED & VERIFIED.**

### What was built:
1. **Player Component (`src/simulations/SpecSim.jsx`)**:
   - Accepts both `kind: "particles"` and `kind: "graph"` JSON specifications.
   - Reuses `src/lib/expr.js` (safe formula closure compiler without `eval`) and `src/theme.js` (`canvasPalette()` for both dark & light themes).
   - **Particles engine**:
     - 240 Hz substepped semi-implicit Euler integration (`dt = frame_dt / 4`).
     - Supports `gravity` (-y, y points up), `restitution`, ground collision, wall boundaries.
     - Supports forces: `spring` with damping, `drag` with power laws, mutual `gravitation` with softening, `custom` & `uniform` force expressions.
     - Rigid distance constraints (`links: rod`) via iterative relaxation (works for pendulums, double pendulums, linkages).
     - Fading motion trails, dynamic vectors with arrowheads, and live rolling series charts (12-second time window).
     - Instability detection (detects NaN/Infinity and alerts student without crashing).
   - **Graph engine**:
     - 400-point smooth curve sampling across `x.min..x.max`.
     - Time animation when `animate: true`.
     - Automatic or explicit Y-range fitting, axes with grid ticks, curve legends.
   - **UI Controls**:
     - Interactive sliders for all `spec.params` (updating parameters resets particles smoothly).
     - Play / Pause / Reset buttons.
     - Readout telemetry cards throttled to ~10 Hz.

2. **Wiring & Integration**:
   - **`src/components/TopicViewer.jsx`**:
     - Added `import SpecSim from '../simulations/SpecSim'`.
     - `SimulationTab` automatically renders `<SpecSim spec={topic.simulation} />` whenever `topic.simulation` is defined.
     - `hasSim = Boolean(topic.simulation || BUILTIN[topic.simulationType])`. The tab lights up automatically for every topic with a simulation!
   - **`server.py`**:
     - `AUTHOR_SIMS` defaulted to `True` (`os.environ.get("SCIEDU_AUTHOR_SIMS", "1") != "0"`).
     - `agy_create_simulation_tool` re-added to `agy_agent_tools`.
     - `AGY_SYSTEM_PROMPT` restored with `create_simulation` guidance.
   - **Topics with Active Simulations**:
     - `ball-hitting-rod.json` (rod collision impulse simulation)
     - `lagrangian-mechanics.json` (chaotic double pendulum simulation)
     - `chemical-reaction-kinetics.json` (multi-particle reaction kinetics)
     - `course-9b63eb1830-01` through `05` (projectile motion, reference frames, relative motion, uniform circular motion, nonuniform circular motion).

3. **Verification**:
   - `npm run build`: built in 194ms with 0 errors.
   - `python -m unittest discover -s tests`: all 24 tests passed.

---

## 📋 Comprehensive Audit Checklist Status

| Item | Finding / Requirement | Status | Verification |
|---|---|---|---|
| **1** | Bind `server.py` to `127.0.0.1`, restrict CORS to `localhost:5173`, add host verification | ✅ Fixed | Verified in `server.py` |
| **2** | Sanitize topic IDs with `^[a-z0-9-]+$` in `POST /api/topics` and AGY tools | ✅ Fixed | Verified with `require_topic_id` |
| **3** | Remove blanket `--dangerously-skip-permissions` from CLI runner | ✅ Fixed | Guarded by `AGY_SKIP_PERMISSIONS=1` |
| **4** | Replace all legacy `localhost:8000` calls with `/api` | ✅ Fixed | `grep -rn "8000" src/` returns 0 hits |
| **5** | Accept both `correct` and `correctAnswer` in QuizEngine (`correctAnswer ?? correct`) | ✅ Fixed | Tested in `QuizEngine.jsx` |
| **6** | Fix cycloid trail sign in `RollingWithoutSlippingSim` (`x - R*sinθ`) | ✅ Fixed | Verified alignment with marker dot |
| **7** | Add `effectiveMuK` / friction deps to `BilliardSim` `useEffect` | ✅ Fixed | Tested dynamic felt friction toggle |
| **8** | Non-blocking execution in `server.py` (`asyncio.to_thread` for sandbox and Gemini) | ✅ Fixed | Event loop remains responsive |
| **9** | Build SimSpec Player (`SpecSim.jsx`) for particles and graphs | ✅ Fixed | Built, wired, and verified |

---

## 🤝 Coordination Notes
- Claude Code can now freely author, inspect, or generate SimSpec v1 simulations for any class or topic.
- Both agents should keep this document updated as new optimizations or features are completed.
