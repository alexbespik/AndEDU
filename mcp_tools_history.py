"""History tools for the &.edu MCP server (Counterfactual Crisis Simulator, Primary Source Interrogator,
Chronological Timeline Challenges, and the history interactives: maps, sources, figures, games). Imported by
mcp_server.py; every tool goes through the backend's validation."""
import re
import unicodedata

import practice_history

# Lon/lat window of each outline map in public/maps/ (lon0, lat0, lon1, lat1); x and y are linear in lon and lat.
MAP_BOUNDS = {"world": (-180, -60, 180, 84), "europe": (-25, 34, 45, 72), "mediterranean": (-10, 29, 42, 47),
              "americas": (-170, -57, -30, 75), "asia": (25, -12, 150, 78)}
HISTORY_TABS = ["map", "sources", "figures", "games", "timeline", "crisis", "cards"]


def lonlat_to_xy(map_name, lon, lat):
    """The 0-1 map fractions of a longitude and latitude on one of the outline maps."""
    lon0, lat0, lon1, lat1 = MAP_BOUNDS[map_name]
    return round((float(lon) - lon0) / (lon1 - lon0), 4), round((lat1 - float(lat)) / (lat1 - lat0), 4)


def map_pins_item(a):
    """A map_pins item; each pin gives x/y fractions, or lon/lat that are converted for the chosen map."""
    pins = []
    for p in a.get("pins") or []:
        pin = {"label": p.get("label")}
        if p.get("x") is None and p.get("lon") is not None and a.get("map") in MAP_BOUNDS:
            pin["x"], pin["y"] = lonlat_to_xy(a["map"], p["lon"], p.get("lat"))
        else:
            pin["x"], pin["y"] = p.get("x"), p.get("y")
        if p.get("tolerance") is not None:
            pin["tolerance"] = p["tolerance"]
        pins.append(pin)
    return {"type": "map_pins", "prompt": a.get("prompt") or "Drag each label to its place on the map", "map": a.get("map"), "pins": pins,
            "explanation": a.get("explanation", "")}


def _slug(text):
    ascii_text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:70] or "history-unit"


def fmt_year(y):
    y = int(round(float(y)))
    return f"{-y} BCE" if y < 0 else str(y)


def _century(y):
    y = int(round(float(y)))
    n = (abs(y) - 1) // 100 + 1 if y else 1
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix} century{' BCE' if y < 0 else ''}"


def _clean(items):
    """Items as the server will store them; anything its normalizers would drop is left out here."""
    out = []
    for i, p in enumerate(items):
        fn = practice_history.NORMALIZERS.get(p["type"])
        base = {"id": f"p{i + 1}", "type": p["type"], "prompt": p["prompt"], "explanation": p.get("explanation", ""), "concept": None}
        item = fn(p, base) if fn else None
        if item:
            out.append(item)
    return [{**p, "id": f"p{i + 1}"} for i, p in enumerate(out)]


def _categorize(events):
    """Events sorted into their centuries (2-4 buckets), or into before/after the middle year."""
    evs = events[:12]
    if len(evs) < 4:
        return None
    cents = list(dict.fromkeys(_century(e["year"]) for e in evs))
    if 2 <= len(cents) <= 4:
        items = [[e["title"], _century(e["year"])] for e in evs]
        return {"type": "categorize", "prompt": "Sort the events by century", "buckets": cents, "items": items}
    mid = sorted(float(e["year"]) for e in evs)[len(evs) // 2]
    before, after = f"Before {fmt_year(mid)}", f"{fmt_year(mid)} or later"
    return {"type": "categorize", "prompt": "Sort the events: earlier or later?", "buckets": [before, after],
            "items": [[e["title"], before if float(e["year"]) < mid else after] for e in evs]}


def _source_items(sources, people, events):
    out = []
    authors = [s.get("author") for s in sources if s.get("author")] + [p["name"] for p in people]
    for s in sources:
        questions = list(s.get("questions") or [])
        if not questions and s.get("author"):
            others = [a for a in dict.fromkeys(authors) if a != s["author"]][:3]
            if others:
                questions.append({"question": "Who wrote or issued this source?", "options": [s["author"], *others], "answer": s["author"]})
        if not questions and s.get("date"):
            others = [e.get("date") or fmt_year(e["year"]) for e in events]
            others = [d for d in dict.fromkeys(others) if d != s["date"]][:3]
            if others:
                questions.append({"question": "When does this source date from?", "options": [s["date"], *others], "answer": s["date"]})
        out.append({"type": "source_analysis", "prompt": s.get("prompt") or f"Read the source{': ' + s['title'] if s.get('title') else ''}",
                    "source": {k: s.get(k, "") for k in ("text", "author", "date", "citation")}, "questions": questions})
    return out


def history_unit_topic(a):
    """A complete history unit (topic JSON) from events, people and optional sources; no model calls."""
    events = sorted([e for e in a.get("events") or [] if e.get("title") and e.get("year") is not None], key=lambda e: float(e["year"]))
    people, sources = [p for p in a.get("people") or [] if p.get("name")], a.get("sources") or []
    md = f"# {a['title']}\n\n{a.get('intro', '')}\n\n## Events\n\n"
    md += "\n".join(f"- **{e.get('date') or fmt_year(e['year'])}**: {e['title']}{(' — ' + e['detail']) if e.get('detail') else ''}" for e in events) + "\n"
    if people:
        md += "\n## People\n\n" + "\n".join(f"- **{p['name']}**{(' (' + p['years'] + ')') if p.get('years') else ''}: {p.get('role', '')}" for p in people) + "\n"
    for s in sources:
        quote = "\n".join("> " + ln for ln in str(s.get("text", "")).splitlines())
        md += f"\n## Source: {s.get('title') or s.get('author') or 'Primary source'}\n\n{quote}\n\n— {s.get('author', '')}{(', ' + s['date']) if s.get('date') else ''}\n"
    practice = []
    cat = _categorize(events)
    if cat:
        practice.append(cat)
    if len(events) >= 3:
        chain = events[:6]
        whys = [e.get("why") or "" for e in chain[1:]]
        practice.append({"type": "cause_effect", "prompt": "Put the chain of events in order, cause first",
                         "chain": [e["title"] for e in chain], "links": whys if all(whys) else []})
    practice += _source_items(sources, people, events)
    return {"id": a.get("id") or _slug(a["title"]), "title": a["title"], "category": a.get("category") or "History",
            "difficulty": a.get("level") or "Introductory", "summary": a.get("intro") or f"Events and people: {a['title']}.",
            "workspace": "history", "markdownContent": md, "quiz": [], "practice": _clean(practice),
            "timeline": [{"year": float(e["year"]), "title": e["title"], "date": e.get("date"), "detail": e.get("detail", ""),
                          **({"era": e["era"]} if e.get("era") else {})} for e in events],
            "flashcards": [{"front": p["name"], "back": p.get("role") or p.get("years") or p["name"],
                            **({"hint": p["years"]} if p.get("years") else {})} for p in people]}


def era_markers(start, end, label):
    """Two timeline events that open and close a named era; the History timeline draws a band between them."""
    start, end = sorted((float(start), float(end)))
    span = f"{fmt_year(start)}–{fmt_year(end)}"
    return [{"year": start, "title": f"{label} begins", "date": fmt_year(start), "detail": f"Era: {label} ({span})", "era": label},
            {"year": end, "title": f"{label} ends", "date": fmt_year(end), "detail": f"Era: {label} ({span})", "era": label}]


def history_overview(topics):
    """History units with practice counts by type and the span of their timelines."""
    units, years = [], []
    for t in topics:
        if ((t.get("source") or {}).get("workspace") or t.get("workspace")) != "history":
            continue
        kinds = {}
        for p in t.get("practice") or []:
            kinds[p.get("type")] = kinds.get(p.get("type"), 0) + 1
        ys = [e["year"] for e in t.get("timeline") or [] if isinstance(e.get("year"), (int, float))]
        years += ys
        units.append({"id": t["id"], "title": t.get("title"), "course": (t.get("source") or {}).get("courseTitle"),
                      "flashcards": len(t.get("flashcards") or []), "timeline": len(t.get("timeline") or []),
                      "eras": sorted({e["era"] for e in t.get("timeline") or [] if e.get("era")}),
                      "span": [fmt_year(min(ys)), fmt_year(max(ys))] if ys else None, "exercises": kinds})
    return {"units": units, "span": [fmt_year(min(years)), fmt_year(max(years))] if years else None}
import re


def tools(call, q, S, STR, OBJ, ARR):
    event = lambda payload: call("POST", "/api/agy/events", {"type": "SWITCH_STUDIO_MODE", "payload": {"mode": "history", **payload}})

    return [
        (
            "start_historical_crisis",
            "Open a counterfactual branching historical crisis simulator on the student's screen (History > Crisis Simulator): "
            "cuban-missile-crisis | crossing-the-rubicon | berlin-airlift | constitutional-convention or custom crisisId.",
            S(crisis_id=STR("crisis scenario id, e.g. cuban-missile-crisis", optional=True)),
            lambda a: event({"tab": "crisis", "crisisId": a.get("crisis_id", "cuban-missile-crisis")}),
        ),
        (
            "add_crisis_scenario",
            "Attach a counterfactual crisis scenario/dilemma to a history topic: {id, title, role, setting, "
            "initialState: {tension, allies, publicSupport}, options: [{id, label, description, delta, consequence, counterfactual, realHistory, isAuthentic}]}.",
            S(topic_id=STR("topic id"), scenario=OBJ("crisis scenario object")),
            lambda a: call("POST", f"/api/topics/{q(a['topic_id'])}/crisis", {"scenario": a["scenario"]}),
        ),
        (
            "open_primary_source",
            "Open an annotated primary source interrogator on the student's screen (History > Primary Sources): "
            "magna-carta-1215 | hammurabi-code | rights-of-man-1789 | douglass-fourth-july or custom docId.",
            S(doc_id=STR("document id, e.g. magna-carta-1215", optional=True)),
            lambda a: event({"tab": "sources", "docId": a.get("doc_id", "magna-carta-1215")}),
        ),
        (
            "add_primary_source_lab",
            "Attach an annotated primary source document to a history topic for Stanford SHEG interrogations: "
            "{id, title, author, date, text, annotations: {target: {title, note, type}}, shegSteps: [{step, name, question, modelAnswer}]}.",
            S(topic_id=STR("topic id"), source=OBJ("annotated primary source object")),
            lambda a: call("POST", f"/api/topics/{q(a['topic_id'])}/primary-source", {"source": a["source"]}),
        ),
        (
            "start_timeline_challenge",
            "Open the chronological event ordering challenge on the student's screen (History > Timeline in challenge mode).",
            S(),
            lambda a: event({"tab": "timeline", "challenge": True}),
        ),
        (
            "get_historical_context",
            "Get all history content (crisis scenarios, primary sources, timeline events, flashcards) for a topic.",
            S(topic_id=STR("topic id")),
            lambda a: call("GET", f"/api/topics/{q(a['topic_id'])}"),
        ),
        (
            "add_historical_flashcards",
            "Add history flashcards to a topic: dates, events, people, places, causes and effects.",
            S(topic_id=STR("topic id"), items=ARR("[{front, back, hint?}] — front is the term/date, back is the definition/event")),
            lambda a: call("POST", f"/api/topics/{q(a['topic_id'])}/flashcards", {"items": a["items"]}),
        ),
        (
            "add_history_timeline_events",
            "Add chronological events to a history topic's timeline (displayed in the History > Timeline tab).",
            S(topic_id=STR("topic id"), events=ARR("[{year (number, negative = BCE), title, date?, detail?, era?}]")),
            lambda a: call("POST", f"/api/topics/{q(a['topic_id'])}/timeline", {"events": [
                {**e, "detail": e.get("detail") or e.get("description") or e.get("significance") or ""} if isinstance(e, dict) else e
                for e in a["events"]]}),
        ),
        (
            "add_history_quiz",
            "Add multiple-choice quiz questions to a history topic (used in Speed Round).",
            S(topic_id=STR("topic id"), questions=ARR("[{id, question, options: [str], correctAnswer: int (0-based), hint?, explanation?}]")),
            lambda a: call("POST", f"/api/topics/{q(a['topic_id'])}/quiz", {"questions": a["questions"]}),
        ),
        (
            "add_history_practice",
            "Add practice exercises to a history topic: fill_blank, order_steps, true_false, match_pairs.",
            S(topic_id=STR("topic id"), items=ARR("practice items; each has type and type-specific fields per AGENTS.md")),
            lambda a: call("POST", f"/api/topics/{q(a['topic_id'])}/practice", {"items": a["items"]}),
        ),
        (
            "create_history_topic",
            "Create a complete history topic with lesson content, quiz questions, timeline events and flashcards in one call.",
            S(
                title=STR("topic title"),
                category=STR("e.g. American History, World History, Ancient History"),
                summary=STR("1-2 sentence summary"),
                content=STR("markdown lesson content with ## headings"),
                id=STR("kebab-case id", optional=True),
                difficulty=STR("Introductory | Intermediate | Advanced", optional=True),
            ),
            lambda a: call(
                "POST",
                "/api/topics",
                {
                    "id": a.get("id") or re.sub(r"[^a-z0-9]+", "-", a["title"].lower()).strip("-")[:60],
                    "title": a["title"],
                    "category": a["category"],
                    "difficulty": a.get("difficulty", "Intermediate"),
                    "summary": a["summary"],
                    "markdownContent": a["content"],
                    "workspace": "history",
                    "quiz": [],
                    "practice": [],
                    "flashcards": [],
                },
            ),
        ),
        (
            "open_history_tab",
            "Show a History workspace tab on the student's screen: courses | crisis | sources | cards | timeline.",
            S(tab=STR("tab", enum=["courses", "crisis", "sources", "cards", "timeline"])),
            lambda a: call(
                "POST",
                "/api/agy/events",
                {"type": "SWITCH_STUDIO_MODE", "payload": {"mode": "history", "tab": a["tab"]}},
            ),
        ),
        (
            "start_history_quiz",
            "Open a Speed Round (Kahoot-style quiz) for a history topic on the student's screen.",
            S(topic_id=STR("topic id")),
            lambda a: call(
                "POST",
                "/api/agy/events",
                {"type": "SWITCH_TOPIC", "payload": {"topicId": a["topic_id"], "tab": "speed"}},
            ),
        ),
        (
            "start_flashcard_review",
            "Open a flashcard review session for a history topic on the student's screen.",
            S(topic_id=STR("topic id")),
            lambda a: call(
                "POST",
                "/api/agy/events",
                {"type": "SWITCH_TOPIC", "payload": {"topicId": a["topic_id"], "tab": "cards"}},
            ),
        ),
        (
            "list_history_topics",
            "List all history topics with their available content (crisis scenarios, primary sources, timeline events, flashcards, quiz questions).",
            S(),
            lambda a: [
                {
                    "id": t["id"],
                    "title": t.get("title"),
                    "category": t.get("category"),
                    "has_crisis": bool(t.get("crisis")),
                    "has_sources": bool(t.get("primarySources") or t.get("primary_source")),
                    "timeline_events": len(t.get("timeline") or []),
                    "flashcards": len(t.get("flashcards") or []),
                    "quiz_questions": len(t.get("quiz") or []),
                }
                for t in call("GET", "/api/topics")
                if ((t.get("source") or {}).get("workspace") or t.get("workspace")) == "history"
            ],
        ),
    ] + _interactive_tools(call, q, S, STR, OBJ, ARR, event)


def _interactive_tools(call, q, S, STR, OBJ, ARR, event):
    """The history interactives (docs/agy-tasks/history_interactives.md §E): practice types, units, tabs, eras, figures."""
    practice = lambda tid, *items: call("POST", f"/api/topics/{q(tid)}/practice", {"items": list(items)})
    STRS = lambda d, **k: {"type": "array", "items": {"type": "string"}, "description": d, **k}
    NUM = lambda d, **k: {"type": "number", "description": d, **k}
    EXPL = lambda: STR("shown after answering", optional=True)

    def item(a, default_prompt, **fields):
        return {"prompt": a.get("prompt") or default_prompt, "explanation": a.get("explanation", ""),
                **{k: v for k, v in fields.items() if v is not None}}

    return [
        ("add_categorize", "Sorting game: the student drags (or taps) each item into its bucket. 2-4 buckets, 4-12 items "
         "as [text, bucket]; every bucket needs at least one item.",
         S(topic_id=STR("topic id"), buckets=STRS("2-4 bucket names"),
           items={"type": "array", "items": {"type": "array", "items": {"type": "string"}}, "description": "[[text, bucket], ...] (4-12)"},
           prompt=STR("instruction, default 'Sort each item into its group'", optional=True), explanation=EXPL()),
         lambda a: practice(a["topic_id"], item(a, "Sort each item into its group", type="categorize", buckets=a["buckets"], items=a["items"]))),
        ("add_cause_effect_chain", "Cause-and-effect chain: the student orders 3-6 shuffled events, cause first. Optional `links` "
         "(one per join, len(chain)-1) explain each step and are revealed when that join is right.",
         S(topic_id=STR("topic id"), chain=STRS("3-6 distinct events, cause first"),
           links=STRS("why each event led to the next (len(chain)-1)", optional=True),
           prompt=STR("instruction", optional=True), explanation=EXPL()),
         lambda a: practice(a["topic_id"], item(a, "Put the chain of events in order, cause first", type="cause_effect", chain=a["chain"],
                                                links=a.get("links") or []))),
        ("add_source_analysis", "Primary-source reading with 2-5 multiple-choice questions (sourcing, context, close reading). "
         "source = {text (up to 1500 chars), author, date, citation}; questions = [{question, options (2-5), answer (option text)}]. "
         "Shown in History > Sources with century filters.",
         S(topic_id=STR("topic id"), source=OBJ("{text, author, date, citation}"), questions=ARR("[{question, options, answer}]"),
           prompt=STR("instruction", optional=True), explanation=EXPL()),
         lambda a: practice(a["topic_id"], item(a, "Read the source and answer the questions", type="source_analysis", source=a["source"],
                                                questions=a["questions"]))),
        ("add_map_pins", "Map game: the student drags up to 10 labels onto an offline outline map (world | europe | mediterranean | "
         "americas | asia). Give each pin x/y as 0-1 fractions of the map, or lon/lat and the tool converts them. "
         f"Map windows (lon0, lat0, lon1, lat1): {MAP_BOUNDS}. Tolerance defaults to 0.06.",
         S(topic_id=STR("topic id"), map=STR("outline map", enum=list(MAP_BOUNDS)),
           pins=ARR("[{label, x, y} or {label, lon, lat}, optional tolerance] (1-10)"),
           prompt=STR("instruction", optional=True), explanation=EXPL()),
         lambda a: practice(a["topic_id"], map_pins_item(a))),
        ("add_who_am_i", "Who am I?: clues are revealed one at a time (hardest first, 3-6); the student picks the answer from 3-5 "
         "options. Fewer clues used scores more points.",
         S(topic_id=STR("topic id"), clues=STRS("3-6 clues, hardest first"), answer=STR("the figure, place or event"),
           options=STRS("3-5 options including the answer"), prompt=STR("instruction", optional=True), explanation=EXPL()),
         lambda a: practice(a["topic_id"], item(a, "Who am I?", type="who_am_i", clues=a["clues"], answer=a["answer"], options=a["options"]))),
        ("add_date_guess", "Date guess: the student guesses the year of an event (negative = BCE) with up to 3 tries and earlier/later hints.",
         S(topic_id=STR("topic id"), event=STR("what happened"), year=NUM("the year, negative for BCE"),
           tolerance=NUM("years either side that count as right (default 5)", optional=True),
           prompt=STR("instruction", optional=True), explanation=EXPL()),
         lambda a: practice(a["topic_id"], item(a, "When did it happen?", type="date_guess", event=a["event"], year=a["year"],
                                                tolerance=a.get("tolerance")))),
        ("add_roleplay_persona", "A historical figure the student can interview (History > Figures, and in the lesson's practice). "
         "The tutor plays the persona in first person, in period, without inventing quotes. Ungraded; done after 4 student turns.",
         S(topic_id=STR("topic id"), persona=STR("who, e.g. 'Cicero, Roman senator'"), era=STR("when and where, e.g. 'Rome, 63 BCE'"),
           goal=STR("what the student should find out"), opening=STR("the figure's first line"), prompt=STR("instruction", optional=True)),
         lambda a: practice(a["topic_id"], item(a, f"Interview {a['persona']}", type="roleplay", persona=a["persona"], era=a["era"],
                                                goal=a["goal"], opening=a["opening"]))),
        ("build_history_unit", "Create a whole history unit offline (no model quota) from events and people: notes, a timeline, "
         "flashcards for the people, a categorize game, a cause-and-effect chain, and source questions for any sources. "
         "Replaces any topic with the same id: check list_topics first.",
         S(title=STR("unit title"),
           events=ARR("[{year (negative = BCE), title, date?, detail?, why? (how the previous event led to this one), era?}]"),
           people=ARR("[{name, role, years?}]"),
           sources=ARR("[{text, author, date, citation, title?, questions?: [{question, options, answer}]}]", optional=True),
           intro=STR("one or two sentences", optional=True), level=STR("Introductory | Intermediate | Advanced", optional=True),
           id=STR("kebab-case id (default from title)", optional=True)),
         lambda a: call("POST", "/api/topics", history_unit_topic(a))),
        ("start_history_activity", "Show a History tab on the student's screen: map | sources | figures | games | timeline | crisis | cards.",
         S(tab=STR("tab", enum=HISTORY_TABS)), lambda a: event({"tab": a["tab"]})),
        ("history_overview", "Every history unit with exercise counts by type, flashcards, named eras and the span of its timeline.",
         S(), lambda a: history_overview(call("GET", "/api/topics"))),
        ("chat_as_figure", "Ask a historical figure a question through the tutor's persona mode (in period, no invented quotes, "
         "under 120 words, ends with a question back). Pass earlier turns in `history` to continue a conversation.",
         S(topic_id=STR("topic id (the lesson the figure belongs to)"), persona=STR("who the tutor plays"), message=STR("the question"),
           era=STR("when and where", optional=True),
           history=ARR("[{role: user|assistant, content}]", optional=True)),
         lambda a: call("POST", "/api/tutor/lesson", {"topicId": a["topic_id"], "mode": "persona", "persona": a["persona"],
                                                      "era": a.get("era", ""), "message": a["message"], "history": a.get("history") or []})),
        ("add_timeline_era", "Name an era on a topic's timeline (e.g. 'Roman Republic', -509 to -27): adds two timeline markers "
         "tagged with the era, and History > Timeline draws it as a band.",
         S(topic_id=STR("topic id"), start=NUM("first year (negative = BCE)"), end=NUM("last year"), label=STR("era name (up to 60 chars)")),
         lambda a: call("POST", f"/api/topics/{q(a['topic_id'])}/timeline", {"items": era_markers(a["start"], a["end"], a["label"][:60])})),
    ]
