#!/usr/bin/env python3
"""
SciEdu Studio Backend Server with AGY Live Bridge
Provides dynamic REST & Event streaming endpoints for Antigravity (AGY)
to control the UI, inject derivations, adjust simulations, and record quiz progress.
"""

import os
import sys
import json
import glob
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

TOPICS_DIR = Path(__file__).parent / "content" / "topics"
RESULTS_FILE = Path(__file__).parent / "content" / "quiz_results.json"
EVENTS_FILE = Path(__file__).parent / "content" / "agy_events.json"
MESSAGES_FILE = Path(__file__).parent / "content" / "agy_messages.json"
ENV_FILE = Path(__file__).parent / ".env"

TOPICS_DIR.mkdir(parents=True, exist_ok=True)
Path(__file__).parent.joinpath("content").mkdir(parents=True, exist_ok=True)

# Load .env if present
if ENV_FILE.exists():
    with open(ENV_FILE, "r") as ef:
        for line in ef:
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

api_key = os.environ.get("api_KEY", os.environ.get("GEMINI_API_KEY"))

# In-memory event queue for live UI updates
ui_events_queue: List[Dict[str, Any]] = []

def load_json_file(path: Path, default: Any):
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json_file(path: Path, data: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel

    app = FastAPI(title="SciEdu Studio AGY Bridge API")
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

    class AgyEventModel(BaseModel):
        type: str  # SWITCH_TAB, SET_SIM_PRESET, ADD_QUIZ_QUESTION, SHOW_TOAST, HIGHLIGHT_FORMULA
        payload: Dict[str, Any]

    class AgyPromptModel(BaseModel):
        prompt: str
        topicId: Optional[str] = "rolling-without-slipping"

    @app.get("/api/topics")
    def get_topics():
        topics = []
        for file_path in sorted(TOPICS_DIR.glob("*.json")):
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
        save_json_file(file_path, topic.dict())
        # Emit a live event to UI
        ui_events_queue.append({
            "id": f"evt-{int(time.time()*1000)}",
            "type": "TOPIC_UPDATED",
            "payload": {"topicId": topic.id, "title": topic.title}
        })
        return {"status": "success", "id": topic.id, "path": str(file_path)}

    @app.post("/api/quiz/submit")
    def submit_quiz_answer(sub: QuizSubmission):
        results = load_json_file(RESULTS_FILE, [])
        record = sub.dict()
        record["timestamp"] = time.time()
        results.append(record)
        save_json_file(RESULTS_FILE, results)

        # Notify AGY Event Stream
        status_msg = "Correct answer recorded!" if sub.isCorrect else "Answer incorrect — review recommended."
        ui_events_queue.append({
            "id": f"evt-{int(time.time()*1000)}",
            "type": "QUIZ_SUBMITTED",
            "payload": {
                "topicId": sub.topicId,
                "isCorrect": sub.isCorrect,
                "statusMessage": status_msg
            }
        })
        return {"status": "recorded", "isCorrect": sub.isCorrect}

    @app.get("/api/agy/events")
    def get_agy_events(since: Optional[float] = 0):
        # Return recent queued events
        events = list(ui_events_queue)
        return {"events": events, "timestamp": time.time()}

    @app.post("/api/agy/events")
    def push_agy_event(event: AgyEventModel):
        event_dict = {
            "id": f"evt-{int(time.time()*1000)}",
            "type": event.type,
            "payload": event.payload,
            "timestamp": time.time()
        }
        ui_events_queue.append(event_dict)
        if len(ui_events_queue) > 50:
            ui_events_queue.pop(0)
        return {"status": "event_pushed", "event": event_dict}

    @app.get("/api/agy/messages")
    def get_messages():
        return load_json_file(MESSAGES_FILE, [])

    @app.post("/api/agy/prompt")
    def post_user_prompt(data: AgyPromptModel):
        messages = load_json_file(MESSAGES_FILE, [])
        user_msg = {
            "id": f"msg-{int(time.time()*1000)}",
            "sender": "user",
            "content": data.prompt,
            "timestamp": time.time()
        }
        messages.append(user_msg)

        # Generate responsive answer via Gemini Flash Lite if API key exists
        reply_content = ""
        if api_key:
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model="gemini-2.5-flash-lite",
                    contents=(
                        f"You are the AGY physics tutor inside SciEdu Studio. "
                        f"Current topic: {data.topicId}. "
                        f"Explain concisely using clear scientific notation and KaTeX math ($...$): {data.prompt}"
                    )
                )
                reply_content = response.text
            except Exception as e:
                reply_content = f"AGY Note received: '{data.prompt}'. Your request has been queued for real-time analysis."
        else:
            reply_content = f"AGY bridge received request: '{data.prompt}'. Dynamic response ready."

        agent_msg = {
            "id": f"msg-{int(time.time()*1000)+1}",
            "sender": "agy",
            "content": reply_content,
            "timestamp": time.time()
        }
        messages.append(agent_msg)
        save_json_file(MESSAGES_FILE, messages)

        # Emit message event
        ui_events_queue.append({
            "id": f"evt-{int(time.time()*1000)}",
            "type": "NEW_MESSAGE",
            "payload": {"message": agent_msg}
        })

        return {"status": "ok", "reply": reply_content}

    @app.get("/api/status")
    def get_status():
        return {
            "status": "online",
            "agent_sync": True,
            "topic_count": len(list(TOPICS_DIR.glob("*.json"))),
            "pending_events": len(ui_events_queue),
            "agy_bridge": "active"
        }

    if __name__ == "__main__":
        import uvicorn
        print("Starting SciEdu Studio AGY Bridge API server on port 8090...")
        uvicorn.run(app, host="0.0.0.0", port=8090)

except ImportError:
    pass
