"""Problem sprints and reference-only courses: the two ways a student can bring their own problems.

mode "problem_sprint": a short course that skips the diagnostic. Class 1 (kind "primer") teaches only the concepts and
formulas the problems need; then one class per extracted problem (kind "problem", meta.problemIndex). A problem class's
parts (prompt, staged steps, numeric answer, unit, tolerance) are kept in classes.meta.sprint in the database only,
never in the topic JSON, so /api/topics, practice, MCP get_topic, the tutor and exported lessons cannot show them.
public_class() is the one scrub every course serializer uses: per part only the steps the student revealed (one per
POST /reveal), the answer, unit and tolerance only after one submitted attempt or every step revealed, never compute.
A part whose stated answer failed the server's recomputation (recheck_numeric in server.py) keeps its steps but has no
automatic check: it is done once all of its steps are revealed. When every part of every problem is done and the
course has auto_cleanup (the default; CourseRequest.keep=true turns it off), the course becomes status "cleared":
hidden from My courses, its lessons from the library and the review queue, and purged for good after
SCIEDU_SPRINT_RETAIN_DAYS (default 7). POST /keep and /restore (Undo) bring it back until then, with auto-clean off,
so it is not cleared again. Only a request that newly solves a part can clear a course.

mode "thematic_reference": a normal learn course where the uploads only show the topic, difficulty and assignment
type. Prompts ask for original problems, and drop_copied() removes practice items that reuse the materials' wording
(>= 30% of an item's word 6-grams found in the materials).

Mounted by server.py through build_router(...); this module never imports server.py.
"""
import math
import os
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import db

MODES = ("problem_sprint", "thematic_reference")
KINDS = ("primer", "problem")
MAX_PROBLEMS = 11              # + the primer = at most 12 classes, like other courses
MAX_PARTS, MAX_STEPS = 6, 6
PART_IDS = "abcdefgh"
DEFAULT_TOLERANCE = 0.02       # relative, the same rule as numeric practice items (PracticeDeck.jsx)
NGRAM, COPY_SHARE = 6, 0.30


def retain_days() -> int:
    try:
        return min(max(int(os.environ.get("SCIEDU_SPRINT_RETAIN_DAYS", "7")), 1), 365)
    except ValueError:
        return 7


# ---------------------------------------------------------------------------------------------------------- prompts
PLAN_PROMPT = """
You are preparing a short PROBLEM SPRINT: the student uploaded problems they have to solve and wants each one
explained. Do not solve anything here: only find the problems and the ideas they need.

Return JSON only:
{{"title": "short sprint title", "subject": "e.g. Physics / Calculus / Chemistry",
  "workspace": "math | code | lab | history | language",
  "concepts": [{{"id": "kebab-case-id", "name": "Concept name", "summary": "one sentence"}}],
  "primer": {{"title": "What you need for these problems", "concepts": ["<concept id>"], "objectives": ["By the end the student can ..."]}},
  "problems": [{{"title": "Problem 1: short name", "statement": "the problem exactly as written in the materials, every part (a), (b)... included, LaTeX in $...$",
                "concepts": ["<concept id>"], "objectives": ["Solve part (a): ..."]}}]}}
{mode_rules}

STUDENT GOAL: {goal}

MATERIALS:
{materials}
"""

SPRINT_SYLLABUS = """Rules:
- List every distinct problem in the materials, in their order, at most {max_problems}; one entry per problem
  (its parts stay together). Copy each statement faithfully; never add a solution or a result.
- 2-6 concepts: only the ideas, formulas and techniques these problems need. The primer covers all of them."""

PRIMER_CLASS = (
    "PROBLEM SPRINT PRIMER: the student must solve the problems in the materials soon. Teach ONLY the concepts, formulas "
    "and techniques those problems need, compactly (400-700 words), each with one worked example on a DIFFERENT situation "
    "and different numbers. Never solve, set up or state the result of any of the student's problems. Write 4 quiz "
    "questions on these tools instead of 5, and practice items that use other numbers than the problems."
)

PROBLEM_CLASS = """
PROBLEM SPRINT, problem {index}. The student's own problem, from their materials:
<<<PROBLEM
{statement}
PROBLEM>>>
Build this class around that one problem WITHOUT giving its results away in the lesson, quiz or practice:
- markdownContent: restate the problem, list what is given and what is asked, then "What you need" (200-400 words:
  the ideas and formulas it uses and how to recognise them). Do NOT solve it and do not state any of its results.
- quiz: 3 questions on the ideas it uses (never its answers); practice: 2-3 items on the same ideas with DIFFERENT numbers.
- Also return "problem" (the app reveals it step by step and checks the student's answers; it is never shown at once):
  "problem": {{"given": [{{"symbol": "$m$", "value": "2.0 kg"}}],
    "parts": [{{"id": "a", "prompt": "what part (a) asks", "steps": ["3-5 staged steps, each one step further than the last; the last one finishes the derivation"],
               "answer": 4.2, "unit": "m/s", "tolerance": 0.02, "compute": "arithmetic expression for the answer from the given numbers"}}],
    "pitfalls": ["2-4 mistakes students make on this problem"]}}
  One entry per part (a, b, c, ...; a single part "a" if the problem has none). "answer" is a plain number; use null and
  an empty compute for a part that has no numeric answer. compute may use numbers, + - * / ** ( ), pi, e, sqrt, exp,
  ln, log10, sin, cos, tan, asin, acos, atan; NEVER '^'."""

REFERENCE_SYLLABUS = """
- REFERENCE-ONLY MATERIALS: the uploaded problems only show the topic, the difficulty and the kind of assignment the
  student faces. Plan classes that teach those topics; never plan a class around solving one of the uploaded problems.
"""

REFERENCE_CLASS = (
    "REFERENCE-ONLY MATERIALS: the student's uploads show the topic, difficulty and type of assignment they face. Write "
    "ORIGINAL problems, examples, quiz and practice items in that style, with different situations, wording and numbers. "
    "Never copy, paraphrase or solve the uploaded problems."
)


def mode_rules(course: Dict[str, Any]) -> str:
    if course.get("mode") == "problem_sprint":
        return SPRINT_SYLLABUS.format(max_problems=MAX_PROBLEMS)
    if course.get("mode") == "thematic_reference":
        return REFERENCE_SYLLABUS.strip("\n")
    return ""


def class_adjustment(course: Dict[str, Any], klass: Dict[str, Any]) -> str:
    meta = klass.get("meta") or {}
    if course.get("mode") == "thematic_reference":
        return REFERENCE_CLASS
    if meta.get("kind") == "problem":
        return PROBLEM_CLASS.format(index=meta.get("problemIndex") or "?",
                                    statement=meta.get("statement") or klass.get("title", "")).strip("\n")
    return PRIMER_CLASS


# ---------------------------------------------------------------------------------------------------------- planning
def sprint_meta(kind: str, index: int = 0, statement: str = "") -> Dict[str, Any]:
    """Class meta for sprint classes, separate from semester_meta: kind primer|problem, problemIndex, the statement."""
    if kind != "problem":
        return {"kind": "primer"}
    return {"kind": "problem", "problemIndex": index, "statement": str(statement or "").strip()[:4000]}


def build_outline(plan: Any, concept_ids: set) -> List[Dict[str, Any]]:
    """Primer + one class per problem (at most MAX_PROBLEMS). Empty when the plan found no problems."""
    plan = plan if isinstance(plan, dict) else {}
    problems = [p for p in plan.get("problems") or [] if isinstance(p, dict) and (p.get("statement") or p.get("title"))]
    if not problems:
        return []

    def keep(item, title):
        return {"title": str(item.get("title") or title)[:120],
                "concepts": [c for c in (item.get("concepts") or []) if c in concept_ids],
                "objectives": [str(o) for o in (item.get("objectives") or [])][:5]}

    primer = plan.get("primer") if isinstance(plan.get("primer"), dict) else {}
    outline = [{**keep(primer, "What you need for these problems"), "meta": sprint_meta("primer")}]
    if not outline[0]["concepts"]:
        outline[0]["concepts"] = sorted(concept_ids)
    for i, p in enumerate(problems[:MAX_PROBLEMS], start=1):
        outline.append({**keep(p, f"Problem {i}"), "meta": sprint_meta("problem", i, p.get("statement") or p.get("title"))})
    return outline


def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def split_problem(raw: Any, statement: str = "") -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """The model's "problem" object -> (public part for the topic JSON, private part for classes.meta.sprint).
    The topic gets the statement, given values, pitfalls and each part's prompt; steps and answers stay private."""
    raw = raw if isinstance(raw, dict) else {}
    given = [{"symbol": str(g.get("symbol") or "")[:60], "value": str(g.get("value") or "")[:120]}
             for g in raw.get("given") or [] if isinstance(g, dict) and (g.get("symbol") or g.get("value"))][:12]
    pitfalls = [str(p)[:400] for p in raw.get("pitfalls") or [] if isinstance(p, str) and p.strip()][:5]
    parts, seen = [], set()
    for p in raw.get("parts") or []:
        if not isinstance(p, dict) or len(parts) >= MAX_PARTS:
            continue
        steps = [str(s)[:1200] for s in p.get("steps") or [] if isinstance(s, str) and s.strip()][:MAX_STEPS]
        if not steps:
            continue  # nothing to reveal: the part could only leak its answer
        pid = str(p.get("id") or "").strip().lower().strip("()")[:1]
        if pid not in PART_IDS or pid in seen:
            pid = next(c for c in PART_IDS if c not in seen)
        seen.add(pid)
        tol = _num(p.get("tolerance"))
        parts.append({"id": pid, "prompt": str(p.get("prompt") or f"Part ({pid})")[:600], "steps": steps,
                      "answer": _num(p.get("answer")), "unit": str(p.get("unit") or "").strip()[:30],
                      "tolerance": tol if tol is not None and 0 < tol <= 0.2 else DEFAULT_TOLERANCE,
                      "compute": str(p.get("compute") or "")[:300]})
    public = {"statement": str(statement or "")[:4000], "given": given, "pitfalls": pitfalls,
              "parts": [{"id": p["id"], "prompt": p["prompt"]} for p in parts]}
    return public, {"given": given, "pitfalls": pitfalls, "parts": parts}


def apply_checks(parts: List[Dict[str, Any]], oks: List[bool]) -> None:
    """After recheck_numeric: a part keeps an automatic check only if its answer was recomputed; compute is dropped."""
    for p, ok in zip(parts, oks):
        p["checked"] = bool(ok)
        p.pop("compute", None)
        if not ok:
            p["answer"] = None


def drop_answer_echoes(practice: List[Dict[str, Any]], parts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Numeric practice items whose answer equals one of the problem's answers would give it away."""
    answers = [p["answer"] for p in parts if _num(p.get("answer")) is not None]
    out = []
    for item in practice:
        a = _num(item.get("answer")) if item.get("type") == "numeric" else None
        if a is not None and any(abs(a - b) <= max(abs(b) * 0.02, 1e-9) for b in answers):
            continue
        out.append(item)
    return out


# ------------------------------------------------------------------------------------------------- reference overlap
_WORD_RE = re.compile(r"\w+")


def ngrams(text: str, n: int = NGRAM) -> set:
    words = _WORD_RE.findall((text or "").lower())
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def _strings(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def copied_share(item: Dict[str, Any], material_grams: set) -> float:
    grams = ngrams(" ".join(_strings({k: v for k, v in item.items() if k not in ("id", "type")})))
    return len(grams & material_grams) / len(grams) if grams else 0.0


def drop_copied(practice: List[Dict[str, Any]], materials: str) -> Tuple[List[Dict[str, Any]], int]:
    """Reference-only courses: drop practice items with >= 30% of their word 6-grams found in the materials."""
    grams = ngrams(materials)
    if not grams:
        return practice, 0
    kept = [p for p in practice if copied_share(p, grams) < COPY_SHARE]
    return kept, len(practice) - len(kept)


# ------------------------------------------------------------------------------------------------------ public views
def _state(meta: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    s = meta.get("sprint") or {}
    return s.get("revealed") or {}, s.get("attempts") or {}, meta.get("solved") or {}


def public_part(p: Dict[str, Any], revealed: int, attempts: int, solved: bool) -> Dict[str, Any]:
    n = len(p.get("steps") or [])
    r = min(max(int(revealed or 0), 0), n)
    out = {"id": p["id"], "prompt": p.get("prompt", ""), "stepCount": n, "steps": (p.get("steps") or [])[:r],
           "revealed": r, "attempts": int(attempts or 0), "solved": bool(solved), "autoCheck": bool(p.get("checked"))}
    if out["attempts"] >= 1 or (n and r >= n):
        out["unit"] = p.get("unit", "")
        if p.get("checked"):
            out["answer"], out["tolerance"] = p.get("answer"), p.get("tolerance")
    return out


def public_class(klass: Dict[str, Any]) -> Dict[str, Any]:
    """A class row as any client may see it: meta.sprint holds only what the student has unlocked."""
    meta = klass.get("meta") or {}
    if not isinstance(meta, dict) or "sprint" not in meta:
        return klass
    revealed, attempts, solved = _state(meta)
    private = meta.get("sprint") or {}
    view = {"given": private.get("given") or [], "pitfalls": private.get("pitfalls") or [],
            "parts": [public_part(p, revealed.get(p["id"], 0), attempts.get(p["id"], 0), solved.get(p["id"]))
                      for p in private.get("parts") or []]}
    return {**klass, "meta": {**meta, "sprint": view}}


def tutor_context(klass: Optional[Dict[str, Any]]) -> str:
    """What the lesson tutor may use in a sprint class: the parts and only the steps the student already revealed."""
    if not klass or "sprint" not in (klass.get("meta") or {}):
        return ""
    view = public_class(klass)["meta"]["sprint"]
    lines = ["\nPROBLEM SPRINT: the student is working through their own problem. You may discuss only the steps listed "
             "below as revealed; never give a later step or a final answer that is not listed."]
    for p in view["parts"]:
        lines.append(f"Part ({p['id']}): {p['prompt']} [{p['revealed']} of {p['stepCount']} steps revealed"
                     + (", solved" if p["solved"] else "") + "]")
        lines += [f"  step {i}: {s}" for i, s in enumerate(p["steps"], start=1)]
        if "answer" in p:
            lines.append(f"  answer (already shown to the student): {p['answer']} {p.get('unit', '')}".rstrip())
    return "\n".join(lines)


def progress(classes: List[Dict[str, Any]]) -> Tuple[int, int, bool]:
    """(problems done, problems, all done). A problem is done when every part is solved; a problem class whose parts
    could not be built has nothing to check and counts as done once it is written."""
    problems = [k for k in classes if (k.get("meta") or {}).get("kind") == "problem"]
    done = 0
    for k in problems:
        meta = k.get("meta") or {}
        parts = (meta.get("sprint") or {}).get("parts") or []
        solved = meta.get("solved") or {}
        if k.get("status") == "ready" and all(solved.get(p["id"]) for p in parts):
            done += 1
    return done, len(problems), bool(problems) and done == len(problems)


def course_summary(course: Dict[str, Any], classes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if course.get("mode") != "problem_sprint":
        return None
    done, total, complete = progress(classes)
    cleared = course.get("cleared_at")
    return {"problems": total, "done": done, "complete": complete, "autoCleanup": bool(course.get("auto_cleanup")),
            "cleared": course.get("status") == "cleared", "clearedAt": cleared,
            "undoUntil": cleared + retain_days() * 86400 if cleared else None}


# ------------------------------------------------------------------------------------------------------ answer check
_UNIT_ALIASES = {"sec": "s", "secs": "s", "second": "s", "seconds": "s", "hr": "h", "hrs": "h", "hour": "h", "hours": "h",
                 "meter": "m", "meters": "m", "metre": "m", "metres": "m", "kilogram": "kg", "kilograms": "kg",
                 "newton": "n", "newtons": "n", "joule": "j", "joules": "j", "watt": "w", "watts": "w", "°": "deg",
                 "degrees": "deg", "degree": "deg"}


def norm_unit(unit: str) -> str:
    u = (unit or "").replace("\\text", "").replace("\\mathrm", "").replace("\\,", "")
    u = re.sub(r"[\s${}]", "", u).lower().replace("**", "^").replace("·", "*").replace("⋅", "*")
    return _UNIT_ALIASES.get(u, u)


def check_answer(part: Dict[str, Any], value: float, unit: str) -> Dict[str, Any]:
    """correct | unit (number right, unit not) | sign | magnitude (off by a power of ten) | wrong. The expected
    value is never in the message: the answer is shown separately once the attempt is recorded."""
    expected, tol = part["answer"], part.get("tolerance") or DEFAULT_TOLERANCE
    close = lambda v: abs(v - expected) <= max(abs(expected) * tol, 1e-9)  # noqa: E731
    want = norm_unit(part.get("unit", ""))
    if close(value):
        if want and unit.strip() and norm_unit(unit) != want:
            return {"verdict": "unit", "correct": False, "message": "The number is right; check the unit."}
        note = " Remember the unit." if want and not unit.strip() else ""
        return {"verdict": "correct", "correct": True, "message": "Correct." + note}
    if expected and close(-value):
        return {"verdict": "sign", "correct": False, "message": "Right size, wrong sign: check the direction you chose as positive."}
    if expected and value:
        k = math.log10(abs(value / expected))
        if abs(k - round(k)) < 0.01 and 1 <= abs(round(k)) <= 12:
            return {"verdict": "magnitude", "correct": False,
                    "message": f"Off by a factor of 10^{abs(round(k))}: check unit conversions and prefixes."}
    return {"verdict": "wrong", "correct": False, "message": "Not yet. Compare your work with the next step."}


# ------------------------------------------------------------------------------------------------------------ routes
class RevealRequest(BaseModel):
    part: str = Field(max_length=2)
    step: int


class CheckRequest(BaseModel):
    part: str = Field(max_length=2)
    value: float
    unit: Optional[str] = Field(default="", max_length=40)


_lock = threading.Lock()  # read-modify-write of one class's meta (double clicks, two tabs)


def _sprint_class(course_id: str, seq: int) -> Dict[str, Any]:
    klass = next((k for k in db.list_classes(course_id) if k["seq"] == seq), None)
    if not klass or "sprint" not in (klass.get("meta") or {}):
        raise HTTPException(status_code=404, detail="This class has no problem to work through.")
    return klass


def _part(klass: Dict[str, Any], part_id: str) -> Dict[str, Any]:
    part = next((p for p in klass["meta"]["sprint"].get("parts") or [] if p["id"] == (part_id or "").lower()), None)
    if not part:
        raise HTTPException(status_code=404, detail="Part not found")
    return part


def finish_if_done(course_id: str, newly_solved: bool = True,
                   on_cleared: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Every problem done: an auto-clean sprint is soft-cleared (hidden, purged after retain_days, undoable until then).
    Only when this request newly solved a part, so revealing a step after Undo never clears it again; db.clear_course
    re-checks auto_cleanup and status in its UPDATE, so a /keep or /restore that lands first wins."""
    course = db.get_course(course_id)
    _, total, complete = progress(db.list_classes(course_id))
    out = {"complete": complete, "cleared": False, "undoUntil": None}
    at = db.clear_course(course_id) if newly_solved and complete and course and course.get("auto_cleanup") else None
    if at is not None:
        out.update(cleared=True, undoUntil=at + retain_days() * 86400)
        if on_cleared:
            on_cleared(course_id)
        return out
    course = db.get_course(course_id)
    if course and course["status"] == "cleared":
        out.update(cleared=True, undoUntil=(course.get("cleared_at") or time.time()) + retain_days() * 86400)
    return out


def purge_cleared(delete_course: Callable[[str], Any], now: Optional[float] = None) -> List[str]:
    """Hard-deletes cleared auto-clean sprints older than retain_days (db.cleared_due filters them)."""
    gone = []
    for cid in db.cleared_due((now or time.time()) - retain_days() * 86400):
        delete_course(cid)
        gone.append(cid)
    return gone


def build_router(*, rate_limit: Callable[[str], None], require_course: Callable[[str], Dict[str, Any]],
                 public_course: Callable[[Dict[str, Any]], Dict[str, Any]],
                 course_event: Callable[[str], None], topics_changed: Callable[[], None] = lambda: None) -> APIRouter:
    """require_course raises 404 for a missing course or, with accounts on, someone else's (cleared ones included).
    topics_changed runs when a sprint is cleared, kept or restored: its lessons leave or rejoin the library."""
    router = APIRouter()

    def reply(course_id: str, **extra):
        course_event(course_id)
        return {"course": public_course(db.get_course(course_id)), **extra}

    @router.post("/api/courses/{course_id}/classes/{seq}/reveal")
    def reveal_step(course_id: str, seq: int, body: RevealRequest):
        """Reveals the next step of one part (steps open in order, one per call)."""
        rate_limit("quiz")
        require_course(course_id)
        with _lock:
            klass = _sprint_class(course_id, seq)
            part = _part(klass, body.part)
            meta = klass["meta"]
            revealed = dict(meta["sprint"].get("revealed") or {})
            have, n = int(revealed.get(part["id"], 0)), len(part["steps"])
            if not 1 <= body.step <= n:
                raise HTTPException(status_code=422, detail=f"This part has {n} steps.")
            if body.step > have + 1:
                raise HTTPException(status_code=409, detail="Steps open in order: reveal the earlier step first.")
            revealed[part["id"]] = max(have, body.step)
            solved = dict(meta.get("solved") or {})
            newly = False
            if not part.get("checked") and revealed[part["id"]] >= n and not solved.get(part["id"]):
                solved[part["id"]] = newly = True  # no automatic check: working through every step finishes it
            db.update_class(klass["id"], meta={**meta, "sprint": {**meta["sprint"], "revealed": revealed}, "solved": solved})
        return reply(course_id, finished=finish_if_done(course_id, newly, lambda _cid: topics_changed()))

    @router.post("/api/courses/{course_id}/classes/{seq}/check")
    def check_part(course_id: str, seq: int, body: CheckRequest):
        """Grades one numeric answer on the server; the attempt is recorded, which unlocks the part's answer."""
        rate_limit("quiz")
        require_course(course_id)
        if not math.isfinite(body.value):
            raise HTTPException(status_code=422, detail="Enter a number.")
        with _lock:
            klass = _sprint_class(course_id, seq)
            part = _part(klass, body.part)
            if not part.get("checked") or part.get("answer") is None:
                raise HTTPException(status_code=409, detail="This part has no automatic check: compare your work with its steps.")
            result = check_answer(part, body.value, body.unit or "")
            meta = klass["meta"]
            attempts = dict(meta["sprint"].get("attempts") or {})
            attempts[part["id"]] = int(attempts.get(part["id"], 0)) + 1
            solved = dict(meta.get("solved") or {})
            newly = bool(result["correct"] and not solved.get(part["id"]))
            if result["correct"]:
                solved[part["id"]] = True
            db.update_class(klass["id"], meta={**meta, "sprint": {**meta["sprint"], "attempts": attempts}, "solved": solved})
        return reply(course_id, result=result, finished=finish_if_done(course_id, newly, lambda _cid: topics_changed()))

    @router.post("/api/courses/{course_id}/keep")
    def keep_course(course_id: str):
        """Keep a sprint in My courses for good: no auto-clean, and back from "cleared" if it already was."""
        rate_limit("quiz")
        course = require_course(course_id)
        if course.get("mode") != "problem_sprint":
            raise HTTPException(status_code=409, detail="Only problem sprints are cleaned up automatically.")
        db.restore_course(course_id)
        topics_changed()  # it may have been cleared a moment ago: the library shows its lessons again
        return reply(course_id)

    @router.post("/api/courses/{course_id}/restore")
    def restore_course(course_id: str):
        """Undo a clear: the sprint is back in My courses with auto-clean off (Undo is the same as keep), so it stays."""
        rate_limit("quiz")
        require_course(course_id)
        if not db.restore_course(course_id, only_cleared=True):  # one statement: a concurrent restore cannot run twice
            raise HTTPException(status_code=409, detail="This course is not cleared.")
        topics_changed()
        return reply(course_id)

    return router
