"""The test suite never reaches the internet (test_lab blocks outbound connections)."""
from test_lab import LOCAL, TestClient, server  # noqa: F401  (installs the network block first)

import socket
import unittest


class OfflineTests(unittest.TestCase):
    def test_outbound_connections_are_blocked(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            with self.assertRaisesRegex(OSError, "tests run offline"):
                s.connect(("93.184.215.14", 443))

    def test_loopback_stays_open(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", 0))
            except OSError:
                self.skipTest("this sandbox does not allow local port binding")
            s.listen(1)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as c:
                c.connect(s.getsockname())  # must not raise "tests run offline"


if __name__ == "__main__":
    unittest.main()
