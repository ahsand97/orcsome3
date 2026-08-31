"""Window manager singleton, Window objects, and config.py signal decorators (`on_key`, `on_create`, `on_focus`, …).

`KeyboardModifiers`, `WindowMatchers`, and `KeyDefinition` live in `orcsome3.keys` and are re-exported here.
"""

from __future__ import annotations

import logging
from array import array
from functools import wraps
from pathlib import Path
from typing import Callable, NamedTuple, Optional, TypeVar, Union, cast

from typing_extensions import TypeAlias, final

import orcsome3.libs.ev as ev
import orcsome3.libs.xlib as xlib
from orcsome3.keys import KeyboardModifiers as KeyboardModifiers
from orcsome3.keys import KeyDefinition as KeyDefinition
from orcsome3.keys import WindowMatchers as WindowMatchers
from orcsome3.keys import keycode_from_string_or_keysym
from orcsome3.utils import SingletonMixin, match_string

# Globals
_logger: logging.Logger = logging.getLogger(name=__name__)
_ignore_logger: bool = False

_KeyHandler: TypeAlias = Callable[[xlib.TYPES.Cython_Window, xlib.XKeyEvent], None]
_ButtonHandler: TypeAlias = Callable[[xlib.TYPES.Cython_Window, xlib.XButtonEvent], None]
_ClientMessageHandler: TypeAlias = Callable[[xlib.TYPES.Cython_Window, xlib.XClientMessageEvent], None]
_PropertyHandler: TypeAlias = Callable[[xlib.TYPES.Cython_Window, xlib.XPropertyEvent], None]
# Window isn't defined yet at module scope here, and the wrapper's own (Window, event) signature
# is concrete rather than a passthrough TypeVar (unlike on_property_change) — a precisely-typed
# alias would need a forward reference, so this stays as loose as _WindowEventCbs's value type.
_CreateHandler: TypeAlias = Callable[..., None]
_CbNone = TypeVar("_CbNone", bound=Callable[[], None])
_CbKey = TypeVar("_CbKey", bound=Callable[..., None])
_CbButton = TypeVar("_CbButton", bound=Callable[..., None])
_CbClient = TypeVar("_CbClient", bound=Callable[..., None])
_CbStruct = TypeVar("_CbStruct", bound=Callable[..., None])
_CbTimer = TypeVar("_CbTimer", bound=Callable[[], Optional[bool]])
_WindowEventCbs: TypeAlias = dict[Optional[xlib.TYPES.Cython_Window], list[Callable[..., None]]]
# [press, release]; one XGrabKey is shared when both on_key and on_key_release bind the same combo
_KeyGrabSlots: TypeAlias = list[Optional[_KeyHandler]]

# ButtonPress.state includes other buttons held; strip those so Control+Button1 still matches.
_BUTTON_STATE_MASK: int = (
    xlib.BUTTON_MASKS.Button1Mask.value
    | xlib.BUTTON_MASKS.Button2Mask.value
    | xlib.BUTTON_MASKS.Button3Mask.value
    | xlib.BUTTON_MASKS.Button4Mask.value
    | xlib.BUTTON_MASKS.Button5Mask.value
)


def _modifiers_mask(modifiers: Union[int, KeyboardModifiers, list[KeyboardModifiers]]) -> int:
    """OR modifier masks. A `KeyboardModifiers` member is an `int` subclass, so `int(member)` is the X mask."""
    if isinstance(modifiers, list):
        mask: int = KeyboardModifiers.NoModifiers.value
        for modifier in modifiers:
            mask |= int(modifier)
        return mask
    return int(modifiers)


# CapsLock (Lock) and NumLock (Mod2) must be grabbed too or hotkeys miss when those locks are on.
IGNORED_KEY_MASKS: list[int] = [
    xlib.KEY_MASKS.NoModifiers.value,
    xlib.KEY_MASKS.LockMask.value,
    xlib.KEY_MASKS.Mod2Mask.value,
    xlib.KEY_MASKS.LockMask.value | xlib.KEY_MASKS.Mod2Mask.value,
]


class AtomCache:
    """Name ↔ Atom cache for the connected display (avoids repeated `XInternAtom` / `XGetAtomName`)."""

    _wm: WindowManager

    def __init__(self, wm: WindowManager) -> None:
        self._wm = wm
        self._cache: dict[str, xlib.TYPES.Cython_Atom] = {}
        self._names: dict[xlib.TYPES.Cython_Atom, str] = {}

    def get_atom(self, name: str, create_if_not_exists: bool = False) -> xlib.TYPES.Cython_Atom:
        """Return the interned atom for `name`, creating it on first miss when `create_if_not_exists`."""
        atom: Optional[xlib.TYPES.Cython_Atom] = self._cache.get(name)
        if atom is None:
            atom = xlib.x_get_atom_from_name(
                display=self._wm.display, atom_name=name, create_if_not_exists=create_if_not_exists
            )
            if atom:
                self._cache[name] = atom
                self._names[atom] = name
        return atom

    def get_name(self, atom: xlib.TYPES.Cython_Atom) -> Optional[str]:
        """Return the name for `atom`, or `None` if the server has no name for it."""
        name: Optional[str] = self._names.get(atom)
        if name is None:
            name = xlib.x_get_atom_name(display=self._wm.display, atom=atom)
            if name:
                self._names[atom] = name
                _ = self._cache.setdefault(name, atom)
        return name


class _RestartException(Exception):
    """Exception raised by method `WindowManager.restart()`"""

    pass


@final
class WindowManager(SingletonMixin):
    """Core orcsome3 window-manager instance (one per process).

    After `orcsome3` has started, get it from anywhere as::

        from orcsome3 import get_wm

        wm: WindowManager = get_wm()

    `WindowManager()` returns the same singleton once it has been constructed with an event loop.

    Attrs:
    - `display`: Connected X display
    - `root`: Root window of that display
    - `atom_cache`: Interned-atom cache for this display
    - `focus_history`: X window ids that received FocusIn, oldest first
    - `track_kbd_layout`: If True, key grabs also lock the keyboard group (see `_handle_focus`)
    """

    def __init__(self, loop: Optional[ev.Loop] = None) -> None:
        """Connect to X, wrap the root window, and (if `loop` is given) watch the display fd for events."""
        if type(self)._singleton_init_done():
            return
        self.track_kbd_layout: bool = False
        self._event_handlers: dict[xlib.XEvent.EVENT_TYPES, Callable[[xlib.XEvent], None]] = {
            xlib.XEvent.EVENT_TYPES.KeyPress: self._key_press_event_handler,
            xlib.XEvent.EVENT_TYPES.KeyRelease: self._handle_keyrelease,
            xlib.XEvent.EVENT_TYPES.ButtonPress: self._handle_button,
            xlib.XEvent.EVENT_TYPES.CreateNotify: self._handle_create,
            xlib.XEvent.EVENT_TYPES.DestroyNotify: self._handle_destroy,
            xlib.XEvent.EVENT_TYPES.MapNotify: self._handle_map,
            xlib.XEvent.EVENT_TYPES.UnmapNotify: self._handle_unmap,
            xlib.XEvent.EVENT_TYPES.ConfigureNotify: self._handle_configure,
            xlib.XEvent.EVENT_TYPES.FocusIn: self._handle_focus,
            xlib.XEvent.EVENT_TYPES.FocusOut: self._handle_focus,
            xlib.XEvent.EVENT_TYPES.PropertyNotify: self._handle_property,
            xlib.XEvent.EVENT_TYPES.ClientMessage: self._handle_client_message,
        }
        self._restart_handler: Optional[Callable[[], None]] = None
        self.focus_history: list[xlib.TYPES.Cython_Window] = []
        self._focus_ids: set[xlib.TYPES.Cython_Window] = set()
        self._recently_destroyed_window: Optional[xlib.TYPES.Cython_Window] = None
        self.display: xlib.TYPES.Cython_Display = xlib.x_open_display()
        self.root: Window = Window(xlib.get_default_root_window(display=self.display))
        self._loop: Optional[ev.Loop] = loop
        self._xevent_watcher: Optional[ev.IOWatcher] = None
        self.atom_cache: AtomCache = AtomCache(wm=self)
        self._wm_name: Optional[str] = None
        self._wm_name_loaded: bool = False
        self._startup: bool = False
        self._inited: bool = False
        self._key_handlers: dict[Optional[WindowMatchers], dict[KeyDefinition, _KeyHandler]] = {}
        self._key_release_handlers: dict[Optional[WindowMatchers], dict[KeyDefinition, _KeyHandler]] = {}
        self._key_grabs: dict[xlib.TYPES.Cython_Window, dict[tuple[int, xlib.TYPES.Cython_KeyCode], _KeyGrabSlots]] = {}
        self._button_handlers: dict[Optional[WindowMatchers], dict[tuple[int, int], _ButtonHandler]] = {}
        self._button_grabs: dict[xlib.TYPES.Cython_Window, dict[tuple[int, int], _ButtonHandler]] = {}
        self._create_handlers: list[_CreateHandler] = []
        self._destroy_handlers: _WindowEventCbs = {}
        self._focus_handlers: _WindowEventCbs = {}
        self._unfocus_handlers: _WindowEventCbs = {}
        self._map_handlers: _WindowEventCbs = {}
        self._unmap_handlers: _WindowEventCbs = {}
        self._configure_handlers: _WindowEventCbs = {}
        self._property_handlers: dict[
            xlib.TYPES.Cython_Atom, dict[Optional[xlib.TYPES.Cython_Window], list[_PropertyHandler]]
        ] = {}
        self._client_message_handlers: dict[
            xlib.TYPES.Cython_Atom, dict[Optional[xlib.TYPES.Cython_Window], list[_ClientMessageHandler]]
        ] = {}
        self._timer_handlers: list[Callable[[], Optional[bool]]] = []
        self._init_handlers: list[Callable[[], None]] = []
        self._deinit_handlers: list[Callable[[], None]] = []
        self._event_window: Optional[Window] = None
        if loop is not None:
            # Must stay alive for the life of the instance: __dealloc__ frees the underlying
            # ev_io C struct, and libev keeps a pointer to it after start() (use-after-free
            # crash in fd_reify otherwise, once the loop actually runs).
            self._xevent_watcher = ev.IOWatcher.new(
                callback=self._xevent_cb,
                file_descriptor=xlib.get_connection_number(display=self.display),
                event=ev.IOWatcher.Events.EV_READ,
            )
            self._xevent_watcher.start(loop=loop)
        Window.set_wm(self)

    @property
    def event_window(self) -> Window:
        """Window associated with the current event (create, destroy, property, key, map, focus, …)."""
        return cast(Window, self._event_window)

    @property
    def startup(self) -> bool:
        """True while orcsome3 is processing existing clients at startup."""
        return self._startup

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
        if self._wm_name_loaded:
            return self._wm_name
        result: Optional[xlib.WindowProperty] = self.root.get_property(property_="_NET_SUPPORTING_WM_CHECK")
        if not result:
            self._wm_name = None
        else:
            name_prop: Optional[xlib.WindowProperty] = Window(result.get_int_list()[0]).get_property(
                property_="_NET_WM_NAME"
            )
            self._wm_name = None if not name_prop else name_prop.get_string_list()[0]
        self._wm_name_loaded = True
        return self._wm_name

    # ------------------------------------------  DECORATORS  ------------------------------------------
    def _grab_key_binding(
        self,
        window: xlib.TYPES.Cython_Window,
        key_definition: KeyDefinition,
        handler: _KeyHandler,
        *,
        release: bool = False,
    ) -> None:
        """XGrabKey on `window` for the binding, once per CapsLock/NumLock combination in `IGNORED_KEY_MASKS`."""
        modifiers_value, keycode = key_definition.get_modifiers_value_and_keycode(display=self.display)
        slot: int = 1 if release else 0
        for ignored_key_mask in IGNORED_KEY_MASKS:
            mask: int = modifiers_value | ignored_key_mask
            xlib.x_grab_key(
                display=self.display,
                window=window,
                keycode=keycode,
                modifiers=mask,
                owner_events=False,
                pointer_mode=xlib.GRAB_MODE.GrabModeAsync,
                keyboard_mode=xlib.GRAB_MODE.GrabModeAsync,
            )
            slots: _KeyGrabSlots = self._key_grabs.setdefault(window, {}).setdefault((mask, keycode), [None, None])
            slots[slot] = handler

    def _x_ungrab_key_binding(self, window: xlib.TYPES.Cython_Window, key_definition: KeyDefinition) -> None:
        """XUngrabKey for the CapsLock/NumLock variants. Does not touch `_key_grabs` (press/release share the grab)."""
        modifiers_value, keycode = key_definition.get_modifiers_value_and_keycode(display=self.display)
        for ignored_key_mask in IGNORED_KEY_MASKS:
            mask: int = modifiers_value | ignored_key_mask
            xlib.x_ungrab_key(display=self.display, keycode=keycode, modifiers=mask, window=window)

    def _x_grab_key_binding(self, window: xlib.TYPES.Cython_Window, key_definition: KeyDefinition) -> None:
        """XGrabKey for the CapsLock/NumLock variants. Does not touch `_key_grabs`."""
        modifiers_value, keycode = key_definition.get_modifiers_value_and_keycode(display=self.display)
        for ignored_key_mask in IGNORED_KEY_MASKS:
            mask: int = modifiers_value | ignored_key_mask
            xlib.x_grab_key(
                display=self.display,
                window=window,
                keycode=keycode,
                modifiers=mask,
                owner_events=False,
                pointer_mode=xlib.GRAB_MODE.GrabModeAsync,
                keyboard_mode=xlib.GRAB_MODE.GrabModeAsync,
            )

    def _ungrab_handler(self, handler: _KeyHandler) -> None:
        """Drop every X grab whose callback is `handler` (window ids are reused by the server)."""
        for window, grabs in list(self._key_grabs.items()):
            for (mask, keycode), slots in list(grabs.items()):
                if slots[0] is handler:
                    slots[0] = None
                if slots[1] is handler:
                    slots[1] = None
                if slots[0] is not None or slots[1] is not None:
                    continue
                xlib.x_ungrab_key(display=self.display, keycode=keycode, modifiers=mask, window=window)
                del grabs[(mask, keycode)]
            if not grabs:
                del self._key_grabs[window]

    def _install_key_binding(
        self,
        window_matcher: Optional[WindowMatchers],
        key_definition: KeyDefinition,
        handler: _KeyHandler,
        *,
        release: bool = False,
    ) -> None:
        """Grab now: root if `window_matcher` is None, otherwise every matching mapped client."""
        if window_matcher is None:
            self._grab_key_binding(window=self.root, key_definition=key_definition, handler=handler, release=release)
            return
        for client in self.get_clients():
            if client.matches(matcher=window_matcher):
                self._grab_key_binding(window=client, key_definition=key_definition, handler=handler, release=release)

    def _propagate_grabbed_key(self, key_definition: KeyDefinition, x_key_event: xlib.XKeyEvent) -> None:
        """Temporarily ungrab so the key event can reach the focused client (or the grabbed window), then re-grab."""
        grab_window: xlib.TYPES.Cython_Window = x_key_event.window
        self._x_ungrab_key_binding(window=grab_window, key_definition=key_definition)
        target: xlib.TYPES.Cython_Window = grab_window
        if grab_window == self.root:
            focused: Optional[Window] = self.current_window
            if focused is not None:
                target = focused
        event_mask: xlib.INPUT_EVENT_MASKS = (
            xlib.INPUT_EVENT_MASKS.KeyReleaseMask
            if x_key_event.type == xlib.XEvent.EVENT_TYPES.KeyRelease
            else xlib.INPUT_EVENT_MASKS.KeyPressMask
        )
        xlib.x_send_event(
            display=self.display,
            window=target,
            propagate=False,
            xevent=x_key_event,
            event_masks=event_mask,
        )
        xlib.x_flush(display=self.display)
        self._x_grab_key_binding(window=grab_window, key_definition=key_definition)

    def _install_global_key_handlers(self) -> None:
        """Grab `on_key` / `on_key_release` bindings that have no window matcher on the root window."""
        for key_definition, handler in self._key_handlers.get(None, {}).items():
            self._grab_key_binding(window=self.root, key_definition=key_definition, handler=handler)
        for key_definition, handler in self._key_release_handlers.get(None, {}).items():
            self._grab_key_binding(window=self.root, key_definition=key_definition, handler=handler, release=True)

    def _install_key_handlers_for_window(self, window: Window) -> None:
        """Grab `on_key` / `on_key_release` bindings whose `WindowMatchers` match `window`."""
        for window_matcher, key_bindings in self._key_handlers.items():
            if window_matcher is None or not window.matches(matcher=window_matcher):
                continue
            for key_definition, handler in key_bindings.items():
                self._grab_key_binding(window=window, key_definition=key_definition, handler=handler)
        for window_matcher, key_bindings in self._key_release_handlers.items():
            if window_matcher is None or not window.matches(matcher=window_matcher):
                continue
            for key_definition, handler in key_bindings.items():
                self._grab_key_binding(window=window, key_definition=key_definition, handler=handler, release=True)

    def _grab_button_binding(
        self,
        window: xlib.TYPES.Cython_Window,
        button: int,
        modifiers_value: int,
        handler: _ButtonHandler,
    ) -> None:
        """XGrabButton on `window`, once per CapsLock/NumLock combination in `IGNORED_KEY_MASKS`."""
        for ignored_key_mask in IGNORED_KEY_MASKS:
            mask: int = modifiers_value | ignored_key_mask
            xlib.x_grab_button(
                display=self.display,
                window=window,
                button=button,
                modifiers=mask,
                owner_events=False,
                event_mask=xlib.INPUT_EVENT_MASKS.ButtonPressMask.value,
                pointer_mode=xlib.GRAB_MODE.GrabModeAsync,
                keyboard_mode=xlib.GRAB_MODE.GrabModeAsync,
            )
            self._button_grabs.setdefault(window, {})[(mask, button)] = handler

    def _x_ungrab_button_binding(self, window: xlib.TYPES.Cython_Window, button: int, modifiers_value: int) -> None:
        """XUngrabButton for the CapsLock/NumLock variants. Does not touch `_button_grabs`."""
        for ignored_key_mask in IGNORED_KEY_MASKS:
            mask: int = modifiers_value | ignored_key_mask
            xlib.x_ungrab_button(display=self.display, button=button, modifiers=mask, window=window)

    def _x_grab_button_binding(self, window: xlib.TYPES.Cython_Window, button: int, modifiers_value: int) -> None:
        """XGrabButton for the CapsLock/NumLock variants. Does not touch `_button_grabs`."""
        for ignored_key_mask in IGNORED_KEY_MASKS:
            mask: int = modifiers_value | ignored_key_mask
            xlib.x_grab_button(
                display=self.display,
                window=window,
                button=button,
                modifiers=mask,
                owner_events=False,
                event_mask=xlib.INPUT_EVENT_MASKS.ButtonPressMask.value,
                pointer_mode=xlib.GRAB_MODE.GrabModeAsync,
                keyboard_mode=xlib.GRAB_MODE.GrabModeAsync,
            )

    def _ungrab_button_handler(self, handler: _ButtonHandler) -> None:
        """Drop every button grab whose callback is `handler`."""
        for window, grabs in list(self._button_grabs.items()):
            for (mask, button), bound in list(grabs.items()):
                if bound is not handler:
                    continue
                xlib.x_ungrab_button(display=self.display, button=button, modifiers=mask, window=window)
                del grabs[(mask, button)]
            if not grabs:
                del self._button_grabs[window]

    def _install_button_binding(
        self,
        window_matcher: Optional[WindowMatchers],
        button: int,
        modifiers_value: int,
        handler: _ButtonHandler,
    ) -> None:
        """Grab now: root if `window_matcher` is None, otherwise every matching mapped client."""
        if window_matcher is None:
            self._grab_button_binding(window=self.root, button=button, modifiers_value=modifiers_value, handler=handler)
            return
        for client in self.get_clients():
            if client.matches(matcher=window_matcher):
                self._grab_button_binding(
                    window=client, button=button, modifiers_value=modifiers_value, handler=handler
                )

    def _propagate_grabbed_button(self, button: int, modifiers_value: int, x_button_event: xlib.XButtonEvent) -> None:
        """Temporarily ungrab so the ButtonPress can reach the focused client (or the grabbed window), then re-grab."""
        grab_window: xlib.TYPES.Cython_Window = x_button_event.window
        self._x_ungrab_button_binding(window=grab_window, button=button, modifiers_value=modifiers_value)
        target: xlib.TYPES.Cython_Window = grab_window
        if grab_window == self.root:
            focused: Optional[Window] = self.current_window
            if focused is not None:
                target = focused
        xlib.x_send_event(
            display=self.display,
            window=target,
            propagate=False,
            xevent=x_button_event,
            event_masks=xlib.INPUT_EVENT_MASKS.ButtonPressMask,
        )
        xlib.x_flush(display=self.display)
        self._x_grab_button_binding(window=grab_window, button=button, modifiers_value=modifiers_value)

    def _install_global_button_handlers(self) -> None:
        """Grab `on_button` bindings that have no window matcher on the root window."""
        for (modifiers_value, button), handler in self._button_handlers.get(None, {}).items():
            self._grab_button_binding(window=self.root, button=button, modifiers_value=modifiers_value, handler=handler)

    def _install_button_handlers_for_window(self, window: Window) -> None:
        """Grab `on_button` bindings whose `WindowMatchers` match `window`."""
        for window_matcher, bindings in self._button_handlers.items():
            if window_matcher is None or not window.matches(matcher=window_matcher):
                continue
            for (modifiers_value, button), handler in bindings.items():
                self._grab_button_binding(
                    window=window, button=button, modifiers_value=modifiers_value, handler=handler
                )

    def on_key(
        self,
        key_definition: Union[str, KeyDefinition],
        window_matcher: Optional[WindowMatchers] = None,
        propagate_event: bool = False,
        *,
        release: bool = False,
    ) -> Callable[[_CbKey], _CbKey]:
        """
        Signal decorator to define a hotkey (`XGrabKey`).

        Bindings are recorded when the decorator runs (config import). `init()` grabs them on the X server.
        After `init()`, a new `@wm.on_key` grabs immediately (including on already-mapped matching clients).

        Args:
        - `key_definition`: `"Control + d"` (`Modifier + … + key`) or a `KeyDefinition`.
          Modifiers: `NoModifiers`, `AnyModifier`, `Control`/`Ctrl`, `Alt`/`Meta`, `Shift`, `Win`/`Windows`/`Hyper`/`Super`.
          Key: an X keysym name (`X11/keysymdef.h` without `XK_`) or `ANY_KEY`.
        - `window_matcher`: `None` (default) grabs on the **root** window — a process-wide hotkey.
          The callback's `window` is that root; use `wm.current_window` for the focused client.
          If set, grabs on every client that matches (at create time, and immediately if already mapped after `init()`).
        - `propagate_event`: If True, after the handler runs, replay the key event to the focused client
          (global grab) or the grabbed window (matcher grab), then re-grab. Defaults to `False` (orcsome3 consumes the key).

        Signature of the decorated function::

            def function_cb(window: Window, event: XKeyEvent) -> None: ...

        Global hotkey::

            from orcsome3 import get_wm
            from orcsome3.keys import KeyboardModifiers, KeyDefinition
            from orcsome3.libs.xlib import XKeyEvent
            from orcsome3.window_manager import Window

            wm = get_wm()

            @wm.on_key(key_definition=KeyDefinition(modifiers=KeyboardModifiers.Control, key=KeyDefinition.Key(name="a")))
            def test_hotkey(window: Window, event: XKeyEvent) -> None:
                print("hotkey Control + a pressed")

        Per-class grab (every matching window, including ones that already exist after `init()`)::

            @wm.on_key(
                key_definition=KeyDefinition(modifiers=KeyboardModifiers.Control, key=KeyDefinition.Key(name="d")),
                window_matcher=WindowMatchers(class_="URxvt"),
            )
            def close_urxvt_window(window: Window, event: XKeyEvent) -> None:
                window.close()

        String form::

            @wm.on_key(key_definition="Control + d")
            def change_window_desktop(window: Window, event: XKeyEvent) -> None:
                window.change_desktop(desktop=1)

        Call `.remove()` on the decorated function to ungrab and unregister.
        """

        def decorator_on_key(original_function: _CbKey) -> _CbKey:
            try:
                parsed_key_definition: KeyDefinition = (
                    KeyDefinition.new_from_string(keydef=key_definition)
                    if isinstance(key_definition, str)
                    else key_definition
                )
                _ = parsed_key_definition.get_modifiers_value_and_keycode(display=self.display)
            except Exception as e:
                _logger.error(msg=f"Invalid key definition: {key_definition}.\n{e}")
                return original_function

            if window_matcher is not None and window_matcher.is_empty():
                _logger.error(msg="The window matcher provided is empty.")
                return original_function

            @wraps(wrapped=original_function)
            def wrapper(window: xlib.TYPES.Cython_Window, x_key_event: xlib.XKeyEvent) -> None:
                original_function(window, x_key_event)
                if propagate_event:
                    self._propagate_grabbed_key(key_definition=parsed_key_definition, x_key_event=x_key_event)

            table: dict[Optional[WindowMatchers], dict[KeyDefinition, _KeyHandler]] = (
                self._key_release_handlers if release else self._key_handlers
            )
            table.setdefault(window_matcher, {})[parsed_key_definition] = wrapper

            def remove() -> None:
                _ = table.get(window_matcher, {}).pop(parsed_key_definition, None)
                self._ungrab_handler(handler=wrapper)

            setattr(wrapper, "remove", remove)
            if self._inited:
                self._install_key_binding(
                    window_matcher=window_matcher,
                    key_definition=parsed_key_definition,
                    handler=wrapper,
                    release=release,
                )
            return cast(_CbKey, wrapper)

        return decorator_on_key

    def on_key_release(
        self,
        key_definition: Union[str, KeyDefinition],
        window_matcher: Optional[WindowMatchers] = None,
        propagate_event: bool = False,
    ) -> Callable[[_CbKey], _CbKey]:
        """Like `on_key`, but KeyRelease. Shares the `XGrabKey` with a matching `on_key` if both are registered."""
        return self.on_key(
            key_definition=key_definition,
            window_matcher=window_matcher,
            propagate_event=propagate_event,
            release=True,
        )

    def on_button(
        self,
        button: Union[int, xlib.BUTTONS],
        modifiers: Union[int, KeyboardModifiers, list[KeyboardModifiers]] = KeyboardModifiers.NoModifiers,
        window_matcher: Optional[WindowMatchers] = None,
        propagate_event: bool = False,
    ) -> Callable[[_CbButton], _CbButton]:
        """
        Signal decorator for a pointer grab (`XGrabButton`). ButtonPress only.

        Args:
        - `button`: `BUTTONS.Button1`…`Button5` or `BUTTONS.AnyButton`.
        - `modifiers`: A `KeyboardModifiers` member, an int mask, or a list of members. Defaults to no modifiers.
        - `window_matcher`: `None` (default) grabs on the **root** window. If set, grabs on matching clients.
        - `propagate_event`: If True, replay the ButtonPress after the handler, then re-grab.

        Signature of the decorated function::

            def function_cb(window: Window, event: XButtonEvent) -> None: ...

            @wm.on_button(button=BUTTONS.Button1, modifiers=KeyboardModifiers.Control)
            def on_ctrl_click(window: Window, event: XButtonEvent) -> None:
                print(event.x, event.y)

        Call `.remove()` on the decorated function to ungrab and unregister.
        """

        def decorator_on_button(original_function: _CbButton) -> _CbButton:
            if window_matcher is not None and window_matcher.is_empty():
                _logger.error(msg="The window matcher provided is empty.")
                return original_function

            button_n: int = int(button)
            modifiers_value: int = _modifiers_mask(modifiers=modifiers)

            @wraps(wrapped=original_function)
            def wrapper(window: xlib.TYPES.Cython_Window, x_button_event: xlib.XButtonEvent) -> None:
                original_function(window, x_button_event)
                if propagate_event:
                    self._propagate_grabbed_button(
                        button=button_n, modifiers_value=modifiers_value, x_button_event=x_button_event
                    )

            self._button_handlers.setdefault(window_matcher, {})[(modifiers_value, button_n)] = wrapper

            def remove() -> None:
                _ = self._button_handlers.get(window_matcher, {}).pop((modifiers_value, button_n), None)
                self._ungrab_button_handler(handler=wrapper)

            setattr(wrapper, "remove", remove)
            if self._inited:
                self._install_button_binding(
                    window_matcher=window_matcher,
                    button=button_n,
                    modifiers_value=modifiers_value,
                    handler=wrapper,
                )
            return cast(_CbButton, wrapper)

        return decorator_on_button

    def on_create(self, matcher: Optional[WindowMatchers] = None) -> Callable[[_CbStruct], _CbStruct]:
        """
        Run on CreateNotify, including the existing-client sweep in `init()`.

        Use `@wm.on_create()` or `@wm.on_create(WindowMatchers(...))`. Filter with a `WindowMatchers`
        instance (not `name=` / `cls=` kwargs).

        `event` is `None` during the startup sweep (there is no real CreateNotify for windows that
        already existed before orcsome3 started) and a real `XCreateWindowEvent` otherwise::

            @wm.on_create()
            def on_any_create(window: Window, event: Optional[XCreateWindowEvent]) -> None:
                print(window.get_name_and_class())

            @wm.on_create(matcher=WindowMatchers(class_="Opera"))
            def replace_opera(window: Window, event: Optional[XCreateWindowEvent]) -> None:
                window.close()

        Call `.remove()` on the decorated function to unregister.
        """
        return self.on_create_manage(ignore_startup=False, matcher=matcher)

    def on_manage(self, matcher: Optional[WindowMatchers] = None) -> Callable[[_CbStruct], _CbStruct]:
        """
        Same as `on_create`, but skipped for windows already mapped when `init()` runs — so `event`
        is always a real `XCreateWindowEvent` here, never `None`.

        Use `@wm.on_manage()` or `@wm.on_manage(WindowMatchers(...))`.

        Nested per-window hooks belong here so they are not installed once per existing client at startup::

            @wm.on_manage(matcher=WindowMatchers(name="easyeffects", class_="easyeffects"))
            def on_easyeffects(window: Window, event: XCreateWindowEvent) -> None:
                @wm.on_destroy(window=window)
                def on_easyeffects_gone(window: Window, event: XDestroyWindowEvent) -> None:
                    print("easyeffects closed")

        Call `.remove()` to unregister.
        """
        return self.on_create_manage(ignore_startup=True, matcher=matcher)

    def on_create_manage(
        self, ignore_startup: bool, matcher: Optional[WindowMatchers] = None
    ) -> Callable[[_CbStruct], _CbStruct]:
        """Shared implementation of `on_create` / `on_manage`. Prefer those in the config.

        Args:
        - `ignore_startup`: If True, skip the existing-client sweep in `init()` (`on_manage`)
        - `matcher`: If set, run only when `window` matches

        Sets `.remove()` on the **user** function (the object `@wm.on_create()` returns).
        """

        def decorator(function: _CbStruct) -> _CbStruct:
            @wraps(wrapped=function)
            def wrapper(window: Window, event: Optional[xlib.XCreateWindowEvent]) -> None:
                if ignore_startup and self._startup:
                    return
                if matcher is None or window.matches(matcher=matcher):
                    function(window, event)

            def remove() -> None:
                try:
                    self._create_handlers.remove(wrapper)
                except ValueError:
                    pass

            self._create_handlers.append(wrapper)
            setattr(function, "remove", remove)
            return function

        return decorator

    def _window_event_cb_decorator(
        self, handlers: _WindowEventCbs, window: Optional[xlib.TYPES.Cython_Window]
    ) -> Callable[[_CbStruct], _CbStruct]:
        """`on_destroy`-style: `window=None` is every window, else one id. Callback is `(window, event)`."""

        def decorator(function: _CbStruct) -> _CbStruct:
            def remove() -> None:
                try:
                    handlers[window].remove(function)
                except Exception:
                    _logger.exception(msg="An exception occurred removing the function.")

            handlers.setdefault(window, []).append(function)
            setattr(function, "remove", remove)
            return function

        return decorator

    def _dispatch_window_event_cbs(
        self,
        handlers: _WindowEventCbs,
        window: xlib.TYPES.Cython_Window,
        event: xlib.XEvent,
    ) -> None:
        """Run `window=None` handlers, then per-id handlers. Sets `event_window`."""
        self._event_window = Window(window)
        event_window: Window = self._event_window
        if None in handlers:
            for handler in handlers[None]:
                handler(event_window, event)
        if window in handlers:
            for handler in handlers[window]:
                handler(event_window, event)

    def on_destroy(self, window: Optional[xlib.TYPES.Cython_Window] = None) -> Callable[[_CbStruct], _CbStruct]:
        """Signal decorator for DestroyNotify.

        `@wm.on_destroy()` runs for every destroyed window. Pass `window=` (typically the `window`
        parameter from `on_manage`) to listen to one id.

        `window` is only that id; reading properties on it will fail (it is already gone)::

            @wm.on_destroy()
            def cb_destroy_window(window: Window, event: XDestroyWindowEvent) -> None:
                print(f"The window {window} was destroyed")

            @wm.on_manage(matcher=WindowMatchers(name="easyeffects", class_="easyeffects"))
            def on_create_easyeffects(window: Window, event: XCreateWindowEvent) -> None:
                @wm.on_destroy(window=window)
                def on_destroy_easyeffects(window: Window, event: XDestroyWindowEvent) -> None:
                    print("easyeffect's window destroyed")

        Call `.remove()` on the decorated function to unregister.
        """
        return self._window_event_cb_decorator(handlers=self._destroy_handlers, window=window)

    def on_property_change(
        self, property: str, window: Optional[xlib.TYPES.Cython_Window] = None
    ) -> Callable[[_CbStruct], _CbStruct]:
        """Signal decorator for PropertyNotify (new value only).

        `property` is an atom name (`_NET_WM_STATE`, …). `window=None` (default) is every window;
        pass `window=` (typically the `window` parameter from `on_manage`) to watch one id.

            @wm.on_property_change(property="_NET_WM_STATE")
            def window_maximized_state_change(window: Window, event: XPropertyEvent) -> None:
                if window.maximized_vert and window.maximized_horz:
                    print("The window is maximized now!")

            @wm.on_manage()
            def switch_to_desktop(window: Window, event: XCreateWindowEvent) -> None:
                if window.activate_desktop() is None:

                    @wm.on_property_change(window=window, property="_NET_WM_DESKTOP")
                    def property_was_set(window: Window, event: XPropertyEvent) -> None:
                        window.activate_desktop()
                        property_was_set.remove()

        Call `.remove()` on the decorated function to unregister.
        """

        def decorator(function: _CbStruct) -> _CbStruct:
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

    def on_focus(self, window: Optional[xlib.TYPES.Cython_Window] = None) -> Callable[[_CbStruct], _CbStruct]:
        """Signal decorator for FocusIn (`NotifyNormal` / `NotifyWhileGrabbed`).

        `@wm.on_focus()` runs for every focused window. Pass `window=` (typically the `window`
        parameter from `on_manage`) to listen to one id.

        Signature::

            def function_cb(window: Window, event: XFocusChangeEvent) -> None: ...

        Call `.remove()` on the decorated function to unregister.
        """
        return self._window_event_cb_decorator(handlers=self._focus_handlers, window=window)

    def on_unfocus(self, window: Optional[xlib.TYPES.Cython_Window] = None) -> Callable[[_CbStruct], _CbStruct]:
        """Signal decorator for FocusOut (`NotifyNormal` / `NotifyWhileGrabbed`). Same `window=` rules as `on_focus`."""
        return self._window_event_cb_decorator(handlers=self._unfocus_handlers, window=window)

    def on_map(self, window: Optional[xlib.TYPES.Cython_Window] = None) -> Callable[[_CbStruct], _CbStruct]:
        """Signal decorator for MapNotify. Same `window=` rules as `on_destroy`.

        Signature::

            def function_cb(window: Window, event: XMapEvent) -> None: ...
        """
        return self._window_event_cb_decorator(handlers=self._map_handlers, window=window)

    def on_unmap(self, window: Optional[xlib.TYPES.Cython_Window] = None) -> Callable[[_CbStruct], _CbStruct]:
        """Signal decorator for UnmapNotify. Same `window=` rules as `on_destroy`.

        Signature::

            def function_cb(window: Window, event: XUnmapEvent) -> None: ...
        """
        return self._window_event_cb_decorator(handlers=self._unmap_handlers, window=window)

    def on_configure(self, window: Optional[xlib.TYPES.Cython_Window] = None) -> Callable[[_CbStruct], _CbStruct]:
        """Signal decorator for ConfigureNotify. Same `window=` rules as `on_destroy`.

        Fires often during interactive resize. `event.x`/`event.y` are relative to the parent;
        `event.width`/`event.height` are the size from this event (not a later `get_geometry()`).

        Signature::

            def function_cb(window: Window, event: XConfigureEvent) -> None: ...
        """
        return self._window_event_cb_decorator(handlers=self._configure_handlers, window=window)

    def on_client_message(
        self, message_type: str, window: Optional[xlib.TYPES.Cython_Window] = None
    ) -> Callable[[_CbClient], _CbClient]:
        """Signal decorator for ClientMessage.

        `message_type` is an atom name (`_NET_WM_STATE`, `_NET_ACTIVE_WINDOW`, …). `window=None` (default)
        is every destination this connection sees; pass `window=` to watch one id.

        EWMH messages sent to the root with `SubstructureNotify` arrive here (`event_window` is the root).
        Messages targeted at other clients' windows are only delivered to this connection if the sender
        used a non-zero event mask this process selected.

        Signature of the decorated function::

            def function_cb(window: Window, event: XClientMessageEvent) -> None: ...

        Call `.remove()` on the decorated function to unregister.
        """

        def decorator(original_function: _CbClient) -> _CbClient:
            atom: xlib.TYPES.Cython_Atom = self.atom_cache.get_atom(name=message_type)

            def remove() -> None:
                try:
                    self._client_message_handlers[atom][window].remove(original_function)
                except Exception:
                    _logger.exception(msg="An exception occurred removing the function.")

            self._client_message_handlers.setdefault(atom, {}).setdefault(window, []).append(original_function)
            setattr(original_function, "remove", remove)
            return original_function

        return decorator

    def on_timer(
        self, timeout: float, start: bool = True, first_timeout: Optional[float] = None
    ) -> Callable[[_CbTimer], _CbTimer]:
        """Signal decorator for a repeating libev timer.

        Signature of decorated function should be::

            function_cb() -> Optional[bool]:
                # return True to stop the timer

        The wrapper gains `.start()`, `.stop()`, `.again()`, `.remaining()`, `.overdue(seconds)`, and `.remove()`.

        Args:
        - `timeout`: Repeat interval in seconds
        - `start`: If True, start the timer immediately
        - `first_timeout`: Delay before the first fire; `None` means `timeout`. `0` fires as soon as the loop runs.
        """

        def decorator(function: _CbTimer) -> _CbTimer:
            loop: Optional[ev.Loop] = self._loop
            if loop is None:
                raise RuntimeError("WindowManager was created without an event loop")

            def callback_of_timer(__loop__: ev.Loop, __watcher__: ev.TimerWatcher, __events__: int) -> None:
                if function():
                    timer.stop(loop=loop)
                else:
                    timer.update_next_stop()

            timer: ev.TimerWatcher = ev.TimerWatcher.new(
                callback=callback_of_timer,
                after=timeout if first_timeout is None else first_timeout,
                repeat=timeout,
            )

            self._timer_handlers.append(function)
            setattr(
                function,
                "start",
                lambda after=0.0, repeat=0.0: timer.start(loop=loop, after=after, repeat=repeat),
            )
            setattr(function, "stop", lambda: timer.stop(loop=loop))
            setattr(function, "again", lambda: timer.again(loop=loop))
            setattr(function, "remaining", lambda: timer.remaining(loop=loop))

            def overdue(overdue_by: float) -> bool:
                return timer.overdue(timeout=overdue_by)

            setattr(function, "overdue", overdue)

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

        return decorator

    def on_init(self, func: _CbNone) -> _CbNone:
        """`@wm.on_init` (no parentheses). Runs in `init()` after root events are selected, before existing clients."""
        self._init_handlers.append(func)
        return func

    def on_deinit(self, func: _CbNone) -> _CbNone:
        """`@wm.on_deinit` (no parentheses). Runs in `stop()` after key grabs and timers are torn down."""
        self._deinit_handlers.append(func)
        return func

    def init(self) -> None:
        """Select root events, run `on_init` handlers, grab global keys, then fire create handlers for existing clients."""
        xlib.x_select_input(
            display=self.display, window=self.root, event_mask=xlib.INPUT_EVENT_MASKS.SubstructureNotifyMask
        )

        for handler in self._init_handlers:
            handler()

        self._install_global_key_handlers()
        self._install_global_button_handlers()
        self._startup = True
        for window in self.get_clients():
            self._process_create_window(window=window)

        xlib.x_sync(display=self.display, discard=False)
        self._startup = False
        self._inited = True

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
        """Clear handlers and ungrab keys and buttons.

        Args:
        - `exit`: If True, close the X display (process shutdown). If False, ungrab keys/buttons so a restart can re-init.
        """
        self._inited = False
        self._startup = False
        self._wm_name = None
        self._wm_name_loaded = False
        self._key_handlers.clear()
        self._key_release_handlers.clear()
        self._key_grabs.clear()
        self._button_handlers.clear()
        self._button_grabs.clear()
        self._property_handlers.clear()
        self._client_message_handlers.clear()
        self._create_handlers[:] = []
        self._destroy_handlers.clear()
        self._focus_handlers.clear()
        self._unfocus_handlers.clear()
        self._map_handlers.clear()
        self._unmap_handlers.clear()
        self._configure_handlers.clear()
        self.focus_history[:] = []
        self._focus_ids.clear()

        if not exit:
            xlib.x_ungrab_key(
                display=self.display,
                keycode=xlib.CONSTANTS.KB.ANY_KEY,
                modifiers=xlib.KEY_MASKS.AnyModifier.value,
                window=self.root,
            )
            xlib.x_ungrab_button(
                display=self.display,
                button=xlib.BUTTONS.AnyButton.value,
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
                xlib.x_ungrab_button(
                    display=self.display,
                    button=xlib.BUTTONS.AnyButton.value,
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
        """Intern `name` on this display (`XInternAtom`). Prefer `atom_cache.get_atom` for repeated lookups."""
        return self.atom_cache.get_atom(name=name, create_if_not_exists=create_if_not_exists)

    def get_keycode_from_string_or_keysym(
        self, key: Union[str, xlib.TYPES.Cython_KeySym]
    ) -> Optional[xlib.TYPES.Cython_KeyCode]:
        """Get keycode for `key`"""
        return keycode_from_string_or_keysym(display=self.display, key=key)

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
                message_type=self.atom_cache.get_atom(name=message_type, create_if_not_exists=True),
                format_=format_,
                data=data,
                send_event=True,
            ),
        )

    def flush(self) -> None:
        """Flush the output buffer to the X server (`XFlush`)."""
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
        for client in clients:
            if client.matches(matcher=matcher):
                return client
        return None

    def _process_create_window(self, window: Window, event: Optional[xlib.XCreateWindowEvent] = None) -> None:
        """Select events on `window`, run create handlers, then grab matching per-window hotkeys.

        `event` is `None` for the startup sweep in `init()` (no real CreateNotify exists for those).
        """
        xlib.x_select_input(
            display=self.display,
            window=window,
            event_mask=[
                xlib.INPUT_EVENT_MASKS.StructureNotifyMask,
                xlib.INPUT_EVENT_MASKS.PropertyChangeMask,
                xlib.INPUT_EVENT_MASKS.FocusChangeMask,
            ],
        )
        self._event_window = window
        for handler in self._create_handlers:
            handler(window, event)
        self._install_key_handlers_for_window(window=window)
        self._install_button_handlers_for_window(window=window)

    def _remember_focus(self, window: xlib.TYPES.Cython_Window) -> None:
        """Move `window` to the end of `focus_history` (oldest first)."""
        if window in self._focus_ids:
            self.focus_history.remove(window)
        else:
            self._focus_ids.add(window)
        self.focus_history.append(window)

    def _forget_focus(self, window: xlib.TYPES.Cython_Window) -> None:
        """Drop `window` from `focus_history` if present."""
        if window not in self._focus_ids:
            return
        self._focus_ids.discard(window)
        try:
            self.focus_history.remove(window)
        except ValueError:
            pass

    def _process_remove_window(self, window: xlib.TYPES.Cython_Window) -> None:
        """Drop destroy/property/key-grab/button-grab state for a window that is gone (X ids are reused)."""
        _ = self._key_grabs.pop(window, None)
        _ = self._button_grabs.pop(window, None)
        for table in (
            self._destroy_handlers,
            self._focus_handlers,
            self._unfocus_handlers,
        ):
            _ = table.pop(window, None)
        for table in (self._map_handlers, self._unmap_handlers, self._configure_handlers):
            _ = table.pop(window, None)

        self._forget_focus(window=window)

        for atom, whandlers in list(self._property_handlers.items()):
            if window in whandlers:
                del whandlers[window]

            if not len(self._property_handlers[atom]):
                del self._property_handlers[atom]

        for atom, cwhandlers in list(self._client_message_handlers.items()):
            if window in cwhandlers:
                del cwhandlers[window]

            if not len(self._client_message_handlers[atom]):
                del self._client_message_handlers[atom]

    def _lookup_key_handler(self, event: xlib.XKeyEvent, *, release: bool) -> Optional[_KeyHandler]:
        slots: Optional[_KeyGrabSlots] = self._key_grabs.get(event.window, {}).get((event.state, event.keycode))
        if slots is None:
            return None
        return slots[1 if release else 0]

    def _key_press_event_handler(self, event: xlib.XEvent) -> None:
        if not isinstance(event, xlib.XKeyEvent):
            return

        handler: Optional[_KeyHandler] = self._lookup_key_handler(event=event, release=False)
        if handler is None:
            return

        self._event_window = Window(event.window)
        handler(self._event_window, event)

    def _handle_keyrelease(self, event: xlib.XEvent) -> None:
        if not isinstance(event, xlib.XKeyEvent):
            return

        handler: Optional[_KeyHandler] = self._lookup_key_handler(event=event, release=True)
        if handler is None:
            return

        self._event_window = Window(event.window)
        handler(self._event_window, event)

    def _handle_button(self, event: xlib.XEvent) -> None:
        if not isinstance(event, xlib.XButtonEvent):
            return
        state: int = event.state & ~_BUTTON_STATE_MASK
        grabs: dict[tuple[int, int], _ButtonHandler] = self._button_grabs.get(event.window, {})
        handler: Optional[_ButtonHandler] = grabs.get((state, int(event.button)))
        if handler is None:
            handler = grabs.get((state, int(xlib.BUTTONS.AnyButton)))
        if handler is None:
            return
        self._event_window = Window(event.window)
        handler(self._event_window, event)

    def _handle_create(self, event: xlib.XEvent) -> None:
        if not isinstance(event, xlib.XCreateWindowEvent):
            return
        _logger.debug(msg=event)
        self._startup = False
        window: Window = Window(event.window)
        global _ignore_logger
        _ignore_logger = True
        attrs: Optional[WindowAttributes] = window.attributes
        if attrs is None or attrs.override_redirect:
            _ignore_logger = False
            return
        _ignore_logger = False
        self._process_create_window(window=window, event=event)

    def _handle_destroy(self, event: xlib.XEvent) -> None:
        if not isinstance(event, xlib.XDestroyWindowEvent):
            return
        _logger.debug(msg=event)
        if event.window == self._recently_destroyed_window:
            return
        self._recently_destroyed_window = event.window
        self._dispatch_window_event_cbs(handlers=self._destroy_handlers, window=event.window, event=event)
        self._process_remove_window(window=event.window)

    def _handle_property(self, event: xlib.XEvent) -> None:
        if not isinstance(event, xlib.XPropertyEvent):
            return
        atom: xlib.TYPES.Cython_Atom = event.atom
        if event.state == xlib.XPropertyEvent.STATE.PropertyNewValue and atom in self._property_handlers:
            self._event_window = Window(event.window)
            event_window: Window = self._event_window
            wphandlers: dict[Optional[xlib.TYPES.Cython_Window], list[_PropertyHandler]] = self._property_handlers[atom]
            if event.window in wphandlers:
                for handler in wphandlers[event.window]:
                    handler(event_window, event)

            if None in wphandlers:
                for handler in wphandlers[None]:
                    handler(event_window, event)

    def _deliver_structure(
        self,
        event: Union[xlib.XMapEvent, xlib.XUnmapEvent, xlib.XConfigureEvent],
        handlers: _WindowEventCbs,
    ) -> None:
        # SubstructureNotify on root duplicates StructureNotify on the client; skip the root copy.
        if event.event == self.root:
            return
        self._dispatch_window_event_cbs(handlers=handlers, window=event.window, event=event)

    def _handle_map(self, event: xlib.XEvent) -> None:
        if not isinstance(event, xlib.XMapEvent):
            return
        self._deliver_structure(event=event, handlers=self._map_handlers)

    def _handle_unmap(self, event: xlib.XEvent) -> None:
        if not isinstance(event, xlib.XUnmapEvent):
            return
        self._deliver_structure(event=event, handlers=self._unmap_handlers)

    def _handle_configure(self, event: xlib.XEvent) -> None:
        if not isinstance(event, xlib.XConfigureEvent):
            return
        self._deliver_structure(event=event, handlers=self._configure_handlers)

    def _handle_client_message(self, event: xlib.XEvent) -> None:
        if not isinstance(event, xlib.XClientMessageEvent):
            return
        atom: xlib.TYPES.Cython_Atom = event.message_type
        if atom not in self._client_message_handlers:
            return
        self._event_window = Window(event.window)
        wphandlers: dict[Optional[xlib.TYPES.Cython_Window], list[_ClientMessageHandler]] = (
            self._client_message_handlers[atom]
        )
        event_window: Window = self._event_window
        if event.window in wphandlers:
            for handler in wphandlers[event.window]:
                handler(event_window, event)
        if None in wphandlers:
            for handler in wphandlers[None]:
                handler(event_window, event)

    def _handle_focus(self, event: xlib.XEvent) -> None:
        if not isinstance(event, xlib.XFocusChangeEvent):
            return
        _logger.debug(msg=event)
        is_real_focus: bool = event.mode in (
            xlib.XFocusChangeEvent.NOTIFY_MODE.NotifyNormal,
            xlib.XFocusChangeEvent.NOTIFY_MODE.NotifyWhileGrabbed,
        )
        if event.type == xlib.XEvent.EVENT_TYPES.FocusIn:
            self._remember_focus(window=event.window)
            if is_real_focus:
                self._dispatch_window_event_cbs(handlers=self._focus_handlers, window=event.window, event=event)
            if is_real_focus and self.track_kbd_layout:
                prop: Optional[xlib.WindowProperty] = Window(event.window).get_property(property_="_ORCSOME_KBD_GROUP")
                if prop is not None:
                    _ = xlib.x_kb_lock_group(
                        display=self.display,
                        group=xlib.KEYSYM_GROUPS(prop.get_int_list()[0]) if prop else xlib.KEYSYM_GROUPS.XkbGroup1Index,
                    )
        else:
            if is_real_focus:
                self._dispatch_window_event_cbs(handlers=self._unfocus_handlers, window=event.window, event=event)
            if is_real_focus and self.track_kbd_layout:
                _ = Window(event.window).set_property(
                    property_name="_ORCSOME_KBD_GROUP",
                    type_="CARDINAL",
                    format_=xlib.PROPERTY_FORMAT.LONG,
                    property_data=array("l", [xlib.x_kb_get_state(display=self.display).group]),
                )

    def _xevent_cb(self, __loop__: ev.Loop, __watcher__: ev.IOWatcher, __revents__: int) -> None:
        try:
            while True:
                pending_events: int = xlib.x_pending(display=self.display)
                if not pending_events:
                    break

                while pending_events > 0:
                    try:
                        event: xlib.XEvent = xlib.x_next_event(display=self.display)
                    except Exception:
                        _logger.exception(msg="XNextEvent failed")
                        return
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
        except Exception as e:
            _logger.exception(msg=e)

    def get_screen_size(self) -> Optional[xlib.XWindowGeometry]:
        """Get size of screen (root window)"""
        return self.root.get_geometry()

    def get_workarea(self, desktop: Optional[int] = None) -> list[int]:
        """
        Get workarea geometry.

        - `desktop`: Desktop for working area receiving. If `None` then `self.current_desktop` is used
        """
        result: Optional[xlib.WindowProperty] = self.root.get_property(property_="_NET_WORKAREA")
        if desktop is None:
            desktop = self.current_desktop
        if not desktop or not result:
            return []
        return result.get_int_list()[4 * desktop : 4 * desktop + 4]

    def get_screen_saver_info(self) -> Optional[xlib.XScreenSaverInfo]:
        """
        This is a wrapper around `XScreenSaverQueryInfo`, returns information about the current
        state of the screen saver or `None` if there's no screensaver active.
        """
        return xlib.x_get_screen_saver_info(display=self.display, drawable=self.root)

    def get_atom_name(self, atom: xlib.TYPES.Cython_Atom) -> Optional[str]:
        """Return the name associated with an atom"""
        return self.atom_cache.get_name(atom=atom)

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
        """Called when `restart()` raises; the CLI sets this to reload the config without exiting."""
        self._restart_handler = handler


class Window(int):
    """X window id (`int` subclass) with EWMH helpers.

    Use `wm`, `event_window`, and `current_window` from `WindowManager`. The class holds a process-wide
    `WindowManager` set by `Window.set_wm` during manager construction.
    """

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
                atom_type=self.wm.atom_cache.get_atom(name=type_, create_if_not_exists=True),
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

        Returns a `orcsome3.window_manager.WindowTree` object containing info about the tree (root, parent and children windows).
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
        if matcher.name is not None or matcher.class_ is not None:
            name_and_class: Optional[tuple[str, str]] = self.get_name_and_class()
            name: str = "" if name_and_class is None else name_and_class[0]
            class_: str = "" if name_and_class is None else name_and_class[1]
            if matcher.name is not None and not match_string(pattern=matcher.name, string=name):
                return False
            if matcher.class_ is not None and not match_string(pattern=matcher.class_, string=class_):
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
        """Windows under the root tree that share this window's `_NET_WM_PID` (empty if pid is unknown)."""
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
        """Set `_NET_WM_ICON` from an image file. Fails if the path is missing or larger than 10 MB."""
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
                if motif_hints is not None:
                    params = motif_hints.get_int_list()
                    if len(params) == 5:
                        params[2] = int(decorate)
                    else:
                        params = [2, 0, int(decorate), 0, 0]
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
        """Move/resize relative to the current desktop workarea (`_NET_MOVERESIZE_WINDOW`). Omitted edges stay 0 / 1px min size."""

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
        """Place the window by workarea insets: `left`/`top` origin, width/height = workarea minus `right`/`bottom`."""
        flags: int = 0x2F00
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
        """Process-wide WindowManager bound by `set_wm` (raises if accessed before the manager exists)."""
        return cast(WindowManager, self._wm)

    @classmethod
    def set_wm(cls, window_manager: WindowManager) -> None:
        """Bind every Window instance to this manager. Called from `WindowManager.__init__`."""
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
        name_and_class: Optional[tuple[str, str]] = self.get_name_and_class()
        return None if name_and_class is None else name_and_class[0]

    @property
    def class_(self) -> Optional[str]:
        """Return second part from `WM_CLASS` property"""
        name_and_class: Optional[tuple[str, str]] = self.get_name_and_class()
        return None if name_and_class is None else name_and_class[1]

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

    def _state_atoms(self) -> Optional[list[int]]:
        """`_NET_WM_STATE` atom ids, or `None` if the property is missing."""
        states: Optional[xlib.WindowProperty] = self.get_property(property_="_NET_WM_STATE")
        if states is None or not len(states.property_data):
            return None
        return states.get_int_list()

    def _has_net_state(self, atom_name: str) -> bool:
        """True if `_NET_WM_STATE` contains `atom_name` (one property read)."""
        atoms: Optional[list[int]] = self._state_atoms()
        if not atoms:
            return False
        return self.wm.atom_cache.get_atom(name=atom_name) in atoms

    @property
    def state(self) -> Optional[list[str]]:
        """Return `_NET_WM_STATE` property"""
        atoms: Optional[list[int]] = self._state_atoms()
        if atoms is None:
            return None
        try:
            states_: list[str] = []
            for state in atoms:
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
        return self._has_net_state(atom_name="_NET_WM_STATE_MAXIMIZED_VERT")

    @property
    def maximized_horz(self) -> bool:
        """Check if atom `_NET_WM_STATE_MAXIMIZED_HORZ` is present in window state"""
        return self._has_net_state(atom_name="_NET_WM_STATE_MAXIMIZED_HORZ")

    @property
    def decorated(self) -> bool:
        """
        Return `False` if window is not decorated otherwise `True`

        window is considered non-decorated when:
        - There's no window manager running
        - It has the attribute override-redirect in its window attributes
        - It has a 0 on the third bit in the property `_MOTIF_WM_HINTS` if the property is present
        """
        wm_name: Optional[str] = self.wm.wm_name
        if wm_name is None:
            return False
        attrs: Optional[WindowAttributes] = self.attributes
        if attrs is not None and attrs.override_redirect:
            return False
        if wm_name == "Openbox":
            return not self._has_net_state(atom_name="_OB_WM_STATE_UNDECORATED")
        motif_hints: Optional[xlib.WindowProperty] = self.get_property(property_="_MOTIF_WM_HINTS")
        try:
            if motif_hints is not None and motif_hints.get_int_list()[2] == 0:
                return False
        except:
            pass
        return True

    @property
    def urgent(self) -> bool:
        """Check if atom `_NET_WM_STATE_DEMANDS_ATTENTION` is present in window state"""
        return self._has_net_state(atom_name="_NET_WM_STATE_DEMANDS_ATTENTION")

    @property
    def fullscreen(self) -> bool:
        """Check if atom `_NET_WM_STATE_FULLSCREEN` is present in window state"""
        return self._has_net_state(atom_name="_NET_WM_STATE_FULLSCREEN")

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
        """Wrap an `xlib.XWindowTree` so every id is a `Window`."""
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
    - `map_state`: Map state. See enum `orcsome3.libs.xlib.XWindowAttributes.MapState`
    """

    def __init__(self, window: Window, root: Window, xwindowattributes: xlib.XWindowAttributes) -> None:
        """Copy geometry and map state from the Xlib attributes struct onto this window."""
        self.window: Window = window
        self.root: Window = root
        self.x: int = xwindowattributes.x
        self.y: int = xwindowattributes.y
        self.width: int = xwindowattributes.width
        self.height: int = xwindowattributes.height
        self.border_width: int = xwindowattributes.border_width
        self.depth: int = xwindowattributes.depth
        self.override_redirect: bool = xwindowattributes.override_redirect
        self.map_state: xlib.XWindowAttributes.MapState = xwindowattributes.map_state
