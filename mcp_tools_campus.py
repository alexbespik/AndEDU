"""MCP tools for campus events (W&M calendars): search, now, week, save an event, set the interest prompt.

Ported from AndEVENTS (github.com/alexbespik/AndEVENTS) by the same author. Each tool calls the running backend
(campus_events.py routes), so results are the same ones the Campus tab shows.
"""


def tools(call, q, S, STR, OBJ, ARR):
    def query(**params):
        pairs = [f"{k}={q(v)}" for k, v in params.items() if v not in (None, "")]
        return ("?" + "&".join(pairs)) if pairs else ""

    def search(a):
        return call("GET", f"/api/campus/{q(a['user_id'])}/events" + query(
            q=a.get("query"), category=a.get("category"), **{"from": a.get("from"), "to": a.get("to")}))

    def week(a):
        return call("GET", f"/api/campus/{q(a['user_id'])}/planner" + query(week=a.get("week"), scope=a.get("scope")))

    def set_interest(a):
        current = call("GET", f"/api/campus/{q(a['user_id'])}/intent")
        if not isinstance(current, dict) or "prompt" not in current:
            return current
        return call("PUT", f"/api/campus/{q(a['user_id'])}/intent",
                    {"prompt": a["prompt"], "auto_add": bool(a.get("auto_add", current.get("auto_add"))),
                     "notify": bool(current.get("notify", True))})

    DAY = "a date like 2026-11-16"
    return [
        ("campus_events_search",
         "Search upcoming W&M campus events (default: today to 30 days ahead, at most 90). Returns events with uid, "
         "title, time, location, category, and whether the student saved it or it clashes with a class.",
         S(user_id=STR("profile id"), query=STR("words to look for in titles and descriptions", optional=True),
           **{"from": STR(f"first day, {DAY}", optional=True), "to": STR(f"last day, {DAY}", optional=True)},
           category=STR("cs | arts | sports | bio | civics | life | acad", optional=True)),
         search),
        ("campus_now",
         "What is on right now for a student: the current and next class, events happening now, starting within "
         "three hours, and later today.",
         S(user_id=STR("profile id")),
         lambda a: call("GET", f"/api/campus/{q(a['user_id'])}/now")),
        ("campus_week",
         "A student's week: classes and events per day with clash counts. scope 'saved' (default) shows only saved "
         "events, 'all' shows every campus event (at most 40 a day).",
         S(user_id=STR("profile id"), week=STR(f"any day of the week, {DAY} (default: this week)", optional=True),
           scope=STR("saved | all", optional=True)),
         week),
        ("campus_save_event",
         "Save a campus event to a student's planner (uid from campus_events_search). Saving twice changes nothing.",
         S(user_id=STR("profile id"), uid=STR("event uid")),
         lambda a: call("POST", f"/api/campus/{q(a['user_id'])}/saved", {"uid": a["uid"]})),
        ("campus_set_interest",
         "Set what a student wants to hear about (e.g. 'robotics talks and a cappella concerts'). The text is sent to "
         "the AI model once to pick keywords; matching upcoming events become alerts. Returns the matched counts.",
         S(user_id=STR("profile id"), prompt=STR("the student's interests, up to 500 characters"),
           auto_add={"type": "boolean", "description": "also save every match to the planner", "optional": True}),
         set_interest),
    ]
