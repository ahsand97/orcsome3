"""Named tuples describing a native library (pkg-config names, include/lib dirs, objects)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Generator, NamedTuple, Optional


class PkgConfigInfo(NamedTuple):
    """pkg-config module names, optional extra search path, and whether to request `--static`."""

    name: list[str]
    pkg_config_path: Optional[Path] = None
    static: bool = False


class CompilerArgs(NamedTuple):
    """`cflags` and `libs` lists as pkg-config would emit them."""

    cflags: list[str]
    libs: list[str]


class ExtraDirs(NamedTuple):
    """Include, lib, and optional cmake prefix directories for a built static library."""

    include_dirs: list[Path]
    lib_dir: Path
    cmake_dirs: Optional[list[Path]] = None

    def iter_dirs(self) -> Generator[Path, Any, Any]:
        """Yield include dirs, the lib dir, then optional cmake prefix dirs."""
        list_of_dirs: list[Path] = list(self.include_dirs)
        list_of_dirs.append(self.lib_dir)
        if self.cmake_dirs is not None:
            list_of_dirs.extend(self.cmake_dirs)
        for dir_ in list_of_dirs:
            yield dir_


class Library(NamedTuple):
    """One compiled (or system) library: name, compiler args, optional pkg-config and extra dirs/objects."""

    name: str
    compiler_args: CompilerArgs
    pkg_config_info: Optional[PkgConfigInfo] = None
    extra_dirs: Optional[ExtraDirs] = None
    extra_objects: list[Path] = []
