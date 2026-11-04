# &.edu LAB — one container: the FastAPI backend also serves the built frontend.
# Build:  docker build -t andedu-lab .
# Run:    see docker-compose.yml (accounts on, data in ./content)

# ---- 1. build the React frontend ----
FROM node:22-alpine AS web
WORKDIR /web
COPY package.json ./
RUN npm install --no-audit --no-fund
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
COPY server.py db.py simspec.py chemspec.py engage.py advisor.py backend_puzzles.py ./
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
CMD ["/app/entrypoint.sh"]
