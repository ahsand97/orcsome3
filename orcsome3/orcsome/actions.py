from typing import Optional

from . import wm, wrappers


class Actions(wm.Actions):
    def __init__(self, window_manager: wm.WM) -> None:
        self._wm: wm.WM = window_manager

    def _focus(self, window: wrappers.Window, direction: int) -> None:
        clients = self._wm.find_clients(clients=self._wm.get_clients(), desktop=window.desktop)
        idx = clients.index(window)
        newc = clients[(idx + direction) % len(clients)]
        self._wm.focus_and_raise(window=newc)

    def focus_next(self, window: Optional[wrappers.Window] = None) -> None:
        window_: Optional[wrappers.Window] = window
        if window is None:
            window_ = self._wm.current_window
        if window_ is not None:
            self._focus(window=window_, direction=1)

    def focus_prev(self, window: Optional[wrappers.Window] = None) -> None:
        window_: Optional[wrappers.Window] = window
        if window is None:
            window_ = self._wm.current_window
        if window_ is not None:
            self._focus(window=window_, direction=-1)

    def restart(self) -> None:
        raise wm.RestartException()

    def activate_window_desktop(self, window: wrappers.Window) -> Optional[bool]:
        wd = window.desktop
        if wd is not None:
            if self._wm.current_desktop != wd:
                self._wm.activate_desktop(num=wd)
                return True
            else:
                return False
        else:
            return None
