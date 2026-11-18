#!/usr/bin/env python3
"""Record the Commissar's fixed lines once with ElevenLabs into the local voice pack content/voice_packs/commissar/.

The app only ever plays these files (voice_packs.py); it never calls ElevenLabs for Commissar mode. The text is the
original lines in src/lib/commissarLines.json, spoken by a stock ElevenLabs voice (not a clone of anyone).
The pack folder is gitignored and is not copied into the Docker image or the desktop bundle.

  python3 scripts/make_commissar_voice.py --dry-run        # count the characters, call nothing
  python3 scripts/make_commissar_voice.py                  # record the missing clips (needs ELEVENLABS_API_KEY in .env)
  python3 scripts/make_commissar_voice.py --only on --limit 1   # a single test clip

Already recorded clips are kept (their file name carries a hash of the text and voice), so a rerun only pays for
new or changed lines. --max-chars stops before the total would pass the cap.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

LINES = ROOT / "src" / "lib" / "commissarLines.json"
VOICE = "onwK4e9ZLuTAKqWW03F9"  # ElevenLabs default voice "Daniel" (deep, British, authoritative; free-plan safe); --voice to change
MODEL = "eleven_multilingual_v2"
FORMAT = "mp3_44100_128"
API = "https://api.elevenlabs.io/v1/text-to-speech/{voice}"
# a stern, steady delivery: low variation, strong style
SETTINGS = {"stability": 0.6, "similarity_boost": 0.8, "style": 0.35, "use_speaker_boost": True}


def clip_name(event: str, text: str, voice: str) -> str:
    h = hashlib.sha256(f"{voice}|{MODEL}|{text}".encode()).hexdigest()[:12]
    return f"{event}-{h}.mp3"


def write_manifest(out: Path, manifest: dict, voice: str) -> None:
    """Lists only clips that exist, so a partial run still gives a working pack."""
    events = {e: [n for n in names if (out / n).is_file() and not (out / n).is_symlink()] for e, names in manifest.items()}
    events = {e: n for e, n in events.items() if n}
    if not events:
        return
    target, tmp = out / "manifest.json", out / ".manifest.json.tmp"
    tmp.unlink(missing_ok=True)
    tmp.write_text(json.dumps({"name": "Commissar (premade)", "voice": voice, "model": MODEL, "events": events}, indent=2) + "\n",
                   encoding="utf-8")
    os.replace(tmp, target)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voice", default=VOICE)
    ap.add_argument("--out", default=str(Path(os.environ.get("SCIEDU_CONTENT_DIR") or ROOT / "content") / "voice_packs" / "commissar"))
    ap.add_argument("--only", help="record only this event (e.g. on)")
    ap.add_argument("--limit", type=int, default=0, help="at most this many new clips")
    ap.add_argument("--max-chars", type=int, default=3000, help="refuse to send more characters than this")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    lines = json.loads(LINES.read_text(encoding="utf-8"))
    out = Path(args.out)
    todo, manifest = [], {}
    for event, texts in lines.items():
        for text in texts:
            name = clip_name(event, text, args.voice)
            manifest.setdefault(event, []).append(name)
            if (out / name).exists() or (args.only and event != args.only):
                continue
            todo.append((event, text, name))
    if args.limit:
        todo = todo[:args.limit]
    chars = sum(len(t) for _, t, _ in todo)
    print(f"{len(todo)} clips to record, {chars} characters (cap {args.max_chars}); voice {args.voice}")
    if chars > args.max_chars:
        print("Over the cap: nothing sent. Raise --max-chars or use --only/--limit.")
        return 1
    if args.dry_run:
        return 0
    if not todo:
        write_manifest(out, manifest, args.voice)
        return 0

    load_dotenv(ROOT / ".env")
    key = (os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVEN_LABS_API_KEY") or "").strip()
    if not key:
        print("No ELEVENLABS_API_KEY in .env.")
        return 1
    out.mkdir(parents=True, exist_ok=True)
    made = spent = 0
    for event, text, name in todo:
        try:
            r = httpx.post(API.format(voice=args.voice), params={"output_format": FORMAT},
                           headers={"xi-api-key": key, "Accept": "audio/mpeg"},
                           json={"text": text, "model_id": MODEL, "voice_settings": SETTINGS}, timeout=30.0)
        except httpx.HTTPError as e:
            print(f"  {name}: request failed ({type(e).__name__}); stopping")
            break
        if r.status_code != 200 or not r.content:
            detail = ""
            try:
                detail = (r.json().get("detail") or {}).get("message", "")
            except ValueError:
                pass
            print(f"  {name}: HTTP {r.status_code} {detail}; stopping")
            break
        tmp = out / f".{name}.tmp"
        tmp.unlink(missing_ok=True)
        tmp.write_bytes(r.content)
        os.replace(tmp, out / name)  # replaces a planted symlink instead of writing through it
        made += 1
        spent += len(text)
        print(f"  {name}  ({len(text)} chars)")
    write_manifest(out, manifest, args.voice)
    print(f"Recorded {made} clips, {spent} characters sent. Pack: {out}")
    return 0 if made == len(todo) else 1


if __name__ == "__main__":
    sys.exit(main())
