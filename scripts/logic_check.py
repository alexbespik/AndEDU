"""
Command line for the deterministic logic engine (logic_engine.py); prints JSON.

    python3 scripts/logic_check.py parse "~P & Q -> R"
    python3 scripts/logic_check.py table "P -> Q" "~P | Q"
    python3 scripts/logic_check.py valid --premises "P -> Q" "Q" --conclusion "P"
    python3 scripts/logic_check.py classify "P | ~P"
    python3 scripts/logic_check.py equiv "P -> Q" "~P | Q"
    python3 scripts/logic_check.py forms --premises "Rain -> Wet" "Wet" --conclusion "Rain"
    python3 scripts/logic_check.py syllogism AAA-1 [--reading aristotelian]
    python3 scripts/logic_check.py proof proof.json          (- reads stdin)
    python3 scripts/logic_check.py argmap map.json
    python3 scripts/logic_check.py request request.json       (any engine request, {"op": ...})
    python3 scripts/logic_check.py guide

Exit status: 0 = valid / fine, 1 = the argument, proof or map has a problem, 2 = the input could not be read.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logic_engine  # noqa: E402


def _load(path):
    try:
        text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
        return json.loads(text)
    except (OSError, ValueError) as e:
        raise SystemExit(json.dumps({"ok": False, "error": {"code": "bad_file", "message": str(e)}})) from None


def _request(args):
    cmd = args.cmd
    if cmd == "parse":
        return {"op": "parse", "formula": args.formula}
    if cmd == "table":
        return {"op": "truth_table", "formulas": args.formulas}
    if cmd in ("valid", "forms"):
        return {"op": "validity" if cmd == "valid" else "forms", "premises": args.premises, "conclusion": args.conclusion}
    if cmd == "classify":
        return {"op": "classify", "formula": args.formula}
    if cmd == "equiv":
        return {"op": "equivalence", "a": args.a, "b": args.b}
    if cmd == "syllogism":
        return {"op": "syllogism", "form": args.form, "reading": args.reading}
    if cmd == "proof":
        return {"op": "proof", **_load(args.file)}
    if cmd == "argmap":
        return {"op": "argmap", "map": _load(args.file)}
    if cmd == "request":
        return _load(args.file)
    return {"op": "guide"}


def _status(out):
    if not out["ok"]:
        return 2
    r = out["result"]
    if r.get("valid") is False or r.get("equivalent") is False or r.get("findings"):
        return 1
    if "complete" in r and r.get("goal") and not r["complete"]:
        return 1
    return 0


def main(argv=None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--compact", action="store_true", help="one-line JSON")
    ap = argparse.ArgumentParser(description="Deterministic logic checks (no model).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    _add = sub.add_parser
    sub.add_parser = lambda name: _add(name, parents=[common])  # --compact after any command
    sub.add_parser("parse").add_argument("formula")
    sub.add_parser("table").add_argument("formulas", nargs="+")
    for name in ("valid", "forms"):
        p = sub.add_parser(name)
        p.add_argument("--premises", nargs="*", default=[])
        p.add_argument("--conclusion", required=True)
    sub.add_parser("classify").add_argument("formula")
    p = sub.add_parser("equiv")
    p.add_argument("a")
    p.add_argument("b")
    p = sub.add_parser("syllogism")
    p.add_argument("form")
    p.add_argument("--reading", default="boolean", choices=["boolean", "aristotelian"])
    for name in ("proof", "argmap", "request"):
        sub.add_parser(name).add_argument("file")
    sub.add_parser("guide")
    args = ap.parse_args(argv)
    out = logic_engine.check(_request(args))
    if args.cmd == "guide" and out["ok"]:
        print(out["result"]["guide"])
        return 0
    print(json.dumps(out, ensure_ascii=False, indent=None if args.compact else 2))
    return _status(out)


if __name__ == "__main__":
    sys.exit(main())
