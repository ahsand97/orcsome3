from __future__ import annotations

import sys
from pathlib import Path

from setuptools import setup

# python -m build (PEP 517) execs this in an isolated subprocess whose sys.path doesn't
# include the source tree, so the local `orcsome3` package isn't importable without this.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orcsome3.libs.build import build_extensions  # noqa: E402

_build_dir, extensions = build_extensions(skip_build_external_libs=True, static=True)
_ = setup(ext_modules=extensions)
