"""Cross-subject authoring and progress tools for the &.edu MCP server. Imported by mcp_server.py, which passes in
its HTTP helpers. Every tool goes through the backend (so accounts-mode owner checks apply); none writes files or
calls a model. The parsing and building helpers are plain functions so tests can call them directly."""
import json
import random
import re

KINDS = ("practice", "flashcards", "timeline")
WORKSPACES = ("home", "physics", "lab", "class", "code", "math", "history", "language", "advisor", "review")
_SEP = re.compile(r"\s+[-–—]\s+|\s*:\s+")
_YEAR = re.compile(r"(?<![\d.])(\d{1,4})(?:\s*(BCE|BC|CE|AD|B\.C\.E?\.?|A\.D\.))?(?![\d])", re.I)


def workspace_of(t):
    return (t.get("source") or {}).get("workspace") or t.get("workspace") or "lab"


# ---------------------------------------------------------------- pure helpers
def parse_glossary(text, lang=None):
    """`term: definition` or `term - definition` lines (also – and —) to flashcards; other lines are skipped."""
    cards, seen = [], set()
    for line in str(text or "").splitlines():
        line = re.sub(r"^(?:[*•]|[-–—](?=\s))\s*", "", line.strip())
        m = re.match(r"^(.+?)\s*(?::|\s[-–—]\s|\t)\s*(.+)$", line)
        if not m:
            continue
        front, back = m.group(1).strip(), m.group(2).strip()
        if front and back and front.lower() not in seen:
            seen.add(front.lower())
            cards.append({"front": front[:300], "back": back[:600], **({"lang": lang} if lang else {})})
    return cards


def parse_timeline_text(text):
    """`1789 - Storming of the Bastille` lines to timeline events. The left side holds the date (`44 BCE`, `c. 500 BC`,
    `14 July 1789`, `-490`); its last number is the year (the first of a range like `1914–1918`), negative for BCE.
    Text after ` | ` becomes the detail."""
    events = []
    for line in str(text or "").splitlines():
        line = re.sub(r"^(?:[*•]|[-–—](?=\s))\s*", "", line.strip())  # list bullets, not a BCE minus sign
        neg = line.startswith("-") and line[1:2].isdigit()
        body = line[1:] if neg else line
        parts = _SEP.split(body, maxsplit=1)
        if len(parts) != 2 or not parts[1].strip():
            continue
        when, what = parts[0].strip(), parts[1].strip()
        years = list(_YEAR.finditer(when))
        if not years:
            continue
        y = years[-1]
        if len(years) >= 2 and re.search(r"\d\s*[-–—]\s*\d", when):  # a range such as 1914–1918 starts at its first year
            y = years[-2]
        era = ((y.group(2) or years[-1].group(2)) or "").upper().replace(".", "")
        year = int(y.group(1))
        if neg or era in ("BCE", "BC"):
            year = -year
        title, _, detail = what.partition(" | ")
        event = {"year": year, "title": title.strip()[:160]}
        if detail.strip():
            event["detail"] = detail.strip()[:600]
        if when not in (y.group(0), str(y.group(1))):
            event["date"] = (("-" if neg else "") + when)[:40]
        events.append(event)
    return events


def build_quiz_from_flashcards(cards, count=5, seed=None):
    """Multiple-choice questions from flashcards: the question is the front, the answer its back, and up to three
    other cards' backs are the distractors. Needs at least two different backs; returns at most `count` questions."""
    count = 5 if count is None else count
    rng = random.Random(seed)
    cards = [c for c in cards or [] if isinstance(c, dict) and str(c.get("front", "")).strip() and str(c.get("back", "")).strip()]
    backs = list(dict.fromkeys(str(c["back"]) for c in cards))
    if len(backs) < 2:
        return []
    picked = rng.sample(cards, min(max(int(count), 0), len(cards)))
    out = []
    for i, c in enumerate(picked):
        right = str(c["back"])
        wrong = rng.sample([b for b in backs if b != right], min(3, len(backs) - 1))
        options = wrong + [right]
        rng.shuffle(options)
        out.append({"id": f"qff-{i}", "question": f"What does '{c['front']}' mean?", "options": options, "correctAnswer": options.index(right),
                    "hint": str(c.get("hint") or ""), "explanation": f"'{c['front']}' means '{right}'."})
    return out


def pick_match_pairs(cards, count=6):
    """3-8 [front, back] pairs with unique fronts and backs (the server's match_pairs rule), or [] if too few."""
    count = 6 if count is None else count
    pairs, fronts, backs = [], set(), set()
    for c in cards or []:
        if not isinstance(c, dict):
            continue
        a, b = str(c.get("front", "")).strip()[:160], str(c.get("back", "")).strip()[:160]
        if a and b and a not in fronts and b not in backs:
            fronts.add(a)
            backs.add(b)
            pairs.append([a, b])
    pairs = pairs[:max(3, min(8, int(count)))]
    return pairs if len(pairs) >= 3 else []


def copy_payloads(topic, kinds=None):
    """What to post to the target topic: {kind: items}. Practice ids are dropped (the server assigns new ones)."""
    kinds = [k for k in (kinds or KINDS) if k in KINDS]
    out = {}
    if "practice" in kinds and topic.get("practice"):
        out["practice"] = [{k: v for k, v in p.items() if k != "id"} for p in topic["practice"] if isinstance(p, dict)]
    if "flashcards" in kinds and topic.get("flashcards"):
        out["flashcards"] = list(topic["flashcards"])
    if "timeline" in kinds and topic.get("timeline"):
        out["timeline"] = list(topic["timeline"])
    return out


def topic_stats(topic):
    """Counts by activity type plus quiz-check verdicts and missing explanations."""
    practice = {}
    for p in topic.get("practice") or []:
        practice[p.get("type")] = practice.get(p.get("type"), 0) + 1
    quiz = topic.get("quiz") or []
    verdicts = {}
    for qn in quiz:
        chk = qn.get("check")
        v = chk.get("verdict") if isinstance(chk, dict) else (chk if isinstance(chk, str) else "unchecked")
        verdicts[v] = verdicts.get(v, 0) + 1
    return {"id": topic.get("id"), "title": topic.get("title"), "workspace": workspace_of(topic),
            "quiz": len(quiz), "quizChecks": verdicts, "practice": practice, "practiceTotal": sum(practice.values()),
            "flashcards": len(topic.get("flashcards") or []), "timeline": len(topic.get("timeline") or []),
            "cheatSheet": len(topic.get("cheatSheet") or []), "simulation": (topic.get("simulation") or {}).get("kind"),
            "missingExplanations": sum(1 for qn in quiz if not str(qn.get("explanation") or "").strip())
            + sum(1 for p in topic.get("practice") or [] if not str(p.get("explanation") or "").strip())}


def lint_topic(topic):
    """Problems worth fixing: quiz items without an explanation, duplicate questions, practice items with no hint or
    explanation, an empty cheat sheet, and quiz checks that were not verified."""
    issues = []
    seen = {}
    for qn in topic.get("quiz") or []:
        qid = qn.get("id")
        if not str(qn.get("explanation") or "").strip():
            issues.append({"where": f"quiz {qid}", "issue": "no explanation"})
        key = re.sub(r"\s+", " ", str(qn.get("question") or "").strip().lower())
        if key in seen:
            issues.append({"where": f"quiz {qid}", "issue": f"duplicate of quiz {seen[key]}"})
        else:
            seen[key] = qid
        chk = qn.get("check")
        verdict = chk.get("verdict") if isinstance(chk, dict) else (chk if isinstance(chk, str) else None)
        if verdict in ("ambiguous", "low-confidence"):
            issues.append({"where": f"quiz {qid}", "issue": f"answer check: {verdict}"})
    for p in topic.get("practice") or []:
        if not str(p.get("hint") or "").strip() and not str(p.get("explanation") or "").strip():
            issues.append({"where": f"practice {p.get('id')} ({p.get('type')})", "issue": "no hint or explanation"})
    if not topic.get("cheatSheet"):
        issues.append({"where": "cheatSheet", "issue": "empty"})
    return {"id": topic.get("id"), "ok": not issues, "issues": issues}


def search_topics(topics, query, workspace=None):
    """Topics whose title, summary or category contain every word of the query (case-insensitive)."""
    words = [w for w in str(query or "").lower().split() if w]
    out = []
    for t in topics or []:
        if workspace and workspace_of(t) != workspace:
            continue
        blob = " ".join(str(t.get(k) or "") for k in ("title", "summary", "category")).lower()
        if all(w in blob for w in words):
            out.append({"id": t.get("id"), "title": t.get("title"), "workspace": workspace_of(t),
                        "summary": str(t.get("summary") or "")[:200], "course": (t.get("source") or {}).get("courseTitle")})
    return out


def weakest_classes(courses, limit=5):
    """Ready classes with a quiz score, lowest first, across the given course objects (each with `classes`)."""
    rows = []
    for c in courses or []:
        for k in c.get("classes") or []:
            if k.get("score") is not None and k.get("topic_id"):
                rows.append({"courseId": c.get("id"), "course": c.get("title"), "workspace": c.get("workspace"),
                             "seq": k.get("seq"), "title": k.get("title"), "topicId": k["topic_id"], "score": k["score"]})
    rows.sort(key=lambda r: r["score"])
    return rows[:limit]


def challenge_mix(review_questions, weak_topics, size=10):
    """Up to `size` items: missed questions due for review first, then practice items from the weakest topics in turn."""
    mix = [{"kind": "review", "topicId": r.get("topicId"), "questionId": r.get("questionId"), "question": r.get("question")}
           for r in (review_questions or [])[:size]]
    pools = [[p for p in t.get("practice") or [] if isinstance(p, dict)] for t in weak_topics or []]
    i = 0
    while len(mix) < size and any(pools):
        pool = pools[i % len(pools)]
        if pool:
            p = pool.pop(0)
            mix.append({"kind": "practice", "topicId": weak_topics[i % len(pools)].get("id"), "itemId": p.get("id"),
                        "type": p.get("type"), "prompt": p.get("prompt")})
        i += 1
    return mix


# ---------------------------------------------------------------- tools
def tools(call, q, S, STR, OBJ, ARR):
    INT = lambda d, **k: {"type": "integer", "description": d, **k}
    topic = lambda tid: call("GET", f"/api/topics/{q(tid)}")
    post = lambda tid, kind, items: call("POST", f"/api/topics/{q(tid)}/{kind}", {"items": items})
    event = lambda typ, payload: call("POST", "/api/agy/events", {"type": typ, "payload": payload})

    def quiz_from_cards(a):
        quiz = build_quiz_from_flashcards(topic(a["topic_id"]).get("flashcards"), a.get("count", 5))
        if not quiz:
            return {"added": 0, "note": "Needs at least two flashcards with different backs."}
        return {**post(a["topic_id"], "quiz", quiz), "questions": [x["question"] for x in quiz]}

    def glossary(a):
        cards = parse_glossary(a["text"], a.get("lang"))
        if not cards:
            return {"added": 0, "note": "No 'term: definition' or 'term - definition' lines found."}
        return {**post(a["topic_id"], "flashcards", cards), "cards": cards}

    def match_from_cards(a):
        pairs = pick_match_pairs(topic(a["topic_id"]).get("flashcards"), a.get("count", 6))
        if not pairs:
            return {"added": 0, "note": "Needs at least three flashcards with distinct fronts and backs."}
        item = {"type": "match_pairs", "prompt": a.get("prompt") or "Match each term to its meaning", "pairs": pairs}
        return {**post(a["topic_id"], "practice", [item]), "pairs": pairs}

    def timeline(a):
        events = parse_timeline_text(a["text"])
        if not events:
            return {"added": 0, "note": "No 'year - event' lines found (e.g. '1789 - Storming of the Bastille', '44 BCE - ...')."}
        return {**post(a["topic_id"], "timeline", events), "events": events}

    def copy(a):
        payloads = copy_payloads(topic(a["from_topic"]), a.get("kinds"))
        topic(a["to_topic"])  # 404 before anything is written
        return {"copied": {kind: post(a["to_topic"], kind, items) for kind, items in payloads.items()}}

    def outline(a):
        course = call("GET", f"/api/courses/{q(a['course_id'])}")
        rows = []
        for k in course.get("classes") or []:
            row = {"seq": k.get("seq"), "title": k.get("title"), "status": k.get("status"), "score": k.get("score"),
                   "topicId": k.get("topic_id")}
            if k.get("topic_id") and k.get("status") == "ready":
                try:
                    s = topic_stats(topic(k["topic_id"]))
                    row["activities"] = {"quiz": s["quiz"], "practice": s["practiceTotal"], "flashcards": s["flashcards"],
                                         "timeline": s["timeline"]}
                except RuntimeError as e:
                    row["activities"] = {"error": str(e)}
            rows.append(row)
        return {"id": course.get("id"), "title": course.get("title"), "status": course.get("status"),
                "workspace": course.get("workspace"), "classes": rows}

    def user_courses(uid):
        return [call("GET", f"/api/courses/{q(c['id'])}") for c in call("GET", f"/api/users/{q(uid)}/courses").get("courses") or []]

    def dashboard(a):
        uid = a["user_id"]
        p = call("GET", f"/api/engage/{q(uid)}")
        review = call("GET", f"/api/review/{q(uid)}/session")
        return {"xpToday": p.get("xpToday"), "dailyGoal": p.get("dailyGoal"), "totalXp": p.get("totalXp"),
                "level": p.get("level"), "streak": p.get("streak"), "longestStreak": p.get("longestStreak"),
                "freezes": p.get("freezes"), "badges": [b["name"] for b in p.get("badges") or [] if b.get("earned")],
                "quests": p.get("quests"), "reviewDue": len(review.get("questions") or []),
                "nextReview": review.get("nextReview"), "weakestClasses": weakest_classes(user_courses(uid))}

    def challenge(a):
        uid = a["user_id"]
        review = call("GET", f"/api/review/{q(uid)}/session").get("questions") or []
        weak = weakest_classes(user_courses(uid), 3)
        weak_topics = []
        for w in weak:
            try:
                weak_topics.append(topic(w["topicId"]))
            except RuntimeError:
                continue
        mix = challenge_mix(review, weak_topics)
        if not mix:
            return {"items": [], "opened": None, "note": "Nothing to practise yet: no missed questions and no scored classes."}
        if weak and weak[0].get("workspace") == "language" and not review:
            opened = {"mode": "language", "tab": "session", "sessionMode": "missed"}
            event("SWITCH_STUDIO_MODE", opened)
        elif review:
            opened = {"mode": "review"}
            event("SWITCH_STUDIO_MODE", opened)
        else:
            opened = {"topicId": weak[0]["topicId"], "tab": "practice"}
            event("SWITCH_TOPIC", opened)
        return {"items": mix, "opened": opened, "weakest": weak}

    def replace(a):
        return call("PUT", f"/api/topics/{q(a['topic_id'])}/practice/{q(a['item_id'])}", {"item": a["item"]})

    def add_drawing(a):
        from simspec import validate_geometry
        diagram = dict(a.get("diagram") or {})
        if diagram.get("kind") not in ("geometry", "fbd"):
            diagram["kind"] = "geometry"
        clean_diag, errors = validate_geometry(diagram)
        if errors:
            raise RuntimeError(f"Invalid geometry diagram: {'; '.join(errors)}")
        top = topic(a["topic_id"])
        raw_caption = str(a.get("caption") or clean_diag.get("title") or "Geometric Diagram")
        caption = re.sub(r"[\r\n#`]+", " ", raw_caption).strip()[:100] or "Geometric Diagram"
        kind = clean_diag.get("kind", "geometry")
        block = f"\n\n### {caption}\n\n```{kind}\n{json.dumps(clean_diag, indent=2)}\n```\n"
        top["markdownContent"] = (top.get("markdownContent") or "").rstrip() + block
        call("POST", "/api/topics", top)
        return {"status": "added", "topic_id": a["topic_id"], "caption": caption, "spec": clean_diag}

    def preview_drawing(a):
        spec = a.get("spec") or {}
        return call("POST", "/api/ui/geometry", {"spec": spec})

    return [
        ("quiz_from_flashcards", "Offline: turn a lesson's flashcards into multiple-choice quiz questions (other cards' backs are the distractors) and append them.",
         S(topic_id=STR("topic id"), count=INT("how many questions, default 5", optional=True)), quiz_from_cards),
        ("flashcards_from_glossary", "Add flashcards parsed from glossary text, one 'term: definition' or 'term - definition' per line.",
         S(topic_id=STR("topic id"), text=STR("glossary lines"), lang=STR("BCP-47 language of the fronts, read aloud", optional=True)), glossary),
        ("match_pairs_from_flashcards", "Offline: add a match_pairs practice item built from 3-8 of a lesson's flashcards.",
         S(topic_id=STR("topic id"), count=INT("pairs, 3-8 (default 6)", optional=True), prompt=STR("instruction", optional=True)), match_from_cards),
        ("timeline_from_text", "Add timeline events parsed from lines like '1789 - Storming of the Bastille' or '44 BCE - Caesar is killed | detail'.",
         S(topic_id=STR("topic id"), text=STR("one event per line")), timeline),
        ("copy_activities", "Copy practice items, flashcards and/or timeline events from one lesson to another (practice gets new ids).",
         S(from_topic=STR("source topic id"), to_topic=STR("target topic id"),
           kinds={"type": "array", "items": {"type": "string", "enum": list(KINDS)}, "description": "default all three", "optional": True}), copy),
        ("topic_stats", "A lesson's activity counts by type, quiz answer-check verdicts and missing explanations.",
         S(topic_id=STR("topic id")), lambda a: topic_stats(topic(a["topic_id"]))),
        ("lint_topic", "Problems in a lesson: quiz items without explanations, duplicate questions, practice with no hint, empty cheat sheet, doubtful answer checks.",
         S(topic_id=STR("topic id")), lambda a: lint_topic(topic(a["topic_id"]))),
        ("search_topics", "Search lessons by words in their title, summary and category, optionally in one workspace.",
         S(query=STR("words"), workspace=STR("math | code | lab | history | language", optional=True)),
         lambda a: search_topics(call("GET", "/api/topics"), a["query"], a.get("workspace"))),
        ("course_outline", "A course's classes with status, quiz score and activity counts.",
         S(course_id=STR("course id")), outline),
        ("student_dashboard", "A student's XP, level, streak, daily goal, badges, quests, review questions due and weakest classes.",
         S(user_id=STR("profile id")), dashboard),
        ("review_queue", "Missed quiz questions due for spaced review today (up to 10).",
         S(user_id=STR("profile id")), lambda a: call("GET", f"/api/review/{q(a['user_id'])}/session")),
        ("open_workspace", "Show a workspace on the student's screen, optionally one of its sub-tabs (e.g. history > timeline, language > words).",
         S(mode=STR("workspace", enum=list(WORKSPACES)), tab=STR("sub-tab id", optional=True)),
         lambda a: {"status": "opened", "mode": a["mode"], "tab": a.get("tab"),
                    "event": event("SWITCH_STUDIO_MODE", {"mode": a["mode"], **({"tab": a["tab"]} if a.get("tab") else {})})}),
        ("daily_challenge", "Build a 10-item mix from a student's due review questions and weakest classes, and open the best place to start it.",
         S(user_id=STR("profile id")), challenge),
        ("remove_practice_item", "Delete one practice item from a lesson; returns the removed item.",
         S(topic_id=STR("topic id"), item_id=STR("practice item id, e.g. p3")),
         lambda a: call("DELETE", f"/api/topics/{q(a['topic_id'])}/practice/{q(a['item_id'])}")),
        ("replace_practice_item", "Replace one practice item (normalized like new ones; keeps its id and, if omitted, its prompt). Returns before and after.",
         S(topic_id=STR("topic id"), item_id=STR("practice item id"), item=OBJ("the new practice item (any type)")), replace),
        ("remove_flashcard", "Delete one flashcard by its 0-based position; returns the removed card.",
         S(topic_id=STR("topic id"), index=INT("0-based card index")),
         lambda a: call("DELETE", f"/api/topics/{q(a['topic_id'])}/flashcards/{int(a['index'])}")),
        ("add_drawing_to_notes", "Append an interactive geometry or free-body diagram block directly to a lesson's markdown notes.",
         S(topic_id=STR("topic id"), diagram=OBJ("geometry or fbd specification"), caption=STR("optional section title/caption", optional=True)), add_drawing),
        ("preview_geometry_diagram", "Project an interactive geometry or free-body diagram in Math Lab on the student's screen in real time.",
         S(spec=OBJ("geometry or fbd specification")), preview_drawing),
    ]
