"""Lab, Math and IDE activity tools for the &.edu MCP server: label_diagram, sort_by, odd_one_out, cloze and
spot_the_bug practice items, the offline diagram list and the practice type guide. Imported by mcp_server.py, which
passes in its HTTP helpers; every item goes through the backend's validation (server.normalize_practice)."""


def item(a, default_prompt, **fields):
    """A practice item with a prompt (normalize_practice drops items without one) and only the fields that are set."""
    return {"prompt": a.get("prompt") or default_prompt, "explanation": a.get("explanation", ""),
            **{k: v for k, v in fields.items() if v not in (None, "", [])}}


def label_diagram_item(a):
    return item(a, "Label the diagram", type="label_diagram", image=a.get("image"), svg_spec=a.get("svg_spec"), labels=a["labels"])


def sort_by_item(a):
    return item(a, f"Order these by {a['property']}, lowest first", type="sort_by", property=a["property"], items=a["items"], unit=a.get("unit"))


def odd_one_out_item(a):
    return item(a, "Which one does not belong?", type="odd_one_out", options=a["options"], answer=a["answer"], why=a.get("why"))


def cloze_item(a):
    return item(a, "Fill the gaps", type="cloze", text=a["text"], bank=a.get("bank"))


def spot_the_bug_item(a):
    return item(a, "Find the line with the bug", type="spot_the_bug", code=a["code"], language="python",
                bug_line=a["bug_line"], fix=a.get("fix"))


def tools(call, q, S, STR, OBJ, ARR):
    practice = lambda tid, it: call("POST", f"/api/topics/{q(tid)}/practice", {"items": [it]})
    EXPL = lambda: STR("shown after answering", optional=True)
    STRS = lambda d, **k: {"type": "array", "items": {"type": "string"}, "description": d, **k}

    return [
        ("add_label_diagram", "Label-the-diagram activity: the student drags 3-8 labels onto their spots (counted within 0.06). "
         "Give `image` (a name from list_diagram_images) OR `svg_spec` ({width, height, shapes: [{kind: rect|circle|line|text, "
         "numeric attrs, text, tone?, filled?}]}: data, never SVG markup; anything with <script, on*= or href is rejected). "
         "Label x/y are fractions 0-1 of the image (0,0 = top left).",
         S(topic_id=STR("topic id"), prompt=STR("instruction, default 'Label the diagram'", optional=True),
           image=STR("diagram file name, e.g. cell.svg", optional=True),
           svg_spec=OBJ("drawn diagram, see practice_type_guide", optional=True),
           labels=ARR("[{text, x, y}] with x/y in 0-1, 3-8 labels"), explanation=EXPL()),
         lambda a: practice(a["topic_id"], label_diagram_item(a))),
        ("add_sort_by", "Sorting activity: the student orders 3-7 items by a numeric property from low to high; the values are revealed after checking.",
         S(topic_id=STR("topic id"), property=STR("what to sort by, e.g. 'density'"),
           items=ARR("[{text, value}] with numeric, distinct values"), unit=STR("unit shown with the values", optional=True),
           prompt=STR("instruction", optional=True), explanation=EXPL()),
         lambda a: practice(a["topic_id"], sort_by_item(a))),
        ("add_odd_one_out", "Odd-one-out activity: four options, the student picks the one that does not belong; `why` is shown afterwards.",
         S(topic_id=STR("topic id"), options=STRS("exactly 4 options"), answer=STR("the odd one, one of the options"),
           why=STR("why it does not belong"), prompt=STR("instruction", optional=True), explanation=EXPL()),
         lambda a: practice(a["topic_id"], odd_one_out_item(a))),
        ("add_cloze", "Cloze (fill the gaps) activity: write 1-6 gaps in `text` as [[answer]] or [[answer|alternative]]. Answers are graded "
         "leniently (case, punctuation, small typos). An optional `bank` of words must contain each gap's first answer.",
         S(topic_id=STR("topic id"), text=STR("text with [[gaps]]"), bank=STRS("word bank (answers plus distractors)", optional=True),
           prompt=STR("instruction", optional=True), explanation=EXPL()),
         lambda a: practice(a["topic_id"], cloze_item(a))),
        ("add_spot_the_bug", "Spot-the-bug activity for Python: the student clicks the buggy line, then can edit it and run the program in "
         "the browser (Pyodide). `bug_line` is 1-based; `fix` is the corrected version of that one line.",
         S(topic_id=STR("topic id"), code=STR("Python code, up to 60 lines"), bug_line={"type": "integer", "description": "1-based line with the bug"},
           fix=STR("corrected line", optional=True), prompt=STR("instruction", optional=True), explanation=EXPL()),
         lambda a: practice(a["topic_id"], spot_the_bug_item(a))),
        ("list_diagram_images", "Names of the offline diagram images (public/diagrams/) to use as `image` in add_label_diagram.",
         S(), lambda a: call("GET", "/api/diagrams")),
        ("practice_type_guide", "Every practice type with its fields and drop rules (from the server's normalizers). Read it before writing practice items.",
         S(), lambda a: call("GET", "/api/practice/guide")),
    ]
