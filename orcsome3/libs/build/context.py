"""Build flags and paths for compiling bundled native libraries."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def parallel_jobs() -> int:
    """Job count from `ORCSOME3_BUILD_JOBS` / `CMAKE_BUILD_PARALLEL_LEVEL`, else CPU count."""
    raw: Optional[str] = os.getenv(key="ORCSOME3_BUILD_JOBS") or os.getenv(key="CMAKE_BUILD_PARALLEL_LEVEL")
    if raw:
        return max(1, int(raw))
    return max(1, os.cpu_count() or 1)


def make_build_cmd() -> str:
    """`make -jN` using `parallel_jobs()`."""
    return f"make -j{parallel_jobs()}"


def meson_compile_cmd() -> str:
    """`meson compile -j N` using `parallel_jobs()`."""
    return f"meson compile -j {parallel_jobs()}"


@dataclass
class BuildContext:
    """Where to put compiled libs and whether to skip / force debug cmake."""

    build_directory: Path
    skip_build_external_libs: bool
    static: bool
    debug: bool = False

    @property
    def cmake_debug_flag(self) -> str:
        """`ON`/`OFF` for `-DCMAKE_FIND_DEBUG_MODE`."""
        return "ON" if self.debug else "OFF"
