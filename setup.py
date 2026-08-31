from __future__ import annotations

import sys
from pathlib import Path

from setuptools import setup

# python -m build (PEP 517) execs this in an isolated subprocess whose sys.path doesn't
# include the source tree, so the local `orcsome3` package isn't importable without this.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orcsome3.libs.build import build_extensions  # noqa: E402

_build_dir, extensions = build_extensions(skip_build_external_libs=True, static=True)
# setuptools rejects absolute paths in Extension.sources for a source distribution; build_extensions()
# returns them absolute since the direct `make native` path needs that (it chdirs before building).
_cwd: Path = Path.cwd()
for _extension in extensions:
    _extension.sources = [str(Path(_source).resolve().relative_to(_cwd)) for _source in _extension.sources]

_ = setup(ext_modules=extensions)
