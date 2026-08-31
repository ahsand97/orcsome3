"""On-disk cache of compiled static libraries (`~/.cache/orcsome3/libs` or `ORCSOME3_LIB_CACHE`)."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Iterable, Optional

from orcsome3.common import VERSION
from orcsome3.utils import rmdir


def force_rebuild() -> bool:
    """True when `ORCSOME3_FORCE_REBUILD` is 1/true/yes."""
    return os.getenv(key="ORCSOME3_FORCE_REBUILD", default="").lower() in ("1", "true", "yes")


def cache_root() -> Path:
    """Cache directory: `ORCSOME3_LIB_CACHE` or `~/.cache/orcsome3/libs`."""
    override: Optional[str] = os.getenv(key="ORCSOME3_LIB_CACHE")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "orcsome3" / "libs"


def library_cache_key(name: str, version: str, artifacts: Iterable[Path]) -> str:
    """Hash of name, version, orcsome3 version, and artifact paths (cache folder name)."""
    payload: dict[str, object] = {
        "name": name,
        "version": version,
        "orcsome3": VERSION,
        "artifacts": [str(a) for a in artifacts],
    }
    return hashlib.sha256(json.dumps(obj=payload, sort_keys=True).encode()).hexdigest()[:16]


def artifacts_exist(artifacts: Iterable[Path]) -> bool:
    """True if every path in `artifacts` is an existing file."""
    return all(path.is_file() for path in artifacts)


def restore_from_cache(cache_key: str, compiled_library_folder: Path, artifacts: list[Path]) -> bool:
    """Copy cached install dir into `compiled_library_folder`. True if artifacts are then present."""
    if force_rebuild():
        return False
    if artifacts_exist(artifacts=artifacts):
        return True
    cached: Path = cache_root() / cache_key
    if not cached.is_dir():
        return False
    if compiled_library_folder.is_dir():
        shutil.rmtree(path=compiled_library_folder)
    _ = shutil.copytree(src=cached, dst=compiled_library_folder)
    return artifacts_exist(artifacts=artifacts)


def store_in_cache(cache_key: str, compiled_library_folder: Path) -> None:
    """Copy `compiled_library_folder` into the cache keyed by `cache_key`."""
    if not compiled_library_folder.is_dir():
        return
    cached: Path = cache_root() / cache_key
    cached.parent.mkdir(parents=True, exist_ok=True)
    if cached.is_dir():
        shutil.rmtree(path=cached)
    _ = shutil.copytree(src=compiled_library_folder, dst=cached)


def begin_library_build(
    skip_build: bool,
    cache_name: str,
    cache_version: str,
    artifacts: list[Path],
    compiled_library_folder: Path,
    clean_paths: tuple[Path, ...] = (),
) -> bool:
    """Return True if the caller should compile. False if skip, artifacts exist, or cache restored."""
    if skip_build:
        return False
    if artifacts_exist(artifacts=artifacts) and not force_rebuild():
        return False
    cache_key: str = library_cache_key(name=cache_name, version=cache_version, artifacts=artifacts)
    if restore_from_cache(cache_key=cache_key, compiled_library_folder=compiled_library_folder, artifacts=artifacts):
        return False
    rmdir(*clean_paths)
    return True


def end_library_build(lib_name: str, version: str, artifacts: list[Path], compiled_library_folder: Path) -> None:
    """Store the just-built install dir in cache."""
    store_in_cache(
        cache_key=library_cache_key(name=lib_name, version=version, artifacts=artifacts),
        compiled_library_folder=compiled_library_folder,
    )
