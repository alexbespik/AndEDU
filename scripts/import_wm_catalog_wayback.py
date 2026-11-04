#!/usr/bin/env python3
"""
Imports a W&M undergraduate catalog into the course advisor from the Internet Archive (web.archive.org).

catalog.wm.edu refuses scripted access, but the Internet Archive keeps public snapshots of its course pages.
This fetches those snapshots politely (one request per --delay seconds, backing off on 429), caches every page
under content/catalog_cache/, and imports code, title, credits, description, prerequisites and attributes.

    python3 scripts/import_wm_catalog_wayback.py                 # 2023-2024 undergraduate catalog (catoid 28)
    python3 scripts/import_wm_catalog_wayback.py --catoid 34 --year 2025-2026

Catalog ids (Acalog "catoid"): 34 = 2025-26 UG, 30 = 2024-25 UG, 28 = 2023-24 UG, 26 = 2022-23 UG.
Coverage depends on what the Archive captured; the advisor labels the data with its year and shows it as
possibly out of date.
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import db  # noqa: E402
import advisor  # noqa: E402

UA = "andedu-catalog-import/1.0 (personal study tool; polite, cached)"


def get(url: str, tries: int = 4) -> bytes:
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and k < tries - 1:
                wait = 60 * (k + 1)
                print(f"  archive asked us to slow down ({e.code}); waiting {wait}s", flush=True)
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError:
            if k < tries - 1:
                time.sleep(15)
                continue
            raise
    raise RuntimeError("unreachable")


def snapshots(catoid: int, cache: Path):
    """Latest archived snapshot of every course page of one catalog."""
    idx = cache / "index.json"
    if idx.exists():
        return json.loads(idx.read_text())
    url = ("https://web.archive.org/cdx/search/cdx?url=catalog.wm.edu/preview_course_nopop.php"
           f"&matchType=prefix&output=json&filter=statuscode:200&fl=original,timestamp")
    rows = json.loads(get(url))[1:]
    latest = {}
    for original, ts in rows:
        m = re.search(r"catoid=(\d+)&coid=(\d+)", original)
        if m and int(m.group(1)) == catoid and ts > latest.get(m.group(2), ("", ""))[1]:
            latest[m.group(2)] = (original, ts)
    out = sorted(latest.items())
    idx.write_text(json.dumps(out))
    return out


def parse(page: str):
    m0 = re.search(r"<h1[^>]*id=['\"]course_preview_title['\"][^>]*>", page)
    if not m0:
        return None
    blk = page[m0.end():]
    end = blk.find("Back to Top")
    blk = blk[: end if end > 0 else 6000]
    text = html.unescape(re.sub(r"<br\s*/?>|</p>|</li>", "\n", blk))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    head = lines[0] if lines else ""
    m = re.match(r'^[">\s]*([A-Z]{2,5})\s?(\d{3}[A-Z]?)\s*-\s*(.+?)\s*(?:Credits?:\s*\(?([\d.\-\s]+?)\)?\s*)?$', head)
    if not m:
        return None
    body = " ".join(lines[1:])
    cm = re.search(r"Credits?\s*:?\s*\(?\s*([\d.]+(?:\s*[-–]\s*[\d.]+)?)\s*\)?", body)
    body = body[:cm.start()] + body[cm.end():] if cm else body
    pre = re.search(r"Prerequisites?(?:\(s\))?\s*:\s*(.+?)(?:\s+\.\s+|\.\s+(?=[A-Z])|\s(?=Corequisite|Cross-listed|Course Attributes)|$)", body, re.I)
    prereqs = pre.group(1).strip(" .") if pre else ""
    labels = re.findall(r"(?:College Curriculum|Domain(?:\s*\([^)]*\))?|Proficiency)\s*:\s*((?:COLL\s?\d{3}[A-Z]?|[A-Z]{2,4}))", body)
    desc = body
    if pre:
        desc = desc[:pre.start()] + " " + desc[pre.end():]
    desc = re.sub(r"(?:College Curriculum|Domain(?:\s*\([^)]*\))?|Proficiency)\s*:\s*(?:COLL\s?\d{3}[A-Z]?|[A-Z]{2,4})", " ", desc)
    desc = re.split(r"\s(?:Cross-listed with:|Corequisite\(?s?\)?:)", desc, maxsplit=1)[0]
    desc = re.sub(r"\s+", " ", desc).strip()
    code = advisor.norm_code(m.group(1), m.group(2))
    return {"code": code, "title": m.group(3).strip(), "credits": (m.group(4) or (cm.group(1) if cm else "")).strip(),
            "description": desc[:2000], "prereqs": prereqs[:500],
            "prereq_codes": [c for c in advisor.find_codes(prereqs) if c != code],
            "attributes": sorted(set(labels) | set(re.findall(r"\b(COLL\s?\d{3}[A-Z]?|NQR|ALV|CSI)\b", body)))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catoid", type=int, default=28)
    ap.add_argument("--year", default="2023-2024")
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    cache = ROOT / "content" / "catalog_cache" / str(a.catoid)
    cache.mkdir(parents=True, exist_ok=True)
    db.init_db()
    advisor.init()
    snaps = snapshots(a.catoid, cache)
    if a.limit:
        snaps = snaps[: a.limit]
    print(f"{len(snaps)} archived course pages for catalog {a.catoid} ({a.year})", flush=True)
    rows, fetched = [], 0
    for n, (coid, (original, ts)) in enumerate(snaps, 1):
        f = cache / f"{coid}.html"
        if not f.exists():
            try:
                f.write_bytes(get(f"https://web.archive.org/web/{ts}id_/{original}"))
            except Exception as e:  # skip pages the archive can't serve; they can be retried later
                print(f"  skip coid {coid}: {e}", flush=True)
                continue
            fetched += 1
            time.sleep(a.delay)
        r = parse(f.read_text(errors="ignore"))
        if r:
            rows.append(r)
        if n % 50 == 0:
            advisor.upsert_courses(rows, f"wayback {a.year} catalog")
            print(f"  {n}/{len(snaps)} pages, {len(rows)} courses parsed", flush=True)
    imported = advisor.upsert_courses(rows, f"wayback {a.year} catalog")
    print(f"done: {imported} courses imported ({fetched} pages downloaded, the rest from cache)", flush=True)


if __name__ == "__main__":
    main()
