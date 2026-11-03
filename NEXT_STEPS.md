# Next steps (for Claude, after agy runs)

State at this commit:
- Workspaces: courses have `workspace` (math | code | lab). Math classes open in Math (Class tab), lab classes
  in Lab, code classes in a lesson page under IDE until agy's Part B lands.
- Math kit: `kind: "math"` with 9 widgets (`simspec.validate_math`, `src/simulations/MathSim.jsx`), a Sim kit
  tab in Math, and math classes now ask for math widgets when their simulation is generated.
- Not yet verified in the browser: Math Class tab, the Sim kit widgets, Lab course classes in the sidebar.

To do:
1. Browser-check (scratchpad `sims_check.mjs`-style script, as profile Oleksii u-b6496b4c92):
   - the limits course opens in Math > Class tab with Previous/Next; Lab no longer opens it;
   - every Sim kit widget renders, sliders and Animate work, no console errors, light and dark;
   - Lab sidebar shows the physics course classes again.
2. Regenerate math simulations for the limits course (4 Gemini calls):
   `POST /api/simulations/generate {"topicId": "<class topic id>"}` for each `course-cea58df574-*` topic.
3. Add tests: `validate_math` for each widget; `guess_workspace` (Calculus -> math, Python -> code,
   Physics -> lab); `/api/topics` adds `source.workspace`.
4. Review agy's work (AGY_TASK_workspaces.md): run tests and the build, read the diff, then integrate:
   - chemistry: pass `CHEM_GUIDE` into `author_simulation` for lab classes about chemistry (add a `chem`
     flag like `math`), and add a "Chemistry kit" tab to Lab (gallery like Math's KitTab);
   - code classes: check the IDE class view end to end (a code exercise passes, quiz answers reach
     `/api/quiz/submit`, XP appears).
5. Update AGENTS.md (workspaces, `kind: "math"` and `"chem"`), then commit.
