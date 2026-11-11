# Migrating sui-sec-bench to sec-bench-core

After these steps, sui-sec-bench keeps its cases, results, Move prompts, the
`sui move test` runner and its own reports. Everything else comes from
sec-bench-core. Results files keep every existing field and gain `core_version`
and `chain`. Existing results files grade unchanged, so no rerun is needed.

Do these steps on a branch of the sui-sec-bench repo
(github.com/Quincy-Labs/sui-sec-bench, cloned locally as `sui-sec-bench-public`).
Its `harness/` is byte-identical to the code sec-bench-core was extracted from.
sec-bench-core is its own repository (github.com/Quincy-Labs/sec-bench-core).

## 1. Add the dependency

Pin a tag, so every results file's `core_version` maps to exact grading code:

```sh
cd sui-sec-bench-public
git switch -c use-sec-bench-core
uv add "sec-bench-core @ git+https://github.com/Quincy-Labs/sec-bench-core@v0.3.0"
```

To work on both repos at once, use `uv add --editable ../sec-bench-core` instead,
then switch back to the pinned tag before a release.

`pyyaml`, `requests`, `openai` and `anthropic` now come from the core. You can
drop them from `pyproject.toml`. Add `known-first-party = ["sui_bench"]` for ruff.

## 2. Create `bench.toml`

```toml
chain = "sui_bench.chain:SuiChain"
cases = "cases"
results = "results"
```

## 3. Create the `sui_bench` package

```sh
mkdir sui_bench && touch sui_bench/__init__.py
git mv harness/taxonomy.py sui_bench/taxonomy.py   # update the path in docs/TAXONOMY.md
```

Create `sui_bench/chain.py`. Copy the `PROMPTS` and `ANSWER_FORMATS` dicts from
`harness/run.py` (lines 43–130, comment included) **unchanged** where marked.
That keeps `prompt_sha256` and every prompt identical to the released benchmark.

```python
"""Sui Move chain for sec-bench-core."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from sec_bench_core.chain import TestResult

from . import taxonomy

# >>> paste PROMPTS = {...} and ANSWER_FORMATS = {...} from harness/run.py here, unchanged <<<

AGENTIC_RETRY = (  # was inline in run.py _feedback(); braces doubled for str.format
    "Your last answer could not be graded ({why}). Return ONLY a JSON object "
    '{{"test_file": "<complete content of one *_tests.move file>"}} with the '
    "revised test. No prose outside the JSON."
)

_TEST_PHASE_MARK = re.compile(r"Running Move unit tests", re.I)


def _decode(b) -> str:
    if isinstance(b, bytes):
        return b.decode(errors="replace")
    return b or ""


class SuiChain:
    name = "sui"
    bug_classes = taxonomy.CLASSES
    prompts = {task: {"system": PROMPTS[task], "answer_format": ANSWER_FORMATS[task]} for task in PROMPTS}
    prompts["exploit"]["agentic_retry"] = AGENTIC_RETRY
    exploit_filename = "model_exploit_tests.move"
    leak_terms: list[str] = []  # the generic list was never Sui-specific
    test_glob = "*.move"
    extra_required_meta = ["sui_version"]

    def read_sources(self, pkg: Path) -> str:
        parts = []
        for f in sorted((pkg / "sources").rglob("*.move")):
            parts.append(f"// File: {f.relative_to(pkg)}\n{f.read_text()}")
        return "\n\n".join(parts)

    def model_visible_files(self, case_path: Path) -> list[Path]:
        files = sorted((case_path / "vulnerable" / "sources").rglob("*.move"))
        prompt = case_path / "prompt.md"
        if prompt.exists():
            files.append(prompt)
        return files

    def is_allowed_patch_path(self, rel: str) -> bool:
        p = Path(rel.strip())
        return len(p.parts) >= 2 and p.parts[0] == "sources"

    def split_location(self, loc: str) -> tuple[str, str]:
        # Model output is often fully qualified ("case::math::scale"); compare the
        # trailing module::function.
        parts = [p for p in re.split(r"[:.]+", loc.strip().lower()) if p]
        return (parts[-2] if len(parts) >= 2 else "", parts[-1] if parts else "")

    def toolchain_warning(self, meta: dict) -> str | None:
        try:
            out = subprocess.run(["sui", "--version"], capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return None
        m = re.search(r"(\d+\.\d+\.\d+)", out.stdout)
        want = str(meta.get("sui_version") or "")
        if m and want and m.group(1) != want:
            return f"installed sui {m.group(1)} != meta sui_version {want}"
        return None

    def run_tests(self, pkg, test_dirs, extra_files=None, timeout=900) -> TestResult:
        """Copy pkg to a temp dir, add test files, run `sui move test` (pkg is never modified)."""
        with tempfile.TemporaryDirectory(prefix="ssb-") as tmp:
            work = Path(tmp) / "pkg"
            try:
                shutil.copytree(pkg, work)
            except OSError as e:
                return TestResult(False, "error", f"SSB-RUN phase=error setup failed: {e}")
            tests = work / "tests"
            tests.mkdir(exist_ok=True)
            for d in test_dirs:
                if d and d.exists():
                    for f in sorted(d.glob("*.move")):
                        shutil.copy(f, tests / f.name)
            for name, content in (extra_files or {}).items():
                (tests / name).write_text(content)
            log = f"SSB-RUN phase=setup pkg={pkg.name}\n"
            try:
                proc = subprocess.run(
                    ["sui", "move", "test"], cwd=work, capture_output=True, text=True, timeout=timeout
                )
            except subprocess.TimeoutExpired as e:
                out, err = _decode(e.stdout), _decode(e.stderr)
                phase = "timeout" if _TEST_PHASE_MARK.search(out) else "build_timeout"
                return TestResult(False, phase, log + f"SSB-RUN phase={phase} after {timeout}s\n{out}\n{err}")
            out, err = proc.stdout or "", proc.stderr or ""
            ran = _TEST_PHASE_MARK.search(out) or _TEST_PHASE_MARK.search(err)
            phase = "ok" if proc.returncode == 0 else ("test_failed" if ran else "build_failed")
            tail = (out + err)[-8000:]
            return TestResult(
                proc.returncode == 0,
                phase,
                log + f"SSB-RUN phase={phase} rc={proc.returncode}\n{tail}",
                returncode=proc.returncode,
            )
```

`run_tests` keeps the 900 s default from `run_move_tests`. The core never passes
a timeout, so the chain's default is the one that applies.

## 4. Delete the code that moved to the core

```sh
git rm -r harness/adapters harness/run.py harness/grade.py harness/common.py \
          harness/leak_check.py harness/check_case.py scripts/leak_check.py
```

Keep these files, with the import changes shown:

| File | Change |
|---|---|
| `harness/regrade_v2.py` | Change the imports to `from sec_bench_core.cases import Case, load_cases`, `from sec_bench_core.patching import write_package_with_sources`, `from sec_bench_core.jsonparse import parse_json`. Replace `run_move_tests(...)` with `SuiChain().run_tests(...)`. Optionally move it to `scripts/` |
| `leaderboard/build.py` | No change needed (it only reads JSON). Optionally import `table`, `passes`, `frac` and `avg_tokens` from `sec_bench_core.leaderboard` |
| `scripts/new_case.py` | Update the printed commands (lines 66–67) |

## 5. Update the commands

| Before | After |
|---|---|
| `uv run python harness/run.py --model M --task T ...` | `uv run sec-bench run --model M --task T ...` (same flags) |
| `uv run python harness/grade.py R.json` | `uv run sec-bench grade R.json` |
| `uv run python harness/check_case.py cases/X` / `--all` | `uv run sec-bench check-case cases/X` / `--all` |
| `uv run python scripts/leak_check.py --all` | `uv run sec-bench leak-check --all` |
| `uv run python leaderboard/build.py` (pilot report) | unchanged. `uv run sec-bench leaderboard` adds general tables |

Update these: `scripts/run_pilot.sh` (lines 23–31), `CONTRIBUTING.md` (lines 24–25)
and the folder layout in `README.md`. Leave `PUBLIC_RELEASE_AUDIT.md` and the
dated reports in `docs/` as they are: they describe the code as it was then.

## 6. Verify

```sh
uv run sec-bench check-case --all && uv run sec-bench leak-check --all
mkdir -p /tmp/regrade
for f in results/run2/*.json; do uv run sec-bench grade "$f" --out "/tmp/regrade/$(basename "$f")"; done
```

Then compare each `outputs[i].grade` and `summary` in `/tmp/regrade` with the
original file. Ignore what is new: `summary.core_version`/`summary.chain`, the
`incomplete` key (the current `grade.py` also adds it), and since core 0.2.0
`located` and `class_exact` in detect grades plus `located` and `located_any` in
summaries (and since 0.3.0 `pinpointed`, which needs `bug_subject` in a case). No Sui case sets `bug_class_also` yet, so every other detect and
exploit field should match exactly. Patch grades will **not** match in this repo: the
exploit tests are withheld, so patches grade as `incomplete`. Compare patch
grades only in a working copy that has the exploit tests. These checks were
run against such a copy:

- identical system/user messages and `prompt_sha256` for every task and case
- all 84 detect outputs in 20 results files, grades and summaries
- patch and exploit files graded with `sui` 1.82.3, including passing patches

## Behavior changes

- A patch path with a leading `/` (e.g. `/sources/a.move`) is now **rejected**.
  The old check stripped the `/` before validating, but then wrote to the absolute
  path. Patch contents that are not strings are rejected instead of crashing.
- `check-case` also fails a case whose `bug_class` is not in `taxonomy.CLASSES`.
- `run --resume` refuses a results file with a different `task`, `model` or `chain`.
- Code fences with any language tag are stripped (before: only `json` and `move`).
  This changes no existing grade.
