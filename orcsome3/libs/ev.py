"""Thin Python wrappers around libev (loop + IO / signal / timer watchers) via orcsome3_backend."""

from __future__ import annotations

import time
from enum import Enum
from signal import Signals
from typing import Callable, Optional, Union

import orcsome3_backend
from orcsome3.utils import Final


class TYPES(metaclass=Final):
    """Type aliases for Cython objects."""

    Cython_Loop: type = orcsome3_backend.PyLoop
    Cython_IOWatcher: type = orcsome3_backend.PyIOWatcher
    Cython_SignalWatcher: type = orcsome3_backend.PySignalWatcher
    Cython_TimerWatcher: type = orcsome3_backend.PyTimerWatcher
    Cython_StatWatcher: type = orcsome3_backend.PyStatWatcher


class Loop:
    """libev event loop wrapper."""

    cython_loop: Optional[orcsome3_backend.PyLoop] = None

    class NewLoopFlags(int, Enum):
        EVFLAG_AUTO = orcsome3_backend.PYLOOP_NEW_LOOP_FLAGS.EVFLAG_AUTO
        EVFLAG_NOENV = orcsome3_backend.PYLOOP_NEW_LOOP_FLAGS.EVFLAG_NOENV
        EVFLAG_FORKCHECK = orcsome3_backend.PYLOOP_NEW_LOOP_FLAGS.EVFLAG_FORKCHECK
        EVFLAG_NOINOTIFY = orcsome3_backend.PYLOOP_NEW_LOOP_FLAGS.EVFLAG_NOINOTIFY
        EVFLAG_SIGNALFD = orcsome3_backend.PYLOOP_NEW_LOOP_FLAGS.EVFLAG_SIGNALFD
        EVFLAG_NOSIGMASK = orcsome3_backend.PYLOOP_NEW_LOOP_FLAGS.EVFLAG_NOSIGMASK
        EVBACKEND_SELECT = orcsome3_backend.PYLOOP_NEW_LOOP_FLAGS.EVBACKEND_SELECT
        EVBACKEND_POLL = orcsome3_backend.PYLOOP_NEW_LOOP_FLAGS.EVBACKEND_POLL
        EVBACKEND_EPOLL = orcsome3_backend.PYLOOP_NEW_LOOP_FLAGS.EVBACKEND_EPOLL
        EVBACKEND_KQUEUE = orcsome3_backend.PYLOOP_NEW_LOOP_FLAGS.EVBACKEND_KQUEUE
        EVBACKEND_DEVPOLL = orcsome3_backend.PYLOOP_NEW_LOOP_FLAGS.EVBACKEND_DEVPOLL
        EVBACKEND_PORT = orcsome3_backend.PYLOOP_NEW_LOOP_FLAGS.EVBACKEND_PORT
        EVBACKEND_ALL = orcsome3_backend.PYLOOP_NEW_LOOP_FLAGS.EVBACKEND_ALL
        EVBACKEND_MASK = orcsome3_backend.PYLOOP_NEW_LOOP_FLAGS.EVBACKEND_MASK

    class RunFlags(int, Enum):
        EVRUN_ALWAYS = orcsome3_backend.PYLOOP_RUN_LOOP_FLAGS.EVRUN_ALWAYS
        EVRUN_ONCE = orcsome3_backend.PYLOOP_RUN_LOOP_FLAGS.EVRUN_ONCE
        EVRUN_NOWAIT = orcsome3_backend.PYLOOP_RUN_LOOP_FLAGS.EVRUN_NOWAIT

    class BreakFlags(int, Enum):
        EVBREAK_ALL = orcsome3_backend.PYLOOP_BREAK_LOOP_FLAGS.EVBREAK_ALL
        EVBREAK_ONE = orcsome3_backend.PYLOOP_BREAK_LOOP_FLAGS.EVBREAK_ONE
        EVBREAK_CANCEL = orcsome3_backend.PYLOOP_BREAK_LOOP_FLAGS.EVBREAK_CANCEL

    @classmethod
    def new(cls, init_flags: Union[NewLoopFlags, list[NewLoopFlags]] = NewLoopFlags.EVFLAG_AUTO) -> Loop:
        """Allocate a libev loop. Default backend is `EVFLAG_AUTO` (epoll on Linux)."""
        flags: Union[int, list[int]] = (
            [x.value for x in init_flags] if isinstance(init_flags, list) else init_flags.value
        )
        cython_loop: orcsome3_backend.PyLoop = orcsome3_backend.PyLoop._new_from_python_(flags=flags)
        return cls.new_from_cython_loop(cython_loop=cython_loop)

    @classmethod
    def new_from_cython_loop(cls, cython_loop: orcsome3_backend.PyLoop) -> Loop:
        """Wrap an existing Cython loop object (used from watcher callbacks)."""
        loop: Loop = cls()
        loop.cython_loop = cython_loop
        return loop

    def run(self, run_flags: Union[RunFlags, list[RunFlags]] = RunFlags.EVRUN_ALWAYS) -> None:
        """Enter the loop. `EVRUN_ALWAYS` blocks until `break_()`."""
        if self.cython_loop is not None:
            flags: Union[int, list[int]] = (
                [x.value for x in run_flags] if isinstance(run_flags, list) else run_flags.value
            )
            self.cython_loop.run(flags=flags)

    def break_(self, how: BreakFlags) -> None:
        """Stop `run()`. Named `break_` because `break` is a keyword."""
        if self.cython_loop is not None:
            self.cython_loop.break_(how_to_break_flag=how.value)

    def destroy(self) -> None:
        """Free the native loop. Further `run()` / `break_()` calls are no-ops."""
        if self.cython_loop is not None:
            self.cython_loop.destroy()
            self.cython_loop = None


class IOWatcher:
    """File-descriptor watcher."""

    cython_io_watcher: Optional[orcsome3_backend.PyIOWatcher] = None

    class Events(int, Enum):
        EV_READ = orcsome3_backend.PYIOWATCHER_INIT_FLAGS.EV_READ
        EV_WRITE = orcsome3_backend.PYIOWATCHER_INIT_FLAGS.EV_WRITE
        EV_READ_WRITE = orcsome3_backend.PYIOWATCHER_INIT_FLAGS.EV_READ_WRITE

    @classmethod
    def new(cls, callback: Callable[[Loop, IOWatcher, int], None], file_descriptor: int, event: Events) -> IOWatcher:
        """Watch `file_descriptor` for `event` (read/write). `callback(loop, watcher, revents)`."""
        cython_io_watcher: orcsome3_backend.PyIOWatcher = orcsome3_backend.PyIOWatcher._new_from_python_()
        cython_io_watcher.init(
            callbacks={"default": IOWatcher.default_callback, "user_callback": callback},
            file_descriptor=file_descriptor,
            events=event.value,
        )
        return cls.new_from_cython_io_watcher(cython_io_watcher=cython_io_watcher)

    @classmethod
    def new_from_cython_io_watcher(cls, cython_io_watcher: orcsome3_backend.PyIOWatcher) -> IOWatcher:
        """Wrap an existing Cython IO watcher."""
        io_watcher: IOWatcher = cls()
        io_watcher.cython_io_watcher = cython_io_watcher
        return io_watcher

    @staticmethod
    def default_callback(
        native_cython_loop: orcsome3_backend.PyLoop,
        native_cython_io_watcher: orcsome3_backend.PyIOWatcher,
        revents: int,
    ) -> None:
        """Native → Python adapter; invokes the user callback stored on the Cython watcher."""
        py_loop: Loop = Loop.new_from_cython_loop(cython_loop=native_cython_loop)
        py_io_watcher: IOWatcher = IOWatcher.new_from_cython_io_watcher(cython_io_watcher=native_cython_io_watcher)
        watcher: Optional[orcsome3_backend.PyIOWatcher] = py_io_watcher.cython_io_watcher
        if watcher is not None:
            watcher.callbacks["user_callback"](py_loop, py_io_watcher, revents)

    def start(self, loop: Loop) -> None:
        """Start watching on `loop`."""
        if self.cython_io_watcher is not None and loop.cython_loop is not None:
            self.cython_io_watcher.start(loop=loop.cython_loop)

    def stop(self, loop: Loop) -> None:
        """Stop watching on `loop` (watcher can be started again)."""
        if self.cython_io_watcher is not None and loop.cython_loop is not None:
            self.cython_io_watcher.stop(loop=loop.cython_loop)

    def close(self, loop: Loop) -> None:
        """Stop and drop the native watcher."""
        self.stop(loop=loop)
        self.cython_io_watcher = None


class SignalWatcher:
    """Signal watcher."""

    cython_signal_watcher: Optional[orcsome3_backend.PySignalWatcher] = None

    @classmethod
    def new(cls, callback: Callable[[Loop, SignalWatcher, int], None], signal_number: Signals) -> SignalWatcher:
        """Watch POSIX `signal_number`. `callback(loop, watcher, revents)`."""
        cython_signal_watcher: orcsome3_backend.PySignalWatcher = orcsome3_backend.PySignalWatcher._new_from_python_()
        cython_signal_watcher.init(
            callbacks={"default": SignalWatcher.default_callback, "user_callback": callback},
            signal_number=signal_number.value,
        )
        return cls.new_from_cython_signal_watcher(cython_signal_watcher=cython_signal_watcher)

    @classmethod
    def new_from_cython_signal_watcher(cls, cython_signal_watcher: orcsome3_backend.PySignalWatcher) -> SignalWatcher:
        """Wrap an existing Cython signal watcher."""
        signal_watcher: SignalWatcher = cls()
        signal_watcher.cython_signal_watcher = cython_signal_watcher
        return signal_watcher

    @staticmethod
    def default_callback(
        native_cython_loop: orcsome3_backend.PyLoop,
        native_cython_signal_watcher: orcsome3_backend.PySignalWatcher,
        revents: int,
    ) -> None:
        """Native → Python adapter; invokes the user callback stored on the Cython watcher."""
        py_loop: Loop = Loop.new_from_cython_loop(cython_loop=native_cython_loop)
        py_signal_watcher: SignalWatcher = SignalWatcher.new_from_cython_signal_watcher(
            cython_signal_watcher=native_cython_signal_watcher
        )
        watcher: Optional[orcsome3_backend.PySignalWatcher] = py_signal_watcher.cython_signal_watcher
        if watcher is not None:
            watcher.callbacks["user_callback"](py_loop, py_signal_watcher, revents)

    def start(self, loop: Loop) -> None:
        """Start watching on `loop`."""
        if self.cython_signal_watcher is not None and loop.cython_loop is not None:
            self.cython_signal_watcher.start(loop=loop.cython_loop)

    def stop(self, loop: Loop) -> None:
        """Stop watching on `loop`."""
        if self.cython_signal_watcher is not None and loop.cython_loop is not None:
            self.cython_signal_watcher.stop(loop=loop.cython_loop)

    def close(self, loop: Loop) -> None:
        """Stop and drop the native watcher."""
        self.stop(loop=loop)
        self.cython_signal_watcher = None


class TimerWatcher:
    """Timer watcher."""

    cython_timer_watcher: Optional[orcsome3_backend.PyTimerWatcher] = None
    after: float = 0.0
    repeat: float = 0.0
    next_stop: float = 0.0

    @classmethod
    def new(
        cls, callback: Callable[[Loop, TimerWatcher, int], None], after: float = 0.0, repeat: float = 0.0
    ) -> TimerWatcher:
        """Fire `callback` after `after` seconds, then every `repeat` seconds if `repeat` > 0."""
        cython_timer_watcher: orcsome3_backend.PyTimerWatcher = orcsome3_backend.PyTimerWatcher._new_from_python_()
        cython_timer_watcher.init(
            callbacks={"default": TimerWatcher.default_callback, "user_callback": callback},
            after=after,
            repeat=repeat,
        )
        return cls.new_from_cython_timer_watcher(cython_timer_watcher=cython_timer_watcher)

    @classmethod
    def new_from_cython_timer_watcher(cls, cython_timer_watcher: orcsome3_backend.PyTimerWatcher) -> TimerWatcher:
        """Wrap an existing Cython timer watcher."""
        timer_watcher: TimerWatcher = cls()
        timer_watcher.cython_timer_watcher = cython_timer_watcher
        return timer_watcher

    @staticmethod
    def default_callback(
        native_cython_loop: orcsome3_backend.PyLoop,
        native_cython_timer_watcher: orcsome3_backend.PyTimerWatcher,
        revents: int,
    ) -> None:
        """Native → Python adapter; invokes the user callback stored on the Cython watcher."""
        py_loop: Loop = Loop.new_from_cython_loop(cython_loop=native_cython_loop)
        py_timer_watcher: TimerWatcher = TimerWatcher.new_from_cython_timer_watcher(
            cython_timer_watcher=native_cython_timer_watcher
        )
        watcher: Optional[orcsome3_backend.PyTimerWatcher] = py_timer_watcher.cython_timer_watcher
        if watcher is not None:
            watcher.callbacks["user_callback"](py_loop, py_timer_watcher, revents)

    def start(self, loop: Loop, after: float = 0.0, repeat: float = 0.0) -> None:
        """Start the timer. Non-zero `after`/`repeat` retune it before starting."""
        if self.cython_timer_watcher is not None and loop.cython_loop is not None:
            if after or repeat:
                self.after = after or self.after
                self.repeat = repeat or self.repeat
                self.cython_timer_watcher.set_timer(after=self.after, repeat=self.repeat)
            self.next_stop = time.time() + self.after
            self.cython_timer_watcher.start(loop=loop.cython_loop)

    def stop(self, loop: Loop) -> None:
        """Stop the timer without destroying it."""
        if self.cython_timer_watcher is not None and loop.cython_loop is not None:
            self.cython_timer_watcher.stop(loop=loop.cython_loop)

    def close(self, loop: Loop) -> None:
        """Stop and drop the native watcher."""
        self.stop(loop=loop)
        self.cython_timer_watcher = None

    def again(self, loop: Loop) -> None:
        """Restart the repeating timer from now (`ev_timer_again`)."""
        if self.cython_timer_watcher is not None and loop.cython_loop is not None:
            self.next_stop = time.time() + self.repeat
            self.cython_timer_watcher.again(loop=loop.cython_loop)

    def remaining(self, loop: Loop) -> float:
        """Seconds until the next fire, or 0 if the native watcher is gone."""
        if self.cython_timer_watcher is not None and loop.cython_loop is not None:
            return float(self.cython_timer_watcher.remaining(loop=loop.cython_loop))
        return 0.0

    def update_next_stop(self) -> None:
        """Set `next_stop` to now + `repeat` (used after a timer callback that keeps running)."""
        self.next_stop = time.time() + self.repeat

    def overdue(self, timeout: float) -> bool:
        """True if the scheduled `next_stop` was more than `timeout` seconds ago."""
        return time.time() > self.next_stop + timeout


class StatWatcher:
    """Path watcher (`ev_stat`: inotify on Linux, with a periodic `stat` fallback)."""

    cython_stat_watcher: Optional[orcsome3_backend.PyStatWatcher] = None

    @classmethod
    def new(cls, callback: Callable[[Loop, StatWatcher, int], None], path: str, interval: float = 0.0) -> StatWatcher:
        """Watch `path`. `interval` 0 lets libev pick the fallback poll (~5s). `callback(loop, watcher, revents)`."""
        cython_stat_watcher: orcsome3_backend.PyStatWatcher = orcsome3_backend.PyStatWatcher._new_from_python_()
        cython_stat_watcher.init(
            callbacks={"default": StatWatcher.default_callback, "user_callback": callback},
            path=path,
            interval=interval,
        )
        return cls.new_from_cython_stat_watcher(cython_stat_watcher=cython_stat_watcher)

    @classmethod
    def new_from_cython_stat_watcher(cls, cython_stat_watcher: orcsome3_backend.PyStatWatcher) -> StatWatcher:
        """Wrap an existing Cython stat watcher."""
        stat_watcher: StatWatcher = cls()
        stat_watcher.cython_stat_watcher = cython_stat_watcher
        return stat_watcher

    @staticmethod
    def default_callback(
        native_cython_loop: orcsome3_backend.PyLoop,
        native_cython_stat_watcher: orcsome3_backend.PyStatWatcher,
        revents: int,
    ) -> None:
        """Native → Python adapter; invokes the user callback stored on the Cython watcher."""
        py_loop: Loop = Loop.new_from_cython_loop(cython_loop=native_cython_loop)
        py_stat_watcher: StatWatcher = StatWatcher.new_from_cython_stat_watcher(
            cython_stat_watcher=native_cython_stat_watcher
        )
        watcher: Optional[orcsome3_backend.PyStatWatcher] = py_stat_watcher.cython_stat_watcher
        if watcher is not None:
            watcher.callbacks["user_callback"](py_loop, py_stat_watcher, revents)

    def start(self, loop: Loop) -> None:
        """Start watching on `loop`."""
        if self.cython_stat_watcher is not None and loop.cython_loop is not None:
            self.cython_stat_watcher.start(loop=loop.cython_loop)

    def stop(self, loop: Loop) -> None:
        """Stop watching on `loop`."""
        if self.cython_stat_watcher is not None and loop.cython_loop is not None:
            self.cython_stat_watcher.stop(loop=loop.cython_loop)

    def close(self, loop: Loop) -> None:
        """Stop and drop the native watcher."""
        self.stop(loop=loop)
        self.cython_stat_watcher = None
