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


def _readiness_query(a):
    """?crn=&term= from the non-empty arguments only ('' when neither is given)."""
    parts = [f"{k}={q(str(a[k]).strip())}" for k in ("crn", "term") if str(a.get(k) or "").strip()]
    return "?" + "&".join(parts) if parts else ""


READINESS_STATUS = ("status is met | missing | check | none | unknown; check = only a test score, equivalency or admission "
                    "(score_options per missing group, required_alts) would satisfy it: not verified, the record holds no scores. "
                    "concurrent lists codes counted because they are in that term's primary cart.")


TOOLS = [
    ("simulation_guide", "The full SimSpec format: kinds particles (physics), graph, math (9 widgets), "
     "geometry / fbd (interactive apparatus, statics, vectors, free-body diagrams), and chem when installed. Read this before writing a spec.",
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
       kind=STR("auto (by workspace) | math | physics | chem", optional=True, enum=["auto", "math", "physics", "chem"])),
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
    # ---- activities: flashcards, speed rounds (Kahoot-style), matching, timelines
    ("add_flashcards", "Append flashcards to a lesson (spaced recall; read aloud when lang is set): {front, back, hint?, lang? e.g. 'es'}.",
     S(topic_id=STR("topic id"), cards=ARR("cards")), lambda a: call("POST", f"/api/topics/{q(a['topic_id'])}/flashcards", {"items": a["cards"]})),
    ("add_timeline_events", "Append history timeline events: {year (number, negative = BCE), title, date?, detail?}. Powers the Timeline tab and the ordering challenge.",
     S(topic_id=STR("topic id"), events=ARR("events")), lambda a: call("POST", f"/api/topics/{q(a['topic_id'])}/timeline", {"items": a["events"]})),
    ("add_match_pairs", "Add a matching challenge (3-8 pairs: term-definition, word-translation, person-event, sound-IPA).",
     S(topic_id=STR("topic id"), prompt=STR("instruction shown to the student"),
       pairs={"type": "array", "items": {"type": "array", "items": {"type": "string"}}, "description": "[[left, right], ...]"},
       explanation=STR("shown after solving", optional=True)),
     lambda a: call("POST", f"/api/topics/{q(a['topic_id'])}/practice", {"items": [{"type": "match_pairs", "prompt": a["prompt"], "pairs": a["pairs"], "explanation": a.get("explanation", "")}]})),
    ("add_drawing_assignment", "Add a drawing assignment (the student draws on an in-app whiteboard; the AI checks the drawing against "
     "your criteria): e.g. a free-body diagram, circuit, graph sketch, cell, map or concept map.",
     S(topic_id=STR("topic id"), prompt=STR("what to draw"),
       criteria={"type": "array", "items": {"type": "string"}, "description": "3-5 checkable things the drawing must show"},
       reference=STR("what a correct drawing contains (hidden from the student)", optional=True),
       background=STR("grid | axes | blank", optional=True, enum=["grid", "axes", "blank"])),
     lambda a: call("POST", f"/api/topics/{q(a['topic_id'])}/practice", {"items": [{"type": "draw", "prompt": a["prompt"], "criteria": a["criteria"],
                                                                                   "reference": a.get("reference", ""), "background": a.get("background", "grid")}]})),
    ("start_speed_round", "Open a lesson's Kahoot-style speed round on the student's screen (timed questions, points for speed, streaks). "
     "Add questions first with add_quiz_questions; a round needs at least 3.",
     S(topic_id=STR("topic id")), lambda a: call("POST", "/api/agy/events", {"type": "SWITCH_TOPIC", "payload": {"topicId": a["topic_id"], "tab": "speed"}})),
    ("start_flashcards", "Open a lesson's flashcards on the student's screen.",
     S(topic_id=STR("topic id")), lambda a: call("POST", "/api/agy/events", {"type": "SWITCH_TOPIC", "payload": {"topicId": a["topic_id"], "tab": "cards"}})),
    # ---- course advisor
    ("catalog_search", "Search the imported course catalog (W&M by default) by words and/or department, e.g. dept='CSCI'. "
     "Returns up to `limit` courses (default 100, max 500) and `total`, the number of matches.",
     S(query=STR("words", optional=True), dept=STR("department code", optional=True), limit={"type": "integer", "description": "max courses (default 100, max 500)", "optional": True}),
     lambda a: call("GET", f"/api/advisor/catalog?q={q(a.get('query', ''))}&dept={q(a.get('dept', ''))}&limit={int(a.get('limit') or 100)}")),
    ("catalog_import", "Import catalog entries: rows [{code, title, credits, description, prereqs, attributes}] or raw catalog text "
     "('DEPT 123. Title. (3 Credits)' layout). Set use_model to let the app's model read text the parser can't (uses quota).",
     S(rows=ARR("course rows", optional=True), text=STR("catalog text", optional=True), source=STR("where it came from", optional=True),
       year=STR("catalog year, e.g. 2016-2017 (shown to students as possibly outdated)", optional=True),
       use_model={"type": "boolean", "optional": True, "description": "fall back to the model"}),
     lambda a: call("POST", "/api/advisor/catalog/import", {"rows": a.get("rows"), "text": a.get("text", ""), "source": a.get("source", "mcp"), "year": a.get("year", ""), "useModel": bool(a.get("use_model"))})),
    ("student_record", "Courses a student has completed (codes, grades, terms).",
     S(user_id=STR("profile id")), lambda a: call("GET", f"/api/advisor/{q(a['user_id'])}/completed")),
    ("add_completed_courses", "Record completed courses from transcript text or rows [{code, title?, grade?, term?}].",
     S(user_id=STR("profile id"), text=STR("transcript text or list of codes", optional=True), rows=ARR("rows", optional=True)),
     lambda a: call("POST", f"/api/advisor/{q(a['user_id'])}/completed", {"text": a.get("text", ""), "rows": a.get("rows"), "source": "mcp"})),
    ("recommend_courses", "Courses the student can take next (prerequisites met), ranked by how they build on their record and interests.",
     S(user_id=STR("profile id"), interests=STR("e.g. 'machine learning, statistics'", optional=True)),
     lambda a: call("GET", f"/api/advisor/{q(a['user_id'])}/recommend?interests={q(a.get('interests', ''))}")),
    ("get_cart", "A student's planning cart for a term (default: the next term): primary and backup courses, chosen sections, "
     "flags (no_section, prereq_missing, prereq_check, already_done; prereq_check: only a test score, equivalency or "
     "admission would satisfy what is missing, not verified), the primary credit load and section time conflicts.",
     S(user_id=STR("profile id"), term=STR("term code, e.g. 202720", optional=True)),
     lambda a: call("GET", f"/api/advisor/{q(a['user_id'])}/cart?term={q(a.get('term', ''))}")),
    ("add_to_cart", "Add a catalog course to a student's planning cart (adding it again updates it). Give a section CRN only "
     "if it is a listed section of that course in that term (search_sections); otherwise leave it empty for the student to pick.",
     S(user_id=STR("profile id"), code=STR("course code, e.g. CSCI 241"), term=STR("term code", optional=True),
       cart_type=STR("primary (counts toward the load) or backup", optional=True, enum=["primary", "backup"]),
       section_crn=STR("CRN of a listed section", optional=True), notes=STR("short note", optional=True),
       priority=STR("must, want (default for a new course) or nice; omit to keep the current one", optional=True,
                    enum=["must", "want", "nice"])),
     lambda a: call("POST", f"/api/advisor/{q(a['user_id'])}/cart", {"code": a["code"], "term": a.get("term", ""),
                    "cart_type": a.get("cart_type") or "primary", "section_crn": a.get("section_crn", ""), "notes": a.get("notes", ""),
                    "priority": a.get("priority") or None})),
    ("remove_from_cart", "Remove a course from a student's planning cart.",
     S(user_id=STR("profile id"), code=STR("course code"), term=STR("term code", optional=True)),
     lambda a: call("DELETE", f"/api/advisor/{q(a['user_id'])}/cart/{q(a['code'])}?term={q(a.get('term', ''))}")),
    ("set_cart_priority", "Set how much the student needs a course in their cart: must, want or nice.",
     S(user_id=STR("profile id"), code=STR("course code"), priority=STR("must, want or nice", enum=["must", "want", "nice"]),
       term=STR("term code", optional=True)),
     lambda a: call("PATCH", f"/api/advisor/{q(a['user_id'])}/cart/{q(a['code'])}", {"term": a.get("term", ""), "priority": a["priority"]})),
    ("research_cart", "A registration plan for a student's cart: courses ordered by priority (must, want, nice) and then seat "
     "risk, each with a risk level (high, medium, low, unknown), a likely fill phase, evidence and advice. The risk is an "
     "ESTIMATE from past imported schedules (often unknown or low confidence; registration window dates are not loaded): "
     "present it as likely, never certain.",
     S(user_id=STR("profile id"), term=STR("term code, e.g. 202720", optional=True)),
     lambda a: call("GET", f"/api/advisor/{q(a['user_id'])}/cart/research?term={q(a.get('term', ''))}")),
    ("check_readiness", "Are the listed prerequisites of a course met by the student's record? Returns what is missing. "
     "Per-section rule when crn is given (sections can list different prerequisites); basis says which rule applied. "
     + READINESS_STATUS,
     S(user_id=STR("profile id"), code=STR("course code, e.g. CSCI 241"),
       crn=STR("CRN of a section of that course", optional=True), term=STR("term code, e.g. 202720 (default: next term)", optional=True)),
     lambda a: call("GET", f"/api/advisor/{q(a['user_id'])}/readiness/{q(a['code'])}{_readiness_query(a)}")),
    ("create_readiness_course", "Build a readiness course for a target course: a diagnostic on its prerequisite knowledge, then bridge classes. Uses Gemini quota.",
     S(user_id=STR("profile id"), code=STR("course code")),
     lambda a: call("POST", f"/api/advisor/{q(a['user_id'])}/readiness-course", {"code": a["code"]})),
    ("search_sections", "Search course sections (with CRNs) by course code, department or instructor. Defaults to the "
     "NEXT term only (the response names it). Pass term='all' or a term code (e.g. 202710) for other terms: those rows "
     "are history, not next-term offerings, and their CRNs are not registrable for the next term.",
     S(query=STR("course code e.g. CSCI 141, department code e.g. CSCI, or instructor name"),
       term=STR("'next' (default), 'all', or a term code like 202720", optional=True),
       limit={"type": "integer", "description": "max results (default 20)", "optional": True}),
     lambda a: call("GET", f"/api/advisor/sections?q={q(a['query'])}&term={q(a.get('term') or 'next')}"
                           f"&limit={int(a.get('limit') or 20)}")),
    ("get_prerequisite_tree", "Get the full prerequisite chain for a course (all direct and indirect prerequisites).",
     S(code=STR("course code e.g. CSCI 303")),
     lambda a: call("GET", f"/api/advisor/catalog/{q(a['code'])}")),
    ("check_major_requirements", "Check which W&M major requirements a student has met and what's still needed, based on their completed courses.",
     S(user_id=STR("profile id"), major=STR("major name or keyword e.g. computer science, biology, economics")),
     lambda a: call("GET", f"/api/advisor/{q(a['user_id'])}/degree-audit")),
    ("get_student_degree_audit", "Get the full degree audit for a student: COLL requirements, proficiencies, credits, gaps.",
     S(user_id=STR("profile id")),
     lambda a: call("GET", f"/api/advisor/{q(a['user_id'])}/degree-audit")),
    ("get_student_readiness", "Check whether a student meets the prerequisites for a given course. Per-section rule "
     "when crn is given; basis says which rule applied. " + READINESS_STATUS,
     S(user_id=STR("profile id"), code=STR("course code e.g. CSCI 303"),
       crn=STR("CRN of a section of that course", optional=True), term=STR("term code, e.g. 202720 (default: next term)", optional=True)),
     lambda a: call("GET", f"/api/advisor/{q(a['user_id'])}/readiness/{q(a['code'])}{_readiness_query(a)}")),
    ("list_completed_courses", "List all courses a student has recorded as completed, with grades.",
     S(user_id=STR("profile id")),
     lambda a: call("GET", f"/api/advisor/{q(a['user_id'])}/completed")),
    ("add_completed_course", "Record that a student has completed a course (adds to their transcript for advising purposes).",
     S(user_id=STR("profile id"), code=STR("course code e.g. CSCI 141"),
       grade=STR("letter grade e.g. A, B+", optional=True)),
     lambda a: call("POST", f"/api/advisor/{q(a['user_id'])}/completed",
                    {"code": a["code"], "grade": a.get("grade")})),
    ("ask_advisor", "Ask the AI academic advisor a question on behalf of a student. Returns a reply with course suggestions.",
     S(user_id=STR("profile id"), message=STR("the student's question"),
       history={
           "type": "array",
           "items": {"type": "object"},
           "description": "[{role: 'user'|'advisor', content: str}] prior turns",
           "optional": True
       }),
     lambda a: call("POST", f"/api/advisor/{q(a['user_id'])}/ask",
                    {"message": a["message"], "history": a.get("history", [])})),
]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mcp_tools_history  # noqa: E402  (subject tool modules get the helpers above; see ARCHITECTURE.md §3.1.1)
import mcp_tools_language  # noqa: E402
import mcp_tools_language_extra  # noqa: E402
import mcp_tools_general  # noqa: E402
import mcp_tools_studio  # noqa: E402

for _mod in (mcp_tools_language, mcp_tools_history, mcp_tools_language_extra, mcp_tools_general, mcp_tools_studio):
    TOOLS += _mod.tools(call, q, S, STR, OBJ, ARR)
BY_NAME = {name: (desc, schema, fn) for name, desc, schema, fn in TOOLS}


def handle(msg):
    method, mid = msg.get("method"), msg.get("id")
    if method == "initialize":
        return {"protocolVersion": msg.get("params", {}).get("protocolVersion", PROTOCOL),
                "capabilities": {"tools": {}}, "serverInfo": {"name": "andedu", "version": "1.0"},
                "instructions": "Tools for &.edu: author simulations (call simulation_guide first), extend lessons, "
                                "build gamified language units and exercises, adjust course classes and show results on the student's screen."}
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
