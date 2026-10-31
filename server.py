#!/usr/bin/env python3
"""
SciEdu Studio Backend Server
Provides dynamic REST endpoints for AI coding agents to ingest topics,
update derivations, and record assessment results.
"""

import os
import json
import glob
from pathlib import Path
from typing import List, Dict, Any, Optional

TOPICS_DIR = Path(__file__).parent / "content" / "topics"
RESULTS_FILE = Path(__file__).parent / "content" / "quiz_results.json"

TOPICS_DIR.mkdir(parents=True, exist_ok=True)

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel

    app = FastAPI(title="SciEdu Studio Dynamic Agent API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class TopicModel(BaseModel):
        id: str
        title: str
        category: str
        difficulty: Optional[str] = "Undergraduate"
        summary: Optional[str] = ""
        simulationType: Optional[str] = None
        cheatSheet: Optional[List[Dict[str, str]]] = []
        mermaid: Optional[str] = None
        markdownContent: str
        quiz: Optional[List[Dict[str, Any]]] = []

    class QuizSubmission(BaseModel):
        topicId: str
        questionId: Any
        selected: int
        isCorrect: bool

    @app.get("/api/topics")
    def get_topics():
        topics = []
        for file_path in TOPICS_DIR.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    topics.append(json.load(f))
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
        return topics

    @app.get("/api/topics/{topic_id}")
    def get_topic(topic_id: str):
        file_path = TOPICS_DIR / f"{topic_id}.json"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Topic not found")
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @app.post("/api/topics")
    def create_or_update_topic(topic: TopicModel):
        file_path = TOPICS_DIR / f"{topic.id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(topic.dict(), f, indent=2, ensure_ascii=False)
        return {"status": "success", "id": topic.id, "path": str(file_path)}

    @app.post("/api/quiz/submit")
    def submit_quiz_answer(sub: QuizSubmission):
        results = []
        if RESULTS_FILE.exists():
            try:
                with open(RESULTS_FILE, "r", encoding="utf-8") as f:
                    results = json.load(f)
            except Exception:
                results = []
        results.append(sub.dict())
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        return {"status": "recorded"}

    @app.get("/api/status")
    def get_status():
        return {
            "status": "online",
            "agent_sync": True,
            "topic_count": len(list(TOPICS_DIR.glob("*.json")))
        }

    if __name__ == "__main__":
        import uvicorn
        print("Starting SciEdu Studio FastAPI server on port 8090...")
        uvicorn.run(app, host="0.0.0.0", port=8090)

except ImportError:
    # Standard library fallback if FastAPI is not installed in the active environment
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import urllib.parse

    class SimpleAPIHandler(BaseHTTPRequestHandler):
        def _set_headers(self, status=200):
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()

        def do_OPTIONS(self):
            self._set_headers(204)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/topics":
                topics = []
                for file_path in TOPICS_DIR.glob("*.json"):
                    with open(file_path, "r", encoding="utf-8") as f:
                        topics.append(json.load(f))
                self._set_headers(200)
                self.wfile.write(json.dumps(topics).encode('utf-8'))
            elif parsed.path == "/api/status":
                self._set_headers(200)
                self.wfile.write(json.dumps({
                    "status": "online",
                    "agent_sync": True,
                    "topic_count": len(list(TOPICS_DIR.glob("*.json")))
                }).encode('utf-8'))
            elif parsed.path.startswith("/api/topics/"):
                topic_id = parsed.path.split("/")[-1]
                file_path = TOPICS_DIR / f"{topic_id}.json"
                if file_path.exists():
                    self._set_headers(200)
                    with open(file_path, "rb") as f:
                        self.wfile.write(f.read())
                else:
                    self._set_headers(404)
                    self.wfile.write(b'{"error": "Not found"}')
            else:
                self._set_headers(404)
                self.wfile.write(b'{"error": "Endpoint not found"}')

        def do_POST(self):
            length = int(self.headers.get('content-length', 0))
            body = self.rfile.read(length)
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/api/topics":
                data = json.loads(body.decode('utf-8'))
                topic_id = data.get("id")
                file_path = TOPICS_DIR / f"{topic_id}.json"
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                self._set_headers(200)
                self.wfile.write(json.dumps({"status": "success", "id": topic_id}).encode('utf-8'))
            elif parsed.path == "/api/quiz/submit":
                data = json.loads(body.decode('utf-8'))
                results = []
                if RESULTS_FILE.exists():
                    try:
                        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
                            results = json.load(f)
                    except Exception:
                        results = []
                results.append(data)
                with open(RESULTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=2)
                self._set_headers(200)
                self.wfile.write(b'{"status": "recorded"}')

    print("Starting SciEdu Studio HTTP server on port 8090...")
    server = HTTPServer(("0.0.0.0", 8090), SimpleAPIHandler)
    server.serve_forever()
