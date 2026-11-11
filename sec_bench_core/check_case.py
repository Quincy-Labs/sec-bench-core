"""Validate one case: metadata, builds, test rules, and leak check.

Checks:
- meta.yaml has all required fields (core list plus chain.extra_required_meta);
  reviewers accepts [self] before v1.0.
- Functional tests pass on both vulnerable/ and fixed/.
- The exploit test passes on vulnerable/ and fails on fixed/. When tests/exploit/
  has no test (not written yet, or withheld from the public repo), the check is
  skipped and reported, not treated as an error.
- No leak terms in any file the model sees.
- Prints chain.toolchain_warning(meta) when there is one.
"""

from __future__ import annotations

import re
from pathlib import Path

from .cases import Case
from .chain import Chain
from .leak import scan_case
from .subject import normalize_subject

REQUIRED = [
    "id",
    "title",
    "source",
    "reference",
    "report_date",
    "severity",
    "bug_class",
    "bug_location",
    "contamination_risk",
    "tasks",
    "license_note",
    "reviewers",
    "added",
]


def _tests_in(chain: Chain, d: Path) -> list[Path]:
    return sorted(d.glob(chain.test_glob)) if d.exists() else []


def has_exploit_test(chain: Chain, case: Case) -> bool:
    return bool(_tests_in(chain, case.path / "tests" / "exploit"))


def _check_subject(chain: Chain, case: Case) -> list[str]:
    """bug_subject: a list of names, each one an identifier the model can see in the sources."""
    names = case.meta.get("bug_subject")
    if names is None:
        return []
    if case.meta.get("source") == "clean":
        return ["clean case cannot have bug_subject"]
    if not isinstance(names, list) or not names:
        return ["bug_subject must be a non-empty list of names"]
    seen = {
        t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", chain.read_sources(case.path / "vulnerable"))
    }
    errors = []
    for n in names:
        if normalize_subject(str(n)) != str(n).lower():
            errors.append(f"bug_subject {n!r}: must be one plain identifier")
        elif str(n).lower() not in seen:
            errors.append(f"bug_subject {n!r} does not appear in the vulnerable sources")
    return errors


def check_case(chain: Chain, case: Case) -> list[str]:
    errors: list[str] = []
    meta = case.meta
    for k in [*REQUIRED, *chain.extra_required_meta]:
        if not meta.get(k):
            errors.append(f"missing field: {k}")
    reviewers = meta.get("reviewers") or []
    if not reviewers:
        errors.append("needs at least one reviewer ([self] is allowed before v1.0)")
    elif "self" not in reviewers and len(reviewers) < 2:
        errors.append("needs a second reviewer before v1.0")
    if meta.get("bug_class") == "none" and meta.get("source") != "clean":
        errors.append("bug_class none requires source clean")
    if meta.get("bug_class") and meta["bug_class"] not in chain.bug_classes:
        errors.append(f"bug_class {meta['bug_class']!r} is not one of the chain's bug_classes")
    also = meta.get("bug_class_also") or []
    if not isinstance(also, list):
        errors.append("bug_class_also must be a list")
    else:
        for c in also:
            if c not in chain.bug_classes or c in ("none", meta.get("bug_class")):
                errors.append(f"bug_class_also {c!r}: must be another of the chain's bug_classes, not none")
        if also and meta.get("source") == "clean":
            errors.append("clean case cannot have bug_class_also")
    errors += _check_subject(chain, case)

    func = case.path / "tests" / "functional"
    expl = case.path / "tests" / "exploit"
    checks = [
        ("functional on vulnerable", case.path / "vulnerable", [func], True),
        ("functional on fixed", case.path / "fixed", [func], True),
    ]
    if meta.get("source") == "clean":
        if has_exploit_test(chain, case):
            errors.append("clean case should not have an exploit test")
    elif not has_exploit_test(chain, case):
        if "exploit" in meta.get("tasks", []):
            print("[SKIP] no exploit test (withheld in the public repo); exploit check not run")
    else:
        checks += [
            ("exploit on vulnerable (must pass)", case.path / "vulnerable", [expl], True),
            ("exploit on fixed (must fail)", case.path / "fixed", [expl], False),
        ]
    for name, pkg, dirs, want in checks:
        res = chain.run_tests(pkg, dirs)
        status = "OK" if res.passed == want else "FAIL"
        print(f"[{status}] {name} (phase={res.phase})")
        if res.passed != want:
            errors.append(f"{name} phase={res.phase}\n{res.log[-2000:]}")

    for rel, line, term, snippet in scan_case(chain, case):
        errors.append(f"leak: {rel}:{line} '{term}': {snippet}")

    warning = chain.toolchain_warning(meta)
    if warning:
        print(f"[WARN] {warning}")
    return errors
