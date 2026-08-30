"""Orcsome3: Python 3 scripting for NETWM-compliant X11 window managers.

Typical rc.py usage::

    from orcsome3 import get_wm

    wm = get_wm()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from orcsome3.run import get_wm as get_wm

__all__: list[str] = ["get_wm"]


def __getattr__(name: str) -> Any:
    # Importing this package must not load orcsome3_backend; `python -m orcsome3.libs.build` needs that.
    if name == "get_wm":
        from orcsome3.run import get_wm

        return get_wm
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
