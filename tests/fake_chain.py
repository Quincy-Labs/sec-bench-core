"""A Chain implementation with no blockchain toolchain, for tests.

Packages hold plain-text sources under src/*.txt. A test file (*.test) is a
list of rules, checked against the concatenated sources:

    require: TEXT   the sources must contain TEXT
    forbid: TEXT    the sources must not contain TEXT
    syntax error    the test does not "compile" (phase build_failed)

A package passes when every rule in every test file holds.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

import yaml

from sec_bench_core.chain import TestResult


class FakeChain:
    name = "fake"
    bug_classes = ["access-control", "arithmetic", "none"]
    prompts = {
        "detect": {
            "system": "Audit this fake package. Allowed bug_class values: {classes}.",
            "answer_format": "## Answer format\n\nJSON: found, bug_class, location; classes: {classes}",
        },
        "patch": {
            "system": "Fix this fake package.",
            "answer_format": '## Answer format\n\nJSON {"files": {"src/<file>.txt": "<content>"}}',
        },
        "exploit": {
            "system": "Write a fake exploit test.",
            "answer_format": '## Answer format\n\nJSON {"test_file": "<rules>"}',
        },
    }
    exploit_filename = "model_exploit.test"
    leak_terms = ["fakecoin"]
    test_glob = "*.test"
    extra_required_meta = ["fake_version"]

    def __init__(self):
        self.calls: list[tuple[str, list[str], dict]] = []

    def read_sources(self, pkg: Path) -> str:
        return "\n\n".join(
            f"// File: {f.relative_to(pkg)}\n{f.read_text()}" for f in sorted((pkg / "src").rglob("*.txt"))
        )

    def model_visible_files(self, case_path: Path) -> list[Path]:
        files = sorted((case_path / "vulnerable" / "src").rglob("*.txt"))
        if (case_path / "prompt.md").exists():
            files.append(case_path / "prompt.md")
        return files

    def is_allowed_patch_path(self, rel: str) -> bool:
        parts = Path(rel).parts
        return len(parts) >= 2 and parts[0] == "src"

    def run_tests(self, pkg, test_dirs, extra_files=None, timeout=300) -> TestResult:
        self.calls.append((Path(pkg).name, [Path(d).name for d in test_dirs], dict(extra_files or {})))
        with tempfile.TemporaryDirectory(prefix="fake-") as tmp:
            work = Path(tmp) / "pkg"
            shutil.copytree(pkg, work)
            tests = work / "tests"
            tests.mkdir(exist_ok=True)
            for d in test_dirs:
                if d and Path(d).exists():
                    for f in sorted(Path(d).glob(self.test_glob)):
                        shutil.copy(f, tests / f.name)
            for name, content in (extra_files or {}).items():
                (tests / name).write_text(content)
            sources = self.read_sources(work)
            rules = [ln.strip() for f in sorted(tests.glob("*")) for ln in f.read_text().splitlines()]
        if any(r == "syntax error" for r in rules):
            return TestResult(False, "build_failed", "build failed", 1)
        for r in rules:
            kind, _, text = r.partition(":")
            text = text.strip()
            if (kind == "require" and text not in sources) or (kind == "forbid" and text in sources):
                return TestResult(False, "test_failed", f"rule failed: {r}", 1)
        return TestResult(True, "ok", "all rules hold", 0)

    def split_location(self, loc: str) -> tuple[str, str]:
        parts = [p for p in re.split(r"[:.]+", loc.strip().lower()) if p]
        return (parts[-2] if len(parts) >= 2 else "", parts[-1] if parts else "")

    def toolchain_warning(self, meta: dict) -> str | None:
        return None


VULN_SRC = "fn withdraw(amount)\n  NO_AUTH\n"
FIXED_SRC = "fn withdraw(amount)\n  ASSERT_OWNER\n"


def make_case(
    root: Path,
    case_id: str = "FAKE-0001",
    *,
    source: str = "audit",
    bug_class: str = "access-control",
    bug_location: str = "vault::withdraw",
    tasks: tuple[str, ...] = ("detect", "patch", "exploit"),
    with_exploit_test: bool = True,
    prompt: str = "Review the vault package.\n\n## Answer format\n\nold format",
) -> Path:
    """Write a fake case folder and return its path.

    The reference exploit test forbids ASSERT_OWNER: it passes on vulnerable/
    and fails on fixed/. The functional test only requires the function to exist.
    """
    d = root / case_id
    for pkg, src in (("vulnerable", VULN_SRC), ("fixed", FIXED_SRC)):
        (d / pkg / "src").mkdir(parents=True)
        (d / pkg / "src" / "vault.txt").write_text(src)
    (d / "tests" / "functional").mkdir(parents=True)
    (d / "tests" / "functional" / "basic.test").write_text("require: fn withdraw\n")
    (d / "tests" / "exploit").mkdir(parents=True)
    if with_exploit_test and source != "clean":
        (d / "tests" / "exploit" / "steal.test").write_text("forbid: ASSERT_OWNER\n")
    (d / "prompt.md").write_text(prompt)
    meta = {
        "id": case_id,
        "title": "Fake vault",
        "source": source,
        "reference": "n/a",
        "report_date": "2026-01-01",
        "severity": "high",
        "bug_class": bug_class,
        "bug_location": bug_location,
        "contamination_risk": "low",
        "tasks": list(tasks),
        "fake_version": "1.0",
        "license_note": "test",
        "reviewers": ["self"],
        "added": "2026-01-01",
    }
    (d / "meta.yaml").write_text(yaml.safe_dump(meta))
    return d
