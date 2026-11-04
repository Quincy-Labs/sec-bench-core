# sec-bench-core

The chain-independent harness behind a family of AI smart-contract security
benchmarks. Each benchmark (Sui Move, Solana, later EVM) lives in its own repo
with its cases and one `Chain` class; this package holds everything else:

- **Model adapters**: `omlx:` / `local:`, `lmstudio:`, `ollama:`, `openai:`, `anthropic:`
- **Run loop**: `--samples` (best@k and mean), `--resume`, `--agentic` exploit mode
- **JSON parsing and repair** of model output (code fences, prose, truncation)
- **Grading** for three tasks:
  - **detect**: *strict* = right bug class and right (module, function);
    *lenient* = right class and right module. Clean cases score on the `found` flag.
  - **patch**: the model's files must pass the path check (never test folders); the
    patched package must build, pass the functional tests and fail the reference exploit.
  - **exploit**: the model's test must pass on `vulnerable/` and fail on `fixed/`.
    A test that passes on both scores zero.
- **Leak check**: model-visible files must not mention the bug class, generic
  remediation words, the chain's `leak_terms` or the case's `leak_terms`
- **Case validation** (`check-case`) and loading from `meta.yaml`
- **Leaderboard** tables from graded results files
- The **`sec-bench` CLI**

The core never builds code or runs tests itself; it always asks the Chain.

## Install

```sh
uv add "sec-bench-core @ git+https://github.com/<org>/sec-bench-core"   # or a path: ../sec-bench-core
```

Python 3.11+.

## How a chain repo uses it

```
my-bench/
  bench.toml            chain = "my_bench.chain:MyChain"
  my_bench/chain.py     the Chain class
  cases/<CASE-ID>/
    meta.yaml           id, title, source (incident|audit|clean), bug_class, bug_location, tasks, ...
    prompt.md           task description; everything from "## Answer format" on is replaced
    vulnerable/         package shown to the model
    fixed/              hidden reference fix
    tests/functional/   must pass on vulnerable and fixed (and on a patch)
    tests/exploit/      must pass on vulnerable, fail on fixed (may be withheld)
  results/
```

`bench.toml`:

```toml
chain = "my_bench.chain:MyChain"   # required
cases = "cases"                    # optional (default cases/)
results = "results"                # optional (default results/)
```

The directory holding `bench.toml` is put on `sys.path`, so the chain module
needs no install. Run every command from that directory:

```sh
sec-bench run --model openai:gpt-x --task detect --samples 3
sec-bench run --model openai:gpt-x --task patch --resume --out results/<run_id>.json
sec-bench run --model openai:gpt-x --task exploit --agentic --iters 5
sec-bench grade results/<run_id>.json          # in place; --out to write elsewhere
sec-bench leak-check --all                      # or a case folder
sec-bench check-case cases/CASE-0001            # or --all
sec-bench leaderboard --results results --out leaderboard [--recursive]
```

## The Chain interface

`sec_bench_core/chain.py` defines a `typing.Protocol`, so implement it as a plain
class with no base class. Loading checks that every member exists and that
`prompts` covers all three tasks.

| Member | Purpose |
|---|---|
| `name: str` | Chain id written into every results file, e.g. `"solana"` |
| `bug_classes: list[str]` | Allowed `bug_class` values; fills `{classes}` in prompts |
| `prompts: dict[task, {"system", "answer_format"}]` | Per task. `answer_format` replaces the `## Answer format` part of `prompt.md`. Optional `prompts["exploit"]["agentic_retry"]`: a `str.format` template with `{why}` |
| `exploit_filename: str` | Name the model's exploit test is saved as |
| `leak_terms: list[str]` | Chain-specific words forbidden in model-visible files |
| `test_glob: str` | Test files in `tests/functional` and `tests/exploit`, e.g. `"*.rs"` |
| `extra_required_meta: list[str]` | `meta.yaml` fields required on top of the core list |
| `read_sources(pkg) -> str` | Package sources as shown to the model |
| `model_visible_files(case_path) -> list[Path]` | Files scanned by the leak check |
| `is_allowed_patch_path(rel) -> bool` | Paths a patch may write. The core has already rejected empty, absolute and `..` paths |
| `run_tests(pkg, test_dirs, extra_files=None, timeout=300) -> TestResult` | Copy `pkg` to a temp dir, add tests, build and run them. Must never modify `pkg` |
| `split_location(loc) -> (module, function)` | Parse a location for detect grading. Use `""` for a missing part |
| `toolchain_warning(meta) -> str \| None` | Warning when the installed toolchain differs from the case's |

`TestResult(passed, phase, log, returncode=None)`, where `phase` is one of
`ok | build_failed | test_failed | build_timeout | timeout | error`. Graders store
the phase so a build failure is never confused with a failed test.

A minimal chain, for example in `my_bench/chain.py`:

```python
from pathlib import Path
from sec_bench_core.chain import TestResult

class MyChain:
    name = "mychain"
    bug_classes = ["access-control", "arithmetic", "none"]
    prompts = {t: {"system": "...", "answer_format": "## Answer format\n\n..."}
               for t in ("detect", "patch", "exploit")}
    exploit_filename = "model_exploit_test.rs"
    leak_terms = []
    test_glob = "*.rs"
    extra_required_meta = ["toolchain_version"]

    def read_sources(self, pkg): ...
    def model_visible_files(self, case_path): ...
    def is_allowed_patch_path(self, rel): return rel.startswith("src/")
    def run_tests(self, pkg, test_dirs, extra_files=None, timeout=300) -> TestResult: ...
    def split_location(self, loc): ...
    def toolchain_warning(self, meta): return None
```

`tests/fake_chain.py` is a complete working example that needs no toolchain.

## Results files

A run writes one JSON file:

- **Top level**: `run_id`, `model`, `task`, `samples`, `agentic`, `iters`, `thinking`,
  `max_tokens`, `lmstudio_defaults`, `prompt_sha256`, **`core_version`**, **`chain`**,
  `started_at`, `finished_at`, `outputs`.
- **Each output**: `task`, `model`, `case`, `sample`, `raw`, `reasoning`, `latency_s`,
  `prompt_tokens`, `completion_tokens`, `cost_usd`, `error`, `timestamp`. Agentic runs
  also have `agentic` and `iterations`.

`grade` adds `grade` to each output and a `summary` (with the grader's own
`core_version` and `chain`). The summary holds strict/lenient best@k and mean,
incident/audit/clean splits, the false-positive rate and per-case results.
`run --resume` and `grade` refuse a file whose `chain` differs from the
loaded chain. Files written before the core existed (no `chain`) are accepted.

## Development

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

`tests/test_no_chain_words.py` fails if the words "move" or "sui" appear in
`sec_bench_core/`. Chain-specific code belongs in the chain repo.
