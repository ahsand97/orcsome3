"""Thin Python wrappers around Xlib / Xss / Xext / DPMS via the compiled `orcsome3_backend` extension.

Only this module and `orcsome3.libs.ev` should import `orcsome3_backend`.
The `.so` is looked up on `sys.path`; set `PYTHONPATH` if it lives elsewhere.
"""

from __future__ import annotations

import logging
from array import array
from enum import Enum
from pathlib import Path
from typing import Callable, NamedTuple, Optional, Union, cast

# Import TypeAlias from module typing_extensions to make it compatible with python 3.8
from typing_extensions import TypeAlias, override

# Try to import shared library orcsome3_backend.cpython-xxx-x86_64-linux-gnu.so, it looks for standard locations at sys.path,
# to specify another location use env var PYTHONPATH (PYTHONPATH="/custom/dir:$PYTHONPATH")
import orcsome3_backend
from orcsome3.utils import Final

# Globals
_logger: logging.Logger = logging.getLogger(name=__name__)


class TYPES(metaclass=Final):
    """Type aliases for Cython data types."""

    Cython_Atom: TypeAlias = int
    Cython_Window: TypeAlias = int
    Cython_KeySym: TypeAlias = int
    Cython_KeyCode: TypeAlias = int
    Cython_Time: TypeAlias = int
    Cython_Display: TypeAlias = orcsome3_backend.PyDisplay
    Cython_XWindowChanges: TypeAlias = orcsome3_backend.PyXWindowChanges
    Cython_XWindowAttributes: TypeAlias = orcsome3_backend.PyXWindowAttributes
    Cython_XWindowTree: TypeAlias = orcsome3_backend.PyXWindowTree
    Cython_XWindowGeometry: TypeAlias = orcsome3_backend.PyXWindowGeometry
    Cython_XScreenSaverInfo: TypeAlias = orcsome3_backend.PyXScreenSaverInfo
    Cython_XkbStateRec: TypeAlias = orcsome3_backend.PyXkbStateRec
    Cython_DPMSInfo: TypeAlias = orcsome3_backend.PyDPMSInfo

    class EVENTS(metaclass=Final):
        Cython_XEvent: TypeAlias = orcsome3_backend.PyXEvent
        Cython_XButtonEvent: TypeAlias = orcsome3_backend.PyXButtonEvent
        Cython_XKeyEvent: TypeAlias = orcsome3_backend.PyXKeyEvent
        Cython_XFocusChangeEvent: TypeAlias = orcsome3_backend.PyXFocusChangeEvent
        Cython_XCreateWindowEvent: TypeAlias = orcsome3_backend.PyXCreateWindowEvent
        Cython_XDestroyWindowEvent: TypeAlias = orcsome3_backend.PyXDestroyWindowEvent
        Cython_XMapEvent: TypeAlias = orcsome3_backend.PyXMapEvent
        Cython_XUnmapEvent: TypeAlias = orcsome3_backend.PyXUnmapEvent
        Cython_XConfigureEvent: TypeAlias = orcsome3_backend.PyXConfigureEvent
        Cython_XPropertyEvent: TypeAlias = orcsome3_backend.PyXPropertyEvent
        Cython_XClientMessageEvent: TypeAlias = orcsome3_backend.PyXClientMessageEvent
        Cython_XErrorEvent: TypeAlias = orcsome3_backend.PyXErrorEvent


class CONSTANTS(metaclass=Final):
    """Constants"""

    CURRENT_TIME: TYPES.Cython_Time = TYPES.Cython_Time(orcsome3_backend.CONSTANTS.CurrentTime)
    ANY_PROPERTY_TYPE: TYPES.Cython_Atom = TYPES.Cython_Atom(orcsome3_backend.CONSTANTS.AnyPropertyType)

    class KB(metaclass=Final):
        """Keyboard Constants"""

        NO_SYMBOL: TYPES.Cython_KeySym = TYPES.Cython_KeySym(orcsome3_backend.CONSTANTS.NoSymbol)
        ANY_KEY: TYPES.Cython_KeyCode = TYPES.Cython_KeyCode(orcsome3_backend.CONSTANTS.AnyKey)
        X_KB_USE_CORE_KBD: int = orcsome3_backend.CONSTANTS.XkbUseCoreKbd

    REVERT_TO_NONE: int = orcsome3_backend.CONSTANTS.RevertToNone
    REVERT_TO_POINTER_ROOT: int = orcsome3_backend.CONSTANTS.RevertToPointerRoot
    REVERT_TO_PARENT: int = orcsome3_backend.CONSTANTS.RevertToParent


class INPUT_EVENT_MASKS(int, Enum):
    """
    Input Event Masks. Used as event-mask window attribute and as arguments to grab requests
    """

    NoEventMask = orcsome3_backend.INPUT_EVENT_MASKS.NoEventMask
    StructureNotifyMask = orcsome3_backend.INPUT_EVENT_MASKS.StructureNotifyMask
    SubstructureNotifyMask = orcsome3_backend.INPUT_EVENT_MASKS.SubstructureNotifyMask
    SubstructureRedirectMask = orcsome3_backend.INPUT_EVENT_MASKS.SubstructureRedirectMask
    PropertyChangeMask = orcsome3_backend.INPUT_EVENT_MASKS.PropertyChangeMask
    FocusChangeMask = orcsome3_backend.INPUT_EVENT_MASKS.FocusChangeMask
    KeyPressMask = orcsome3_backend.INPUT_EVENT_MASKS.KeyPressMask
    KeyReleaseMask = orcsome3_backend.INPUT_EVENT_MASKS.KeyReleaseMask
    ButtonPressMask = orcsome3_backend.INPUT_EVENT_MASKS.ButtonPressMask
    ButtonReleaseMask = orcsome3_backend.INPUT_EVENT_MASKS.ButtonReleaseMask


class KEY_MASKS(int, Enum):
    """
    Key masks. Used as modifiers to GrabButton and GrabKey, results of QueryPointer,
    state in various key-, mouse-, and button-related events.
    """

    NoModifiers = 0  # No modifiers
    AnyModifier = orcsome3_backend.KEY_MASKS.AnyModifier  # Any modifier
    Mod1Mask = orcsome3_backend.KEY_MASKS.Mod1Mask  # Alt
    ControlMask = orcsome3_backend.KEY_MASKS.ControlMask  # Ctrl
    ShiftMask = orcsome3_backend.KEY_MASKS.ShiftMask  # Shift
    Mod2Mask = orcsome3_backend.KEY_MASKS.Mod2Mask  # Num Lock
    Mod4Mask = orcsome3_backend.KEY_MASKS.Mod4Mask  # Windows
    LockMask = orcsome3_backend.KEY_MASKS.LockMask  # Caps Lock


class BUTTON_MASKS(int, Enum):
    """Button masks"""

    NoModifiers = 0  # No modifiers
    AnyModifier = orcsome3_backend.BUTTON_MASKS.AnyModifier  # Any modifier
    Button1Mask = orcsome3_backend.BUTTON_MASKS.Button1Mask
    Button2Mask = orcsome3_backend.BUTTON_MASKS.Button2Mask
    Button3Mask = orcsome3_backend.BUTTON_MASKS.Button3Mask
    Button4Mask = orcsome3_backend.BUTTON_MASKS.Button4Mask
    Button5Mask = orcsome3_backend.BUTTON_MASKS.Button5Mask


class BUTTONS(int, Enum):
    """Button names"""

    AnyButton = orcsome3_backend.BUTTONS.AnyButton
    Button1 = orcsome3_backend.BUTTONS.Button1
    Button2 = orcsome3_backend.BUTTONS.Button2
    Button3 = orcsome3_backend.BUTTONS.Button3
    Button4 = orcsome3_backend.BUTTONS.Button4
    Button5 = orcsome3_backend.BUTTONS.Button5


class WINDOW_VALUE_MASK(int, Enum):
    """Window value mask bits. Enum used by function `x_configure_window()`"""

    CWX = orcsome3_backend.WINDOW_VALUE_MASK.CWX
    CWY = orcsome3_backend.WINDOW_VALUE_MASK.CWY
    CWWidth = orcsome3_backend.WINDOW_VALUE_MASK.CWWidth
    CWHeight = orcsome3_backend.WINDOW_VALUE_MASK.CWHeight
    CWBorderWidth = orcsome3_backend.WINDOW_VALUE_MASK.CWBorderWidth
    CWSibling = orcsome3_backend.WINDOW_VALUE_MASK.CWSibling
    CWStackMode = orcsome3_backend.WINDOW_VALUE_MASK.CWStackMode


class GRAB_MODE(int, Enum):
    """GrabPointer, GrabButton, GrabKeyboard, GrabKey Modes"""

    GrabModeSync = orcsome3_backend.GRAB_MODE.GrabModeSync
    GrabModeAsync = orcsome3_backend.GRAB_MODE.GrabModeAsync


class SET_PROPERTY_MODE(int, Enum):
    """Specifies the mode of the operation. Enum used by function `x_change_window_property()`"""

    # Discards the previous property value and stores the new data
    PropModeReplace = orcsome3_backend.SET_PROPERTY_MODE.PropModeReplace
    # Inserts the specified data before the beginning of the existing data
    PropModePrepend = orcsome3_backend.SET_PROPERTY_MODE.PropModePrepend
    # Inserts the specified data onto the end of the existing data
    PropModeAppend = orcsome3_backend.SET_PROPERTY_MODE.PropModeAppend


class KEYSYM_GROUPS(int, Enum):
    """Specifies the index of the keysym group to lock. Enum used by function `x_kb_lock_group()`"""

    XkbGroup1Index = orcsome3_backend.KB_GROUP_INDEX.XkbGroup1Index
    XkbGroup2Index = orcsome3_backend.KB_GROUP_INDEX.XkbGroup2Index
    XkbGroup3Index = orcsome3_backend.KB_GROUP_INDEX.XkbGroup3Index
    XkbGroup4Index = orcsome3_backend.KB_GROUP_INDEX.XkbGroup4Index


class XWindowChanges:
    """Values for `XConfigureWindow` (`XWindowChanges`). Unset fields stay `None` and are omitted from the mask."""

    class StackMode(int, Enum):
        Above = orcsome3_backend.WINDOW_STACKING_METHOD.Above
        Below = orcsome3_backend.WINDOW_STACKING_METHOD.Below
        TopIf = orcsome3_backend.WINDOW_STACKING_METHOD.TopIf
        BottomIf = orcsome3_backend.WINDOW_STACKING_METHOD.BottomIf
        Opposite = orcsome3_backend.WINDOW_STACKING_METHOD.Opposite

    def __init__(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        border_width: Optional[int] = None,
        sibling: Optional[TYPES.Cython_Window] = None,
        stack_mode: Optional[StackMode] = None,
    ) -> None:
        self._cython_xwindowchanges: TYPES.Cython_XWindowChanges = orcsome3_backend.PyXWindowChanges._new_from_python_(
            x=x if x is not None else 0,
            y=y if y is not None else 0,
            width=width if width is not None else 0,
            height=height if height is not None else 0,
            border_width=border_width if border_width is not None else 0,
            sibling_window=sibling if sibling is not None else 0,
            stack_mode=stack_mode.value if stack_mode is not None else 0,
        )
        self.x: Optional[int] = x
        self.y: Optional[int] = y
        self.width: Optional[int] = width
        self.height: Optional[int] = height
        self.border_width: Optional[int] = border_width
        self.sibling: Optional[TYPES.Cython_Window] = sibling
        self.stack_mode: Optional[XWindowChanges.StackMode] = stack_mode


class XWindowAttributes:
    """Python view of `XWindowAttributes` (geometry, map state, override-redirect)."""

    class MapState(int, Enum):
        """
        Enum representing the map state of a window.

        - IsUnmapped
        - IsUnviewable
        - IsViewable
        """

        IsUnmapped = orcsome3_backend.WINDOW_MAP_STATE.IsUnmapped
        IsUnviewable = orcsome3_backend.WINDOW_MAP_STATE.IsUnviewable
        IsViewable = orcsome3_backend.WINDOW_MAP_STATE.IsViewable

    def __init__(
        self,
        window: TYPES.Cython_Window,
        x: int,
        y: int,
        width: int,
        height: int,
        border_width: int,
        depth: int,
        root: TYPES.Cython_Window,
        override_redirect: bool,
        map_state: XWindowAttributes.MapState,
    ) -> None:
        self.window: TYPES.Cython_Window = window
        self.x: int = x  # location of window
        self.y: int = y  # location of window
        self.width: int = width  # width of window
        self.height: int = height  # height of window
        self.border_width: int = border_width  # border width of window
        self.depth: int = depth  # depth of window
        self.root: TYPES.Cython_Window = root  # root of screen containing window
        self.override_redirect: bool = override_redirect  # boolean value for override-redirect
        self.map_state: XWindowAttributes.MapState = map_state  # map state of the window

    @classmethod
    def _new_from_cython_xwindowattributes_(
        cls,
        window: TYPES.Cython_Window,
        cython_xwindowattributes: TYPES.Cython_XWindowAttributes,
    ) -> XWindowAttributes:
        x_window_attributes: XWindowAttributes = cls(
            window=window,
            x=int(cython_xwindowattributes.x),
            y=int(cython_xwindowattributes.y),
            width=int(cython_xwindowattributes.width),
            height=int(cython_xwindowattributes.height),
            border_width=int(cython_xwindowattributes.border_width),
            depth=int(cython_xwindowattributes.depth),
            root=TYPES.Cython_Window(cython_xwindowattributes.root),
            override_redirect=bool(cython_xwindowattributes.override_redirect),
            map_state=XWindowAttributes.MapState(int(cython_xwindowattributes.map_state)),
        )
        return x_window_attributes

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items() if not k.startswith('_')])})"


class EventType(NamedTuple):
    """
    Class representation of an event type.

    Attrs:
    - `id`: Id of the event
    - `cython_class`: Cython class representing the event
    - `python_class`: Lambda that returns the python class representing the event
    """

    id: int
    cython_class: Optional[object]
    python_class: Optional[Callable[[], object]]


class XEvent:
    """Base class of all X events."""

    class EVENT_TYPES(Enum):
        """Enum representing the different types of events"""

        # XErrorEvent
        ErrorEvent = EventType(
            id=orcsome3_backend.EVENT_TYPES.ErrorEvent,
            cython_class=orcsome3_backend.PyXErrorEvent,
            python_class=lambda: XErrorEvent,
        )
        # XKeyEvent
        KeyPress = EventType(
            id=orcsome3_backend.EVENT_TYPES.KeyPress,
            cython_class=orcsome3_backend.PyXKeyEvent,
            python_class=lambda: XKeyEvent,
        )
        KeyRelease = EventType(
            id=orcsome3_backend.EVENT_TYPES.KeyRelease,
            cython_class=orcsome3_backend.PyXKeyEvent,
            python_class=lambda: XKeyEvent,
        )
        # XButtonEvent
        ButtonPress = EventType(
            id=orcsome3_backend.EVENT_TYPES.ButtonPress,
            cython_class=orcsome3_backend.PyXButtonEvent,
            python_class=lambda: XButtonEvent,
        )
        ButtonRelease = EventType(
            id=orcsome3_backend.EVENT_TYPES.ButtonRelease,
            cython_class=orcsome3_backend.PyXButtonEvent,
            python_class=lambda: XButtonEvent,
        )
        # XFocusChangeEvent
        FocusIn = EventType(
            id=orcsome3_backend.EVENT_TYPES.FocusIn,
            cython_class=orcsome3_backend.PyXFocusChangeEvent,
            python_class=lambda: XFocusChangeEvent,
        )
        FocusOut = EventType(
            id=orcsome3_backend.EVENT_TYPES.FocusOut,
            cython_class=orcsome3_backend.PyXFocusChangeEvent,
            python_class=lambda: XFocusChangeEvent,
        )
        # XCreateWindowEvent
        CreateNotify = EventType(
            id=orcsome3_backend.EVENT_TYPES.CreateNotify,
            cython_class=orcsome3_backend.PyXCreateWindowEvent,
            python_class=lambda: XCreateWindowEvent,
        )
        # XDestroyWindowEvent
        DestroyNotify = EventType(
            id=orcsome3_backend.EVENT_TYPES.DestroyNotify,
            cython_class=orcsome3_backend.PyXDestroyWindowEvent,
            python_class=lambda: XDestroyWindowEvent,
        )
        # XPropertyEvent
        PropertyNotify = EventType(
            id=orcsome3_backend.EVENT_TYPES.PropertyNotify,
            cython_class=orcsome3_backend.PyXPropertyEvent,
            python_class=lambda: XPropertyEvent,
        )
        # XClientMessageEvent
        ClientMessage = EventType(
            id=orcsome3_backend.EVENT_TYPES.ClientMessage,
            cython_class=orcsome3_backend.PyXClientMessageEvent,
            python_class=lambda: XClientMessageEvent,
        )
        # Generic event
        GenericEvent = EventType(
            id=orcsome3_backend.EVENT_TYPES.GenericEvent,
            cython_class=None,
            python_class=None,
        )
        # XMotionEvent
        MotionNotify = EventType(
            id=orcsome3_backend.EVENT_TYPES.MotionNotify,
            cython_class=None,
            python_class=None,
        )
        # XCrossingEvent
        EnterNotify = EventType(
            id=orcsome3_backend.EVENT_TYPES.EnterNotify,
            cython_class=None,
            python_class=None,
        )
        LeaveNotify = EventType(
            id=orcsome3_backend.EVENT_TYPES.LeaveNotify,
            cython_class=None,
            python_class=None,
        )
        # XExposeEvent
        Expose = EventType(
            id=orcsome3_backend.EVENT_TYPES.Expose,
            cython_class=None,
            python_class=None,
        )
        # XGraphicsExposeEvent
        GraphicsExpose = EventType(
            id=orcsome3_backend.EVENT_TYPES.GraphicsExpose,
            cython_class=None,
            python_class=None,
        )
        # XNoExposeEvent
        NoExpose = EventType(
            id=orcsome3_backend.EVENT_TYPES.NoExpose,
            cython_class=None,
            python_class=None,
        )
        # XVisibilityEvent
        VisibilityNotify = EventType(
            id=orcsome3_backend.EVENT_TYPES.VisibilityNotify,
            cython_class=None,
            python_class=None,
        )
        # XUnmapEvent
        UnmapNotify = EventType(
            id=orcsome3_backend.EVENT_TYPES.UnmapNotify,
            cython_class=orcsome3_backend.PyXUnmapEvent,
            python_class=lambda: XUnmapEvent,
        )
        # XMapEvent
        MapNotify = EventType(
            id=orcsome3_backend.EVENT_TYPES.MapNotify,
            cython_class=orcsome3_backend.PyXMapEvent,
            python_class=lambda: XMapEvent,
        )
        # XMapRequestEvent
        MapRequest = EventType(
            id=orcsome3_backend.EVENT_TYPES.MapRequest,
            cython_class=None,
            python_class=None,
        )
        # XReparentEvent
        ReparentNotify = EventType(
            id=orcsome3_backend.EVENT_TYPES.ReparentNotify,
            cython_class=None,
            python_class=None,
        )
        # XConfigureEvent
        ConfigureNotify = EventType(
            id=orcsome3_backend.EVENT_TYPES.ConfigureNotify,
            cython_class=orcsome3_backend.PyXConfigureEvent,
            python_class=lambda: XConfigureEvent,
        )
        # XGravityEvent
        GravityNotify = EventType(
            id=orcsome3_backend.EVENT_TYPES.GravityNotify,
            cython_class=None,
            python_class=None,
        )
        # XResizeRequestEvent
        ResizeRequest = EventType(
            id=orcsome3_backend.EVENT_TYPES.ResizeRequest,
            cython_class=None,
            python_class=None,
        )
        # XConfigureRequestEvent
        ConfigureRequest = EventType(
            id=orcsome3_backend.EVENT_TYPES.ConfigureRequest,
            cython_class=None,
            python_class=None,
        )
        # XCirculateEvent
        CirculateNotify = EventType(
            id=orcsome3_backend.EVENT_TYPES.CirculateNotify,
            cython_class=None,
            python_class=None,
        )
        # XCirculateRequestEvent
        CirculateRequest = EventType(
            id=orcsome3_backend.EVENT_TYPES.CirculateRequest,
            cython_class=None,
            python_class=None,
        )
        # XSelectionClearEvent
        SelectionClear = EventType(
            id=orcsome3_backend.EVENT_TYPES.SelectionClear,
            cython_class=None,
            python_class=None,
        )
        # XSelectionRequestEvent
        SelectionRequest = EventType(
            id=orcsome3_backend.EVENT_TYPES.SelectionRequest,
            cython_class=None,
            python_class=None,
        )
        # XSelectionEvent
        SelectionNotify = EventType(
            id=orcsome3_backend.EVENT_TYPES.SelectionNotify,
            cython_class=None,
            python_class=None,
        )
        # XColormapEvent
        ColormapNotify = EventType(
            id=orcsome3_backend.EVENT_TYPES.ColormapNotify,
            cython_class=None,
            python_class=None,
        )
        # XMappingEvent
        MappingNotify = EventType(
            id=orcsome3_backend.EVENT_TYPES.MappingNotify,
            cython_class=None,
            python_class=None,
        )
        # XKeymapEvent
        KeymapNotify = EventType(
            id=orcsome3_backend.EVENT_TYPES.KeymapNotify,
            cython_class=None,
            python_class=None,
        )

        @classmethod
        def from_id(cls, id_: int) -> XEvent.EVENT_TYPES:
            cache: Optional[dict[int, XEvent.EVENT_TYPES]] = getattr(cls, "_by_id", None)
            if cache is None:
                cache = {member.value.id: member for member in cls}
                type.__setattr__(cls, "_by_id", cache)
            try:
                return cache[id_]
            except KeyError:
                raise ValueError(f"Invalid id {id_}")

    _cython_event: Optional[TYPES.EVENTS.Cython_XEvent] = None
    _type: Optional[XEvent.EVENT_TYPES] = None
    _serial: Optional[int] = None
    _send_event: Optional[bool] = None
    _display: Optional[TYPES.Cython_Display] = None
    _window: Optional[TYPES.Cython_Window] = None

    @property
    def type(self) -> XEvent.EVENT_TYPES:
        return cast(XEvent.EVENT_TYPES, self._type)

    @type.setter
    def type(self, type: XEvent.EVENT_TYPES) -> None:
        self._type = type

    @property
    def serial(self) -> int:
        return cast(int, self._serial)

    @serial.setter
    def serial(self, serial: int) -> None:
        self._serial = serial

    @property
    def send_event(self) -> bool:
        return cast(bool, self._send_event)

    @send_event.setter
    def send_event(self, send_event: bool) -> None:
        self._send_event = send_event

    @property
    def display(self) -> TYPES.Cython_Display:
        return cast(TYPES.Cython_Display, self._display)

    @display.setter
    def display(self, display: TYPES.Cython_Display) -> None:
        self._display = display

    @property
    def window(self) -> TYPES.Cython_Window:
        return cast(TYPES.Cython_Window, self._window)

    @window.setter
    def window(self, window: TYPES.Cython_Window) -> None:
        self._window = window

    def _set_attributes_from_cython_event_(self, cython_event: TYPES.EVENTS.Cython_XEvent) -> None:
        """
        Set common attributes from the `cython_event`:

        - `_cython_event`
        - `type`
        - `serial`
        - `send_event`
        - `display`
        - `window`
        """
        self._cython_event = cython_event
        self._set_attributes_(
            type=XEvent.EVENT_TYPES.from_id(id_=int(cython_event.type)),
            serial=int(cython_event.serial),
            send_event=bool(cython_event.send_event),
            display=cython_event.display,
            window=TYPES.Cython_Window(cython_event.window),
        )

    def _set_attributes_(
        self,
        type: XEvent.EVENT_TYPES,
        serial: int,
        send_event: bool,
        display: TYPES.Cython_Display,
        window: TYPES.Cython_Window,
    ) -> None:
        """Set common attributes for the event"""
        self.type = type
        self.serial = serial
        self.send_event = send_event
        self.display = display
        self.window = window

    def get_specific_event(
        self,
    ) -> Optional[
        Union[
            XEvent,
            XErrorEvent,
            XButtonEvent,
            XKeyEvent,
            XFocusChangeEvent,
            XCreateWindowEvent,
            XDestroyWindowEvent,
            XMapEvent,
            XUnmapEvent,
            XConfigureEvent,
            XPropertyEvent,
            XClientMessageEvent,
        ]
    ]:
        """
        Returns the specific class related to the event or the base class `XEvent` if no child class exists for the type of event.
        """
        try:
            if self._cython_event is None:
                return None
            if self.type.value.python_class is None:
                return self
            cython_instance: TYPES.EVENTS.Cython_XEvent = self._cython_event._get_specific_event_()
            if self.type == XEvent.EVENT_TYPES.ErrorEvent:
                return XErrorEvent(error_event=cast(TYPES.EVENTS.Cython_XErrorEvent, cython_instance))
            elif self.type == XEvent.EVENT_TYPES.ButtonPress or self.type == XEvent.EVENT_TYPES.ButtonRelease:
                return XButtonEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
                    button_event=cast(TYPES.EVENTS.Cython_XButtonEvent, cython_instance)
                )
            elif self.type == XEvent.EVENT_TYPES.KeyPress or self.type == XEvent.EVENT_TYPES.KeyRelease:
                return XKeyEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
                    key_event=cast(TYPES.EVENTS.Cython_XKeyEvent, cython_instance)
                )
            elif self.type == XEvent.EVENT_TYPES.FocusIn or self.type == XEvent.EVENT_TYPES.FocusOut:
                return XFocusChangeEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
                    focus_change_event=cast(TYPES.EVENTS.Cython_XFocusChangeEvent, cython_instance)
                )
            elif self.type == XEvent.EVENT_TYPES.CreateNotify:
                return XCreateWindowEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
                    create_window_event=cast(TYPES.EVENTS.Cython_XCreateWindowEvent, cython_instance)
                )
            elif self.type == XEvent.EVENT_TYPES.DestroyNotify:
                return XDestroyWindowEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
                    destroy_window_event=cast(TYPES.EVENTS.Cython_XDestroyWindowEvent, cython_instance)
                )
            elif self.type == XEvent.EVENT_TYPES.MapNotify:
                return XMapEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
                    map_event=cast(TYPES.EVENTS.Cython_XMapEvent, cython_instance)
                )
            elif self.type == XEvent.EVENT_TYPES.UnmapNotify:
                return XUnmapEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
                    unmap_event=cast(TYPES.EVENTS.Cython_XUnmapEvent, cython_instance)
                )
            elif self.type == XEvent.EVENT_TYPES.ConfigureNotify:
                return XConfigureEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
                    configure_event=cast(TYPES.EVENTS.Cython_XConfigureEvent, cython_instance)
                )
            elif self.type == XEvent.EVENT_TYPES.PropertyNotify:
                return XPropertyEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
                    property_event=cast(TYPES.EVENTS.Cython_XPropertyEvent, cython_instance)
                )
            elif self.type == XEvent.EVENT_TYPES.ClientMessage:
                return XClientMessageEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
                    client_message_event=cast(TYPES.EVENTS.Cython_XClientMessageEvent, cython_instance)
                )
            return self
        except Exception as e:
            _logger.error(msg=f"An exception occurred getting the specific event. {e}")
            return None

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"


class XErrorEvent(XEvent):
    """X protocol error (`XErrorEvent`) plus a decoded `msg` string."""

    def __init__(self, error_event: TYPES.EVENTS.Cython_XErrorEvent) -> None:
        self._set_attributes_from_cython_event_(cython_event=error_event)
        self.resourceid: int = int(error_event.resourceid)  # resource id
        self.error_code: int = int(error_event.error_code)  # error code of failed request
        self.request_code: int = int(
            error_event.request_code  # Major op-code of failed request
        )
        self.minor_code: int = int(error_event.minor_code)  # Minor op-code of failed request
        self.msg: str = str(error_event.msg)  # Message of the error


class XButtonEvent(XEvent):
    """Pointer button press/release (`XButtonEvent`)."""

    class TYPE(int, Enum):
        ButtonPress = XEvent.EVENT_TYPES.ButtonPress.value.id
        ButtonRelease = XEvent.EVENT_TYPES.ButtonRelease.value.id

    def __init__(
        self,
        display: TYPES.Cython_Display,
        type: XButtonEvent.TYPE,
        window: TYPES.Cython_Window,
        root: TYPES.Cython_Window,
        subwindow: TYPES.Cython_Window,
        button: BUTTONS,
        serial: int = 0,
        send_event: bool = False,
        time: TYPES.Cython_Time = CONSTANTS.CURRENT_TIME,
        x: int = 0,
        y: int = 0,
        x_root: int = 0,
        y_root: int = 0,
        state: Optional[Union[list[Union[BUTTON_MASKS, KEY_MASKS]], int]] = None,
        same_screen: bool = True,
        create_cython_event: bool = True,
    ) -> None:
        type_: XEvent.EVENT_TYPES = XEvent.EVENT_TYPES.from_id(id_=type.value)
        state_: int = 0
        if state is not None:
            if isinstance(state, int):
                state_ = state
            else:
                for state__ in state:
                    state_ |= state__.value
        if create_cython_event and type_.value.cython_class is not None:
            cython_event: TYPES.EVENTS.Cython_XButtonEvent = orcsome3_backend.PyXButtonEvent._new_from_python_(
                type=type_.value.id,
                serial=serial,
                send_event=send_event,
                display=display,
                window=window,
                root=root,
                subwindow=subwindow,
                time=time,
                x=x,
                y=y,
                x_root=x_root,
                y_root=y_root,
                state=state_,
                button=button.value,
                same_screen=same_screen,
            )
            setattr(self, "_cython_event", cython_event)
        self._set_attributes_(
            type=type_,
            serial=serial,
            send_event=send_event,
            display=display,
            window=window,
        )

        self.root: TYPES.Cython_Window = root
        self.subwindow: TYPES.Cython_Window = subwindow
        self.time: TYPES.Cython_Time = time
        self.x: int = x
        self.y: int = y
        self.x_root: int = x_root
        self.y_root: int = y_root
        self.state: int = state_
        self.button: BUTTONS = button
        self.same_screen: bool = same_screen

    @classmethod
    def _new_from_cython_event_(cls, button_event: TYPES.EVENTS.Cython_XButtonEvent) -> XButtonEvent:
        x_button_event: XButtonEvent = cls(
            display=button_event.display,
            type=XButtonEvent.TYPE(button_event.type),
            window=TYPES.Cython_Window(button_event.window),
            root=TYPES.Cython_Window(button_event.root),
            subwindow=TYPES.Cython_Window(button_event.subwindow),
            button=BUTTONS(button_event.button),
            serial=int(button_event.serial),
            send_event=bool(button_event.send_event),
            time=TYPES.Cython_Time(button_event.time),
            x=int(button_event.x),
            y=int(button_event.y),
            x_root=int(button_event.x_root),
            y_root=int(button_event.y_root),
            state=int(button_event.state),
            same_screen=bool(button_event.same_screen),
            create_cython_event=False,
        )
        x_button_event._cython_event = button_event
        return x_button_event


class XKeyEvent(XEvent):
    """Keyboard press/release (`XKeyEvent`)."""

    class TYPE(int, Enum):
        KeyPress = XEvent.EVENT_TYPES.KeyPress.value.id
        KeyRelease = XEvent.EVENT_TYPES.KeyRelease.value.id

    def __init__(
        self,
        display: TYPES.Cython_Display,
        type: XKeyEvent.TYPE,
        window: TYPES.Cython_Window,
        root: TYPES.Cython_Window,
        subwindow: TYPES.Cython_Window,
        keycode: TYPES.Cython_KeyCode,
        serial: int = 0,
        send_event: bool = False,
        time: TYPES.Cython_Time = CONSTANTS.CURRENT_TIME,
        x: int = 0,
        y: int = 0,
        x_root: int = 0,
        y_root: int = 0,
        state: Optional[Union[list[Union[BUTTON_MASKS, KEY_MASKS]], int]] = None,
        same_screen: bool = True,
        create_cython_event: bool = True,
    ) -> None:
        type_: XEvent.EVENT_TYPES = XEvent.EVENT_TYPES.from_id(id_=type.value)
        state_: int = 0
        if state is not None:
            if isinstance(state, int):
                state_ = state
            else:
                for state__ in state:
                    state_ |= state__.value
        if create_cython_event and type_.value.cython_class is not None:
            cython_event: TYPES.EVENTS.Cython_XKeyEvent = orcsome3_backend.PyXKeyEvent._new_from_python_(
                type=type_.value.id,
                serial=serial,
                send_event=send_event,
                display=display,
                window=window,
                root=root,
                subwindow=subwindow,
                time=time,
                x=x,
                y=y,
                x_root=x_root,
                y_root=y_root,
                state=state_,
                keycode=keycode,
                same_screen=same_screen,
            )
            setattr(self, "_cython_event", cython_event)
        self._set_attributes_(
            type=type_,
            serial=serial,
            send_event=send_event,
            display=display,
            window=window,
        )
        self.root: TYPES.Cython_Window = root
        self.subwindow: TYPES.Cython_Window = subwindow
        self.time: TYPES.Cython_Time = time
        self.x: int = x
        self.y: int = y
        self.x_root: int = x_root
        self.y_root: int = y_root
        self.state: int = state_
        self.keycode: TYPES.Cython_KeyCode = keycode
        self.same_screen: bool = same_screen

    @classmethod
    def _new_from_cython_event_(cls, key_event: TYPES.EVENTS.Cython_XKeyEvent) -> XKeyEvent:
        x_key_event: XKeyEvent = cls(
            display=key_event.display,
            type=XKeyEvent.TYPE(key_event.type),
            window=TYPES.Cython_Window(key_event.window),
            root=TYPES.Cython_Window(key_event.root),
            subwindow=TYPES.Cython_Window(key_event.subwindow),
            keycode=TYPES.Cython_KeyCode(key_event.keycode),
            serial=int(key_event.serial),
            send_event=bool(key_event.send_event),
            time=TYPES.Cython_Time(key_event.time),
            x=int(key_event.x),
            y=int(key_event.y),
            x_root=int(key_event.x_root),
            y_root=int(key_event.y_root),
            state=int(key_event.state),
            same_screen=bool(key_event.same_screen),
            create_cython_event=False,
        )
        x_key_event._cython_event = key_event
        return x_key_event


class XFocusChangeEvent(XEvent):
    """FocusIn / FocusOut (`XFocusChangeEvent`)."""

    class TYPE(int, Enum):
        FocusIn = XEvent.EVENT_TYPES.FocusIn.value.id
        FocusOut = XEvent.EVENT_TYPES.FocusOut.value.id

    class NOTIFY_MODE(int, Enum):
        NotifyNormal = orcsome3_backend.NOTIFY_MODES.NotifyNormal
        NotifyGrab = orcsome3_backend.NOTIFY_MODES.NotifyGrab
        NotifyUngrab = orcsome3_backend.NOTIFY_MODES.NotifyUngrab
        NotifyWhileGrabbed = orcsome3_backend.NOTIFY_MODES.NotifyWhileGrabbed

    class NOTIFY_DETAIL(int, Enum):
        NotifyAncestor = orcsome3_backend.NOTIFY_DETAILS.NotifyAncestor
        NotifyVirtual = orcsome3_backend.NOTIFY_DETAILS.NotifyVirtual
        NotifyInferior = orcsome3_backend.NOTIFY_DETAILS.NotifyInferior
        NotifyNonlinear = orcsome3_backend.NOTIFY_DETAILS.NotifyNonlinear
        NotifyNonlinearVirtual = orcsome3_backend.NOTIFY_DETAILS.NotifyNonlinearVirtual
        NotifyPointer = orcsome3_backend.NOTIFY_DETAILS.NotifyPointer
        NotifyPointerRoot = orcsome3_backend.NOTIFY_DETAILS.NotifyPointerRoot
        NotifyDetailNone = orcsome3_backend.NOTIFY_DETAILS.NotifyDetailNone

    def __init__(
        self,
        display: TYPES.Cython_Display,
        type: XFocusChangeEvent.TYPE,
        window: TYPES.Cython_Window,
        detail: XFocusChangeEvent.NOTIFY_DETAIL,
        mode: XFocusChangeEvent.NOTIFY_MODE = NOTIFY_MODE.NotifyNormal,
        serial: int = 0,
        send_event: bool = False,
        create_cython_event: bool = True,
    ) -> None:
        type_: XEvent.EVENT_TYPES = XEvent.EVENT_TYPES.from_id(id_=type.value)
        if create_cython_event and type_.value.cython_class is not None:
            cython_event: TYPES.EVENTS.Cython_XFocusChangeEvent = (
                orcsome3_backend.PyXFocusChangeEvent._new_from_python_(
                    type=type_.value.id,
                    serial=serial,
                    send_event=send_event,
                    display=display,
                    window=window,
                    mode=mode.value,
                    detail=detail.value,
                )
            )
            setattr(self, "_cython_event", cython_event)
        self._set_attributes_(
            type=type_,
            serial=serial,
            send_event=send_event,
            display=display,
            window=window,
        )
        self.mode: XFocusChangeEvent.NOTIFY_MODE = mode
        self.detail: XFocusChangeEvent.NOTIFY_DETAIL = detail

    @classmethod
    def _new_from_cython_event_(cls, focus_change_event: TYPES.EVENTS.Cython_XFocusChangeEvent) -> XFocusChangeEvent:
        x_focus_change_event: XFocusChangeEvent = cls(
            display=focus_change_event.display,
            type=XFocusChangeEvent.TYPE(focus_change_event.type),
            window=TYPES.Cython_Window(focus_change_event.window),
            detail=XFocusChangeEvent.NOTIFY_DETAIL(focus_change_event.detail),
            mode=XFocusChangeEvent.NOTIFY_MODE(focus_change_event.mode),
            serial=int(focus_change_event.serial),
            send_event=bool(focus_change_event.send_event),
            create_cython_event=False,
        )
        x_focus_change_event._cython_event = focus_change_event
        return x_focus_change_event


class XCreateWindowEvent(XEvent):
    """CreateNotify (`XCreateWindowEvent`)."""

    def __init__(
        self,
        display: TYPES.Cython_Display,
        window: TYPES.Cython_Window,
        parent: TYPES.Cython_Window,
        width: int,
        height: int,
        override_redirect: bool,
        x: int = 0,
        y: int = 0,
        border_width: int = 0,
        serial: int = 0,
        send_event: bool = False,
        create_cython_event: bool = True,
    ) -> None:
        type_: XEvent.EVENT_TYPES = XEvent.EVENT_TYPES.CreateNotify
        if create_cython_event and type_.value.cython_class is not None:
            cython_event: TYPES.EVENTS.Cython_XCreateWindowEvent = (
                orcsome3_backend.PyXCreateWindowEvent._new_from_python_(
                    type=type_.value.id,
                    serial=serial,
                    send_event=send_event,
                    display=display,
                    parent=parent,
                    window=window,
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    border_width=border_width,
                    override_redirect=override_redirect,
                )
            )
            setattr(self, "_cython_event", cython_event)
        self._set_attributes_(
            type=type_,
            serial=serial,
            send_event=send_event,
            display=display,
            window=window,
        )
        self.parent: TYPES.Cython_Window = parent
        self.x: int = x
        self.y: int = y
        self.width: int = width
        self.height: int = height
        self.border_width: int = border_width
        self.override_redirect: bool = override_redirect

    @classmethod
    def _new_from_cython_event_(cls, create_window_event: TYPES.EVENTS.Cython_XCreateWindowEvent) -> XCreateWindowEvent:
        x_create_window_event: XCreateWindowEvent = cls(
            display=create_window_event.display,
            parent=TYPES.Cython_Window(create_window_event.parent),
            window=TYPES.Cython_Window(create_window_event.window),
            width=int(create_window_event.width),
            height=int(create_window_event.height),
            override_redirect=bool(create_window_event.override_redirect),
            x=int(create_window_event.x),
            y=int(create_window_event.y),
            border_width=int(create_window_event.border_width),
            serial=int(create_window_event.serial),
            send_event=bool(create_window_event.send_event),
            create_cython_event=False,
        )
        x_create_window_event._cython_event = create_window_event
        return x_create_window_event


class XDestroyWindowEvent(XEvent):
    """DestroyNotify (`XDestroyWindowEvent`)."""

    def __init__(
        self,
        display: TYPES.Cython_Display,
        event: TYPES.Cython_Window,
        window: TYPES.Cython_Window,
        serial: int = 0,
        send_event: bool = False,
        create_cython_event: bool = True,
    ) -> None:
        type_: XEvent.EVENT_TYPES = XEvent.EVENT_TYPES.DestroyNotify
        if create_cython_event and type_.value.cython_class is not None:
            cython_event: TYPES.EVENTS.Cython_XDestroyWindowEvent = (
                orcsome3_backend.PyXDestroyWindowEvent._new_from_python_(
                    type=type_.value.id,
                    serial=serial,
                    send_event=send_event,
                    display=display,
                    event=event,
                    window=window,
                )
            )
            setattr(self, "_cython_event", cython_event)
        self._set_attributes_(
            type=type_,
            serial=serial,
            send_event=send_event,
            display=display,
            window=window,
        )
        self.event: TYPES.Cython_Window = event

    @classmethod
    def _new_from_cython_event_(
        cls, destroy_window_event: TYPES.EVENTS.Cython_XDestroyWindowEvent
    ) -> XDestroyWindowEvent:
        x_destroy_window_event: XDestroyWindowEvent = cls(
            display=destroy_window_event.display,
            event=TYPES.Cython_Window(destroy_window_event.event),
            window=TYPES.Cython_Window(destroy_window_event.window),
            serial=int(destroy_window_event.serial),
            send_event=bool(destroy_window_event.send_event),
            create_cython_event=False,
        )
        x_destroy_window_event._cython_event = destroy_window_event
        return x_destroy_window_event


class XMapEvent(XEvent):
    """MapNotify (`XMapEvent`). `window` is the mapped client; `event` is who selected (parent or self)."""

    def __init__(
        self,
        display: TYPES.Cython_Display,
        event: TYPES.Cython_Window,
        window: TYPES.Cython_Window,
        override_redirect: bool,
        serial: int = 0,
        send_event: bool = False,
        create_cython_event: bool = True,
    ) -> None:
        type_: XEvent.EVENT_TYPES = XEvent.EVENT_TYPES.MapNotify
        if create_cython_event and type_.value.cython_class is not None:
            cython_event: TYPES.EVENTS.Cython_XMapEvent = orcsome3_backend.PyXMapEvent._new_from_python_(
                type=type_.value.id,
                serial=serial,
                send_event=send_event,
                display=display,
                event=event,
                window=window,
                override_redirect=override_redirect,
            )
            setattr(self, "_cython_event", cython_event)
        self._set_attributes_(
            type=type_,
            serial=serial,
            send_event=send_event,
            display=display,
            window=window,
        )
        self.event: TYPES.Cython_Window = event
        self.override_redirect: bool = override_redirect

    @classmethod
    def _new_from_cython_event_(cls, map_event: TYPES.EVENTS.Cython_XMapEvent) -> XMapEvent:
        x_map_event: XMapEvent = cls(
            display=map_event.display,
            event=TYPES.Cython_Window(map_event.event),
            window=TYPES.Cython_Window(map_event.window),
            override_redirect=bool(map_event.override_redirect),
            serial=int(map_event.serial),
            send_event=bool(map_event.send_event),
            create_cython_event=False,
        )
        x_map_event._cython_event = map_event
        return x_map_event


class XUnmapEvent(XEvent):
    """UnmapNotify (`XUnmapEvent`). `from_configure` is True when the unmap is due to a parent configure."""

    def __init__(
        self,
        display: TYPES.Cython_Display,
        event: TYPES.Cython_Window,
        window: TYPES.Cython_Window,
        from_configure: bool = False,
        serial: int = 0,
        send_event: bool = False,
        create_cython_event: bool = True,
    ) -> None:
        type_: XEvent.EVENT_TYPES = XEvent.EVENT_TYPES.UnmapNotify
        if create_cython_event and type_.value.cython_class is not None:
            cython_event: TYPES.EVENTS.Cython_XUnmapEvent = orcsome3_backend.PyXUnmapEvent._new_from_python_(
                type=type_.value.id,
                serial=serial,
                send_event=send_event,
                display=display,
                event=event,
                window=window,
                from_configure=from_configure,
            )
            setattr(self, "_cython_event", cython_event)
        self._set_attributes_(
            type=type_,
            serial=serial,
            send_event=send_event,
            display=display,
            window=window,
        )
        self.event: TYPES.Cython_Window = event
        self.from_configure: bool = from_configure

    @classmethod
    def _new_from_cython_event_(cls, unmap_event: TYPES.EVENTS.Cython_XUnmapEvent) -> XUnmapEvent:
        x_unmap_event: XUnmapEvent = cls(
            display=unmap_event.display,
            event=TYPES.Cython_Window(unmap_event.event),
            window=TYPES.Cython_Window(unmap_event.window),
            from_configure=bool(unmap_event.from_configure),
            serial=int(unmap_event.serial),
            send_event=bool(unmap_event.send_event),
            create_cython_event=False,
        )
        x_unmap_event._cython_event = unmap_event
        return x_unmap_event


class XConfigureEvent(XEvent):
    """ConfigureNotify (`XConfigureEvent`). `x`/`y` are relative to the parent; `above` is the stacking sibling."""

    def __init__(
        self,
        display: TYPES.Cython_Display,
        event: TYPES.Cython_Window,
        window: TYPES.Cython_Window,
        x: int = 0,
        y: int = 0,
        width: int = 0,
        height: int = 0,
        border_width: int = 0,
        above: TYPES.Cython_Window = 0,
        override_redirect: bool = False,
        serial: int = 0,
        send_event: bool = False,
        create_cython_event: bool = True,
    ) -> None:
        type_: XEvent.EVENT_TYPES = XEvent.EVENT_TYPES.ConfigureNotify
        if create_cython_event and type_.value.cython_class is not None:
            cython_event: TYPES.EVENTS.Cython_XConfigureEvent = orcsome3_backend.PyXConfigureEvent._new_from_python_(
                type=type_.value.id,
                serial=serial,
                send_event=send_event,
                display=display,
                event=event,
                window=window,
                x=x,
                y=y,
                width=width,
                height=height,
                border_width=border_width,
                above=above,
                override_redirect=override_redirect,
            )
            setattr(self, "_cython_event", cython_event)
        self._set_attributes_(
            type=type_,
            serial=serial,
            send_event=send_event,
            display=display,
            window=window,
        )
        self.event: TYPES.Cython_Window = event
        self.x: int = x
        self.y: int = y
        self.width: int = width
        self.height: int = height
        self.border_width: int = border_width
        self.above: TYPES.Cython_Window = above
        self.override_redirect: bool = override_redirect

    @classmethod
    def _new_from_cython_event_(cls, configure_event: TYPES.EVENTS.Cython_XConfigureEvent) -> XConfigureEvent:
        x_configure_event: XConfigureEvent = cls(
            display=configure_event.display,
            event=TYPES.Cython_Window(configure_event.event),
            window=TYPES.Cython_Window(configure_event.window),
            x=int(configure_event.x),
            y=int(configure_event.y),
            width=int(configure_event.width),
            height=int(configure_event.height),
            border_width=int(configure_event.border_width),
            above=TYPES.Cython_Window(configure_event.above),
            override_redirect=bool(configure_event.override_redirect),
            serial=int(configure_event.serial),
            send_event=bool(configure_event.send_event),
            create_cython_event=False,
        )
        x_configure_event._cython_event = configure_event
        return x_configure_event


class XPropertyEvent(XEvent):
    """PropertyNotify (`XPropertyEvent`)."""

    class STATE(int, Enum):
        PropertyNewValue = orcsome3_backend.PROPERTY_NOTIFICATION.PropertyNewValue
        PropertyDelete = orcsome3_backend.PROPERTY_NOTIFICATION.PropertyDelete

    def __init__(
        self,
        display: TYPES.Cython_Display,
        window: TYPES.Cython_Window,
        atom: TYPES.Cython_Atom,
        state: STATE,
        serial: int = 0,
        send_event: bool = False,
        time: TYPES.Cython_Time = CONSTANTS.CURRENT_TIME,
        create_cython_event: bool = True,
    ) -> None:
        type_: XEvent.EVENT_TYPES = XEvent.EVENT_TYPES.PropertyNotify
        if create_cython_event and type_.value.cython_class is not None:
            cython_event: TYPES.EVENTS.Cython_XPropertyEvent = orcsome3_backend.PyXPropertyEvent._new_from_python_(
                type=type_.value.id,
                serial=serial,
                send_event=send_event,
                display=display,
                window=window,
                atom=atom,
                time=time,
                state=state.value,
            )
            setattr(self, "_cython_event", cython_event)
        self._set_attributes_(
            type=type_,
            serial=serial,
            send_event=send_event,
            display=display,
            window=window,
        )
        self.atom: TYPES.Cython_Atom = atom
        self.time: TYPES.Cython_Time = time
        self.state: XPropertyEvent.STATE = state

    @classmethod
    def _new_from_cython_event_(cls, property_event: TYPES.EVENTS.Cython_XPropertyEvent) -> XPropertyEvent:
        x_property_event: XPropertyEvent = cls(
            display=property_event.display,
            window=TYPES.Cython_Window(property_event.window),
            atom=TYPES.Cython_Atom(property_event.atom),
            state=XPropertyEvent.STATE(property_event.state),
            serial=int(property_event.serial),
            send_event=bool(property_event.send_event),
            time=TYPES.Cython_Time(property_event.time),
            create_cython_event=False,
        )
        x_property_event._cython_event = property_event
        return x_property_event


class XClientMessageEvent(XEvent):
    """ClientMessage (`XClientMessageEvent`), used for EWMH `_NET_*` requests."""

    def __init__(
        self,
        display: TYPES.Cython_Display,
        window: TYPES.Cython_Window,
        message_type: TYPES.Cython_Atom,
        format_: PROPERTY_FORMAT,
        data: Union[str, list[int]],
        serial: int = 0,
        send_event: bool = False,
        create_cython_event: bool = True,
    ) -> None:
        message_data: array[int] = _build_client_message_array(format_=format_, data=data)
        type_: XEvent.EVENT_TYPES = XEvent.EVENT_TYPES.ClientMessage
        if create_cython_event and type_.value.cython_class is not None:
            cython_event: TYPES.EVENTS.Cython_XClientMessageEvent = (
                orcsome3_backend.PyXClientMessageEvent._new_from_python_(
                    type=type_.value.id,
                    serial=serial,
                    send_event=send_event,
                    display=display,
                    window=window,
                    message_type=message_type,
                    format=format_.value[0],
                    data=message_data,
                )
            )
            setattr(self, "_cython_event", cython_event)
        self._set_attributes_(
            type=type_,
            serial=serial,
            send_event=send_event,
            display=display,
            window=window,
        )
        self.message_type: TYPES.Cython_Atom = message_type
        self.format_: PROPERTY_FORMAT = format_
        self.data: array[int] = message_data

    @classmethod
    def _new_from_cython_event_(
        cls, client_message_event: TYPES.EVENTS.Cython_XClientMessageEvent
    ) -> XClientMessageEvent:
        x_client_message_event: XClientMessageEvent = cls(
            display=client_message_event.display,
            window=TYPES.Cython_Window(client_message_event.window),
            message_type=TYPES.Cython_Atom(client_message_event.message_type),
            format_=PROPERTY_FORMAT.new_from_value(value=client_message_event.format.value[0]),
            data=client_message_event.data.tolist(),
            serial=int(client_message_event.serial),
            send_event=bool(client_message_event.send_event),
            create_cython_event=False,
        )
        x_client_message_event._cython_event = client_message_event
        return x_client_message_event


class XScreenSaverInfo:
    """Result of `XScreenSaverQueryInfo`."""

    class State(int, Enum):
        Off = orcsome3_backend.SCREENSAVER_STATE.ScreenSaverOff
        On = orcsome3_backend.SCREENSAVER_STATE.ScreenSaverOn
        Cycle = orcsome3_backend.SCREENSAVER_STATE.ScreenSaverCycle
        Disabled = orcsome3_backend.SCREENSAVER_STATE.ScreenSaverDisabled

    class Kind(int, Enum):
        Blanked = orcsome3_backend.SCREENSAVER_KIND.ScreenSaverBlanked
        Internal = orcsome3_backend.SCREENSAVER_KIND.ScreenSaverInternal
        External = orcsome3_backend.SCREENSAVER_KIND.ScreenSaverExternal

    def __init__(
        self,
        window: TYPES.Cython_Window,
        state: int,
        kind: int,
        til_or_since: int,
        idle: int,
        event_mask: int,
    ) -> None:
        self.window: TYPES.Cython_Window = window  # screen saver window
        self.state: XScreenSaverInfo.State = XScreenSaverInfo.State(state)
        self.kind: XScreenSaverInfo.Kind = XScreenSaverInfo.Kind(kind)
        self.til_or_since: int = til_or_since  # time til or since screen saver (milliseconds)
        self.idle: int = idle  # total time since last user input (milliseconds)
        self.event_mask: int = event_mask  # currently selected events for this client

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items() if not k.startswith('_')])})"


class XkbStateRec(NamedTuple):
    """Class representing Xkb keyboard state"""

    group: int
    base_group: int
    latched_group: int
    locked_group: int
    mods: int
    base_mods: int
    latched_mods: int
    locked_mods: int
    compat_state: int
    grab_mods: int
    compat_grab_mods: int
    lookup_mods: int
    compat_lookup_mods: int
    ptr_buttons: int

    @classmethod
    def new(cls, state: TYPES.Cython_XkbStateRec) -> XkbStateRec:
        """Copy fields from the Cython Xkb state struct."""
        return cls(
            group=int(state.group),
            base_group=int(state.base_group),
            latched_group=int(state.latched_group),
            locked_group=int(state.locked_group),
            mods=int(state.mods),
            base_mods=int(state.base_mods),
            latched_mods=int(state.latched_mods),
            locked_mods=int(state.locked_mods),
            compat_state=int(state.compat_state),
            grab_mods=int(state.grab_mods),
            compat_grab_mods=int(state.compat_grab_mods),
            lookup_mods=int(state.lookup_mods),
            compat_lookup_mods=int(state.compat_lookup_mods),
            ptr_buttons=int(state.ptr_buttons),
        )


class XWindowGeometry(NamedTuple):
    """
    Class representing the geometry of a window.

    Attrs:
    - `x`: Location of the drawable
    - `y`: Location of the drawable
    - `width`: Dimension of the drawable
    - `height`: Dimension of the drawable


    For a window, `x` and `y` coordinates specify the upper-left outer corner relative to its parent's origin.
    For pixmaps, these coordinates are always zero.

    For a window, `width` and `height` dimensions specify the inside size, not including the border.
    """

    window: TYPES.Cython_Window
    root: TYPES.Cython_Window
    x: int
    y: int
    width: int
    height: int
    border_width: int
    depth: int


class XWindowTree(NamedTuple):
    """
    Class representing the tree of a window.

    Attrs:
    - `window`: window
    - `root`: Root window
    - `parent`: Parent window
    - `children`: Children windows
    """

    window: TYPES.Cython_Window
    root: TYPES.Cython_Window
    parent: TYPES.Cython_Window
    children: list[TYPES.Cython_Window]


class PROPERTY_FORMAT(tuple[int, str], Enum):
    """
    Enum representing the valid formats when getting/setting a property.

    - CHAR: Format with value 8. The value of the property is a char array
    - SHORT: Format with value 16. The value of the property is a short array
    - LONG: Format with value 32. The value of the property is a long array
    """

    CHAR = (8, "b")
    SHORT = (16, "h")
    LONG = (32, "l")

    @classmethod
    def new_from_value(cls, value: Union[int, str]) -> PROPERTY_FORMAT:
        """Look up by bit width (`8`/`16`/`32`) or array typecode (`b`/`h`/`l`)."""
        for member in cls:
            if value in member:
                return member
        raise ValueError(f"The value {value} is not in the enum members")


def _build_client_message_array(format_: PROPERTY_FORMAT, data: Union[str, list[int]]) -> array[int]:
    """Build a typed array payload for XClientMessageEvent matching the X11 format field."""
    if format_ == PROPERTY_FORMAT.CHAR:
        chars: list[int] = list(data.encode()) if isinstance(data, str) else list(data)
        return array("b", (chars + [0] * 20)[:20])
    if isinstance(data, str):
        raise ValueError(f"Invalid data type for format {format_}, expected list[int]")
    item_count: int = 10 if format_ == PROPERTY_FORMAT.SHORT else 5
    return array(format_.value[1], (list(data) + [0] * item_count)[:item_count])


class WindowProperty(NamedTuple):
    """
    Class used to represent the property of a window

    Attributes:
      - `window`: Related window
      - `property_name`: Name of the property.
      - `type_`: Name of the type of the property.
      - `atom_type`: Atom of the type of the property.
      - `format_`: Format of the property. See enum `orcsome3.libs.xlib.PROPERTY_FORMAT`.
      - `property_data`: Actual data of the property, it must be an array of char ('b'), short ('h') or long ('l').

    """

    window: TYPES.Cython_Window
    property_name: str
    type_: str
    atom_type: TYPES.Cython_Atom
    format_: PROPERTY_FORMAT
    property_data: array[int]

    def get_int_list(self) -> list[int]:
        """Get list of int from the array when the format is not `CHAR`, else returns an empty list."""
        if self.format_ == PROPERTY_FORMAT.CHAR:
            return []
        return self.property_data.tolist()

    def get_string_list(self) -> list[str]:
        """Get list of string from the array when the format is `CHAR`, else returns an empty list."""
        if self.format_ != PROPERTY_FORMAT.CHAR:
            return []
        null_byte: bytes = b"\x00"
        return [part.decode() for part in self.property_data.tobytes().split(sep=null_byte) if part]


class DPMSInfo:
    """DPMS enabled flag and current power level."""

    class PowerLEvel(int, Enum):
        DPMSModeOn = orcsome3_backend.DPMS_POWER_LEVEL.DPMSModeOn
        DPMSModeStandby = orcsome3_backend.DPMS_POWER_LEVEL.DPMSModeStandby
        DPMSModeSuspend = orcsome3_backend.DPMS_POWER_LEVEL.DPMSModeSuspend
        DPMSModeOff = orcsome3_backend.DPMS_POWER_LEVEL.DPMSModeOff

    def __init__(self, dpms_info: TYPES.Cython_DPMSInfo) -> None:
        self.state: bool = bool(dpms_info.state)
        self.power_level: DPMSInfo.PowerLEvel = DPMSInfo.PowerLEvel(dpms_info.power_level)

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items() if not k.startswith('_')])})"


def x_open_display(display_name: Optional[str] = None) -> TYPES.Cython_Display:
    """
    Connect to the X server. Wrapper for `XOpenDisplay`. Returns a `orcsome3.libs.xlib.TYPES.Cython_Display` object.

    Params:
    - `display_name`: Specifies the hardware display name, which determines the display and communications
                      domain to be used. On a POSIX-conformant system, if the display_name is `None`,
                      it defaults to the value of the `DISPLAY` environment variable.
    """
    display: Optional[TYPES.Cython_Display] = orcsome3_backend.PyXOpenDisplay(display_name=display_name)
    if display is None:
        raise Exception("Can't open display")
    return display


def x_close_display(display: TYPES.Cython_Display) -> None:
    """Disconnect from X server. Wrapper for `XCloseDisplay`."""
    orcsome3_backend.PyXCloseDisplay(display=display)


def get_default_root_window(display: TYPES.Cython_Display) -> TYPES.Cython_Window:
    """Returns the root window for `display`"""
    return TYPES.Cython_Window(orcsome3_backend.PyXDefaultRootWindow(display=display))


def get_connection_number(display: TYPES.Cython_Display) -> int:
    """
    Return a connection number for `display`.
    On a POSIX-conformant system, this is the file descriptor of the connection.
    """
    return int(orcsome3_backend.PyXConnectionNumber(display=display))


def x_create_window(
    display: TYPES.Cython_Display,
    parent: TYPES.Cython_Window,
    width: int = 32,
    height: int = 32,
) -> TYPES.Cython_Window:
    """InputOnly override-redirect window at (0, 0). Wrapper for `XCreateWindow`."""
    return TYPES.Cython_Window(
        orcsome3_backend.PyXCreateOverrideRedirectWindow(display=display, parent=parent, width=width, height=height)
    )


def x_map_window(display: TYPES.Cython_Display, window: TYPES.Cython_Window) -> None:
    """Wrapper for `XMapWindow`"""
    _ = orcsome3_backend.PyXMapWindow(display=display, window=window)


def x_destroy_window(display: TYPES.Cython_Display, window: TYPES.Cython_Window) -> None:
    """Wrapper for `XDestroyWindow`"""
    _ = orcsome3_backend.PyXDestroyWindow(display=display, window=window)


def x_set_input_focus(
    display: TYPES.Cython_Display,
    window: TYPES.Cython_Window,
    revert_to: int = CONSTANTS.REVERT_TO_POINTER_ROOT,
) -> None:
    """Wrapper for `XSetInputFocus`"""
    _ = orcsome3_backend.PyXSetInputFocus(display=display, window=window, revert_to=revert_to)


def x_get_input_focus(display: TYPES.Cython_Display) -> tuple[TYPES.Cython_Window, int]:
    """Wrapper for `XGetInputFocus`. Returns `(focus_window, revert_to)`."""
    window: int
    revert_to: int
    window, revert_to = orcsome3_backend.PyXGetInputFocus(display=display)
    return TYPES.Cython_Window(window), revert_to


def x_grab_key(
    display: TYPES.Cython_Display,
    window: TYPES.Cython_Window,
    owner_events: bool,
    pointer_mode: GRAB_MODE,
    keyboard_mode: GRAB_MODE,
    keycode: TYPES.Cython_KeyCode = CONSTANTS.KB.ANY_KEY,
    modifiers: int = KEY_MASKS.AnyModifier,
) -> None:
    """Wrapper for `XGrabKey`"""
    _ = orcsome3_backend.PyXGrabKey(
        display=display,
        keycode=keycode,
        modifiers=modifiers,
        window=window,
        owner_events=owner_events,
        pointer_mode=pointer_mode.value,
        keyboard_mode=keyboard_mode.value,
    )


def x_ungrab_key(
    display: TYPES.Cython_Display,
    keycode: int,
    modifiers: int,
    window: TYPES.Cython_Window,
) -> None:
    """Wrapper for `XUngrabKey`"""
    _ = orcsome3_backend.PyXUngrabKey(display=display, keycode=keycode, modifiers=modifiers, window=window)


def x_grab_button(
    display: TYPES.Cython_Display,
    window: TYPES.Cython_Window,
    button: int,
    modifiers: int,
    owner_events: bool,
    event_mask: int,
    pointer_mode: GRAB_MODE,
    keyboard_mode: GRAB_MODE,
    confine_to: TYPES.Cython_Window = 0,
    cursor: int = 0,
) -> None:
    """Wrapper for `XGrabButton`. `confine_to`/`cursor` of 0 is X `None`."""
    _ = orcsome3_backend.PyXGrabButton(
        display=display,
        button=button,
        modifiers=modifiers,
        window=window,
        owner_events=owner_events,
        event_mask=event_mask,
        pointer_mode=pointer_mode.value,
        keyboard_mode=keyboard_mode.value,
        confine_to=confine_to,
        cursor=cursor,
    )


def x_ungrab_button(
    display: TYPES.Cython_Display,
    button: int,
    modifiers: int,
    window: TYPES.Cython_Window,
) -> None:
    """Wrapper for `XUngrabButton`"""
    _ = orcsome3_backend.PyXUngrabButton(display=display, button=button, modifiers=modifiers, window=window)


def x_select_input(
    display: TYPES.Cython_Display,
    window: TYPES.Cython_Window,
    event_mask: Union[list[INPUT_EVENT_MASKS], INPUT_EVENT_MASKS] = INPUT_EVENT_MASKS.NoEventMask,
) -> None:
    """Wrapper for `XSelectInput`"""
    mask: int = 0
    if isinstance(event_mask, list):
        mask = INPUT_EVENT_MASKS.NoEventMask.value
        for em in event_mask:
            mask |= em.value
    else:
        mask = event_mask.value
    _ = orcsome3_backend.PyXSelectInput(display=display, window=window, event_mask=mask)


def x_configure_window(
    display: TYPES.Cython_Display,
    window: TYPES.Cython_Window,
    value_mask: Union[list[WINDOW_VALUE_MASK], WINDOW_VALUE_MASK],
    window_changes: XWindowChanges,
) -> None:
    """Wrapper for `XConfigureWindow`"""
    value_mask_: int = 0
    if isinstance(value_mask, list):
        for mask in value_mask:
            value_mask_ |= mask.value
    else:
        value_mask_ = value_mask.value
    _ = orcsome3_backend.PyXConfigureWindow(
        display=display,
        window=window,
        value_mask=value_mask_,
        window_changes=window_changes._cython_xwindowchanges,  # pyright: ignore[reportPrivateUsage]
    )


def x_sync(display: TYPES.Cython_Display, discard: bool) -> None:
    """Wrapper for `XSync`"""
    _ = orcsome3_backend.PyXSync(display=display, discard=discard)


def x_set_error_handler(
    handler: Callable[[TYPES.Cython_Display, TYPES.EVENTS.Cython_XErrorEvent], None],
) -> None:
    """Wrapper for `XSetErrorHandler`"""
    _ = orcsome3_backend.PyXSetErrorHandler(handler=handler)


def x_get_window_property(
    display: TYPES.Cython_Display, window: TYPES.Cython_Window, property_: str
) -> Optional[WindowProperty]:
    """Wrapper for `XGetWindowProperty`"""
    result: Optional[tuple[array[int], TYPES.Cython_Atom, str]] = orcsome3_backend.PyXGetWindowProperty(
        display=display, window=window, property_=property_
    )
    if result is None:
        return None
    property_data, atom_type, type_name = result
    resolved_type: str = type_name if type_name else (x_get_atom_name(display=display, atom=atom_type) or "")
    try:
        prop_format: PROPERTY_FORMAT = PROPERTY_FORMAT.new_from_value(value=property_data.typecode)
    except ValueError:
        _logger.warning("Unsupported property format %r for %s", property_data.typecode, property_)
        return None
    return WindowProperty(
        window=window,
        property_name=property_,
        type_=resolved_type,
        atom_type=atom_type,
        format_=prop_format,
        property_data=property_data,
    )


def x_change_window_property(
    display: TYPES.Cython_Display,
    window_property: WindowProperty,
    mode: SET_PROPERTY_MODE = SET_PROPERTY_MODE.PropModeReplace,
) -> bool:
    """Wrapper for `XChangeProperty`.

    `window_property.property_data` must use the array typecode that matches
    `window_property.format_` (b/h/l); the Cython layer sends it as-is to X11.
    """
    return bool(
        orcsome3_backend.PyXChangeProperty(
            display=display,
            window=window_property.window,
            property_name=window_property.property_name,
            atom_type=window_property.atom_type,
            format_=window_property.format_.value[0],
            mode=mode.value,
            property_data=window_property.property_data,
        )
    )


def x_get_window_attributes(display: TYPES.Cython_Display, window: TYPES.Cython_Window) -> Optional[XWindowAttributes]:
    """Wrapper for `XGetWindowAttributes`"""
    attrs: Optional[TYPES.Cython_XWindowAttributes] = orcsome3_backend.PyXGetWindowAttributes(
        display=display, window=window
    )
    if attrs is None:
        return None

    return XWindowAttributes._new_from_cython_xwindowattributes_(  # pyright:ignore[reportPrivateUsage]
        window=window, cython_xwindowattributes=attrs
    )


def x_get_window_tree(display: TYPES.Cython_Display, window: TYPES.Cython_Window) -> Optional[XWindowTree]:
    """Wrapper for `XQueryTree`"""
    result: Optional[TYPES.Cython_XWindowTree] = orcsome3_backend.PyXQueryTree(display=display, window=window)
    if result is None:
        return None

    return XWindowTree(
        window=result.window,
        root=result.root,
        parent=result.parent,
        children=result.children,
    )


def x_get_window_geometry(display: TYPES.Cython_Display, window: TYPES.Cython_Window) -> Optional[XWindowGeometry]:
    """Wrapper for `XGetGeometry`"""
    window_geometry: Optional[TYPES.Cython_XWindowGeometry] = orcsome3_backend.PyXGetGeometry(
        display=display, window=window
    )
    if window_geometry is None:
        return None

    return XWindowGeometry(
        window=window,
        root=window_geometry.root,
        x=window_geometry.x,
        y=window_geometry.y,
        width=window_geometry.width,
        height=window_geometry.height,
        border_width=window_geometry.border_width,
        depth=window_geometry.depth,
    )


def x_get_screen_saver_info(display: TYPES.Cython_Display, drawable: TYPES.Cython_Window) -> Optional[XScreenSaverInfo]:
    """Wrapper for `XScreenSaverQueryInfo`"""
    result: Optional[TYPES.Cython_XScreenSaverInfo] = orcsome3_backend.PyXScreenSaverQueryInfo(
        display=display, window=drawable
    )
    if result is None:
        return None

    return XScreenSaverInfo(
        window=result.window,
        state=result.state,
        kind=result.kind,
        til_or_since=result.til_or_since,
        idle=result.idle,
        event_mask=result.event_mask,
    )


def x_kb_get_state(display: TYPES.Cython_Display, device_spec: int = CONSTANTS.KB.X_KB_USE_CORE_KBD) -> XkbStateRec:
    """Wrapper for `XkbGetState`"""
    result: TYPES.Cython_XkbStateRec = orcsome3_backend.PyXkbGetState(display=display, device_spec=device_spec)
    return XkbStateRec.new(state=result)


def x_kb_lock_group(
    display: TYPES.Cython_Display,
    group: KEYSYM_GROUPS,
    device_spec: int = CONSTANTS.KB.X_KB_USE_CORE_KBD,
) -> bool:
    """Wrapper for `XkbLockGroup`"""
    result: bool = bool(orcsome3_backend.PyXkbLockGroup(display=display, device_spec=device_spec, group=group.value))
    x_flush(display=display)
    return result


def x_flush(display: TYPES.Cython_Display) -> None:
    """Wrapper for `XFlush`"""
    _ = orcsome3_backend.PyXFlush(display=display)


def xtest_query_extension(display: TYPES.Cython_Display) -> bool:
    """True if the XTEST extension is present. Wrapper for `XTestQueryExtension`."""
    return bool(orcsome3_backend.PyXTestQueryExtension(display=display))


def xtest_fake_key_event(display: TYPES.Cython_Display, keycode: int, press: bool, delay: int = 0) -> None:
    """Wrapper for `XTestFakeKeyEvent`"""
    _ = orcsome3_backend.PyXTestFakeKeyEvent(display=display, keycode=keycode, press=press, delay=delay)
    x_flush(display=display)


def xtest_fake_button_event(display: TYPES.Cython_Display, button: int, press: bool, delay: int = 0) -> None:
    """Wrapper for `XTestFakeButtonEvent`"""
    _ = orcsome3_backend.PyXTestFakeButtonEvent(display=display, button=button, press=press, delay=delay)
    x_flush(display=display)


def xtest_fake_motion_event(display: TYPES.Cython_Display, x: int, y: int, screen: int = -1, delay: int = 0) -> None:
    """Wrapper for `XTestFakeMotionEvent`. `screen=-1` is the screen the pointer is on."""
    _ = orcsome3_backend.PyXTestFakeMotionEvent(display=display, screen=screen, x=x, y=y, delay=delay)
    x_flush(display=display)


def x_get_atom_name(display: TYPES.Cython_Display, atom: TYPES.Cython_Atom) -> Optional[str]:
    """
    Returns the name associated with an Atom if the Atom exists.

    Wrapper for `XGetAtomName`
    """
    result: str = str(orcsome3_backend.PyXGetAtomName(display=display, atom=atom))
    return result if len(result.strip()) else None


def x_get_atom_from_name(
    display: TYPES.Cython_Display, atom_name: str, create_if_not_exists: bool
) -> TYPES.Cython_Atom:
    """Wrapper for XInternAtom"""
    atom: TYPES.Cython_Atom = orcsome3_backend.PyXInternAtom(
        display=display, atom_name=atom_name, only_if_exists=not create_if_not_exists
    )
    return atom


def x_send_event(
    display: TYPES.Cython_Display,
    window: TYPES.Cython_Window,
    propagate: bool,
    xevent: XEvent,
    event_masks: Union[list[INPUT_EVENT_MASKS], INPUT_EVENT_MASKS] = INPUT_EVENT_MASKS.NoEventMask,
) -> None:
    """Wrapper for `XSendEvent`"""

    if xevent._cython_event is None:  # pyright: ignore[reportPrivateUsage]
        return

    event_mask: int = 0
    if isinstance(event_masks, list):
        for event_mask_ in event_masks:
            event_mask |= event_mask_.value
    else:
        event_mask = event_masks.value

    _ = orcsome3_backend.PyXSendEvent(
        display=display,
        window=window,
        propagate=propagate,
        event_mask=event_mask,
        xevent=xevent._cython_event,  # pyright: ignore[reportPrivateUsage]
    )


def set_window_icon(display: TYPES.Cython_Display, window: TYPES.Cython_Window, icon_path: Path) -> bool:
    """Encode `icon_path` and set `_NET_WM_ICON`. True on success."""
    return bool(orcsome3_backend.PySetWindowIcon(display=display, window=window, filepath=icon_path))


def render_svg_to_argb(svg_path: Path, size: int) -> Optional[bytes]:
    """Rasterize `svg_path` to `size`x`size` raw ARGB32 pixels (network byte order: A,R,G,B per
    pixel) via resvg. `None` if the file can't be parsed. No X display or window involved.
    """
    result: Optional[bytes] = orcsome3_backend.PyRenderSvgToArgb(filepath=str(svg_path), size=size)
    return result


def x_string_to_keysym(string: str) -> TYPES.Cython_KeySym:
    """Wrapper for `XStringToKeysym`"""
    return TYPES.Cython_KeySym(orcsome3_backend.PyXStringToKeysym(string=string))


def x_keysym_to_keycode(display: TYPES.Cython_Display, keysym: TYPES.Cython_KeySym) -> TYPES.Cython_KeyCode:
    """Wrapper for `XKeysymToKeycode`"""
    return TYPES.Cython_KeyCode(orcsome3_backend.PyXKeysymToKeycode(display=display, keysym=keysym))


def x_pending(display: TYPES.Cython_Display) -> int:
    """Wrapper for `XPending`"""
    return int(orcsome3_backend.PyXPending(display=display))


def x_next_event(
    display: TYPES.Cython_Display,
) -> Union[
    XEvent,
    XErrorEvent,
    XButtonEvent,
    XKeyEvent,
    XFocusChangeEvent,
    XCreateWindowEvent,
    XDestroyWindowEvent,
    XMapEvent,
    XUnmapEvent,
    XConfigureEvent,
    XPropertyEvent,
    XClientMessageEvent,
]:
    """Wrapper for `XNextEvent`"""
    cython_xevent: TYPES.EVENTS.Cython_XEvent = orcsome3_backend.PyXNextEvent(display=display)
    if isinstance(cython_xevent, orcsome3_backend.PyXKeyEvent):
        return XKeyEvent._new_from_cython_event_(key_event=cython_xevent)  # pyright: ignore[reportPrivateUsage]
    if isinstance(cython_xevent, orcsome3_backend.PyXButtonEvent):
        return XButtonEvent._new_from_cython_event_(button_event=cython_xevent)  # pyright: ignore[reportPrivateUsage]
    if isinstance(cython_xevent, orcsome3_backend.PyXFocusChangeEvent):
        return XFocusChangeEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
            focus_change_event=cython_xevent
        )
    if isinstance(cython_xevent, orcsome3_backend.PyXCreateWindowEvent):
        return XCreateWindowEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
            create_window_event=cython_xevent
        )
    if isinstance(cython_xevent, orcsome3_backend.PyXDestroyWindowEvent):
        return XDestroyWindowEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
            destroy_window_event=cython_xevent
        )
    if isinstance(cython_xevent, orcsome3_backend.PyXMapEvent):
        return XMapEvent._new_from_cython_event_(map_event=cython_xevent)  # pyright: ignore[reportPrivateUsage]
    if isinstance(cython_xevent, orcsome3_backend.PyXUnmapEvent):
        return XUnmapEvent._new_from_cython_event_(unmap_event=cython_xevent)  # pyright: ignore[reportPrivateUsage]
    if isinstance(cython_xevent, orcsome3_backend.PyXConfigureEvent):
        return XConfigureEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
            configure_event=cython_xevent
        )
    if isinstance(cython_xevent, orcsome3_backend.PyXPropertyEvent):
        return XPropertyEvent._new_from_cython_event_(property_event=cython_xevent)  # pyright: ignore[reportPrivateUsage]
    if isinstance(cython_xevent, orcsome3_backend.PyXClientMessageEvent):
        return XClientMessageEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
            client_message_event=cython_xevent
        )
    if isinstance(cython_xevent, orcsome3_backend.PyXErrorEvent):
        return XErrorEvent(error_event=cython_xevent)
    xevent: XEvent = XEvent()
    xevent._set_attributes_from_cython_event_(cython_event=cython_xevent)  # pyright: ignore[reportPrivateUsage]
    return xevent


def dpms_info(display: TYPES.Cython_Display) -> DPMSInfo:
    """Wrapper for `DPMSInfo`"""
    return DPMSInfo(dpms_info=orcsome3_backend.PyGetDPMSInfo(display=display))


def dpms_enable(display: TYPES.Cython_Display) -> bool:
    """Wrapper for `DPMSEnable`"""
    return bool(orcsome3_backend.PyDPMSEnable(display=display))


def dpms_disable(display: TYPES.Cython_Display) -> bool:
    """Wrapper for `DPMSDisable`"""
    return bool(orcsome3_backend.PyDPMSDisable(display=display))


def reset_dpms(display: TYPES.Cython_Display) -> None:
    """If DPMS is enabled, disable then re-enable it so the display wakes / timer resets."""
    dpms_info_: DPMSInfo = dpms_info(display=display)
    if dpms_info_.state:
        _ = dpms_disable(display=display)
        _ = dpms_enable(display=display)


def default_error_handler(__display__: TYPES.Cython_Display, error: TYPES.EVENTS.Cython_XErrorEvent) -> None:
    """Default callback for errors"""
    err: XErrorEvent = XErrorEvent(error_event=error)
    msg_resource: str = f"{'0x%0.2X' % int(err.resourceid)}:{int(err.resourceid)}"
    _logger.error(msg=f"{err.msg} ({msg_resource})")
