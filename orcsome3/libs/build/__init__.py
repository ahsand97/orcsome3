"""Native library build system for orcsome3."""

from __future__ import annotations

from pathlib import Path

from setuptools.command.build_py import build_py as _BuildPy
from typing_extensions import override

from orcsome3.libs.build.libraries import (
    build_extensions,
    build_shared_library,
    cythonize_cython_extensions,
    install_backend_for_local_dev,
    main,
)

__all__: list[str] = [
    "BuildPy",
    "build_extensions",
    "build_shared_library",
    "cythonize_cython_extensions",
    "install_backend_for_local_dev",
    "main",
]


class BuildPy(_BuildPy):
    """Copy the top-level Cython stub next to the .so (it is not package data)."""

    @override
    def run(self) -> None:
        super().run()
        stub: Path = Path("orcsome3_backend.pyi")
        if stub.is_file():
            _ = self.copy_file(infile=str(stub), outfile=str(Path(self.build_lib).joinpath(stub.name)))
