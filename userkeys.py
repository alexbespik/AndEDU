"""
Accounts on this computer (docs/plans/ACCOUNTS.md): password hashes that also yield a key-encryption key, each
account's Gemini key sealed with AES-256-GCM, the keys unlocked in this process, and the check of a new key with
Google before it is saved.

- `scrypt2$<n>$<r>$<p>$<salt hex>$<verifier hex>`: one scrypt run (dklen 32), then HKDF-SHA256 with info b"verifier"
  (stored) and b"kek" (never stored: it seals the account's secrets in password mode).
- Password mode: the KEK from the password. Device mode (accounts without a password): DEVICE_KEY, a 32-byte key the
  desktop app keeps in the OS keychain; None until the app hands it over, and then device mode refuses.
- The AAD binds each sealed secret to its row: f"{user_id}|{kind}|{mode}".
"""
import hashlib
import hmac
import os
import re
import secrets
import threading
from typing import Any, Dict, Optional, Tuple

import httpx
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

SCRYPT_N = 2 ** 17      # tests lower it; stored hashes carry their own n, r, p
SCRYPT_R, SCRYPT_P = 8, 1
SCRYPT_MAXMEM = 2 ** 28  # n=2^17, r=8 needs 128 MiB; hashlib's default cap is 32 MiB
_derivations = threading.BoundedSemaphore(2)  # at most two 128 MiB derivations at once

DEVICE_KEY: Optional[bytes] = None  # set by the desktop app (phase 4); None: no device-mode secrets
# user id -> {"key": Gemini key or None, "kek": bytes or None, "unlocked_at": float, "last_active": float}
UNLOCKED: Dict[str, Dict[str, Any]] = {}

# Google's answer when the key itself is wrong, revoked or lacks the Gemini API. server._is_bad_key reads errors
# mid-run with the same expressions, classify_key_response reads the test request made before a key is saved.
BAD_KEY_RE = re.compile(r"api_key_invalid|api key not valid", re.I)
REVOKED_KEY_RE = re.compile(r"leaked|suspended", re.I)
API_DISABLED_RE = re.compile(r"service_disabled|has not been used in project", re.I)
_DISABLED_ANSWER_RE = re.compile(API_DISABLED_RE.pattern + r"|is disabled", re.I)

KEY_CHECK_URL = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1"


class KeyUnavailable(Exception):
    """The key that seals this secret is not here (no password KEK, or no device key on this computer)."""


class KeyUnreadable(Exception):
    """The sealed secret does not open with this key (wrong key, another row's data, or damaged)."""


# ---- password hashes ----
def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    with _derivations:
        return hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32, maxmem=SCRYPT_MAXMEM)


def _hkdf(master: bytes, info: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(master)


def hash_password(password: str) -> Tuple[str, bytes]:
    """A new scrypt2 hash and the KEK that goes with it."""
    salt = secrets.token_bytes(16)
    master = _scrypt(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    verifier = _hkdf(master, b"verifier")
    return f"scrypt2${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${verifier.hex()}", _hkdf(master, b"kek")


def verify_password(password: str, stored: Optional[str]) -> Optional[bytes]:
    """The KEK when the password matches a scrypt2 hash, else None."""
    try:
        scheme, n, r, p, salt_hex, verifier_hex = (stored or "").split("$")
        n, r, p, salt = int(n), int(r), int(p), bytes.fromhex(salt_hex)
    except ValueError:
        return None
    if scheme != "scrypt2" or not (2 <= n <= 2 ** 20 and 1 <= r <= 16 and 1 <= p <= 4):
        return None
    try:
        master = _scrypt(password, salt, n, r, p)
    except ValueError:  # parameters over SCRYPT_MAXMEM
        return None
    if not hmac.compare_digest(_hkdf(master, b"verifier").hex(), verifier_hex):
        return None
    return _hkdf(master, b"kek")


# ---- sealed secrets ----
def _sealing_key(mode: str, kek: Optional[bytes]) -> bytes:
    if mode == "password":
        key = kek
    elif mode == "device":
        key = DEVICE_KEY
    else:
        raise ValueError(f"unknown secret mode: {mode!r}")
    if not key:
        raise KeyUnavailable(mode)
    return key


def _aad(user_id: str, kind: str, mode: str) -> bytes:
    return f"{user_id}|{kind}|{mode}".encode()


def wrap(secret: str, user_id: str, kind: str, mode: str, kek: Optional[bytes] = None) -> Tuple[bytes, bytes]:
    """(nonce, ciphertext) of the secret, sealed with the KEK (password mode) or DEVICE_KEY (device mode)."""
    key = _sealing_key(mode, kek)
    nonce = os.urandom(12)
    return nonce, AESGCM(key).encrypt(nonce, secret.encode(), _aad(user_id, kind, mode))


def unwrap(nonce: bytes, ciphertext: bytes, user_id: str, kind: str, mode: str, kek: Optional[bytes] = None) -> str:
    key = _sealing_key(mode, kek)
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, _aad(user_id, kind, mode)).decode()
    except (InvalidTag, UnicodeDecodeError) as e:
        raise KeyUnreadable(mode) from e


# ---- Gemini key check ----
def is_bad_key_text(text: str, code: Any = None) -> bool:
    """server._is_bad_key: a model error that means the key is wrong, revoked or lacks the Gemini API."""
    return bool(BAD_KEY_RE.search(text)) or (code == 403 and bool(REVOKED_KEY_RE.search(text) or API_DISABLED_RE.search(text)))


def classify_key_response(status: int, body: Any) -> str:
    """Google's answer to GET /v1beta/models made with a key: 'ok', 'invalid' (wrong, revoked or leaked),
    'service_disabled' (the key's project lacks the Gemini API) or 'unverified' (quota, server trouble, anything
    unclear: the key is saved unverified)."""
    text = str(body or "")
    if status == 200:
        return "ok"
    if status in (400, 401) and BAD_KEY_RE.search(text):
        return "invalid"
    if status == 401:
        return "invalid"
    if status == 403 and (REVOKED_KEY_RE.search(text) or BAD_KEY_RE.search(text)):
        return "invalid"
    if status == 403 and _DISABLED_ANSWER_RE.search(text):
        return "service_disabled"
    return "unverified"


def check_key(key: str) -> str:
    """Asks Google whether this key works (one list-models request, 8 s). Nothing about the key is logged."""
    try:
        r = httpx.get(KEY_CHECK_URL, headers={"x-goog-api-key": key}, timeout=8.0)
    except Exception:
        return "unverified"  # offline or timed out: save it unverified, the first real call tells
    return classify_key_response(r.status_code, r.text)
