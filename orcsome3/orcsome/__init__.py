from typing import Optional, cast

from .wm import WM, ImmediateWM

VERSION = "0.1"

_wm: Optional[WM] = None


def get_wm() -> WM:
    return cast(WM, _wm)


def get_wm_immediate() -> ImmediateWM:
    return ImmediateWM()


def update_wm(new_wm: WM) -> None:
    global _wm
    _wm = new_wm
