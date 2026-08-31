"""Library source versions and declarative build recipes (used by engine.py)."""

from pathlib import Path
from typing import Any

from orcsome3.libs.build.engine import (
    CargoGitRecipe,
    CMakeGitRecipe,
    MesonGitRecipe,
)
from orcsome3.libs.build.helpers import versioned_folder

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
    "libgd": ("https://github.com/libgd/libgd.git", "gd-2.3.3"),
    "cairo": ("https://gitlab.freedesktop.org/cairo/cairo.git", "1.17.8"),
    "resvg": ("https://github.com/RazrFalcon/resvg.git", "v0.30.0"),
    "libev": ("http://dist.schmorp.de/libev/libev-4.33.tar.gz", "4.33"),
    "imagemagick": ("https://github.com/ImageMagick/ImageMagick.git", "7.1.1-47"),
}


def _keep_static_archives_only(lib_dir: Path) -> None:
    for library_file in lib_dir.iterdir():
        if library_file.is_dir():
            continue
        if not library_file.name.endswith(".a"):
            library_file.unlink()


def _patch_libwebp_tiff_static_linking(source_dir: Path) -> None:
    """Allow libwebp to link statically against libtiff (upstream disables this by default)."""
    file_to_edit: Path = source_dir / "cmake" / "deps.cmake"
    lines: list[str] = file_to_edit.read_text().splitlines(keepends=True)
    for index, line in enumerate(lines):
        if '"TIFF is disabled when statically linking."' in line:
            lines[index + 1] = f"#{lines[index + 1]}"
            break
    _ = file_to_edit.write_text(data="".join(lines))


def _recipe(name: str, **kwargs: Any) -> CMakeGitRecipe:
    url, tag = LIBRARIES_SOURCES_VERSION[name]
    folder: str = kwargs.pop("source_folder", versioned_folder(name=name, version=tag))
    return CMakeGitRecipe(name=name, url=url, tag=tag, source_folder=folder, **kwargs)


CMAKE_GIT_RECIPES: dict[str, CMakeGitRecipe] = {
    "zlib": _recipe(
        name="zlib",
        pkg_config_names=["zlib"],
        pkg_config_subpath=("share", "pkgconfig"),
        artifacts=["libz.a"],
        cmake_flags=["-DBUILD_SHARED_LIBS=OFF"],
        post_install_cleanup=_keep_static_archives_only,
    ),
    "Imath": _recipe(
        name="Imath",
        pkg_config_names=["Imath"],
        include_subdirs=["include", "include/Imath"],
        artifacts=["libImath-3_1.a"],
        cmake_flags=["-DBUILD_SHARED_LIBS=OFF", "-DPYTHON=OFF", "-DBUILD_TESTING=OFF"],
        cmake_dirs=["cmake/Imath"],
    ),
    "openjpeg": _recipe(
        name="openjpeg",
        pkg_config_names=["libopenjp2"],
        include_subdirs=["include", "include/openjpeg-2.5"],
        artifacts=["libopenjp2.a"],
        cmake_flags=[
            "-DBUILD_SHARED_LIBS=OFF",
            "-DBUILD_STATIC_LIBS=ON",
            "-DBUILD_DOC=OFF",
            "-DBUILD_CODEC=OFF",
            "-DBUILD_JPIP=OFF",
            "-DBUILD_VIEWER=OFF",
            "-DBUILD_JAVA=OFF",
        ],
        cmake_dirs=["cmake/openjpeg-2.5"],
    ),
    "liblzma": _recipe(
        name="liblzma",
        include_subdirs=["include", "include/lzma"],
        artifacts=["liblzma.a"],
        cmake_flags=[
            "-DBUILD_SHARED_LIBS=OFF",
            "-DXZ_TOOL_XZDEC=OFF",
            "-DXZ_TOOL_LZMADEC=OFF",
            "-DXZ_TOOL_LZMAINFO=OFF",
            "-DXZ_TOOL_XZ=OFF",
            "-DXZ_TOOL_SYMLINKS_LZMA=OFF",
            "-DXZ_TOOL_SCRIPTS=OFF",
            "-DXZ_DOC=OFF",
        ],
        cmake_dirs=["cmake/liblzma"],
    ),
    "libjpeg": _recipe(
        name="libjpeg",
        lib_subdir="lib64",
        pkg_config_subpath=("lib64", "pkgconfig"),
        artifacts=["libjpeg.a"],
        cmake_flags=[
            "-DENABLE_SHARED=FALSE",
            "-DENABLE_STATIC=TRUE",
            "-DWITH_TURBOJPEG=OFF",
        ],
        cmake_dirs=["cmake/libjpeg-turbo"],
    ),
    "zstd": _recipe(
        name="zstd",
        pkg_config_names=["libzstd"],
        artifacts=["libzstd.a"],
        pre_build_steps=["cd build", "cd cmake"],
        cmake_source=".",
        post_install_cleanup=_keep_static_archives_only,
        cmake_dirs=["cmake/zstd"],
    ),
    "libpng": _recipe(
        name="libpng",
        include_subdirs=["include", "include/libpng16"],
        artifacts=["libpng.a", "libpng16.a"],
        cmake_flags=[
            "-DPNG_SHARED=OFF",
            "-DPNG_STATIC=ON",
            "-DPNG_EXECUTABLES=OFF",
            "-DPNG_TESTS=OFF",
        ],
        cmake_dirs=["libpng", "cmake/PNG"],
    ),
    "openexr": _recipe(
        name="openexr",
        pkg_config_names=["OpenEXR"],
        include_subdirs=["include", "include/OpenEXR"],
        artifacts=[
            "libIex-3_3.a",
            "libIlmThread-3_3.a",
            "libOpenEXR-3_3.a",
            "libOpenEXRCore-3_3.a",
            "libOpenEXRUtil-3_3.a",
        ],
        cmake_flags=["-DBUILD_SHARED_LIBS=OFF", "-DOPENEXR_INSTALL_TOOLS=OFF", "-DBUILD_DOCS=OFF"],
        cmake_dirs=["cmake"],
    ),
    "libwebp": _recipe(
        name="libwebp",
        include_subdirs=["include", "include/webp", "include/webp/sharpyuv"],
        cmake_dirs=["share/WebP/cmake"],
        artifacts=[
            "libwebp.a",
            "libsharpyuv.a",
            "libwebpdecoder.a",
            "libwebpdemux.a",
            "libwebpmux.a",
        ],
        cmake_flags=[
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
        ],
        post_clone_hook=_patch_libwebp_tiff_static_linking,
    ),
    "libtiff": _recipe(
        name="libtiff",
        pkg_config_names=["libtiff-4"],
        cmake_dirs=["cmake/tiff"],
        artifacts=["libtiff.a"],
        cmake_flags=[
            "-DBUILD_SHARED_LIBS=OFF",
            "-Dzlib=ON",
            "-Dzstd=ON",
            "-Djpeg=ON",
            "-Djbig=ON",
            "-Dlzma=ON",
            "-Dlibdeflate=OFF",
            "-Dpixarlog=OFF",
            "-Dlerc=OFF",
            "-Dcxx=OFF",
            "-Dtiff-opengl=OFF",
            "-Dtiff-tools=OFF",
            "-Dtiff-tests=OFF",
            "-Dtiff-contrib=OFF",
            "-Dtiff-docs=OFF",
        ],
    ),
}

MESON_GIT_RECIPES: dict[str, MesonGitRecipe] = {
    "pixman": MesonGitRecipe(
        name="pixman",
        url=LIBRARIES_SOURCES_VERSION["pixman"][0],
        tag=LIBRARIES_SOURCES_VERSION["pixman"][1],
        source_folder=versioned_folder(
            name="pixman", version=LIBRARIES_SOURCES_VERSION["pixman"][1].removeprefix("pixman-")
        ),
        pkg_config_names=["pixman-1"],
        include_subdirs=["include", "include/pixman-1"],
        artifacts=["libpixman-1.a"],
        meson_flags=[
            "--default-library static",
            "-Db_staticpic=true",
            "-Dopenmp=disabled",
            "-Dgtk=disabled",
            "-Dlibpng=disabled",
            "-Dtests=disabled",
        ],
    ),
}

CARGO_GIT_RECIPES: dict[str, CargoGitRecipe] = {
    "resvg": CargoGitRecipe(
        name="resvg",
        url=LIBRARIES_SOURCES_VERSION["resvg"][0],
        tag=LIBRARIES_SOURCES_VERSION["resvg"][1],
        source_folder=versioned_folder(name="resvg", version=LIBRARIES_SOURCES_VERSION["resvg"][1]),
    ),
}

CORE_CMAKE_RECIPES: dict[str, CMakeGitRecipe] = {
    "libgd": CMakeGitRecipe(
        name="libgd",
        url=LIBRARIES_SOURCES_VERSION["libgd"][0],
        tag=LIBRARIES_SOURCES_VERSION["libgd"][1],
        source_folder=versioned_folder(name="libgd", version=LIBRARIES_SOURCES_VERSION["libgd"][1]),
        pkg_config_names=["gdlib"],
        artifacts=["libgd.a"],
        cmake_flags=[
            "-DENABLE_PNG=ON",
            "-DENABLE_CPP=OFF",
            "-DBUILD_SHARED_LIBS=OFF",
            "-DBUILD_STATIC_LIBS=ON",
            "-DBUILD_TEST=OFF",
        ],
    ),
}

CORE_MESON_RECIPES: dict[str, MesonGitRecipe] = {
    "cairo": MesonGitRecipe(
        name="cairo",
        url=LIBRARIES_SOURCES_VERSION["cairo"][0],
        tag=LIBRARIES_SOURCES_VERSION["cairo"][1],
        source_folder=versioned_folder(name="cairo", version=LIBRARIES_SOURCES_VERSION["cairo"][1]),
        pkg_config_names=["cairo"],
        artifacts=["libcairo.a"],
        meson_flags=[
            "--default-library static",
            "-Db_staticpic=true",
            "-Dfontconfig=disabled",
            "-Dfreetype=disabled",
            "-Dpng=enabled",
            "-Dquartz=disabled",
            "-Dxcb=disabled",
            "-Dxlib=disabled",
            "-Dzlib=disabled",
            "-Dtests=disabled",
            "-Dgtk2-utils=disabled",
            "-Dglib=disabled",
            "-Dspectre=disabled",
            "-Dsymbol-lookup=disabled",
            "-Dgtk_doc=false",
        ],
    ),
}
