"""Orchestrate static native builds and Cythonize `orcsome3_backend` (CLI: `python -m orcsome3.libs.build`)."""

from __future__ import annotations

import argparse
import os
import shutil
import traceback
import urllib.request
from pathlib import Path
from typing import Any, Callable, Optional, cast

from setuptools import setup
from setuptools.extension import Extension

from orcsome3.common import APPNAME
from orcsome3.libs.build.cache import force_rebuild as env_force_rebuild
from orcsome3.libs.build.context import BuildContext, make_build_cmd
from orcsome3.libs.build.engine import build_cargo_git_library, build_cmake_git_library, build_meson_git_library
from orcsome3.libs.build.helpers import make_build_context, maybe_build_library, versioned_folder
from orcsome3.libs.build.paths import CYTHON_BACKEND_PYX, CYTHON_LIBS_DIR
from orcsome3.libs.build.pkgconfig import complete_linker_args, get_compiler_args
from orcsome3.libs.build.recipes import (
    CARGO_GIT_RECIPES,
    CMAKE_GIT_RECIPES,
    CORE_CMAKE_RECIPES,
    CORE_MESON_RECIPES,
    LIBRARIES_SOURCES_VERSION,
    MESON_GIT_RECIPES,
)
from orcsome3.libs.build.types import CompilerArgs, ExtraDirs, Library, PkgConfigInfo
from orcsome3.utils import extract_tar_strip_components, rmdir, run_command_and_show_output

debug: bool = False


def _lib_dirs(name: str) -> tuple[str, str]:
    source: str = versioned_folder(name=name, version=LIBRARIES_SOURCES_VERSION[name][1])
    return source, f"{source}-compiled"


def validate_skipped_external_build(build_directory: Path) -> None:
    """Ensure cached static libraries exist when skipping external builds."""
    missing: list[str] = []
    required_files: list[Path] = [
        build_directory / _lib_dirs(name="zlib")[1] / "lib" / "libz.a",
        build_directory / _lib_dirs(name="libev")[1] / "lib" / "libev.a",
        build_directory / _lib_dirs(name="resvg")[1] / "lib" / "libresvg.a",
        build_directory / _lib_dirs(name="libgd")[1] / "lib" / "libgd.a",
    ]
    for path in required_files:
        if not path.is_file():
            missing.append(str(path.relative_to(build_directory)))

    magick_compiled: Path = build_directory / _lib_dirs(name="imagemagick")[1] / "lib"
    magick_libs: list[Path] = list(magick_compiled.glob(pattern="libMagickWand*.a"))
    if not magick_libs:
        missing.append(f"{_lib_dirs(name='imagemagick')[1]}/lib/libMagickWand*.a")

    if missing:
        raise FileNotFoundError(
            "External libraries are missing but --skip-build-external-libs was used. "
            + "Run a full build first:\n"
            + f"  python -m orcsome3.libs.build --build-dir {build_directory.parent}\n"
            + "Missing:\n  - "
            + "\n  - ".join(missing)
        )


def install_backend_for_local_dev(library_directory: Path, destination: Path) -> None:
    """Copy the compiled backend .so next to the project for local imports without extra PYTHONPATH."""
    destination = destination.resolve()
    for shared_library in library_directory.glob(pattern="orcsome3_backend*.so"):
        dst: Path = destination / shared_library.name
        if dst.resolve() == shared_library.resolve():
            continue
        _ = shutil.copy2(src=shared_library, dst=dst)


def run_function_in_another_directory(directory: Path, function: Callable[..., Any]) -> Any:
    """Run `function` with cwd=`directory`, then restore the original cwd even if `function` raises."""
    tmp: Path = Path.cwd()
    os.chdir(path=directory)
    try:
        return function()
    finally:
        os.chdir(path=tmp)


def clean_build_directory(build_directory: Path, remove: Optional[list[Path]] = None) -> None:
    """Clean `build_directory` and remove files specified in the parameter `remove`"""
    run_function_in_another_directory(
        directory=build_directory, function=lambda: setup(py_modules=[], script_args=["clean", "--all"])
    )
    if remove is not None:
        rmdir(*remove)


def build_base_libraries(build_directory: Path, skip_build_external_libs: bool) -> dict[str, Library]:
    """
    Function that builds the base libraries needed to build the core libraries.

    Base libraries:
    - `zlib`: https://github.com/madler/zlib.git.
    - `lzo`: https://www.oberhumer.com/opensource/lzo.
    - `zstd`: https://github.com/facebook/zstd.git.
    - `libjpeg`: https://github.com/libjpeg-turbo/libjpeg-turbo.git.
    - `jbig`: JBIG-KIT https://www.cl.cam.ac.uk/~mgk25/jbigkit.
    - `liblzma`: https://github.com/tukaani-project/xz.git.
    - `Imath`: https://github.com/AcademySoftwareFoundation/Imath.git.
    - `openjpeg` (libopenjp2): https://github.com/uclouvain/openjpeg.git.
    - `pixman`: https://github.com/freedesktop/pixman.git.
    - `libpng`: https://github.com/glennrp/libpng.git. Depends on `zlib`.
    - `libwebp`: https://chromium.googlesource.com/webm/libwebp. Dependes on `zlib`, `libpng`, `libtiff` and `libjpeg`.
    - `libtiff`: https://gitlab.com/libtiff/libtiff.git. Depends on `zlib`, `zstd`, `libjpeg`, `jbig`, `liblzma` and `libwebp`.
    - `djvulibre`: https://djvu.sourceforge.net. Depends on `libjpeg` and `libtiff`.
    - `openexr`: https://github.com/AcademySoftwareFoundation/openexr.git. Depends on `zlib` and `Imath`.
    - `libraw`: https://github.com/LibRaw/LibRaw.git. Depends on `zlib` and `libjpeg`.
    """
    ctx: BuildContext = make_build_context(
        build_directory=build_directory, skip_build_external_libs=skip_build_external_libs, debug=debug
    )

    def build_zlib(skip_build: bool = skip_build_external_libs) -> Library:
        return build_cmake_git_library(ctx=ctx, recipe=CMAKE_GIT_RECIPES["zlib"], skip_build=skip_build)

    def build_lzo(skip_build: bool = skip_build_external_libs) -> Library:
        """Build lzo statically"""
        lib_name: str = "lzo"
        source_folder, compiled_name = _lib_dirs(name=lib_name)
        lib_base_folder: Path = build_directory.joinpath(source_folder)
        build_library_folder: Path = build_directory.joinpath(f"{source_folder}-build")
        compiled_library_folder: Path = build_directory.joinpath(compiled_name)

        # Folders with the compiled library and the include files
        static_include_folder: Path = compiled_library_folder.joinpath(
            "include", "lzo"
        )  # {build_directory}/lzo-{version}-compiled/include/lzo
        static_lib_folder: Path = compiled_library_folder.joinpath(
            "lib"
        )  # {build_directory}/lzo-{version}-compiled/lib
        pkg_config_folder: Path = static_lib_folder.joinpath(
            "pkgconfig"
        )  # {build_directory}/lzo-{version}-compiled/lib/pkgconfig
        artifacts: list[Path] = [static_lib_folder.joinpath("liblzo2.a")]

        def _build() -> None:
            file_with_lib_source: Path = Path(
                urllib.request.urlretrieve(
                    url=LIBRARIES_SOURCES_VERSION[lib_name][0], filename=f"{str(lib_base_folder)}.tar.gz"
                )[0]
            )
            if not file_with_lib_source.is_file():
                raise Exception(
                    f"An error occurred downloading {lib_name} source from: {LIBRARIES_SOURCES_VERSION[lib_name][0]}"
                )
            try:
                extract_tar_strip_components(
                    tar_path=file_with_lib_source, destination_path=lib_base_folder, strip_components=1
                )
            except Exception as e:
                raise Exception(f"An error occurred extracting the files from file: {str(file_with_lib_source)}", e)

            flags_to_configure_command: list[str] = [
                f"-DCMAKE_FIND_DEBUG_MODE={'ON' if debug else 'OFF'}",
                f'-DCMAKE_INSTALL_PREFIX="{str(compiled_library_folder)}"',
                "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
                "-DBUILD_SHARED_LIBS=OFF",
            ]
            configure_command: str = (
                f"CMAKE_POLICY_VERSION_MINIMUM=3.5 cmake {' '.join(flags_to_configure_command)} -S"
                + f" {str(lib_base_folder)}"
            )
            commands: str = " && ".join(
                [
                    f"mkdir -p {str(build_library_folder)}",
                    f"cd {str(build_library_folder)}",
                    configure_command,
                    make_build_cmd(),
                    "make install",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(file_with_lib_source, lib_base_folder, build_library_folder)

        maybe_build_library(
            skip_build=skip_build,
            lib_name=lib_name,
            version=LIBRARIES_SOURCES_VERSION[lib_name][1],
            artifacts=artifacts,
            compiled_library_folder=compiled_library_folder,
            clean_paths=[lib_base_folder, build_library_folder, compiled_library_folder],
            build_fn=_build,
        )
        pkg_config_info: PkgConfigInfo = PkgConfigInfo(name=["lzo2"], pkg_config_path=pkg_config_folder, static=True)
        return Library(
            name=lib_name,
            compiler_args=get_compiler_args(libraries=[pkg_config_info]),
            pkg_config_info=pkg_config_info,
            extra_dirs=ExtraDirs(include_dirs=[static_include_folder], lib_dir=static_lib_folder),
            extra_objects=[static_lib_folder.joinpath("liblzo2.a")],
        )

    def build_zstd(skip_build: bool = skip_build_external_libs) -> Library:
        return build_cmake_git_library(ctx=ctx, recipe=CMAKE_GIT_RECIPES["zstd"], skip_build=skip_build)

    def build_libjpeg(skip_build: bool = skip_build_external_libs) -> Library:
        return build_cmake_git_library(ctx=ctx, recipe=CMAKE_GIT_RECIPES["libjpeg"], skip_build=skip_build)

    def build_jbig(skip_build: bool = skip_build_external_libs) -> Library:
        """Build jbig statically"""
        lib_name: str = "jbig"
        source_folder, compiled_name = _lib_dirs(name=lib_name)
        lib_base_folder: Path = build_directory.joinpath(source_folder)
        compiled_library_folder: Path = build_directory.joinpath(compiled_name)
        artifacts: list[Path] = [compiled_library_folder.joinpath("libjbig.a")]

        def _build() -> None:
            git_clone_command: str = f"git clone {LIBRARIES_SOURCES_VERSION[lib_name][0]} '{str(lib_base_folder)}'"
            commands: str = " && ".join(
                [
                    git_clone_command,
                    f"cd '{str(lib_base_folder)}'",
                    f"git switch --detach {LIBRARIES_SOURCES_VERSION[lib_name][1]}",
                    # Only the "lib" target (libjbig.a); "pbm" builds jbigkit's CLI tools (unneeded here)
                    # and their man pages need groff, which isn't a build dependency of this project.
                    f"{make_build_cmd()} lib",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            _ = shutil.move(src=lib_base_folder.joinpath(f"lib{lib_name}"), dst=compiled_library_folder)
            rmdir(lib_base_folder)

        maybe_build_library(
            skip_build=skip_build,
            lib_name=lib_name,
            version=LIBRARIES_SOURCES_VERSION[lib_name][1],
            artifacts=artifacts,
            compiled_library_folder=compiled_library_folder,
            clean_paths=[lib_base_folder, compiled_library_folder],
            build_fn=_build,
        )
        return Library(
            name=lib_name,
            compiler_args=CompilerArgs(
                cflags=[f"-I{str(compiled_library_folder)}"], libs=[f"-L{str(compiled_library_folder)}", "-l:libjbig.a"]
            ),
            extra_dirs=ExtraDirs(include_dirs=[compiled_library_folder], lib_dir=compiled_library_folder),
            extra_objects=[compiled_library_folder.joinpath("libjbig.a")],
        )

    def build_liblzma(skip_build: bool = skip_build_external_libs) -> Library:
        return build_cmake_git_library(ctx=ctx, recipe=CMAKE_GIT_RECIPES["liblzma"], skip_build=skip_build)

    def build_Imath(skip_build: bool = skip_build_external_libs) -> Library:
        return build_cmake_git_library(ctx=ctx, recipe=CMAKE_GIT_RECIPES["Imath"], skip_build=skip_build)

    def build_openjpeg(skip_build: bool = skip_build_external_libs) -> Library:
        return build_cmake_git_library(ctx=ctx, recipe=CMAKE_GIT_RECIPES["openjpeg"], skip_build=skip_build)

    def build_pixman(skip_build: bool = skip_build_external_libs) -> Library:
        return build_meson_git_library(ctx=ctx, recipe=MESON_GIT_RECIPES["pixman"], skip_build=skip_build)

    def build_libpng(zlib: Library, skip_build: bool = skip_build_external_libs) -> Library:
        return build_cmake_git_library(
            ctx=ctx, recipe=CMAKE_GIT_RECIPES["libpng"], skip_build=skip_build, dependencies=[zlib]
        )

    def build_libwebp(build_dependencies: dict[str, Library], skip_build: bool = skip_build_external_libs) -> Library:
        return build_cmake_git_library(
            ctx=ctx,
            recipe=CMAKE_GIT_RECIPES["libwebp"],
            skip_build=skip_build,
            dependencies=build_dependencies.values(),
        )

    def build_libtiff(
        build_dependencies: dict[str, Optional[Library]],
        skip_build: bool = skip_build_external_libs,
        *,
        enable_webp: bool = False,
    ) -> Library:
        return build_cmake_git_library(
            ctx=ctx,
            recipe=CMAKE_GIT_RECIPES["libtiff"],
            skip_build=skip_build,
            dependencies=[dependency for dependency in build_dependencies.values() if dependency is not None],
            extra_cmake_flags=[f"-Dwebp={'ON' if enable_webp else 'OFF'}"],
        )

    def build_djvulibre(build_dependencies: dict[str, Library], skip_build: bool = skip_build_external_libs) -> Library:
        """
        Buld djvulibre statically.

        Dependencies:
        - libjpeg
        - libtiff
        """
        lib_name: str = "djvulibre"
        source_folder, compiled_name = _lib_dirs(name=lib_name)
        lib_base_folder: Path = build_directory.joinpath(source_folder)
        compiled_library_folder: Path = build_directory.joinpath(compiled_name)

        # Folders with the compiled library and the include files
        static_include_folder: Path = compiled_library_folder.joinpath(
            "include"
        )  # {build_directory}/djvulibre-{version}-compiled/include
        static_lib_folder: Path = compiled_library_folder.joinpath(
            "lib"
        )  # {build_directory}/djvulibre-{version}-compiled/lib
        pkg_config_folder: Path = static_lib_folder.joinpath(
            "pkgconfig"
        )  # {build_directory}/djvulibre-{version}-compiled/lib/pkgconfig
        artifacts: list[Path] = [static_lib_folder.joinpath("libdjvulibre.a")]

        def _build() -> None:
            file_with_lib_source: Path = Path(
                urllib.request.urlretrieve(
                    url=LIBRARIES_SOURCES_VERSION[lib_name][0], filename=f"{str(lib_base_folder)}.tar.gz"
                )[0]
            )
            if not file_with_lib_source.is_file():
                raise Exception(
                    f"An error occurred downloading {lib_name} source from: {LIBRARIES_SOURCES_VERSION[lib_name][0]}"
                )
            try:
                extract_tar_strip_components(
                    tar_path=file_with_lib_source, destination_path=lib_base_folder, strip_components=1
                )
            except Exception as e:
                raise Exception(f"An error occurred extracting the files from file: {str(file_with_lib_source)}", e)

            flags_to_configure_command: list[str] = [
                f"--prefix='{str(compiled_library_folder)}'",
                "--enable-static",
                "--disable-shared",
                "--with-pic=yes",
                "--disable-xmltools",
                "--disable-desktopfiles",
                f"--with-jpeg='{str(cast(ExtraDirs, build_dependencies['libjpeg'].extra_dirs).lib_dir)}'",
                f"--with-tiff='{str(cast(ExtraDirs, build_dependencies['libtiff'].extra_dirs).lib_dir)}'",
            ]
            configure_command: str = f"./configure {' '.join(flags_to_configure_command)}"
            commands: str = " && ".join(
                [f"cd '{str(lib_base_folder)}'", configure_command, make_build_cmd(), "make install"]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(file_with_lib_source, lib_base_folder)

        maybe_build_library(
            skip_build=skip_build,
            lib_name=lib_name,
            version=LIBRARIES_SOURCES_VERSION[lib_name][1],
            artifacts=artifacts,
            compiled_library_folder=compiled_library_folder,
            clean_paths=[lib_base_folder, compiled_library_folder],
            build_fn=_build,
        )
        pkg_config_info: PkgConfigInfo = PkgConfigInfo(
            name=["ddjvuapi"], pkg_config_path=pkg_config_folder, static=True
        )
        return Library(
            name=lib_name,
            compiler_args=get_compiler_args(
                libraries=[pkg_config_info],
                extra_paths_to_search=[
                    x.pkg_config_info.pkg_config_path
                    for x in build_dependencies.values()
                    if x.pkg_config_info is not None and x.pkg_config_info.pkg_config_path is not None
                ],
            ),
            pkg_config_info=pkg_config_info,
            extra_dirs=ExtraDirs(
                include_dirs=[static_include_folder, static_include_folder.joinpath("libdjvu")],
                lib_dir=static_lib_folder,
            ),
            extra_objects=[static_lib_folder.joinpath("libdjvulibre.a")],
        )

    def build_openexr(build_dependencies: dict[str, Library], skip_build: bool = skip_build_external_libs) -> Library:
        return build_cmake_git_library(
            ctx=ctx,
            recipe=CMAKE_GIT_RECIPES["openexr"],
            skip_build=skip_build,
            dependencies=build_dependencies.values(),
        )

    def build_libraw(build_dependencies: dict[str, Library], skip_build: bool = skip_build_external_libs) -> Library:
        """
        Build libraw statically.

        Dependencies:
        - zlib
        - libjpeg
        """
        lib_name: str = "libraw"
        source_folder, compiled_name = _lib_dirs(name=lib_name)
        lib_base_folder: Path = build_directory.joinpath(source_folder)
        compiled_library_folder: Path = build_directory.joinpath(compiled_name)

        # Folders with the compiled library and the include files
        static_include_folder: Path = compiled_library_folder.joinpath(
            "include"
        )  # {build_directory}/libraw-{version}-compiled/include
        static_lib_folder: Path = compiled_library_folder.joinpath(
            "lib"
        )  # {build_directory}/libraw-{version}-compiled/lib
        pkg_config_folder: Path = static_lib_folder.joinpath(
            "pkgconfig"
        )  # {build_directory}/libraw-{version}-compiled/lib/pkgconfig
        artifacts: list[Path] = [static_lib_folder.joinpath("libraw.a"), static_lib_folder.joinpath("libraw_r.a")]

        def _build() -> None:
            pkg_config_path: list[str] = []
            for library_dep in build_dependencies.values():
                if library_dep.pkg_config_info is not None and library_dep.pkg_config_info.pkg_config_path is not None:
                    pkg_config_path.append(str(library_dep.pkg_config_info.pkg_config_path))

            git_clone_command: str = f"git clone {LIBRARIES_SOURCES_VERSION[lib_name][0]} '{str(lib_base_folder)}'"
            flags_to_configure_command: list[str] = [
                f"--prefix='{str(compiled_library_folder)}'",
                "--enable-static",
                "--disable-shared",
                "--with-pic=yes",
                "--enable-examples=no",
                "--enable-jpeg=yes",
                "--enable-zlib=yes",
                "--enable-openmp=no",
                "--enable-jasper=no",
                "--enable-lcms=no",
            ]
            configure_command: str = f"./configure {' '.join(flags_to_configure_command)}"
            build_compiler_args: CompilerArgs = CompilerArgs(
                cflags=build_dependencies["zlib"].compiler_args.cflags
                + build_dependencies["libjpeg"].compiler_args.cflags,
                libs=build_dependencies["zlib"].compiler_args.libs + build_dependencies["libjpeg"].compiler_args.libs,
            )
            commands: str = " && ".join(
                [
                    git_clone_command,
                    f"cd '{str(lib_base_folder)}'",
                    f"git switch --detach {LIBRARIES_SOURCES_VERSION[lib_name][1]}",
                    "autoreconf --install",
                    (
                        f'CFLAGS="{" ".join(build_compiler_args.cflags)}"'
                        f' LDFLAGS="{" ".join(build_compiler_args.libs)}" PKG_CONFIG_PATH="{":".join(pkg_config_path)}"'
                        f" {configure_command}"
                    ),
                    make_build_cmd(),
                    "make install",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(lib_base_folder)

        maybe_build_library(
            skip_build=skip_build,
            lib_name=lib_name,
            version=LIBRARIES_SOURCES_VERSION[lib_name][1],
            artifacts=artifacts,
            compiled_library_folder=compiled_library_folder,
            clean_paths=[lib_base_folder, compiled_library_folder],
            build_fn=_build,
        )
        pkg_config_info: PkgConfigInfo = PkgConfigInfo(
            name=[lib_name, "libraw_r"], pkg_config_path=pkg_config_folder, static=True
        )
        return Library(
            name=lib_name,
            compiler_args=get_compiler_args(
                libraries=[pkg_config_info],
                extra_paths_to_search=[
                    x.pkg_config_info.pkg_config_path
                    for x in build_dependencies.values()
                    if x.pkg_config_info is not None and x.pkg_config_info.pkg_config_path is not None
                ],
            ),
            pkg_config_info=pkg_config_info,
            extra_dirs=ExtraDirs(
                include_dirs=[static_include_folder, static_include_folder.joinpath("libraw")],
                lib_dir=static_lib_folder,
            ),
            extra_objects=[static_lib_folder.joinpath("libraw.a"), static_lib_folder.joinpath("libraw_r.a")],
        )

    base_libraries: dict[str, Library] = {}
    base_libraries["zlib"] = build_zlib()
    base_libraries["lzo"] = build_lzo()
    base_libraries["zstd"] = build_zstd()
    base_libraries["libjpeg"] = build_libjpeg()
    base_libraries["jbig"] = build_jbig()
    base_libraries["liblzma"] = build_liblzma()
    base_libraries["Imath"] = build_Imath()
    base_libraries["openjpeg"] = build_openjpeg()
    base_libraries["pixman"] = build_pixman()
    base_libraries["libpng"] = build_libpng(zlib=base_libraries["zlib"])
    base_libraries["libtiff"] = build_libtiff(
        build_dependencies=(
            {x: base_libraries[x] for x in base_libraries if x in ("zlib", "zstd", "libjpeg", "jbig", "liblzma")}
        ),
        enable_webp=False,
    )
    base_libraries["libwebp"] = build_libwebp(
        build_dependencies=(
            {x: base_libraries[x] for x in base_libraries if x in ("zlib", "libpng", "libjpeg", "libtiff")}
        )
    )
    base_libraries["libtiff"] = build_libtiff(
        build_dependencies=(
            {
                x: base_libraries[x]
                for x in base_libraries
                if x in ("zlib", "zstd", "libjpeg", "jbig", "liblzma", "libwebp")
            }
        ),
        enable_webp=True,
    )
    base_libraries["djvulibre"] = build_djvulibre(
        build_dependencies={x: base_libraries[x] for x in base_libraries if x in ("libjpeg", "libtiff")}
    )
    base_libraries["openexr"] = build_openexr(
        build_dependencies={x: base_libraries[x] for x in base_libraries if x in ("zlib", "Imath")}
    )
    base_libraries["libraw"] = build_libraw(
        build_dependencies={x: base_libraries[x] for x in base_libraries if x in ("zlib", "libjpeg")}
    )

    final_base_libraries: dict[str, Library] = {}
    for library_name, library in base_libraries.items():
        final_base_libraries[library_name] = library._replace(
            compiler_args=complete_linker_args(library=library, libraries=base_libraries)
        )

    return final_base_libraries


def build_core_libraries(
    build_directory: Path, skip_build_external_libs: bool, static: bool, base_libraries: dict[str, Library]
) -> dict[str, Library]:
    """
    Build core libraries needed to build the cython extensions.

    Core libraries:
    - `X11` (shared using pkg-config `x11`): (Also known as libX11) X Window System Protocol client library.
    - `Xss` (shared using pkg-config `xscrnsaver`): X Screen Saver extension client library.
    - `Xtst` (shared using pkg-config `xtst`): XTEST extension (synthetic key/button events).
    - `libgd`: https://github.com/libgd/libgd.git. Depends on `zlib` and `libpng`.
    - `MagickWand`: https://github.com/ImageMagick/ImageMagick.git. ImageMagick C library, depends on `djvulibre`, `jbig`, `libjpeg`, `liblzma`,
        `Imath`, `openexr`, `openjpeg` (`libopenjp2`), `libpng`, `libraw`, `libwebp`, `libtiff`, `zlib` and `zstd`.
    - `resvg`: https://github.com/RazrFalcon/resvg.git.
    - `cairo`: https://gitlab.freedesktop.org/cairo/cairo.git. Depends on `zlib`, `libpng`, `pixman` and `lzo`.
    - `libev`: https://github.com/enki/libev.git.
    """
    ctx: BuildContext = make_build_context(
        build_directory=build_directory, skip_build_external_libs=skip_build_external_libs, static=static, debug=debug
    )

    def build_libgd(build_dependencies: dict[str, Library], _debug_find_libraries: bool = False) -> Library:
        if not static:
            return Library(name="libgd", compiler_args=get_compiler_args(libraries=[PkgConfigInfo(name=["gdlib"])]))
        return build_cmake_git_library(
            ctx=ctx,
            recipe=CORE_CMAKE_RECIPES["libgd"],
            skip_build=skip_build_external_libs,
            dependencies=build_dependencies.values(),
        )

    def build_imagemagick(build_dependencies: dict[str, Library]) -> Library:
        """
        Build imagemagick.

        Dependencies (if static):
        - djvulibre
        - jbig
        - libjpeg
        - liblzma
        - Imath
        - openexr
        - openjpeg (libopenjp2)
        - libpng
        - libraw
        - libwebp
        - libtiff
        - zlib
        - zstd
        """
        lib_name: str = "imagemagick"

        if not static:
            return Library(
                name=lib_name, compiler_args=get_compiler_args(libraries=[PkgConfigInfo(name=["MagickWand"])])
            )  # shared library

        source_folder, compiled_name = _lib_dirs(name=lib_name)
        lib_base_folder: Path = build_directory.joinpath(source_folder)
        compiled_library_folder: Path = build_directory.joinpath(compiled_name)

        # Folders with the compiled library and the include files
        static_lib_folder: Path = compiled_library_folder.joinpath("lib")
        pkg_config_folder: Path = static_lib_folder.joinpath("pkgconfig")
        static_include_folder: Path = compiled_library_folder.joinpath("include")
        artifacts: list[Path] = [
            static_lib_folder.joinpath("libMagickCore-7.Q16HDRI.a"),
            static_lib_folder.joinpath("libMagickWand-7.Q16HDRI.a"),
        ]

        def _build() -> None:
            pkg_config_path: list[str] = []
            for library_dep in build_dependencies.values():
                if library_dep.pkg_config_info is not None and library_dep.pkg_config_info.pkg_config_path is not None:
                    pkg_config_path.append(str(library_dep.pkg_config_info.pkg_config_path))

            git_clone_command: str = f"git clone {LIBRARIES_SOURCES_VERSION[lib_name][0]} '{str(lib_base_folder)}'"
            flags_to_configure_command: list[str] = [
                f'--prefix="{str(compiled_library_folder)}"',
                "--enable-static",
                "--disable-shared",
                "--with-pic=yes",
                "--with-djvu=yes",
                "--with-jbig=yes",
                "--with-jpeg=yes",
                "--with-lzma=yes",
                "--with-openexr=yes",
                "--with-openjp2=yes",
                "--with-png=yes",
                "--with-raw=yes",
                "--with-rsvg=no",  # librsvg is not used, instead we use resvg
                "--with-tiff=yes",
                "--with-webp=yes",
                "--with-wmf=no",  # not included
                "--with-zlib=yes",
                "--with-zstd=yes",
                "--with-xml=no",
                "--with-bzlib=no",
                "--with-autotrace=no",
                "--with-dps=no",
                "--with-fftw=no",
                "--with-flif=no",
                "--with-fpx=no",
                "--with-fontconfig=no",
                "--with-freetype=no",
                "--with-gslib=no",
                "--with-gvc=no",
                "--with-heic=no",
                "--with-lcms=no",
                "--with-lqr=no",
                "--with-magick-plus-plus=no",
                "--with-pango=no",
                "--with-perl=no",
                "--with-raqm=no",
                "--with-x=no",
                "--with-zip=no",
                "--with-jxl=no",
            ]
            configure_command: str = f"./configure {' '.join(flags_to_configure_command)}"

            cflags: list[str] = []
            ldflags: list[str] = []
            for build_dep in build_dependencies.values():
                cflags.extend(build_dep.compiler_args.cflags)
                ldflags.extend(build_dep.compiler_args.libs)

            commands: str = " && ".join(
                [
                    git_clone_command,
                    f"cd '{str(lib_base_folder)}'",
                    f"git switch --detach {LIBRARIES_SOURCES_VERSION[lib_name][1]}",
                    (
                        f'CFLAGS="{" ".join(cflags)}" LIBS="{" ".join(ldflags)}"'
                        f' PKG_CONFIG_LIBDIR="{":".join(pkg_config_path)}" {configure_command}'
                    ),
                    make_build_cmd(),
                    "make install",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(lib_base_folder)

        maybe_build_library(
            skip_build=skip_build_external_libs,
            lib_name=lib_name,
            version=LIBRARIES_SOURCES_VERSION[lib_name][1],
            artifacts=artifacts,
            compiled_library_folder=compiled_library_folder,
            clean_paths=[lib_base_folder, compiled_library_folder],
            build_fn=_build,
        )
        pkg_config_info: PkgConfigInfo = PkgConfigInfo(
            name=["MagickWand"], pkg_config_path=pkg_config_folder, static=True
        )
        return Library(
            name=lib_name,
            compiler_args=get_compiler_args(
                libraries=[pkg_config_info],
                extra_paths_to_search=[
                    x.pkg_config_info.pkg_config_path
                    for x in build_dependencies.values()
                    if x.pkg_config_info is not None and x.pkg_config_info.pkg_config_path is not None
                ],
            ),
            pkg_config_info=pkg_config_info,
            extra_dirs=ExtraDirs(include_dirs=[static_include_folder], lib_dir=static_lib_folder),
            extra_objects=artifacts,
        )

    def build_resvg() -> Library:
        return build_cargo_git_library(ctx=ctx, recipe=CARGO_GIT_RECIPES["resvg"], skip_build=skip_build_external_libs)

    def build_cairo(build_dependencies: dict[str, Library]) -> Library:
        if not static:
            return Library(name="cairo", compiler_args=get_compiler_args(libraries=[PkgConfigInfo(name=["cairo"])]))
        return build_meson_git_library(
            ctx=ctx,
            recipe=CORE_MESON_RECIPES["cairo"],
            skip_build=skip_build_external_libs,
            dependencies=build_dependencies.values(),
        )

    def build_libev() -> Library:
        """Build libev"""

        lib_name: str = "libev"
        source_folder, compiled_name = _lib_dirs(name=lib_name)
        lib_base_folder: Path = build_directory.joinpath(source_folder)
        compiled_library_folder: Path = build_directory.joinpath(compiled_name)

        # Folders with the compiled library and the include files
        static_lib_folder: Path = compiled_library_folder.joinpath("lib")
        static_include_folder: Path = compiled_library_folder.joinpath("include")
        artifacts: list[Path] = [static_lib_folder.joinpath("libev.a")]

        def _build() -> None:
            url_of_file: str = LIBRARIES_SOURCES_VERSION[lib_name][0]
            tar_path: Path = Path(f"{lib_base_folder}.tar.gz")
            _ = urllib.request.urlretrieve(url=url_of_file, filename=str(tar_path))
            extract_tar_strip_components(tar_path=tar_path, destination_path=lib_base_folder, strip_components=1)

            flags_to_configure_command: list[str] = [
                f'--prefix="{str(compiled_library_folder)}"',
                "--enable-static",
                "--with-pic=yes",
            ]
            configure_command: str = f"./configure {' '.join(flags_to_configure_command)}"
            commands: str = " && ".join(
                [
                    f"cd '{str(lib_base_folder)}'",
                    configure_command,
                    make_build_cmd(),
                    "make install",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(tar_path, lib_base_folder)

        maybe_build_library(
            skip_build=skip_build_external_libs,
            lib_name=lib_name,
            version=LIBRARIES_SOURCES_VERSION[lib_name][1],
            artifacts=artifacts,
            compiled_library_folder=compiled_library_folder,
            clean_paths=[lib_base_folder, compiled_library_folder],
            build_fn=_build,
        )
        library: Library = Library(
            name=lib_name,
            compiler_args=CompilerArgs(
                cflags=[f"-I{str(static_include_folder)}"],
                libs=[f"-L{str(static_lib_folder)} -l:libev{'.a' if static else '.so'}"],
            ),
            extra_dirs=ExtraDirs(include_dirs=[static_include_folder], lib_dir=static_lib_folder),
        )
        if static:
            library = library._replace(extra_objects=[static_lib_folder.joinpath("libev.a")])
        return library

    core_libraries: dict[str, Library] = {}
    core_libraries["x11"] = Library(
        name="x11", compiler_args=get_compiler_args(libraries=[PkgConfigInfo(name=["x11"])])
    )
    core_libraries["xscrnsaver"] = Library(
        name="xscrnsaver", compiler_args=get_compiler_args(libraries=[PkgConfigInfo(name=["xscrnsaver"])])
    )
    core_libraries["xext"] = Library(
        name="xext", compiler_args=get_compiler_args(libraries=[PkgConfigInfo(name=["xext"])])
    )
    core_libraries["xtst"] = Library(
        name="xtst", compiler_args=get_compiler_args(libraries=[PkgConfigInfo(name=["xtst"])])
    )
    core_libraries["libgd"] = build_libgd(
        build_dependencies={x: base_libraries[x] for x in base_libraries if x in ("zlib", "libpng")} if static else {}
    )
    core_libraries["imagemagick"] = build_imagemagick(
        build_dependencies=(
            {
                x: base_libraries[x]
                for x in base_libraries
                if x
                in (
                    "djvulibre",
                    "jbig",  # doesn't have pkg-config files
                    "libjpeg",
                    "liblzma",
                    "Imath",
                    "openexr",
                    "openjpeg",
                    "libpng",
                    "libraw",
                    "libwebp",
                    "libtiff",
                    "zlib",
                    "zstd",
                )
            }
            if static
            else {}
        )
    )
    core_libraries["resvg"] = build_resvg()
    core_libraries["cairo"] = build_cairo(
        build_dependencies=(
            {x: base_libraries[x] for x in base_libraries if x in ("zlib", "libpng", "pixman", "lzo")} if static else {}
        )
    )
    core_libraries["libev"] = build_libev()

    final_core_libraries: dict[str, Library] = core_libraries
    if static:
        final_core_libraries = {}
        for library_name, library in core_libraries.items():
            final_core_libraries[library_name] = library._replace(
                compiler_args=complete_linker_args(
                    library=library, libraries=dict(list(base_libraries.items()) + list(core_libraries.items()))
                )
            )

    return final_core_libraries


def _cythonize_extensions(module_list: list[Extension], **options: Any) -> list[Extension]:
    cythonize: Callable[..., list[Extension]] = cast(
        Callable[..., list[Extension]],
        __import__(name="Cython.Build.Dependencies", fromlist=["cythonize"]).cythonize,
    )
    return cythonize(module_list=module_list, **options)


def cythonize_cython_extensions(
    build_directory: Path,
    static: bool,
    skip_build_external_libs: bool,
    force_cython: bool = False,
    validate_cached_libs: bool = False,
) -> list[Extension]:
    """
    Function that cythonize all the extensions to use with orcsome3.

    It takes all the cython files and produce a .c file ready to be compiled
    """
    extensions: list[Extension] = []
    try:
        if skip_build_external_libs and static and validate_cached_libs:
            validate_skipped_external_build(build_directory=build_directory)

        # Build base libraries, needed to build the core dependencies of the application
        base_libraries: dict[str, Library] = (
            build_base_libraries(build_directory=build_directory, skip_build_external_libs=skip_build_external_libs)
            if static
            else {}
        )

        # Build core libraries, these are the actual dependencies of the application
        core_libraries: dict[str, Library] = build_core_libraries(
            build_directory=build_directory,
            skip_build_external_libs=skip_build_external_libs,
            static=static,
            base_libraries=base_libraries,
        )

        # Get compile and link args
        extra_compile_args: list[str] = []
        extra_link_args: list[str] = []
        for library in core_libraries.values():
            for cflag in library.compiler_args.cflags:
                extra_compile_args.extend([x.strip() for x in cflag.split(sep=" ")])
            for ldflag in library.compiler_args.libs:
                extra_link_args.extend([x.strip() for x in ldflag.split(sep=" ")])

        # Add static libraries to the final .so
        extra_objects: list[str] = []
        extra_library_dirs: list[str] = []
        for library in list(base_libraries.values()) + list(core_libraries.values()):
            if library.extra_dirs is not None:
                extra_library_dirs.extend([str(x) for x in library.extra_dirs.iter_dirs()])
            if len(library.extra_objects):
                extra_objects.extend([str(x) for x in library.extra_objects])

        if not CYTHON_BACKEND_PYX.is_file():
            raise FileNotFoundError(f"Cython backend source not found: {CYTHON_BACKEND_PYX}")

        cython_source_files: list[Path] = [CYTHON_BACKEND_PYX]
        extensions = _cythonize_extensions(
            module_list=[
                Extension(
                    name=f"{APPNAME}_backend",  # Name of the produced shared library (.so), it should be: orcsome3_backend
                    language="c",
                    library_dirs=extra_library_dirs,
                    sources=[str(x) for x in cython_source_files],
                    extra_compile_args=extra_compile_args,
                    extra_link_args=extra_link_args,
                    extra_objects=extra_objects,
                )
            ],
            compiler_directives={"language_level": "3"},
            include_path=[str(CYTHON_LIBS_DIR)],
            force=force_cython,
        )
        for index, compiled_extension in enumerate(iterable=extensions):
            sources: list[str] = [str(s) for s in compiled_extension.sources]
            for other_index, source_file in enumerate(iterable=sources):
                path_source_file: Path = Path(source_file)
                new_path_source_file: Path = build_directory.joinpath(path_source_file.name)
                _ = shutil.move(src=path_source_file, dst=new_path_source_file)
                sources[other_index] = str(new_path_source_file)
            extensions[index].sources = sources
        return extensions
    except Exception as e:
        print("Exception in function 'cythonize_cython_extensions':", e)
        traceback.print_tb(tb=e.__traceback__)
        raise


def build_shared_library(
    extensions: list[Extension],
    directory: Path,
    keep_c_files: bool,
    install_dir: Optional[Path] = None,
) -> None:
    """Build final .so in `directory`"""
    install_destination: Optional[Path] = install_dir.resolve() if install_dir is not None else None

    def build_shared_library_() -> None:
        # Remove .so files
        files_to_remove: list[Path] = []
        extension_names: list[str] = [x.name for x in extensions]
        for shared_library in directory.rglob(pattern="*.so"):
            if shared_library.name in extension_names or any(
                substring in shared_library.name for substring in extension_names
            ):
                files_to_remove.append(shared_library)
        clean_build_directory(build_directory=directory, remove=files_to_remove)
        _ = setup(zip_safe=False, ext_modules=extensions, script_args=["build_ext", "--inplace"])
        files_to_remove_after_building_extensions: list[Path] = [directory.joinpath("build")]
        if not keep_c_files:
            for extension in extensions:
                for source_file in extension.sources:
                    files_to_remove_after_building_extensions.append(Path(source_file))
        clean_build_directory(build_directory=directory, remove=files_to_remove_after_building_extensions)
        if install_destination is not None:
            install_backend_for_local_dev(library_directory=directory, destination=install_destination)

    run_function_in_another_directory(directory=directory, function=build_shared_library_)


def build_extensions(
    skip_build_external_libs: bool,
    static: bool = True,
    build_dir: Optional[Path] = None,
    force_rebuild: bool = False,
    force_cython: bool = False,
    validate_cached_libs: bool = False,
) -> tuple[Path, list[Extension]]:
    """
    Create the build directory and prepare cython extensions.

    - skip_build_external_libs=True: reuse static libraries already in the build directory.
    - force_rebuild=True: wipe the build directory and rebuild external libraries.
    - force_cython=True: always regenerate C files from .pyx sources.
    """
    # cmake/meson --prefix is relative to their cwd; a relative `--build-dir .` nested the install tree.
    build_directory: Path = (Path.cwd() if build_dir is None else build_dir).resolve()
    new_build_directory: Path = build_directory.joinpath(f"{APPNAME}_built_libraries")
    if skip_build_external_libs:
        pass
    elif force_rebuild or env_force_rebuild():
        rmdir(new_build_directory)
    if not new_build_directory.is_dir():
        print("\nThe build directory does not exist, creating it...\n")
    new_build_directory.mkdir(exist_ok=True, parents=True)
    return new_build_directory, cythonize_cython_extensions(
        build_directory=new_build_directory,
        static=static,
        skip_build_external_libs=skip_build_external_libs,
        force_cython=force_cython,
        validate_cached_libs=validate_cached_libs,
    )


def main() -> None:
    """
    Function used to build the shared library (.so) needed for the application.

    It should be used as a module: `python -m orcsome3.libs.build --build-dir /build/dir`.

    The parameter `--build-dir` defaults to current working directory if not specified.

    It requires `git`, `cargo`, `cmake`, `autoreconf`, `meson` and `make` commands to be available on PATH when downloading and building the external libraries statically.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    _ = parser.add_argument(
        "-b",
        "--build-dir",
        help="Build directory of the libraries of the application. Defaults to current working directory",
        type=Path,
        default=Path.cwd(),
    )
    _ = parser.add_argument(
        "-d",
        "--dynamic",
        help=(
            "Build shared library (.so) using dynamic external libraries. By default, the final shared library is"
            " compiled with the external libraries statically"
        ),
        default=False,
        action="store_true",
    )
    _ = parser.add_argument(
        "-s",
        "--skip-build-external-libs",
        help=(
            "Skip downloading and building external libraries; only re-cythonize and re-link the backend "
            "(requires a previous full build in the build directory)"
        ),
        default=False,
        action="store_true",
    )
    _ = parser.add_argument(
        "-f",
        "--force-rebuild",
        help="Delete the build directory and rebuild all external libraries from scratch",
        default=False,
        action="store_true",
    )
    _ = parser.add_argument(
        "-k",
        "--keep-c-files",
        help=(
            "Keep the generated .c files produced when cythonizing the cython files. By default the generated .c file"
            + " gets deleted. Defaults to False"
        ),
        default=False,
        action="store_true",
    )
    _ = parser.add_argument("--debug", help="Show debug information", default=False, action="store_true")
    args: argparse.Namespace = parser.parse_args()
    project_directory: Path = args.build_dir
    build_using_dynamic_libraries: bool = args.dynamic
    skip_build_external_libs: bool = args.skip_build_external_libs
    force_rebuild_libraries: bool = args.force_rebuild
    if force_rebuild_libraries and skip_build_external_libs:
        print("Error: --force-rebuild cannot be used together with --skip-build-external-libs.")
        return
    if not skip_build_external_libs:
        needed_apps: list[str] = ["git", "cargo", "make"]
        if not build_using_dynamic_libraries:
            needed_apps.extend(["cmake", "autoreconf", "meson"])
        for needed_command in needed_apps:
            if not shutil.which(cmd=needed_command):
                print(f"Error: command {needed_command} not found.")
                return
    keep_c_files: bool = args.keep_c_files
    global debug
    debug = args.debug
    # `.so` is two steps: cythonize first (static libs + .pyx → setuptools Extension / .c),
    # then compile/link that Extension into orcsome3_backend*.so and copy it to the project dir.
    library_directory, extensions = build_extensions(
        skip_build_external_libs=skip_build_external_libs,
        static=not build_using_dynamic_libraries,
        build_dir=project_directory,
        force_rebuild=force_rebuild_libraries,
        force_cython=True,
        validate_cached_libs=skip_build_external_libs,
    )
    build_shared_library(
        extensions=extensions,
        directory=library_directory,
        keep_c_files=keep_c_files,
        install_dir=project_directory,
    )


if __name__ == "__main__":
    main()
