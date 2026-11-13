"""
Accounts on this computer (docs/plans/ACCOUNTS.md): password hashes that also yield a key-encryption key, each
account's Gemini key sealed with AES-256-GCM, the keys unlocked in this process, and the check of a new key with
Google before it is saved.

- `scrypt2$<n>$<r>$<p>$<salt hex>$<verifier hex>`: one scrypt run (dklen 32), then HKDF-SHA256 with info b"verifier"
  (stored) and b"kek" (never stored: it seals the account's secrets in password mode).
- Password mode: the KEK from the password. Device mode (accounts without a password): DEVICE_KEY, a 32-byte key the
  desktop app keeps in the OS keychain; None until the app hands it over, and then device mode refuses.
- The AAD binds each sealed secret to its row: f"{user_id}|{kind}|{mode}".
- Each unlocked key gets a KeyHandle (its own Gemini client) and per-key model state in KEY_STATE (cooldowns, grounding
  pause, invalid flag, daily budget). A job keeps the handle of whoever started it (its lease, in ACTIVE_KEY), so a job
  running when its account locks or signs out finishes on that key within KEY_LEASE_GRACE_S. Deleting the key or the
  account stops it at the next call (a hard revoke).
"""
import contextvars
import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

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


KEY_LEASE_GRACE_S = 1800  # a job may finish on a locked account's key for this long after the lock


class NoGeminiKey(Exception):
    """The signed-in account (or the job's owner) has no Gemini key unlocked here."""


class KeyLocked(Exception):
    """The job's account locked longer than KEY_LEASE_GRACE_S ago: its key is gone until it signs in again."""


KEY_ERRORS = (NoGeminiKey, KeyLocked)  # model calls that could not start: the API answers them with a `code`


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


# ---- unlocked keys: handles, per-key state, leases ----
@dataclass(eq=False)
class KeyHandle:
    user_id: Optional[str]
    key_id: str  # sha256(key)[:16]: names the key's state without keeping the key itself here
    client: Any
    revoked_at: Optional[float] = None
    hard: bool = False  # revoked because the key or the account was deleted: no grace


client_factory: Optional[Callable[[str], Any]] = None  # key -> Gemini client; server sets it, tests inject fakes
HANDLES: Dict[str, KeyHandle] = {}  # user id -> handle of the key in UNLOCKED[user id]["key"]
KEY_STATE: Dict[str, Dict[str, Any]] = {}  # key id -> {cooldown{}, grounding_paused_until, invalid, budget{day, used}}
ACTIVE_KEY: "contextvars.ContextVar[Optional[KeyHandle]]" = contextvars.ContextVar("active_key", default=None)
_handles_lock = threading.Lock()


def key_id(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def key_state(kid: str) -> Dict[str, Any]:
    with _handles_lock:
        return KEY_STATE.setdefault(kid, {"cooldown": {}, "grounding_paused_until": 0.0, "invalid": False,
                                          "budget": {"day": "", "used": 0}})


def handle_for(user_id: Optional[str]) -> Optional[KeyHandle]:
    """The handle of the account's unlocked key (made on first use), or None. A replaced key revokes the old handle."""
    key = (UNLOCKED.get(user_id or "") or {}).get("key")
    with _handles_lock:
        h = HANDLES.get(user_id or "")
        if h and key and h.key_id == key_id(key):
            return h
        if h:
            HANDLES.pop(user_id, None)
            h.revoked_at = h.revoked_at or time.time()
        if not key:
            return None
        if client_factory is None:
            raise NoGeminiKey("no Gemini client factory")
        h = HANDLES[user_id] = KeyHandle(user_id=user_id, key_id=key_id(key), client=client_factory(key))
        return h


def revoke(user_id: str, hard: bool = False):
    """The account's key handle stops. Jobs already holding it finish within KEY_LEASE_GRACE_S (lock, logout, a
    replaced key); with hard (the key or the account deleted) they stop at their next model call."""
    with _handles_lock:
        h = HANDLES.pop(user_id, None)
        if h:
            h.revoked_at = h.revoked_at or time.time()
            h.hard = h.hard or hard


def forget(user_id: str, hard: bool = False):
    """Lock, logout, delete: the unlocked key leaves memory and its handle is revoked."""
    UNLOCKED.pop(user_id, None)
    revoke(user_id, hard)


def acquire(owner_id: Optional[str]) -> Optional[KeyHandle]:
    """The lease of a job of `owner_id`: the key running this code if it is the same owner's (a job queued by a job),
    else the owner's unlocked key. None when the owner has none."""
    h = ACTIVE_KEY.get()
    if h is None or h.user_id != owner_id:
        h = handle_for(owner_id) if owner_id else None
    return h


def usable(h: Optional[KeyHandle]) -> KeyHandle:
    """The handle a model call may use now. A revoked handle gives way to the owner's current one (signed in again, or
    a new key); without one it still works within the grace, unless revoked hard. None or hard -> NoGeminiKey, past
    the grace -> KeyLocked."""
    if h is None:
        raise NoGeminiKey("no Gemini key")
    if h.revoked_at is not None:
        fresh = handle_for(h.user_id)
        if fresh is not None:
            return fresh
        if h.hard:
            raise NoGeminiKey("Gemini key deleted")
        if time.time() - h.revoked_at > KEY_LEASE_GRACE_S:
            raise KeyLocked("account locked")
    return h
