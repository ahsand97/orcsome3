from __future__ import annotations

import time
from enum import Enum
from signal import Signals
from typing import Callable, Optional, Union

# Try to import shared library orcsome3_backend.cpython-xxx-x86_64-linux-gnu.so, it looks for standard locations at sys.path,
# to specify another location use env var PYTHONPATH (PYTHONPATH="/custom/dir:$PYTHONPATH")
import orcsome3_backend  # pyright: ignore[reportMissingImports]

from orcsome3.utils import CythonClass, CythonWrapper, Final

# Globals
_cython_wrapper: CythonWrapper = CythonWrapper(cython_module=orcsome3_backend)  # Global Cython Wrapper instance


class TYPES(metaclass=Final):
    """Class wrappers for Cython objects"""

    class Cython_Loop(CythonClass):
        cython_class: object = _cython_wrapper.get(name="PyLoop")

        def __init__(self, cython_instance: object) -> None:
            super().__init__(cython_class_instance=cython_instance)

    class Cython_IOWatcher(CythonClass):
        cython_class: object = _cython_wrapper.get(name="PyIOWatcher")

        def __init__(self, cython_instance: object) -> None:
            super().__init__(cython_class_instance=cython_instance)

    class Cython_SignalWatcher(CythonClass):
        cython_class: object = _cython_wrapper.get(name="PySignalWatcher")

        def __init__(self, cython_instance: object) -> None:
            super().__init__(cython_class_instance=cython_instance)

    class Cython_TimerWatcher(CythonClass):
        cython_class: object = _cython_wrapper.get(name="PyTimerWatcher")

        def __init__(self, cython_instance: object) -> None:
            super().__init__(cython_class_instance=cython_instance)


class Loop:
    """
    Class Loop, use method `new` to instantiate it and method `new_from_cython_loop` to instantiate it from a `TYPES.Cython_Loop` object.
    """

    cython_loop: Optional[TYPES.Cython_Loop] = None

    class NewLoopFlags(int, Enum):
        EVFLAG_AUTO = int(_cython_wrapper.get(name="PYLOOP_NEW_LOOP_FLAGS").EVFLAG_AUTO.value)
        EVFLAG_NOENV = int(_cython_wrapper.get(name="PYLOOP_NEW_LOOP_FLAGS").EVFLAG_NOENV.value)
        EVFLAG_FORKCHECK = int(_cython_wrapper.get(name="PYLOOP_NEW_LOOP_FLAGS").EVFLAG_FORKCHECK.value)
        EVFLAG_NOINOTIFY = int(_cython_wrapper.get(name="PYLOOP_NEW_LOOP_FLAGS").EVFLAG_NOINOTIFY.value)
        EVFLAG_SIGNALFD = int(_cython_wrapper.get(name="PYLOOP_NEW_LOOP_FLAGS").EVFLAG_SIGNALFD.value)
        EVFLAG_NOSIGMASK = int(_cython_wrapper.get(name="PYLOOP_NEW_LOOP_FLAGS").EVFLAG_NOSIGMASK.value)
        EVBACKEND_SELECT = int(_cython_wrapper.get(name="PYLOOP_NEW_LOOP_FLAGS").EVBACKEND_SELECT.value)
        EVBACKEND_POLL = int(_cython_wrapper.get(name="PYLOOP_NEW_LOOP_FLAGS").EVBACKEND_POLL.value)
        EVBACKEND_EPOLL = int(_cython_wrapper.get(name="PYLOOP_NEW_LOOP_FLAGS").EVBACKEND_EPOLL.value)
        EVBACKEND_KQUEUE = int(_cython_wrapper.get(name="PYLOOP_NEW_LOOP_FLAGS").EVBACKEND_KQUEUE.value)
        EVBACKEND_DEVPOLL = int(_cython_wrapper.get(name="PYLOOP_NEW_LOOP_FLAGS").EVBACKEND_DEVPOLL.value)
        EVBACKEND_PORT = int(_cython_wrapper.get(name="PYLOOP_NEW_LOOP_FLAGS").EVBACKEND_PORT.value)
        EVBACKEND_ALL = int(_cython_wrapper.get(name="PYLOOP_NEW_LOOP_FLAGS").EVBACKEND_ALL.value)
        EVBACKEND_MASK = int(_cython_wrapper.get(name="PYLOOP_NEW_LOOP_FLAGS").EVBACKEND_MASK.value)

    class RunFlags(int, Enum):
        EVRUN_ALWAYS = int(_cython_wrapper.get(name="PYLOOP_RUN_LOOP_FLAGS").EVRUN_ALWAYS.value)
        EVRUN_ONCE = int(_cython_wrapper.get(name="PYLOOP_RUN_LOOP_FLAGS").EVRUN_ONCE.value)
        EVRUN_NOWAIT = int(_cython_wrapper.get(name="PYLOOP_RUN_LOOP_FLAGS").EVRUN_NOWAIT.value)

    class BreakFlags(int, Enum):
        EVBREAK_ALL = int(_cython_wrapper.get(name="PYLOOP_BREAK_LOOP_FLAGS").EVBREAK_ALL.value)
        EVBREAK_ONE = int(_cython_wrapper.get(name="PYLOOP_BREAK_LOOP_FLAGS").EVBREAK_ONE.value)
        EVBREAK_CANCEL = int(_cython_wrapper.get(name="PYLOOP_BREAK_LOOP_FLAGS").EVBREAK_CANCEL.value)

    @classmethod
    def new(cls, init_flags: Union[NewLoopFlags, list[NewLoopFlags]] = NewLoopFlags.EVBACKEND_SELECT) -> Loop:
        cython_loop: TYPES.Cython_Loop = TYPES.Cython_Loop(
            cython_instance=getattr(TYPES.Cython_Loop.cython_class, "_new_from_python_")(
                [x.value for x in init_flags] if isinstance(init_flags, list) else init_flags.value
            )
        )
        return cls.new_from_cython_loop(cython_loop=cython_loop)

    @classmethod
    def new_from_cython_loop(cls, cython_loop: TYPES.Cython_Loop) -> Loop:
        loop: Loop = cls()
        loop.cython_loop = cython_loop
        return loop

    def run(self, run_flags: Union[RunFlags, list[RunFlags]] = RunFlags.EVRUN_ALWAYS) -> None:
        if self.cython_loop is not None:
            self.cython_loop.call_function(
                name="run", params=[[x.value for x in run_flags] if isinstance(run_flags, list) else run_flags.value]
            )

    def break_(self, how: BreakFlags) -> None:
        if self.cython_loop is not None:
            self.cython_loop.call_function(name="break_", params=[how.value])

    def destroy(self) -> None:
        if self.cython_loop is not None:
            self.cython_loop.call_function(name="destroy")


class IOWatcher:
    """
    Class IOWatcher, use method `new` to instantiate it and method `new_from_cython_io_watcher` to instantiate it from a `TYPES.Cython_IO_Watcher` object.
    """

    cython_io_watcher: Optional[TYPES.Cython_IOWatcher] = None

    class Events(int, Enum):
        EV_READ = int(_cython_wrapper.get(name="PYIOWATCHER_INIT_FLAGS").EV_READ.value)
        EV_WRITE = int(_cython_wrapper.get(name="PYIOWATCHER_INIT_FLAGS").EV_WRITE.value)
        EV_READ_WRITE = int(_cython_wrapper.get(name="PYIOWATCHER_INIT_FLAGS").EV_READ_WRITE.value)

    @classmethod
    def new(cls, callback: Callable[[Loop, IOWatcher, int], None], file_descriptor: int, event: Events) -> IOWatcher:
        cython_io_watcher: TYPES.Cython_IOWatcher = TYPES.Cython_IOWatcher(
            cython_instance=getattr(TYPES.Cython_IOWatcher.cython_class, "_new_from_python_")()
        )
        cython_io_watcher.call_function(
            name="init",
            params=[{"default": IOWatcher.default_callback, "user_callback": callback}, file_descriptor, event.value],
        )
        return cls.new_from_cython_io_watcher(cython_io_watcher=cython_io_watcher)

    @classmethod
    def new_from_cython_io_watcher(cls, cython_io_watcher: TYPES.Cython_IOWatcher) -> IOWatcher:
        io_watcher: IOWatcher = cls()
        io_watcher.cython_io_watcher = cython_io_watcher
        return io_watcher

    @staticmethod
    def default_callback(native_cython_loop: object, native_cython_io_watcher: object, revents: int) -> None:
        cython_loop: TYPES.Cython_Loop = TYPES.Cython_Loop(cython_instance=native_cython_loop)
        cython_io_watcher: TYPES.Cython_IOWatcher = TYPES.Cython_IOWatcher(cython_instance=native_cython_io_watcher)
        py_loop: Loop = Loop.new_from_cython_loop(cython_loop=cython_loop)
        py_io_watcher: IOWatcher = IOWatcher.new_from_cython_io_watcher(cython_io_watcher=cython_io_watcher)
        if py_io_watcher.cython_io_watcher is not None:
            py_io_watcher.cython_io_watcher.get_attribute(attr_name="callbacks")["user_callback"](
                py_loop, py_io_watcher, revents
            )

    def start(self, loop: Loop) -> None:
        if self.cython_io_watcher is not None and loop.cython_loop is not None:
            self.cython_io_watcher.call_function(name="start", params=[loop.cython_loop.cython_instance])

    def stop(self, loop: Loop) -> None:
        if self.cython_io_watcher is not None and loop.cython_loop is not None:
            self.cython_io_watcher.call_function(name="stop", params=[loop.cython_loop.cython_instance])


class SignalWatcher:
    """
    Class SignalWatcher, use method `new` to instantiate it and method
    `new_from_cython_signal_watcher` to instantiate it from a `TYPES.Cython_Signal_Watcher` object.
    """

    cython_signal_watcher: Optional[TYPES.Cython_SignalWatcher] = None

    @classmethod
    def new(cls, callback: Callable[[Loop, SignalWatcher, int], None], signal_number: Signals) -> SignalWatcher:
        cython_signal_watcher: TYPES.Cython_SignalWatcher = TYPES.Cython_SignalWatcher(
            cython_instance=getattr(TYPES.Cython_SignalWatcher.cython_class, "_new_from_python_")()
        )
        cython_signal_watcher.call_function(
            name="init",
            params=[{"default": SignalWatcher.default_callback, "user_callback": callback}, signal_number.value],
        )
        return cls.new_from_cython_signal_watcher(cython_signal_watcher=cython_signal_watcher)

    @classmethod
    def new_from_cython_signal_watcher(cls, cython_signal_watcher: TYPES.Cython_SignalWatcher) -> SignalWatcher:
        signal_watcher: SignalWatcher = cls()
        signal_watcher.cython_signal_watcher = cython_signal_watcher
        return signal_watcher

    @staticmethod
    def default_callback(native_cython_loop: object, native_cython_signal_watcher: object, revents: int) -> None:
        cython_loop: TYPES.Cython_Loop = TYPES.Cython_Loop(cython_instance=native_cython_loop)
        cython_signal_watcher: TYPES.Cython_SignalWatcher = TYPES.Cython_SignalWatcher(
            cython_instance=native_cython_signal_watcher
        )
        py_loop: Loop = Loop.new_from_cython_loop(cython_loop=cython_loop)
        py_signal_watcher: SignalWatcher = SignalWatcher.new_from_cython_signal_watcher(
            cython_signal_watcher=cython_signal_watcher
        )
        if py_signal_watcher.cython_signal_watcher is not None:
            py_signal_watcher.cython_signal_watcher.get_attribute(attr_name="callbacks")["user_callback"](
                py_loop, py_signal_watcher, revents
            )

    def start(self, loop: Loop) -> None:
        if self.cython_signal_watcher is not None and loop.cython_loop is not None:
            self.cython_signal_watcher.call_function(name="start", params=[loop.cython_loop.cython_instance])

    def stop(self, loop: Loop) -> None:
        if self.cython_signal_watcher is not None and loop.cython_loop is not None:
            self.cython_signal_watcher.call_function(name="stop", params=[loop.cython_loop.cython_instance])


class TimerWatcher:
    """
    Class TimerWatcher, use method `new` to instantiate it and method
    `new_from_cython_timer_watcher` to instantiate it from a `TYPES.Cython_TimerWatcher` object.
    """

    cython_timer_watcher: Optional[TYPES.Cython_TimerWatcher] = None
    after: float = 0.0
    repeat: float = 0.0
    next_stop: float = 0.0

    @classmethod
    def new(
        cls, callback: Callable[[Loop, TimerWatcher, int], None], after: float = 0.0, repeat: float = 0.0
    ) -> TimerWatcher:
        cython_timer_watcher: TYPES.Cython_TimerWatcher = TYPES.Cython_TimerWatcher(
            cython_instance=getattr(TYPES.Cython_TimerWatcher.cython_class, "_new_from_python_")()
        )
        cython_timer_watcher.call_function(
            name="init", params=[{"default": TimerWatcher.default_callback, "user_callback": callback}, after, repeat]
        )
        return cls.new_from_cython_timer_watcher(cython_timer_watcher=cython_timer_watcher)

    @classmethod
    def new_from_cython_timer_watcher(cls, cython_timer_watcher: TYPES.Cython_TimerWatcher) -> TimerWatcher:
        timer_watcher: TimerWatcher = cls()
        timer_watcher.cython_timer_watcher = cython_timer_watcher
        return timer_watcher

    @staticmethod
    def default_callback(native_cython_loop: object, native_cython_timer_watcher: object, revents: int) -> None:
        cython_loop: TYPES.Cython_Loop = TYPES.Cython_Loop(cython_instance=native_cython_loop)
        cython_timer_watcher: TYPES.Cython_TimerWatcher = TYPES.Cython_TimerWatcher(
            cython_instance=native_cython_timer_watcher
        )
        py_loop: Loop = Loop.new_from_cython_loop(cython_loop=cython_loop)
        py_timer_watcher: TimerWatcher = TimerWatcher.new_from_cython_timer_watcher(
            cython_timer_watcher=cython_timer_watcher
        )
        if py_timer_watcher.cython_timer_watcher is not None:
            py_timer_watcher.cython_timer_watcher.get_attribute(attr_name="callbacks")["user_callback"](
                py_loop, py_timer_watcher, revents
            )

    def start(self, loop: Loop, after: float = 0.0, repeat: float = 0.0) -> None:
        if self.cython_timer_watcher is not None and loop.cython_loop is not None:
            if after or repeat:
                self.after = after or self.after
                self.repeat = repeat or self.repeat
                self.cython_timer_watcher.call_function(name="set_timer", params=[self.after, self.repeat])
            self.next_stop = time.time() + self.after
            self.cython_timer_watcher.call_function(name="start", params=[loop.cython_loop.cython_instance])

    def stop(self, loop: Loop) -> None:
        if self.cython_timer_watcher is not None and loop.cython_loop is not None:
            self.cython_timer_watcher.call_function(name="stop", params=[loop.cython_loop.cython_instance])

    def again(self, loop: Loop) -> None:
        if self.cython_timer_watcher is not None and loop.cython_loop is not None:
            self.next_stop = time.time() + self.repeat
            self.cython_timer_watcher.call_function(name="again", params=[loop.cython_loop.cython_instance])

    def remaining(self, loop: Loop) -> float:
        if self.cython_timer_watcher is not None and loop.cython_loop is not None:
            return float(
                self.cython_timer_watcher.call_function(name="remaining", params=[loop.cython_loop.cython_instance])
            )
        return 0.0

    def update_next_stop(self) -> None:
        self.next_stop = time.time() + self.repeat

    def overdue(self, timeout: float) -> bool:
        return time.time() > self.next_stop + timeout


"""# Test code
def test_callback(loop: Loop, io_watcher: IOWatcher, revents: int) -> None:
    print("Test callback called")
    print(loop, io_watcher, revents)
    io_watcher.stop(loop=loop)
    loop.break_(how=Loop.BreakFlags.EVBREAK_ALL)
    loop.destroy()


def test_callback_signal(loop: Loop, signal_watcher: SignalWatcher, revents: int) -> None:
    print("Test callback signal called")
    print(loop, signal_watcher, revents)
    if display is not None:
        xlib.x_close_display(display=display)
    signal_watcher.stop(loop=loop)
    loop.break_(how=Loop.BreakFlags.EVBREAK_ALL)
    loop.destroy()


def test_callback_xevent(__loop__: Loop, __xevent_watcher__: IOWatcher, __revents__: int) -> None:
    pending_events: int = xlib.x_pending(display=display)
    print("PENDING EVENTS: ", pending_events)
    event: xlib.XEvent = xlib.x_next_event(display=display)
    print(event.get_specific_event())
    print("")


display: xlib.TYPES.Cython_Display | None = None


def main() -> None:
    global display
    loop: Loop = Loop.new(init_flags=Loop.NewLoopFlags.EVBACKEND_SELECT)
    # Signal watcher to stop event loop when a SIGINT arrives
    signal_watcher: SignalWatcher = SignalWatcher.new(callback=test_callback_signal, signal_number=Signals.SIGINT)
    signal_watcher.start(loop=loop)
    display = xlib.x_open_display()
    # Event watcher
    xevent_watcher: IOWatcher = IOWatcher.new(
        callback=test_callback_xevent,
        file_descriptor=xlib.get_connection_number(display=display),
        event=IOWatcher.Events.EV_READ,
    )
    xevent_watcher.start(loop=loop)

    xlib.x_select_input(
        display=display,
        window=xlib.get_default_root_window(display=display),
        event_mask=xlib.INPUT_EVENT_MASKS.SubstructureNotifyMask,
    )
    xlib.x_sync(display=display, discard=False)

    def default_error_handler(
        __display__: xlib.TYPES.Cython_Display, error: xlib.TYPES.EVENTS.Cython_XErrorEvent
    ) -> None:
        err: xlib.XErrorEvent = xlib.XErrorEvent(error_event=error)
        msg_resource: str = f"{'0x%0.2X' % int(err.resourceid)}:{int(err.resourceid)}"
        print(f"{err.msg} ({msg_resource})")

    xlib.x_set_error_handler(handler=default_error_handler)
    loop.run(run_flags=Loop.RunFlags.EVRUN_ALWAYS)


if __name__ == "__main__":
    main()"""
