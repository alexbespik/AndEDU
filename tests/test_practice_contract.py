"""Every practice type the server accepts must have a renderer in the browser: a key of a *_RENDER map in
src/practice/*.jsx or of the RENDER map in PracticeDeck.jsx. A missing renderer means the exercise would be saved
and then silently hidden from the student. The allowlist below names every exception with its reason; fix the
renderer instead of widening it."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from test_lab import server  # noqa: E402

# type -> reason it has no renderer of its own
ALLOWLIST: dict = {}  # empty today: every type renders. Add "type": "reason" only for a type that truly cannot.


def _top_level_keys(body: str) -> set:
    """Keys of an object literal body: split on commas at depth 0, take the text before ':' (or the shorthand name)."""
    keys, depth, cur = set(), 0, []
    parts = []
    for ch in body:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    for part in parts:
        part = re.sub(r"//[^\n]*", "", part).strip()
        if not part or part.startswith("..."):
            continue
        m = re.match(r"""^['"]?([A-Za-z_][A-Za-z0-9_]*)['"]?\s*(?::|$)""", part)
        if m:
            keys.add(m.group(1))
    return keys


def _object_body(src: str, start: int) -> str:
    depth, i = 0, src.index("{", start)
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i + 1:j]
    raise AssertionError("unbalanced braces")


def renderer_keys() -> set:
    keys = set()
    for f in sorted((ROOT / "src" / "practice").glob("*.jsx")):
        src = f.read_text(encoding="utf-8")
        for m in re.finditer(r"export\s+const\s+[A-Z_]*RENDER\s*=\s*\{", src):
            keys |= _top_level_keys(_object_body(src, m.start()))
    deck = (ROOT / "src" / "components" / "PracticeDeck.jsx").read_text(encoding="utf-8")
    m = re.search(r"const\s+RENDER\s*=\s*\{", deck)
    assert m, "PracticeDeck.jsx no longer has a RENDER map"
    keys |= _top_level_keys(_object_body(deck, m.start()))
    return keys


class PracticeContract(unittest.TestCase):
    def test_every_practice_type_has_a_renderer(self):
        have = renderer_keys()
        missing = sorted(t for t in server.PRACTICE_TYPES if t not in have and t not in ALLOWLIST)
        self.assertEqual(missing, [], f"practice types with no renderer in src/practice/*.jsx or PracticeDeck RENDER: {missing}")

    def test_allowlist_has_no_stale_entries(self):
        have = renderer_keys()
        for t in ALLOWLIST:
            self.assertIn(t, server.PRACTICE_TYPES, f"{t} is allowlisted but the server no longer has it")
            self.assertNotIn(t, have, f"{t} now has a renderer: remove it from the allowlist")

    def test_every_server_graded_type_has_a_renderer(self):
        have = renderer_keys()
        self.assertEqual(sorted(t for t in server.PRACTICE_GRADERS if t not in have), [])


if __name__ == "__main__":
    unittest.main()
