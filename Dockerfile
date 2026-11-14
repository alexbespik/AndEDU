# &.edu LAB — one container: the FastAPI backend also serves the built frontend.
# Build:  docker build -t andedu-lab .
# Run:    see docker-compose.yml (accounts on, data in ./content)

# ---- 1. build the React frontend ----
FROM node:22-alpine AS web
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY index.html vite.config.js ./
COPY src ./src
COPY content/topics ./content/topics
RUN npm run build

# ---- 2. Python runtime ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    SCIEDU_HOST=0.0.0.0 SCIEDU_PORT=8090 SCIEDU_AUTH=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py db.py simspec.py chemspec.py engage.py advisor.py advisor_chat.py advisor_cart.py advisor_risk.py advisor_classifier.py advisor_rules.py explain.py sprint.py userkeys.py philin.py logic_formula.py logic_forms.py logic_argmap.py logic_proof.py logic_syllogism.py logic_ast.py logic_engine.py decision_tree_engine.py wm_advising.py backend_puzzles.py language_de.py language_tts.py practice_general.py practice_history.py practice_language_extra.py practice_philosophy.py practice_literature.py practice_music.py practice_art_history.py practice_classics.py practice_rhetoric.py practice_polity.py practice_ee.py practice_ai.py practice_systems.py practice_stats.py practice_bio.py mcp_server.py mcp_tools_history.py mcp_tools_language.py mcp_tools_language_extra.py mcp_tools_general.py mcp_tools_studio.py mcp_tools_philosophy.py fbd_grader.py sandbox_preamble.py ./
COPY scripts ./scripts
COPY content/topics ./seed/topics
COPY --from=web /web/dist ./dist
# first start on an empty volume: copy the starter lessons in
RUN printf '#!/bin/sh\nmkdir -p /app/content/topics\n[ -n "$(ls -A /app/content/topics 2>/dev/null)" ] || cp /app/seed/topics/*.json /app/content/topics/\nexec python server.py\n' > /app/entrypoint.sh \
 && chmod +x /app/entrypoint.sh \
 && useradd --create-home --uid 10001 lab && mkdir -p /app/content && chown -R lab /app/content
USER lab
VOLUME ["/app/content"]
EXPOSE 8090
# /api/status needs no login; localhost is always an allowed Host, whatever SCIEDU_ALLOWED_HOSTS says
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/status' % os.environ.get('SCIEDU_PORT', '8090'), timeout=4)" || exit 1
CMD ["/app/entrypoint.sh"]
