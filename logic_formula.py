"""
Propositional formulas for the Philosophy logic engine (logic_engine.py): parsing, printing, evaluation, truth
tables and validity. Deterministic and offline: no model ever judges an argument, so the same input always gets the
same verdict.

Formulas are tuples: ("var", name), ("bot",), ("not", a), ("and", a, b), ("or", a, b), ("imp", a, b), ("iff", a, b).
Accepted notation (any mix):
- not: ~ ! ¬ not      and: & ∧ /\\ and      or: | ∨ \\/ or      implies: -> → => implies      iff: <-> ↔ <=> iff
- falsum: ⊥ or _|_    statement letters: a capital letter, then letters, digits or _ (P, Q2, Rain)
Binding, tightest first: not, and, or, implies, iff. `and`/`or` group to the left, `->` to the right
(A -> B -> C is A -> (B -> C)), and `<->` does not chain: write (A <-> B) <-> C.
"""
from itertools import product
from typing import Any, Dict, List, Optional, Sequence, Tuple

MAX_INPUT_LEN = 500  # characters per formula
MAX_VARS = 8         # statement letters per truth table (2^8 = 256 rows)
MAX_DEPTH = 50       # nesting of a formula
MAX_PREMISES = 20

Formula = Tuple[Any, ...]
BOT: Formula = ("bot",)


class LogicError(ValueError):
    """Bad input, with a stable code and, for parse errors, the position (0-based) and length of the culprit."""
    def __init__(self, code: str, message: str, pos: Optional[int] = None, length: int = 1):
        super().__init__(message)
        self.code, self.message, self.pos, self.length = code, message, pos, length

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.pos is not None:
            out.update(pos=self.pos, length=self.length)
        return out


# ---- tokens ----
_SYMBOLS = [  # longest first
    ("<->", "iff"), ("<=>", "iff"), ("_|_", "bot"), ("->", "imp"), ("=>", "imp"), ("/\\", "and"), ("\\/", "or"),
    ("~", "not"), ("!", "not"), ("¬", "not"), ("&", "and"), ("∧", "and"), ("|", "or"), ("∨", "or"),
    ("→", "imp"), ("↔", "iff"), ("⊥", "bot"), ("(", "lp"), (")", "rp"),
]
_WORDS = {"not": "not", "and": "and", "or": "or", "implies": "imp", "iff": "iff"}
_BINARY = {"and": (7, 8), "or": (5, 6), "imp": (4, 3), "iff": (1, 2)}  # (left, right) binding power
_NAMES = {"not": "~", "and": "&", "or": "|", "imp": "->", "iff": "<->", "lp": "(", "rp": ")"}


def _tokens(text: str) -> List[Tuple[str, str, int, int]]:
    out, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        for sym, kind in _SYMBOLS:
            if text.startswith(sym, i):
                out.append((kind, sym, i, len(sym)))
                i += len(sym)
                break
        else:
            if ch.isalpha() and ch.isascii():
                j = i
                while j < n and (text[j].isascii() and (text[j].isalnum() or text[j] == "_")):
                    j += 1
                word = text[i:j]
                if word.lower() in _WORDS:
                    out.append((_WORDS[word.lower()], word, i, j - i))
                elif word.lower() in ("if", "then"):
                    raise LogicError("unsupported_word", "Write 'if A then B' as A -> B.", i, j - i)
                elif word[0].isupper():
                    out.append(("var", word, i, j - i))
                else:
                    raise LogicError("bad_letter", f"Statement letters start with a capital letter: '{word}'.", i, j - i)
                i = j
            else:
                raise LogicError("bad_character", f"Unexpected character '{ch}'.", i, 1)
    out.append(("end", "", n, 0))
    return out


class _Parser:
    def __init__(self, text: str):
        self.toks = _tokens(text)
        self.i = 0

    def peek(self):
        return self.toks[self.i]

    def take(self):
        tok = self.toks[self.i]
        self.i += 1
        return tok

    def expr(self, min_bp: int, depth: int) -> Formula:
        if depth > MAX_DEPTH:
            tok = self.peek()
            raise LogicError("too_deep", f"The formula nests more than {MAX_DEPTH} levels.", tok[2], tok[3])
        kind, text, pos, length = self.take()
        if kind == "not":
            lhs: Formula = ("not", self.expr(9, depth + 1))
        elif kind == "lp":
            lhs = self.expr(0, depth + 1)
            close = self.take()
            if close[0] != "rp":
                raise LogicError("unbalanced", "A '(' is not closed.", pos, length)
        elif kind == "var":
            lhs = ("var", text)
        elif kind == "bot":
            lhs = BOT
        elif kind == "end":
            raise LogicError("unexpected_end", "The formula ends where a statement was expected.", pos, 0)
        elif kind == "rp":
            raise LogicError("unbalanced", "This ')' has no matching '('.", pos, length)
        else:
            raise LogicError("missing_operand", f"'{text}' needs a statement on its left.", pos, length)
        while True:
            kind, text, pos, length = self.peek()
            if kind not in _BINARY:
                break
            left_bp, right_bp = _BINARY[kind]
            if left_bp < min_bp:
                break
            self.take()
            lhs = (kind, lhs, self.expr(right_bp, depth + 1))
            if kind == "iff" and self.peek()[0] == "iff":
                nxt = self.peek()
                raise LogicError("chained_iff", "'<->' does not chain: add parentheses, as in (A <-> B) <-> C.", nxt[2], nxt[3])
        return lhs


def parse(text: Any) -> Formula:
    """A formula from text; LogicError (with pos) when it is not one."""
    if not isinstance(text, str):
        raise LogicError("not_text", "A formula must be text.")
    if len(text) > MAX_INPUT_LEN:
        raise LogicError("too_long", f"A formula may have at most {MAX_INPUT_LEN} characters.")
    if not text.strip():
        raise LogicError("empty", "The formula is empty.")
    p = _Parser(text)
    node = p.expr(0, 0)
    kind, tok, pos, length = p.peek()
    if kind != "end":
        if kind == "rp":
            raise LogicError("unbalanced", "This ')' has no matching '('.", pos, length)
        raise LogicError("missing_connective", f"A connective is missing before '{tok}'.", pos, length)
    return node


_PREC = {"iff": 1, "imp": 2, "or": 3, "and": 4, "not": 5, "var": 6, "bot": 6}
_ASCII = {"not": "~", "and": " & ", "or": " | ", "imp": " -> ", "iff": " <-> ", "bot": "_|_"}
_UNICODE = {"not": "¬", "and": " ∧ ", "or": " ∨ ", "imp": " → ", "iff": " ↔ ", "bot": "⊥"}


def to_string(f: Formula, unicode: bool = False) -> str:
    """Canonical text, with parentheses only where needed; parse(to_string(f)) == f."""
    sym = _UNICODE if unicode else _ASCII
    op = f[0]
    if op == "var":
        return f[1]
    if op == "bot":
        return sym["bot"]
    if op == "not":
        inner = to_string(f[1], unicode)
        return sym["not"] + (f"({inner})" if _PREC[f[1][0]] < _PREC["not"] else inner)
    p = _PREC[op]
    left, right = f[1], f[2]
    lp, rp = _PREC[left[0]], _PREC[right[0]]
    wrap_left = lp < p or (lp == p and op in ("imp", "iff"))        # -> groups right, <-> never chains
    wrap_right = rp < p or (rp == p and op in ("and", "or", "iff"))  # & and | group left
    ltxt, rtxt = to_string(left, unicode), to_string(right, unicode)
    return f"{'(' + ltxt + ')' if wrap_left else ltxt}{sym[op]}{'(' + rtxt + ')' if wrap_right else rtxt}"


def variables(*formulas: Formula) -> List[str]:
    """The statement letters, sorted."""
    seen, stack = set(), list(formulas)
    while stack:
        f = stack.pop()
        if f[0] == "var":
            seen.add(f[1])
        elif f[0] != "bot":
            stack.extend(f[1:])
    return sorted(seen)


def evaluate(f: Formula, env: Dict[str, bool]) -> bool:
    op = f[0]
    if op == "var":
        return env[f[1]]
    if op == "bot":
        return False
    if op == "not":
        return not evaluate(f[1], env)
    a = evaluate(f[1], env)
    b = evaluate(f[2], env)
    return {"and": a and b, "or": a or b, "imp": (not a) or b, "iff": a == b}[op]


def _rows(names: Sequence[str]):
    """Every assignment, in the usual textbook order: all true first."""
    if len(names) > MAX_VARS:
        raise LogicError("too_many_letters", f"At most {MAX_VARS} statement letters ({len(names)} given).")
    for values in product((True, False), repeat=len(names)):
        yield dict(zip(names, values))


def parse_all(texts: Any, what: str = "formulas", limit: int = MAX_PREMISES) -> List[Formula]:
    if not isinstance(texts, list):
        raise LogicError("not_a_list", f"Give the {what} as a list.")
    if len(texts) > limit:
        raise LogicError("too_many", f"At most {limit} {what}.")
    out = []
    for i, t in enumerate(texts):
        try:
            out.append(parse(t))
        except LogicError as e:
            e.message = f"{what[:-1].capitalize() if what.endswith('s') else what} {i + 1}: {e.message}"
            e.args = (e.message,)
            e.index = i
            raise
    return out


def truth_table(formulas: Sequence[Formula]) -> Dict[str, Any]:
    names = variables(*formulas)
    rows = [{"values": env, "results": [evaluate(f, env) for f in formulas]} for env in _rows(names)]
    return {"vars": names, "formulas": [to_string(f) for f in formulas], "rows": rows}


def check_validity(premises: Sequence[Formula], conclusion: Formula) -> Dict[str, Any]:
    """Valid exactly when no row makes every premise true and the conclusion false; else the first such row."""
    names = variables(*premises, conclusion)
    checked = 0
    for env in _rows(names):
        checked += 1
        if all(evaluate(p, env) for p in premises) and not evaluate(conclusion, env):
            return {"valid": False, "counterexample": env, "rows_checked": checked}
    return {"valid": True, "counterexample": None, "rows_checked": checked}


def classify(f: Formula) -> Dict[str, Any]:
    """tautology (true in every row), contradiction (false in every row) or contingent, with a witness row each way."""
    true_row = false_row = None
    for env in _rows(variables(f)):
        if evaluate(f, env):
            true_row = true_row or env
        else:
            false_row = false_row or env
        if true_row and false_row:
            break
    kind = "contingent" if true_row and false_row else "tautology" if true_row else "contradiction"
    return {"kind": kind, "true_row": true_row, "false_row": false_row}


def equivalent(a: Formula, b: Formula) -> Dict[str, Any]:
    """Equivalent when they agree in every row; else the first row where they differ."""
    for env in _rows(variables(a, b)):
        if evaluate(a, env) != evaluate(b, env):
            return {"equivalent": False, "counterexample": env}
    return {"equivalent": True, "counterexample": None}
