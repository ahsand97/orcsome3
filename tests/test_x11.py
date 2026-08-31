"""X11 tests: Cython event round-trip and WindowManager decorator dispatch.

Skipped when `XOpenDisplay` fails (no `$DISPLAY` / no X server). Does not call `init()`,
so it does not grab keys or select on the root of a running session.

Grab *delivery* prefers a nested Xephyr/Xvfb server. On a live session it uses a throwaway
window and an obscure key (F24…F21), and skips button grabs so the pointer is not warped.
"""

from __future__ import annotations

import os
import select
import shutil
import subprocess
import unittest
from typing import Callable, Optional, cast

from typing_extensions import TypeAlias

import orcsome3.libs.xlib as xlib
from orcsome3.keys import KeyboardModifiers, KeyDefinition
from orcsome3.window_manager import Window, WindowManager

_Popen: TypeAlias = subprocess.Popen[bytes]
_nested_server: Optional[_Popen] = None


def _try_spawn_displayfd(argv: list[str]) -> Optional[tuple[_Popen, str]]:
    if shutil.which(cmd=argv[0]) is None:
        return None
    read_fd: int
    write_fd: int
    read_fd, write_fd = os.pipe()
    os.set_inheritable(write_fd, True)
    proc: Optional[_Popen] = None
    try:
        proc = subprocess.Popen(
            args=[argv[0], "-displayfd", str(write_fd), *argv[1:]],
            pass_fds=(write_fd,),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        os.close(fd=read_fd)
        os.close(fd=write_fd)
        return None
    os.close(fd=write_fd)
    ready: list[int]
    ready, _, _ = select.select([read_fd], [], [], 5.0)
    if not ready:
        proc.kill()
        _ = proc.wait(timeout=2)
        os.close(fd=read_fd)
        return None
    raw: bytes = os.read(read_fd, 64)
    os.close(fd=read_fd)
    line: str = raw.decode().strip()
    if not line.isdigit():
        proc.kill()
        _ = proc.wait(timeout=2)
        return None
    return proc, f":{line}"


def _spawn_nested_x() -> Optional[tuple[_Popen, str]]:
    candidates: list[list[str]] = []
    if os.getenv(key="DISPLAY") and shutil.which(cmd="Xephyr"):
        candidates.append(["Xephyr", "-screen", "200x200", "-ac"])
    if shutil.which(cmd="Xvfb"):
        candidates.append(["Xvfb", "-screen", "0", "200x200x24"])
    for argv in candidates:
        spawned: Optional[tuple[_Popen, str]] = _try_spawn_displayfd(argv=argv)
        if spawned is not None:
            return spawned
    return None


def _stop_nested_x() -> None:
    global _nested_server
    if _nested_server is None:
        return
    _nested_server.terminate()
    try:
        _ = _nested_server.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _nested_server.kill()
        _ = _nested_server.wait(timeout=2)
    _nested_server = None


def _obscure_keycode(display: xlib.TYPES.Cython_Display, *, nested: bool) -> Optional[int]:
    names: tuple[str, ...] = ("a", "F1") if nested else ("F24", "F23", "F22", "F21")
    for name in names:
        keysym: xlib.TYPES.Cython_KeySym = xlib.x_string_to_keysym(string=name)
        keycode: xlib.TYPES.Cython_KeyCode = xlib.x_keysym_to_keycode(display=display, keysym=keysym)
        if keycode:
            return int(keycode)
    return None


def _drain_x_events(wm: WindowManager) -> None:
    while xlib.x_pending(display=wm.display) > 0:
        event: xlib.XEvent = xlib.x_next_event(display=wm.display)
        handler: Optional[Callable[[xlib.XEvent], None]] = wm._event_handlers.get(event.type)
        if handler is not None:
            handler(event)


def _swallow_x_errors(__display__: xlib.TYPES.Cython_Display, __error__: xlib.TYPES.EVENTS.Cython_XErrorEvent) -> None:
    return


def _try_open_display() -> Optional[xlib.TYPES.Cython_Display]:
    try:
        return xlib.x_open_display()
    except Exception:
        return None


class TestEventRoundTrip(unittest.TestCase):
    display: xlib.TYPES.Cython_Display

    @classmethod
    def setUpClass(cls) -> None:
        opened: Optional[xlib.TYPES.Cython_Display] = _try_open_display()
        if opened is None:
            raise unittest.SkipTest("no X display")
        cls.display = opened

    @classmethod
    def tearDownClass(cls) -> None:
        xlib.x_close_display(display=cls.display)

    def test_configure_round_trip(self) -> None:
        original: xlib.XConfigureEvent = xlib.XConfigureEvent(
            display=self.display,
            event=1,
            window=2,
            x=10,
            y=20,
            width=300,
            height=400,
            border_width=1,
            above=99,
            override_redirect=False,
        )
        self.assertIsNotNone(original._cython_event)
        wrapped: xlib.XConfigureEvent = xlib.XConfigureEvent._new_from_cython_event_(
            configure_event=cast(xlib.TYPES.EVENTS.Cython_XConfigureEvent, original._cython_event),
        )
        self.assertEqual(wrapped.window, 2)
        self.assertEqual(wrapped.event, 1)
        self.assertEqual(wrapped.x, 10)
        self.assertEqual(wrapped.y, 20)
        self.assertEqual(wrapped.width, 300)
        self.assertEqual(wrapped.height, 400)
        self.assertEqual(wrapped.above, 99)

    def test_map_unmap_round_trip(self) -> None:
        mapped: xlib.XMapEvent = xlib.XMapEvent(display=self.display, event=5, window=6, override_redirect=True)
        self.assertIsNotNone(mapped._cython_event)
        wrapped_map: xlib.XMapEvent = xlib.XMapEvent._new_from_cython_event_(
            map_event=cast(xlib.TYPES.EVENTS.Cython_XMapEvent, mapped._cython_event),
        )
        self.assertEqual(wrapped_map.window, 6)
        self.assertTrue(wrapped_map.override_redirect)

        unmapped: xlib.XUnmapEvent = xlib.XUnmapEvent(display=self.display, event=5, window=6, from_configure=True)
        self.assertIsNotNone(unmapped._cython_event)
        wrapped_unmap: xlib.XUnmapEvent = xlib.XUnmapEvent._new_from_cython_event_(
            unmap_event=cast(xlib.TYPES.EVENTS.Cython_XUnmapEvent, unmapped._cython_event),
        )
        self.assertTrue(wrapped_unmap.from_configure)

    def test_button_round_trip(self) -> None:
        press: xlib.XButtonEvent = xlib.XButtonEvent(
            display=self.display,
            type=xlib.XButtonEvent.TYPE.ButtonPress,
            window=7,
            root=1,
            subwindow=0,
            button=xlib.BUTTONS.Button1,
            x=4,
            y=5,
            state=xlib.KEY_MASKS.ControlMask.value,
        )
        self.assertIsNotNone(press._cython_event)
        wrapped: xlib.XButtonEvent = xlib.XButtonEvent._new_from_cython_event_(
            button_event=cast(xlib.TYPES.EVENTS.Cython_XButtonEvent, press._cython_event),
        )
        self.assertEqual(wrapped.button, xlib.BUTTONS.Button1)
        self.assertEqual(wrapped.x, 4)
        self.assertEqual(wrapped.state, xlib.KEY_MASKS.ControlMask.value)


class TestWindowManagerSignals(unittest.TestCase):
    wm: WindowManager

    @classmethod
    def setUpClass(cls) -> None:
        probe: Optional[xlib.TYPES.Cython_Display] = _try_open_display()
        if probe is None:
            raise unittest.SkipTest("no X display")
        xlib.x_close_display(display=probe)

    def setUp(self) -> None:
        WindowManager.delete_singleton()
        self.wm = WindowManager(loop=None)

    def tearDown(self) -> None:
        try:
            self.wm.stop(exit=True)
        finally:
            WindowManager.delete_singleton()

    def test_configure_dispatches_client_copy_not_root(self) -> None:
        seen: list[tuple[int, int, int]] = []

        @self.wm.on_configure()
        def on_cfg(window: Window, event: xlib.XConfigureEvent) -> None:
            seen.append((int(window), event.width, event.height))

        client: int = 0x1111
        root_copy: xlib.XConfigureEvent = xlib.XConfigureEvent(
            display=self.wm.display,
            event=self.wm.root,
            window=client,
            width=100,
            height=50,
        )
        self.wm._handle_configure(event=root_copy)
        self.assertEqual(seen, [])

        client_copy: xlib.XConfigureEvent = xlib.XConfigureEvent(
            display=self.wm.display,
            event=client,
            window=client,
            width=640,
            height=480,
        )
        self.wm._handle_configure(event=client_copy)
        self.assertEqual(seen, [(client, 640, 480)])
        self.assertEqual(int(self.wm.event_window), client)

    def test_map_and_unmap(self) -> None:
        mapped: list[int] = []
        unmapped: list[bool] = []

        @self.wm.on_map()
        def on_map(window: Window, _event: xlib.XMapEvent) -> None:
            mapped.append(int(window))

        @self.wm.on_unmap()
        def on_unmap(_window: Window, event: xlib.XUnmapEvent) -> None:
            unmapped.append(event.from_configure)

        client: int = 0x2222
        self.wm._handle_map(
            event=xlib.XMapEvent(display=self.wm.display, event=client, window=client, override_redirect=False)
        )
        self.wm._handle_unmap(
            event=xlib.XUnmapEvent(display=self.wm.display, event=client, window=client, from_configure=True)
        )
        self.assertEqual(mapped, [client])
        self.assertEqual(unmapped, [True])

    def test_focus_ignores_pointer_detail_mode(self) -> None:
        focused: list[int] = []
        unfocused: list[int] = []

        @self.wm.on_focus()
        def on_focus(window: Window, _event: xlib.XFocusChangeEvent) -> None:
            focused.append(int(window))

        @self.wm.on_unfocus()
        def on_unfocus(window: Window, _event: xlib.XFocusChangeEvent) -> None:
            unfocused.append(int(window))

        client: int = 0x3333
        pointer: xlib.XFocusChangeEvent = xlib.XFocusChangeEvent(
            display=self.wm.display,
            type=xlib.XFocusChangeEvent.TYPE.FocusIn,
            window=client,
            detail=xlib.XFocusChangeEvent.NOTIFY_DETAIL.NotifyPointer,
            mode=xlib.XFocusChangeEvent.NOTIFY_MODE.NotifyGrab,
        )
        self.wm._handle_focus(event=pointer)
        self.assertEqual(focused, [])
        self.assertIn(client, self.wm.focus_history)

        real: xlib.XFocusChangeEvent = xlib.XFocusChangeEvent(
            display=self.wm.display,
            type=xlib.XFocusChangeEvent.TYPE.FocusIn,
            window=client,
            detail=xlib.XFocusChangeEvent.NOTIFY_DETAIL.NotifyNonlinear,
            mode=xlib.XFocusChangeEvent.NOTIFY_MODE.NotifyNormal,
        )
        self.wm._handle_focus(event=real)
        self.assertEqual(focused, [client])

        out: xlib.XFocusChangeEvent = xlib.XFocusChangeEvent(
            display=self.wm.display,
            type=xlib.XFocusChangeEvent.TYPE.FocusOut,
            window=client,
            detail=xlib.XFocusChangeEvent.NOTIFY_DETAIL.NotifyNonlinear,
            mode=xlib.XFocusChangeEvent.NOTIFY_MODE.NotifyNormal,
        )
        self.wm._handle_focus(event=out)
        self.assertEqual(unfocused, [client])

    def test_destroy_and_per_window_handler(self) -> None:
        all_gone: list[int] = []
        one_gone: list[int] = []
        client: int = 0x4444

        @self.wm.on_destroy()
        def on_any(window: Window, _event: xlib.XDestroyWindowEvent) -> None:
            all_gone.append(int(window))

        @self.wm.on_destroy(window=client)
        def on_one(window: Window, _event: xlib.XDestroyWindowEvent) -> None:
            one_gone.append(int(window))

        event: xlib.XDestroyWindowEvent = xlib.XDestroyWindowEvent(display=self.wm.display, event=client, window=client)
        self.wm._handle_destroy(event=event)
        self.wm._handle_destroy(event=event)
        self.assertEqual(all_gone, [client])
        self.assertEqual(one_gone, [client])
        self.assertNotIn(client, self.wm._destroy_handlers)

    def test_client_message(self) -> None:
        got: list[int] = []
        atom: xlib.TYPES.Cython_Atom = self.wm.atom_cache.get_atom(name="WM_PROTOCOLS")

        @self.wm.on_client_message(message_type="WM_PROTOCOLS")
        def on_msg(window: Window, _event: xlib.XClientMessageEvent) -> None:
            got.append(int(window))

        event: xlib.XClientMessageEvent = xlib.XClientMessageEvent(
            display=self.wm.display,
            window=0x5555,
            message_type=atom,
            format_=xlib.PROPERTY_FORMAT.LONG,
            data=[1, 0, 0, 0, 0],
        )
        self.wm._handle_client_message(event=event)
        self.assertEqual(got, [0x5555])

    def test_key_press_and_release_slots(self) -> None:
        order: list[str] = []
        client: int = 0x6666
        keycode: int = 38

        def on_press(_window: xlib.TYPES.Cython_Window, _event: xlib.XKeyEvent) -> None:
            order.append("press")

        def on_release(_window: xlib.TYPES.Cython_Window, _event: xlib.XKeyEvent) -> None:
            order.append("release")

        self.wm._key_grabs[client] = {(0, keycode): [on_press, on_release]}
        press: xlib.XKeyEvent = xlib.XKeyEvent(
            display=self.wm.display,
            type=xlib.XKeyEvent.TYPE.KeyPress,
            window=client,
            root=self.wm.root,
            subwindow=0,
            keycode=keycode,
            state=0,
        )
        release: xlib.XKeyEvent = xlib.XKeyEvent(
            display=self.wm.display,
            type=xlib.XKeyEvent.TYPE.KeyRelease,
            window=client,
            root=self.wm.root,
            subwindow=0,
            keycode=keycode,
            state=0,
        )
        self.wm._key_press_event_handler(event=press)
        self.wm._handle_keyrelease(event=release)
        self.assertEqual(order, ["press", "release"])

    def test_button_ignores_other_button_mask_in_state(self) -> None:
        clicks: list[int] = []
        client: int = 0x7777
        modifiers: int = KeyboardModifiers.Control.value

        def on_click(_window: xlib.TYPES.Cython_Window, event: xlib.XButtonEvent) -> None:
            clicks.append(int(event.button))

        self.wm._button_grabs[client] = {(modifiers, int(xlib.BUTTONS.Button1)): on_click}
        event: xlib.XButtonEvent = xlib.XButtonEvent(
            display=self.wm.display,
            type=xlib.XButtonEvent.TYPE.ButtonPress,
            window=client,
            root=self.wm.root,
            subwindow=0,
            button=xlib.BUTTONS.Button1,
            state=modifiers | xlib.BUTTON_MASKS.Button2Mask.value,
        )
        self.wm._handle_button(event=event)
        self.assertEqual(clicks, [int(xlib.BUTTONS.Button1)])

    def test_any_key_keycode(self) -> None:
        key: KeyDefinition.Key = KeyDefinition.Key(name="any_key")
        self.assertEqual(key.get_keycode(display=self.wm.display), xlib.CONSTANTS.KB.ANY_KEY)

    def test_create_map_destroy_window(self) -> None:
        window: xlib.TYPES.Cython_Window = xlib.x_create_window(display=self.wm.display, parent=self.wm.root)
        self.assertTrue(window)
        xlib.x_map_window(display=self.wm.display, window=window)
        xlib.x_sync(display=self.wm.display, discard=False)
        xlib.x_destroy_window(display=self.wm.display, window=window)
        xlib.x_sync(display=self.wm.display, discard=False)


class TestGrabDelivery(unittest.TestCase):
    wm: WindowManager
    nested: bool = False
    _saved_display: Optional[str] = None

    @classmethod
    def setUpClass(cls) -> None:
        global _nested_server
        cls._saved_display = os.getenv(key="DISPLAY")
        spawned: Optional[tuple[_Popen, str]] = _spawn_nested_x()
        if spawned is not None:
            _nested_server, nested_display = spawned
            os.environ["DISPLAY"] = nested_display
            cls.nested = True
        probe: Optional[xlib.TYPES.Cython_Display] = _try_open_display()
        if probe is None:
            _stop_nested_x()
            if cls._saved_display is None:
                _ = os.environ.pop("DISPLAY", default=None)
            else:
                os.environ["DISPLAY"] = cls._saved_display
            raise unittest.SkipTest("no X display")
        xlib.x_close_display(display=probe)

    @classmethod
    def tearDownClass(cls) -> None:
        _stop_nested_x()
        if cls._saved_display is None:
            _ = os.environ.pop("DISPLAY", default=None)
        else:
            os.environ["DISPLAY"] = cls._saved_display

    def setUp(self) -> None:
        WindowManager.delete_singleton()
        self.wm = WindowManager(loop=None)

    def tearDown(self) -> None:
        try:
            self.wm.stop(exit=True)
        finally:
            WindowManager.delete_singleton()

    def test_grab_key_delivers_via_xtest(self) -> None:
        if not xlib.xtest_query_extension(display=self.wm.display):
            raise unittest.SkipTest("XTEST extension not available")
        keycode: Optional[int] = _obscure_keycode(display=self.wm.display, nested=self.nested)
        if keycode is None:
            raise unittest.SkipTest("no usable keycode on this keyboard")

        xlib.x_set_error_handler(handler=_swallow_x_errors)
        seen: list[int] = []

        def on_press(_window: xlib.TYPES.Cython_Window, event: xlib.XKeyEvent) -> None:
            seen.append(int(event.keycode))

        key_definition: KeyDefinition = KeyDefinition(
            modifiers=KeyboardModifiers.NoModifiers,
            key=KeyDefinition.Key(keycode=keycode),
        )
        prev_focus, prev_revert = xlib.x_get_input_focus(display=self.wm.display)
        grab_window: Optional[xlib.TYPES.Cython_Window] = None
        try:
            grab_window = xlib.x_create_window(display=self.wm.display, parent=self.wm.root)
            xlib.x_map_window(display=self.wm.display, window=grab_window)
            xlib.x_sync(display=self.wm.display, discard=False)
            xlib.x_set_input_focus(display=self.wm.display, window=grab_window)
            xlib.x_sync(display=self.wm.display, discard=False)
            self.wm._grab_key_binding(window=grab_window, key_definition=key_definition, handler=on_press)
            xlib.x_sync(display=self.wm.display, discard=False)
            _drain_x_events(wm=self.wm)
            xlib.xtest_fake_key_event(display=self.wm.display, keycode=keycode, press=True)
            xlib.xtest_fake_key_event(display=self.wm.display, keycode=keycode, press=False)
            xlib.x_sync(display=self.wm.display, discard=False)
            _drain_x_events(wm=self.wm)
        finally:
            xlib.xtest_fake_key_event(display=self.wm.display, keycode=keycode, press=False)
            self.wm._ungrab_handler(handler=on_press)
            xlib.x_set_input_focus(display=self.wm.display, window=prev_focus, revert_to=prev_revert)
            if grab_window:
                xlib.x_destroy_window(display=self.wm.display, window=grab_window)
            xlib.x_sync(display=self.wm.display, discard=False)

        self.assertEqual(seen, [keycode])

    def test_grab_button_delivers_via_xtest(self) -> None:
        if not self.nested:
            raise unittest.SkipTest("button grab delivery needs Xephyr/Xvfb (will not warp the session pointer)")
        if not xlib.xtest_query_extension(display=self.wm.display):
            raise unittest.SkipTest("XTEST extension not available")

        xlib.x_set_error_handler(handler=_swallow_x_errors)
        seen: list[int] = []
        button: int = int(xlib.BUTTONS.Button1)

        def on_click(_window: xlib.TYPES.Cython_Window, event: xlib.XButtonEvent) -> None:
            seen.append(int(event.button))

        grab_window: Optional[xlib.TYPES.Cython_Window] = None
        try:
            grab_window = xlib.x_create_window(display=self.wm.display, parent=self.wm.root)
            xlib.x_map_window(display=self.wm.display, window=grab_window)
            xlib.x_sync(display=self.wm.display, discard=False)
            xlib.xtest_fake_motion_event(display=self.wm.display, x=8, y=8)
            xlib.x_sync(display=self.wm.display, discard=False)
            self.wm._grab_button_binding(
                window=grab_window,
                button=button,
                modifiers_value=KeyboardModifiers.NoModifiers.value,
                handler=on_click,
            )
            xlib.x_sync(display=self.wm.display, discard=False)
            _drain_x_events(wm=self.wm)
            xlib.xtest_fake_button_event(display=self.wm.display, button=button, press=True)
            xlib.xtest_fake_button_event(display=self.wm.display, button=button, press=False)
            xlib.x_sync(display=self.wm.display, discard=False)
            _drain_x_events(wm=self.wm)
        finally:
            xlib.xtest_fake_button_event(display=self.wm.display, button=button, press=False)
            self.wm._ungrab_button_handler(handler=on_click)
            if grab_window:
                xlib.x_destroy_window(display=self.wm.display, window=grab_window)
            xlib.x_sync(display=self.wm.display, discard=False)

        self.assertEqual(seen, [button])


if __name__ == "__main__":
    _ = unittest.main()
