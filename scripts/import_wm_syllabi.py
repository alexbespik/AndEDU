#!/usr/bin/env python3
"""
Imports William & Mary course syllabi into the course advisor AI.

Fetches public W&M course syllabi directly from departmental servers (cs.wm.edu) and public
academic course repositories, parses textbooks, prerequisites, learning objectives, and
weekly lecture schedules, and stores them in `catalog_courses.syllabus`.

Usage:
    python3 scripts/import_wm_syllabi.py                       # fetch and import core W&M STEM syllabi
    python3 scripts/import_wm_syllabi.py --file my_syllabus.pdf --code "CSCI 241" --title "Data Structures"
"""
import argparse
import html
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import db  # noqa: E402
import advisor  # noqa: E402

UA = "andedu-syllabus-import/1.0 (W&M study tool; polite, cached)"
CACHE_DIR = ROOT / "content" / "syllabus_cache"


def fetch_url(url: str, timeout: int = 15) -> bytes:
    """Polite fetcher with local caching."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_key = re.sub(r"[^a-zA-Z0-9_-]", "_", url)[:120]
    cached_file = CACHE_DIR / cache_key
    if cached_file.exists():
        return cached_file.read_bytes()

    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        cached_file.write_bytes(data)
        return data


def extract_pdf_text(data: bytes) -> str:
    """Extracts text from PDF bytes using pypdf if available."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    except Exception as e:
        print(f"  [PDF Warning] Could not extract with pypdf ({e})")
        return ""


def clean_html_cell(text: str) -> str:
    text = re.sub(r"<br\s*/?>", " / ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_cs_davis_course(code: str, title: str, credits: str, url_slug: str) -> Optional[Dict[str, Any]]:
    """Parses Dr. Timothy Davis's W&M computer science course pages (syllabus PDF + schedule table)."""
    base_url = f"https://www.cs.wm.edu/~tadavis/{url_slug}/"
    print(f"Fetching W&M {code}: {title} from {base_url}...")
    try:
        page_html = fetch_url(base_url).decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  Failed to fetch {base_url}: {e}")
        return None

    # 1. Parse syllabus PDF if available
    syllabus_pdf_url = f"{base_url}syllabus.pdf"
    pdf_text = ""
    try:
        pdf_bytes = fetch_url(syllabus_pdf_url)
        pdf_text = extract_pdf_text(pdf_bytes)
    except Exception:
        pass

    # 2. Parse schedule table from HTML
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", page_html, re.S | re.I)
    schedule = []
    for r in rows:
        cells = [clean_html_cell(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S | re.I)]
        if len(cells) >= 2 and not any(h in cells[0].lower() for h in ("date", "lecture")):
            date, topics = cells[0], cells[1]
            sections = cells[2] if len(cells) >= 3 else ""
            if date and len(date) < 25 and topics and len(topics) > 2 and date != "&nbsp;":
                clean_top = " ".join(t.strip() for t in topics.split("/") if t.strip() and t.strip().lower() != "full")
                clean_top = re.sub(r"\s+", " ", clean_top)
                sec_str = f" [Sections: {sections}]" if sections and sections != "&nbsp;" else ""
                schedule.append(f"- **{date}**: {clean_top}{sec_str}")

    # 3. Extract metadata from PDF or HTML
    prereqs = ""
    textbook = ""
    description = ""

    if pdf_text:
        pre_m = re.search(r"Prerequisites?\s*[:\n]\s*([^\n]+)", pdf_text, re.I)
        if pre_m:
            prereqs = pre_m.group(1).strip()
        tb_m = re.search(r"Textbooks?\s*[:\n]\s*([^\n]+(?:\n[^\n]+)?)", pdf_text, re.I)
        if tb_m:
            textbook = re.sub(r"\s+", " ", tb_m.group(1)).strip()
        desc_m = re.search(r"Course Description\s*[:\n]\s*(.*?)(?=\n[A-Z][a-z]+|\Z)", pdf_text, re.S | re.I)
        if desc_m:
            description = re.sub(r"\s+", " ", desc_m.group(1)).strip()

    if not description:
        description = f"William & Mary Department of Computer Science course {code}: {title}."

    # Format complete syllabus markdown
    syllabus_md = f"""# {code}: {title}
**Institution**: William & Mary (Department of Computer Science)  
**Instructor**: Dr. Timothy A. Davis  
**Course Page**: {base_url}  
**Prerequisites**: {prereqs or 'None listed'}  
**Textbook**: {textbook or 'See course page'}

## Course Description
{description}

## Detailed Lecture Schedule & Topics
{chr(10).join(schedule) if schedule else 'Detailed schedule available on course webpage.'}
"""

    return {
        "code": code,
        "title": title,
        "credits": credits,
        "description": description[:1000],
        "prereqs": prereqs,
        "prereq_codes": advisor.find_codes(prereqs),
        "attributes": ["NQR"] if "math" in title.lower() or "discrete" in title.lower() else [],
        "syllabus": syllabus_md.strip(),
        "source": base_url,
    }


def parse_physics_wm_quantum() -> Optional[Dict[str, Any]]:
    """Parses Prof. Wouter Deconinck's W&M Graduate Quantum Mechanics syllabus from GitHub."""
    url = "https://raw.githubusercontent.com/wdconinc/graduate_quantum_mechanics/master/syllabus.md"
    print(f"Fetching W&M PHYS 621: Quantum Mechanics from {url}...")
    try:
        raw_md = fetch_url(url).decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  Failed to fetch physics syllabus: {e}")
        return None

    desc = ("Axiomatic development of wave mechanics and the Schroedinger equation in one and three dimensions; "
            "wave packets; spin and angular momentum, Hilbert space, symmetries, and conservation laws.")

    return {
        "code": "PHYS 621",
        "title": "Quantum Mechanics",
        "credits": "3",
        "description": desc,
        "prereqs": "PHYS 401 or equivalent undergraduate quantum physics",
        "prereq_codes": ["PHYS 401"],
        "attributes": ["NQR"],
        "syllabus": raw_md.strip(),
        "source": "https://github.com/wdconinc/graduate_quantum_mechanics",
    }


def parse_file(path: Path, code: str, title: str, credits: str = "3") -> Optional[Dict[str, Any]]:
    """Parses a local syllabus file (PDF, Markdown, or plain text)."""
    if not path.exists():
        print(f"File not found: {path}")
        return None

    if path.suffix.lower() == ".pdf":
        text = extract_pdf_text(path.read_bytes())
    else:
        text = path.read_text(encoding="utf-8", errors="replace")

    prereqs = ""
    pre_m = re.search(r"Prerequisites?\s*[:\-]?\s*([^\n]+)", text, re.I)
    if pre_m:
        prereqs = pre_m.group(1).strip()

    return {
        "code": code,
        "title": title,
        "credits": credits,
        "description": text[:600].strip(),
        "prereqs": prereqs,
        "prereq_codes": advisor.find_codes(prereqs),
        "attributes": [],
        "syllabus": text.strip(),
        "source": str(path.name),
    }


def main():
    parser = argparse.ArgumentParser(description="Import W&M course syllabi into the advisor database")
    parser.add_argument("--file", help="Path to a syllabus PDF, MD, or TXT file to import")
    parser.add_argument("--code", help="Course code (e.g. CSCI 241)", default="")
    parser.add_argument("--title", help="Course title (e.g. Data Structures)", default="")
    parser.add_argument("--credits", help="Credit hours", default="3")
    args = parser.parse_args()

    db.init_db()
    advisor.init()

    courses_to_import = []

    if args.file:
        if not args.code or not args.title:
            print("Error: --code and --title are required when importing a single file.")
            sys.exit(1)
        res = parse_file(Path(args.file), args.code, args.title, args.credits)
        if res:
            courses_to_import.append(res)
    else:
        # Default suite: W&M STEM courses with public verified syllabi
        c1 = parse_cs_davis_course("CSCI 243", "Discrete Structures in Computer Science", "3", "cs243")
        if c1:
            courses_to_import.append(c1)

        c2 = parse_cs_davis_course("CSCI 304", "Computer Organization", "3", "cs304")
        if c2:
            courses_to_import.append(c2)

        c3 = parse_cs_davis_course("CSCI 423", "Finite Automata & Theory of Computation", "3", "cs423")
        if c3:
            courses_to_import.append(c3)

        c4 = parse_physics_wm_quantum()
        if c4:
            courses_to_import.append(c4)

    if not courses_to_import:
        print("No syllabi could be parsed.")
        sys.exit(1)

    print(f"\nImporting {len(courses_to_import)} courses with full syllabi into advisor...")
    saved_count = advisor.upsert_courses(courses_to_import, source="W&M Syllabi Import")
    print(f"Successfully imported/updated {saved_count} courses with full syllabi!\n")

    for c in courses_to_import:
        syl_len = len(c.get("syllabus", ""))
        print(f"  • {c['code']}: {c['title']} ({c.get('credits')} credits)")
        print(f"    Prerequisites: {c.get('prereqs') or 'None'}")
        print(f"    Syllabus content: {syl_len:,} characters")


if __name__ == "__main__":
    main()
