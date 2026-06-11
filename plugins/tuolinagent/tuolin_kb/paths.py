from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .config import ProjectConfig


def resolve_project_path(root: Path, path_value: str | Path) -> Path:
    path = Path(path_value)
    return path if path.is_absolute() else root / path


def resolve_raw_dir(root: Path, config: ProjectConfig) -> Path:
    return resolve_project_path(root, config.raw_dir)


def source_path(root: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def source_to_path(root: Path, value: str) -> Path:
    return resolve_project_path(root, value)


def cache_key_for_path(root: Path, path: Path) -> Path:
    source = source_path(root, path)
    readable = re.sub(r"[^A-Za-z0-9._-]+", "_", source).strip("_")[:90] or "external"
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]
    return Path(f"{readable}_{digest}")
