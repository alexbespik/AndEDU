# Next steps (for Claude, after agy runs)

State at this commit:
- Workspaces: courses have `workspace` (math | code | lab). Math classes open in Math (Class tab), lab classes
  in Lab, code classes in a lesson page under IDE until agy's Part B lands.
- Math kit: `kind: "math"` with 9 widgets (`simspec.validate_math`, `src/simulations/MathSim.jsx`), a Sim kit
  tab in Math, and math classes now ask for math widgets when their simulation is generated.
- Verified in the browser: limits course opens in Math > Class tab; all 10 Sim kit widgets render with correct
  numbers; the 4 limits classes now have epsilon-delta simulations (regenerated).

To do:
1. Done: browser check, regenerated limits simulations, tests (37 pass).
2. Still open: check the Animate button on each widget, and that Lab's sidebar lists the physics course classes.
4. Review agy's work (AGY_TASK_workspaces.md): run tests and the build, read the diff, then integrate:
   - chemistry: pass `CHEM_GUIDE` into `author_simulation` for lab classes about chemistry (add a `chem`
     flag like `math`), and add a "Chemistry kit" tab to Lab (gallery like Math's KitTab);
   - code classes: check the IDE class view end to end (a code exercise passes, quiz answers reach
     `/api/quiz/submit`, XP appears).
5. Update AGENTS.md (workspaces, `kind: "math"` and `"chem"`), then commit.
