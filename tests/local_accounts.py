"""Test helpers for accounts on this computer (SCIEDU_LOCAL_ACCOUNTS, docs/plans/ACCOUNTS.md).

Local sign-in does not exist yet, so accounts and sessions are made directly with the db helpers the server's own
sign-in uses (get_or_create_user, set_consent, create_session)."""
import unittest

from test_lab import server, db  # noqa: F401  (sets up the temp content dir first)


def local_account(name):
    """A name-only profile with a session: (Authorization headers, user id)."""
    user = db.get_or_create_user(name)
    db.set_consent(user["id"], "privacy", server.PRIVACY_VERSION)
    return {"Authorization": f"Bearer {db.create_session(user['id'])}"}, user["id"]


class LocalAccountsMixin:
    """Runs a test case with local accounts on and server accounts off; restores both flags afterwards.
    Goes before the TestCase in the bases, so a server-mode case's setUp (which turns AUTH_REQUIRED on) is undone."""
    def setUp(self):
        self._account_flags = (server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS)
        server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS = False, True
        super().setUp()
        server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS = False, True

    def tearDown(self):
        try:
            super().tearDown()
        finally:
            server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS = self._account_flags


class BothFlagsMixin:
    """Runs a server-mode test case with SCIEDU_LOCAL_ACCOUNTS set as well: server accounts must win."""
    def setUp(self):
        self._account_flags = (server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS)
        server.LOCAL_ACCOUNTS = True
        super().setUp()

    def tearDown(self):
        try:
            super().tearDown()
        finally:
            server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS = self._account_flags


class LocalAccountsCase(LocalAccountsMixin, unittest.TestCase):
    pass
