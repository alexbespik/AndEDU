# Contributing to &.edu

Thanks for helping. Two things before you open a pull request.

## 1. Sign the CLA

Every contributor must agree to the [Contributor License Agreement](CLA.md). You keep the copyright in your
work; the CLA lets the maintainer license the project, including your contribution, under the AGPL-3.0 and
under other terms (for example a commercial license). The project itself stays open source under the AGPL.

To agree, check the CLA box in the pull request template. You only need to do it once; it covers every later
contribution. Pull requests without it are not merged.

## 2. Run the checks

```bash
.venv/bin/python -m unittest discover -s tests   # backend tests
ruff check .                                     # Python lint
npm run lint && npm run build                    # frontend lint and build
```

CI runs the same checks on every pull request. `AGENTS.md` explains the lesson, simulation and practice
formats; `README.md` explains how to run the app.

Never commit `.env`, API keys, `content/edu_studio.db`, or any student's data.
