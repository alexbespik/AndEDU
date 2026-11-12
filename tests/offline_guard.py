"""Imported first by the test modules: no test may reach the internet (Gemini, ElevenLabs, PATH...), so a missed
mock fails loudly instead of spending credits. Loopback and Unix sockets stay open for the code sandbox and
local servers."""
import socket

_real_connect = socket.socket.connect


def _offline_connect(self, address, *args, **kwargs):
    if self.family in (socket.AF_INET, socket.AF_INET6) and address[0] not in ("127.0.0.1", "::1", "localhost"):
        raise OSError(f"tests run offline: blocked a connection to {address[0]}")
    return _real_connect(self, address, *args, **kwargs)


if socket.socket.connect is not _offline_connect:
    socket.socket.connect = _offline_connect
