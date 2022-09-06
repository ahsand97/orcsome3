import logging
from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, cast

from . import ev, wrappers, xlib
from .aliases import KEYS as KEY_ALIASES

logger: logging.Logger = logging.getLogger(name=__name__)
ignore_logger: bool = False

MODIFICATORS: Dict[str, int] = {
    "Alt": xlib.MASKS.Mod1Mask.value,
    "Control": xlib.MASKS.ControlMask.value,
    "Ctrl": xlib.MASKS.ControlMask.value,
    "Shift": xlib.MASKS.ShiftMask.value,
    "Win": xlib.MASKS.Mod4Mask.value,
    "Mod": xlib.MASKS.Mod4Mask.value,
    "Hyper": xlib.MASKS.Mod4Mask.value,
    "Super": xlib.MASKS.Mod4Mask.value,
}

IGNORED_MOD_MASKS: Tuple[int, int, int, int] = (
    0,
    int(xlib.MASKS.LockMask.value),
    int(xlib.MASKS.Mod2Mask.value),
    int(xlib.MASKS.LockMask.value | xlib.MASKS.Mod2Mask.value),
)


class RestartException(Exception):
    # Exception raised by method `wm.actions.restart()`
    pass


class Actions(ABC):
    @abstractmethod
    def focus_next(self, window: Optional[wrappers.Window] = None) -> None:
        """Focus next client on current desktop.

        next/prev are defined by client creation time
        """
        pass

    @abstractmethod
    def focus_prev(self, window: Optional[wrappers.Window] = None) -> None:
        """Focus previous client on current desktop.

        next/prev are defined by client creation time
        """
        pass

    @abstractmethod
    def restart(self) -> None:
        """Restarts orcsome"""
        pass

    @abstractmethod
    def activate_window_desktop(self, window: wrappers.Window) -> Optional[bool]:
        """Activate a window's desktop

        Returns:

        * True if window is placed on different from current desktop (activates window's desktop)
        * False if window's desktop and current desktop are the same
        * None if window does not have a desktop property
        """
        pass


class WM:
    """Core orcsome instance

    Can be get in any time as::

        from orcsome3.orcsome import get_wm
        from orcsome3.orcsome.wm import WM

        wm: WM = get_wm()
    """

    def __init__(self, loop: ev.Loop) -> None:
        self._handlers: Dict[int, Callable[[xlib.XEvent], None]] = {
            xlib.EVENTS.KeyPress.value: self._handle_keypress,
            xlib.EVENTS.KeyRelease.value: self._handle_keyrelease,
            xlib.EVENTS.CreateNotify.value: self._handle_create,
            xlib.EVENTS.DestroyNotify.value: self._handle_destroy,
            xlib.EVENTS.FocusIn.value: self._handle_focus,
            xlib.EVENTS.FocusOut.value: self._handle_focus,
            xlib.EVENTS.PropertyNotify.value: self._handle_property,
        }
        # This is filled every time a new event comes by the function `_xevent_cb`
        self._native_event: Any = xlib.ffi.new("XEvent *")

        # Event associated with the callback
        self._event: Optional[
            Union[xlib.XKeyEvent, xlib.XCreateWindowEvent, xlib.XDestroyWindowEvent, xlib.XPropertyEvent]
        ] = None
        self._event_window: Optional[wrappers.Window] = None

        # Handlers
        self._key_handlers: Dict[xlib.Window, Dict[Tuple[int, int], Callable[[], None]]] = {}
        self._property_handlers: Dict[xlib.Atom, Dict[Optional[xlib.Window], List[Callable[[], None]]]] = {}
        self._create_handlers: List[Callable[[], None]] = []
        self._destroy_handlers: Dict[Optional[xlib.Window], List[Callable[[], None]]] = {}
        self._init_handlers: List[Callable[[], None]] = []
        self._deinit_handlers: List[Callable[[], None]] = []
        self._timer_handlers: List[Callable[[], None]] = []
        self._restart_handler: Optional[Callable[[], None]] = None

        # History
        self.focus_history: List[xlib.Window] = []

        # Auxiliar vars to avoid callbacks being called twice
        self._recently_destroyed_window: Optional[xlib.Window] = None
        self._recently_mapped_window: Optional[xlib.Window] = None

        self.dpy: xlib.Display = xlib.lib.XOpenDisplay(xlib.ffi.NULL)  # X11's Display
        if self.dpy == xlib.ffi.NULL:
            raise Exception("Can't open display")

        self.root: xlib.Window = xlib.lib.DefaultRootWindow(self.dpy)  # Root window
        self.atom: xlib.AtomCache = xlib.AtomCache(dpy=self.dpy)

        self._loop: ev.Loop = loop
        self._xevent_watcher: ev.IOWatcher = ev.IOWatcher(
            callback=self._xevent_cb, file_descriptor=xlib.lib.ConnectionNumber(self.dpy), flags=ev.lib.EV_READ
        )
        self._xevent_watcher.start(loop=self._loop)

        self.track_kbd_layout: bool = False
        self._startup: bool = False

        from . import actions

        self.actions: Actions = actions.Actions(window_manager=self)

    def init(self) -> None:
        # Report all events within the root window
        xlib.lib.XSelectInput(self.dpy, self.root, xlib.lib.SubstructureNotifyMask)

        for handler in self._init_handlers:
            handler()

        self._startup = True
        for window in self.get_clients():
            self._process_create_window(window=window)

        xlib.lib.XSync(self.dpy, False)
        xlib.lib.XSetErrorHandler(xlib.lib.error_handler)

        # Initializes MagickWand
        xlib.lib.MagickWandGenesis()

    def stop(self, is_exit: bool = False) -> None:
        self._key_handlers.clear()
        self._property_handlers.clear()
        self._create_handlers[:] = []
        self._destroy_handlers.clear()
        self.focus_history[:] = []

        if not is_exit:
            xlib.lib.XUngrabKey(self.dpy, xlib.lib.AnyKey, xlib.lib.AnyModifier, self.root)
            for window in self.get_clients():
                xlib.lib.XUngrabKey(self.dpy, xlib.lib.AnyKey, xlib.lib.AnyModifier, window)

        for handler in self._timer_handlers:
            getattr(handler, "stop")
        self._timer_handlers[:] = []

        for handler in self._deinit_handlers:
            try:
                handler()
            except:
                logger.exception(msg="Shutdown error")

        self._init_handlers[:] = []
        self._deinit_handlers[:] = []

        # Ends MagickWand
        xlib.lib.MagickWandTerminus()

    def create_window(self, window_id: int) -> wrappers.Window:
        window = wrappers.Window(window_id)
        window.wm = self
        return window

    def get_keycode_from_string(self, key: str) -> Optional[int]:
        keysym: int = xlib.lib.XStringToKeysym(str.encode(KEY_ALIASES.get(key, key)))
        if keysym is xlib.lib.NoSymbol:
            return None
        return int(xlib.lib.XKeysymToKeycode(self.dpy, keysym))

    def parse_keydef(self, keydef: str) -> Optional[List[Tuple[int, int]]]:
        keys: List[str] = [r.strip() for r in "".join(keydef.split()).split()]
        result: List[Tuple[int, int]] = []
        for k in keys:
            parts = k.split(sep="+")
            mod, key = parts[:-1], parts[-1]
            modmask = 0
            for m in mod:
                try:
                    modmask |= MODIFICATORS[m]
                except KeyError:
                    return None

            code = self.get_keycode_from_string(key=key)
            if not code:
                return None
            result.append((code, modmask))

        return result

    def on_key(
        self, keydef: str, window: Optional[wrappers.Window] = None
    ) -> Callable[[Callable[[], None]], Callable[[], None]]:
        """Signal decorator to define hotkey

        Signature of decorated function should be::

            function_cb() -> None:
                # ... function's body
                pass

        Key defenition is a string in format ``[mod + ... +]keysym`` where ``mod`` is
        one of modificators [Alt, Shift, Control(Ctrl), Mod(Win)] and
        ``keysym`` is a key name.

        You can define global hotkeys as follows::

            @wm.on_key(keydef='Control + a')
            def test() -> None:
                print('hotkey Control + a pressed')

            wm.on_key(keydef='Control+b')(lambda: print('hotkey Control + b pressed'))

        Or keybinded to a specific window::

            @wm.on_create(cls='URxvt')
            def bind_urxvt_keys() -> None:
                # Custom key to close only urxvt windows
                wm.on_key(window=wm.event_window, keydef='Ctrl+d')(lambda: wm.close_window(window=wm.event_window))
        """

        def decorator(function: Callable[[], None]) -> Callable[[], None]:
            @wraps(function)
            def inner() -> Callable[[], None]:
                window_ = window or self.root
                code_mmask_list = self.parse_keydef(keydef=keydef)
                if not code_mmask_list or not len(code_mmask_list) == 1:
                    logger.error(msg=f"Invalid key definition [{keydef}]")
                else:
                    code, modmask = code_mmask_list[0]
                    keys: List[Tuple[int, int]] = []
                    for imask in IGNORED_MOD_MASKS:
                        mask = modmask | imask
                        xlib.lib.XGrabKey(
                            self.dpy, code, mask, window_, False, xlib.lib.GrabModeAsync, xlib.lib.GrabModeAsync
                        )
                        self._key_handlers.setdefault(window_, {})[(mask, code)] = function
                        keys.append((mask, code))

                    def remove() -> None:
                        for key in keys:
                            del self._key_handlers[window_][key]

                    setattr(function, "remove", remove)
                return function

            return inner()

        return decorator

    def on_create(self, **matchers: Any) -> Callable[[Callable[[], None]], Callable[[], None]]:
        """Signal decorator to handle window creation

        Signature of decorated function should be::

            function_cb() -> None:
                # ... function's body
                pass

        Can be used in two forms. Listen to any window creation::

           @wm.on_create()
           def debug() -> None:
               print(wm.event_window.get_wm_class())

        Or specific window::

           @wm.on_create(cls='Opera')
           def use_firefox_luke() -> None:
               wm.close_window(window=wm.event_window)
               subprocess.Popen(cmd=['firefox'])

        Also, orcsome calls on_create handlers on its startup.
        You can check ``wm.startup`` attribute to denote such event.

        See :meth:`orcsome3.orcsome.wrappers.Window.matches` for ``**matchers`` argument description.
        """

        def decorator(function: Callable[[], None]) -> Callable[[], None]:
            @wraps(function)
            def inner() -> Callable[[], None]:
                return self._on_create_manage(callback=function, ignore_startup=False, **matchers)

            return inner()

        return decorator

    def on_manage(self, **matchers: Any) -> Callable[[Callable[[], None]], Callable[[], None]]:
        """Signal decorator to handle window creation (ignoring orcsome's startup)

        Signature of decorated function should be::

            function_cb() -> None:
                # ... function's body
                pass

        Can be used in two forms. Listen to any window creation::

            @wm.on_manage()
            def debug() -> None:
                print(wm.event_window.get_wm_class())

        or can be written::

            wm.on_manage()(lambda: print(wm.event_window.get_wm_class()))

        Or specific window::

            @wm.on_manage(cls='Opera')
            def use_firefox_luke():
                wm.close_window(window=wm.event_window)
                subprocess.Popen(cmd=['firefox'])

        See :meth:`orcsome3.orcsome.wrappers.Window.matches` for ``**matchers`` argument description.
        """

        def decorator(function: Callable[[], None]) -> Callable[[], None]:
            @wraps(function)
            def inner() -> Callable[[], None]:
                return self._on_create_manage(callback=function, ignore_startup=True, **matchers)

            return inner()

        return decorator

    def _on_create_manage(
        self, callback: Callable[[], None], ignore_startup: bool, **matchers: Any
    ) -> Callable[[], None]:
        if matchers:
            old_function = callback

            def new_callback() -> None:
                if self.event_window.matches(**matchers):
                    old_function()

            callback = new_callback

        if ignore_startup:
            old_old_function = callback

            def new_callback() -> None:
                if not self._startup:
                    old_old_function()

            callback = new_callback

        self._create_handlers.append(callback)
        setattr(callback, "remove", lambda: self._create_handlers.remove(callback))
        return callback

    def on_destroy(
        self, window: Optional[wrappers.Window] = None
    ) -> Callable[[Callable[[], None]], Callable[[], None]]:
        """Signal decorator to handle window destroy

        Signature of decorated function should be::

            function_cb() -> None:
                # ... function's body
                pass

        It can be used to all windows::

            @wm.on_destroy()
            def cb_destroy_window() -> None:
                print(f'The window {wm.event_window} was destroyed')

        Or to a specific window::

            @wm.on_manage(name='easyeffects', cls='easyeffects')
            def on_create_easyeffects() -> None:
                @wm.on_destroy(window=wm.event_window)
                def on_destroy_easyeffects() -> None:
                    print("easyeffect's window destroyed")

        `wm.event_window` only contains the id of the recently closed window,
        trying to access any attribute of the window will result in an error
        cause the function is executed when the window is clonsing/has closed.
        """

        def decorator(function: Callable[[], None]) -> Callable[[], None]:
            @wraps(function)
            def inner() -> Callable[[], None]:
                self._destroy_handlers.setdefault(window, []).append(function)

                def remove() -> None:
                    self._destroy_handlers[window].remove(function)

                setattr(function, "remove", remove)
                return function

            return inner()

        return decorator

    def on_property_change(
        self, properties: List[str], window: Optional[wrappers.Window] = None
    ) -> Callable[[Callable[[], None]], Callable[[], None]]:
        """Signal decorator to handle window property change

        Signature of decorated function should be::

            function_cb() -> None:
                # ... function's body
                pass

        One can handle any window property change::

            @wm.on_property_change(properties=['_NET_WM_STATE']) # one or multiple properties can be handled
            def window_maximized_state_change() -> None:
                window: Window = wm.event_window
                if window.maximized_vert and window.maximized_horz:
                    print('Look, ma! Window is maximized now!')

        And specific window::

            @wm.on_create()
            def switch_to_desktop() -> None:
                if not wm.startup:
                    if wm.actions.activate_window_desktop(window=wm.event_window) is None:
                        # Created window has no any attached desktop so wait for it
                        @wm.on_property_change(window=wm.event_window, properties=['_NET_WM_DESKTOP'])
                        def property_was_set() -> None:
                            wm.actions.activate_window_desktop(window=wm.event_window)
                            getattr('property_was_set', 'remove') # removes the callback

        """

        def decorator(function: Callable[[], None]) -> Callable[[], None]:
            @wraps(function)
            def inner() -> Callable[[], None]:
                for prop in properties:
                    self._property_handlers.setdefault(self.atom[prop], {}).setdefault(window, []).append(function)

                def remove() -> None:
                    for prop in properties:
                        self._property_handlers[self.atom[prop]][window].remove(function)

                setattr(function, "remove", remove)
                return function

            return inner()

        return decorator

    def on_timer(
        self, timeout: float, start: bool = True, first_timeout: Optional[float] = None
    ) -> Callable[[Callable[[], None]], Callable[[], None]]:
        def decorator(function: Callable[[], None]) -> Callable[[], None]:
            @wraps(function)
            def inner() -> Callable[[], None]:
                def callback_of_timer(loop: Any, watcher: Any, events: int) -> None:
                    timer.stop(loop=self._loop) if function() else timer.update_next_stop()

                self._timer_handlers.append(function)
                timer = ev.TimerWatcher(callback=callback_of_timer, after=first_timeout or timeout, repeat=timeout)
                setattr(function, "start", lambda: timer.start(loop=self._loop))
                setattr(function, "stop", lambda: timer.stop(loop=self._loop))
                setattr(function, "again", lambda: timer.again(loop=self._loop))
                setattr(function, "remaining", lambda: timer.remaining(loop=self._loop))
                setattr(function, "overdue", lambda timeout: timer.overdue(timeout=timeout))

                if start:
                    getattr(function, "start")

                def remove() -> None:
                    try:
                        getattr(function, "stop")
                        self._timer_handlers.remove(function)
                    except:
                        pass

                setattr(function, "remove", remove)
                return function

            return inner()

        return decorator

    def get_clients(self) -> List[wrappers.Window]:
        """Return wm client list"""
        result = xlib.get_window_property(
            display=self.dpy, window=self.root, property=self.atom["_NET_CLIENT_LIST"], type=self.atom["WINDOW"] or 0
        )
        return [] if not result else [self.create_window(window_id=x) for x in cast(List[int], result)]

    def get_stacked_clients(self) -> List[wrappers.Window]:
        """Return client list in stacked order.

        Most top window will be last in list. Can be useful to determine window visibility.
        """
        result = xlib.get_window_property(
            display=self.dpy,
            window=self.root,
            property=self.atom["_NET_CLIENT_LIST_STACKING"],
            type=self.atom["WINDOW"] or 0,
        )
        return [] if not result else [self.create_window(window_id=r) for r in cast(List[int], result)]

    @property
    def current_window(self) -> Optional[wrappers.Window]:
        """Returns currently active (with input focus) window"""
        result = xlib.get_window_property(
            display=self.dpy, window=self.root, property=self.atom["_NET_ACTIVE_WINDOW"], type=self.atom["WINDOW"]
        )
        return None if not result else self.create_window(window_id=cast(List[xlib.Window], result)[0])

    @property
    def current_desktop(self) -> int:
        """Return current desktop number

        The index of the current desktop. This is always an integer between 0 and _NET_NUMBER_OF_DESKTOPS - 1
        """
        result = xlib.get_window_property(
            display=self.dpy, window=self.root, property=self.atom["_NET_CURRENT_DESKTOP"]
        )
        return cast(List[int], result)[0]

    @property
    def wm_name(self) -> Optional[str]:
        """
        Returns the actual Window Manager name or None if there's no ICCCM2.0-compliant window manager running.\n
        By the EWMH spec, a compliant window manager will set the _NET_SUPPORTING_WM_CHECK property on the root window to a window ID.\n
        If the `_NET_SUPPORTING_WM_CHECK` property exists and contains the ID of an existing window, then a ICCCM2.0-compliant window manager is running.\n
        If the property exists but does not contain the ID of an existing window, then a ICCCM2.0-compliant window manager exited without proper cleanup.\n
        If the property does not exist, then no ICCCM2.0-compliant window manager is running.
        """
        result = xlib.get_window_property(
            display=self.dpy, window=self.root, property=self.atom["_NET_SUPPORTING_WM_CHECK"], type=self.atom["WINDOW"]
        )
        if not result:
            return None
        result = xlib.get_window_property(
            display=self.dpy,
            window=cast(List[int], result)[0],
            property=self.atom["_NET_WM_NAME"],
            type=self.atom["UTF8_STRING"],
        )
        return None if not result else cast(List[str], result)[0]

    @property
    def event_window(self) -> wrappers.Window:
        """Returns the window associated with the event"""
        return cast(wrappers.Window, self._event_window)

    @property
    def event(self) -> Union[xlib.XKeyEvent, xlib.XCreateWindowEvent, xlib.XDestroyWindowEvent, xlib.XPropertyEvent]:
        """Returns the event associated"""
        return cast(
            Union[xlib.XKeyEvent, xlib.XCreateWindowEvent, xlib.XDestroyWindowEvent, xlib.XPropertyEvent], self._event
        )

    def activate_desktop(self, num: int) -> None:
        """Activate desktop ``num``"""
        if num < 0:
            return

        self._send_event(window=self.root, mtype=self.atom["_NET_CURRENT_DESKTOP"], data=[num])
        self._flush()

    def _send_event(self, window: xlib.Window, mtype: xlib.Atom, data: List[int]) -> None:
        data = (data + ([0] * (5 - len(data))))[:5]
        ev = xlib.ffi.new(
            "XClientMessageEvent *",
            {
                "type": xlib.lib.ClientMessage,
                "window": window,
                "message_type": mtype,
                "format": 32,
                "data": {"l": data},
            },
        )
        xlib.lib.XSendEvent(
            self.dpy, self.root, False, xlib.lib.SubstructureRedirectMask, xlib.ffi.cast("XEvent *", ev)
        )

    def _flush(self) -> None:
        xlib.lib.XFlush(self.dpy)

    def find_clients(self, clients: List[wrappers.Window], **matchers: Any) -> List[wrappers.Window]:
        """Return matching clients list

        :param clients: window list returned by :meth:`get_clients` or :meth:`get_stacked_clients`.
        :param **matchers: keyword arguments defined in :meth:`orcsome3.orcsome.wrappers.Window.matches`
        """
        return [r for r in clients if r.matches(**matchers)]

    def find_client(self, clients: List[wrappers.Window], **matchers: Any) -> Optional[wrappers.Window]:
        """Return first matching client

        :param clients: window list returned by :meth:`get_clients` or :meth:`get_stacked_clients`.
        :param **matchers: keyword arguments defined in :meth:`orcsome3.orcsome.wrappers.Window.matches`
        """
        result = self.find_clients(clients, **matchers)
        try:
            return result[0]
        except IndexError:
            return None

    def _process_create_window(self, window: wrappers.Window) -> None:
        xlib.lib.XSelectInput(
            self.dpy, window, xlib.lib.StructureNotifyMask | xlib.lib.PropertyChangeMask | xlib.lib.FocusChangeMask
        )
        self._event_window = window
        for handler in self._create_handlers:
            handler()

    def _handle_keypress(self, event: xlib.XEvent) -> None:
        xkeyevent: xlib.XKeyEvent = xlib.XKeyEvent(event=event)
        logger.info(msg=f"Keypress {xkeyevent.state} {xkeyevent.keycode}")
        try:
            handler = self._key_handlers[xkeyevent.window][(xkeyevent.state, xkeyevent.keycode)]
        except KeyError:
            pass
        else:
            self._event = xkeyevent
            self._event_window = self.create_window(window_id=xkeyevent.window)
            handler()

    def _handle_keyrelease(self, event: xlib.XEvent) -> None:
        keyevent: xlib.XKeyEvent = xlib.XKeyEvent(event=event)
        logger.info(msg=f"KeyRelease {keyevent.state} {keyevent.keycode}")

    def _handle_create(self, event: xlib.XEvent) -> None:
        xcreatewindowevent: xlib.XCreateWindowEvent = xlib.XCreateWindowEvent(event=event)
        self._startup = False
        window: wrappers.Window = self.create_window(window_id=xcreatewindowevent.window)
        global ignore_logger
        ignore_logger = True
        if not xlib.get_window_attributes(display=self.dpy, window=window):
            ignore_logger = False
            return
        ignore_logger = False
        self._event = xcreatewindowevent
        self._process_create_window(window=window)

    def _handle_destroy(self, event: xlib.XEvent) -> None:
        xdestroywindowevent: xlib.XDestroyWindowEvent = xlib.XDestroyWindowEvent(event=event)
        if xdestroywindowevent.window == self._recently_destroyed_window:
            return
        self._recently_destroyed_window = xdestroywindowevent.window

        handlers: List[Callable[[], None]] = []
        if None in self._destroy_handlers.keys():
            handlers.extend(self._destroy_handlers[None])
        if xdestroywindowevent.window in self._destroy_handlers.keys():
            handlers.extend(self._destroy_handlers[xdestroywindowevent.window])

        self._event = xdestroywindowevent
        self._event_window = self.create_window(window_id=xdestroywindowevent.window)
        for handler in handlers:
            handler()
        self._clean_window_data(window=xdestroywindowevent.window)

    def _handle_property(self, event: xlib.XEvent) -> None:
        xpropertyevent: xlib.XPropertyEvent = xlib.XPropertyEvent(event=event)
        atom: xlib.Atom = xpropertyevent.atom
        if xpropertyevent.state.value == xlib.lib.PropertyNewValue and atom in self._property_handlers:
            wphandlers = self._property_handlers[atom]
            self._event = xpropertyevent
            self._event_window = self.create_window(window_id=xpropertyevent.window)
            if xpropertyevent.window in wphandlers:
                for handler in wphandlers[xpropertyevent.window]:
                    handler()

            if None in wphandlers:
                for handler in wphandlers[None]:
                    handler()

    def _handle_focus(self, event: xlib.XEvent) -> None:
        xfocuschangeevent: xlib.XFocusChangeEvent = xlib.XFocusChangeEvent(event=event)
        if xfocuschangeevent.type == xlib.lib.FocusIn:
            try:
                self.focus_history.remove(xfocuschangeevent.window)
            except ValueError:
                pass

            self.focus_history.append(xfocuschangeevent.window)
            if (
                xfocuschangeevent.mode.value in (xlib.lib.NotifyNormal, xlib.lib.NotifyWhileGrabbed)
                and self.track_kbd_layout
            ):
                prop = xlib.get_window_property(
                    display=self.dpy, window=xfocuschangeevent.window, property=self.atom["_ORCSOME_KBD_GROUP"]
                )
                if prop:
                    xlib.set_kbd_group(display=self.dpy, group=int(prop[0]))
                else:
                    xlib.set_kbd_group(display=self.dpy, group=0)
        else:
            if (
                xfocuschangeevent.mode.value in (xlib.lib.NotifyNormal, xlib.lib.NotifyWhileGrabbed)
                and self.track_kbd_layout
            ):
                xlib.set_window_property(
                    display=self.dpy,
                    window=xfocuschangeevent.window,
                    property=self.atom["_ORCSOME_KBD_GROUP"],
                    type=self.atom["CARDINAL"],
                    format=32,
                    values=[xlib.get_kbd_group(display=self.dpy)],
                )

    def _xevent_cb(self, loop: Any, watcher: Any, events: int) -> None:
        event = self._native_event
        while True:
            pending_events: int = xlib.lib.XPending(self.dpy)
            if not pending_events:
                break

            while pending_events > 0:
                xlib.lib.XNextEvent(self.dpy, event)
                pending_events -= 1

                try:
                    handler = self._handlers[event.type]
                except KeyError:
                    continue

                try:
                    handler(event)
                except RestartException:
                    if self._restart_handler:
                        self._restart_handler()
                        return
                except Exception as e:
                    logger.exception(msg=e)

    def _clean_window_data(self, window: xlib.Window) -> None:
        if window in self._key_handlers:
            del self._key_handlers[window]

        if window in self._destroy_handlers:
            del self._destroy_handlers[window]

        try:
            self.focus_history.remove(window)
        except ValueError:
            pass

        for atom, whandlers in list(self._property_handlers.items()):
            if window in whandlers:
                del whandlers[window]

            if not len(self._property_handlers[atom]):
                del self._property_handlers[atom]

    def focus_window(self, window: xlib.Window) -> None:
        """Activate window"""
        self._send_event(window=window, mtype=self.atom["_NET_ACTIVE_WINDOW"], data=[2, xlib.lib.CurrentTime])
        self._flush()

    def focus_and_raise(self, window: wrappers.Window) -> None:
        """Activate window's desktop, set input focus and raise it"""
        self.actions.activate_window_desktop(window=window)
        xlib.lib.XConfigureWindow(
            self.dpy, window, xlib.lib.CWStackMode, xlib.ffi.new("XWindowChanges *", {"stack_mode": xlib.lib.Above})
        )
        self.focus_window(window=window)

    def place_window_above(self, window: xlib.Window) -> None:
        """Float up window in wm stack"""
        xlib.lib.XConfigureWindow(
            self.dpy, window, xlib.lib.CWStackMode, xlib.ffi.new("XWindowChanges *", {"stack_mode": xlib.lib.Above})
        )
        self._flush()

    def place_window_below(self, window: xlib.Window) -> None:
        """Float down window in wm stack"""
        xlib.lib.XConfigureWindow(
            self.dpy, window, xlib.lib.CWStackMode, xlib.ffi.new("XWindowChanges *", {"stack_mode": xlib.lib.Below})
        )
        self._flush()

    def _change_window_hidden_state(self, window: xlib.Window, minimize: bool) -> None:
        params = int(minimize), self.atom["_NET_WM_STATE_HIDDEN"]
        self._send_event(window=window, mtype=self.atom["_NET_WM_STATE"], data=list(params))
        self._flush()

    def minimize_window(self, window: xlib.Window) -> None:
        """Minimize window"""
        self._change_window_hidden_state(window=window, minimize=True)

    def restore_window(self, window: xlib.Window) -> None:
        """Restore window"""
        self._change_window_hidden_state(window=window, minimize=False)

    def set_window_state(
        self,
        window: xlib.Window,
        taskbar: Optional[bool] = None,
        pager: Optional[bool] = None,
        decorate: Optional[bool] = None,
        otaskbar: Optional[bool] = None,
        vmax: Optional[bool] = None,
        hmax: Optional[bool] = None,
    ) -> None:
        """
        Set window state

        `taskbar`: Indicates if the window is going to be included on the taskbar (_NET_WM_STATE_SKIP_TASKBAR)
        `pager`: Indicates if the window is going to be included on the Pager (_NET_WM_STATE_SKIP_PAGER)
        `decorate`: Indicates if the window is going to have decorations
        `otaskbar`: Indicates if the window is going to be ignored by orcsome3
        `vmax`: Indicates if the window is going to be maximized vertically (_NET_WM_STATE_MAXIMIZED_VERT)
        `hmax`: Indicates if the window is going to be maximized horizontally (_NET_WM_STATE_MAXIMIZED_HORZ)
        """
        state_atom: xlib.Atom = self.atom["_NET_WM_STATE"]
        params: Optional[List[int]] = None

        if decorate is not None:
            if self.wm_name == "Openbox":
                params = [int(not decorate), self.atom["_OB_WM_STATE_UNDECORATED"]]
                self._send_event(window=window, mtype=state_atom, data=params)
            else:
                motif_hints = xlib.get_window_property(
                    display=self.dpy, window=window, property=self.atom["_MOTIF_WM_HINTS"]
                )
                if motif_hints is not None and len(motif_hints) == 5:
                    params = cast(List[int], motif_hints)
                    params[2] = int(decorate)
                else:
                    # "0x2, 0x0, 0x0, 0x0, 0x0" to undecorate and "0x2, 0x0, 0x1, 0x0, 0x0" to redecorate
                    params = [2, 0, int(decorate), 0, 0]
                xlib.set_window_property(
                    display=self.dpy,
                    window=window,
                    property=self.atom["_MOTIF_WM_HINTS"],
                    type=self.atom["_MOTIF_WM_HINTS"],
                    format=32,
                    values=params,
                )

        if taskbar is not None:
            params = [int(not taskbar), self.atom["_NET_WM_STATE_SKIP_TASKBAR"]]
            self._send_event(window=window, mtype=state_atom, data=params)

        if vmax is not None and vmax == hmax:
            params = [int(vmax), self.atom["_NET_WM_STATE_MAXIMIZED_VERT"], self.atom["_NET_WM_STATE_MAXIMIZED_HORZ"]]
            self._send_event(window=window, mtype=state_atom, data=params)

        if otaskbar is not None:
            params = [] if otaskbar else [self.atom["_ORCSOME_SKIP_TASKBAR"]]
            xlib.set_window_property(
                display=self.dpy,
                window=window,
                property=self.atom["_ORCSOME_STATE"],
                type=self.atom["ATOM"],
                format=32,
                values=params,
            )

        if pager is not None:
            params = [int(not pager), self.atom["_NET_WM_STATE_SKIP_PAGER"]]
            self._send_event(window=window, mtype=state_atom, data=params)

        self._flush()

    def get_window_geometry(self, window: xlib.Window) -> Tuple[int, int, int, int]:
        """Get window geometry

        Returns window geometry without decorations"""
        root_ret = xlib.ffi.new("Window *")
        x = xlib.ffi.new("int *")
        y = xlib.ffi.new("int *")
        w = xlib.ffi.new("unsigned int *")
        h = xlib.ffi.new("unsigned int *")
        border_width = xlib.ffi.new("unsigned int *")
        depth = xlib.ffi.new("unsigned int *")
        xlib.lib.XGetGeometry(self.dpy, window, root_ret, x, y, w, h, border_width, depth)
        return x[0], y[0], w[0], h[0]

    def get_screen_size(self) -> Tuple[int, int]:
        """Get size of screen (root window)"""
        return self.get_window_geometry(window=self.root)[2:]

    def get_workarea(self, desktop: Optional[int] = None) -> List[int]:
        """Get workarea geometery

        :param desktop: Desktop for working area receiving. If None then current_desktop is used"""
        result = xlib.get_window_property(
            display=self.dpy, window=self.root, property=self.atom["_NET_WORKAREA"], type=self.atom["CARDINAL"]
        )
        if desktop is None:
            desktop = self.current_desktop
            if not desktop:
                return []
        return cast(List[int], result)[4 * desktop : 4 * desktop + 4]

    def moveresize_window(
        self,
        window: xlib.Window,
        x: Optional[int] = None,
        y: Optional[int] = None,
        w: Optional[int] = None,
        h: Optional[int] = None,
    ) -> None:
        """Change window geometry"""
        flags = 0
        flags |= 2 << 12
        if x is not None:
            flags |= 1 << 8
        if y is not None:
            flags |= 1 << 9
        if w is not None:
            flags |= 1 << 10
        if h is not None:
            flags |= 1 << 11
        # Workarea offsets
        o_x, o_y, _, _ = tuple(self.get_workarea())
        params = (flags, cast(int, x) + o_x, cast(int, y) + o_y, max(1, cast(int, w)), max(1, cast(int, h)))
        self._send_event(window=window, mtype=self.atom["_NET_MOVERESIZE_WINDOW"], data=list(params))
        self._flush()

    def moveresize_window2(self, window: wrappers.Window, left: int, top: int, right: int, bottom: int) -> None:
        """Change window geometry"""
        flags = 0x2F00
        # Workarea offsets
        dl, dt, dw, dh = tuple(self.get_workarea(desktop=window.desktop))
        params = (flags, left + dl, top + dt, max(1, dw - right - left), max(1, dh - bottom - top))
        self._send_event(window=window, mtype=self.atom["_NET_MOVERESIZE_WINDOW"], data=list(params))
        self._flush()

    def close_window(self, window: Optional[wrappers.Window] = None) -> None:
        """Send request to wm to close window"""
        window = window or self.current_window
        if not window:
            return
        self._send_event(window=window, mtype=self.atom["_NET_CLOSE_WINDOW"], data=[xlib.lib.CurrentTime])
        self._flush()

    def change_window_desktop(self, window: xlib.Window, desktop: int) -> None:
        """Move window to ``desktop``"""
        if desktop < 0:
            return

        self._send_event(window=window, mtype=self.atom["_NET_WM_DESKTOP"], data=[desktop])
        self._flush()

    def on_init(self, func: Callable[[], None]) -> Callable[[], None]:
        """
        Adds a function to the list of init handlers, every function on the list gets
        executed whenever orcsome3 is starting
        """
        self._init_handlers.append(func)
        return func

    def on_deinit(self, func: Callable[[], None]) -> Callable[[], None]:
        """
        Adds a function to the list of de-init handlers, every function on the list gets
        executed whenever orcsome3 is stopping
        """
        self._deinit_handlers.append(func)
        return func

    def get_screen_saver_info(self) -> Optional[wrappers.XScreenSaverInfo]:
        """
        This is a wrapper around `XScreenSaverQueryInfo`, returns information about the current state of the screen saver or `None` if there's no screensaver
        active.
        """
        xscreensaverinfo = xlib.get_screen_saver_info(display=self.dpy, drawable=self.root)
        if not xscreensaverinfo:
            return None
        return wrappers.XScreenSaverInfo(screensaverinfo=xscreensaverinfo)

    def reset_dpms(self) -> None:
        """
        Resets Display Power Management Signaling (DPMS)
        """
        power = xlib.ffi.new("unsigned short *")
        state = xlib.ffi.new("unsigned char *")
        if xlib.lib.DPMSInfo(self.dpy, power, state):
            if state[0]:
                xlib.lib.DPMSDisable(self.dpy)
                xlib.lib.DPMSEnable(self.dpy)

    def get_atom_name(self, atom: xlib.Atom) -> str:
        """
        Return the name associated with an atom
        """
        return xlib.get_atom_name(display=self.dpy, atom=atom)

    def _set_window_icon(self, window: xlib.Window, icon: str) -> None:
        xlib.lib.set_window_icon(self.dpy, window, xlib.ffi.new("char[]", icon.encode()))  # char[] is char*

    def _get_window_tree(
        self, window: wrappers.Window
    ) -> Optional[Tuple[wrappers.Window, wrappers.Window, List[wrappers.Window], int]]:
        root_window_ = xlib.ffi.new("Window *")
        parent_window_ = xlib.ffi.new("Window *")
        children_windows_ = xlib.ffi.new("Window **")
        number_of_children_ = xlib.ffi.new("unsigned int *")

        result: int = xlib.lib.XQueryTree(
            self.dpy, window, root_window_, parent_window_, children_windows_, number_of_children_
        )
        if not result:
            return None
        children_windows: List[wrappers.Window] = []
        for i in range(0, number_of_children_[0], 1):
            window_: wrappers.Window = self.create_window(window_id=children_windows_[0][i])
            children_windows.append(window_)
        return (
            self.create_window(window_id=root_window_[0]),
            self.create_window(window_id=parent_window_[0]),
            children_windows,
            number_of_children_[0],
        )


class ImmediateWM(WM):
    """
    ImmediateWM which allows to play with wm from repl.
    """

    def __init__(self) -> None:
        self.dpy: xlib.Display = xlib.lib.XOpenDisplay(xlib.ffi.NULL)
        if self.dpy == xlib.ffi.NULL:
            raise Exception("Can't open display")

        self.root: xlib.Window = xlib.lib.DefaultRootWindow(self.dpy)
        self.atom: xlib.AtomCache = xlib.AtomCache(dpy=self.dpy)


@xlib.ffi.def_extern()  # type: ignore
def error_handler(_display: xlib.Display, error: xlib.XErrorEvent) -> int:
    err: xlib.XErrorEvent_ = xlib.XErrorEvent_(error=error)
    logger.error(
        msg=f"{err.get_message()} ({err.request_code}:{err.minor_code}) ({'0x%0.2X' % int(err.resourceid)}:{int(err.resourceid)})"
    ) if not ignore_logger else None
    return 0
