"""Local voice packs for Commissar mode: recorded clips played instead of the browser voice.

A pack is a folder `content/voice_packs/<pack>/` (gitignored, never copied into the Docker image or the desktop
bundle) holding audio files and a `manifest.json`:

    {"name": "Commissar (premade)", "events": {"on": ["a1.mp3", "a2.mp3"], "tab": ["b1.mp3"], ...}, "summon": "word"}

`summon` (optional, 3-20 lowercase letters, not a console command) is a word that, typed in the console, turns
Commissar mode on in this pack's voice.

Event names are the ones in src/lib/commissarLines.json. The browser only plays clips; nothing is generated here.
`scripts/make_commissar_voice.py` writes the premade `commissar` pack once with ElevenLabs.

Local only: with server accounts (SCIEDU_AUTH=1) every route answers 404. Only files that a pack's manifest lists,
that sit directly in the pack folder (no subfolders, no symlinks) and have an audio extension are ever served.
"""
import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

EVENTS = ("on", "off", "tab", "quizPass", "quizFail", "reward", "streak", "streakRisk", "reviewDue",
          "quizStart", "quizWin", "quizLose", "desert")  # the last four: a quiz begins, ends >=80% / <80%, is left
PACK_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")
FILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}\.(mp3|ogg|wav|m4a|webm)$")
SUMMON_RE = re.compile(r"^[a-z]{3,20}$")
# console commands and the Commissar's own word can't be taken by a pack
RESERVED_WORDS = {"help", "voices", "voice", "rough", "mute", "unmute", "clear", "exit", "yarrik", "auto"}
MEDIA = {"mp3": "audio/mpeg", "ogg": "audio/ogg", "wav": "audio/wav", "m4a": "audio/mp4", "webm": "audio/webm"}
MAX_CLIPS_PER_EVENT = 200
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_MANIFEST_BYTES = 256 * 1024


def _clip_path(folder: Path, name: Any) -> Optional[Path]:
    """The clip's path when it is a plain audio file directly inside `folder`, else None."""
    if not isinstance(name, str) or not FILE_RE.fullmatch(name) or ".." in name:
        return None
    path = folder / name
    try:
        if path.is_symlink() or not path.is_file() or path.resolve().parent != folder.resolve():
            return None
        st = path.stat()
        if st.st_size > MAX_FILE_BYTES or st.st_nlink > 1:  # no hardlinks to files elsewhere
            return None
    except OSError:
        return None
    return path


def load_pack(root: Path, pack: str) -> Optional[Dict[str, Any]]:
    """{"id", "name", "events": {event: [file, ...]}} with only the clips that exist, or None for no usable pack."""
    if not PACK_RE.fullmatch(pack or ""):
        return None
    folder = root / pack
    manifest = folder / "manifest.json"
    try:
        if folder.is_symlink() or not folder.is_dir() or manifest.is_symlink() or manifest.stat().st_size > MAX_MANIFEST_BYTES:
            return None
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("events"), dict):
        return None
    events: Dict[str, List[str]] = {}
    for event in EVENTS:
        files = data["events"].get(event)
        if isinstance(files, list):
            ok = [f for f in files[:MAX_CLIPS_PER_EVENT] if _clip_path(folder, f)]
            if ok:
                events[event] = ok
    if not events:
        return None
    info = {"id": pack, "name": str(data.get("name") or pack)[:60], "events": events}
    word = data.get("summon")
    if isinstance(word, str) and SUMMON_RE.fullmatch(word) and word not in RESERVED_WORDS:
        info["summon"] = word  # typed in the console, it turns the mode on in this pack's voice
    return info


def list_packs(root: Path) -> List[Dict[str, Any]]:
    try:
        names = sorted(p.name for p in root.iterdir() if p.is_dir())
    except OSError:
        return []
    return [p for p in (load_pack(root, n) for n in names) if p]


def build_router(*, root: Callable[[], Path], enabled: Callable[[], bool], rate_limit: Callable[[str], None]) -> APIRouter:
    router = APIRouter()

    def guard():
        if not enabled():
            raise HTTPException(status_code=404, detail="Voice packs are only available on this computer.")

    @router.get("/api/voice-packs")
    def get_packs():
        """Local voice packs with the clips each event can play."""
        guard()
        return {"packs": list_packs(root())}

    @router.get("/api/voice-packs/{pack}/{file}")
    def get_clip(pack: str, file: str):
        guard()
        rate_limit("voice_clip")
        info = load_pack(root(), pack)
        if not info or not any(file in files for files in info["events"].values()):
            raise HTTPException(status_code=404, detail="No such clip.")
        path = _clip_path(root() / pack, file)
        if not path:
            raise HTTPException(status_code=404, detail="No such clip.")
        # open once without following links and read that same file, so a swap after the checks can't change it
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        except OSError:
            raise HTTPException(status_code=404, detail="No such clip.")
        with os.fdopen(fd, "rb") as f:
            st = os.fstat(f.fileno())
            if st.st_nlink > 1 or st.st_size > MAX_FILE_BYTES:
                raise HTTPException(status_code=404, detail="No such clip.")
            data = f.read(MAX_FILE_BYTES + 1)
        return Response(data, media_type=MEDIA[path.suffix[1:].lower()],
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=86400"})

    return router
