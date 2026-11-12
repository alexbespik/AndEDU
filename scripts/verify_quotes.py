"""Check every quote in content/quotes/*.json word for word against its source_url (network).

The app only shows quotes from this bank and never generates one, so each text must occur in its public-domain
source. Spacing, curly quotes, dashes and Gutenberg's _italics_ markers are normalised before comparing.

    python3 scripts/verify_quotes.py            # all banks
    python3 scripts/verify_quotes.py stoic      # one bank
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

QUOTES_DIR = Path(__file__).resolve().parent.parent / "content" / "quotes"
ALLOWED_HOSTS = ("www.gutenberg.org", "gutenberg.org", "standardebooks.org", "classics.mit.edu")


def normalise(text: str) -> str:
    for a, b in (("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"'), ("—", "-"), ("--", "-"), ("_", "")):
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip().lower()


def fetch(url: str, cache: dict) -> str:
    host = url.split("/")[2]
    if not url.startswith("https://") or host not in ALLOWED_HOSTS:
        raise ValueError(f"source_url not allowed: {url}")
    if url not in cache:
        with urllib.request.urlopen(url, timeout=30) as r:
            cache[url] = normalise(r.read().decode("utf-8", "replace"))
    return cache[url]


def main(names) -> int:
    files = [QUOTES_DIR / f"{n}.json" for n in names] if names else sorted(QUOTES_DIR.glob("*.json"))
    cache, bad = {}, 0
    for f in files:
        for q in json.loads(f.read_text(encoding="utf-8"))["quotes"]:
            ok = normalise(q["text"]) in fetch(q["source_url"], cache)
            bad += not ok
            print(f"{'ok  ' if ok else 'MISS'} {f.stem}/{q['id']}: {q['text'][:60]}")
    print(f"{bad} quote(s) not found in their source" if bad else "all quotes found in their sources")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
