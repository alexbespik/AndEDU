"""src/lib/workspaces.js (the browser's list of kit and subject workspaces) must match server.WORKSPACES.
The arrays in workspaces.js are plain literals so this test can read them without a JS runtime."""
import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from test_lab import server  # noqa: E402

# Workspaces that are not "subject" tabs of the Liberal arts group: Math lab, the IDE and Lab each have their own tab.
OWN_TAB_MODES = {"math", "code", "lab"}


def js_array(name: str) -> list:
    src = (ROOT / "src" / "lib" / "workspaces.js").read_text(encoding="utf-8")
    m = re.search(rf"export\s+const\s+{name}\s*=\s*\[(.*?)\]", src, re.S)
    assert m, f"{name} is not an array literal in src/lib/workspaces.js"
    return re.findall(r"""['"]([a-z_]+)['"]""", m.group(1))


class WorkspaceParity(unittest.TestCase):
    def test_kit_and_subject_modes_are_server_workspaces(self):
        kit, subject = js_array("KIT_MODES"), js_array("SUBJECT_MODES")
        self.assertEqual(len(kit), len(set(kit)))
        self.assertEqual(len(subject), len(set(subject)))
        self.assertTrue(set(kit) <= set(subject), "every kit mode is also a subject mode")
        self.assertTrue(set(subject) <= set(server.WORKSPACES), f"unknown to the server: {set(subject) - set(server.WORKSPACES)}")

    def test_every_server_workspace_is_listed_once(self):
        subject = set(js_array("SUBJECT_MODES"))
        self.assertEqual(set(server.WORKSPACES), subject | OWN_TAB_MODES,
                         "a workspace the server knows is missing from workspaces.js (or the reverse)")

    def test_kit_modes_are_the_six_liberal_arts_kits(self):
        self.assertEqual(set(js_array("KIT_MODES")), {"literature", "music", "art_history", "classics", "rhetoric", "polity"})


if __name__ == "__main__":
    unittest.main()
