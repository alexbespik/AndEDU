"""POST /api/client-errors: crash reports from the browser's ErrorBoundary, kept in logs/client_errors.log."""
from test_lab import LOCAL, server  # noqa: E402  (sets up the temporary data folder and the offline guard)

import json  # noqa: E402
import unittest  # noqa: E402
from unittest import mock  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

LOG = server.CONTENT_DIR / "logs" / "client_errors.log"


class ClientErrors(unittest.TestCase):
    def setUp(self):
        server._rate_hits.clear()
        LOG.unlink(missing_ok=True)
        self.ctx = TestClient(server.app, base_url=LOCAL)
        self.c = self.ctx.__enter__()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)
        server._rate_hits.clear()

    def entries(self):
        return [json.loads(line) for line in LOG.read_text(encoding="utf-8").splitlines()]

    def test_report_is_cleaned_cut_and_logged(self):
        r = self.c.post("/api/client-errors", json={"view": "campus", "message": "boom\x00\x1b[31m" + "x" * 900,
                                                     "stack": "s" * 9000, "path": "/#a\nb"})
        self.assertEqual(r.status_code, 200)
        [e] = self.entries()
        self.assertEqual(e["view"], "campus")
        self.assertEqual(len(e["message"]), 500)
        self.assertTrue(e["message"].startswith("boom  [31m"))
        self.assertEqual(len(e["stack"]), 4000)
        self.assertEqual(e["path"], "/#a b")

    def test_log_is_trimmed_past_the_limit(self):
        with mock.patch.object(server, "CLIENT_ERROR_LOG_BYTES", 4000):
            for i in range(20):
                self.c.post("/api/client-errors", json={"view": "v", "message": f"m{i}", "stack": "s" * 300})
        self.assertLessEqual(LOG.stat().st_size, 4000)
        rows = self.entries()  # every remaining line is whole JSON, the newest kept
        self.assertEqual(rows[-1]["message"], "m19")

    def test_rate_limited(self):
        with mock.patch.dict(server.RATE_LIMITS, {"client_error": 2}):
            codes = [self.c.post("/api/client-errors", json={"message": str(i)}).status_code for i in range(3)]
        self.assertEqual(codes, [200, 200, 429])


if __name__ == "__main__":
    unittest.main()
