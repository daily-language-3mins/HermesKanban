#!/usr/bin/env python3
"""Discover and syntax-check every static JavaScript module."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def static_javascript_modules(root: Path) -> list[Path]:
    return sorted((root / "static").glob("*.js"))


def check_static_javascript(root: Path | None = None) -> None:
    root = root or repository_root()
    paths = static_javascript_modules(root)
    if not paths:
        raise RuntimeError(f"no static JavaScript modules found under {root / 'static'}")

    node = shutil.which("node")
    if not node:
        raise RuntimeError("node is required for static JavaScript syntax checks")

    for path in paths:
        rel_path = path.relative_to(root)
        print(f"node --check {rel_path}")
        subprocess.run([node, "--check", str(rel_path)], check=True, cwd=root)


def main() -> int:
    try:
        check_static_javascript()
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"static JavaScript syntax check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
