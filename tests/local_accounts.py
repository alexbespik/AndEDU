"""Test helpers for accounts on this computer (SCIEDU_LOCAL_ACCOUNTS, docs/plans/ACCOUNTS.md).

local_account() makes a name-only account and its session directly with the db helpers; the sign-in endpoints have
their own tests in test_local_accounts.py."""
import os
import unittest
from unittest import mock

from test_lab import server, db  # noqa: F401  (sets up the temp content dir first)
import userkeys

TEST_SCRYPT_N = 2 ** 10  # the real 2^17 takes 128 MiB and a good part of a second per derivation


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
        self._key_state = (userkeys.SCRYPT_N, userkeys.DEVICE_KEY, dict(userkeys.UNLOCKED), dict(server._login_failures),
                           userkeys.client_factory, dict(userkeys.HANDLES), dict(userkeys.KEY_STATE), userkeys.LEGACY_KEY)
        server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS = False, True
        userkeys.SCRYPT_N, userkeys.DEVICE_KEY, userkeys.LEGACY_KEY = TEST_SCRYPT_N, os.urandom(32), None
        for held in (userkeys.UNLOCKED, userkeys.HANDLES, userkeys.KEY_STATE):
            held.clear()
        server._login_failures.clear()
        self._legacy = dict(server._legacy)
        server._legacy.update(busy=False, admin_wait_over=False)
        # check_key swallows network errors ("unverified"), so the offline guard alone would not catch a missed mock
        self._no_key_check = mock.patch.object(userkeys, "check_key", side_effect=AssertionError("mock userkeys.check_key"))
        self._no_key_check.start()
        super().setUp()
        server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS = False, True

    def tearDown(self):
        try:
            super().tearDown()
        finally:
            self._no_key_check.stop()
            server.AUTH_REQUIRED, server.LOCAL_ACCOUNTS = self._account_flags
            (userkeys.SCRYPT_N, userkeys.DEVICE_KEY, unlocked, failures, userkeys.client_factory, handles, states,
             userkeys.LEGACY_KEY) = self._key_state
            for held, saved in ((userkeys.UNLOCKED, unlocked), (userkeys.HANDLES, handles), (userkeys.KEY_STATE, states)):
                held.clear()
                held.update(saved)
            server._login_failures.clear()
            server._login_failures.update(failures)
            server._legacy.clear()
            server._legacy.update(self._legacy)


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
