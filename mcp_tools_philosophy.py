"""
Philosophy and logic tools for the &.edu MCP server: truth tables, validity checks, syllogisms,
Fitch-style proof steps, argument mapping, fallacy identification, and full philosophy unit creation.
Imported by mcp_server.py; validates logic items via logic_engine before submitting to the backend.
"""
import re
import unicodedata
from typing import Any, Dict, List, Optional

import logic_engine
import practice_philosophy


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")[:70] or "philosophy-unit"


def _item(a: Dict[str, Any], default_prompt: str, **fields) -> Dict[str, Any]:
    return {
        "prompt": a.get("prompt") or default_prompt,
        "explanation": a.get("explanation", ""),
        **{k: v for k, v in fields.items() if v not in (None, "", [])},
    }


def philosophy_unit_topic(a: Dict[str, Any]) -> Dict[str, Any]:
    title = str(a.get("title", "Philosophy Unit")).strip()
    topic_id = a.get("id") or _slug(title)
    summary = a.get("summary") or f"Introductory logic and philosophical inquiry into {title}."
    category = a.get("category") or "Philosophy & Logic"
    difficulty = a.get("difficulty") or "Introductory"
    md = a.get("markdown_content") or f"# {title}\n\n{summary}\n\n## Core Concepts\n\nCareful logical analysis of claims, premises, and conclusions."

    # Validate and clean any provided practice exercises
    raw_practice = a.get("exercises") or []
    cleaned_practice = []
    for i, p in enumerate(raw_practice):
        ptype = p.get("type")
        fn = practice_philosophy.NORMALIZERS.get(ptype)
        base = {
            "id": f"p{i + 1}",
            "type": ptype,
            "prompt": p.get("prompt") or "Complete the exercise.",
            "explanation": p.get("explanation", ""),
            "concept": None,
        }
        item = fn(p, base) if fn else None
        if item:
            cleaned_practice.append(item)

    cards = []
    for fc in a.get("flashcards") or []:
        if isinstance(fc, dict) and fc.get("front") and fc.get("back"):
            cards.append({"front": str(fc["front"]).strip()[:200], "back": str(fc["back"]).strip()[:400]})

    return {
        "id": topic_id,
        "title": title,
        "category": category,
        "difficulty": difficulty,
        "summary": summary,
        "workspace": "philosophy",
        "markdownContent": md,
        "practice": cleaned_practice,
        "flashcards": cards,
        "quiz": a.get("quiz") or [],
    }


def tools(call, q, S, STR, OBJ, ARR):
    practice = lambda tid, it: call("POST", f"/api/topics/{q(tid)}/practice", {"items": [it]})
    EXPL = lambda: STR("explanation shown after answering", optional=True)
    STRS = lambda d, **k: {"type": "array", "items": {"type": "string"}, "description": d, **k}

    def add_tt(a):
        chk = logic_engine.check({"op": "truth_table", "formulas": a["formulas"]})
        if not chk["ok"]:
            return {"error": chk["error"]}
        it = _item(a, "Complete the truth table for the given formula(s).", type="truth_table", formulas=a["formulas"])
        return practice(a["topic_id"], it)

    def add_val(a):
        chk = logic_engine.check({"op": "validity", "premises": a["premises"], "conclusion": a["conclusion"]})
        if not chk["ok"]:
            return {"error": chk["error"]}
        it = _item(
            a,
            "Determine whether the argument is valid or invalid.",
            type="validity",
            premises=a["premises"],
            conclusion=a["conclusion"],
        )
        return practice(a["topic_id"], it)

    def add_syl(a):
        spec = {"form": a["form"]} if a.get("form") else {"major": a.get("major"), "minor": a.get("minor"), "conclusion": a.get("conclusion")}
        chk = logic_engine.check({"op": "syllogism", "reading": a.get("reading", "boolean"), **spec})
        if not chk["ok"]:
            return {"error": chk["error"]}
        it = _item(
            a,
            "Evaluate the validity and form of this categorical syllogism.",
            type="syllogism",
            form=a.get("form"),
            major=a.get("major"),
            minor=a.get("minor"),
            conclusion=a.get("conclusion"),
            reading=a.get("reading", "boolean"),
        )
        return practice(a["topic_id"], it)

    def add_proof(a):
        chk = logic_engine.check({
            "op": "proof",
            "premises": a.get("premises", []),
            "goal": a.get("goal"),
            "lines": a["lines"],
            "rules": a.get("rules", "derived"),
        })
        if not chk["ok"]:
            return {"error": chk["error"]}
        it = _item(
            a,
            "Complete or verify the proof steps to reach the conclusion.",
            type="proof_steps",
            premises=a.get("premises", []),
            goal=a.get("goal"),
            lines=a["lines"],
            rules=a.get("rules", "derived"),
        )
        return practice(a["topic_id"], it)

    def add_argmap(a):
        chk = logic_engine.check({"op": "argmap", "map": a["map"]})
        if not chk["ok"]:
            return {"error": chk["error"]}
        it = _item(
            a,
            "Analyze the argument map and identify structural weaknesses or valid inferences.",
            type="argument_map",
            map=a["map"],
        )
        return practice(a["topic_id"], it)

    def add_fallacy(a):
        it = _item(
            a,
            "Identify the fallacy in this argument.",
            type="fallacy_id",
            argument=a["argument"],
            options=a["options"],
            answer=a["answer"],
            fallacy_type=a.get("fallacy_type"),
            why=a.get("why"),
        )
        return practice(a["topic_id"], it)

    def add_parts(a):
        it = _item(
            a,
            a.get("target") or "Identify the requested argument component.",
            type="spot_parts",
            text=a["text"],
            options=a["options"],
            answer=a["answer"],
            target=a.get("target"),
        )
        return practice(a["topic_id"], it)

    return [
        (
            "add_truth_table",
            "Add a truth table practice exercise to a topic. The student completes truth assignments and values for 1-3 propositional formulas (at most 4 variables). Validated deterministically via logic_engine.",
            S(
                topic_id=STR("topic id"),
                formulas=STRS("1-3 propositional formulas, e.g. ['P -> Q', '~P | Q']"),
                prompt=STR("instruction prompt", optional=True),
                explanation=EXPL(),
            ),
            add_tt,
        ),
        (
            "add_validity",
            "Add a propositional validity exercise to a topic. The student evaluates whether conclusion follows from premises, and identifies counterexamples if invalid. Validated deterministically via logic_engine.",
            S(
                topic_id=STR("topic id"),
                premises=STRS("1-5 propositional premises"),
                conclusion=STR("conclusion formula"),
                prompt=STR("instruction prompt", optional=True),
                explanation=EXPL(),
            ),
            add_val,
        ),
        (
            "add_syllogism",
            "Add a categorical syllogism exercise to a topic. Specify form ('AAA-1' ... 'EAO-4') or categorical statements {type: A|E|I|O, subject, predicate}. Validated deterministically via logic_engine.",
            S(
                topic_id=STR("topic id"),
                form=STR("form such as 'AAA-1', 'EIO-2'", optional=True),
                major=OBJ("major premise {type, subject, predicate}", optional=True),
                minor=OBJ("minor premise {type, subject, predicate}", optional=True),
                conclusion=OBJ("conclusion statement {type, subject, predicate}", optional=True),
                reading=STR("reading: 'boolean' (default) | 'aristotelian'", optional=True),
                prompt=STR("instruction prompt", optional=True),
                explanation=EXPL(),
            ),
            add_syl,
        ),
        (
            "add_proof_steps",
            "Add a Fitch-style natural deduction proof exercise to a topic (forall x: Calgary rules). Validated deterministically via logic_engine.",
            S(
                topic_id=STR("topic id"),
                lines=ARR("[{formula, rule, cites?: [int|'i-j'], depth?: int}] proof lines"),
                premises=STRS("premise formulas", optional=True),
                goal=STR("goal formula", optional=True),
                rules=STR("rules: 'derived' (default) | 'basic'", optional=True),
                prompt=STR("instruction prompt", optional=True),
                explanation=EXPL(),
            ),
            add_proof,
        ),
        (
            "add_argument_map",
            "Add an argument map exercise: claims, support/attack relations, and flaw detection (circularity, unsupported claims, invalid inferences). Validated deterministically via logic_engine.",
            S(
                topic_id=STR("topic id"),
                map=OBJ("{claims: [{id, text, role?, kind?, formal?}], edges: [{from: [ids], to: id, type: supports|attacks}], main?: id}"),
                prompt=STR("instruction prompt", optional=True),
                explanation=EXPL(),
            ),
            add_argmap,
        ),
        (
            "add_fallacy_exercise",
            "Add a fallacy identification exercise to a topic. The student identifies formal or informal fallacies from 2-5 options.",
            S(
                topic_id=STR("topic id"),
                argument=STR("passage containing fallacious reasoning"),
                options=STRS("2-5 distinct fallacy options"),
                answer=STR("the correct fallacy name (one of options)"),
                fallacy_type=STR("formal | informal", optional=True),
                why=STR("why this fallacy applies", optional=True),
                prompt=STR("instruction prompt", optional=True),
                explanation=EXPL(),
            ),
            add_fallacy,
        ),
        (
            "add_spot_parts",
            "Add an argument structure identification exercise to a topic (identifying subject/predicate/middle terms, premises, conclusion, or missing assumptions).",
            S(
                topic_id=STR("topic id"),
                text=STR("argument or statement text"),
                options=STRS("2-5 candidate parts/roles/terms"),
                answer=STR("the correct answer (one of options)"),
                target=STR("what to identify e.g. 'Identify the main conclusion'", optional=True),
                prompt=STR("instruction prompt", optional=True),
                explanation=EXPL(),
            ),
            add_parts,
        ),
        (
            "build_philosophy_unit",
            "Create a whole philosophy topic offline (no model quota) with markdown content, flashcards, and logic practice exercises.",
            S(
                title=STR("unit title"),
                id=STR("kebab-case id (default from title)", optional=True),
                summary=STR("summary of the unit", optional=True),
                category=STR("category, default 'Philosophy & Logic'", optional=True),
                difficulty=STR("Introductory | Intermediate | Advanced", optional=True),
                markdown_content=STR("lesson markdown text", optional=True),
                exercises=ARR("list of practice items to validate and include", optional=True),
                flashcards=ARR("[{front, back}] flashcards", optional=True),
                quiz=ARR("quiz questions", optional=True),
            ),
            lambda a: call("POST", "/api/topics", philosophy_unit_topic(a)),
        ),
    ]
