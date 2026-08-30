from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import traceback
import urllib.request
from pathlib import Path
from typing import Any, Callable, Generator, NamedTuple, Optional, cast

from Cython.Build.Dependencies import cythonize  # pyright: ignore[reportUnknownVariableType]
from setuptools import setup
from setuptools.extension import Extension

from orcsome3.common import APPNAME
from orcsome3.utils import extract_tar_strip_components, rmdir, run_command_and_show_output

debug: bool = False
LIBRARIES_SOURCES_VERSION: dict[str, tuple[str, str]] = {
    "zlib": ("https://github.com/madler/zlib.git", "v1.3.1"),
    "lzo": ("https://www.oberhumer.com/opensource/lzo/download/lzo-2.10.tar.gz", "v2.10"),
    "zstd": ("https://github.com/facebook/zstd.git", "v1.5.7"),
    "libjpeg": ("https://github.com/libjpeg-turbo/libjpeg-turbo.git", "3.1.1"),
    "jbig": ("https://www.cl.cam.ac.uk/~mgk25/git/jbigkit", "v2.1"),
    "liblzma": ("https://github.com/tukaani-project/xz.git", "v5.8.1"),
    "Imath": ("https://github.com/AcademySoftwareFoundation/Imath.git", "v3.1.12"),
    "openjpeg": ("https://github.com/uclouvain/openjpeg.git", "v2.5.3"),
    "libpng": ("https://github.com/pnggroup/libpng.git", "v1.6.49"),
    "libwebp": ("https://chromium.googlesource.com/webm/libwebp", "v1.5.0"),
    "pixman": ("https://gitlab.freedesktop.org/pixman/pixman.git", "pixman-0.46.2"),
    "libtiff": ("https://gitlab.com/libtiff/libtiff.git", "v4.7.0"),
    "djvulibre": (
        "https://sourceforge.net/projects/djvu/files/DjVuLibre/3.5.28/djvulibre-3.5.28.tar.gz/download",
        "v3.5.28",
    ),
    "openexr": ("https://github.com/AcademySoftwareFoundation/openexr", "v3.3.4"),
    "libraw": ("https://github.com/LibRaw/LibRaw.git", "0.21.4"),
}


class PkgConfigInfo(NamedTuple):
    name: list[str]
    pkg_config_path: Optional[Path] = None
    static: bool = False


class Library(NamedTuple):
    name: str
    compiler_args: CompilerArgs
    pkg_config_info: Optional[PkgConfigInfo] = None
    extra_dirs: Optional[ExtraDirs] = None
    extra_objects: list[Path] = []


class ExtraDirs(NamedTuple):
    include_dirs: list[Path]
    lib_dir: Path
    cmake_dirs: Optional[list[Path]] = None

    def iter_dirs(self) -> Generator[Path, Any, Any]:
        list_of_dirs: list[Path] = self.include_dirs
        list_of_dirs.append(self.lib_dir)
        if self.cmake_dirs is not None:
            list_of_dirs.extend(self.cmake_dirs)
        for dir_ in list_of_dirs:
            yield dir_


class CompilerArgs(NamedTuple):
    cflags: list[str]
    libs: list[str]


def get_compiler_args(
    libraries: list[PkgConfigInfo], extra_paths_to_search: Optional[list[Path]] = None
) -> CompilerArgs:
    """
    Generates compiler and linker arguments for the specified libraries using pkg-config.
    For each library in the `libraries` list, this function queries pkg-config to obtain
    the necessary compiler flags (`--cflags`) and linker flags (`--libs`). It supports
    searching additional pkg-config paths specified in `extra_paths_to_search` and
    handles static linking if requested by the library.

    Args:
        libraries (list[PkgConfigInfo]):
            A list of PkgConfigInfo objects representing the libraries to query.
        extra_paths_to_search (Optional[list[Path]], optional):
            Additional paths to search for pkg-config files. Defaults to None.

    Returns:
        CompilerArgs:
            An object containing the aggregated compiler flags (`cflags`) and linker flags (`libs`).
    """
    result_cflags: list[str] = []
    result_libs: list[str] = []

    pkg_config_paths: list[str] = []
    if extra_paths_to_search is not None and len(extra_paths_to_search):
        pkg_config_paths.extend([str(x) for x in extra_paths_to_search])
    pkg_config_path_original_value: Optional[str] = os.environ.get("PKG_CONFIG_PATH")

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
    """
    Completes the compiler and linker arguments for a given library by considering its dependencies.

    This function updates the `cflags` and `ldflags` of the provided `library` based on its dependencies listed in `libraries`.
    For each linker flag (`-l...`) in the library, it searches for the corresponding library object in `libraries`, and:
    - Ensures the required include directories are present in `cflags`.
    - Adds missing library paths (`-L...`) before the linker flag in `ldflags` if necessary.

    Args:
        library (Library): The library whose compiler and linker arguments are to be completed.
        libraries (dict[str, Library]): A dictionary of all available libraries, keyed by their names.

    Returns:
        CompilerArgs: The updated compiler arguments with completed `cflags` and `ldflags`.
    """
    cflags: list[str] = library.compiler_args.cflags
    ldflags: list[str] = library.compiler_args.libs
    # For every ldflag of `library` it searches inside `libraries` its corresponding library object
    # then it checks if the 'include' paths in extra_dirs of the Library object are part of the cflags of `library`
    # and then it checks if before the ldflag there should be the path of the library (-L/path/of/lib -llib) if not then it adds it
    for index, ldflag in enumerate(iterable=library.compiler_args.libs):
        if not ldflag.startswith("-l") or index == 0:
            continue
        library_info: Optional[ExtraDirs] = None
        for lib in libraries.values():
            if not len(lib.extra_objects) or lib.extra_dirs is None:
                continue
            for static_lib in lib.extra_objects:
                if f"-l{static_lib.name.replace('lib', '').replace('.a', '')}" == ldflag:
                    library_info = lib.extra_dirs
                    break
            if library_info is not None:
                break
        if library_info is None:
            continue

        # cflags
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

        # ldflags
        if library.compiler_args.libs[index - 1] != f"-L{str(library_info.lib_dir)}":
            if f"-L{str(library_info.lib_dir)}" not in library.compiler_args.libs[index]:
                ldflags[index] = f"-L{str(library_info.lib_dir)} {ldflags[index]}"

    return library.compiler_args._replace(cflags=cflags, libs=" ".join(ldflags).split(sep=" "))


def run_function_in_another_directory(directory: Path, function: Callable[..., Any]) -> Any:
    """Run function in another directory (os.chdir) and restore the original cwd when function finishes"""
    tmp: Path = Path.cwd()
    os.chdir(path=directory)
    result: Any = function()
    os.chdir(path=tmp)
    return result


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

    def build_zlib(skip_build: bool = skip_build_external_libs) -> Library:
        """Build zlib statically"""
        lib_name: str = "zlib"
        lib_base_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}"
        )  # {build_directory}/zlib-{version}
        compiled_library_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}-compiled"
        )  # {build_directory}/zlib-{version}-compiled

        # Folders with the compiled library and the include files
        static_include_folder: Path = compiled_library_folder.joinpath(
            "include"
        )  # {build_directory}/zlib-{version}-compiled/include
        static_lib_folder: Path = compiled_library_folder.joinpath(
            "lib"
        )  # {build_directory}/zlib-{version}-compiled/lib
        pkg_config_folder: Path = compiled_library_folder.joinpath(
            "share", "pkgconfig"
        )  # {build_directory}/zlib-{version}-compiled/share/pkgconfig

        if not skip_build:
            rmdir(lib_base_folder, compiled_library_folder)

            git_clone_command: str = f"git clone {LIBRARIES_SOURCES_VERSION[lib_name][0]} '{str(lib_base_folder)}'"
            flags_to_configure_command: list[str] = [
                f"-DCMAKE_FIND_DEBUG_MODE={'ON' if debug else 'OFF'}",
                f"-DCMAKE_INSTALL_PREFIX='{str(compiled_library_folder)}'",
                "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
                "-DBUILD_SHARED_LIBS=OFF",
            ]
            configure_command: str = (
                f"CMAKE_POLICY_VERSION_MINIMUM=3.5 cmake {' '.join(flags_to_configure_command)} -S ."
            )
            commands: str = " && ".join(
                [
                    git_clone_command,
                    f"cd '{str(lib_base_folder)}'",
                    f"git switch --detach {LIBRARIES_SOURCES_VERSION[lib_name][1]}",
                    configure_command,
                    "make",
                    "make install",
                ]
            )
            run_command_and_show_output(command=commands, cwd=build_directory)
            rmdir(lib_base_folder)
            for library_file in static_lib_folder.iterdir():
                if library_file.is_dir():
                    continue
                if not library_file.name.endswith(".a"):
                    library_file.unlink()
        pkg_config_info: PkgConfigInfo = PkgConfigInfo(name=[lib_name], pkg_config_path=pkg_config_folder, static=True)
        return Library(
            name=lib_name,
            compiler_args=get_compiler_args(libraries=[pkg_config_info]),
            pkg_config_info=pkg_config_info,
            extra_dirs=ExtraDirs(include_dirs=[static_include_folder], lib_dir=static_lib_folder),
            extra_objects=[static_lib_folder.joinpath("libz.a")],
        )

    def build_lzo(skip_build: bool = skip_build_external_libs) -> Library:
        """Build lzo statically"""
        lib_name: str = "lzo"
        lib_base_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}"
        )  # {build_directory}/lzo-{version}
        build_library_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}-build"
        )  # {build_directory}/lzo-{version}-build
        compiled_library_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}-compiled"
        )  # {build_directory}/lzo-{version}-compiled

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

        if not skip_build:
            rmdir(lib_base_folder, build_library_folder, compiled_library_folder)

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
                    "make",
                    "make install",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(file_with_lib_source, lib_base_folder, build_library_folder)
        pkg_config_info: PkgConfigInfo = PkgConfigInfo(name=["lzo2"], pkg_config_path=pkg_config_folder, static=True)
        return Library(
            name=lib_name,
            compiler_args=get_compiler_args(libraries=[pkg_config_info]),
            pkg_config_info=pkg_config_info,
            extra_dirs=ExtraDirs(include_dirs=[static_include_folder], lib_dir=static_lib_folder),
            extra_objects=[static_lib_folder.joinpath("liblzo2.a")],
        )

    def build_zstd(skip_build: bool = skip_build_external_libs) -> Library:
        """Build zstd statically"""
        lib_name: str = "zstd"
        lib_base_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}"
        )  # {build_directory}/zstd-{version}
        compiled_library_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}-compiled"
        )  # {build_directory}/zstd-{version}-compiled

        # Folders with the compiled library and the include files
        static_include_folder: Path = compiled_library_folder.joinpath(
            "include"
        )  # {build_directory}/zstd-{version}-compiled/include
        static_lib_folder: Path = compiled_library_folder.joinpath(
            "lib"
        )  # {build_directory}/zstd-{version}-compiled/lib
        pkg_config_folder: Path = static_lib_folder.joinpath(
            "pkgconfig"
        )  # {build_directory}/zstd-{version}-compiled/lib/pkgconfig

        if not skip_build:
            rmdir(lib_base_folder, compiled_library_folder)

            git_clone_command: str = f"git clone {LIBRARIES_SOURCES_VERSION[lib_name][0]} '{str(lib_base_folder)}'"
            flags_to_configure_command: list[str] = [
                f"-DCMAKE_FIND_DEBUG_MODE={'ON' if debug else 'OFF'}",
                f"-DCMAKE_INSTALL_PREFIX='{str(compiled_library_folder)}'",
                "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
            ]
            configure_command: str = (
                f"CMAKE_POLICY_VERSION_MINIMUM=3.5 cmake {' '.join(flags_to_configure_command)} -S ."
            )
            commands: str = " && ".join(
                [
                    git_clone_command,
                    f"cd '{str(lib_base_folder)}'",
                    f"git switch --detach {LIBRARIES_SOURCES_VERSION[lib_name][1]}",
                    "cd build",
                    "cd cmake",
                    configure_command,
                    "make",
                    "make install",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(lib_base_folder)
            for library_file in static_lib_folder.iterdir():
                if library_file.is_dir():
                    continue
                if not library_file.name.endswith(".a"):
                    library_file.unlink()
        pkg_config_info: PkgConfigInfo = PkgConfigInfo(name=["libzstd"], pkg_config_path=pkg_config_folder, static=True)
        return Library(
            name=lib_name,
            compiler_args=get_compiler_args(libraries=[pkg_config_info]),
            pkg_config_info=pkg_config_info,
            extra_dirs=ExtraDirs(
                include_dirs=[static_include_folder],
                lib_dir=static_lib_folder,
                cmake_dirs=[static_lib_folder.joinpath("cmake", "zstd")],
            ),
            extra_objects=[static_lib_folder.joinpath("libzstd.a")],
        )

    def build_libjpeg(skip_build: bool = skip_build_external_libs) -> Library:
        """Build libjpeg statically"""
        lib_name: str = "libjpeg"
        lib_base_folder: Path = build_directory.joinpath(
            f"{lib_name}-v{LIBRARIES_SOURCES_VERSION[lib_name][1]}"
        )  # {build_directory}/libjpeg-{version}
        compiled_library_folder: Path = build_directory.joinpath(
            f"{lib_name}-v{LIBRARIES_SOURCES_VERSION[lib_name][1]}-compiled"
        )  # {build_directory}/libjpeg-{version}-compiled

        # Folders with the compiled library and the include files
        static_include_folder: Path = compiled_library_folder.joinpath(
            "include"
        )  # {build_directory}/libjpeg-{version}-compiled/include
        static_lib_folder: Path = compiled_library_folder.joinpath(
            "lib64"
        )  # {build_directory}/libjpeg-{version}-compiled/lib64
        pkg_config_folder: Path = static_lib_folder.joinpath(
            "pkgconfig"
        )  # {build_directory}/libjpeg-{version}-compiled/lib64/pkgconfig

        if not skip_build:
            rmdir(lib_base_folder, compiled_library_folder)

            git_clone_command: str = f"git clone {LIBRARIES_SOURCES_VERSION[lib_name][0]} '{str(lib_base_folder)}'"
            flags_to_configure_command: list[str] = [
                f"-DCMAKE_FIND_DEBUG_MODE={'ON' if debug else 'OFF'}",
                f"-DCMAKE_INSTALL_PREFIX='{str(compiled_library_folder)}'",
                "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
                "-DENABLE_SHARED=FALSE",
                "-DENABLE_STATIC=TRUE",
                "-DWITH_TURBOJPEG=OFF",
            ]
            configure_command: str = (
                f"CMAKE_POLICY_VERSION_MINIMUM=3.5 cmake {' '.join(flags_to_configure_command)} -S ."
            )
            commands: str = " && ".join(
                [
                    git_clone_command,
                    f"cd '{str(lib_base_folder)}'",
                    f"git switch --detach {LIBRARIES_SOURCES_VERSION[lib_name][1]}",
                    configure_command,
                    "make",
                    "make install",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(lib_base_folder)
        pkg_config_info: PkgConfigInfo = PkgConfigInfo(name=[lib_name], pkg_config_path=pkg_config_folder, static=True)
        return Library(
            name=lib_name,
            compiler_args=get_compiler_args(libraries=[pkg_config_info]),
            pkg_config_info=pkg_config_info,
            extra_dirs=ExtraDirs(
                include_dirs=[static_include_folder],
                lib_dir=static_lib_folder,
                cmake_dirs=[static_lib_folder.joinpath("cmake", "libjpeg-turbo")],
            ),
            extra_objects=[static_lib_folder.joinpath("libjpeg.a")],
        )

    def build_jbig(skip_build: bool = skip_build_external_libs) -> Library:
        """Build jbig statically"""
        lib_name: str = "jbig"
        lib_base_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}"
        )  # {build_directory}/jbig-{version}
        compiled_library_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}-compiled"
        )  # {build_directory}/jbig-{version}-compiled
        if not skip_build:
            rmdir(lib_base_folder, compiled_library_folder)

            git_clone_command: str = f"git clone {LIBRARIES_SOURCES_VERSION[lib_name][0]} '{str(lib_base_folder)}'"
            commands: str = " && ".join(
                [
                    git_clone_command,
                    f"cd '{str(lib_base_folder)}'",
                    f"git switch --detach {LIBRARIES_SOURCES_VERSION[lib_name][1]}",
                    "make",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            _ = shutil.move(src=lib_base_folder.joinpath(f"lib{lib_name}"), dst=compiled_library_folder)
            rmdir(lib_base_folder)
        return Library(
            name=lib_name,
            compiler_args=CompilerArgs(
                cflags=[f"-I{str(compiled_library_folder)}"], libs=[f"-L{str(compiled_library_folder)}", "-l:libjbig.a"]
            ),
            extra_dirs=ExtraDirs(include_dirs=[compiled_library_folder], lib_dir=compiled_library_folder),
            extra_objects=[compiled_library_folder.joinpath("libjbig.a")],
        )

    def build_liblzma(skip_build: bool = skip_build_external_libs) -> Library:
        """Build liblzma statically"""
        lib_name: str = "liblzma"
        lib_base_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}"
        )  # {build_directory}/liblzma-{version}
        compiled_library_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}-compiled"
        )  # {build_directory}/liblzma-{version}-compiled

        # Folders with the compiled library and the include files
        static_include_folder: Path = compiled_library_folder.joinpath(
            "include"
        )  # {build_directory}/liblzma-{version}-compiled/include
        static_lib_folder: Path = compiled_library_folder.joinpath(
            "lib"
        )  # {build_directory}/liblzma-{version}-compiled/lib
        pkg_config_folder: Path = static_lib_folder.joinpath(
            "pkgconfig"
        )  # {build_directory}/liblzma-{version}-compiled/lib/pkgconfig

        if not skip_build:
            rmdir(lib_base_folder, compiled_library_folder)

            git_clone_command: str = f"git clone {LIBRARIES_SOURCES_VERSION[lib_name][0]} '{str(lib_base_folder)}'"
            flags_to_configure_command: list[str] = [
                f"-DCMAKE_FIND_DEBUG_MODE={'ON' if debug else 'OFF'}",
                f"-DCMAKE_INSTALL_PREFIX='{str(compiled_library_folder)}'",
                "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
                "-DBUILD_SHARED_LIBS=OFF",
                "-DXZ_TOOL_XZDEC=OFF",
                "-DXZ_TOOL_LZMADEC=OFF",
                "-DXZ_TOOL_LZMAINFO=OFF",
                "-DXZ_TOOL_XZ=OFF",
                "-DXZ_TOOL_SYMLINKS_LZMA=OFF",
                "-DXZ_TOOL_SCRIPTS=OFF",
                "-DXZ_DOC=OFF",
            ]
            configure_command: str = (
                f"CMAKE_POLICY_VERSION_MINIMUM=3.5 cmake {' '.join(flags_to_configure_command)} -S ."
            )
            commands: str = " && ".join(
                [
                    git_clone_command,
                    f"cd '{str(lib_base_folder)}'",
                    f"git switch --detach {LIBRARIES_SOURCES_VERSION[lib_name][1]}",
                    configure_command,
                    "make",
                    "make install",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(lib_base_folder)
        pkg_config_info: PkgConfigInfo = PkgConfigInfo(name=[lib_name], pkg_config_path=pkg_config_folder, static=True)
        return Library(
            name=lib_name,
            compiler_args=get_compiler_args(libraries=[pkg_config_info]),
            pkg_config_info=pkg_config_info,
            extra_dirs=ExtraDirs(
                include_dirs=[static_include_folder, static_include_folder.joinpath("lzma")],
                lib_dir=static_lib_folder,
                cmake_dirs=[static_lib_folder.joinpath("cmake", "liblzma")],
            ),
            extra_objects=[static_lib_folder.joinpath("liblzma.a")],
        )

    def build_Imath(skip_build: bool = skip_build_external_libs) -> Library:
        """Build Imath statically"""
        lib_name: str = "Imath"
        lib_base_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}"
        )  # {build_directory}/Imath-{version}
        compiled_library_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}-compiled"
        )  # {build_directory}/Imath-{version}-compiled

        # Folders with the compiled library and the include files
        static_include_folder: Path = compiled_library_folder.joinpath(
            "include"
        )  # {build_directory}/Imath-{version}-compiled/include
        static_lib_folder: Path = compiled_library_folder.joinpath(
            "lib"
        )  # {build_directory}/Imath-{version}-compiled/lib
        pkg_config_folder: Path = static_lib_folder.joinpath(
            "pkgconfig"
        )  # {build_directory}/Imath-{version}-compiled/lib/pkgconfig

        if not skip_build:
            rmdir(lib_base_folder, compiled_library_folder)

            git_clone_command: str = f"git clone {LIBRARIES_SOURCES_VERSION[lib_name][0]} '{str(lib_base_folder)}'"
            flags_to_configure_command: list[str] = [
                f"-DCMAKE_FIND_DEBUG_MODE={'ON' if debug else 'OFF'}",
                f"-DCMAKE_INSTALL_PREFIX='{str(compiled_library_folder)}'",
                "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
                "-DBUILD_SHARED_LIBS=OFF",
                "-DPYTHON=OFF",
                "-DBUILD_TESTING=OFF",
            ]
            configure_command: str = (
                f"CMAKE_POLICY_VERSION_MINIMUM=3.5 cmake {' '.join(flags_to_configure_command)} -S ."
            )
            commands: str = " && ".join(
                [
                    git_clone_command,
                    f"cd '{str(lib_base_folder)}'",
                    f"git switch --detach {LIBRARIES_SOURCES_VERSION[lib_name][1]}",
                    configure_command,
                    "make",
                    "make install",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(lib_base_folder)
        pkg_config_info: PkgConfigInfo = PkgConfigInfo(name=[lib_name], pkg_config_path=pkg_config_folder, static=True)
        return Library(
            name=lib_name,
            compiler_args=get_compiler_args(libraries=[pkg_config_info]),
            pkg_config_info=pkg_config_info,
            extra_dirs=ExtraDirs(
                include_dirs=[static_include_folder, static_include_folder.joinpath("Imath")],
                lib_dir=static_lib_folder,
                cmake_dirs=[static_lib_folder.joinpath("cmake", "Imath")],
            ),
            extra_objects=[static_lib_folder.joinpath("libImath-3_1.a")],
        )

    def build_openjpeg(skip_build: bool = skip_build_external_libs) -> Library:
        """Build openjpeg (libopenjp2) statically"""
        lib_name: str = "openjpeg"
        lib_base_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}"
        )  # {build_directory}/openjpeg-{version}
        compiled_library_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}-compiled"
        )  # {build_directory}/openjpeg-{version}-compiled

        # Folders with the compiled library and the include files
        static_include_folder: Path = compiled_library_folder.joinpath(
            "include"
        )  # {build_directory}/openjpeg-{version}-compiled/include
        static_lib_folder: Path = compiled_library_folder.joinpath(
            "lib"
        )  # {build_directory}/openjpeg-{version}-compiled/lib
        pkg_config_folder: Path = static_lib_folder.joinpath(
            "pkgconfig"
        )  # {build_directory}/openjpeg-{version}-compiled/lib/pkgconfig

        if not skip_build:
            rmdir(lib_base_folder, compiled_library_folder)

            git_clone_command: str = f"git clone {LIBRARIES_SOURCES_VERSION[lib_name][0]} '{str(lib_base_folder)}'"
            flags_to_configure_command: list[str] = [
                f"-DCMAKE_FIND_DEBUG_MODE={'ON' if debug else 'OFF'}",
                f"-DCMAKE_INSTALL_PREFIX='{str(compiled_library_folder)}'",
                "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
                "-DBUILD_SHARED_LIBS=OFF",
                "-DBUILD_STATIC_LIBS=ON",
                "-DBUILD_DOC=OFF",
                "-DBUILD_CODEC=OFF",
                "-DBUILD_JPIP=OFF",
                "-DBUILD_VIEWER=OFF",
                "-DBUILD_JAVA=OFF",
            ]
            configure_command: str = (
                f"CMAKE_POLICY_VERSION_MINIMUM=3.5 cmake {' '.join(flags_to_configure_command)} -S ."
            )
            commands: str = " && ".join(
                [
                    git_clone_command,
                    f"cd '{str(lib_base_folder)}'",
                    f"git switch --detach {LIBRARIES_SOURCES_VERSION[lib_name][1]}",
                    configure_command,
                    "make",
                    "make install",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(lib_base_folder)
        pkg_config_info: PkgConfigInfo = PkgConfigInfo(
            name=["libopenjp2"], pkg_config_path=pkg_config_folder, static=True
        )
        return Library(
            name=lib_name,
            compiler_args=get_compiler_args(libraries=[pkg_config_info]),
            pkg_config_info=pkg_config_info,
            extra_dirs=ExtraDirs(
                include_dirs=[static_include_folder, static_include_folder.joinpath("openjpeg-2.5")],
                lib_dir=static_lib_folder,
                cmake_dirs=[static_lib_folder.joinpath("cmake", "openjpeg-2.5")],
            ),
            extra_objects=[static_lib_folder.joinpath("libopenjp2.a")],
        )

    def build_pixman(skip_build: bool = skip_build_external_libs) -> Library:
        """Build pixman statically"""
        lib_name: str = "pixman"
        lib_base_folder: Path = build_directory.joinpath(
            f"{lib_name}-v{LIBRARIES_SOURCES_VERSION[lib_name][1].removeprefix('pixman-')}"
        )  # {build_directory}/pixman-{version}
        compiled_library_folder: Path = build_directory.joinpath(
            f"{lib_name}-v{LIBRARIES_SOURCES_VERSION[lib_name][1].removeprefix('pixman-')}-compiled"
        )  # {build_directory}/pixman-{version}-compiled

        # Folders with the compiled library and the include files
        static_include_folder: Path = compiled_library_folder.joinpath(
            "include"
        )  # {build_directory}/pixman-{version}-compiled/include
        static_lib_folder: Path = compiled_library_folder.joinpath(
            "lib"
        )  # {build_directory}/pixman-{version}-compiled/lib
        pkg_config_folder: Path = static_lib_folder.joinpath(
            "pkgconfig"
        )  # {build_directory}/pixman-{version}-compiled/lib/pkgconfig

        if not skip_build:
            rmdir(lib_base_folder, compiled_library_folder)

            git_clone_command: str = f"git clone {LIBRARIES_SOURCES_VERSION[lib_name][0]} '{str(lib_base_folder)}'"
            flags_to_configure_command: list[str] = [
                f"--prefix '{str(compiled_library_folder)}'",
                "--default-library static",
                "-Db_staticpic=true",
                "-Dopenmp=disabled",
                "-Dgtk=disabled",
                "-Dlibpng=disabled",
                "-Dtests=disabled",
            ]
            configure_command: str = f"meson setup builddir {' '.join(flags_to_configure_command)}"
            commands: str = " && ".join(
                [
                    git_clone_command,
                    f"cd '{str(lib_base_folder)}'",
                    f"git switch --detach {LIBRARIES_SOURCES_VERSION[lib_name][1]}",
                    configure_command,
                    "cd builddir",
                    "meson compile",
                    "meson install",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(lib_base_folder)
        pkg_config_info: PkgConfigInfo = PkgConfigInfo(
            name=["pixman-1"], pkg_config_path=pkg_config_folder, static=True
        )
        return Library(
            name=lib_name,
            compiler_args=get_compiler_args(libraries=[pkg_config_info]),
            pkg_config_info=pkg_config_info,
            extra_dirs=ExtraDirs(
                include_dirs=[static_include_folder, static_include_folder.joinpath("pixman-1")],
                lib_dir=static_lib_folder,
            ),
            extra_objects=[static_lib_folder.joinpath("libpixman-1.a")],
        )

    def build_libpng(zlib: Library, skip_build: bool = skip_build_external_libs) -> Library:
        """
        Build libpng statically.

        Depencencies:
        - zlib
        """
        lib_name: str = "libpng"
        lib_base_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}"
        )  # {build_directory}/libpng-{version}
        compiled_library_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}-compiled"
        )  # {build_directory}/libpng-{version}-compiled

        # Folders with the compiled library and the include files
        static_include_folder: Path = compiled_library_folder.joinpath(
            "include"
        )  # {build_directory}/libpng-{version}-compiled/include
        static_lib_folder: Path = compiled_library_folder.joinpath(
            "lib"
        )  # {build_directory}/libpng-{version}-compiled/lib
        pkg_config_folder: Path = static_lib_folder.joinpath(
            "pkgconfig"
        )  # {build_directory}/libpng-{version}-compiled/lib/pkgconfig

        if not skip_build:
            rmdir(lib_base_folder, compiled_library_folder)

            cmake_prefix_path: list[str] = []
            if zlib.pkg_config_info is not None and zlib.pkg_config_info.pkg_config_path is not None:
                cmake_prefix_path.append(str(zlib.pkg_config_info.pkg_config_path))
            if zlib.extra_dirs is not None:
                for extra_dir in zlib.extra_dirs.iter_dirs():
                    cmake_prefix_path.append(str(extra_dir))

            git_clone_command: str = f"git clone {LIBRARIES_SOURCES_VERSION[lib_name][0]} '{str(lib_base_folder)}'"
            flags_to_configure_command: list[str] = [
                f"-DCMAKE_FIND_DEBUG_MODE={'ON' if debug else 'OFF'}",
                f"-DCMAKE_PREFIX_PATH='{';'.join(cmake_prefix_path)}'",
                f"-DCMAKE_INSTALL_PREFIX='{str(compiled_library_folder)}'",
                "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
                "-DPNG_SHARED=OFF",
                "-DPNG_STATIC=ON",
                "-DPNG_EXECUTABLES=OFF",
                "-DPNG_TESTS=OFF",
            ]
            configure_command: str = (
                f"CMAKE_POLICY_VERSION_MINIMUM=3.5 cmake {' '.join(flags_to_configure_command)} -S ."
            )
            commands: str = " && ".join(
                [
                    git_clone_command,
                    f"cd '{str(lib_base_folder)}'",
                    f"git switch --detach {LIBRARIES_SOURCES_VERSION[lib_name][1]}",
                    configure_command,
                    "make",
                    "make install",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(lib_base_folder)
        pkg_config_info: PkgConfigInfo = PkgConfigInfo(name=[lib_name], pkg_config_path=pkg_config_folder, static=True)
        return Library(
            name=lib_name,
            compiler_args=get_compiler_args(
                libraries=[pkg_config_info],
                extra_paths_to_search=[cast(Path, cast(PkgConfigInfo, zlib.pkg_config_info).pkg_config_path)],
            ),
            pkg_config_info=pkg_config_info,
            extra_dirs=ExtraDirs(
                include_dirs=[static_include_folder, static_include_folder.joinpath("libpng16")],
                lib_dir=static_lib_folder,
                cmake_dirs=[static_lib_folder.joinpath("libpng"), static_lib_folder.joinpath("cmake", "PNG")],
            ),
            extra_objects=[static_lib_folder.joinpath("libpng.a"), static_lib_folder.joinpath("libpng16.a")],
        )

    def build_libwebp(build_dependencies: dict[str, Library], skip_build: bool = skip_build_external_libs) -> Library:
        """
        Build libwebp statically.

        Dependencies:
        - zlib
        - libpng
        - libjpeg
        - libtiff
        """
        lib_name: str = "libwebp"
        lib_base_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}"
        )  # {build_directory}/libwebp-{version}
        compiled_library_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}-compiled"
        )  # {build_directory}/libwebp-{version}-compiled

        # Folders with the compiled library and the include files
        static_include_folder: Path = compiled_library_folder.joinpath(
            "include"
        )  # {build_directory}/libwebp-{version}-compiled/include
        static_lib_folder: Path = compiled_library_folder.joinpath(
            "lib"
        )  # {build_directory}/libwebp-{version}-compiled/lib
        pkg_config_folder: Path = static_lib_folder.joinpath(
            "pkgconfig"
        )  # {build_directory}/libwebp-{version}-compiled/lib/pkgconfig

        if not skip_build:
            rmdir(lib_base_folder, compiled_library_folder)

            cmake_prefix_path: list[str] = []
            for library_dep in build_dependencies.values():
                if library_dep.pkg_config_info is not None and library_dep.pkg_config_info.pkg_config_path is not None:
                    cmake_prefix_path.append(str(library_dep.pkg_config_info.pkg_config_path))
                if library_dep.extra_dirs is not None:
                    for extra_dir in library_dep.extra_dirs.iter_dirs():
                        cmake_prefix_path.append(str(extra_dir))

            git_clone_command: str = f"git clone {LIBRARIES_SOURCES_VERSION[lib_name][0]} '{str(lib_base_folder)}'"
            flags_to_configure_command: list[str] = [
                f"-DCMAKE_FIND_DEBUG_MODE={'ON' if debug else 'OFF'}",
                f"-DCMAKE_PREFIX_PATH='{';'.join(cmake_prefix_path)}'",
                f"-DCMAKE_INSTALL_PREFIX='{str(compiled_library_folder)}'",
                "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
                "-DBUILD_SHARED_LIBS=OFF",
                "-DWEBP_BUILD_LIBWEBPMUX=ON",
                "-DWEBP_BUILD_WEBPMUX=ON",
                "-DWEBP_BUILD_ANIM_UTILS=OFF",
                "-DWEBP_BUILD_CWEBP=OFF",
                "-DWEBP_BUILD_DWEBP=OFF",
                "-DWEBP_BUILD_GIF2WEBP=OFF",
                "-DWEBP_BUILD_IMG2WEBP=OFF",
                "-DWEBP_BUILD_VWEBP=OFF",
                "-DWEBP_BUILD_WEBPINFO=OFF",
                "-DWEBP_BUILD_EXTRAS=OFF",
            ]
            configure_command: str = (
                f"CMAKE_POLICY_VERSION_MINIMUM=3.5 cmake {' '.join(flags_to_configure_command)} -S ."
            )
            run_command_and_show_output(
                command=" && ".join(
                    [
                        "printf '\\n'",
                        git_clone_command,
                        f"cd '{str(lib_base_folder)}'",
                        f"git switch --detach {LIBRARIES_SOURCES_VERSION[lib_name][1]}",
                    ]
                ),
                cwd=build_directory,
            )

            # Edit file {build_directory}/libwebp-{version}/cmake/deps.cmake to allow static linking with libtiff
            file_to_edit: Path = lib_base_folder.joinpath("cmake", "deps.cmake")
            lines_of_file_to_edit: list[str] = []
            with file_to_edit.open(mode="r") as file_:
                lines_of_file_to_edit = file_.readlines()
            for index, line in enumerate(iterable=lines_of_file_to_edit):
                if '"TIFF is disabled when statically linking."' in line:
                    lines_of_file_to_edit[index + 1] = f"#{lines_of_file_to_edit[index + 1]}"
                    break
            with file_to_edit.open(mode="w") as file_:
                file_.writelines(lines_of_file_to_edit)

            commands: str = " && ".join([f"cd '{str(lib_base_folder)}'", configure_command, "make", "make install"])
            run_command_and_show_output(command=commands, cwd=build_directory)
            rmdir(lib_base_folder)
        pkg_config_info: PkgConfigInfo = PkgConfigInfo(name=[lib_name], pkg_config_path=pkg_config_folder, static=True)
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
                include_dirs=[
                    static_include_folder,
                    static_include_folder.joinpath("webp"),
                    static_include_folder.joinpath("webp", "sharpyuv"),
                ],
                lib_dir=static_lib_folder,
                cmake_dirs=[compiled_library_folder.joinpath("share", "WebP", "cmake")],
            ),
            extra_objects=[
                static_lib_folder.joinpath("libwebp.a"),
                static_lib_folder.joinpath("libsharpyuv.a"),
                static_lib_folder.joinpath("libwebpdecoder.a"),
                static_lib_folder.joinpath("libwebpdemux.a"),
                static_lib_folder.joinpath("libwebpmux.a"),
            ],
        )

    def build_libtiff(
        build_dependencies: dict[str, Optional[Library]], skip_build: bool = skip_build_external_libs
    ) -> Library:
        """
        Buld libtiff statically.

        Dependencies:
        - zlib
        - zstd
        - libjpeg
        - jbig
        - liblzma
        - libwebp
        """
        lib_name: str = "libtiff"
        lib_base_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}"
        )  # {build_directory}/libtiff-{version}
        compiled_library_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}-compiled"
        )  # {build_directory}/libtiff-{version}-compiled

        # Folders with the compiled library and the include files
        static_include_folder: Path = compiled_library_folder.joinpath(
            "include"
        )  # {build_directory}/libtiff-{version}-compiled/include
        static_lib_folder: Path = compiled_library_folder.joinpath(
            "lib"
        )  # {build_directory}/libtiff-{version}-compiled/lib
        pkg_config_folder: Path = static_lib_folder.joinpath(
            "pkgconfig"
        )  # {build_directory}/libtiff-{version}-compiled/lib/pkgconfig

        if not skip_build:
            rmdir(lib_base_folder, compiled_library_folder)

            cmake_prefix_path: list[str] = []
            for library_dep in build_dependencies.values():
                if library_dep is None:
                    continue
                if library_dep.pkg_config_info is not None and library_dep.pkg_config_info.pkg_config_path is not None:
                    cmake_prefix_path.append(str(library_dep.pkg_config_info.pkg_config_path))
                if library_dep.extra_dirs is not None:
                    for extra_dir in library_dep.extra_dirs.iter_dirs():
                        cmake_prefix_path.append(str(extra_dir))

            git_clone_command: str = f"git clone {LIBRARIES_SOURCES_VERSION[lib_name][0]} '{str(lib_base_folder)}'"
            flags_to_configure_command: list[str] = [
                f"-DCMAKE_FIND_DEBUG_MODE={'ON' if debug else 'OFF'}",
                f"-DCMAKE_PREFIX_PATH='{';'.join(cmake_prefix_path)}'",
                f"-DCMAKE_INSTALL_PREFIX='{str(compiled_library_folder)}'",
                "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
                "-DBUILD_SHARED_LIBS=OFF",
                "-Dzlib=ON",
                "-Dzstd=ON",
                "-Djpeg=ON",
                "-Djbig=ON",
                "-Dlzma=ON",
                f"-Dwebp={'ON' if build_dependencies.get('libwebp') is not None else 'OFF'}",
                "-Dlibdeflate=OFF",
                "-Dpixarlog=OFF",
                "-Dlerc=OFF",
                "-Dcxx=OFF",
                "-Dtiff-opengl=OFF",
                "-Dtiff-tools=OFF",
                "-Dtiff-tests=OFF",
                "-Dtiff-contrib=OFF",
                "-Dtiff-docs=OFF",
            ]
            configure_command: str = (
                f"CMAKE_POLICY_VERSION_MINIMUM=3.5 cmake {' '.join(flags_to_configure_command)} -S ."
            )
            commands: str = " && ".join(
                [
                    git_clone_command,
                    f"cd '{str(lib_base_folder)}'",
                    f"git switch --detach {LIBRARIES_SOURCES_VERSION[lib_name][1]}",
                    configure_command,
                    "make",
                    "make install",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(lib_base_folder)
        pkg_config_info: PkgConfigInfo = PkgConfigInfo(
            name=["libtiff-4"], pkg_config_path=pkg_config_folder, static=True
        )
        return Library(
            name=lib_name,
            compiler_args=get_compiler_args(
                libraries=[pkg_config_info],
                extra_paths_to_search=[
                    x.pkg_config_info.pkg_config_path
                    for x in build_dependencies.values()  # jbig not included, it doesn't have pkg-config info
                    if x is not None
                    and (x.pkg_config_info is not None and x.pkg_config_info.pkg_config_path is not None)
                ],
            ),
            pkg_config_info=pkg_config_info,
            extra_dirs=ExtraDirs(
                include_dirs=[static_include_folder],
                lib_dir=static_lib_folder,
                cmake_dirs=[static_lib_folder.joinpath("cmake", "tiff")],
            ),
            extra_objects=[static_lib_folder.joinpath("libtiff.a")],
        )

    def build_djvulibre(build_dependencies: dict[str, Library], skip_build: bool = skip_build_external_libs) -> Library:
        """
        Buld djvulibre statically.

        Dependencies:
        - libjpeg
        - libtiff
        """
        lib_name: str = "djvulibre"
        lib_base_folder: Path = build_directory.joinpath(
            f"{lib_name}-v{LIBRARIES_SOURCES_VERSION[lib_name][1]}"
        )  # {build_directory}/djvulibre-{version}
        compiled_library_folder: Path = build_directory.joinpath(
            f"{lib_name}-v{LIBRARIES_SOURCES_VERSION[lib_name][1]}-compiled"
        )  # {build_directory}/djvulibre-{version}-compiled

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

        if not skip_build:
            rmdir(lib_base_folder, compiled_library_folder)

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
            commands: str = " && ".join([f"cd '{str(lib_base_folder)}'", configure_command, "make", "make install"])
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(file_with_lib_source, lib_base_folder)
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
        """
        Buld openexr statically.

        Dependencies:
        - zlib
        - Imath
        """
        lib_name: str = "openexr"
        lib_base_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}"
        )  # {build_directory}/openexr-{version}
        compiled_library_folder: Path = build_directory.joinpath(
            f"{lib_name}-{LIBRARIES_SOURCES_VERSION[lib_name][1]}-compiled"
        )  # {build_directory}/openexr-{version}-compiled

        # Folders with the compiled library and the include files
        static_include_folder: Path = compiled_library_folder.joinpath(
            "include"
        )  # {build_directory}/openexr-{version}-compiled/include
        static_lib_folder: Path = compiled_library_folder.joinpath(
            "lib"
        )  # {build_directory}/openexr-{version}-compiled/lib
        pkg_config_folder: Path = static_lib_folder.joinpath(
            "pkgconfig"
        )  # {build_directory}/openexr-{version}-compiled/lib/pkgconfig

        if not skip_build:
            rmdir(lib_base_folder, compiled_library_folder)

            cmake_prefix_path: list[str] = []
            for library_dep in build_dependencies.values():
                if library_dep.pkg_config_info is not None and library_dep.pkg_config_info.pkg_config_path is not None:
                    cmake_prefix_path.append(str(library_dep.pkg_config_info.pkg_config_path))
                for extra_dir in cast(ExtraDirs, library_dep.extra_dirs).iter_dirs():
                    cmake_prefix_path.append(str(extra_dir))

            git_clone_command: str = f"git clone {LIBRARIES_SOURCES_VERSION[lib_name][0]} '{str(lib_base_folder)}'"
            flags_to_configure_command: list[str] = [
                f"-DCMAKE_FIND_DEBUG_MODE={'ON' if debug else 'OFF'}",
                f"-DCMAKE_PREFIX_PATH='{';'.join(cmake_prefix_path)}'",
                f"-DCMAKE_INSTALL_PREFIX='{str(compiled_library_folder)}'",
                "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
                "-DBUILD_SHARED_LIBS=OFF",
                "-DOPENEXR_INSTALL_TOOLS=OFF",
                "-DBUILD_DOCS=OFF",
            ]
            configure_command: str = (
                f"CMAKE_POLICY_VERSION_MINIMUM=3.5 cmake {' '.join(flags_to_configure_command)} -S ."
            )
            commands: str = " && ".join(
                [
                    git_clone_command,
                    f"cd '{str(lib_base_folder)}'",
                    f"git switch --detach {LIBRARIES_SOURCES_VERSION[lib_name][1]}",
                    configure_command,
                    "make",
                    "make install",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(lib_base_folder)
        pkg_config_info: PkgConfigInfo = PkgConfigInfo(name=["OpenEXR"], pkg_config_path=pkg_config_folder, static=True)
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
                include_dirs=[static_include_folder, static_include_folder.joinpath("OpenEXR")],
                lib_dir=static_lib_folder,
                cmake_dirs=[static_lib_folder.joinpath("cmake")],
            ),
            extra_objects=[
                static_lib_folder.joinpath("libIex-3_3.a"),
                static_lib_folder.joinpath("libIlmThread-3_3.a"),
                static_lib_folder.joinpath("libOpenEXR-3_3.a"),
                static_lib_folder.joinpath("libOpenEXRCore-3_3.a"),
                static_lib_folder.joinpath("libOpenEXRUtil-3_3.a"),
            ],
        )

    def build_libraw(build_dependencies: dict[str, Library], skip_build: bool = skip_build_external_libs) -> Library:
        """
        Build libraw statically.

        Dependencies:
        - zlib
        - libjpeg
        """
        lib_name: str = "libraw"
        lib_base_folder: Path = build_directory.joinpath(
            f"{lib_name}-v{LIBRARIES_SOURCES_VERSION[lib_name][1]}"
        )  # {build_directory}/libraw-{version}
        compiled_library_folder: Path = build_directory.joinpath(
            f"{lib_name}-v{LIBRARIES_SOURCES_VERSION[lib_name][1]}-compiled"
        )  # {build_directory}/libraw-{version}-compiled

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

        if not skip_build:
            rmdir(lib_base_folder, compiled_library_folder)

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
                    "make",
                    "make install",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(lib_base_folder)
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
        )
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
        )
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
    - `libgd`: https://github.com/libgd/libgd.git. Depends on `zlib` and `libpng`.
    - `MagickWand`: https://github.com/ImageMagick/ImageMagick.git. ImageMagick C library, depends on `djvulibre`, `jbig`, `libjpeg`, `liblzma`,
        `Imath`, `openexr`, `openjpeg` (`libopenjp2`), `libpng`, `libraw`, `libwebp`, `libtiff`, `zlib` and `zstd`.
    - `resvg`: https://github.com/RazrFalcon/resvg.git.
    - `cairo`: https://gitlab.freedesktop.org/cairo/cairo.git. Depends on `zlib`, `libpng`, `pixman` and `lzo`.
    - `libev`: https://github.com/enki/libev.git.
    """

    def build_libgd(build_dependencies: dict[str, Library], debug_find_libraries: bool = False) -> Library:
        """
        Build libgd.

        Dependencies (if static):
        - zlib
        - libpng
        """
        lib_name: str = "libgd"

        if not static:
            return Library(
                name=lib_name, compiler_args=get_compiler_args(libraries=[PkgConfigInfo(name=["gdlib"])])
            )  # shared library

        lib_base_folder: Path = build_directory.joinpath(lib_name)  # ./libgd
        compiled_library_folder: Path = build_directory.joinpath(f"{lib_name}-compiled")  # ./libgd-compiled

        # Folders with the compiled library and the include files
        static_lib_folder: Path = compiled_library_folder.joinpath("lib")  # ./libgd-compiled/lib
        pkg_config_folder: Path = static_lib_folder.joinpath("pkgconfig")  # ./libgd-compiled/lib/pkgconfig
        static_include_folder: Path = compiled_library_folder.joinpath("include")  # ./libgd-compiled/include

        if not skip_build_external_libs:
            rmdir(lib_base_folder, compiled_library_folder)

            cmake_prefix_path: list[str] = []
            for dependency in build_dependencies.values():
                for extra_dir in cast(ExtraDirs, dependency.extra_dirs).iter_dirs():
                    cmake_prefix_path.append(str(extra_dir))

            git_clone_command: str = f"git clone https://github.com/libgd/libgd.git {lib_name}"
            flags_to_configure_command: list[str] = [
                f"-DCMAKE_FIND_DEBUG_MODE={'ON' if debug_find_libraries else 'OFF'}",
                f'-DCMAKE_PREFIX_PATH="{";".join(cmake_prefix_path)}"',
                f"-DCMAKE_INSTALL_PREFIX={str(compiled_library_folder)}",
                "-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
                "-DENABLE_PNG=ON",
                "-DENABLE_CPP=OFF",
                "-DBUILD_SHARED_LIBS=OFF",
                "-DBUILD_STATIC_LIBS=ON",
                "-DBUILD_TEST=OFF",
            ]
            configure_command: str = (
                f"CMAKE_POLICY_VERSION_MINIMUM=3.5 cmake {' '.join(flags_to_configure_command)} -S ."
            )
            commands: str = " && ".join(
                [
                    git_clone_command,
                    f"cd {str(lib_base_folder)}",
                    "git switch --detach gd-2.3.3",
                    configure_command,
                    "make",
                    "make install",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(lib_base_folder)
        pkg_config_info: PkgConfigInfo = PkgConfigInfo(name=["gdlib"], pkg_config_path=pkg_config_folder, static=True)
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
            extra_objects=[static_lib_folder.joinpath("libgd.a")],
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

        lib_base_folder: Path = build_directory.joinpath(lib_name)  # ./imagemagick
        compiled_library_folder: Path = build_directory.joinpath(f"{lib_name}-compiled")  # ./imagemagick-compiled

        # Folders with the compiled library and the include files
        static_lib_folder: Path = compiled_library_folder.joinpath("lib")  # ./imagemagick-compiled/lib
        pkg_config_folder: Path = static_lib_folder.joinpath("pkgconfig")  # ./imagemagick-compiled/lib/pkgconfig
        static_include_folder: Path = compiled_library_folder.joinpath("include")  # ./imagemagick-compiled/include

        if not skip_build_external_libs:
            rmdir(lib_base_folder, compiled_library_folder)

            pkg_config_path: list[str] = []
            for library_dep in build_dependencies.values():
                if library_dep.pkg_config_info is not None and library_dep.pkg_config_info.pkg_config_path is not None:
                    pkg_config_path.append(str(library_dep.pkg_config_info.pkg_config_path))

            git_clone_command: str = f"git clone https://github.com/ImageMagick/ImageMagick.git {lib_name}"
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
                    f"cd {lib_name}",
                    "git switch --detach 7.1.0-60",
                    (
                        f'CFLAGS="{" ".join(cflags)}" LIBS="{" ".join(ldflags)}"'
                        f' PKG_CONFIG_LIBDIR="{":".join(pkg_config_path)}" {configure_command}'
                    ),
                    "make",
                    "make install",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(lib_base_folder)
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
            extra_objects=[
                static_lib_folder.joinpath("libMagickCore-7.Q16HDRI.a"),
                static_lib_folder.joinpath("libMagickWand-7.Q16HDRI.a"),
            ],
        )

    def build_resvg() -> Library:
        """Build resvg statically"""
        lib_name: str = "resvg"

        lib_base_folder: Path = build_directory.joinpath(lib_name)  # ./resvg
        compiled_library_folder: Path = build_directory.joinpath(f"{lib_name}-compiled")  # ./resvg-compiled

        # Folders with the compiled library and the include files
        static_lib_folder: Path = compiled_library_folder.joinpath("lib")  # ./resvg-compiled/lib
        static_include_folder: Path = compiled_library_folder.joinpath("include")  # ./resvg-compiled/include

        if not skip_build_external_libs:
            rmdir(lib_base_folder, compiled_library_folder)

            git_clone_command: str = f"git clone https://github.com/RazrFalcon/resvg.git {lib_name}"
            commands: str = " && ".join(
                [
                    git_clone_command,
                    f"mkdir -p {str(compiled_library_folder)} {str(static_lib_folder)} {str(static_include_folder)}",
                    f"cd {str(lib_base_folder)}",
                    "git switch --detach v0.30.0",
                    "cd c-api",
                    "cargo build --release",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            _ = shutil.move(src=lib_base_folder.joinpath("c-api", "resvg.h"), dst=static_include_folder)
            _ = shutil.move(src=lib_base_folder.joinpath("target", "release", "libresvg.a"), dst=static_lib_folder)
            rmdir(lib_base_folder)
        return Library(
            name=lib_name,
            compiler_args=CompilerArgs(
                cflags=[f"-I{str(static_include_folder)}"], libs=[f"-L{str(static_lib_folder)} -lresvg -lm"]
            ),
            extra_dirs=ExtraDirs(include_dirs=[static_include_folder], lib_dir=static_lib_folder),
            extra_objects=[static_lib_folder.joinpath("libresvg.a")],
        )

    def build_cairo(build_dependencies: dict[str, Library]) -> Library:
        """
        Build cairo.

        Dependencies (if static):
        - zlib
        - libpng
        - pixman
        - lzo
        """
        lib_name: str = "cairo"

        if not static:
            return Library(
                name=lib_name, compiler_args=get_compiler_args(libraries=[PkgConfigInfo(name=[lib_name])])
            )  # shared library

        lib_base_folder: Path = build_directory.joinpath(lib_name)  # ./cairo
        compiled_library_folder: Path = build_directory.joinpath(f"{lib_name}-compiled")  # ./cairo-compiled

        # Folders with the compiled library and the include files
        static_lib_folder: Path = compiled_library_folder.joinpath("lib")  # ./cairo-compiled/lib
        pkg_config_folder: Path = static_lib_folder.joinpath("pkgconfig")  # ./cairo-compiled/lib/pkgconfig
        static_include_folder: Path = compiled_library_folder.joinpath("include")  # ./cairo-compiled/include

        if not skip_build_external_libs:
            rmdir(lib_base_folder, compiled_library_folder)

            pkg_config_path: list[str] = []
            for library_dep in build_dependencies.values():
                if library_dep.pkg_config_info is not None and library_dep.pkg_config_info.pkg_config_path is not None:
                    pkg_config_path.append(str(library_dep.pkg_config_info.pkg_config_path))

            git_clone_command: str = f"git clone https://gitlab.freedesktop.org/cairo/cairo.git {lib_name}"
            flags_to_configure_command: list[str] = [
                f'--prefix "{str(compiled_library_folder)}"',
                f'-Dpkg_config_path="{":".join(pkg_config_path)}"',
                "--default-library static",
                "-Db_staticpic=true",
                "-Dfontconfig=disabled",
                "-Dfreetype=disabled",
                "-Dpng=enabled",
                "-Dquartz=disabled",
                "-Dxcb=disabled",
                "-Dxlib=disabled",
                "-Dzlib=enabled",
                "-Dtests=disabled",
                "-Dgtk2-utils=disabled",
                "-Dglib=disabled",
                "-Dspectre=disabled",
                "-Dsymbol-lookup=disabled",
                "-Dgtk_doc=false",
            ]
            configure_command: str = f"meson setup builddir {' '.join(flags_to_configure_command)}"
            commands: str = " && ".join(
                [
                    git_clone_command,
                    f"cd {lib_name}",
                    "git switch --detach 1.17.8",
                    configure_command,
                    "cd builddir",
                    "meson compile",
                    "meson install",
                ]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(lib_base_folder)
        pkg_config_info: PkgConfigInfo = PkgConfigInfo(name=[lib_name], pkg_config_path=pkg_config_folder, static=True)
        return Library(
            name=lib_name,
            compiler_args=get_compiler_args(libraries=[pkg_config_info]),
            pkg_config_info=pkg_config_info,
            extra_dirs=ExtraDirs(include_dirs=[static_include_folder], lib_dir=static_lib_folder),
            extra_objects=[static_lib_folder.joinpath("libcairo.a")],
        )

    def build_libev() -> Library:
        """Build libev"""

        lib_name: str = "libev"

        lib_base_folder: Path = build_directory.joinpath(lib_name)  # ./libev
        compiled_library_folder: Path = build_directory.joinpath(f"{lib_name}-compiled")  # ./libev-compiled

        # Folders with the compiled library and the include files
        static_lib_folder: Path = compiled_library_folder.joinpath("lib")  # ./libev-compiled/lib
        static_include_folder: Path = compiled_library_folder.joinpath("include")  # ./libev-compiled/include

        if not skip_build_external_libs:
            rmdir(lib_base_folder, compiled_library_folder)

            lib_base_folder.mkdir()
            url_of_file: str = "http://dist.schmorp.de/libev/libev-4.33.tar.gz"
            file_name: str = "libev-4.33.tar.gz"
            tar_path: Path = lib_base_folder.joinpath(file_name)
            _ = urllib.request.urlretrieve(url=url_of_file, filename=str(tar_path))
            extract_tar_strip_components(tar_path=tar_path, destination_path=lib_base_folder)

            flags_to_configure_command: list[str] = [
                f'--prefix="{str(compiled_library_folder)}"',
                "--enable-static",
                "--with-pic=yes",
            ]
            configure_command: str = f"./configure {' '.join(flags_to_configure_command)}"
            commands: str = " && ".join(
                [f"cd {lib_name}", f"cd {file_name.replace('.tar.gz', '')}", configure_command, "make", "make install"]
            )
            run_command_and_show_output(command=f"printf '\\n' && {commands}", cwd=build_directory)
            rmdir(lib_base_folder)
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


def cythonize_cython_extensions(build_directory: Path, static: bool, skip_build_external_libs: bool) -> list[Extension]:
    """
    Function that cythonize all the extensions to use with orcsome3.

    It takes all the cython files and produce a .c file ready to be compiled
    """
    extensions: list[Extension] = []
    try:
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

        cython_source_files: list[Path] = [Path(__file__).parent.joinpath("orcsome3_backend.pyx")]
        extensions = cast(
            list[Extension],
            cythonize(
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
                include_path=[str(x.parent) for x in cython_source_files],  # Include the cython_libs directory
            ),
        )
        for index, compiled_extension in enumerate(iterable=extensions):
            for other_index, source_file in enumerate(iterable=compiled_extension.sources):
                path_source_file: Path = Path(source_file)
                new_path_source_file: Path = build_directory.joinpath(path_source_file.name)
                _ = shutil.move(src=path_source_file, dst=new_path_source_file)
                extensions[index].sources[other_index] = str(new_path_source_file)
        return extensions
    except Exception as e:
        print("Exception in function 'cythonize_cython_extensions':", e)
        traceback.print_tb(tb=e.__traceback__)
        return []


def build_shared_library(extensions: list[Extension], directory: Path, keep_c_files: bool) -> None:
    """Build final .so in `directory`"""

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

    run_function_in_another_directory(directory=directory, function=build_shared_library_)


def build_extensions(
    skip_build_external_libs: bool, static: bool = True, build_dir: Optional[Path] = None
) -> tuple[Path, list[Extension]]:
    """
    Function that creates the build directory if it does not exists and builds the cython extensions.
    Returns a path where the .c file was created and external static libraries were built and a list of cython extensions ready to compile
    """
    build_directory: Path = Path.cwd() if build_dir is None else build_dir
    # The new build directory is {build_directory}/orcsome3_built_libraries
    new_build_directory: Path = build_directory.joinpath(f"{APPNAME}_built_libraries")
    if not skip_build_external_libs:
        rmdir(new_build_directory)
    if not new_build_directory.is_dir():
        print("\nThe build directory does not exist, creating it...\n")
    new_build_directory.mkdir(exist_ok=True, parents=True)
    return new_build_directory, cythonize_cython_extensions(
        build_directory=new_build_directory, static=static, skip_build_external_libs=skip_build_external_libs
    )


def main() -> None:
    """
    Function used to build the shared library (.so) needed for the application.

    It should be used as a module: `python -m orcsome3.libs.cython_libs.setup --build-dir /build/dir`.

    The parameter `--build-dir` defaults to current working directory if not specificed.

    It requires `git`, `cargo`, `cmake`, `autoreconf`, `meson` and `make` commands to be availble on PATH when downloading and building the external libraries statically.
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
        help="Skip downloading and building the external libraries. Defaults to False",
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
    build_directory: Path = args.build_dir
    build_using_dynamic_libraries: bool = args.dynamic
    skip_build_external_libs: bool = args.skip_build_external_libs
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
    build_directory, extensions = build_extensions(
        skip_build_external_libs=skip_build_external_libs,
        static=not build_using_dynamic_libraries,
        build_dir=build_directory,
    )
    build_shared_library(extensions=extensions, directory=build_directory, keep_c_files=keep_c_files)


if __name__ == "__main__":
    main()
