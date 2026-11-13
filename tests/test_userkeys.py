"""userkeys.py: scrypt2 hashes with a KEK, sealed secrets (password and device mode), and the Gemini key check
(the same verdicts as desktop/keycheck.cjs, the sample answers of desktop/keycheck.test.cjs)."""
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import offline_guard  # noqa: E402,F401  (no test may reach the internet)
import userkeys  # noqa: E402

INVALID = '{"error":{"code":400,"message":"API key not valid. Please pass a valid API key.","status":"INVALID_ARGUMENT","details":[{"reason":"API_KEY_INVALID"}]}}'
LEAKED = '{"error":{"code":403,"message":"Your API key was reported as leaked. Please use another API key.","status":"PERMISSION_DENIED"}}'
DISABLED = '{"error":{"code":403,"message":"Generative Language API has not been used in project 123 before or it is disabled.","status":"PERMISSION_DENIED","details":[{"reason":"SERVICE_DISABLED"}]}}'
QUOTA = '{"error":{"code":429,"message":"Resource has been exhausted (e.g. check quota).","status":"RESOURCE_EXHAUSTED"}}'
PLAIN_400 = '{"error":{"code":400,"message":"Invalid JSON payload received.","status":"INVALID_ARGUMENT"}}'
REGION = '{"error":{"code":403,"message":"User location is not supported for the API use.","status":"PERMISSION_DENIED"}}'


class KeyStore(unittest.TestCase):
    def setUp(self):
        self.old = (userkeys.SCRYPT_N, userkeys.DEVICE_KEY)
        userkeys.SCRYPT_N, userkeys.DEVICE_KEY = 2 ** 10, os.urandom(32)

    def tearDown(self):
        userkeys.SCRYPT_N, userkeys.DEVICE_KEY = self.old

    def test_hash_format_and_round_trip(self):
        stored, kek = userkeys.hash_password("correct horse")
        scheme, n, r, p, salt, verifier = stored.split("$")
        self.assertEqual((scheme, n, r, p), ("scrypt2", "1024", "8", "1"))
        self.assertEqual((len(salt), len(verifier), len(kek)), (32, 64, 32))
        self.assertNotIn(kek.hex(), stored)  # the KEK is never stored
        self.assertEqual(userkeys.verify_password("correct horse", stored), kek)
        nonce, ct = userkeys.wrap("AIza-secret", "u-1", "gemini", "password", kek)
        self.assertNotIn(b"AIza-secret", ct)
        self.assertEqual(userkeys.unwrap(nonce, ct, "u-1", "gemini", "password", kek), "AIza-secret")

    def test_stored_hash_keeps_its_own_cost(self):
        stored, kek = userkeys.hash_password("correct horse")
        userkeys.SCRYPT_N = 2 ** 11
        self.assertEqual(userkeys.verify_password("correct horse", stored), kek)

    def test_wrong_password(self):
        stored, kek = userkeys.hash_password("correct horse")
        self.assertIsNone(userkeys.verify_password("wrong horse", stored))
        nonce, ct = userkeys.wrap("AIza-secret", "u-1", "gemini", "password", kek)
        _, other = userkeys.hash_password("wrong horse")
        with self.assertRaises(userkeys.KeyUnreadable):
            userkeys.unwrap(nonce, ct, "u-1", "gemini", "password", other)

    def test_broken_or_foreign_hashes_never_match(self):
        for stored in (None, "", "scrypt$aa$bb", "scrypt2$x$8$1$aa$bb", "scrypt2$1024$8$1$zz$bb",
                       "scrypt2$4194304$8$1$" + "00" * 16 + "$" + "00" * 32):
            self.assertIsNone(userkeys.verify_password("pw", stored), stored)

    def test_aad_binds_the_secret_to_its_row(self):
        _, kek = userkeys.hash_password("correct horse")
        nonce, ct = userkeys.wrap("AIza-secret", "u-1", "gemini", "password", kek)
        for user_id, kind in (("u-2", "gemini"), ("u-1", "other")):
            with self.assertRaises(userkeys.KeyUnreadable):
                userkeys.unwrap(nonce, ct, user_id, kind, "password", kek)
        dn, dct = userkeys.wrap("AIza-secret", "u-1", "gemini", "device")
        with self.assertRaises(userkeys.KeyUnreadable):  # same bytes as the device key, other mode in the AAD
            userkeys.unwrap(dn, dct, "u-1", "gemini", "password", userkeys.DEVICE_KEY)

    def test_device_mode(self):
        nonce, ct = userkeys.wrap("AIza-secret", "u-1", "gemini", "device")
        self.assertEqual(userkeys.unwrap(nonce, ct, "u-1", "gemini", "device"), "AIza-secret")
        userkeys.DEVICE_KEY = os.urandom(32)
        with self.assertRaises(userkeys.KeyUnreadable):
            userkeys.unwrap(nonce, ct, "u-1", "gemini", "device")

    def test_device_mode_refuses_without_a_device_key(self):
        nonce, ct = userkeys.wrap("AIza-secret", "u-1", "gemini", "device")
        userkeys.DEVICE_KEY = None
        with self.assertRaises(userkeys.KeyUnavailable):
            userkeys.wrap("AIza-secret", "u-1", "gemini", "device")
        with self.assertRaises(userkeys.KeyUnavailable):
            userkeys.unwrap(nonce, ct, "u-1", "gemini", "device")
        with self.assertRaises(userkeys.KeyUnavailable):  # password mode without a KEK refuses too
            userkeys.wrap("AIza-secret", "u-1", "gemini", "password", None)

    def test_derivations_go_through_the_bounded_semaphore(self):
        self.assertIsInstance(userkeys._derivations, type(__import__("threading").BoundedSemaphore(2)))
        self.assertEqual(userkeys._derivations._initial_value, 2)
        with mock.patch.object(userkeys.hashlib, "scrypt", wraps=userkeys.hashlib.scrypt) as scrypt:
            userkeys.hash_password("correct horse")
        self.assertEqual(scrypt.call_args.kwargs["maxmem"], 2 ** 28)


class KeyCheck(unittest.TestCase):
    """The cases of desktop/keycheck.test.cjs, with this module's verdict names."""
    def test_classify_key_response(self):
        cases = [(200, '{"models":[]}', "ok"), (400, INVALID, "invalid"), (403, LEAKED, "invalid"),
                 (403, DISABLED, "service_disabled"), (429, QUOTA, "unverified"), (400, PLAIN_400, "unverified"),
                 (403, REGION, "unverified"), (503, "", "unverified"), (0, None, "unverified"), (401, "", "invalid")]
        for status, body, verdict in cases:
            with self.subTest(status=status, body=body):
                self.assertEqual(userkeys.classify_key_response(status, body), verdict)

    def test_check_key_sends_the_key_in_a_header_only(self):
        with mock.patch.object(userkeys.httpx, "get", return_value=SimpleNamespace(status_code=400, text=INVALID)) as get:
            self.assertEqual(userkeys.check_key("AIza-test-key"), "invalid")
        url = get.call_args.args[0]
        self.assertEqual(url, "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1")
        self.assertNotIn("AIza", url)
        self.assertEqual(get.call_args.kwargs["headers"], {"x-goog-api-key": "AIza-test-key"})
        self.assertEqual(get.call_args.kwargs["timeout"], 8.0)

    def test_check_key_offline_is_unverified(self):
        # a failed connection reads as "could not check", never as a bad key
        for err in (userkeys.httpx.ConnectError("offline"), userkeys.httpx.ReadTimeout("slow")):
            with mock.patch.object(userkeys.httpx, "get", side_effect=err):
                self.assertEqual(userkeys.check_key("AIza-test-key"), "unverified")

    def test_bad_key_text_matches_the_server_rule(self):
        self.assertTrue(userkeys.is_bad_key_text("400 API_KEY_INVALID"))
        self.assertTrue(userkeys.is_bad_key_text("API key not valid"))
        self.assertTrue(userkeys.is_bad_key_text(LEAKED, 403))
        self.assertTrue(userkeys.is_bad_key_text(DISABLED, 403))
        self.assertFalse(userkeys.is_bad_key_text(LEAKED, 400))  # leaked/disabled text counts only with a 403
        self.assertFalse(userkeys.is_bad_key_text(QUOTA, 429))


if __name__ == "__main__":
    unittest.main()
