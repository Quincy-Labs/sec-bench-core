"""Load bench.toml and the Chain class it names.

bench.toml (in the directory you run `sec-bench` from):

    chain = "my_bench.chain:MyChain"   # required: module path and class name
    cases = "cases"                    # optional default for --cases
    results = "results"                # optional default results folder
"""

from __future__ import annotations

import importlib
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .chain import CHAIN_MEMBERS, TASKS, Chain

CONFIG_NAME = "bench.toml"


class ConfigError(Exception):
    pass


@dataclass
class BenchConfig:
    root: Path
    chain_spec: str
    cases: Path
    results: Path


def read_config(root: Path | None = None) -> BenchConfig:
    root = Path(root or Path.cwd()).resolve()
    path = root / CONFIG_NAME
    if not path.exists():
        raise ConfigError(f"{path} not found: run sec-bench from a benchmark repo that has a {CONFIG_NAME}")
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: {e}") from e
    spec = data.get("chain")
    if not isinstance(spec, str) or ":" not in spec:
        raise ConfigError(f'{path}: need chain = "package.module:ClassName"')
    return BenchConfig(
        root=root,
        chain_spec=spec,
        cases=root / data.get("cases", "cases"),
        results=root / data.get("results", "results"),
    )


def import_chain(spec: str, root: Path | None = None) -> Chain:
    """Import "pkg.module:ClassName" (root is put on sys.path first) and instantiate it."""
    mod_name, _, cls_name = spec.partition(":")
    if root is not None and str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        module = importlib.import_module(mod_name)
    except ImportError as e:
        raise ConfigError(f"cannot import chain module {mod_name!r}: {e}") from e
    cls = getattr(module, cls_name, None)
    if cls is None:
        raise ConfigError(f"module {mod_name!r} has no class {cls_name!r}")
    chain = cls()
    missing = [m for m in CHAIN_MEMBERS if not hasattr(chain, m)]
    if missing:
        raise ConfigError(f"{spec} does not implement the Chain protocol (missing: {', '.join(missing)})")
    tasks_missing = [t for t in TASKS if t not in (chain.prompts or {})]
    if tasks_missing:
        raise ConfigError(f"{spec}.prompts has no entry for: {', '.join(tasks_missing)}")
    return chain


def load_chain(root: Path | None = None) -> tuple[Chain, BenchConfig]:
    cfg = read_config(root)
    return import_chain(cfg.chain_spec, cfg.root), cfg
