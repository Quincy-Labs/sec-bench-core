"""Apply a model's patch to a copy of a package, rejecting unsafe paths."""

from __future__ import annotations

import shutil
from pathlib import Path, PurePosixPath, PureWindowsPath

from .chain import Chain


def _escapes(rel: str) -> bool:
    """True for absolute paths and paths with '..' (in either path flavor)."""
    for flavor in (PurePosixPath, PureWindowsPath):
        p = flavor(rel)
        if p.is_absolute() or p.anchor or ".." in p.parts:
            return True
    return False


def rejected_patch_paths(chain: Chain, files: dict) -> list[str]:
    """Paths in a model patch that may not be written (empty means all allowed).

    The core rejects empty, absolute and '..' paths; the chain decides the rest
    (for example: only files under the source folder, never test folders).
    """
    bad = []
    for rel in files:
        ok = isinstance(rel, str) and rel.strip() and not _escapes(rel) and chain.is_allowed_patch_path(rel)
        if not ok:
            bad.append(str(rel))
    return bad


def write_package_with_sources(src_pkg: Path, new_sources: dict[str, str], dest: Path) -> Path:
    """Copy a package to dest and overwrite the given files (used to apply a model patch)."""
    shutil.copytree(src_pkg, dest)
    root = dest.resolve()
    for rel, content in new_sources.items():
        target = (dest / rel).resolve()
        if not target.is_relative_to(root):
            raise ValueError(f"patch path escapes the package: {rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return dest
