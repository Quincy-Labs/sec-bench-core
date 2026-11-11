"""Match the `subject` of a detect answer against a case's `bug_subject` names.

The subject is the one account, object, argument or variable whose check is
missing or wrong. Matching is deterministic and the same on every chain:

1. Remove backticks, anything in parentheses, method calls (`.key()`), and a
   type annotation after a single colon (`config: AccountView`).
2. Reduce each path to its last segment: `ctx.accounts.config` and
   `vault::Config` give `config`.
3. Split into identifiers, lowercase them, and drop filler words ("the",
   "account", "argument", ...).
4. Exactly one identifier must remain, and it must equal an accepted name.

Rule 4 is what stops a model from naming several accounts to be sure of a hit:
"config, vault" leaves two identifiers and never matches.
"""

from __future__ import annotations

import re

FILLER = {
    "a",
    "an",
    "the",
    "of",
    "in",
    "its",
    "account",
    "accounts",
    "object",
    "objects",
    "argument",
    "arg",
    "param",
    "parameter",
    "field",
    "variable",
    "var",
    "input",
    "passed",
    "struct",
    "mut",
    "ref",
}

_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
_PATH = re.compile(rf"{_IDENT}(?:(?:\.|::){_IDENT})+")


def normalize_subject(subject: object) -> str | None:
    """The single identifier a subject names, or None if it names zero or several."""
    if not isinstance(subject, str):
        return None
    s = subject.replace("`", "")
    s = re.sub(rf"(?:\.{_IDENT}\(\s*\))+", "", s)  # method calls: authority.key() -> authority
    s = re.sub(r"\([^)]*\)", " ", s)  # remarks in parentheses: "authority (signer)"
    s = re.split(r"(?<!:):(?!:)", s)[0]  # a type annotation after a single colon
    s = _PATH.sub(lambda m: re.split(r"\.|::", m.group(0))[-1], s)
    tokens = [t.lower() for t in re.findall(_IDENT, s)]
    tokens = [t for t in tokens if t not in FILLER]
    return tokens[0] if len(tokens) == 1 else None


def subject_matches(subject: object, accepted: list[str]) -> bool:
    name = normalize_subject(subject)
    return name is not None and name in {a.lower() for a in accepted}
