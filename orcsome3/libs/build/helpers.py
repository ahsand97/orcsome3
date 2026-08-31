"""Path helpers and skip/cache wrappers shared by native library recipes."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from orcsome3.libs.build.cache import begin_library_build, end_library_build
from orcsome3.libs.build.context import BuildContext
from orcsome3.libs.build.types import Library


def versioned_folder(name: str, version: str, *, prefix: str = "") -> str:
    """Directory name `{name}{prefix}-{version}` (e.g. `zlib-v1.3.1`)."""
    return f"{name}{prefix}-{version}"


def cmake_prefix_paths_from_deps(dependencies: Iterable[Library]) -> list[str]:
    """pkg-config and extra include/lib dirs from already-built `dependencies`."""
    paths: list[str] = []
    for dependency in dependencies:
        if dependency.pkg_config_info is not None and dependency.pkg_config_info.pkg_config_path is not None:
            paths.append(str(dependency.pkg_config_info.pkg_config_path))
        if dependency.extra_dirs is not None:
            for extra_dir in dependency.extra_dirs.iter_dirs():
                paths.append(str(extra_dir))
    return paths


def pkg_config_paths_from_deps(dependencies: Iterable[Library]) -> list[str]:
    """`PKG_CONFIG_PATH` entries from already-built `dependencies`."""
    paths: list[str] = []
    for dependency in dependencies:
        if dependency.pkg_config_info is not None and dependency.pkg_config_info.pkg_config_path is not None:
            paths.append(str(dependency.pkg_config_info.pkg_config_path))
    return paths


def maybe_build_library(
    skip_build: bool,
    lib_name: str,
    version: str,
    artifacts: list[Path],
    compiled_library_folder: Path,
    clean_paths: list[Path],
    build_fn: Callable[[], None],
) -> None:
    """Run `build_fn` unless skip/cache already produced `artifacts`; then store the result in cache."""
    if not begin_library_build(
        skip_build=skip_build,
        cache_name=lib_name,
        cache_version=version,
        artifacts=artifacts,
        compiled_library_folder=compiled_library_folder,
        clean_paths=tuple(clean_paths),
    ):
        return
    build_fn()
    end_library_build(
        lib_name=lib_name, version=version, artifacts=artifacts, compiled_library_folder=compiled_library_folder
    )


def make_build_context(
    build_directory: Path,
    skip_build_external_libs: bool,
    *,
    static: bool = True,
    debug: bool = False,
) -> BuildContext:
    """Construct a `BuildContext` for recipe functions."""
    return BuildContext(
        build_directory=build_directory,
        skip_build_external_libs=skip_build_external_libs,
        static=static,
        debug=debug,
    )
