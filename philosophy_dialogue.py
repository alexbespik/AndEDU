"""Philosophy dialogue data: the figures a student can talk to and the real quotations they may be shown with.

A figure is an author with at least one quote in content/quotes/*.json (any number of banks; new files are picked up
on the next request). The model never supplies quotation text: it may only name the id of one quote from the short
list it was given, and the server returns the bank's own text for that id. Pure functions, standard library only;
the prompt and the HTTP routes live in server.py.
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Life dates of the authors the banks hold today. A bank author missing here still works, with no era shown.
ERAS: Dict[str, str] = {
    "socrates": "c. 470-399 BCE",
    "aristotle": "384-322 BCE",
    "epictetus": "c. 50-135 CE",
    "marcus-aurelius": "121-180 CE",
    "david-hume": "1711-1776",
    "immanuel-kant": "1724-1804",
    "john-stuart-mill": "1806-1873",
    "friedrich-nietzsche": "1844-1900",
}

QUOTE_KEYS = ("id", "text", "author", "work", "ref", "translator", "source_url")
_cache: Dict[str, Tuple[Tuple, Dict[str, Any]]] = {}


def slug(name: str) -> str:
    """kebab-case id of an author name ("Marcus Aurelius" -> "marcus-aurelius")."""
    return re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")


def _read_banks(quotes_dir: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    figures: Dict[str, Dict[str, Any]] = {}
    by_slug: Dict[str, str] = {}  # slug -> author name that owns it
    quotes_by_id: Dict[str, Dict[str, Any]] = {}
    files = sorted(Path(quotes_dir).glob("*.json")) if Path(quotes_dir).is_dir() else []
    for f in files:
        try:
            bank = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(bank, dict) or not isinstance(bank.get("quotes"), list):
            continue
        collection = str(bank.get("collection") or f.stem)
        for q in bank["quotes"]:
            if not isinstance(q, dict) or not all(str(q.get(k) or "").strip() for k in ("id", "text", "author")):
                continue
            author = str(q["author"]).strip()
            fid = slug(author)
            if not fid:
                continue
            # two different spellings that slug alike stay two figures: the later one gets a numeric suffix
            n, base = 1, fid
            while fid in by_slug and by_slug[fid] != author:
                n += 1
                fid = f"{base}-{n}"
            by_slug[fid] = author
            fig = figures.setdefault(fid, {"id": fid, "name": author, "era": ERAS.get(fid, ""), "collection": [],
                                           "quotes": {}})
            if collection not in fig["collection"]:
                fig["collection"].append(collection)
            clean = {k: str(q.get(k) or "").strip() for k in QUOTE_KEYS}
            fig["quotes"][clean["id"]] = clean
            quotes_by_id[clean["id"]] = clean
    return sorted(figures.values(), key=lambda x: x["name"].lower()), figures


def load(quotes_dir: Path) -> Dict[str, Dict[str, Any]]:
    """{figure id: {id, name, era, collection: [...], quotes: {quote id: quote}}}, cached until a bank file changes."""
    d = Path(quotes_dir)
    stamp = tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in sorted(d.glob("*.json"))) if d.is_dir() else ()
    hit = _cache.get(str(d))
    if hit and hit[0] == stamp:
        return hit[1]
    _, figures = _read_banks(d)
    _cache[str(d)] = (stamp, figures)
    return figures


def list_figures(quotes_dir: Path) -> List[Dict[str, Any]]:
    """[{id, name, era, collection (a list), quote_count}] sorted by name."""
    figs = load(quotes_dir)
    return [{"id": f["id"], "name": f["name"], "era": f["era"], "collection": list(f["collection"]),
             "quote_count": len(f["quotes"])} for f in sorted(figs.values(), key=lambda x: x["name"].lower())]


def shortlist(figure: Dict[str, Any], text: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Up to `limit` of the figure's quotes, the ones sharing most words with `text` first (bank order breaks ties)."""
    quotes = list(figure["quotes"].values())
    if len(quotes) <= limit:
        return quotes
    words = set(re.findall(r"[a-z]{4,}", str(text or "").lower()))
    scored = sorted(enumerate(quotes), key=lambda iq: (-len(words & set(re.findall(r"[a-z]{4,}", iq[1]["text"].lower()))), iq[0]))
    return [q for _, q in scored[:limit]]


def public_quote(q: Dict[str, Any]) -> Dict[str, str]:
    return {k: q[k] for k in QUOTE_KEYS}


def read_reply(data: Any, allowed: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Turns the model's parsed JSON (or plain text) into {reply, quote, suggested_questions}. The quote is the bank's
    own entry for an id from `allowed`; any other id (or text) is ignored."""
    if not isinstance(data, dict):
        data = {"reply": str(data or "")}
    reply = str(data.get("reply") or "").strip()[:1500]
    qid = data.get("quote_id")
    quote = public_quote(allowed[qid]) if isinstance(qid, str) and qid in allowed else None
    asked = data.get("suggested_questions")
    questions = [str(x).strip()[:140] for x in asked if isinstance(x, (str, int, float)) and str(x).strip()][:3] \
        if isinstance(asked, list) else []
    return {"reply": reply, "quote": quote, "suggested_questions": questions}
