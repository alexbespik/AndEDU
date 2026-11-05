#!/usr/bin/env python3
"""
Classifies William & Mary catalog courses into College Curriculum attributes and Proficiencies
(COLL 200/300, ALV, CSI, NQR, MATH, ARTS).

Usage:
    python3 scripts/classify_wm_courses.py --dry-run
    python3 scripts/classify_wm_courses.py --run --limit 50 --depts CSCI,HIST
    python3 scripts/classify_wm_courses.py --run --force
"""
import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import advisor
import advisor_classifier
import db
import server


async def run_classifier(args):
    db.init_db()
    advisor.init()
    dry_run = not args.run
    depts = [d.strip().upper() for d in args.depts.split(",")] if args.depts else None

    print(f"Running course classifier (dry_run={dry_run}, limit={args.limit}, force={args.force}, depts={depts})...")

    async def call_model(prompt):
        return await server.gemini_json(prompt, role="planner")

    def progress(p, step):
        print(f"[{int(p * 100)}%] {step}")

    res = await advisor_classifier.classify_catalog_courses(
        school="wm",
        dry_run=dry_run,
        limit=args.limit,
        depts=depts,
        force=args.force,
        call_json_fn=call_model,
        progress_fn=progress,
    )
    print(f"\nDone! Processed {res.get('classified', 0)} courses in {res.get('batches', 0)} batches.")
    if dry_run:
        print("Dry run only: no changes saved to database. Use --run to save changes.")
    else:
        print("Successfully updated attributes in database.")


def main():
    parser = argparse.ArgumentParser(description="Classify William & Mary courses into College Curriculum attributes.")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Preview classifications without saving (default unless --run is specified).")
    parser.add_argument("--run", action="store_true", default=False, help="Execute and save classifications to database.")
    parser.add_argument("--limit", type=int, default=200, help="Maximum number of courses to classify (default 200).")
    parser.add_argument("--depts", type=str, default="", help="Comma-separated list of departments (e.g. CSCI,HIST).")
    parser.add_argument("--force", action="store_true", help="Reclassify courses even if their content hash has not changed.")
    args = parser.parse_args()

    asyncio.run(run_classifier(args))


if __name__ == "__main__":
    main()
