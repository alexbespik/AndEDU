"""Lab, Math and IDE activities (label_diagram, sort_by, odd_one_out, cloze, spot_the_bug), their MCP tools and the
diagram list. Offline: shares test_lab's temporary data folder and its Gemini stub."""
import unittest

from test_lab import LOCAL, TMP, TestClient, server, topic  # noqa: F401  (sets up the temp data dir first)

import mcp_server
import mcp_tools_general
import practice_general

NORM = practice_general.NORMALIZERS
BASE = {"id": "p1", "prompt": "p", "explanation": "", "concept": None}

LABELS = [{"text": "Nucleus", "x": 0.5, "y": 0.47}, {"text": "Membrane", "x": 0.05, "y": 0.5},
          {"text": "Mitochondrion", "x": 0.22, "y": 0.37}]
SPEC = {"width": 200, "height": 100, "shapes": [
    {"kind": "rect", "x": 10, "y": 10, "width": 180, "height": 80, "rx": 6, "tone": "muted"},
    {"kind": "circle", "cx": 100, "cy": 50, "r": 20, "filled": True, "tone": "accent"},
    {"kind": "line", "x1": 0, "y1": 0, "x2": 200, "y2": 100},
    {"kind": "text", "x": 5, "y": 95, "size": 10, "text": "cell"}]}
GOOD = {
    "label_diagram": {"image": "cell.svg", "labels": LABELS},
    "sort_by": {"property": "density", "unit": "g/cm³", "items": [{"text": "water", "value": 1}, {"text": "iron", "value": 7.87},
                                                                  {"text": "cork", "value": 0.24}]},
    "odd_one_out": {"options": ["proton", "neutron", "electron", "photon"], "answer": "photon", "why": "Not in the atom."},
    "cloze": {"text": "Force equals [[mass]] times [[acceleration|a]].", "bank": ["mass", "acceleration", "speed"]},
    "spot_the_bug": {"code": "def area(r):\n    return 3.14 * r * 2\n\nprint(area(2))", "language": "python", "bug_line": 2,
                     "fix": "    return 3.14 * r ** 2"},
}


def setUpModule():
    server.TOPICS_DIR.mkdir(parents=True, exist_ok=True)  # test_lab's tearDownModule may already have removed the temp dir


class Base(unittest.TestCase):
    def one(self, t, **fields):
        """Runs the module normalizer and, once server.py merges the module, server.normalize_practice too."""
        direct = NORM[t]({"type": t, "prompt": "p", **fields}, {**BASE, "type": t})
        if t in server.PRACTICE_NORMALIZERS:
            via = server.normalize_practice([{"type": t, "prompt": "p", **fields}])
            self.assertEqual(bool(via), bool(direct), f"{t}: server and module disagree")
        return direct

    def kept(self, t, **change):
        out = self.one(t, **{k: v for k, v in {**GOOD[t], **change}.items() if v is not ...})
        self.assertIsNotNone(out, f"{t} should be kept: {change}")
        return out

    def dropped(self, t, **change):
        fields = {k: v for k, v in {**GOOD[t], **change}.items() if v is not ...}
        self.assertIsNone(self.one(t, **fields), f"{t} should be dropped: {change}")


class LabelDiagram(Base):
    def test_kept_with_image_or_spec(self):
        out = self.kept("label_diagram")
        self.assertEqual(out["image"], "cell.svg")
        self.assertIsNone(out["svg_spec"])
        self.assertEqual(self.kept("label_diagram", image="/diagrams/atom.svg")["image"], "atom.svg")
        out = self.kept("label_diagram", image=None, svg_spec=SPEC)
        self.assertEqual([s["kind"] for s in out["svg_spec"]["shapes"]], ["rect", "circle", "line", "text"])
        self.assertTrue(out["svg_spec"]["shapes"][1]["filled"])

    def test_spec_keeps_only_whitelisted_attributes(self):
        spec = {**SPEC, "shapes": [{"kind": "rect", "x": 1, "y": 2, "width": 3, "height": 4, "style": "fill:red", "tone": "neon"}]}
        shape = self.kept("label_diagram", image=None, svg_spec=spec)["svg_spec"]["shapes"][0]
        self.assertEqual(shape, {"kind": "rect", "x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0})

    def test_dropped(self):
        self.dropped("label_diagram", image=...)                                   # neither image nor spec
        self.dropped("label_diagram", image="../server.py")
        self.dropped("label_diagram", image="cell.png")
        self.dropped("label_diagram", image="missing-diagram.svg")                 # not in public/diagrams/
        self.dropped("label_diagram", labels=LABELS[:2])
        self.dropped("label_diagram", labels=LABELS * 3)
        self.dropped("label_diagram", labels=[*LABELS[:2], {"text": "x", "x": 1.2, "y": 0.5}])
        self.dropped("label_diagram", labels=[*LABELS[:2], {"text": "x", "x": "0.5", "y": 0.5}])
        self.dropped("label_diagram", labels=[*LABELS[:2], {"text": "x", "x": True, "y": 0.5}])
        self.dropped("label_diagram", labels=[*LABELS[:2], {"text": "Nucleus", "x": 0.1, "y": 0.1}])
        self.dropped("label_diagram", image=None, svg_spec={**SPEC, "shapes": [{"kind": "path", "d": "M0 0"}]})
        self.dropped("label_diagram", image=None, svg_spec={**SPEC, "width": 0})
        self.dropped("label_diagram", image=None, svg_spec={**SPEC, "shapes": [{"kind": "circle", "cx": "1", "cy": 1, "r": 1}]})
        self.dropped("label_diagram", image=None, svg_spec="<svg><circle r='4'/></svg>")  # markup, not data

    def test_svg_spec_injection_is_dropped(self):
        for bad in ({"kind": "text", "x": 1, "y": 1, "text": "<script>alert(1)</script>"},
                    {"kind": "text", "x": 1, "y": 1, "text": "< SCRIPT src=x>"},
                    {"kind": "text", "x": 1, "y": 1, "text": "x\" onload=\"alert(1)"},
                    {"kind": "text", "x": 1, "y": 1, "text": "a onClick = b"},
                    {"kind": "text", "x": 1, "y": 1, "text": "javascript link", "href": "javascript:alert(1)"},
                    {"kind": "rect", "x": 1, "y": 1, "width": 2, "height": 2, "onclick": "alert(1)"},
                    {"kind": "text", "x": 1, "y": 1, "text": "see xlink:HREF"}):
            self.dropped("label_diagram", image=None, svg_spec={**SPEC, "shapes": [*SPEC["shapes"], bad]})
        self.dropped("label_diagram", image=None, svg_spec={**SPEC, "title": {"nested": ["<script>"]}})
        self.dropped("label_diagram", image="onload=x.svg")

    def test_drop_rule_helpers(self):
        self.assertTrue(practice_general.has_unsafe({"a": [{"b": "<script"}]}))
        self.assertTrue(practice_general.has_unsafe({"onmouseover=": 1}))
        self.assertFalse(practice_general.has_unsafe({"text": "one ion", "x": 1}))
        self.assertIsNone(practice_general.clean_svg_spec({**SPEC, "shapes": [SPEC["shapes"][0]] * 61}))


class SortBy(Base):
    def test_kept(self):
        out = self.kept("sort_by")
        self.assertEqual(out["property"], "density")
        self.assertEqual([i["value"] for i in out["items"]], [1.0, 7.87, 0.24])
        self.assertEqual(out["unit"], "g/cm³")

    def test_dropped(self):
        items = GOOD["sort_by"]["items"]
        self.dropped("sort_by", property="")
        self.dropped("sort_by", items=items[:2])
        self.dropped("sort_by", items=items + [{"text": f"x{i}", "value": i + 10} for i in range(5)])
        self.dropped("sort_by", items=[*items[:2], {"text": "lead", "value": "11.3"}])
        self.dropped("sort_by", items=[*items[:2], {"text": "lead", "value": float("nan")}])
        self.dropped("sort_by", items=[*items[:2], {"text": "lead", "value": True}])
        self.dropped("sort_by", items=[*items[:2], {"text": "ice", "value": 1}])        # ties make the order ambiguous
        self.dropped("sort_by", items=[*items[:2], {"text": "water", "value": 3}])


class OddOneOut(Base):
    def test_kept(self):
        out = self.kept("odd_one_out")
        self.assertEqual(out["answer"], "photon")
        self.assertEqual(out["why"], "Not in the atom.")

    def test_dropped(self):
        self.dropped("odd_one_out", answer="quark")
        self.dropped("odd_one_out", options=["proton", "neutron", "photon"])
        self.dropped("odd_one_out", options=["proton", "neutron", "electron", "photon", "quark"])
        self.dropped("odd_one_out", options=["proton", "proton", "electron", "photon"])
        self.dropped("odd_one_out", options=["proton", "", "electron", "photon"])
        self.dropped("odd_one_out", options="proton, neutron, electron, photon")


class Cloze(Base):
    def test_kept(self):
        out = self.kept("cloze")
        self.assertEqual(out["gaps"], [["mass"], ["acceleration", "a"]])
        self.assertEqual(out["bank"], ["mass", "acceleration", "speed"])
        self.assertEqual(self.kept("cloze", bank=...)["bank"], [])

    def test_dropped(self):
        self.dropped("cloze", text="No gaps at all.")
        self.dropped("cloze", text=" ".join(f"[[w{i}]]" for i in range(7)), bank=...)
        self.dropped("cloze", text="An [[]] empty gap.", bank=...)
        self.dropped("cloze", text="An [[ | ]] empty gap.", bank=...)
        self.dropped("cloze", text="Unclosed [[mass gap.", bank=...)
        self.dropped("cloze", text="Nested [[a [[b]] c]].", bank=...)
        self.dropped("cloze", bank=["mass", "speed"])                           # the bank misses a gap's answer
        self.dropped("cloze", text=None)


class SpotTheBug(Base):
    def test_kept(self):
        out = self.kept("spot_the_bug")
        self.assertEqual((out["bug_line"], out["language"], out["fix"]), (2, "python", "    return 3.14 * r ** 2"))
        self.assertEqual(self.kept("spot_the_bug", language=..., fix=...)["fix"], "")

    def test_dropped(self):
        self.dropped("spot_the_bug", bug_line=0)
        self.dropped("spot_the_bug", bug_line=5)                                # the code has 4 lines
        self.dropped("spot_the_bug", bug_line=3)                                # a blank line
        self.dropped("spot_the_bug", bug_line="2")
        self.dropped("spot_the_bug", bug_line=True)
        self.dropped("spot_the_bug", language="javascript")
        self.dropped("spot_the_bug", code="")
        self.dropped("spot_the_bug", fix="a\nb")


class Guide(unittest.TestCase):
    def test_every_normalizer_documents_its_drop_rules(self):
        self.assertEqual(set(NORM), {"label_diagram", "sort_by", "odd_one_out", "cloze", "spot_the_bug"})
        for t, fn in NORM.items():
            self.assertIn(t, fn.__doc__)
            self.assertIn("Dropped when", fn.__doc__)

    def test_endpoints(self):
        if "label_diagram" not in server.PRACTICE_NORMALIZERS:
            self.skipTest("server.py has not merged practice_general yet")
        with TestClient(server.app, base_url=LOCAL) as c:
            guide = c.get("/api/practice/guide").json()
            for t in NORM:
                self.assertIn("Dropped when", guide[t])
            names = c.get("/api/diagrams").json()["diagrams"]
            self.assertTrue({"cell.svg", "circuit.svg", "atom.svg"} <= set(names))
            self.assertEqual(c.get("/api/diagrams", params={"name": "../server.py"}).status_code, 400)
            server.save_topic(topic("general-acts"), auto_select=False)
            r = c.post("/api/topics/general-acts/practice", json={"items": [{"type": t, "prompt": "p", **f} for t, f in GOOD.items()]
                                                                  + [{"type": "cloze", "prompt": "p", "text": "none"}]}).json()
            self.assertEqual((r["added"], r["rejected"]), (5, 1))


class GeneralMcpTools(unittest.TestCase):
    NAMES = ("add_label_diagram", "add_sort_by", "add_odd_one_out", "add_cloze", "add_spot_the_bug",
             "list_diagram_images", "practice_type_guide")

    def tools(self, sent):
        fake = lambda method, path, body=None: sent.append((method, path, body)) or {"ok": True}
        return {n: fn for n, _, _, fn in mcp_tools_general.tools(fake, mcp_server.q, mcp_server.S, mcp_server.STR, mcp_server.OBJ, mcp_server.ARR)}

    def test_tools_are_listed_once(self):
        names = [t["name"] for t in mcp_server.handle({"method": "tools/list", "id": 1})["tools"]]
        for n in self.NAMES:
            self.assertEqual(names.count(n), 1, n)
        self.assertEqual(len(self.tools([])), 7)

    def test_tool_calls_build_items_the_normalizers_keep(self):
        sent = []
        t = self.tools(sent)
        t["add_label_diagram"]({"topic_id": "a b", "image": "cell.svg", "labels": LABELS})
        t["add_label_diagram"]({"topic_id": "t", "svg_spec": SPEC, "labels": LABELS})
        t["add_sort_by"]({"topic_id": "t", **GOOD["sort_by"]})
        t["add_odd_one_out"]({"topic_id": "t", **GOOD["odd_one_out"]})
        t["add_cloze"]({"topic_id": "t", **GOOD["cloze"]})
        t["add_spot_the_bug"]({"topic_id": "t", "code": GOOD["spot_the_bug"]["code"], "bug_line": 2})
        t["list_diagram_images"]({})
        t["practice_type_guide"]({})
        self.assertEqual(sent[0][1], "/api/topics/a%20b/practice")
        for method, _, body in sent[:6]:
            self.assertEqual(method, "POST")
            it = body["items"][0]
            self.assertTrue(it["prompt"])
            self.assertIsNotNone(NORM[it["type"]](it, {**BASE, "type": it["type"]}), it)
        self.assertEqual([(m, p) for m, p, _ in sent[6:]], [("GET", "/api/diagrams"), ("GET", "/api/practice/guide")])


if __name__ == "__main__":
    unittest.main()
