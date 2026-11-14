"""
AST nodes and representations for formal logic: singular terms and categorical propositions
compiling to first-order Calgary Fitch syntax.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

# Common singular names / proper nouns frequently encountered in philosophical logic
_SINGULAR_NAMES: Set[str] = {
    "socrates", "plato", "aristotle", "sherlock", "holmes", "kant", "hume",
    "descartes", "russell", "frege", "godel", "tarski", "wittgenstein",
    "john", "mary", "bob", "alice", "london", "paris", "athens", "rome",
}


def is_singular_term(name: str) -> bool:
    """Returns True if the term is an individual constant or proper name rather than a general class.
    
    Heuristics:
    - Known historical/proper names (e.g. 'Socrates', 'Sherlock').
    - Starts with 'this ' or 'that '.
    - Capitalized identifier (length > 1), excluding standard categorical variables ('All', 'Some', 'No', etc.).
    """
    if not isinstance(name, str):
        return False
    s = name.strip()
    if not s:
        return False
    low = s.lower()
    if low in _SINGULAR_NAMES:
        return True
    if low.startswith(("this ", "that ")):
        return True
    # Capitalized proper name (not single letter categorical variables S, P, M unless specified)
    if len(s) > 1 and s[0].isupper() and s not in {"All", "Some", "No", "Every", "Any", "None"}:
        return True
    return False


@dataclass
class Term:
    name: str
    is_singular: bool = False

    def __post_init__(self):
        if not self.is_singular and is_singular_term(self.name):
            self.is_singular = True


def _clean_ident(name: str) -> str:
    cleaned = "".join(c for c in name if c.isalnum() or c == "_")
    return cleaned if cleaned else "x"


def _format_pred(name: str) -> str:
    cleaned = _clean_ident(name)
    return cleaned[0].upper() + cleaned[1:]


def _format_const(name: str) -> str:
    cleaned = _clean_ident(name)
    return cleaned[0].lower() + cleaned[1:]


@dataclass
class CategoricalNode:
    type: str  # "A", "E", "I", "O"
    subject: Term
    predicate: Term

    def __post_init__(self):
        self.type = str(self.type).upper().strip()
        if isinstance(self.subject, str):
            self.subject = Term(self.subject)
        if isinstance(self.predicate, str):
            self.predicate = Term(self.predicate)

    def to_calgary_fol(self) -> str:
        """Compiles categorical propositions into first-order Calgary Fitch syntax:
        - Universal with singular term: e.g. "Sherlock is a cat" -> Cat(sherlock)
        - Standard categorical:
          A: forall x (S(x) -> P(x))
          E: forall x (S(x) -> ~P(x))
          I: exists x (S(x) & P(x))
          O: exists x (S(x) & ~P(x))
        """
        if self.subject.is_singular:
            c = _format_const(self.subject.name)
            p = _format_pred(self.predicate.name)
            if self.type in ("A", "I"):
                return f"{p}({c})"
            elif self.type in ("E", "O"):
                return f"~{p}({c})"

        s = _format_pred(self.subject.name)
        p = _format_pred(self.predicate.name)

        if self.type == "A":
            return f"forall x ({s}(x) -> {p}(x))"
        elif self.type == "E":
            return f"forall x ({s}(x) -> ~{p}(x))"
        elif self.type == "I":
            return f"exists x ({s}(x) & {p}(x))"
        elif self.type == "O":
            return f"exists x ({s}(x) & ~{p}(x))"
        return f"{s}(x)"
