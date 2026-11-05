"""History interactives: the seven practice normalizers (practice_history.py), the offline outline maps, the
history MCP tools and the build_history_unit round trip. Offline: shares test_lab's temporary data folder and its
Gemini stub."""
import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from test_lab import LOCAL, TMP, TestClient, server, topic  # noqa: F401  (sets up the temp data dir first)

import mcp_server
import mcp_tools_history
import practice_history

ROOT = Path(__file__).resolve().parent.parent
N = server.normalize_practice
BASE = {"id": "p1", "prompt": "p", "explanation": "", "concept": None}


def setUpModule():
    server.TOPICS_DIR.mkdir(parents=True, exist_ok=True)  # test_lab's tearDownModule may already have removed the temp dir


def direct(item):
    """The module's own normalizer, without going through server.py."""
    return practice_history.NORMALIZERS[item["type"]](item, {**BASE, "type": item["type"]})


class HistoryTypeCase(unittest.TestCase):
    def kept(self, item):
        a = direct({"prompt": "p", **item})
        b = N([{"prompt": "p", **item}])
        self.assertIsNotNone(a, item)
        self.assertEqual(len(b), 1, f"server.normalize_practice dropped {item}")
        self.assertEqual(b[0]["type"], item["type"])
        return a

    def dropped(self, item):
        self.assertIsNone(direct({"prompt": "p", **item}), item)
        self.assertEqual(N([{"prompt": "p", **item}]), [], item)


class Categorize(HistoryTypeCase):
    OK = {"type": "categorize", "buckets": ["Rome", "Greece"],
          "items": [["Senate", "Rome"], ["Agora", "Greece"], ["Consul", "Rome"], {"text": "Polis", "bucket": "Greece"}]}

    def test_kept(self):
        c = self.kept(self.OK)
        self.assertEqual(c["buckets"], ["Rome", "Greece"])
        self.assertEqual(c["items"][3], ["Polis", "Greece"])

    def test_dropped(self):
        self.dropped({**self.OK, "items": self.OK["items"][:3] + [["Polis", "Persia"]]})       # unknown bucket
        self.dropped({**self.OK, "buckets": ["Rome", "Greece", "Persia"]})                      # empty bucket
        self.dropped({**self.OK, "buckets": ["Rome"]})                                          # too few buckets
        self.dropped({**self.OK, "items": self.OK["items"][:3]})                                # too few items
        self.dropped({**self.OK, "items": self.OK["items"] * 4})                                # too many, repeated
        self.dropped({**self.OK, "buckets": ["Rome", "Rome", "Greece"]})                        # repeated bucket
        self.dropped({**self.OK, "items": self.OK["items"][:3] + [["Senate", "Greece"]]})       # repeated text
        self.dropped({**self.OK, "items": "Senate"})


class CauseEffect(HistoryTypeCase):
    OK = {"type": "cause_effect", "chain": ["Drought", "Famine", "Revolt"], "links": ["crops fail", "people rise up"]}

    def test_kept(self):
        c = self.kept(self.OK)
        self.assertEqual(c["chain"], ["Drought", "Famine", "Revolt"])
        self.assertEqual(c["links"], ["crops fail", "people rise up"])
        self.assertEqual(self.kept({**self.OK, "links": ["only one"]})["links"], [])  # wrong length: links ignored

    def test_dropped(self):
        self.dropped({**self.OK, "chain": ["Drought", "Famine", "Drought"]})   # duplicate events
        self.dropped({**self.OK, "chain": ["Drought", "Famine"]})
        self.dropped({**self.OK, "chain": [str(i) for i in range(7)]})
        self.dropped({**self.OK, "chain": ["Drought", "", "Revolt"]})


class SourceAnalysis(HistoryTypeCase):
    Q = {"question": "Who issued it?", "options": ["King John", "Henry VIII"], "answer": "King John"}
    OK = {"type": "source_analysis", "source": {"text": "No free man shall be seized...", "author": "King John", "date": "1215",
                                                "citation": "Magna Carta, clause 39"}, "questions": [Q, {**Q, "answer": 1}]}

    def test_kept(self):
        c = self.kept(self.OK)
        self.assertEqual(c["source"]["citation"], "Magna Carta, clause 39")
        self.assertEqual(c["questions"][1]["answer"], "Henry VIII")  # an index answer becomes the option text
        long = self.kept({**self.OK, "source": {"text": "x" * 5000}, "questions": [self.Q, {"question": "bad", "options": ["a"], "answer": "a"}]})
        self.assertEqual(len(long["source"]["text"]), 1500)
        self.assertEqual(len(long["questions"]), 1)          # the invalid question is left out

    def test_dropped(self):
        self.dropped({**self.OK, "source": {"text": "  ", "author": "x"}})   # no text
        self.dropped({**self.OK, "source": "just a string"})
        self.dropped({**self.OK, "questions": [{**self.Q, "answer": "Edward I"}]})  # no valid question
        self.dropped({**self.OK, "questions": []})


class MapPins(HistoryTypeCase):
    OK = {"type": "map_pins", "map": "europe", "pins": [{"label": "Rome", "x": 0.52, "y": 0.79}, {"label": "Paris", "x": 0.39, "y": 0.6, "tolerance": 0.9}]}

    def test_kept(self):
        c = self.kept(self.OK)
        self.assertEqual(c["pins"][0]["tolerance"], 0.06)
        self.assertEqual(c["pins"][1]["tolerance"], 0.3)  # clamped
        for m in practice_history.MAPS:
            self.kept({**self.OK, "map": m})

    def test_dropped(self):
        self.dropped({**self.OK, "map": "atlantis"})
        self.dropped({**self.OK, "map": "https://example.com/tiles"})
        self.dropped({**self.OK, "pins": [{"label": "Rome", "x": 1.2, "y": 0.5}]})
        self.dropped({**self.OK, "pins": [{"label": "Rome", "x": 0.5, "y": -0.1}]})
        self.dropped({**self.OK, "pins": [{"label": "Rome", "x": "east", "y": 0.5}]})
        self.dropped({**self.OK, "pins": [{"label": f"P{i}", "x": 0.1, "y": 0.1} for i in range(11)]})
        self.dropped({**self.OK, "pins": []})
        self.dropped({**self.OK, "pins": [{"label": "Rome", "x": 0.1, "y": 0.1}, {"label": "Rome", "x": 0.2, "y": 0.2}]})


class WhoAmI(HistoryTypeCase):
    OK = {"type": "who_am_i", "clues": ["I crossed a river", "I was dictator", "I was stabbed in 44 BCE"],
          "answer": "Julius Caesar", "options": ["Julius Caesar", "Augustus", "Pompey"]}

    def test_kept(self):
        self.assertEqual(self.kept({**self.OK, "clues": [f"c{i}" for i in range(9)]})["clues"], [f"c{i}" for i in range(6)])

    def test_dropped(self):
        self.dropped({**self.OK, "answer": "Cicero"})               # answer not in options
        self.dropped({**self.OK, "clues": ["one", "two"]})
        self.dropped({**self.OK, "options": ["Julius Caesar", "Augustus"]})
        self.dropped({**self.OK, "options": ["Julius Caesar", "Augustus", "Augustus"]})


class DateGuess(HistoryTypeCase):
    OK = {"type": "date_guess", "event": "Battle of Actium", "year": -31}

    def test_kept(self):
        c = self.kept(self.OK)
        self.assertEqual((c["year"], c["tolerance"]), (-31, 5))
        self.assertEqual(self.kept({**self.OK, "year": "1066", "tolerance": 0})["year"], 1066)

    def test_dropped(self):
        self.dropped({**self.OK, "year": "long ago"})
        self.dropped({**self.OK, "year": None})
        self.dropped({**self.OK, "year": True})
        self.dropped({**self.OK, "year": float("nan")})
        self.dropped({**self.OK, "event": ""})


class Roleplay(HistoryTypeCase):
    OK = {"type": "roleplay", "persona": "Cicero", "era": "Rome, 63 BCE", "goal": "Why did he oppose Catiline?",
          "opening": "Salve. You find me busy with the Senate."}

    def test_kept(self):
        self.assertEqual(self.kept(self.OK)["persona"], "Cicero")
        self.assertEqual(self.kept({k: v for k, v in self.OK.items() if k not in ("era", "opening")})["opening"], "")

    def test_dropped(self):
        self.dropped({**self.OK, "persona": ""})
        self.dropped({**self.OK, "goal": None})

    def test_prompt_is_required_for_every_type(self):
        self.assertEqual(N([{k: v for k, v in self.OK.items()}]), [])


class Registry(unittest.TestCase):
    def test_every_type_is_registered_with_a_docstring(self):
        self.assertEqual(set(practice_history.NORMALIZERS), {"categorize", "cause_effect", "source_analysis", "map_pins",
                                                             "who_am_i", "date_guess", "roleplay"})
        for name, fn in practice_history.NORMALIZERS.items():
            self.assertIn(name, server.PRACTICE_TYPES)
            self.assertGreater(len(fn.__doc__ or ""), 80, name)

    def test_module_does_not_import_the_server(self):
        src = (ROOT / "practice_history.py").read_text()
        self.assertNotRegex(src, r"^\s*(import|from)\s+server\b")


class OutlineMaps(unittest.TestCase):
    def test_maps_are_small_offline_outlines(self):
        for name in practice_history.MAPS:
            path = ROOT / "public" / "maps" / f"{name}.svg"
            self.assertTrue(path.exists(), name)
            self.assertLess(path.stat().st_size, 150_000, name)
            text = path.read_text()
            self.assertEqual(re.findall(r"https?://[^\"']+", text), ["http://www.w3.org/2000/svg"])  # namespace only
            root = ET.fromstring(text)
            self.assertEqual(len(root.get("viewBox").split()), 4)
            tags = {el.tag.split("}")[-1] for el in root.iter()}
            self.assertLessEqual(tags, {"svg", "rect", "path"}, name)
            lands = [el for el in root.iter() if el.get("class") == "hist-land"]
            self.assertGreaterEqual(len(lands), 3, name)
            for el in lands:
                self.assertRegex(el.get("d"), r"^[MLHVZmlhvz0-9.,\s-]+$")  # what OutlineMap.jsx accepts

    def test_lon_lat_conversion_matches_map_bounds(self):
        x, y = mcp_tools_history.lonlat_to_xy("europe", 12.5, 41.9)   # Rome
        self.assertTrue(0.5 < x < 0.6 and 0.75 < y < 0.85)
        self.assertEqual(mcp_tools_history.lonlat_to_xy("world", -180, 84), (0.0, 0.0))
        for name in practice_history.MAPS:
            svg = (ROOT / "public" / "maps" / f"{name}.svg").read_text()
            lon0, lat0, lon1, lat1 = (float(v) for v in re.search(r'data-bounds="([^"]+)"', svg).group(1).split())
            self.assertEqual(mcp_tools_history.MAP_BOUNDS[name], (lon0, lat0, lon1, lat1))


UNIT = {
    "title": "The Fall of the Roman Republic",
    "intro": "From the Gracchi to Augustus.",
    "events": [
        {"year": -133, "title": "Tiberius Gracchus killed", "detail": "Political violence enters Roman politics."},
        {"year": -88, "title": "Sulla marches on Rome", "why": "Armies loyal to generals, not the state"},
        {"year": -49, "title": "Caesar crosses the Rubicon", "why": "A general defies the Senate"},
        {"year": -44, "title": "Caesar assassinated", "why": "Senators fear a king"},
        {"year": -31, "title": "Battle of Actium", "why": "The heirs fight a civil war", "era": "Late Republic"},
        {"year": 14, "title": "Death of Augustus", "why": "The principate outlives its founder"},
    ],
    "people": [{"name": "Julius Caesar", "role": "General and dictator", "years": "100-44 BCE"},
               {"name": "Cicero", "role": "Orator and consul"}, {"name": "Augustus", "role": "First emperor"}],
    "sources": [{"title": "First Catilinarian", "text": "How long, O Catiline, will you abuse our patience?", "author": "Cicero",
                 "date": "63 BCE", "citation": "In Catilinam 1.1"},
                {"text": "I found Rome a city of bricks.", "author": "Augustus", "date": "14 CE", "citation": "Suetonius, Aug. 28",
                 "questions": [{"question": "What does the claim boast of?", "options": ["Building", "Conquest", "Laws"], "answer": "Building"}]}],
}


class BuildHistoryUnit(unittest.TestCase):
    def test_unit_round_trips_through_the_server_with_nothing_dropped(self):
        built = mcp_tools_history.history_unit_topic(UNIT)
        kinds = [p["type"] for p in built["practice"]]
        self.assertEqual(kinds, ["categorize", "cause_effect", "source_analysis", "source_analysis"])
        self.assertEqual(N(built["practice"]), built["practice"])  # already in the server's clean form
        with TestClient(server.app, base_url=LOCAL) as c:
            r = c.post("/api/topics", json=built)
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(r.json()["warnings"], [])
            t = c.get(f"/api/topics/{built['id']}").json()
        self.assertEqual(t["id"], "the-fall-of-the-roman-republic")
        self.assertEqual(t["practice"], built["practice"])
        self.assertEqual(len(t["timeline"]), len(UNIT["events"]))
        self.assertEqual([e.get("era") for e in t["timeline"]].count("Late Republic"), 1)
        self.assertEqual([c["front"] for c in t["flashcards"]], ["Julius Caesar", "Cicero", "Augustus"])
        self.assertIn("## People", t["markdownContent"])
        chain = next(p for p in t["practice"] if p["type"] == "cause_effect")
        self.assertEqual(len(chain["links"]), len(chain["chain"]) - 1)
        cat = next(p for p in t["practice"] if p["type"] == "categorize")
        self.assertEqual(len(cat["items"]), 6)

    def test_small_unit_still_saves(self):
        built = mcp_tools_history.history_unit_topic({"title": "Two dates", "events": [{"year": 1066, "title": "Hastings"}, {"year": 1215, "title": "Magna Carta"}], "people": []})
        self.assertEqual(built["practice"], [])
        self.assertEqual(built["workspace"], "history")


class HistoryMcpTools(unittest.TestCase):
    NEW = ("add_categorize", "add_cause_effect_chain", "add_source_analysis", "add_map_pins", "add_who_am_i", "add_date_guess",
           "add_roleplay_persona", "build_history_unit", "start_history_activity", "history_overview", "chat_as_figure", "add_timeline_era")
    AGY = ("start_historical_crisis", "add_crisis_scenario", "open_primary_source", "add_primary_source_lab", "start_timeline_challenge")

    def tools(self, sent, reply=None):
        fake = lambda method, path, body=None: sent.append((method, path, body)) or (reply if reply is not None else {"ok": True})
        return {n: fn for n, _, _, fn in mcp_tools_history.tools(fake, mcp_server.q, mcp_server.S, mcp_server.STR, mcp_server.OBJ, mcp_server.ARR)}

    def test_tools_are_listed_with_schemas(self):
        listed = mcp_server.handle({"method": "tools/list", "id": 1})["tools"]
        names = {t["name"]: t for t in listed}
        for n in self.NEW + self.AGY:
            self.assertIn(n, names)
            self.assertEqual(names[n]["inputSchema"]["type"], "object")
        for n in self.NEW:  # unique across every module
            self.assertEqual([t["name"] for t in listed].count(n), 1, n)

    def test_practice_tools_send_items_the_server_keeps(self):
        sent = []
        t = self.tools(sent)
        t["add_categorize"]({"topic_id": "x", "buckets": ["A", "B"], "items": [["a1", "A"], ["b1", "B"], ["a2", "A"], ["b2", "B"]]})
        t["add_cause_effect_chain"]({"topic_id": "x", "chain": ["one", "two", "three"]})
        t["add_source_analysis"]({"topic_id": "x", "source": {"text": "Veni, vidi, vici", "author": "Caesar"},
                                  "questions": [{"question": "Who?", "options": ["Caesar", "Brutus"], "answer": "Caesar"}]})
        t["add_map_pins"]({"topic_id": "x", "map": "mediterranean", "pins": [{"label": "Rome", "lon": 12.5, "lat": 41.9}, {"label": "Carthage", "x": 0.39, "y": 0.6}]})
        t["add_who_am_i"]({"topic_id": "x", "clues": ["a", "b", "c"], "answer": "Hannibal", "options": ["Hannibal", "Scipio", "Fabius"]})
        t["add_date_guess"]({"topic_id": "x", "event": "Cannae", "year": -216})
        t["add_roleplay_persona"]({"topic_id": "x", "persona": "Hannibal", "era": "216 BCE", "goal": "Why not march on Rome?", "opening": "Ask."})
        items = [body["items"][0] for _, path, body in sent]
        self.assertTrue(all(path == "/api/topics/x/practice" for _, path, _ in sent))
        self.assertTrue(all(i["prompt"] for i in items))
        self.assertEqual([p["type"] for p in N(items)], ["categorize", "cause_effect", "source_analysis", "map_pins", "who_am_i", "date_guess", "roleplay"])
        rome = items[3]["pins"][0]
        self.assertTrue(0 < rome["x"] < 1 and 0 < rome["y"] < 1)

    def test_items_reach_a_lesson_through_the_practice_endpoint(self):
        sent = []
        t = self.tools(sent)
        t["add_who_am_i"]({"topic_id": "x", "clues": ["a", "b", "c"], "answer": "Hannibal", "options": ["Hannibal", "Scipio", "Fabius"]})
        t["add_date_guess"]({"topic_id": "x", "event": "Cannae", "year": "not a year"})
        with TestClient(server.app, base_url=LOCAL) as c:
            c.post("/api/topics", json=topic("hist-practice"))
            r = c.post("/api/topics/hist-practice/practice", json={"items": [b["items"][0] for _, _, b in sent]}).json()
            saved = c.get("/api/topics/hist-practice").json()
        self.assertEqual((r["added"], r["rejected"]), (1, 1))
        self.assertEqual([p["type"] for p in saved["practice"]], ["who_am_i"])

    def test_era_tool_adds_tagged_markers(self):
        sent = []
        self.tools(sent)["add_timeline_era"]({"topic_id": "hist-era", "start": -27, "end": -509, "label": "Roman Republic"})
        body = sent[0][2]
        self.assertEqual([e["year"] for e in body["items"]], [-509, -27])
        with TestClient(server.app, base_url=LOCAL) as c:
            c.post("/api/topics", json=topic("hist-era"))
            r = c.post("/api/topics/hist-era/timeline", json=body).json()
            saved = c.get("/api/topics/hist-era").json()
        self.assertEqual(r["added"], 2)
        self.assertEqual({e.get("era") for e in saved["timeline"]}, {"Roman Republic"})

    def test_events_overview_and_persona_chat(self):
        sent = []
        t = self.tools(sent)
        t["start_history_activity"]({"tab": "games"})
        t["chat_as_figure"]({"topic_id": "x", "persona": "Cicero", "message": "Why?"})
        self.assertEqual(sent[0][2], {"type": "SWITCH_STUDIO_MODE", "payload": {"mode": "history", "tab": "games"}})
        self.assertEqual(sent[1][:2], ("POST", "/api/tutor/lesson"))
        self.assertEqual({k: sent[1][2][k] for k in ("topicId", "mode", "persona")}, {"topicId": "x", "mode": "persona", "persona": "Cicero"})
        topics = [{"id": "h", "title": "H", "workspace": "history", "practice": [{"type": "date_guess"}, {"type": "date_guess"}],
                   "timeline": [{"year": -44, "title": "a", "era": "Late Republic"}, {"year": 14, "title": "b"}]},
                  {"id": "p", "title": "P", "workspace": "lab"}]
        out = self.tools([], reply=topics)["history_overview"]({})
        self.assertEqual(len(out["units"]), 1)
        self.assertEqual(out["units"][0]["exercises"], {"date_guess": 2})
        self.assertEqual(out["units"][0]["eras"], ["Late Republic"])
        self.assertEqual(out["span"], ["44 BCE", "14"])
        tabs = next(s for n, _, s, _ in mcp_tools_history.tools(lambda *a: None, mcp_server.q, mcp_server.S, mcp_server.STR, mcp_server.OBJ,
                                                                   mcp_server.ARR) if n == "start_history_activity")
        self.assertEqual(set(tabs["properties"]["tab"]["enum"]), {"map", "sources", "figures", "games", "timeline", "crisis", "cards"})


class PersonaModeHistory(unittest.TestCase):
    def test_roleplay_hist_normalizer_and_registration(self):
        self.assertIn("hist_roleplay", server.PRACTICE_TYPES)
        self.assertIn("roleplay", server.PRACTICE_TYPES)
        self.assertIsNotNone(server._np_roleplay_hist(Roleplay.OK, {**BASE, "type": "hist_roleplay"}))
        self.assertIsNone(server._np_roleplay_hist({"persona": ""}, BASE))
        self.assertIsNone(server._np_roleplay_hist({"persona": "Cicero", "goal": ""}, BASE))

    def test_persona_mode_tutor_stubbed(self):
        seen = {}
        reply_text = "I am Cicero, consul of Rome. Catiline conspired to burn our beloved Republic. What would you have done?"
        self.assertLessEqual(len(reply_text.split()), 120)

        def fake_call(contents, role=None, **kw):
            seen.update(contents=contents, role=role, config=kw.get("config"))
            return SimpleNamespace(text=reply_text)

        with TestClient(server.app, base_url=LOCAL) as c:
            c.post("/api/topics", json=topic("hist-cicero", markdownContent="# Cicero\n\nConsul in 63 BCE.",
                                             timeline=[{"year": -63, "title": "Catilinarian Conspiracy", "era": "Late Republic"}]))
            with mock.patch.object(server, "call_gemini", fake_call):
                r = c.post("/api/tutor/lesson", json={
                    "topicId": "hist-cicero",
                    "mode": "persona",
                    "persona": "Cicero",
                    "era": "Rome, 63 BCE",
                    "message": "Why did you denounce Catiline?",
                    "history": [{"role": "user", "content": "Salve"}]
                })
            self.assertEqual(r.status_code, 200)
            data = r.json()
            self.assertEqual(data["reply"], reply_text)
            self.assertLessEqual(len(data["reply"].split()), 120)
            self.assertTrue(data["reply"].strip().endswith("?"))

            system = seen["config"].system_instruction
            for phrase in ("Cicero", "Rome, 63 BCE", "first person", "Never invent", "120 words"):
                self.assertIn(phrase, system)

            # Persona is required
            r_no_persona = c.post("/api/tutor/lesson", json={"topicId": "hist-cicero", "mode": "persona", "message": "Hi"})
            self.assertEqual(r_no_persona.status_code, 422)


if __name__ == "__main__":
    unittest.main()
