from __future__ import annotations

from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _BuildPy
from typing_extensions import override

from orcsome3.libs.build import build_extensions


class build_py(_BuildPy):
    """Copy the top-level Cython stub next to the .so (it is not package data)."""

    @override
    def run(self) -> None:
        super().run()
        stub: Path = Path("orcsome3_backend.pyi")
        if stub.is_file():
            _ = self.copy_file(infile=str(stub), outfile=str(Path(self.build_lib).joinpath(stub.name)))


_, extensions = build_extensions(skip_build_external_libs=True, static=True)
_ = setup(
    ext_modules=extensions,
    cmdclass={"build_py": build_py},
)
