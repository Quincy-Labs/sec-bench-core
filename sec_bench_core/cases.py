"""Case loading from meta.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Case:
    path: Path
    meta: dict

    @property
    def id(self) -> str:
        return self.meta["id"]


def load_case(path: Path) -> Case:
    """One case folder (must contain meta.yaml)."""
    path = Path(path).resolve()
    meta = yaml.safe_load((path / "meta.yaml").read_text()) or {}
    return Case(path, meta)


def load_cases(root: Path) -> list[Case]:
    """All cases under root (folders with a meta.yaml; underscore folders are skipped)."""
    cases = []
    for d in sorted(Path(root).iterdir()):
        if d.is_dir() and not d.name.startswith("_") and (d / "meta.yaml").exists():
            meta = yaml.safe_load((d / "meta.yaml").read_text()) or {}
            cases.append(Case(d, meta))
    return cases
