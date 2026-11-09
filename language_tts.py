"""Spoken words and phrases for the Languages workspace (ElevenLabs, cached on disk) and the built-in course seed.

POST /api/language/tts {text, lang, voice?, purpose?} -> {url, source: cache | elevenlabs | browser}. Audio is made only with
SCIEDU_ELEVENLABS=1 and the server's own key (never a key from the browser); everything else answers "browser" and the
page reads the text with its own voice. Every clip is generated once: content/tts_cache/<sha256>.mp3, keyed on the model,
voice, format, language and the NFC-normalized text, so slow playback (a browser playbackRate) reuses the same file.
The cache is capped (SCIEDU_TTS_CACHE_MB, oldest files removed first) and so is spending: SCIEDU_TTS_DAILY_CHARS
characters per server day (an in-memory counter, reset by a restart) plus the "language_tts" hourly rate limit on misses.
purpose "explain" (the lesson walkthroughs, explain.py) draws on its own SCIEDU_EXPLAIN_TTS_CHARS budget instead, so a
long walkthrough never uses up the Languages allowance; cache hits cost nothing either way.

POST /api/language/seed {"lang": "de"} installs the offline German course (language_de); with accounts on, admins only.

Mounted by server.py through build_router(...); this module never imports server.py.
"""
import hashlib
import os
import re
import threading
import time
import unicodedata
import uuid
from typing import Any, Callable, Dict, Literal, Optional

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

import db
import language_de

MODEL = "eleven_multilingual_v2"
FORMAT = "mp3_44100_128"
MAX_TEXT = 300
# languages eleven_multilingual_v2 speaks (BCP-47 base codes)
TTS_LANGS = {"de", "en", "es", "fr", "it", "pt", "pl", "nl", "sv", "da", "fi", "no", "cs", "sk", "ro", "hr", "bg", "el",
             "uk", "ru", "tr", "ar", "hi", "ta", "id", "ms", "fil", "zh", "ja", "ko"}
VOICE_ID_RE = re.compile(r"^[A-Za-z0-9]{10,40}$")  # same rule as server.VOICE_ID_RE: the id goes into the URL path
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # "george" in server.PROFESSOR_VOICES (multilingual)
API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}"
SEED_LANGS = {"de": language_de}

_locks: Dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()
_usage = {"day": "", "chars": 0}          # purpose "language"
_explain_usage = {"day": "", "chars": 0}  # purpose "explain"
_usage_lock = threading.Lock()
BUDGETS = {"language": (_usage, "SCIEDU_TTS_DAILY_CHARS", 20000), "explain": (_explain_usage, "SCIEDU_EXPLAIN_TTS_CHARS", 15000)}


def _server_key() -> Optional[str]:
    """The server's ElevenLabs key, only when SCIEDU_ELEVENLABS=1 (same variables as the lecture voiceover)."""
    if os.environ.get("SCIEDU_ELEVENLABS") != "1":
        return None
    return (os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVEN_LABS_API_KEY") or os.environ.get("XI_API_KEY") or "").strip() or None


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name) or default)
    except ValueError:
        return default


def cache_dir():
    return db.CONTENT_ROOT / "tts_cache"


def cache_key(text: str, lang: str, voice: str) -> str:
    clean = unicodedata.normalize("NFC", text.strip())
    return hashlib.sha256(f"v1|{MODEL}|{voice}|{FORMAT}|{lang}|{clean}".encode("utf-8")).hexdigest()


def default_voice(lang: str) -> str:
    voice = (os.environ.get("ELEVENLABS_GERMAN_VOICE_ID") or "").strip() if lang == "de" else ""
    return voice if VOICE_ID_RE.fullmatch(voice) else DEFAULT_VOICE


def _key_lock(key: str) -> threading.Lock:
    with _locks_guard:
        if len(_locks) > 512:  # drop idle locks so the table stays small
            for k in [k for k, v in _locks.items() if not v.locked()]:
                _locks.pop(k, None)
        return _locks.setdefault(key, threading.Lock())


def _reserve_chars(n: int, purpose: str = "language") -> Optional[str]:
    """Counts n characters against today's cap for this purpose and returns the day they were counted on (for
    _refund_chars); None (and nothing counted) when they don't fit."""
    usage, env, default = BUDGETS[purpose]
    day = time.strftime("%Y-%m-%d", time.gmtime())
    cap = _int_env(env, default)
    with _usage_lock:
        if usage["day"] != day:
            usage.update(day=day, chars=0)
        if usage["chars"] + n > cap:
            return None
        usage["chars"] += n
        return day


def _refund_chars(n: int, purpose: str = "language", day: Optional[str] = None):
    """Gives back n reserved characters. With day (from _reserve_chars), nothing happens once the counter has moved on
    to another day: those characters were counted against yesterday's cap, not today's."""
    usage = BUDGETS[purpose][0]
    with _usage_lock:
        if day is not None and usage["day"] != day:
            return
        usage["chars"] = max(0, usage["chars"] - n)


def sweep(limit_bytes: Optional[int] = None):
    """Deletes the oldest clips (by modification time; a cache hit refreshes it) until the folder fits the cap."""
    limit = limit_bytes if limit_bytes is not None else _int_env("SCIEDU_TTS_CACHE_MB", 200) * 1_000_000
    files = []
    for p in cache_dir().glob("*.mp3"):
        try:
            st = p.stat()
        except OSError:
            continue
        files.append((st.st_mtime, st.st_size, p))
    total = sum(size for _, size, _ in files)
    for _, size, p in sorted(files, key=lambda f: f[0]):
        if total <= limit:
            break
        try:
            p.unlink()
            total -= size
        except OSError:
            pass


def _synthesize(text: str, voice: str, key: str) -> Optional[bytes]:
    """One ElevenLabs request; None on any failure (the browser voice takes over)."""
    try:
        r = httpx.post(API_URL.format(voice=voice), params={"output_format": FORMAT},
                       headers={"xi-api-key": key, "Accept": "audio/mpeg"},
                       json={"text": text, "model_id": MODEL}, timeout=15.0)
    except httpx.HTTPError as e:
        print(f"[TTS] ElevenLabs request failed: {type(e).__name__}")
        return None
    if r.status_code != 200 or not r.content:
        print(f"[TTS] ElevenLabs answered HTTP {r.status_code}")
        return None
    return r.content


class TtsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")  # no api_key from the browser, ever
    text: str
    lang: str
    voice: Optional[str] = None
    purpose: Literal["language", "explain"] = "language"  # which daily character budget a new clip draws on


class SeedRequest(BaseModel):
    lang: str = "de"


def build_router(*, rate_limit: Callable[[str], None], require_user: Callable[[str], Any], current_user: Callable[[], Any],
                 auth_required: Any, is_admin: Callable[[], bool] = lambda: True,
                 save_topic: Optional[Callable[[Dict[str, Any]], Any]] = None,
                 topic_exists: Optional[Callable[[str], bool]] = None,
                 normalize_practice: Optional[Callable[[Any], Any]] = None) -> APIRouter:
    """auth_required may be a bool or a callable (tests flip accounts mode at runtime). require_user is accepted for
    the shared module signature; these routes act for the signed-in user and take no user id."""
    router = APIRouter()
    accounts = auth_required if callable(auth_required) else (lambda: bool(auth_required))
    browser = lambda reason: {"url": None, "source": "browser", "reason": reason}

    @router.post("/api/language/tts")
    def language_tts(body: TtsRequest):
        if accounts() and not current_user():
            raise HTTPException(status_code=401, detail="Sign in to continue.")
        text = (body.text or "").strip()
        if not text or len(text) > MAX_TEXT:
            raise HTTPException(status_code=400, detail=f"Text must be 1-{MAX_TEXT} characters.")
        lang = str(body.lang or "").lower().split("-")[0]
        if lang not in TTS_LANGS:
            raise HTTPException(status_code=400, detail="This language has no voice here.")
        # only the server's own voices: any other id could reach private or cloned voices on the account
        if body.voice is not None and body.voice not in {DEFAULT_VOICE, default_voice(lang)}:
            raise HTTPException(status_code=400, detail="Unknown voice.")
        key = _server_key()
        if not key:
            return browser("disabled")
        voice = body.voice or default_voice(lang)
        digest = cache_key(text, lang, voice)
        path = cache_dir() / f"{digest}.mp3"
        url = f"/api/language/tts/{digest}.mp3"
        if path.exists():
            try:
                os.utime(path)  # recently heard clips survive the sweep
            except OSError:
                pass
            return {"url": url, "source": "cache"}
        with _key_lock(digest):  # two students asking for the same new word make one request
            if path.exists():
                return {"url": url, "source": "cache"}
            try:
                rate_limit("language_tts")
            except HTTPException as e:
                if e.status_code == 429:
                    return browser("rate_limited")
                raise
            n = len(unicodedata.normalize("NFC", text))
            day = _reserve_chars(n, body.purpose)
            if not day:
                return browser("daily_cap")
            audio = _synthesize(unicodedata.normalize("NFC", text), voice, key)
            if not audio:
                _refund_chars(n, body.purpose, day)
                return browser("upstream_error")
            tmp = path.with_name(f"{digest}.{uuid.uuid4().hex}.tmp")
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_bytes(audio)
                os.replace(tmp, path)
            except OSError as e:  # disk full or read-only: no clip was kept, so it isn't counted
                print(f"[TTS] could not save the clip: {type(e).__name__}")
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass  # a stray .tmp is never served (only <hash>.mp3 is)
                _refund_chars(n, body.purpose, day)
                return browser("upstream_error")
        sweep()
        return {"url": url, "source": "elevenlabs"}

    @router.get("/api/language/tts/{digest}.mp3")
    def language_tts_file(digest: str):
        if not HASH_RE.fullmatch(digest or ""):
            raise HTTPException(status_code=404, detail="Not found")
        path = cache_dir() / f"{digest}.mp3"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        scope = "private" if accounts() else "public"  # same bytes for everyone, but only signed-in users may fetch
        return FileResponse(path, media_type="audio/mpeg",
                            headers={"Cache-Control": f"{scope}, max-age=31536000, immutable"})

    @router.post("/api/language/seed")
    def language_seed(body: SeedRequest):
        if accounts() and not (current_user() and is_admin()):
            raise HTTPException(status_code=403, detail="Only an administrator can install the built-in courses.")
        course = SEED_LANGS.get(str(body.lang or "").lower())
        if not course:
            raise HTTPException(status_code=400, detail=f"No built-in course for this language (available: {', '.join(sorted(SEED_LANGS))}).")
        if not (save_topic and topic_exists and normalize_practice):
            raise HTTPException(status_code=503, detail="Seeding is not available on this server.")
        return course.seed(save=save_topic, exists=topic_exists, normalize_practice=normalize_practice)

    return router
