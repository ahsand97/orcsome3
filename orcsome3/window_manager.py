from __future__ import annotations

import logging
from array import array
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Callable, NamedTuple, Optional, Union, cast, override

import orcsome3.libs.ev as ev
import orcsome3.libs.xlib as xlib
from orcsome3.aliases import KEYS as KEY_ALIASES
from orcsome3.utils import Singleton, match_string

# Globals
_logger: logging.Logger = logging.getLogger(name=__name__)
_ignore_logger: bool = False


class KeyboardModifiers(int, Enum):
    """Enum representation of keyboard modifiers. A modifier is a key associated with a keyboard modifier mask."""

    NoModifiers = xlib.KEY_MASKS.NoModifiers.value
    AnyModifier = xlib.KEY_MASKS.AnyModifier.value
    Alt = xlib.KEY_MASKS.Mod1Mask.value
    Meta = Alt
    Control = xlib.KEY_MASKS.ControlMask.value
    Ctrl = Control
    Shift = xlib.KEY_MASKS.ShiftMask.value
    Win = xlib.KEY_MASKS.Mod4Mask.value
    Windows = Win
    Hyper = Win
    Super = Win


# Ignored key masks
_IGNORED_KEY_MASKS: list[int] = [
    xlib.KEY_MASKS.NoModifiers.value,  # No modifiers
    xlib.KEY_MASKS.LockMask.value,  # Caps Lock
    xlib.KEY_MASKS.Mod2Mask.value,  # Num Lock
    xlib.KEY_MASKS.LockMask.value | xlib.KEY_MASKS.Mod2Mask.value,  # Caps Lock and Num Lock
]


class _RestartException(Exception):
    """Exception raised by method `WindowManager.restart()`"""

    pass


class WindowMatchers(NamedTuple):
    """
    Class representing matchers for a window. All attributes can be `None`

    Attrs:
    - `name`: Window name. The first part of `WM_CLASS` property.
    - `class_`: Window class. The second part of `WM_CLASS` property.
    - `role`: Window role. Value of `WM_WINDOW_ROLE` property.
    - `desktop`: Matches windows placed on specific desktop. Value of `_NET_WM_DESKTOP` property.
    - `title`: Window title. Value of `_NET_WM_NAME` property.
    - `window_type`: Window type/s. Value/s of `_NET_WM_WINDOW_TYPE` property.

    `name`, `cls`, `title`, `role` and the elements of `window_type` can be regular expressions.
    """

    name: Optional[str] = None
    class_: Optional[str] = None
    role: Optional[str] = None
    desktop: Optional[int] = None
    title: Optional[str] = None
    window_type: Optional[list[str]] = None

    def is_empty(self) -> bool:
        """Check if all attributes are `None`"""
        attrs: list[str] = ["name", "class_", "role", "desktop", "title", "window_type"]
        values: list[Any] = [getattr(self, x) for x in attrs]
        return all(value is None for value in values)


class KeyDefinition:
    """
    Class representing a key definition for a global hotkey. A Key definition consits in modifiers and a key.

    Attrs:
    - `modifiers`: Specifies the set of modifiers for the global hotkey.

        It can be an instance of `int` representing a valid value for a keymask bit or the value of the
         bitwise inclusive OR of valid keymask bits.

        Also, it can be a value from enum :class:`orcsome3.window_manager.KeyboardModifiers`
         or a list of values from same enum.

        For all possible modifiers combination use `orcsome3.window_manager.KeyboardModifiers.Any`.

    - `key`: Key for the global hotkey. See class :class:`orcsome3.window_manager.KeyDefinition.Key`


    More information about keyboard modifiers can be found using utility `xmodmap`.

    More information about keys, keycodes and keysyms cand be found using utility `xev`.
    """

    class Key:
        """
        Class representing a key. a Key can be represented by its keycode, keysym or name. Only one attribute is allowed.

        For all possible keys use keycode `orcsome3.xlib.CONSTANTS.KB.ANY_KEY`

        Attrs:
        - `name`: Key name. Valid names can be obtained from `X11/keysymdef.h` by removing the "XK_" prefix from each.
         Defaults to `None`.
        - `keycode`: KeyCode of key. Defaults to `None`.
        - `keysym`: KeySym of key. Defaults to `None`.
        """

        def __init__(
            self,
            name: Optional[str] = None,
            keycode: Optional[xlib.TYPES.Cython_KeyCode] = None,
            keysym: Optional[xlib.TYPES.Cython_KeySym] = None,
        ) -> None:
            self.name: Optional[str] = name
            self.keycode: Optional[Union[int, xlib.TYPES.Cython_KeyCode]] = keycode
            self.keysym: Optional[Union[int, xlib.TYPES.Cython_KeySym]] = keysym

            non_none_attrs: int = 0
            for attr in ["name", "keycode", "keysym"]:
                if getattr(self, attr) is not None:
                    non_none_attrs += 1
            if non_none_attrs == 0:
                raise Exception("Provide one attribute to create a Key object")
            elif non_none_attrs > 1:
                raise Exception("Only one attribute can be specified when creating a Key object")

            if self.name is not None and not len(self.name.strip()):
                raise Exception("Key name cannot be empty")

        def get_keycode(self) -> Optional[xlib.TYPES.Cython_KeyCode]:
            wm: WindowManager = WindowManager()
            if self.keycode is not None:
                return self.keycode
            if self.keysym is not None:
                return wm.get_keycode_from_string_or_keysym(key=self.keysym)
            if self.name is not None:
                if self.name.lower() == "any_key":
                    return xlib.CONSTANTS.KB.ANY_KEY
                return wm.get_keycode_from_string_or_keysym(key=self.name)
            return None

        @override
        def __repr__(self) -> str:
            return (
                f"{self.__class__.__name__}({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items() if not k.startswith('_')])})"
            )

    def __init__(self, modifiers: Union[int, KeyboardModifiers, list[KeyboardModifiers]], key: Key) -> None:
        self.modifiers: Union[int, KeyboardModifiers, list[KeyboardModifiers]] = modifiers
        self.key: KeyDefinition.Key = key

    @classmethod
    def new_from_string(cls, keydef: str) -> KeyDefinition:
        """Create a KeyDefinition from a string"""
        parts: list[str] = ["".join(x.split()) for x in keydef.split(sep="+") if len(x.strip())]
        modifiers: list[str] = parts[:-1]
        key: str = parts[-1]
        modifiers_for_key_definition: list[KeyboardModifiers] = []
        for modifier in modifiers:
            for keyboard_modifier in KeyboardModifiers:
                if modifier.lower() == keyboard_modifier.name.lower():
                    modifiers_for_key_definition.append(keyboard_modifier)
                    break
        return KeyDefinition(modifiers=modifiers_for_key_definition, key=KeyDefinition.Key(name=key))

    def get_modifiers_value(self) -> int:
        if isinstance(self.modifiers, int):
            return self.modifiers
        elif isinstance(self.modifiers, KeyboardModifiers):
            return self.modifiers.value
        else:
            new_modifier: int = KeyboardModifiers.NoModifiers.value
            if not len(self.modifiers):
                return new_modifier
            for modifier in self.modifiers:
                new_modifier |= modifier.value
            return new_modifier

    def get_modifiers_value_and_keycode(self) -> tuple[int, xlib.TYPES.Cython_KeyCode]:
        """Returns modifiers value and keycode for the key definition. Raise an exception if no keycode is found for attribute `key`."""

        modifiers_value: int = self.get_modifiers_value()
        keycode_of_key: Optional[xlib.TYPES.Cython_KeyCode] = self.key.get_keycode()
        if keycode_of_key is None:
            raise Exception(f"Error obtaining KeyCode for {self.key}")
        return modifiers_value, keycode_of_key

    @override
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items() if not k.startswith('_')])})"
        )


class WindowManager(metaclass=Singleton["WindowManager"]):
    """Core orcsome3 window manager instance

    Can be get in any time as::

        from orcsome3.window_manager import WindowManager

        wm: WindowManager = WindowManager()
    """

    def __init__(self, loop: Optional[ev.Loop] = None) -> None:
        # Track keyboard layout
        self.track_kbd_layout: bool = False

        # Denote orcsome3 startup
        self._startup: bool = False

        # Handlers of events
        self._event_handlers: dict[xlib.XEvent.EVENT_TYPES, Callable[[xlib.XEvent], None]] = {
            xlib.XEvent.EVENT_TYPES.KeyPress: self._key_press_event_handler,
            xlib.XEvent.EVENT_TYPES.KeyRelease: self._handle_keyrelease,
            xlib.XEvent.EVENT_TYPES.CreateNotify: self._handle_create,
            xlib.XEvent.EVENT_TYPES.DestroyNotify: self._handle_destroy,
            xlib.XEvent.EVENT_TYPES.FocusIn: self._handle_focus,
            xlib.XEvent.EVENT_TYPES.FocusOut: self._handle_focus,
            xlib.XEvent.EVENT_TYPES.PropertyNotify: self._handle_property,
        }

        # User handlers
        self._key_handlers: dict[
            Optional[WindowMatchers], dict[KeyDefinition, Callable[[Window, xlib.XKeyEvent], None]]
        ] = {}
        self._property_handlers: dict[
            xlib.TYPES.Cython_Atom, dict[Optional[xlib.TYPES.Cython_Window], list[Callable[[], None]]]
        ] = {}
        self._create_handlers: list[Callable[[], None]] = []
        self._destroy_handlers: dict[Optional[xlib.TYPES.Cython_Window], list[Callable[[], None]]] = {}
        self._init_handlers: list[Callable[[], None]] = []
        self._deinit_handlers: list[Callable[[], None]] = []
        self._timer_handlers: list[Callable[[], None]] = []
        self._restart_handler: Optional[Callable[[], None]] = None

        # History
        self.focus_history: list[xlib.TYPES.Cython_Window] = []

        # Auxiliar var to avoid destroy callback being called twice for the same window
        self._recently_destroyed_window: Optional[xlib.TYPES.Cython_Window] = None

        # X11 Display
        self.display: xlib.TYPES.Cython_Display = xlib.x_open_display()

        # Root window
        self.root: Window = Window(xlib.get_default_root_window(display=self.display))

        # Event loop
        if loop is not None:
            self._loop: ev.Loop = loop

            # Event watcher
            xevent_watcher: ev.IOWatcher = ev.IOWatcher.new(
                callback=self._xevent_cb,
                file_descriptor=xlib.get_connection_number(display=self.display),
                event=ev.IOWatcher.Events.EV_READ,
            )
            xevent_watcher.start(loop=self._loop)

        # Share self for all `wrappers.Window` instances
        Window.wm = self

    @property
    def current_window(self) -> Optional[Window]:
        """Current active (with input focus) window"""
        result: Optional[xlib.WindowProperty] = self.root.get_property(property_="_NET_ACTIVE_WINDOW")
        return None if result is None else Window(result.get_int_list()[0])

    @property
    def current_desktop(self) -> int:
        """Current desktop number. This is always an integer between 0 and `_NET_NUMBER_OF_DESKTOPS` - 1"""
        result: Optional[xlib.WindowProperty] = self.root.get_property(property_="_NET_CURRENT_DESKTOP")
        return cast(xlib.WindowProperty, result).get_int_list()[0]

    @property
    def wm_name(self) -> Optional[str]:
        """
        Actual window manager name or `None` if there's no ICCCM2.0-compliant window manager running.

        By the EWMH spec, a compliant window manager will set the `_NET_SUPPORTING_WM_CHECK` property on the root window to a window ID.

        If the `_NET_SUPPORTING_WM_CHECK` property exists and contains the ID of an existing window, then a ICCCM2.0-compliant window manager is running.

        If the property exists but does not contain the ID of an existing window, then a ICCCM2.0-compliant window manager exited without proper cleanup.

        If the property does not exist, then no ICCCM2.0-compliant window manager is running.
        """
        result: Optional[xlib.WindowProperty] = self.root.get_property(property_="_NET_SUPPORTING_WM_CHECK")
        if not result:
            return None
        result = Window(result.get_int_list()[0]).get_property(property_="_NET_WM_NAME")
        return None if not result else result.get_string_list()[0]

    # ------------------------------------------  DECORATORS  ------------------------------------------

    def on_key(
        self,
        key_definition: Union[str, KeyDefinition],
        window_matcher: Optional[WindowMatchers] = None,
        propagate_event: bool = False,
    ) -> Callable[[Callable[[Window, xlib.XKeyEvent], None]], Callable[[Window, xlib.XKeyEvent], None]]:
        """
        Signal decorator to define hotkey.

        `key_definition` parameter can be a string or an instance of the class `orcsome3.window_manager.KeyDefinition`
        containing the modifiers and keycode for the global hotkey.

        `window_matcher` parameter can be a `orcsome3.window_manager.WindowMatchers` instance representing matchers for a window,
        defaults to `None`. If provided, the hotkey will only be triggered if the window matches the matchers.
        If not provided, the hotkey will be triggered for any window.

        `propagate_event` parameter indicates if the event should be propagated to the event window, defaults to `False`.

        Signature of decorated function should be::

            from orcsome3.window_manager import Window
            from orcsome3.libs.xlib import XKeyEvent

            def function_cb(window: Window, event: XKeyEvent) -> None:
                # ... function's body

        You can define global hotkeys as follows::

            from orcsome3.libs.xlib import XKeyEvent
            from orcsome3.window_manager import KeyboardModifiers, KeyDefinition, Window, WindowManager

            wm: WindowManager = WindowManager()

            # Global hotkey to print "hotkey Control + a pressed" when Control + a is pressed
            @wm.on_key(key_definition=KeyDefinition(modifiers=KeyboardModifiers.Control, key=KeyDefinition.Key(name="a")))
            def test_hotkey(window: Window, event: XKeyEvent) -> None:
                print('hotkey Control + a pressed')

        Or keybinded to all the windows that matches the `orcsome3.window_manager.WindowMatchers`
        when the parameter `window_matcher` is provided::

            from orcsome3.libs.xlib import XKeyEvent
            from orcsome3.window_manager import KeyboardModifiers, KeyDefinition, Window, WindowManager, WindowMatchers

            wm: WindowManager = WindowManager()

            # Custom key to close all the windows that matches the class "URxvt" when Control + d is pressed
            @wm.on_key(
                key_definition=KeyDefinition(modifiers=KeyboardModifiers.Control, key=KeyDefinition.Key(name="d")),
                window_matcher=WindowMatchers(class_="URxvt"),
            )
            def close_urxvt_window(window: Window, event: XKeyEvent) -> None:
                window.close()

        Or using a string instead of a `orcsome3.window_manager.KeyDefinition` for the parameter `key_definition`::

            from orcsome3.libs.xlib import XKeyEvent
            from orcsome3.window_manager import KeyboardModifiers, KeyDefinition, Window, WindowManager

            wm: WindowManager = WindowManager()

            @wm.on_key(key_definition="Control + d")
            def change_window_desktop(window: Window, event: XKeyEvent) -> None:
                window.change_desktop(desktop=1)

        If a string is provided for the parameter `key_definition`, it must be in the format `modifiers+key`,
        where `modifiers` is a combination of modifiers and `key` is the key to be pressed.

        Modifiers can be:
        - `NoModifiers`
        - `AnyModifier`
        - `Control` or `Ctrl`
        - `Alt` or `Meta`
        - `Shift`
        - `Win` or `Windows` or `Hyper` or `Super`

        And keys can be a string with the key or the special string `ANY_KEY`, meaning any key.
        """

        def decorator_on_key(
            original_function: Callable[[Window, xlib.XKeyEvent], None],
        ) -> Callable[[Window, xlib.XKeyEvent], None]:
            @wraps(wrapped=original_function)
            def wrapper(window: Window, x_key_event: xlib.XKeyEvent) -> None:
                # Call the function
                original_function(window, x_key_event)

                # Propagate the event to the event window
                if not propagate_event:
                    return

                # Ungrab the key
                xlib.x_ungrab_key(
                    display=self.display,
                    keycode=x_key_event.keycode,
                    modifiers=x_key_event.state,
                    window=x_key_event.window,
                )

                # Send the event to the event window
                xlib.x_send_event(
                    display=self.display,
                    window=x_key_event.window,
                    propagate=False,
                    xevent=x_key_event,
                    event_masks=xlib.INPUT_EVENT_MASKS.KeyReleaseMask,
                )
                self.flush()

                # FALTA: Esta logica se debe mover a cuando llega el evento, mirar si hay match entre la ventana y el matcher
                # y posteriormente llamar a x_grab_key con los valores correctos
                # En el decorador solo se debe verificar que el key_definition sea valido y guardarlo en _key_handlers
                # Parse the key definition provided in the decorator
                """original_modifier_and_keycode: Optional[tuple[int, xlib.TYPES.Cython_KeyCode]] = None
                try:
                    original_modifier_and_keycode = (
                        self._parse_keydef_from_string(keydef=key_definition)
                        if isinstance(key_definition, str)
                        else self._parse_keydef_from_key_definition(keydef=key_definition)
                    )
                except Exception as e:
                    _logger.error(msg=f"Invalid key definition {key_definition}\n{e}")
                    return wrapper
                if original_modifier_and_keycode is None:
                    return wrapper
                for ignored_key_mask in _IGNORED_KEY_MASKS:
                    new_keydef: KeyDefinition = KeyDefinition(
                        modifiers=original_modifier_and_keycode[0] | ignored_key_mask,
                        key=KeyDefinition.Key(keycode=original_modifier_and_keycode[1]),
                    )
                    xlib.x_grab_key(
                        display=self.display,
                        window=window,
                        keycode=cast(xlib.TYPES.Cython_KeyCode, new_keydef.key.keycode),
                        modifiers=new_keydef.get_modifiers_value(),
                        owner_events=False,
                        pointer_mode=xlib.GRAB_MODE.GrabModeAsync,
                        keyboard_mode=xlib.GRAB_MODE.GrabModeAsync,
                    )
                    self._key_handlers.setdefault(window, {})[new_keydef] = wrapper"""

            try:
                nonlocal key_definition
                if isinstance(key_definition, str):
                    key_definition = KeyDefinition.new_from_string(keydef=key_definition)
                _ = key_definition.get_modifiers_value_and_keycode()
                self._key_handlers.setdefault(window_matcher, {})[key_definition] = wrapper
            except Exception as e:
                _logger.error(msg=f"Invalid key definition: {key_definition}.\n{e}")
            finally:
                if window_matcher is not None and window_matcher.is_empty():
                    _logger.error(msg="The window matcher provided is empty.")
                return wrapper

        return decorator_on_key

    '''def on_create(self, matcher: Optional[WindowMatchers] = None) -> Callable[[Callable[[], None]], Callable[[], None]]:
        """
        Signal decorator to handle window creation

        Signature of decorated function should be::

            function_cb() -> None:
                # ... function's body

        Can be used in two forms. Listen to any window creation::

            @wm.on_create()
            def on_create() -> None:
                print(wm.event_window.get_name_and_class())

        Or specific window::

            @wm.on_create(matcher=WindowMatchers(cls='Opera'))
            def use_firefox_luke() -> None:
                wm.event_window.close()
                subprocess.Popen(cmd=['firefox'])

        orcsome3 calls on_create handlers on its startup.

        See class `orcsome3.window_manager.WindowMatchers` for `matcher` argument description.
        """

        def decorator(function: Callable[[], None]) -> Callable[[], None]:
            _ = self.on_create_manage(ignore_startup=False, matcher=matcher)(function)
            return function

        return decorator

    def on_manage(self, matcher: Optional[WindowMatchers] = None) -> Callable[[Callable[[], None]], Callable[[], None]]:
        """
        Signal decorator to handle window creation (ignoring orcsome3 startup)

        Signature of decorated function should be::

            function_cb() -> None:
                # ... function's body

        Can be used in two forms. Listen to any window creation::

            @wm.on_manage()
            def on_manage() -> None:
                print(wm.event_window.get_name_and_class())

        Or specific window::

            @wm.on_manage(matcher=WindowMatchers(cls='Opera'))
            def use_firefox_luke():
                wm.event_window.close()
                subprocess.Popen(cmd=['firefox'])

        See class `orcsome3.window_manager.WindowMatchers` for `matcher` argument description.
        """

        def decorator(function: Callable[[], None]) -> Callable[[], None]:
            _ = self.on_create_manage(ignore_startup=True, matcher=matcher)(function)
            return function

        return decorator

    def on_create_manage(
        self, ignore_startup: bool, matcher: Optional[WindowMatchers] = None
    ) -> Callable[[Callable[[], None]], Callable[[], None]]:
        def decorator(function: Callable[[], None]) -> Callable[[], None]:
            @wraps(wrapped=function)
            def wrapper() -> None:
                if ignore_startup and self._startup:
                    return
                if matcher is None or self.event_window.matches(matcher=matcher):
                    function()

            def remove() -> None:
                try:
                    self._create_handlers.remove(wrapper)
                except Exception:
                    _logger.exception(msg="An exception occurred removing the function.")

            self._create_handlers.append(wrapper)
            setattr(wrapper, "remove", remove)
            return wrapper

        return decorator

    def on_destroy(self, window: Optional[Window] = None) -> Callable[[Callable[[], None]], Callable[[], None]]:
        """Signal decorator to handle window destroy

        Signature of decorated function should be::

            function_cb() -> None:
                # ... function's body

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
        trying to access any attribute or method on the window will result in an error
        cause this callback is executed when the window is clonsing/has closed.
        """

        def decorator(function: Callable[[], None]) -> Callable[[], None]:
            def remove() -> None:
                try:
                    self._destroy_handlers[window].remove(function)
                except Exception:
                    _logger.exception(msg="An exception occurred removing the function.")

            self._destroy_handlers.setdefault(window, []).append(function)
            setattr(function, "remove", remove)
            return function

        return decorator

    def on_property_change(
        self, property: str, window: Optional[Window] = None
    ) -> Callable[[Callable[[], None]], Callable[[], None]]:
        """Signal decorator to handle window property change

        Signature of decorated function should be::

            function_cb() -> None:
                # ... function's body

        One can handle any window property change::

            @wm.on_property_change(property='_NET_WM_STATE')
            def window_maximized_state_change() -> None:
                window: Window = wm.event_window
                if window.maximized_vert and window.maximized_horz:
                    print('The window is maximized now!')

        And specific window::

            @wm.on_manage()
            def switch_to_desktop() -> None:
                if wm.event_window.activate_desktop() is None:
                    # Created window has no any attached desktop so wait for it
                    @wm.on_property_change(window=wm.event_window, property='_NET_WM_DESKTOP')
                    def property_was_set() -> None:
                        wm.event_window.activate_desktop()
                        getattr('property_was_set', 'remove')() # removes the callback

        """

        def decorator(function: Callable[[], None]) -> Callable[[], None]:
            def remove() -> None:
                try:
                    self._property_handlers[self.atom_cache.get_atom(name=property)][window].remove(function)
                except Exception:
                    _logger.exception(msg="An exception occurred removing the function.")

            self._property_handlers.setdefault(self.atom_cache.get_atom(name=property), {}).setdefault(
                window, []
            ).append(function)
            setattr(function, "remove", remove)
            return function

        return decorator

    def on_timer(
        self, timeout: float, start: bool = True, first_timeout: Optional[float] = None
    ) -> Callable[[Callable[[], None]], Callable[[], None]]:
        def decorator(function: Callable[[], None]) -> Callable[[], None]:
            def callback_of_timer(
                __loop__: ev.TYPES.Cython_Loop, __watcher__: ev.TYPES.Cython_TimerWatcher, __events__: int
            ) -> None:
                timer.stop(loop=self._loop) if function() else timer.update_next_stop()

            self._timer_handlers.append(function)
            timer = ev.TimerWatcher(callback=callback_of_timer, after=first_timeout or timeout, repeat=timeout)
            setattr(function, "start", lambda: timer.start(loop=self._loop))
            setattr(function, "stop", lambda: timer.stop(loop=self._loop))
            setattr(function, "again", lambda: timer.again(loop=self._loop))
            setattr(function, "remaining", lambda: timer.remaining(loop=self._loop))
            setattr(function, "overdue", lambda timeout: timer.overdue(timeout=timeout))

            if start:
                getattr(function, "start")()

            def remove() -> None:
                try:
                    getattr(function, "stop")()
                    self._timer_handlers.remove(function)
                except Exception:
                    _logger.exception(msg="An exception occurred removing the function.")

            setattr(function, "remove", remove)
            return function

        return decorator'''

    # --------------------------------------------------------------------------------------------------

    def init(self) -> None:
        # Report all events within the root window
        xlib.x_select_input(
            display=self.display, window=self.root, event_mask=xlib.INPUT_EVENT_MASKS.SubstructureNotifyMask
        )

        for handler in self._init_handlers:
            handler()

        self._startup = True
        for window in self.get_clients():
            self._process_create_window(window=window)

        xlib.x_sync(display=self.display, discard=False)

        def default_error_handler(
            __display__: xlib.TYPES.Cython_Display, error: xlib.TYPES.EVENTS.Cython_XErrorEvent
        ) -> None:
            """Default callback for errors"""
            if not _ignore_logger:
                err: xlib.XErrorEvent = xlib.XErrorEvent(error_event=error)
                msg_resource: str = f"{'0x%0.2X' % int(err.resourceid)}:{int(err.resourceid)}"
                _logger.error(msg=f"{err.msg} ({msg_resource})")

        xlib.x_set_error_handler(handler=default_error_handler)

    def stop(self, exit: bool = False) -> None:
        self._key_handlers.clear()
        self._property_handlers.clear()
        self._create_handlers[:] = []
        self._destroy_handlers.clear()
        self.focus_history[:] = []

        if not exit:
            xlib.x_ungrab_key(
                display=self.display,
                keycode=xlib.CONSTANTS.KB.ANY_KEY,
                modifiers=xlib.KEY_MASKS.AnyModifier.value,
                window=self.root,
            )
            for window in self.get_clients():
                xlib.x_ungrab_key(
                    display=self.display,
                    keycode=xlib.CONSTANTS.KB.ANY_KEY,
                    modifiers=xlib.KEY_MASKS.AnyModifier.value,
                    window=window,
                )
        else:
            xlib.x_close_display(display=self.display)

        for handler in self._timer_handlers:
            try:
                getattr(handler, "stop")()
            except:
                _logger.exception(msg="Shutdown error")

        self._timer_handlers[:] = []

        for handler in self._deinit_handlers:
            try:
                handler()
            except:
                _logger.exception(msg="Shutdown error")

        self._init_handlers[:] = []
        self._deinit_handlers[:] = []

    def get_atom(self, name: str, create_if_not_exists: bool = False) -> xlib.TYPES.Cython_Atom:
        return xlib.x_get_atom_from_name(
            display=self.display, atom_name=name, create_if_not_exists=create_if_not_exists
        )

    def get_keycode_from_string_or_keysym(
        self, key: Union[str, xlib.TYPES.Cython_KeySym]
    ) -> Optional[xlib.TYPES.Cython_KeyCode]:
        """Get keycode for `key`"""
        keysym: xlib.TYPES.Cython_KeySym = xlib.CONSTANTS.KB.NO_SYMBOL
        if isinstance(key, str):
            keysym = xlib.x_string_to_keysym(string=KEY_ALIASES.get(key, key))
        else:
            keysym = key
        if keysym == xlib.CONSTANTS.KB.NO_SYMBOL:
            return None
        return xlib.x_keysym_to_keycode(display=self.display, keysym=keysym)

    def get_clients(self) -> list[Window]:
        """Return wm client list"""
        result: Optional[xlib.WindowProperty] = self.root.get_property(property_="_NET_CLIENT_LIST")
        return [] if result is None else [Window(x) for x in result.get_int_list()]

    def get_stacked_clients(self) -> list[Window]:
        """Return client list in stacked order.

        Most top window will be last in list. Can be useful to determine window visibility.
        """
        result: Optional[xlib.WindowProperty] = self.root.get_property(property_="_NET_CLIENT_LIST_STACKING")
        return [] if result is None else [Window(r) for r in result.get_int_list()]

    def send_event_to_x_server_to_root_window(
        self, window: int, message_type: str, format_: xlib.PROPERTY_FORMAT, data: Union[str, list[int]]
    ) -> None:
        """Send an event to the X server on the root window"""
        xlib.x_send_event(
            display=self.display,
            window=self.root,
            propagate=False,
            event_masks=xlib.INPUT_EVENT_MASKS.SubstructureRedirectMask,
            xevent=xlib.XClientMessageEvent(
                display=self.display,
                window=window,
                message_type=self.get_atom(name=message_type, create_if_not_exists=True),
                format_=format_,
                data=data,
                send_event=True,
            ),
        )

    def flush(self) -> None:
        xlib.x_flush(display=self.display)

    def find_clients(self, clients: list[Window], matcher: WindowMatchers) -> list[Window]:
        """
        Return matching clients list.

        - `clients`: Window list. It can be returned by methods `self.get_clients()` or `self.get_stacked_clients()`
        - `matcher`: Window Matcher. See class `orcsome3.window_manager.WindowMatchers` for description
        """
        return [x for x in clients if x.matches(matcher=matcher)]

    def find_client(self, clients: list[Window], matcher: WindowMatchers) -> Optional[Window]:
        """
        Return first matching client.

        - `clients`: Window list. It can be returned by methods `self.get_clients()` or `self.get_stacked_clients()`
        - `matcher`: Window Matcher. See class `orcsome3.window_manager.WindowMatchers` for description
        """
        result: list[Window] = self.find_clients(clients=clients, matcher=matcher)
        try:
            return result[0]
        except IndexError:
            return None

    def _process_create_window(self, window: Window) -> None:
        xlib.x_select_input(
            display=self.display,
            window=window,
            event_mask=[
                xlib.INPUT_EVENT_MASKS.StructureNotifyMask,
                xlib.INPUT_EVENT_MASKS.PropertyChangeMask,
                xlib.INPUT_EVENT_MASKS.FocusChangeMask,
                xlib.INPUT_EVENT_MASKS.KeyPressMask,
                xlib.INPUT_EVENT_MASKS.KeyReleaseMask,
            ],
        )
        for handler in self._create_handlers:
            handler()

    def _process_remove_window(self, window: xlib.TYPES.Cython_Window) -> None:
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

    def _key_press_event_handler(self, event: xlib.XEvent) -> None:
        xkeyevent: Optional[xlib.XKeyEvent] = cast(Optional[xlib.XKeyEvent], event.get_specific_event())
        if xkeyevent is None:
            return
        _logger.info(msg=xkeyevent)

        """if not xkeyevent.window in self._key_handlers:
            return"""

        """handler: Optional[Callable[[], None]] = None
        for key_definition in self._key_handlers[xkeyevent.window]:
            if key_definition.modifiers == xkeyevent.state and key_definition.key.keycode == xkeyevent.keycode:
                handler = self._key_handlers[xkeyevent.window][key_definition]
                break
        if handler is not None:
            handler()"""  # FALTA

    def _handle_keyrelease(self, event: xlib.XEvent) -> None:
        xkeyevent: Optional[xlib.XKeyEvent] = cast(Optional[xlib.XKeyEvent], event.get_specific_event())
        if xkeyevent is None:
            return
        _logger.info(msg=xkeyevent)

    def _handle_create(self, event: xlib.XEvent) -> None:
        xcreatewindowevent: Optional[xlib.XCreateWindowEvent] = cast(
            Optional[xlib.XCreateWindowEvent], event.get_specific_event()
        )
        if xcreatewindowevent is None:
            return
        _logger.info(msg=xcreatewindowevent)
        self._startup = False
        window: Window = Window(xcreatewindowevent.window)
        global _ignore_logger
        _ignore_logger = True
        if window.attributes is None:
            _ignore_logger = False
            return
        _ignore_logger = False
        self._process_create_window(window=window)

    def _handle_destroy(self, event: xlib.XEvent) -> None:
        xdestroywindowevent: Optional[xlib.XDestroyWindowEvent] = cast(
            Optional[xlib.XDestroyWindowEvent], event.get_specific_event()
        )
        if xdestroywindowevent is None:
            return
        _logger.info(msg=xdestroywindowevent)
        if xdestroywindowevent.window == self._recently_destroyed_window:
            return
        self._recently_destroyed_window = xdestroywindowevent.window

        handlers: list[Callable[[], None]] = []
        if None in self._destroy_handlers.keys():
            handlers.extend(self._destroy_handlers[None])
        if xdestroywindowevent.window in self._destroy_handlers.keys():
            handlers.extend(self._destroy_handlers[xdestroywindowevent.window])

        for handler in handlers:
            handler()
        self._process_remove_window(window=xdestroywindowevent.window)

    def _handle_property(self, event: xlib.XEvent) -> None:
        xpropertyevent: Optional[xlib.XPropertyEvent] = cast(Optional[xlib.XPropertyEvent], event.get_specific_event())
        if xpropertyevent is None:
            return
        atom: xlib.TYPES.Cython_Atom = xpropertyevent.atom
        if xpropertyevent.state == xlib.XPropertyEvent.STATE.PropertyNewValue and atom in self._property_handlers:
            wphandlers: dict[Optional[xlib.TYPES.Cython_Window], list[Callable[[], None]]] = self._property_handlers[
                atom
            ]
            if xpropertyevent.window in wphandlers:
                for handler in wphandlers[xpropertyevent.window]:
                    handler()

            if None in wphandlers:
                for handler in wphandlers[None]:
                    handler()

    def _handle_focus(self, event: xlib.XEvent) -> None:
        xfocuschangeevent: Optional[xlib.XFocusChangeEvent] = cast(
            Optional[xlib.XFocusChangeEvent], event.get_specific_event()
        )
        if xfocuschangeevent is None:
            return
        _logger.info(msg=xfocuschangeevent)
        if xfocuschangeevent.type == xlib.XEvent.EVENT_TYPES.FocusIn:
            try:
                self.focus_history.remove(xfocuschangeevent.window)
            except ValueError:
                pass

            self.focus_history.append(xfocuschangeevent.window)
            if (
                xfocuschangeevent.mode
                in (
                    xlib.XFocusChangeEvent.NOTIFY_MODE.NotifyNormal,
                    xlib.XFocusChangeEvent.NOTIFY_MODE.NotifyWhileGrabbed,
                )
                and self.track_kbd_layout
            ):
                prop: Optional[xlib.WindowProperty] = Window(xfocuschangeevent.window).get_property(
                    property_="_ORCSOME_KBD_GROUP"
                )
                if prop is not None:
                    _ = xlib.x_kb_lock_group(
                        display=self.display,
                        group=xlib.KEYSYM_GROUPS(prop.get_int_list()[0]) if prop else xlib.KEYSYM_GROUPS.XkbGroup1Index,
                    )
        else:
            if (
                xfocuschangeevent.mode
                in (
                    xlib.XFocusChangeEvent.NOTIFY_MODE.NotifyNormal,
                    xlib.XFocusChangeEvent.NOTIFY_MODE.NotifyWhileGrabbed,
                )
                and self.track_kbd_layout
            ):
                _ = Window(xfocuschangeevent.window).set_property(
                    property_name="_ORCSOME_KBD_GROUP",
                    type_="CARDINAL",
                    format_=xlib.PROPERTY_FORMAT.LONG,
                    property_data=array("l", [xlib.x_kb_get_state(display=self.display).group]),
                )

    def _xevent_cb(self, __loop__: ev.Loop, __watcher__: ev.IOWatcher, __revents__: int) -> None:
        while True:
            pending_events: int = xlib.x_pending(display=self.display)
            if not pending_events:
                break

            while pending_events > 0:
                event: xlib.XEvent = xlib.x_next_event(display=self.display)
                pending_events -= 1

                try:
                    handler: Callable[[xlib.XEvent], None] = self._event_handlers[event.type]
                except KeyError:
                    continue

                try:
                    handler(event)
                except _RestartException:
                    if self._restart_handler is not None:
                        self._restart_handler()
                        return
                except Exception as e:
                    _logger.exception(msg=e)

    def get_screen_size(self) -> Optional[xlib.XWindowGeometry]:
        """Get size of screen (root window)"""
        return self.root.get_geometry()

    def get_workarea(self, desktop: Optional[int] = None) -> list[int]:
        """
        Get workarea geometery.

        - `desktop`: Desktop for working area receiving. If `None` then `self.current_desktop` is used
        """
        result: Optional[xlib.WindowProperty] = self.root.get_property(property_="_NET_WORKAREA")
        if desktop is None:
            desktop = self.current_desktop
        if not desktop or not result:
            return []
        return result.get_int_list()[4 * desktop : 4 * desktop + 4]

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

    def get_screen_saver_info(self) -> Optional[xlib.XScreenSaverInfo]:
        """
        This is a wrapper around `XScreenSaverQueryInfo`, returns information about the current
        state of the screen saver or `None` if there's no screensaver active.
        """
        return xlib.x_get_screen_saver_info(display=self.display, drawable=self.root)

    def get_atom_name(self, atom: xlib.TYPES.Cython_Atom) -> Optional[str]:
        """Return the name associated with an atom"""
        return xlib.x_get_atom_name(display=self.display, atom=atom)

    def reset_dpms(self) -> None:
        """Reset Display Power Management Signaling (DPMS)"""
        xlib.reset_dpms(display=self.display)

    def activate_desktop(self, num: int) -> None:
        """Activate desktop `num`"""
        if num < 0:
            return

        self.send_event_to_x_server_to_root_window(
            window=self.root, message_type="_NET_CURRENT_DESKTOP", format_=xlib.PROPERTY_FORMAT.LONG, data=[num]
        )
        self.flush()

    def restart(self) -> None:
        """Restarts orcsome3"""
        raise _RestartException()

    def set_restart_handler(self, handler: Callable[[], None]) -> None:
        self._restart_handler = handler


class Window(int):
    """Class representation of a window"""

    _wm: Optional[WindowManager] = None

    def get_property(self, property_: str) -> Optional[xlib.WindowProperty]:
        """
        Returns the property for window.

        The result can be `None` if no property was found or an instance of `orcsome3.libs.xlib.WindowProperty`.

        Params:
        - `property_`: Property to get
        """
        return xlib.x_get_window_property(display=self.wm.display, window=self, property_=property_)

    def set_property(
        self,
        property_name: str,
        type_: str,
        format_: xlib.PROPERTY_FORMAT,
        property_data: array[int],
        mode: xlib.SET_PROPERTY_MODE = xlib.SET_PROPERTY_MODE.PropModeReplace,
    ) -> bool:
        """
        Alters a property of window or sets it if it doesn't exist.

        Params:
        - `property_name`: Name of the property.
        - `type_`: Name of the type of the property.
        - `format_`: Format of the property. See enum `orcsome3.libs.xlib.PROPERTY_FORMAT`.
        - `property_data`: Actual data of the property, it must be an array of char ('b'), short ('h') or long ('l').
        - `mode`: Mode of setting the data. Defaults to `xlib.SET_PROPERTY_MODE.PropModeReplace`.

        Returns `True` if the property was succesfully changed, `False` otherwise.
        """
        return xlib.x_change_window_property(
            display=self.wm.display,
            window_property=xlib.WindowProperty(
                window=self,
                property_name=property_name,
                type_=type_,
                atom_type=self.wm.get_atom(name=type_, create_if_not_exists=True),
                format_=format_,
                property_data=property_data,
            ),
            mode=mode,
        )

    def get_geometry(self) -> Optional[xlib.XWindowGeometry]:
        """Get geometry without decorations"""
        return xlib.x_get_window_geometry(display=self.wm.display, window=self)

    def get_tree(self) -> Optional[WindowTree]:
        """
        Get window tree of window, returns `None` if no tree was found.

        Returns a `orcsome3.wrappers.WindowTree` object containing info about the tree (root, parend and children windows).
        """
        x_window_tree: Optional[xlib.XWindowTree] = xlib.x_get_window_tree(display=self.wm.display, window=self)
        return None if x_window_tree is None else WindowTree.new_from_x_window_tree(x_window_tree=x_window_tree)

    def get_name_and_class(self) -> Optional[tuple[str, str]]:
        """Return `WM_CLASS` property"""
        result: Optional[xlib.WindowProperty] = self.get_property(property_="WM_CLASS")
        if result is None:
            return None
        try:
            result_list: list[str] = result.get_string_list()
            return result_list[0], result_list[1]
        except:
            return None

    def matches(self, matcher: WindowMatchers) -> bool:
        """
        Check if window suits given matchers defined in `matcher`. If `matcher` is empty `False` is returned.

        Params:
        - `matcher`: a `WindowMatchers` instance containing the desired matchers

        See class `orcsome3.window_manager.WindowMatchers` for description.
        """
        if matcher.is_empty():
            return False
        if matcher.name is not None and not match_string(pattern=matcher.name, string=self.name or ""):
            return False
        if matcher.class_ is not None and not match_string(pattern=matcher.class_, string=self.class_ or ""):
            return False
        if matcher.role is not None and not match_string(pattern=matcher.role, string=self.role or ""):
            return False
        if matcher.title is not None and not match_string(pattern=matcher.title, string=self.title or ""):
            return False
        if matcher.desktop is not None and matcher.desktop != self.desktop:
            return False
        if matcher.window_type is not None:
            if not len(matcher.window_type) or not self.type_:
                return False
            for desired_type in matcher.window_type:
                if not match_string(pattern=desired_type, string=self.type_):
                    return False
        return True

    def get_windows_same_pid(self) -> list[Window]:
        """This function returns a `List[Window]` that has the same pid of window"""
        if self.pid is None:
            return []

        windows_associated: list[Window] = []

        window_tree: Optional[WindowTree] = self.wm.root.get_tree()

        if window_tree is None or not len(window_tree.children):
            return []

        for window_child in window_tree.children:
            if window_child.pid == self.pid:
                windows_associated.append(window_child)

        return windows_associated

    def set_icon(self, icon: Union[Path, str]) -> bool:
        """This function set the icon for window, the maximum icon size is 10Mb"""
        if isinstance(icon, str):
            icon = Path(icon)
        if not icon.is_file():
            _logger.error(msg=f'The path "{icon}" is not a valid file')
            return False
        if icon.stat().st_size > (10 * 1000000):
            _logger.error(msg="The maximum icon size is 10Mb")
            return False
        return xlib.set_window_icon(display=self.wm.display, window=self, icon_path=icon)

    def focus(self) -> None:
        """Activate window"""
        self.wm.send_event_to_x_server_to_root_window(
            window=self,
            message_type="_NET_ACTIVE_WINDOW",
            format_=xlib.PROPERTY_FORMAT.LONG,
            data=[2, xlib.CONSTANTS.CURRENT_TIME],
        )
        self.wm.flush()

    def focus_and_raise(self) -> None:
        """Activate window desktop, set input focus and raise `self`"""
        _ = self.activate_desktop()
        xlib.x_configure_window(
            display=self.wm.display,
            window=self,
            value_mask=[xlib.WINDOW_VALUE_MASK.CWStackMode],
            window_changes=xlib.XWindowChanges(stack_mode=xlib.XWindowChanges.StackMode.Above),
        )
        self.wm.flush()
        self.focus()

    def place_above(self) -> None:
        """Float up window in wm stack"""
        xlib.x_configure_window(
            display=self.wm.display,
            window=self,
            value_mask=[xlib.WINDOW_VALUE_MASK.CWStackMode],
            window_changes=xlib.XWindowChanges(stack_mode=xlib.XWindowChanges.StackMode.Above),
        )
        self.wm.flush()

    def place_below(self) -> None:
        """Float down window in wm stack"""
        xlib.x_configure_window(
            display=self.wm.display,
            window=self,
            value_mask=[xlib.WINDOW_VALUE_MASK.CWStackMode],
            window_changes=xlib.XWindowChanges(stack_mode=xlib.XWindowChanges.StackMode.Below),
        )
        self.wm.flush()

    def _change_hidden_state(self, minimize: bool) -> None:
        self.wm.send_event_to_x_server_to_root_window(
            window=self,
            message_type="_NET_WM_STATE",
            format_=xlib.PROPERTY_FORMAT.LONG,
            data=[int(minimize), self.wm.get_atom(name="_NET_WM_STATE_HIDDEN")],
        )
        self.wm.flush()

    def minimize(self) -> None:
        """Minimize window"""
        self._change_hidden_state(minimize=True)

    def restore(self) -> None:
        """Restore window"""
        self._change_hidden_state(minimize=False)

    def activate_desktop(self) -> Optional[bool]:
        """
        Activate window desktop.

        Returns:

        - `True` if window is placed on different from current desktop (activates window's desktop)
        - `False` if window desktop and current desktop are the same
        - `None` if window does not have a desktop property
        """
        if self.desktop is not None:
            if self.wm.current_desktop != self.desktop:
                self.wm.activate_desktop(num=self.desktop)
                return True
            else:
                return False
        else:
            return None

    def set_state(
        self,
        taskbar: Optional[bool] = None,
        pager: Optional[bool] = None,
        decorate: Optional[bool] = None,
        otaskbar: Optional[bool] = None,
        vmax: Optional[bool] = None,
        hmax: Optional[bool] = None,
        fullscreen: Optional[bool] = None,
    ) -> None:
        """
        Set window state.

        Params:
        - `taskbar`: Indicates if the window is going to be included on the taskbar (`_NET_WM_STATE_SKIP_TASKBAR` property)
        - `pager`: Indicates if the window is going to be included on the Pager (`_NET_WM_STATE_SKIP_PAGER` property)
        - `decorate`: Indicates if the window is going to have decorations
        - `otaskbar`: Indicates if the window is going to be ignored by orcsome3
        - `vmax`: Indicates if the window is going to be maximized vertically (`_NET_WM_STATE_MAXIMIZED_VERT` property)
        - `hmax`: Indicates if the window is going to be maximized horizontally (`_NET_WM_STATE_MAXIMIZED_HORZ` property)
        - `fullscreen`: Indicates if the window is going to be fullscreen (`_NET_WM_STATE_FULLSCREEN` property)
        """
        state_property_name: str = "_NET_WM_STATE"

        if decorate is not None:
            if self.wm.wm_name is not None and self.wm.wm_name.lower() == "openbox":
                self.wm.send_event_to_x_server_to_root_window(
                    window=self,
                    message_type=state_property_name,
                    format_=xlib.PROPERTY_FORMAT.LONG,
                    data=[int(not decorate), self.wm.get_atom(name="_OB_WM_STATE_UNDECORATED")],
                )
            else:
                params: list[int] = []
                motif_hints: Optional[xlib.WindowProperty] = self.get_property(property_="_MOTIF_WM_HINTS")
                if motif_hints is not None and len(motif_hints.get_int_list()) == 5:
                    params = motif_hints.get_int_list()
                    params[2] = int(decorate)
                else:
                    # "0x2, 0x0, 0x0, 0x0, 0x0" to undecorate and "0x2, 0x0, 0x1, 0x0, 0x0" to redecorate
                    params = [2, 0, int(decorate), 0, 0]
                _ = self.set_property(
                    property_name="_MOTIF_WM_HINTS",
                    type_="_MOTIF_WM_HINTS",
                    format_=xlib.PROPERTY_FORMAT.LONG,
                    property_data=array("l", params),
                )

        if taskbar is not None:
            self.wm.send_event_to_x_server_to_root_window(
                window=self,
                message_type=state_property_name,
                format_=xlib.PROPERTY_FORMAT.LONG,
                data=[int(not taskbar), self.wm.get_atom(name="_NET_WM_STATE_SKIP_TASKBAR")],
            )

        if vmax is not None:
            self.wm.send_event_to_x_server_to_root_window(
                window=self,
                message_type=state_property_name,
                format_=xlib.PROPERTY_FORMAT.LONG,
                data=[int(vmax), self.wm.get_atom(name="_NET_WM_STATE_MAXIMIZED_VERT")],
            )

        if hmax is not None:
            self.wm.send_event_to_x_server_to_root_window(
                window=self,
                message_type=state_property_name,
                format_=xlib.PROPERTY_FORMAT.LONG,
                data=[int(hmax), self.wm.get_atom(name="_NET_WM_STATE_MAXIMIZED_HORZ")],
            )

        if fullscreen is not None:
            self.wm.send_event_to_x_server_to_root_window(
                window=self,
                message_type=state_property_name,
                format_=xlib.PROPERTY_FORMAT.LONG,
                data=[int(fullscreen), self.wm.get_atom(name="_NET_WM_STATE_FULLSCREEN")],
            )

        if otaskbar is not None:
            arr: array[int] = array("l", [] if otaskbar else [self.wm.get_atom(name="_ORCSOME_SKIP_TASKBAR")])
            _ = self.set_property(
                property_name="_ORCSOME_STATE", type_="ATOM", format_=xlib.PROPERTY_FORMAT.LONG, property_data=arr
            )

        if pager is not None:
            self.wm.send_event_to_x_server_to_root_window(
                window=self,
                message_type=state_property_name,
                format_=xlib.PROPERTY_FORMAT.LONG,
                data=[int(not pager), self.wm.get_atom(name="_NET_WM_STATE_SKIP_PAGER")],
            )

        self.wm.flush()

    def move_resize(
        self, x: Optional[int] = None, y: Optional[int] = None, w: Optional[int] = None, h: Optional[int] = None
    ) -> None:
        """Change `window` geometry"""

        flags: int = 0
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
        o_x, o_y, _, _ = tuple(self.wm.get_workarea())
        params: list[int] = [
            flags,
            (0 if x == None else x) + o_x,
            (0 if y == None else y) + o_y,
            max(1, (0 if w == None else w)),
            max(1, (0 if h == None else h)),
        ]
        self.wm.send_event_to_x_server_to_root_window(
            window=self, message_type="_NET_MOVERESIZE_WINDOW", format_=xlib.PROPERTY_FORMAT.LONG, data=params
        )
        self.wm.flush()

    def move_resize2(self, left: int, top: int, right: int, bottom: int) -> None:
        """Change window geometry"""
        flags = 0x2F00
        # Workarea offsets
        dl, dt, dw, dh = tuple(self.wm.get_workarea(desktop=self.desktop))
        params: list[int] = [flags, left + dl, top + dt, max(1, dw - right - left), max(1, dh - bottom - top)]
        self.wm.send_event_to_x_server_to_root_window(
            window=self, message_type="_NET_MOVERESIZE_WINDOW", format_=xlib.PROPERTY_FORMAT.LONG, data=params
        )
        self.wm.flush()

    def close(self) -> None:
        """Send request to wm to close window"""
        self.wm.send_event_to_x_server_to_root_window(
            window=self,
            message_type="_NET_CLOSE_WINDOW",
            format_=xlib.PROPERTY_FORMAT.LONG,
            data=[xlib.CONSTANTS.CURRENT_TIME],
        )
        self.wm.flush()

    def change_desktop(self, desktop: int) -> None:
        """Move window to `desktop`"""
        if desktop < 0:
            return
        self.wm.send_event_to_x_server_to_root_window(
            window=self, message_type="_NET_WM_DESKTOP", format_=xlib.PROPERTY_FORMAT.LONG, data=[desktop]
        )
        self.wm.flush()

    @property
    def wm(self) -> WindowManager:
        return cast(WindowManager, self._wm)

    @classmethod
    @wm.setter
    def wm(cls, window_manager: WindowManager) -> None:
        cls._wm = window_manager

    @property
    def desktop(self) -> Optional[int]:
        """
        Return window desktop (`_NET_WM_DESKTOP` property). The result can be:

        - Number from 0 to desktop_count - 1
        - -1 if window placed on all desktops
        - `None` if window does not have desktop property
        """
        result: Optional[xlib.WindowProperty] = self.get_property(property_="_NET_WM_DESKTOP")
        if result is None:
            return None
        try:
            desktop: int = result.get_int_list()[0]
            if desktop == 0xFFFFFFF or desktop == 0xFFFFFFFFFFFFFFFF:
                desktop = -1
            return desktop
        except:
            return None

    @property
    def role(self) -> Optional[str]:
        """Return `WM_WINDOW_ROLE` property"""
        result: Optional[xlib.WindowProperty] = self.get_property(property_="WM_WINDOW_ROLE")
        if result is None:
            return None
        try:
            return result.get_string_list()[0]
        except:
            return None

    @property
    def name(self) -> Optional[str]:
        """Return first part from `WM_CLASS` property"""
        result: Optional[xlib.WindowProperty] = self.get_property(property_="WM_CLASS")
        if result is None:
            return None
        try:
            result_list: list[str] = result.get_string_list()
            return result_list[0]
        except:
            return None

    @property
    def class_(self) -> Optional[str]:
        """Return second part from `WM_CLASS` property"""
        result: Optional[xlib.WindowProperty] = self.get_property(property_="WM_CLASS")
        if result is None:
            return None
        try:
            result_list: list[str] = result.get_string_list()
            return result_list[1]
        except:
            return None

    @property
    def title(self) -> Optional[str]:
        """Return `_NET_WM_NAME` property"""
        result: Optional[xlib.WindowProperty] = self.get_property(property_="_NET_WM_NAME")
        if result is None:
            return None
        try:
            return result.get_string_list()[0]
        except:
            return None

    @property
    def attributes(self) -> Optional[WindowAttributes]:
        """Get current attributes for window"""
        attrs: Optional[xlib.XWindowAttributes] = xlib.x_get_window_attributes(display=self.wm.display, window=self)
        return None if attrs is None else WindowAttributes(window=self, root=self.wm.root, xwindowattributes=attrs)

    @property
    def state(self) -> Optional[list[str]]:
        """Return `_NET_WM_STATE` property"""
        states: Optional[xlib.WindowProperty] = self.get_property(property_="_NET_WM_STATE")
        if states is None or not len(states.property_data):
            return None
        try:
            states_: list[str] = []
            for state in states.get_int_list():
                state_atom_name: Optional[str] = self.wm.get_atom_name(atom=state)
                if state_atom_name is None:
                    continue
                states_.append(state_atom_name)
            return states_
        except:
            return None

    @property
    def maximized_vert(self) -> bool:
        """Check if atom `_NET_WM_STATE_MAXIMIZED_VERT` is present in window state"""
        return "_NET_WM_STATE_MAXIMIZED_VERT" in self.state if self.state is not None else False

    @property
    def maximized_horz(self) -> bool:
        """Check if atom `_NET_WM_STATE_MAXIMIZED_HORZ` is present in window state"""
        return "_NET_WM_STATE_MAXIMIZED_HORZ" in self.state if self.state is not None else False

    @property
    def decorated(self) -> bool:
        """
        Return `False` if window is not decorated otherwise `True`

        window is considered non-decorated when:
        - There's no window manager running
        - It has the attribute override-redirect in its window attributes
        - It has a 0 on the third bit in the property `_MOTIF_WM_HINTS` if the property is present
        """
        decorated: bool = True
        if self.wm.wm_name is None:  # If the window manager is not running window can't be decorated
            decorated = False
        else:
            # If the window has the attribute override-redirect it can't be decorated
            if self.attributes is not None and self.attributes.override_redirect:
                decorated = False
            # If the window manager running is Openbox then it checks if window has the state '_OB_WM_STATE_UNDECORATED'
            elif self.wm.wm_name == "Openbox":
                if self.state is not None and "_OB_WM_STATE_UNDECORATED" in self.state:
                    decorated = False
            # If the window manager is not Openbox then it looks for the third bit on the property '_MOTIF_WM_HINTS'
            # to determine the decorations
            else:
                """
                {
                    int     flags;
                    int     functions;
                    int     decorations;
                    int     input_mode;
                    int     status;
                } MotifWmHints;
                """
                motif_hints: Optional[xlib.WindowProperty] = self.get_property(property_="_MOTIF_WM_HINTS")
                # If the decorations bit in the _MOTIF_WM_HINTS (position 2) is 0 then we can assume the window is not decorated
                try:
                    if motif_hints is not None and motif_hints.get_int_list()[2] == 0:
                        decorated = False
                except:
                    pass
        return decorated

    @property
    def urgent(self) -> bool:
        """Check if atom `_NET_WM_STATE_DEMANDS_ATTENTION` is present in window state"""
        return "_NET_WM_STATE_DEMANDS_ATTENTION" in self.state if self.state is not None else False

    @property
    def fullscreen(self) -> bool:
        """Check if atom `_NET_WM_STATE_FULLSCREEN` is present in window state"""
        return "_NET_WM_STATE_FULLSCREEN" in self.state if self.state is not None else False

    @property
    def pid(self) -> Optional[int]:
        """Return `_NET_WM_PID` property"""
        result: Optional[xlib.WindowProperty] = self.get_property(property_="_NET_WM_PID")
        if result is None:
            return None
        try:
            return result.get_int_list()[0]
        except:
            return None

    @property
    def type_(self) -> Optional[str]:
        """Return `_NET_WM_WINDOW_TYPE` property"""
        window_type: Optional[xlib.WindowProperty] = self.get_property(property_="_NET_WM_WINDOW_TYPE")
        if window_type is None:
            return None
        try:
            return self.wm.get_atom_name(atom=window_type.get_int_list()[0])
        except:
            return None


class WindowTree(NamedTuple):
    """
    Class representation of a window tree.

    Attrs:
    - `window`: Window
    - `root`: Root window
    - `parent`: Parent window
    - `children`: Children windows
    """

    window: Window
    root: Window
    parent: Window
    children: list[Window]

    @classmethod
    def new_from_x_window_tree(cls, x_window_tree: xlib.XWindowTree) -> WindowTree:
        return cls(
            window=Window(x_window_tree.window),
            root=Window(x_window_tree.root),
            parent=Window(x_window_tree.parent),
            children=[Window(x) for x in x_window_tree.children],
        )


class WindowAttributes:
    """
    Class representation of window attributes.

    Attrs:
    - `window`: Window
    - `root`: Root window
    - `x`: Location of window
    - `y`: Location of window
    - `width`: Width of window
    - `height`: Height of window
    - `border_width`: Border width of window
    - `depth`: Depth of window
    - `override_redirect`: The override-redirect flag specifies whether map and configure requests on this window
                           should override a SubstructureRedirectMask on the parent
    - `map_state`: Map state. See enum `orcsome3.xlib.XWindowAttributes.MapState`
    """

    def __init__(self, window: Window, root: Window, xwindowattributes: xlib.XWindowAttributes) -> None:
        self.window: Window = window
        self.root: Window = root
        self.x: int = xwindowattributes.x
        self.y: int = xwindowattributes.y
        self.width: int = xwindowattributes.width
        self.height: int = xwindowattributes.width
        self.border_width: int = xwindowattributes.border_width
        self.depth: int = xwindowattributes.depth
        self.override_redirect: bool = xwindowattributes.override_redirect
        self.map_state: xlib.XWindowAttributes.MapState = xwindowattributes.map_state
