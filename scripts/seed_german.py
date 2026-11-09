#!/usr/bin/env python3
"""
Writes the built-in German course (language_de.py, ten A1-A2 units) to content/topics/de-*.json.

    .venv/bin/python scripts/seed_german.py            # writes only the units that don't exist yet
    .venv/bin/python scripts/seed_german.py --dry-run  # lists what it would write

Every unit goes through the server's own normalizers (server.normalize_practice and normalize_topic). The server is
imported against a throwaway data folder, so the live database is never opened; an existing file is never overwritten.
With the backend running, POST /api/language/seed {"lang": "de"} does the same.
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOPICS_DIR = Path(os.environ.get("SCIEDU_CONTENT_DIR") or ROOT / "content") / "topics"
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description="Write the built-in German course to content/topics")
    parser.add_argument("--dry-run", action="store_true", help="print what would be written")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="andedu-seed-") as scratch:
        os.environ["SCIEDU_CONTENT_DIR"] = scratch  # server.py and db.py open their data here, not the live database
        import server  # noqa: E402
        import language_de  # noqa: E402

        def exists(topic_id):
            return (TOPICS_DIR / f"{server.require_topic_id(topic_id)}.json").exists()

        def save(topic):
            clean, warnings = server.normalize_topic(topic)
            if warnings:
                raise SystemExit(f"{clean['id']}: {warnings}")
            if args.dry_run:
                return
            path = TOPICS_DIR / f"{clean['id']}.json"
            TOPICS_DIR.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, path)

        result = language_de.seed(save=save, exists=exists, normalize_practice=server.normalize_practice)

    verb = "would write" if args.dry_run else "wrote"
    for tid in result["created"]:
        print(f"{verb} {TOPICS_DIR / (tid + '.json')}")
    for tid in result["skipped"]:
        print(f"kept   {tid} (already exists)")
    if result["dropped"]:
        print(f"items dropped by the normalizers: {result['dropped']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
