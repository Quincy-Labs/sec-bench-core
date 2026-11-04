"""`sec-bench` command line. Run it from a benchmark repo that has a bench.toml.

sec-bench run --model openai:<model> --task detect --samples 3
sec-bench run --model omlx:<model> --task patch --case CASE-0001 --resume --out results/<run>.json
sec-bench grade results/<run_id>.json
sec-bench leak-check --all
sec-bench check-case cases/CASE-0001
sec-bench leaderboard --results results --out leaderboard
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .adapters import get_adapter
from .cases import load_case, load_cases
from .chain import TASKS
from .config import ConfigError, load_chain


def _cases_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--cases", type=Path, default=None, help="cases folder (default: from bench.toml, or cases/)"
    )


def _select_cases(args, cfg) -> list:
    root = args.cases or cfg.cases
    if getattr(args, "all", False):
        return load_cases(root)
    if getattr(args, "case", None):
        return [load_case(args.case)]
    raise SystemExit("need a case path or --all")


def cmd_run(args, chain, cfg) -> int:
    from .run import new_run, run_task

    if args.resume and not args.out:
        raise SystemExit("--resume needs --out pointing at the existing results file")
    cases = load_cases(args.cases or cfg.cases)
    if args.case:
        wanted = set(args.case)
        cases = [c for c in cases if c.id in wanted or c.path.name in wanted]
    thinking = {"on": True, "off": False, "default": None}[args.thinking]
    if args.resume:
        if not args.out.exists():
            raise SystemExit(f"--resume: {args.out} does not exist yet (rerun without --resume to start it)")
        run = json.loads(args.out.read_text())
        for key in ("task", "model"):
            if run.get(key) != getattr(args, key):
                raise SystemExit(
                    f"--resume: {args.out} has {key}={run.get(key)!r}, not {getattr(args, key)!r}"
                )
    else:
        run = new_run(
            chain,
            model=args.model,
            task=args.task,
            samples=args.samples,
            agentic=args.agentic,
            iters=args.iters,
            thinking=thinking,
            max_tokens=args.max_tokens,
        )
    out_path = args.out if args.out else cfg.results / f"{run['run_id']}.json"
    adapter = get_adapter(args.model)
    if thinking is not None:
        adapter.thinking = thinking
    run_task(
        chain,
        adapter,
        run,
        cases,
        out_path,
        samples=args.samples,
        max_tokens=args.max_tokens,
        agentic=args.agentic,
        iters=args.iters,
    )
    return 0


def cmd_grade(args, chain, cfg) -> int:
    from .grade import grade_file

    try:
        run = grade_file(chain, args.results, args.cases or cfg.cases, out=args.out)
    except ValueError as e:
        raise SystemExit(str(e)) from e
    print("summary", json.dumps(run["summary"], indent=1))
    return 0


def cmd_leak_check(args, chain, cfg) -> int:
    from .leak import scan_case

    leaked = 0
    for c in _select_cases(args, cfg):
        findings = scan_case(chain, c)
        if findings:
            leaked += 1
            print(f"{c.id}: {len(findings)} leak(s)")
            for rel, line, term, snippet in findings[:20]:
                print(f"  {rel}:{line} '{term}': {snippet}")
        else:
            print(f"{c.id}: clean")
    return 1 if leaked else 0


def cmd_check_case(args, chain, cfg) -> int:
    from .check_case import check_case, has_exploit_test

    failed = 0
    for c in _select_cases(args, cfg):
        errors = check_case(chain, c)
        if errors:
            failed += 1
            print(f"== {c.id} FAIL")
            for e in errors:
                print("ERROR:", e)
        elif "exploit" in c.meta.get("tasks", []) and not has_exploit_test(chain, c):
            print(f"== {c.id} PASS (functional and build only; exploit check not run)")
        else:
            print(f"== {c.id} PASS")
    return 1 if failed else 0


def cmd_leaderboard(args, chain, cfg) -> int:
    from .leaderboard import build

    data = build(args.results or cfg.results, args.out or cfg.root / "leaderboard", recursive=args.recursive)
    print(f"{len(data['rows'])} graded file(s) -> {args.out or cfg.root / 'leaderboard'}")
    return 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="sec-bench", description="Shared harness for AI security benchmarks.")
    ap.add_argument("--version", action="version", version=f"sec-bench-core {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="run a model on one task; save outputs to a results file")
    p.add_argument(
        "--model",
        required=True,
        help="omlx:<model> | local:<model> | lmstudio:<model> | ollama:<model> | openai:<model> | "
        "anthropic:<model>",
    )
    p.add_argument("--task", choices=TASKS, required=True)
    _cases_arg(p)
    p.add_argument(
        "--case", action="append", default=None, help="run only this case id or folder name (repeatable)"
    )
    p.add_argument("--samples", type=int, default=3, help="runs per case (reports best@k and mean)")
    p.add_argument(
        "--thinking",
        choices=["on", "off", "default"],
        default="default",
        help="ask the server to pin thinking/reasoning (some servers ignore this)",
    )
    p.add_argument(
        "--max-tokens",
        type=int,
        default=16384,
        help="completion budget; thinking models need room for reasoning before the answer (e.g. 32768)",
    )
    p.add_argument(
        "--resume",
        action="store_true",
        help="continue the existing results file given via --out; skip case/sample pairs already recorded",
    )
    p.add_argument(
        "--agentic",
        action="store_true",
        help="exploit only: run the model's test on the VULNERABLE package and feed the result back, "
        "up to --iters times. The fixed package is never shown; only a pass/fail bit about it is reported.",
    )
    p.add_argument("--iters", type=int, default=5, help="max agent iterations per sample when --agentic")
    p.add_argument("--out", type=Path, default=None, help="results file (default: <results>/<run_id>.json)")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("grade", help="grade a results file in place")
    p.add_argument("results", type=Path)
    _cases_arg(p)
    p.add_argument("--out", type=Path, default=None, help="write the graded file here instead of in place")
    p.set_defaults(func=cmd_grade)

    for name, func, help_text in (
        ("leak-check", cmd_leak_check, "scan model-visible files for words that reveal the bug"),
        ("check-case", cmd_check_case, "validate case metadata, builds, test rules and leaks"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("case", type=Path, nargs="?", help="case folder")
        p.add_argument("--all", action="store_true", help="every case in --cases")
        _cases_arg(p)
        p.set_defaults(func=func)

    p = sub.add_parser("leaderboard", help="build leaderboard tables from graded results files")
    p.add_argument(
        "--results", type=Path, default=None, help="folder of graded results (default: from bench.toml)"
    )
    p.add_argument("--out", type=Path, default=None, help="output folder (default: leaderboard/)")
    p.add_argument("--recursive", action="store_true", help="also read results in subfolders")
    p.set_defaults(func=cmd_leaderboard)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        chain, cfg = load_chain()
    except ConfigError as e:
        print(f"sec-bench: {e}", file=sys.stderr)
        return 2
    return args.func(args, chain, cfg)


if __name__ == "__main__":
    sys.exit(main())
