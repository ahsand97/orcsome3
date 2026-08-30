from __future__ import annotations

from setuptools import setup

from orcsome3.libs.build import build_extensions

_build_dir, extensions = build_extensions(skip_build_external_libs=True, static=True)
_ = setup(ext_modules=extensions)
