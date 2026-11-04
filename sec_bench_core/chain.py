"""The Chain protocol: everything the core needs to know about one blockchain.

A chain repo (for example a Solana or EVM benchmark) implements one class with
these members and names it in bench.toml:

    chain = "my_bench.chain:MyChain"

The core never inspects source code, builds packages or runs tests itself; it
always asks the Chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

TASKS = ("detect", "patch", "exploit")

# Every member of the Chain protocol, checked when bench.toml loads a chain.
CHAIN_MEMBERS = (
    "name",
    "bug_classes",
    "prompts",
    "exploit_filename",
    "leak_terms",
    "test_glob",
    "extra_required_meta",
    "read_sources",
    "model_visible_files",
    "is_allowed_patch_path",
    "run_tests",
    "split_location",
    "toolchain_warning",
)


@dataclass
class TestResult:
    """Outcome of building a package and running its tests.

    phase is one of: ok | build_failed | test_failed | build_timeout | timeout | error.
    Graders store it so build failures, test failures and timeouts stay distinguishable.
    """

    __test__ = False  # not a pytest test class

    passed: bool
    phase: str
    log: str
    returncode: int | None = None


@runtime_checkable
class Chain(Protocol):
    name: str
    """Short chain id written into every results file, e.g. "solana"."""

    bug_classes: list[str]
    """Allowed bug_class values; substituted for {classes} in prompts."""

    prompts: dict[str, dict[str, str]]
    """Per task ("detect", "patch", "exploit"): {"system": ..., "answer_format": ...}.

    answer_format replaces everything from the "## Answer format" marker in a
    case's prompt.md. Both strings may contain {classes}.

    Optional: prompts["exploit"]["agentic_retry"], the message sent in --agentic
    mode when the model's answer had no usable test. It is a str.format template
    with {why}; write literal braces as {{ and }}.
    """

    exploit_filename: str
    """File name the model's exploit test is written under (passed to run_tests)."""

    leak_terms: list[str]
    """Chain-specific words that must not appear in model-visible files."""

    test_glob: str
    """Glob for test files in a case's tests/functional and tests/exploit folders."""

    extra_required_meta: list[str]
    """meta.yaml fields required on top of the core's list (e.g. a toolchain version)."""

    def read_sources(self, pkg: Path) -> str:
        """Concatenated sources of a package, as shown to the model."""
        ...

    def model_visible_files(self, case_path: Path) -> list[Path]:
        """Every file of a case that the model sees (scanned by the leak check)."""
        ...

    def is_allowed_patch_path(self, rel: str) -> bool:
        """True if a model patch may write this package-relative path.

        The core has already rejected absolute paths and '..' before calling this.
        """
        ...

    def run_tests(
        self,
        pkg: Path,
        test_dirs: list[Path],
        extra_files: dict[str, str] | None = None,
        timeout: int = 300,
    ) -> TestResult:
        """Copy pkg somewhere temporary, add tests from test_dirs and extra_files, run them.

        Must never modify pkg.
        """
        ...

    def split_location(self, loc: str) -> tuple[str, str]:
        """Parse a location such as "pkg::module::function" into (module, function).

        Use "" for a missing part. Detect grading compares these tuples: strict
        needs both equal, lenient needs the module equal.
        """
        ...

    def toolchain_warning(self, meta: dict) -> str | None:
        """A warning when the installed toolchain differs from what the case expects."""
        ...
