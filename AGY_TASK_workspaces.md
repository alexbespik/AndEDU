# Task for agy: workspace toolkits (Chemistry kit for Lab, code classes inside the IDE)

Context: every course now has a workspace (`math` | `code` | `lab`). The server stores it on the course
(`courses.workspace`, set by the planner, with a keyword fallback in `server.py: guess_workspace`). Each
class topic carries it in `topic.source.workspace`. `src/App.jsx` routes classes by it:
- `math` classes open in the Math workspace (`src/components/MathLab.jsx`, Class tab). Done.
- `lab` classes open in Lab with the physics/chemistry sidebar. Done.
- `code` classes currently open as a plain lesson page under the IDE tab (`mode === 'class'`). **Part B.**

Simulations: SimSpec kinds `particles`, `graph`, `math` exist (`simspec.py`, `src/simulations/`).
Kind `chem` is wired but empty. **Part A.**

## Rules
- Only edit the files listed for each part. Do NOT edit `server.py`, `simspec.py`, `MathLab.jsx`,
  `MathSim.jsx`, `SpecSim.jsx`, `lab.css` (except where a part says so), or `db.py`.
- No `eval`/`new Function`: compile expressions with `src/lib/expr.js` (`tryCompile`).
- Colors via `canvasPalette()` from `src/theme.js` (works in light and dark).
- Run `python -m unittest discover -s tests` and `npx vite build` before you finish. Both must pass.
- Do not spend Gemini quota; everything here is offline code.

## Part A: Chemistry kit (SimSpec `kind: "chem"`)
Files: `chemspec.py` (new), `src/simulations/ChemSim.jsx` (replace the placeholder), `tests/test_chem.py` (new).

1. `chemspec.py` must export `validate_chem(spec) -> (clean_spec, errors)` and `CHEM_GUIDE` (a string in the
   style of `simspec.MATH_GUIDE`). `simspec.validate_spec` already imports it for `kind == "chem"`.
   Reuse `simspec._check_expr`, `simspec._clean_params`, `simspec._num`. Keep `"version": 1, "kind": "chem",
   "widget", "title", "description", "params"` in the cleaned spec, and add default sliders the way
   `simspec.validate_math` does.
2. Widgets (`spec.widget`), each one canvas plus readouts plus sliders, with an "Animate" button where it makes sense:
   - `kinetics`: A → B (order 0/1/2) or A ⇌ B; sliders k (and k_rev), [A]0. Concentration vs time curves and
     half-life marker. Readout: rate, t½, [A](t).
   - `equilibrium`: aA + bB ⇌ cC + dD with K; sliders for initial amounts; solve for the equilibrium extent
     (bisection) and show Q vs K plus a bar chart. Show which way the reaction shifts (Le Chatelier).
   - `titration`: strong/weak acid with strong base; sliders Ka (as pKa), concentrations, volume added.
     pH curve with equivalence point and half-equivalence (pH = pKa). Use a correct charge-balance solve.
   - `gas_law`: piston box with moving particles (simple elastic 2D); sliders n, T, V; readout P = nRT/V and a
     measured pressure from wall collisions.
   - `energy_diagram`: reaction coordinate curve with Ea, ΔH, an optional catalyst curve; slider T and a
     Boltzmann fraction readout exp(−Ea/RT).
   - `decay`: radioactive decay with N particles flipping randomly, against the N0·e^(−λt) curve.
3. Add `CHEM_GUIDE` text describing each widget's fields (like `MATH_GUIDE`).
4. `tests/test_chem.py`: every widget validates with a minimal spec; unknown names are rejected; the titration
   pH at equivalence for a strong acid is 7.00 ± 0.05 (test your pH solver as a pure Python function).
5. Done when the six widgets render in both themes without console errors.

Integration (Claude does this later, not you): use `CHEM_GUIDE` in `author_simulation` for chemistry classes,
and add a Chemistry kit tab to Lab.

## Part B: code classes inside the IDE
Files: `src/components/EduStudioIDE.jsx` and one line in `src/App.jsx` (described below).

1. Add a prop `classTopic` (a topic JSON from a `code` course: `markdownContent`, `quiz`, `practice`, where
   practice items of `type: "code"` have `starter`, `tests`, `solution`).
2. When `classTopic` is set, build an IDE curriculum from it instead of the default one:
   - one chapter titled with the class title; its README/notes tab shows `markdownContent` (rendered as now);
   - each `practice` item of type `code` becomes an editor problem: starter code in the editor; "Run" runs the
     user code plus `tests` with the existing Pyodide worker (`src/lib/pyodide.js`, `runPython`); solved when
     all asserts pass;
   - each `quiz` item becomes a multiple-choice problem using the IDE's existing quiz problem type;
   - on first solve call the existing `reportXp('ide_solved', ...)` (already imported) and also
     `api('/api/quiz/submit', ...)` for quiz items, the same body `QuizEngine.jsx` sends, so course scores and
     adaptation keep working.
   - Keep the Socratic mentor per problem as it works now.
3. Show a small header strip in the IDE with "Class N of M · course title" and Previous/Next class buttons
   (props `prevClass`, `nextClass`, `onOpenClass`, `onHome`, the same as `TopicViewer` receives).
4. In `src/App.jsx`, the block `{mode === 'class' && (codeClass ? (<TopicViewer ... />) : ...)}`: replace the
   TopicViewer with `<EduStudioIDE initialMode="code" classTopic={codeClass} {...classNav(codeClass)} ... />`
   inside the existing `Suspense`. Change nothing else in App.jsx.
5. Done when a code-course class opens in the IDE with its exercises, tests run in the browser, and
   `npx vite build` passes.

## Part C: author math simulations through the MCP tools (after A and B)
Register `mcp_server.py` as an MCP server (config in AGENTS.md, "MCP tools") and use the tools, not file edits.
1. `list_topics`, then for every topic with `workspace: "math"` whose simulation is missing or not `math/...`:
   read it with `get_topic`, design the widget that shows its key idea (`simulation_guide` lists 9 widgets),
   `validate_simulation`, then `attach_simulation`. For epsilon-delta proofs always include the `delta_rule`
   the lesson's proof uses, and set `view` so the interesting region fills the plot.
2. Add 2 `numeric` practice items per math class with `add_practice_items` that use the widget's numbers
   (e.g. "for eps = 0.1, what is the largest delta?"), with worked explanations.
3. Do not call `generate_simulation` or `regenerate_class` (they spend Gemini quota); write specs yourself.

## Part D: content for the new sections through MCP tools (after C)
1. History and Languages: for every topic in those workspaces, make sure it has 8+ flashcards (`add_flashcards`,
   with `lang` on target-language fronts), a timeline for history (`add_timeline_events`), one `add_match_pairs`
   challenge, and at least 5 quiz questions so its Speed round is worth playing (`add_quiz_questions`).
2. Course advisor: if the student gives you catalog pages or PDFs, import them with `catalog_import` (rows you
   extract yourself, faithfully; never invent courses). Never fill the catalog from memory.

When finished, append a short "What I changed" section to this file and leave the changes uncommitted.
