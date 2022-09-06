import time
from typing import Any, Callable, Optional

try:
    from ._ev import ffi, lib  # type: ignore
except ModuleNotFoundError:
    from . import ev_build

    ev_build.main()
finally:
    from ._ev import ffi, lib  # type: ignore


class Loop(object):
    def __init__(self) -> None:
        self._loop = lib.ev_loop_new(lib.EVBACKEND_SELECT)

    def destroy(self) -> None:
        lib.ev_loop_destroy(self._loop)

    def run(self, flags: int = 0) -> None:
        lib.ev_run(self._loop, flags)

    def break_(self, flags: int = lib.EVBREAK_ALL) -> None:
        lib.ev_break(self._loop, flags)


class IOWatcher(object):
    def __init__(self, callback: Callable[..., Any], file_descriptor: int, flags: int) -> None:
        self._watcher = ffi.new("ev_io*")
        self._callback = ffi.callback("io_cb", callback)
        lib.ev_io_init(self._watcher, self._callback, file_descriptor, flags)

    def start(self, loop: Loop) -> None:
        lib.ev_io_start(loop._loop, self._watcher)

    def stop(self, loop: Loop) -> None:
        lib.ev_io_stop(loop._loop, self._watcher)


class SignalWatcher(object):
    def __init__(self, callback: Callable[..., Any], signum: int) -> None:
        self._watcher = ffi.new("ev_signal*")
        self._callback = ffi.callback("signal_cb", callback)
        lib.ev_signal_init(self._watcher, self._callback, signum)

    def start(self, loop: Loop) -> None:
        lib.ev_signal_start(loop._loop, self._watcher)

    def stop(self, loop: Loop) -> None:
        lib.ev_signal_stop(loop._loop, self._watcher)


class TimerWatcher(object):
    def __init__(self, callback: Callable[..., Any], after: float, repeat: float = 0.0) -> None:
        self._after: float = after
        self._repeat: float = repeat
        self._watcher = ffi.new("ev_timer*")
        self._cb = ffi.callback("timer_cb", callback)
        self.next_stop: float = 0
        lib.ev_timer_init(self._watcher, self._cb, after, repeat)

    def start(self, loop: Loop, after: Optional[float] = None, repeat: Optional[float] = None) -> None:
        if after or repeat:
            self._after = after or self._after
            self._repeat = repeat or self._repeat
            lib.ev_timer_set(self._watcher, self._after, self._repeat)

        self.next_stop = time.time() + self._after
        lib.ev_timer_start(loop._loop, self._watcher)

    def stop(self, loop: Loop) -> None:
        lib.ev_timer_stop(loop._loop, self._watcher)

    def again(self, loop: Loop) -> None:
        self.next_stop = time.time() + self._repeat
        lib.ev_timer_again(loop._loop, self._watcher)

    def remaining(self, loop: Loop) -> float:
        return float(lib.ev_timer_remaining(loop._loop, self._watcher))

    def update_next_stop(self) -> None:
        self.next_stop = time.time() + self._repeat

    def overdue(self, timeout: float) -> bool:
        return time.time() > self.next_stop + timeout
