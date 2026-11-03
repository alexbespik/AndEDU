#!/usr/bin/env python3
"""
&.edu MCP server: lets any MCP client (agy / Antigravity, Claude Code, Claude Desktop, ...) work inside the app
with real tools instead of editing files: author simulations (physics, math kit, chemistry kit), add quiz
questions and practice, adjust course classes, and put things on the student's screen.

It talks to the running backend over HTTP, so everything goes through the same validation and shows up live
in the UI. Standard library only; MCP over stdio (newline-delimited JSON-RPC 2.0).

    python3 mcp_server.py            # the client starts it; see AGENTS.md for client config
Environment: ANDEDU_API (default http://127.0.0.1:8090), ANDEDU_TOKEN (bearer token when SCIEDU_AUTH=1).
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("ANDEDU_API", "http://127.0.0.1:8090").rstrip("/")
TOKEN = os.environ.get("ANDEDU_TOKEN", "")
PROTOCOL = "2025-06-18"


def call(method, path, body=None):
    req = urllib.request.Request(API + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read()).get("detail")
        except Exception:
            detail = e.reason
        raise RuntimeError(f"HTTP {e.code}: {json.dumps(detail) if not isinstance(detail, str) else detail}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"The &.edu backend is not reachable at {API} ({e.reason}). Start it with: python3 server.py")


def q(s):
    return urllib.parse.quote(str(s), safe="")


S = lambda **props: {"type": "object", "properties": props, "required": [k for k, v in props.items() if not v.pop("optional", False)]}
STR = lambda d, **k: {"type": "string", "description": d, **k}
OBJ = lambda d, **k: {"type": "object", "description": d, **k}
ARR = lambda d, **k: {"type": "array", "items": {"type": "object"}, "description": d, **k}


def _topics(_):
    out = []
    for t in call("GET", "/api/topics"):
        src = t.get("source") or {}
        sim = t.get("simulation") or {}
        out.append({"id": t["id"], "title": t.get("title"), "category": t.get("category"),
                    "workspace": src.get("workspace", "lab"), "course": src.get("courseTitle"), "class": src.get("classSeq"),
                    "simulation": sim.get("kind") and f"{sim.get('kind')}{'/' + sim['widget'] if sim.get('widget') else ''}",
                    "quiz": len(t.get("quiz") or []), "practice": len(t.get("practice") or [])})
    return out


TOOLS = [
    ("simulation_guide", "The full SimSpec format: kinds particles (physics), graph, math (9 widgets: epsilon_delta, epsilon_n, "
     "secant_tangent, riemann, series, unit_circle, parametric, vector_field, transform2d) and chem when installed. Read this before writing a spec.",
     S(), lambda a: call("GET", "/api/simulations/guide")["guide"]),
    ("list_topics", "Every lesson with its workspace (math | code | lab), course, simulation kind and quiz/practice counts.",
     S(), _topics),
    ("get_topic", "One lesson's full JSON (markdown, formulas, quiz, practice, simulation).",
     S(topic_id=STR("topic id")), lambda a: call("GET", f"/api/topics/{q(a['topic_id'])}")),
    ("save_topic", "Create or replace a lesson (see AGENTS.md for the topic JSON). Returns warnings for anything dropped.",
     S(topic=OBJ("topic JSON with id, title, category, markdownContent, quiz, practice, optional simulation")),
     lambda a: call("POST", "/api/topics", a["topic"])),
    ("validate_simulation", "Check a SimSpec without saving it; returns every error with its location.",
     S(spec=OBJ("SimSpec JSON")), lambda a: call("POST", "/api/simulations/validate", a["spec"])),
    ("attach_simulation", "Validate a SimSpec you wrote (any kind) and attach it to a lesson's Simulation tab. Use this for precise, "
     "hand-designed simulations, e.g. a math epsilon_delta widget with the exact delta_rule a proof uses.",
     S(topic_id=STR("topic id"), spec=OBJ("SimSpec JSON")), lambda a: call("POST", f"/api/topics/{q(a['topic_id'])}/simulation", {"spec": a["spec"]})),
    ("generate_simulation", "Have the app's model design a simulation for a lesson in the background (20-40 s, uses Gemini quota).",
     S(topic_id=STR("topic id"), focus=STR("what the student should explore", optional=True),
       kind=STR("auto (by workspace) | math | physics", optional=True, enum=["auto", "math", "physics"])),
     lambda a: call("POST", "/api/simulations/generate", {"topicId": a["topic_id"], "focus": a.get("focus", ""), "kind": a.get("kind", "auto")})),
    ("add_quiz_questions", "Append multiple-choice questions to a lesson: {question, options[4], correctAnswer (0-based), hint, explanation}. LaTeX in $...$.",
     S(topic_id=STR("topic id"), questions=ARR("questions")), lambda a: call("POST", f"/api/topics/{q(a['topic_id'])}/quiz", {"items": a["questions"]})),
    ("add_practice_items", "Append practice puzzles: fill_blank, order_steps, numeric (answer, tolerance, unit), true_false, or code "
     "(starter, tests with assert lines, solution). Ungradable items are rejected.",
     S(topic_id=STR("topic id"), items=ARR("practice items")), lambda a: call("POST", f"/api/topics/{q(a['topic_id'])}/practice", {"items": a["items"]})),
    ("list_profiles", "Local student profiles (personal machine only).", S(), lambda a: call("GET", "/api/users")),
    ("list_courses", "A student's courses with workspace, mode (learn | test_prep) and progress.",
     S(user_id=STR("profile id")), lambda a: call("GET", f"/api/users/{q(a['user_id'])}/courses")),
    ("get_course", "A course with its classes, scores and diagnostic results.",
     S(course_id=STR("course id")), lambda a: call("GET", f"/api/courses/{q(a['course_id'])}")),
    ("regenerate_class", "Rewrite one class of a course with guidance (easier, more worked examples, a new angle...). Uses Gemini quota.",
     S(course_id=STR("course id"), seq={"type": "integer", "description": "class number, 1-based"}, instruction=STR("what to change")),
     lambda a: call("POST", f"/api/courses/{q(a['course_id'])}/classes/{int(a['seq'])}/regenerate", {"instruction": a["instruction"]})),
    ("show_on_graph", "Open Math > Graph on the student's screen with these functions of x; other letters become sliders.",
     S(functions={"type": "array", "items": {"type": "string"}, "description": "e.g. ['sin(k*x)', 'x^2 - c']"},
       params={"type": "object", "description": "starting slider values, e.g. {'k': 2}", "optional": True}),
     lambda a: call("POST", "/api/ui/graph", {"functions": a["functions"], "params": a.get("params") or {}})),
    ("preview_math_simulation", "Show a math-kit widget in Math > Sim kit on the student's screen without saving it.",
     S(spec=OBJ("math SimSpec (kind math is implied)")), lambda a: call("POST", "/api/ui/math-sim", {"spec": a["spec"]})),
    ("open_topic", "Navigate the student's screen to a lesson tab (theory | simulation | quiz | practice | tutor).",
     S(topic_id=STR("topic id"), tab=STR("tab", optional=True)),
     lambda a: call("POST", "/api/agy/events", {"type": "SWITCH_TOPIC", "payload": {"topicId": a["topic_id"], "tab": a.get("tab", "theory")}})),
]
BY_NAME = {name: (desc, schema, fn) for name, desc, schema, fn in TOOLS}


def handle(msg):
    method, mid = msg.get("method"), msg.get("id")
    if method == "initialize":
        return {"protocolVersion": msg.get("params", {}).get("protocolVersion", PROTOCOL),
                "capabilities": {"tools": {}}, "serverInfo": {"name": "andedu", "version": "1.0"},
                "instructions": "Tools for &.edu: author simulations (call simulation_guide first), extend lessons, "
                                "adjust course classes and show results on the student's screen."}
    if method == "tools/list":
        return {"tools": [{"name": n, "description": d, "inputSchema": s} for n, d, s, _ in TOOLS]}
    if method == "tools/call":
        p = msg.get("params", {})
        tool = BY_NAME.get(p.get("name"))
        if not tool:
            return {"content": [{"type": "text", "text": f"Unknown tool {p.get('name')}"}], "isError": True}
        try:
            result = tool[2](p.get("arguments") or {})
            text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, indent=1)[:60000]
            return {"content": [{"type": "text", "text": text}]}
        except (RuntimeError, KeyError, ValueError, TypeError) as e:
            return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}
    if method == "ping":
        return {}
    if mid is None:  # notifications (initialized, cancelled) need no answer
        return None
    raise LookupError(method)


def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            result = handle(msg)
            if result is None or msg.get("id") is None:
                continue
            out = {"jsonrpc": "2.0", "id": msg["id"], "result": result}
        except LookupError as e:
            out = {"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32601, "message": f"Method not found: {e}"}}
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
