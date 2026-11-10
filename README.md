# &.edu

Turn your course materials into a course that adapts to you. Upload notes, slides or a problem set;
&.edu places you with a short diagnostic, writes an ordered sequence of classes (lesson, quiz,
practice puzzles, simulation, `.md` notes), and rewrites upcoming classes when a quiz shows you are
struggling or bored. Started at &hacks (best Gemini API usage); continued from the original &EDU.

## Run it on your machine
```bash
# once: put your Gemini key in .env
echo 'api_KEY=your-key' > .env

scripts/start.sh            # backend on 127.0.0.1:8090, app on http://localhost:5173
```
Sign in with a name, choose **New course**, add files and a goal. After changing backend code,
restart the backend: a server started earlier keeps running the old code.

Optional `.env` settings:

| Variable | Effect |
| --- | --- |
| `SCIEDU_PLANNER_MODELS` | Models for the diagnostic, the syllabus and answer checking (bigger), comma-separated |
| `SCIEDU_LESSON_MODELS` | Models for lessons, quizzes and practice (lighter) |
| `SCIEDU_GROUNDED_CHECKS=0` | Turn off Google Search grounding when answer keys are checked |
| `AGY_CLI=1` | Route the in-app assistant through the Antigravity CLI (see `AGENTS.md`) |

## Host it for a class or a university
Accounts are required whenever the server is reachable from other machines; it refuses to start otherwise.
```bash
cp .env.example .env                        # fill in api_KEY; SCIEDU_DOMAIN for HTTPS
cp Caddyfile.example Caddyfile
docker compose --profile tls up -d --build  # app + Caddy (automatic HTTPS on 80/443)
```
Put the domain in `SCIEDU_ALLOWED_HOSTS` in docker-compose.yml. Without `--profile tls` the app listens on
127.0.0.1:8090 only, so it is reachable from the server itself and nothing else.
Without Docker: `npm run build`, then `SCIEDU_AUTH=1 SCIEDU_HOST=0.0.0.0 SCIEDU_ALLOWED_HOSTS=lab.example.edu python server.py`.
The backend serves the built app and the API on one port (8090). Data lives in `content/`
(SQLite database, lessons, notes), or wherever `SCIEDU_CONTENT_DIR` points.
The Dockerfile has not been built on this project's dev machine (Docker isn't installed there); the
non-Docker path above was tested.

## Tests
```bash
python -m unittest discover -s tests -v    # the full suite (292 tests on 2026-11-07), temporary data folder, no Gemini calls
```

## Where things are
| Path | What |
| --- | --- |
| `server.py` | FastAPI backend: courses, generation jobs, adaptation, answer checking, AGY tools |
| `db.py` | SQLite: accounts, courses, classes, lessons, quiz attempts |
| `simspec.py` | Validator for generated simulations (SimSpec v1) |
| `src/` | React app; `src/styles/lab.css` is the design system (light, dark, system) |
| `AGENTS.md` | Contract for agy and other coding agents: formats, endpoints, rules |
| `tests/` | Regression tests |

`PROJECT_GUIDE.md` describes the earlier SciEdu Studio version and is kept for history.

## License

Copyright (C) 2026 Oleksii Besporochnyi. Licensed under the GNU Affero General Public License v3.0 (`LICENSE`):
you may use, change and share it, and anyone who runs a changed version as a network service must offer its source to its users.
