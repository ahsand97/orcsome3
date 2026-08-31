from __future__ import annotations

"""Locations of the Cython backend sources (`orcsome3/libs/cython_libs`)."""

from pathlib import Path

# orcsome3/libs/build/paths.py -> orcsome3/libs/cython_libs
CYTHON_LIBS_DIR: Path = Path(__file__).resolve().parent.parent / "cython_libs"
CYTHON_BACKEND_PYX: Path = CYTHON_LIBS_DIR / "orcsome3_backend.pyx"
