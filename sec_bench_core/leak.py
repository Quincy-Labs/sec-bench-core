"""Scan model-visible files for words that would reveal the bug.

A case leaks if any file the model sees (chain.model_visible_files: usually the
vulnerable sources and prompt.md) mentions the bug class, a generic
remediation word, a chain-specific word (chain.leak_terms) or a case-specific
identifier from the meta.yaml `leak_terms` field. The fixed/ package and the
tests are hidden from the model and are not scanned.
"""

from __future__ import annotations

import re

from .cases import Case
from .chain import Chain

DEFAULT_TERMS = [
    "vulnerab",
    "exploit",
    "bug",
    "fix",
    "patch",
    "hack",
    "attack",
    "malicious",
    "unauthorized",
    "insecure",
    "remediat",
    "drain",
    "todo",
    "fixme",
    "audit",
]

# Stems (no trailing word boundary) versus whole words (bounded on both sides).
STEMS = {"vulnerab", "remediat"}


def terms_for(chain: Chain, case: Case) -> list[str]:
    extras = [str(t) for t in (chain.leak_terms or [])]
    extras += [str(t) for t in (case.meta.get("leak_terms") or [])]
    bug_class = str(case.meta.get("bug_class") or "")
    if bug_class and bug_class != "none":
        extras += [bug_class, bug_class.replace("-", " ")]
    out: list[str] = []
    seen: set[str] = set()
    for t in [*DEFAULT_TERMS, *extras]:
        k = t.lower()
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _pattern(term: str) -> str:
    body = re.escape(term)
    return rf"\b{body}" if term in STEMS else rf"\b{body}\b"


def _prompt_lines(case: Case) -> list[str]:
    """Model-visible prompt lines, with the standard answer-format tail dropped.

    Everything from the '## Answer format' marker on is the same boilerplate
    in every case (it must list all bug class names for the JSON schema), so
    it cannot be a case-specific hint and is not scanned.
    """
    f = case.path / "prompt.md"
    if not f.exists():
        return []
    lines: list[str] = []
    for line in f.read_text().splitlines():
        if line.strip().startswith("## Answer format"):
            break
        lines.append(line)
    return lines


def scan_case(chain: Chain, case: Case) -> list[tuple[str, int, str, str]]:
    """Return (relative_file, line_no, term, snippet) for each leak found."""
    patterns = [(t, re.compile(_pattern(t))) for t in terms_for(chain, case)]
    findings: list[tuple[str, int, str, str]] = []
    prompt_lines = _prompt_lines(case)
    for f in chain.model_visible_files(case.path):
        rel = str(f.relative_to(case.path))
        body = prompt_lines if f.name == "prompt.md" else f.read_text().splitlines()
        for i, line in enumerate(body, 1):
            low = line.lower()
            for term, pat in patterns:
                if pat.search(low):
                    findings.append((rel, i, term, line.strip()[:100]))
                    break
    return findings
