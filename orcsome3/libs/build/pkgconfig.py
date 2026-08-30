"""Run pkg-config and stitch static linker flags for bundled native libraries."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from orcsome3.libs.build.types import CompilerArgs, ExtraDirs, Library, PkgConfigInfo


def get_compiler_args(
    libraries: list[PkgConfigInfo], extra_paths_to_search: Optional[list[Path]] = None
) -> CompilerArgs:
    """Collect `pkg-config --cflags/--libs` for each entry, honoring extra `PKG_CONFIG_PATH` dirs."""
    result_cflags: list[str] = []
    result_libs: list[str] = []

    pkg_config_paths: list[str] = []
    if extra_paths_to_search is not None and len(extra_paths_to_search):
        pkg_config_paths.extend([str(x) for x in extra_paths_to_search])
    pkg_config_path_original_value: Optional[str] = os.getenv(key="PKG_CONFIG_PATH")

    for library in libraries:
        if not len(library.name):
            continue

        if library.pkg_config_path is not None:
            pkg_config_paths.append(str(library.pkg_config_path))
        if pkg_config_path_original_value is not None:
            pkg_config_paths.append(pkg_config_path_original_value)

        cmd_cflags_command: str = f"pkg-config --cflags {' '.join(library.name)}"
        if len(pkg_config_paths):
            cmd_cflags_command = f'PKG_CONFIG_PATH="{":".join(pkg_config_paths)}" {cmd_cflags_command}'
        process_cflags: subprocess.CompletedProcess[str] = subprocess.run(
            args=["bash", "-c", cmd_cflags_command], capture_output=True, text=True, encoding="utf-8"
        )
        result_cflags.extend([x for x in process_cflags.stdout.replace("\n", "").split(sep=" ") if len(x.strip())])

        cmd_libs_command: str = "pkg-config --libs"
        if library.static:
            cmd_libs_command += " --static"
        cmd_libs_command += f" {' '.join(library.name)}"
        if len(pkg_config_paths):
            cmd_libs_command = f'PKG_CONFIG_PATH="{":".join(pkg_config_paths)}" {cmd_libs_command}'
        process_libs: subprocess.CompletedProcess[str] = subprocess.run(
            args=["bash", "-c", cmd_libs_command], capture_output=True, text=True, encoding="utf-8"
        )
        result_libs.extend([x for x in process_libs.stdout.replace("\n", "").split(sep=" ") if len(x.strip())])

    return CompilerArgs(cflags=result_cflags, libs=result_libs)


def complete_linker_args(library: Library, libraries: dict[str, Library]) -> CompilerArgs:
    """Rewrite `-lfoo` flags to the matching static archive path when we built that dep."""
    cflags: list[str] = library.compiler_args.cflags
    ldflags: list[str] = library.compiler_args.libs
    for index, ldflag in enumerate(iterable=library.compiler_args.libs):
        if not ldflag.startswith("-l") or index == 0:
            continue
        library_info: Optional[ExtraDirs] = None
        for lib in libraries.values():
            if not len(lib.extra_objects) or lib.extra_dirs is None:
                continue
            for static_lib in lib.extra_objects:
                stem: str = static_lib.stem
                ldname: str = stem[3:] if stem.startswith("lib") else stem
                if f"-l{ldname}" == ldflag:
                    library_info = lib.extra_dirs
                    break
            if library_info is not None:
                break
        if library_info is None:
            continue

        if len(library_info.include_dirs):
            for include_dir in library_info.include_dirs:
                if not include_dir.is_dir():
                    continue
                if f"-I{str(include_dir)}" not in cflags:
                    cflags.append(f"-I{str(include_dir)}")
                for inner_include in include_dir.iterdir():
                    if inner_include.is_file() or f"-I{str(inner_include)}" in cflags:
                        continue
                    cflags.append(f"-I{str(inner_include)}")

        if library.compiler_args.libs[index - 1] != f"-L{str(library_info.lib_dir)}":
            if f"-L{str(library_info.lib_dir)}" not in library.compiler_args.libs[index]:
                ldflags[index] = f"-L{str(library_info.lib_dir)} {ldflags[index]}"

    return library.compiler_args._replace(cflags=cflags, libs=" ".join(ldflags).split(sep=" "))
