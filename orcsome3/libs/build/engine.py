"""Clone, configure, and install static C/C++/Rust libraries used by the Cython backend."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

from orcsome3.libs.build.cache import begin_library_build, end_library_build
from orcsome3.libs.build.context import BuildContext, make_build_cmd, meson_compile_cmd
from orcsome3.libs.build.helpers import cmake_prefix_paths_from_deps, pkg_config_paths_from_deps
from orcsome3.libs.build.pkgconfig import get_compiler_args
from orcsome3.libs.build.types import CompilerArgs, ExtraDirs, Library, PkgConfigInfo
from orcsome3.utils import rmdir, run_command_and_show_output


@dataclass
class _BaseRecipe:
    """Shared fields for git-cloned native libraries (url, tag, install layout, artifacts)."""

    name: str
    url: str
    tag: str
    source_folder: str
    install_prefix_suffix: str = "-compiled"
    pkg_config_names: list[str] = field(default_factory=list)
    pkg_config_subpath: tuple[str, ...] = ("lib", "pkgconfig")
    include_subdirs: list[str] = field(default_factory=lambda: ["include"])
    lib_subdir: str = "lib"
    artifacts: list[str] = field(default_factory=list)
    cmake_dirs: Optional[list[str]] = None


@dataclass
class CMakeGitRecipe(_BaseRecipe):
    """Git + CMake recipe (`cmake_flags`, optional clone/install hooks)."""

    cmake_flags: list[str] = field(default_factory=list)
    cmake_source: str = "."
    pre_build_steps: list[str] = field(default_factory=list)
    post_install_cleanup: Optional[Callable[[Path], None]] = None
    post_clone_steps: list[str] = field(default_factory=list)
    post_clone_hook: Optional[Callable[[Path], None]] = None


@dataclass
class MesonGitRecipe(_BaseRecipe):
    """Git + Meson recipe."""

    meson_flags: list[str] = field(default_factory=list)
    meson_build_dir: str = "builddir"
    pre_meson_steps: list[str] = field(default_factory=list)


@dataclass
class CargoGitRecipe:
    """Git + Cargo recipe (used for resvg)."""

    name: str
    url: str
    tag: str
    source_folder: str
    install_prefix_suffix: str = "-compiled"
    cargo_subdir: str = "c-api"
    header_relative: str = "c-api/resvg.h"
    artifact_relative: str = "target/release/libresvg.a"
    artifact_name: str = "libresvg.a"
    include_subdirs: list[str] = field(default_factory=lambda: ["include"])
    lib_subdir: str = "lib"
    link_libs: list[str] = field(default_factory=lambda: ["-lresvg", "-lm"])


def _compiled_folder(ctx: BuildContext, recipe: _BaseRecipe | CargoGitRecipe) -> Path:
    return ctx.build_directory / f"{recipe.source_folder}{recipe.install_prefix_suffix}"


def _pkg_config_folder(compiled: Path, recipe: _BaseRecipe) -> Path:
    return compiled.joinpath(*recipe.pkg_config_subpath)


def _artifact_paths(lib_dir: Path, names: list[str]) -> list[Path]:
    return [lib_dir / name for name in names]


def _resolve_cmake_deps(
    cmake_prefix_path: Optional[list[str]],
    extra_paths_to_search: Optional[list[Path]],
    dependencies: Optional[Iterable[Library]],
) -> tuple[list[str], Optional[list[Path]]]:
    prefix_paths: list[str] = list(cmake_prefix_path or [])
    search_paths: list[Path] = list(extra_paths_to_search or [])
    if dependencies is not None:
        prefix_paths.extend(cmake_prefix_paths_from_deps(dependencies=dependencies))
        search_paths.extend(Path(path) for path in pkg_config_paths_from_deps(dependencies=dependencies))
    return prefix_paths, search_paths or None


def _library_from_recipe(
    recipe: _BaseRecipe,
    compiled_library_folder: Path,
    artifacts: list[Path],
    extra_paths_to_search: Optional[list[Path]] = None,
) -> Library:
    static_lib_folder: Path = compiled_library_folder / recipe.lib_subdir
    pkg_config_folder: Path = _pkg_config_folder(compiled=compiled_library_folder, recipe=recipe)
    pkg_config_info: PkgConfigInfo = PkgConfigInfo(
        name=recipe.pkg_config_names or [recipe.name],
        pkg_config_path=pkg_config_folder,
        static=True,
    )
    cmake_dir_paths: Optional[list[Path]] = None
    if recipe.cmake_dirs is not None:
        cmake_dir_paths = [static_lib_folder.joinpath(*part.split("/")) for part in recipe.cmake_dirs]

    return Library(
        name=recipe.name,
        compiler_args=get_compiler_args(libraries=[pkg_config_info], extra_paths_to_search=extra_paths_to_search),
        pkg_config_info=pkg_config_info,
        extra_dirs=ExtraDirs(
            include_dirs=[compiled_library_folder / part for part in recipe.include_subdirs],
            lib_dir=static_lib_folder,
            cmake_dirs=cmake_dir_paths,
        ),
        extra_objects=artifacts,
    )


def build_cmake_git_library(
    ctx: BuildContext,
    recipe: CMakeGitRecipe,
    skip_build: bool,
    cmake_prefix_path: Optional[list[str]] = None,
    extra_paths_to_search: Optional[list[Path]] = None,
    dependencies: Optional[Iterable[Library]] = None,
    extra_cmake_flags: Optional[list[str]] = None,
) -> Library:
    """Clone `recipe.url` at `recipe.tag`, cmake/make install, and return a `Library` with compiler flags."""
    lib_base_folder: Path = ctx.build_directory / recipe.source_folder
    compiled_library_folder: Path = _compiled_folder(ctx=ctx, recipe=recipe)
    static_lib_folder: Path = compiled_library_folder / recipe.lib_subdir
    artifacts: list[Path] = _artifact_paths(lib_dir=static_lib_folder, names=recipe.artifacts)
    prefix_paths, search_paths = _resolve_cmake_deps(
        cmake_prefix_path=cmake_prefix_path, extra_paths_to_search=extra_paths_to_search, dependencies=dependencies
    )

    if begin_library_build(
        skip_build=skip_build,
        cache_name=recipe.name,
        cache_version=recipe.tag,
        artifacts=artifacts,
        compiled_library_folder=compiled_library_folder,
        clean_paths=(lib_base_folder, compiled_library_folder),
    ):
        flags: list[str] = [
            f"-DCMAKE_FIND_DEBUG_MODE={ctx.cmake_debug_flag}",
            f"-DCMAKE_INSTALL_PREFIX='{compiled_library_folder}'",
            "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
        ]
        if prefix_paths:
            flags.append(f"-DCMAKE_PREFIX_PATH='{';'.join(prefix_paths)}'")
        flags.extend(recipe.cmake_flags)
        if extra_cmake_flags:
            flags.extend(extra_cmake_flags)
        configure_command: str = f"CMAKE_POLICY_VERSION_MINIMUM=3.5 cmake {' '.join(flags)} -S {recipe.cmake_source}"
        clone_command: str = " && ".join(
            [
                f"git clone {recipe.url} '{lib_base_folder}'",
                f"cd '{lib_base_folder}'",
                f"git switch --detach {recipe.tag}",
                *recipe.post_clone_steps,
            ]
        )
        run_command_and_show_output(command=clone_command, cwd=ctx.build_directory)
        if recipe.post_clone_hook is not None:
            recipe.post_clone_hook(lib_base_folder)
        build_command: str = " && ".join(
            [
                f"cd '{lib_base_folder}'",
                *recipe.pre_build_steps,
                configure_command,
                make_build_cmd(),
                "make install",
            ]
        )
        run_command_and_show_output(command=build_command, cwd=ctx.build_directory)
        rmdir(lib_base_folder)
        if recipe.post_install_cleanup is not None:
            recipe.post_install_cleanup(static_lib_folder)
        end_library_build(
            lib_name=recipe.name,
            version=recipe.tag,
            artifacts=artifacts,
            compiled_library_folder=compiled_library_folder,
        )

    return _library_from_recipe(
        recipe=recipe,
        compiled_library_folder=compiled_library_folder,
        artifacts=artifacts,
        extra_paths_to_search=search_paths,
    )


def build_meson_git_library(
    ctx: BuildContext,
    recipe: MesonGitRecipe,
    skip_build: bool,
    extra_paths_to_search: Optional[list[Path]] = None,
    dependencies: Optional[Iterable[Library]] = None,
) -> Library:
    """Clone `recipe.url` at `recipe.tag`, meson setup/compile/install, and return a `Library`."""
    lib_base_folder: Path = ctx.build_directory / recipe.source_folder
    compiled_library_folder: Path = _compiled_folder(ctx=ctx, recipe=recipe)
    static_lib_folder: Path = compiled_library_folder / recipe.lib_subdir
    artifacts: list[Path] = _artifact_paths(lib_dir=static_lib_folder, names=recipe.artifacts)
    _, search_paths = _resolve_cmake_deps(
        cmake_prefix_path=None, extra_paths_to_search=extra_paths_to_search, dependencies=dependencies
    )

    if begin_library_build(
        skip_build=skip_build,
        cache_name=recipe.name,
        cache_version=recipe.tag,
        artifacts=artifacts,
        compiled_library_folder=compiled_library_folder,
        clean_paths=(lib_base_folder, compiled_library_folder),
    ):
        meson_flags: list[str] = [f"--prefix '{compiled_library_folder}'", *recipe.meson_flags]
        if dependencies is not None:
            pkg_config_path: str = ":".join(pkg_config_paths_from_deps(dependencies=dependencies))
            if pkg_config_path:
                meson_flags.append(f'-Dpkg_config_path="{pkg_config_path}"')
        configure_command: str = f"meson setup {recipe.meson_build_dir} {' '.join(meson_flags)}"
        commands: str = " && ".join(
            [
                f"git clone {recipe.url} '{lib_base_folder}'",
                f"cd '{lib_base_folder}'",
                f"git switch --detach {recipe.tag}",
                *recipe.pre_meson_steps,
                configure_command,
                f"cd {recipe.meson_build_dir}",
                meson_compile_cmd(),
                "meson install",
            ]
        )
        run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=ctx.build_directory)
        rmdir(lib_base_folder)
        end_library_build(
            lib_name=recipe.name,
            version=recipe.tag,
            artifacts=artifacts,
            compiled_library_folder=compiled_library_folder,
        )

    return _library_from_recipe(
        recipe=recipe,
        compiled_library_folder=compiled_library_folder,
        artifacts=artifacts,
        extra_paths_to_search=search_paths,
    )


def build_cargo_git_library(
    ctx: BuildContext,
    recipe: CargoGitRecipe,
    skip_build: bool,
) -> Library:
    """Clone `recipe.url` at `recipe.tag`, `cargo build --release`, and return a `Library`."""
    lib_base_folder: Path = ctx.build_directory / recipe.source_folder
    compiled_library_folder: Path = _compiled_folder(ctx=ctx, recipe=recipe)
    static_lib_folder: Path = compiled_library_folder / recipe.lib_subdir
    static_include_folder: Path = compiled_library_folder / "include"
    artifacts: list[Path] = [static_lib_folder / recipe.artifact_name]

    if begin_library_build(
        skip_build=skip_build,
        cache_name=recipe.name,
        cache_version=recipe.tag,
        artifacts=artifacts,
        compiled_library_folder=compiled_library_folder,
        clean_paths=(lib_base_folder, compiled_library_folder),
    ):
        commands: str = " && ".join(
            [
                f"git clone {recipe.url} '{lib_base_folder}'",
                f"mkdir -p '{compiled_library_folder}' '{static_lib_folder}' '{static_include_folder}'",
                f"cd '{lib_base_folder}'",
                f"git switch --detach {recipe.tag}",
                f"cd {recipe.cargo_subdir}",
                "cargo build --release",
            ]
        )
        run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=ctx.build_directory)
        _ = shutil.move(src=str(lib_base_folder / recipe.header_relative), dst=str(static_include_folder))
        _ = shutil.move(
            src=str(lib_base_folder / recipe.artifact_relative), dst=str(static_lib_folder / recipe.artifact_name)
        )
        rmdir(lib_base_folder)
        end_library_build(
            lib_name=recipe.name,
            version=recipe.tag,
            artifacts=artifacts,
            compiled_library_folder=compiled_library_folder,
        )

    return Library(
        name=recipe.name,
        compiler_args=CompilerArgs(
            cflags=[f"-I{static_include_folder}"],
            libs=[f"-L{static_lib_folder}", *recipe.link_libs],
        ),
        extra_dirs=ExtraDirs(
            include_dirs=[compiled_library_folder / part for part in recipe.include_subdirs],
            lib_dir=static_lib_folder,
        ),
        extra_objects=artifacts,
    )
