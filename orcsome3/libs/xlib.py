from __future__ import annotations

import logging
from array import array
from enum import Enum
from pathlib import Path
from typing import Callable, NamedTuple, Optional, Union, cast, override

# Try to import shared library orcsome3_backend.cpython-xxx-x86_64-linux-gnu.so, it looks for standard locations at sys.path,
# to specify another location use env var PYTHONPATH (PYTHONPATH="/custom/dir:$PYTHONPATH")
import orcsome3_backend  # pyright: ignore[reportMissingImports]

# Import TypeAlias from module typing_extensions to make it compatible with python 3.8
from typing_extensions import TypeAlias

from orcsome3.utils import CythonClass, CythonWrapper, Final

# Globals
_logger: logging.Logger = logging.getLogger(name=__name__)
_cython_wrapper: CythonWrapper = CythonWrapper(cython_module=orcsome3_backend)  # Global Cython Wrapper instance


class TYPES(metaclass=Final):
    """Type aliases for Cython Data Types"""

    Cython_Atom: TypeAlias = int
    Cython_Window: TypeAlias = int
    Cython_KeySym: TypeAlias = int
    Cython_KeyCode: TypeAlias = int
    Cython_Time: TypeAlias = int

    class Cython_Display(CythonClass):
        cython_class: object = _cython_wrapper.get(name="PyDisplay")

        def __init__(self, cython_instance: object) -> None:
            super().__init__(cython_class_instance=cython_instance)

    class Cython_XWindowChanges(CythonClass):
        cython_class: object = _cython_wrapper.get(name="PyXWindowChanges")

        def __init__(self, cython_instance: object) -> None:
            super().__init__(cython_class_instance=cython_instance)

    class Cython_XWindowAttributes(CythonClass):
        cython_class: object = _cython_wrapper.get(name="PyXWindowAttributes")

        def __init__(self, cython_instance: object) -> None:
            super().__init__(cython_class_instance=cython_instance)

    class Cython_XWindowTree(CythonClass):
        cython_class: object = _cython_wrapper.get(name="PyXWindowTree")

        def __init__(self, cython_instance: object) -> None:
            super().__init__(cython_class_instance=cython_instance)

    class Cython_XWindowGeometry(CythonClass):
        cython_class: object = _cython_wrapper.get(name="PyXWindowGeometry")

        def __init__(self, cython_instance: object) -> None:
            super().__init__(cython_class_instance=cython_instance)

    class Cython_XScreenSaverInfo(CythonClass):
        cython_class: object = _cython_wrapper.get(name="PyXScreenSaverInfo")

        def __init__(self, cython_instance: object) -> None:
            super().__init__(cython_class_instance=cython_instance)

    class Cython_XkbStateRec(CythonClass):
        cython_class: object = _cython_wrapper.get(name="PyXkbStateRec")

        def __init__(self, cython_instance: object) -> None:
            super().__init__(cython_class_instance=cython_instance)

    class Cython_DPMSInfo(CythonClass):
        cython_class: object = _cython_wrapper.get(name="PyDPMSInfo")

        def __init__(self, cython_instance: object) -> None:
            super().__init__(cython_class_instance=cython_instance)

    class EVENTS(metaclass=Final):
        """Cython events objects"""

        class Cython_XEvent(CythonClass):
            cython_class: object = _cython_wrapper.get(name="PyXEvent")

            def __init__(self, cython_instance: object) -> None:
                super().__init__(cython_class_instance=cython_instance)

        class Cython_XButtonEvent(Cython_XEvent):
            cython_class: object = _cython_wrapper.get(name="PyXButtonEvent")

            def __init__(self, cython_instance: object) -> None:
                super().__init__(cython_instance=cython_instance)

        class Cython_XKeyEvent(Cython_XEvent):
            cython_class: object = _cython_wrapper.get(name="PyXKeyEvent")

            def __init__(self, cython_instance: object) -> None:
                super().__init__(cython_instance=cython_instance)

        class Cython_XFocusChangeEvent(Cython_XEvent):
            cython_class: object = _cython_wrapper.get(name="PyXFocusChangeEvent")

            def __init__(self, cython_instance: object) -> None:
                super().__init__(cython_instance=cython_instance)

        class Cython_XCreateWindowEvent(Cython_XEvent):
            cython_class: object = _cython_wrapper.get(name="PyXCreateWindowEvent")

            def __init__(self, cython_instance: object) -> None:
                super().__init__(cython_instance=cython_instance)

        class Cython_XDestroyWindowEvent(Cython_XEvent):
            cython_class: object = _cython_wrapper.get(name="PyXDestroyWindowEvent")

            def __init__(self, cython_instance: object) -> None:
                super().__init__(cython_instance=cython_instance)

        class Cython_XPropertyEvent(Cython_XEvent):
            cython_class: object = _cython_wrapper.get(name="PyXPropertyEvent")

            def __init__(self, cython_instance: object) -> None:
                super().__init__(cython_instance=cython_instance)

        class Cython_XClientMessageEvent(Cython_XEvent):
            cython_class: object = _cython_wrapper.get(name="PyXClientMessageEvent")

            def __init__(self, cython_instance: object) -> None:
                super().__init__(cython_instance=cython_instance)

        class Cython_XErrorEvent(Cython_XEvent):
            cython_class: object = _cython_wrapper.get(name="PyXErrorEvent")

            def __init__(self, cython_instance: object) -> None:
                super().__init__(cython_instance=cython_instance)


class CONSTANTS(metaclass=Final):
    """Constants"""

    CURRENT_TIME: TYPES.Cython_Time = TYPES.Cython_Time(_cython_wrapper.get(name="CONSTANTS").CurrentTime.value)
    ANY_PROPERTY_TYPE: TYPES.Cython_Atom = TYPES.Cython_Atom(
        _cython_wrapper.get(name="CONSTANTS").AnyPropertyType.value
    )

    class KB(metaclass=Final):
        """Keyboard Constants"""

        NO_SYMBOL: TYPES.Cython_KeySym = TYPES.Cython_KeySym(_cython_wrapper.get(name="CONSTANTS").NoSymbol.value)
        ANY_KEY: TYPES.Cython_KeyCode = TYPES.Cython_KeyCode(_cython_wrapper.get(name="CONSTANTS").AnyKey.value)
        X_KB_USE_CORE_KBD: int = int(_cython_wrapper.get(name="CONSTANTS").XkbUseCoreKbd.value)


class INPUT_EVENT_MASKS(int, Enum):
    """
    Input Event Masks. Used as event-mask window attribute and as arguments to grab requests
    """

    NoEventMask = int(_cython_wrapper.get(name="INPUT_EVENT_MASKS").NoEventMask.value)
    StructureNotifyMask = int(_cython_wrapper.get(name="INPUT_EVENT_MASKS").StructureNotifyMask.value)
    SubstructureNotifyMask = int(_cython_wrapper.get(name="INPUT_EVENT_MASKS").SubstructureNotifyMask.value)
    SubstructureRedirectMask = int(_cython_wrapper.get(name="INPUT_EVENT_MASKS").SubstructureRedirectMask.value)
    PropertyChangeMask = int(_cython_wrapper.get(name="INPUT_EVENT_MASKS").PropertyChangeMask.value)
    FocusChangeMask = int(_cython_wrapper.get(name="INPUT_EVENT_MASKS").FocusChangeMask.value)
    KeyPressMask = int(_cython_wrapper.get(name="INPUT_EVENT_MASKS").KeyPressMask.value)
    KeyReleaseMask = int(_cython_wrapper.get(name="INPUT_EVENT_MASKS").KeyReleaseMask.value)


class KEY_MASKS(int, Enum):
    """
    Key masks. Used as modifiers to GrabButton and GrabKey, results of QueryPointer,
    state in various key-, mouse-, and button-related events.
    """

    NoModifiers = 0  # No modifiers
    AnyModifier = int(_cython_wrapper.get(name="KEY_MASKS").AnyModifier.value)  # Any modifier
    Mod1Mask = int(_cython_wrapper.get(name="KEY_MASKS").Mod1Mask.value)  # Alt
    ControlMask = int(_cython_wrapper.get(name="KEY_MASKS").ControlMask.value)  # Ctrl
    ShiftMask = int(_cython_wrapper.get(name="KEY_MASKS").ShiftMask.value)  # Shift
    Mod2Mask = int(_cython_wrapper.get(name="KEY_MASKS").Mod2Mask.value)  # Num Lock
    Mod4Mask = int(_cython_wrapper.get(name="KEY_MASKS").Mod4Mask.value)  # Windows
    LockMask = int(_cython_wrapper.get(name="KEY_MASKS").LockMask.value)  # Caps Lock


class BUTTON_MASKS(int, Enum):
    """Button masks"""

    NoModifiers = 0  # No modifiers
    AnyModifier = int(_cython_wrapper.get(name="BUTTON_MASKS").AnyModifier.value)  # Any modifier
    Button1Mask = int(_cython_wrapper.get(name="BUTTON_MASKS").Button1Mask.value)
    Button2Mask = int(_cython_wrapper.get(name="BUTTON_MASKS").Button2Mask.value)
    Button3Mask = int(_cython_wrapper.get(name="BUTTON_MASKS").Button3Mask.value)
    Button4Mask = int(_cython_wrapper.get(name="BUTTON_MASKS").Button4Mask.value)
    Button5Mask = int(_cython_wrapper.get(name="BUTTON_MASKS").Button5Mask.value)


class BUTTONS(int, Enum):
    """Button names"""

    Button1 = int(_cython_wrapper.get(name="BUTTONS").Button1.value)
    Button2 = int(_cython_wrapper.get(name="BUTTONS").Button2.value)
    Button3 = int(_cython_wrapper.get(name="BUTTONS").Button3.value)
    Button4 = int(_cython_wrapper.get(name="BUTTONS").Button4.value)
    Button5 = int(_cython_wrapper.get(name="BUTTONS").Button5.value)


class WINDOW_VALUE_MASK(int, Enum):
    """Window value mask bits. Enum used by function `x_configure_window()`"""

    CWX = int(_cython_wrapper.get(name="WINDOW_VALUE_MASK").CWX.value)
    CWY = int(_cython_wrapper.get(name="WINDOW_VALUE_MASK").CWY.value)
    CWWidth = int(_cython_wrapper.get(name="WINDOW_VALUE_MASK").CWWidth.value)
    CWHeight = int(_cython_wrapper.get(name="WINDOW_VALUE_MASK").CWHeight.value)
    CWBorderWidth = int(_cython_wrapper.get(name="WINDOW_VALUE_MASK").CWBorderWidth.value)
    CWSibling = int(_cython_wrapper.get(name="WINDOW_VALUE_MASK").CWSibling.value)
    CWStackMode = int(_cython_wrapper.get(name="WINDOW_VALUE_MASK").CWStackMode.value)


class GRAB_MODE(int, Enum):
    """GrabPointer, GrabButton, GrabKeyboard, GrabKey Modes"""

    GrabModeSync = int(_cython_wrapper.get(name="GRAB_MODE").GrabModeSync.value)
    GrabModeAsync = int(_cython_wrapper.get(name="GRAB_MODE").GrabModeAsync.value)


class SET_PROPERTY_MODE(int, Enum):
    """Specifies the mode of the operation. Enum used by function `x_change_window_property()`"""

    # Discards the previous property value and stores the new data
    PropModeReplace = int(_cython_wrapper.get(name="SET_PROPERTY_MODE").PropModeReplace.value)
    # Inserts the specified data before the beginning of the existing data
    PropModePrepend = int(_cython_wrapper.get(name="SET_PROPERTY_MODE").PropModePrepend.value)
    # Inserts the specified data onto the end of the existing data
    PropModeAppend = int(_cython_wrapper.get(name="SET_PROPERTY_MODE").PropModeAppend.value)


class KEYSYM_GROUPS(int, Enum):
    """Specifies the index of the keysym group to lock. Enum used by function `x_kb_lock_group()`"""

    XkbGroup1Index = int(_cython_wrapper.get(name="KB_GROUP_INDEX").XkbGroup1Index.value)
    XkbGroup2Index = int(_cython_wrapper.get(name="KB_GROUP_INDEX").XkbGroup2Index.value)
    XkbGroup3Index = int(_cython_wrapper.get(name="KB_GROUP_INDEX").XkbGroup3Index.value)
    XkbGroup4Index = int(_cython_wrapper.get(name="KB_GROUP_INDEX").XkbGroup4Index.value)


class XWindowChanges:
    class StackMode(int, Enum):
        Above = int(_cython_wrapper.get(name="WINDOW_STACKING_METHOD").Above.value)
        Below = int(_cython_wrapper.get(name="WINDOW_STACKING_METHOD").Below.value)
        TopIf = int(_cython_wrapper.get(name="WINDOW_STACKING_METHOD").TopIf.value)
        BottomIf = int(_cython_wrapper.get(name="WINDOW_STACKING_METHOD").BottomIf.value)
        Opposite = int(_cython_wrapper.get(name="WINDOW_STACKING_METHOD").Opposite.value)

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
        self._cython_xwindowchanges: TYPES.Cython_XWindowChanges = TYPES.Cython_XWindowChanges(
            cython_instance=getattr(TYPES.Cython_XWindowChanges.cython_class, "_new_from_python_")(
                x=x if x is not None else 0,
                y=y if y is not None else 0,
                width=width if width is not None else 0,
                height=height if height is not None else 0,
                border_width=border_width if border_width is not None else 0,
                sibling_window=sibling if sibling is not None else 0,
                stack_mode=stack_mode.value if stack_mode is not None else 0,
            )
        )
        self.x: Optional[int] = x
        self.y: Optional[int] = y
        self.width: Optional[int] = width
        self.height: Optional[int] = height
        self.border_width: Optional[int] = border_width
        self.sibling: Optional[TYPES.Cython_Window] = sibling
        self.stack_mode: Optional[XWindowChanges.StackMode] = stack_mode


class XWindowAttributes:
    class MapState(int, Enum):
        """
        Enum representing the map state of a window.

        - IsUnmapped
        - IsUnviewable
        - IsViewable
        """

        IsUnmapped = int(_cython_wrapper.get(name="WINDOW_MAP_STATE").IsUnmapped.value)
        IsUnviewable = int(_cython_wrapper.get(name="WINDOW_MAP_STATE").IsUnviewable.value)
        IsViewable = int(_cython_wrapper.get(name="WINDOW_MAP_STATE").IsViewable.value)

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
            x=int(cython_xwindowattributes.get_attribute(attr_name="x")),
            y=int(cython_xwindowattributes.get_attribute(attr_name="y")),
            width=int(cython_xwindowattributes.get_attribute(attr_name="width")),
            height=int(cython_xwindowattributes.get_attribute(attr_name="height")),
            border_width=int(cython_xwindowattributes.get_attribute(attr_name="border_width")),
            depth=int(cython_xwindowattributes.get_attribute(attr_name="depth")),
            root=TYPES.Cython_Window(cython_xwindowattributes.get_attribute(attr_name="root")),
            override_redirect=bool(cython_xwindowattributes.get_attribute(attr_name="override_redirect")),
            map_state=XWindowAttributes.MapState(int(cython_xwindowattributes.get_attribute(attr_name="map_state"))),
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
            id=int(_cython_wrapper.get(name="EVENT_TYPES").ErrorEvent.value),
            cython_class=TYPES.EVENTS.Cython_XErrorEvent,
            python_class=lambda: XErrorEvent,
        )
        # XKeyEvent
        KeyPress = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").KeyPress.value),
            cython_class=TYPES.EVENTS.Cython_XKeyEvent,
            python_class=lambda: XKeyEvent,
        )
        KeyRelease = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").KeyRelease.value),
            cython_class=TYPES.EVENTS.Cython_XKeyEvent,
            python_class=lambda: XKeyEvent,
        )
        # XButtonEvent
        ButtonPress = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").ButtonPress.value),
            cython_class=TYPES.EVENTS.Cython_XButtonEvent,
            python_class=lambda: XButtonEvent,
        )
        ButtonRelease = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").ButtonRelease.value),
            cython_class=TYPES.EVENTS.Cython_XButtonEvent,
            python_class=lambda: XButtonEvent,
        )
        # XFocusChangeEvent
        FocusIn = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").FocusIn.value),
            cython_class=TYPES.EVENTS.Cython_XFocusChangeEvent,
            python_class=lambda: XFocusChangeEvent,
        )
        FocusOut = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").FocusOut.value),
            cython_class=TYPES.EVENTS.Cython_XFocusChangeEvent,
            python_class=lambda: XFocusChangeEvent,
        )
        # XCreateWindowEvent
        CreateNotify = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").CreateNotify.value),
            cython_class=TYPES.EVENTS.Cython_XCreateWindowEvent,
            python_class=lambda: XCreateWindowEvent,
        )
        # XDestroyWindowEvent
        DestroyNotify = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").DestroyNotify.value),
            cython_class=TYPES.EVENTS.Cython_XDestroyWindowEvent,
            python_class=lambda: XDestroyWindowEvent,
        )
        # XPropertyEvent
        PropertyNotify = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").PropertyNotify.value),
            cython_class=TYPES.EVENTS.Cython_XPropertyEvent,
            python_class=lambda: XPropertyEvent,
        )
        # XClientMessageEvent
        ClientMessage = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").ClientMessage.value),
            cython_class=TYPES.EVENTS.Cython_XClientMessageEvent,
            python_class=lambda: XClientMessageEvent,
        )
        # Generic event
        GenericEvent = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").GenericEvent.value),
            cython_class=None,
            python_class=None,
        )
        # XMotionEvent
        MotionNotify = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").MotionNotify.value),
            cython_class=None,
            python_class=None,
        )
        # XCrossingEvent
        EnterNotify = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").EnterNotify.value),
            cython_class=None,
            python_class=None,
        )
        LeaveNotify = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").LeaveNotify.value),
            cython_class=None,
            python_class=None,
        )
        # XExposeEvent
        Expose = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").Expose.value),
            cython_class=None,
            python_class=None,
        )
        # XGraphicsExposeEvent
        GraphicsExpose = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").GraphicsExpose.value),
            cython_class=None,
            python_class=None,
        )
        # XNoExposeEvent
        NoExpose = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").NoExpose.value),
            cython_class=None,
            python_class=None,
        )
        # XVisibilityEvent
        VisibilityNotify = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").VisibilityNotify.value),
            cython_class=None,
            python_class=None,
        )
        # XUnmapEvent
        UnmapNotify = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").UnmapNotify.value),
            cython_class=None,
            python_class=None,
        )
        # XMapEvent
        MapNotify = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").MapNotify.value),
            cython_class=None,
            python_class=None,
        )
        # XMapRequestEvent
        MapRequest = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").MapRequest.value),
            cython_class=None,
            python_class=None,
        )
        # XReparentEvent
        ReparentNotify = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").ReparentNotify.value),
            cython_class=None,
            python_class=None,
        )
        # XConfigureEvent
        ConfigureNotify = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").ConfigureNotify.value),
            cython_class=None,
            python_class=None,
        )
        # XGravityEvent
        GravityNotify = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").GravityNotify.value),
            cython_class=None,
            python_class=None,
        )
        # XResizeRequestEvent
        ResizeRequest = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").ResizeRequest.value),
            cython_class=None,
            python_class=None,
        )
        # XConfigureRequestEvent
        ConfigureRequest = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").ConfigureRequest.value),
            cython_class=None,
            python_class=None,
        )
        # XCirculateEvent
        CirculateNotify = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").CirculateNotify.value),
            cython_class=None,
            python_class=None,
        )
        # XCirculateRequestEvent
        CirculateRequest = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").CirculateRequest.value),
            cython_class=None,
            python_class=None,
        )
        # XSelectionClearEvent
        SelectionClear = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").SelectionClear.value),
            cython_class=None,
            python_class=None,
        )
        # XSelectionRequestEvent
        SelectionRequest = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").SelectionRequest.value),
            cython_class=None,
            python_class=None,
        )
        # XSelectionEvent
        SelectionNotify = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").SelectionNotify.value),
            cython_class=None,
            python_class=None,
        )
        # XColormapEvent
        ColormapNotify = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").ColormapNotify.value),
            cython_class=None,
            python_class=None,
        )
        # XMappingEvent
        MappingNotify = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").MappingNotify.value),
            cython_class=None,
            python_class=None,
        )
        # XKeymapEvent
        KeymapNotify = EventType(
            id=int(_cython_wrapper.get(name="EVENT_TYPES").KeymapNotify.value),
            cython_class=None,
            python_class=None,
        )

        @classmethod
        def from_id(cls, id_: int) -> XEvent.EVENT_TYPES:
            for member in cls:
                if member.value.id == id_:
                    return member
            raise ValueError(f"Invalid id {id}")

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
            type=XEvent.EVENT_TYPES.from_id(id_=int(cython_event.get_attribute(attr_name="type").value)),
            serial=int(cython_event.get_attribute(attr_name="serial")),
            send_event=bool(cython_event.get_attribute(attr_name="send_event")),
            display=TYPES.Cython_Display(cython_instance=cython_event.get_attribute(attr_name="display")),
            window=TYPES.Cython_Window(cython_event.get_attribute(attr_name="window")),
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
            cython_instance: object = self._cython_event.get_attribute(attr_name="_get_specific_event_")()
            if self.type == XEvent.EVENT_TYPES.ErrorEvent:
                return XErrorEvent(error_event=TYPES.EVENTS.Cython_XErrorEvent(cython_instance=cython_instance))
            elif self.type == XEvent.EVENT_TYPES.ButtonPress or self.type == XEvent.EVENT_TYPES.ButtonRelease:
                return XButtonEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
                    button_event=TYPES.EVENTS.Cython_XButtonEvent(cython_instance=cython_instance)
                )
            elif self.type == XEvent.EVENT_TYPES.KeyPress or self.type == XEvent.EVENT_TYPES.KeyRelease:
                return XKeyEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
                    key_event=TYPES.EVENTS.Cython_XKeyEvent(cython_instance=cython_instance)
                )
            elif self.type == XEvent.EVENT_TYPES.FocusIn or self.type == XEvent.EVENT_TYPES.FocusOut:
                return XFocusChangeEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
                    focus_change_event=TYPES.EVENTS.Cython_XFocusChangeEvent(cython_instance=cython_instance)
                )
            elif self.type == XEvent.EVENT_TYPES.CreateNotify:
                return XCreateWindowEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
                    create_window_event=TYPES.EVENTS.Cython_XCreateWindowEvent(cython_instance=cython_instance)
                )
            elif self.type == XEvent.EVENT_TYPES.DestroyNotify:
                return XDestroyWindowEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
                    destroy_window_event=TYPES.EVENTS.Cython_XDestroyWindowEvent(cython_instance=cython_instance)
                )
            elif self.type == XEvent.EVENT_TYPES.PropertyNotify:
                return XPropertyEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
                    property_event=TYPES.EVENTS.Cython_XPropertyEvent(cython_instance=cython_instance)
                )
            elif self.type == XEvent.EVENT_TYPES.ClientMessage:
                return XClientMessageEvent._new_from_cython_event_(  # pyright: ignore[reportPrivateUsage]
                    client_message_event=TYPES.EVENTS.Cython_XClientMessageEvent(cython_instance=cython_instance)
                )
            return self
        except Exception as e:
            _logger.error(msg=f"An exception occurrede getting the specific event. {e}")
            return None

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items()])})"


class XErrorEvent(XEvent):
    def __init__(self, error_event: TYPES.EVENTS.Cython_XErrorEvent) -> None:
        self._set_attributes_from_cython_event_(cython_event=error_event)
        self.resourceid: int = int(error_event.get_attribute(attr_name="resourceid"))  # resource id
        self.error_code: int = int(error_event.get_attribute(attr_name="error_code"))  # error code of failed request
        self.request_code: int = int(
            error_event.get_attribute(attr_name="request_code")  # Major op-code of failed request
        )
        self.minor_code: int = int(error_event.get_attribute(attr_name="minor_code"))  # Minor op-code of failed request
        self.msg: str = str(error_event.get_attribute(attr_name="msg"))  # Message of the error


class XButtonEvent(XEvent):
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
            cython_event: TYPES.EVENTS.Cython_XButtonEvent = TYPES.EVENTS.Cython_XButtonEvent(
                cython_instance=getattr(
                    TYPES.EVENTS.Cython_XButtonEvent.cython_class,
                    "_new_from_python_",
                )(
                    type=type_.value.id,
                    serial=serial,
                    send_event=send_event,
                    display=display.cython_instance,
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
        x_button_event = cls(
            display=TYPES.Cython_Display(cython_instance=button_event.get_attribute(attr_name="display")),
            type=XButtonEvent.TYPE(button_event.get_attribute(attr_name="type").value),
            window=TYPES.Cython_Window(button_event.get_attribute(attr_name="window")),
            root=TYPES.Cython_Window(button_event.get_attribute(attr_name="root")),
            subwindow=TYPES.Cython_Window(button_event.get_attribute(attr_name="subwindow")),
            button=BUTTONS(button_event.get_attribute(attr_name="button").value),
            serial=int(button_event.get_attribute(attr_name="serial")),
            send_event=bool(button_event.get_attribute(attr_name="send_event")),
            time=TYPES.Cython_Time(button_event.get_attribute(attr_name="time")),
            x=int(button_event.get_attribute(attr_name="x")),
            y=int(button_event.get_attribute(attr_name="y")),
            x_root=int(button_event.get_attribute(attr_name="x_root")),
            y_root=int(button_event.get_attribute(attr_name="y_root")),
            state=int(button_event.get_attribute(attr_name="state")),
            same_screen=bool(button_event.get_attribute(attr_name="same_screen")),
            create_cython_event=False,
        )
        x_button_event._cython_event = button_event
        return x_button_event


class XKeyEvent(XEvent):
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
            cython_event: TYPES.EVENTS.Cython_XKeyEvent = TYPES.EVENTS.Cython_XKeyEvent(
                cython_instance=getattr(TYPES.EVENTS.Cython_XKeyEvent.cython_class, "_new_from_python_")(
                    type=type_.value.id,
                    serial=serial,
                    send_event=send_event,
                    display=display.cython_instance,
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
        x_key_event = cls(
            display=TYPES.Cython_Display(cython_instance=key_event.get_attribute(attr_name="display")),
            type=XKeyEvent.TYPE(key_event.get_attribute(attr_name="type").value),
            window=TYPES.Cython_Window(key_event.get_attribute(attr_name="window")),
            root=TYPES.Cython_Window(key_event.get_attribute(attr_name="root")),
            subwindow=TYPES.Cython_Window(key_event.get_attribute(attr_name="subwindow")),
            keycode=TYPES.Cython_KeyCode(key_event.get_attribute(attr_name="keycode")),
            serial=int(key_event.get_attribute(attr_name="serial")),
            send_event=bool(key_event.get_attribute(attr_name="send_event")),
            time=TYPES.Cython_Time(key_event.get_attribute(attr_name="time")),
            x=int(key_event.get_attribute(attr_name="x")),
            y=int(key_event.get_attribute(attr_name="y")),
            x_root=int(key_event.get_attribute(attr_name="x_root")),
            y_root=int(key_event.get_attribute(attr_name="y_root")),
            state=int(key_event.get_attribute(attr_name="state")),
            same_screen=bool(key_event.get_attribute(attr_name="same_screen")),
            create_cython_event=False,
        )
        x_key_event._cython_event = key_event
        return x_key_event


class XFocusChangeEvent(XEvent):
    class TYPE(int, Enum):
        FocusIn = XEvent.EVENT_TYPES.FocusIn.value.id
        FocusOut = XEvent.EVENT_TYPES.FocusOut.value.id

    class NOTIFY_MODE(int, Enum):
        NotifyNormal = int(_cython_wrapper.get(name="NOTIFY_MODES").NotifyNormal.value)
        NotifyGrab = int(_cython_wrapper.get(name="NOTIFY_MODES").NotifyGrab.value)
        NotifyUngrab = int(_cython_wrapper.get(name="NOTIFY_MODES").NotifyUngrab.value)
        NotifyWhileGrabbed = int(_cython_wrapper.get(name="NOTIFY_MODES").NotifyWhileGrabbed.value)

    class NOTIFY_DETAIL(int, Enum):
        NotifyAncestor = int(_cython_wrapper.get(name="NOTIFY_DETAILS").NotifyAncestor.value)
        NotifyVirtual = int(_cython_wrapper.get(name="NOTIFY_DETAILS").NotifyVirtual.value)
        NotifyInferior = int(_cython_wrapper.get(name="NOTIFY_DETAILS").NotifyInferior.value)
        NotifyNonlinear = int(_cython_wrapper.get(name="NOTIFY_DETAILS").NotifyNonlinear.value)
        NotifyNonlinearVirtual = int(_cython_wrapper.get(name="NOTIFY_DETAILS").NotifyNonlinearVirtual.value)
        NotifyPointer = int(_cython_wrapper.get(name="NOTIFY_DETAILS").NotifyPointer.value)
        NotifyPointerRoot = int(_cython_wrapper.get(name="NOTIFY_DETAILS").NotifyPointerRoot.value)
        NotifyDetailNone = int(_cython_wrapper.get(name="NOTIFY_DETAILS").NotifyDetailNone.value)

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
            cython_event: TYPES.EVENTS.Cython_XFocusChangeEvent = TYPES.EVENTS.Cython_XFocusChangeEvent(
                cython_instance=getattr(TYPES.EVENTS.Cython_XFocusChangeEvent, "_new_from_python_")(
                    type=type_.value.id,
                    serial=serial,
                    send_event=send_event,
                    display=display.cython_instance,
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
        x_focus_change_event = cls(
            display=TYPES.Cython_Display(cython_instance=focus_change_event.get_attribute(attr_name="display")),
            type=XFocusChangeEvent.TYPE(focus_change_event.get_attribute(attr_name="type").value),
            window=TYPES.Cython_Window(focus_change_event.get_attribute(attr_name="window")),
            detail=XFocusChangeEvent.NOTIFY_DETAIL(focus_change_event.get_attribute(attr_name="detail").value),
            mode=XFocusChangeEvent.NOTIFY_MODE(focus_change_event.get_attribute(attr_name="mode").value),
            serial=int(focus_change_event.get_attribute(attr_name="serial")),
            send_event=bool(focus_change_event.get_attribute(attr_name="send_event")),
            create_cython_event=False,
        )
        x_focus_change_event._cython_event = focus_change_event
        return x_focus_change_event


class XCreateWindowEvent(XEvent):
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
            cython_event: TYPES.EVENTS.Cython_XCreateWindowEvent = TYPES.EVENTS.Cython_XCreateWindowEvent(
                cython_instance=getattr(TYPES.EVENTS.Cython_XCreateWindowEvent, "_new_from_python_")(
                    type=type_.value.id,
                    serial=serial,
                    send_event=send_event,
                    display=display.cython_instance,
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
        x_create_window_event = cls(
            display=TYPES.Cython_Display(cython_instance=create_window_event.get_attribute(attr_name="display")),
            parent=TYPES.Cython_Window(create_window_event.get_attribute(attr_name="parent")),
            window=TYPES.Cython_Window(create_window_event.get_attribute(attr_name="window")),
            width=int(create_window_event.get_attribute(attr_name="width")),
            height=int(create_window_event.get_attribute(attr_name="height")),
            override_redirect=bool(create_window_event.get_attribute(attr_name="override_redirect")),
            x=int(create_window_event.get_attribute(attr_name="x")),
            y=int(create_window_event.get_attribute(attr_name="y")),
            border_width=int(create_window_event.get_attribute(attr_name="border_width")),
            serial=int(create_window_event.get_attribute(attr_name="serial")),
            send_event=bool(create_window_event.get_attribute(attr_name="send_event")),
            create_cython_event=False,
        )
        x_create_window_event._cython_event = create_window_event
        return x_create_window_event


class XDestroyWindowEvent(XEvent):
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
            cython_event: TYPES.EVENTS.Cython_XDestroyWindowEvent = TYPES.EVENTS.Cython_XDestroyWindowEvent(
                cython_instance=getattr(TYPES.EVENTS.Cython_XDestroyWindowEvent, "_new_from_python_")(
                    type=type_.value.id,
                    serial=serial,
                    send_event=send_event,
                    display=display.cython_instance,
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
        x_destroy_window_event = cls(
            display=TYPES.Cython_Display(cython_instance=destroy_window_event.get_attribute(attr_name="display")),
            event=TYPES.Cython_Window(destroy_window_event.get_attribute(attr_name="event")),
            window=TYPES.Cython_Window(destroy_window_event.get_attribute(attr_name="window")),
            serial=int(destroy_window_event.get_attribute(attr_name="serial")),
            send_event=bool(destroy_window_event.get_attribute(attr_name="send_event")),
            create_cython_event=False,
        )
        x_destroy_window_event._cython_event = destroy_window_event
        return x_destroy_window_event


class XPropertyEvent(XEvent):
    class STATE(int, Enum):
        PropertyNewValue = int(_cython_wrapper.get(name="PROPERTY_NOTIFICATION").PropertyNewValue.value)
        PropertyDelete = int(_cython_wrapper.get(name="PROPERTY_NOTIFICATION").PropertyDelete.value)

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
            cython_event: TYPES.EVENTS.Cython_XPropertyEvent = TYPES.EVENTS.Cython_XPropertyEvent(
                cython_instance=getattr(TYPES.EVENTS.Cython_XPropertyEvent, "_new_from_python_")(
                    type=type_.value.id,
                    serial=serial,
                    send_event=send_event,
                    display=display.cython_instance,
                    window=window,
                    atom=atom,
                    time=time,
                    state=state.value,
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
        self.atom: TYPES.Cython_Atom = atom
        self.time: TYPES.Cython_Time = time
        self.state: XPropertyEvent.STATE = state

    @classmethod
    def _new_from_cython_event_(cls, property_event: TYPES.EVENTS.Cython_XPropertyEvent) -> XPropertyEvent:
        x_property_event = cls(
            display=TYPES.Cython_Display(cython_instance=property_event.get_attribute(attr_name="display")),
            window=TYPES.Cython_Window(property_event.get_attribute(attr_name="window")),
            atom=TYPES.Cython_Atom(property_event.get_attribute(attr_name="atom")),
            state=XPropertyEvent.STATE(property_event.get_attribute(attr_name="state").value),
            serial=int(property_event.get_attribute(attr_name="serial")),
            send_event=bool(property_event.get_attribute(attr_name="send_event")),
            time=TYPES.Cython_Time(property_event.get_attribute(attr_name="time")),
            create_cython_event=False,
        )
        x_property_event._cython_event = property_event
        return x_property_event


class XClientMessageEvent(XEvent):
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
        arr: Optional[array[int]] = None
        if format_ == PROPERTY_FORMAT.CHAR:
            list_with_chars: list[int] = []
            if isinstance(data, str):
                temp_arr: array[int] = array("b", data.encode())
                list_with_chars = (temp_arr.tolist() + ([0] * (20 - len(temp_arr.tolist()))))[:20]
            else:
                list_with_chars = (data + ([0] * (20 - len(data))))[:20]
            arr = array("b", list_with_chars)
        elif format_ == PROPERTY_FORMAT.SHORT:
            if isinstance(data, str):
                raise Exception(f"Invalid data type for format {format_}, it should be a list[int]")
            arr = array("h", (data + ([0] * (10 - len(data))))[:10])
        elif format_ == PROPERTY_FORMAT.LONG:
            if isinstance(data, str):
                raise Exception(f"Invalid data type for format {format_}, it should be a list[int]")
            arr = array("l", (data + ([0] * (5 - len(data))))[:5])
        type_: XEvent.EVENT_TYPES = XEvent.EVENT_TYPES.ClientMessage
        if create_cython_event and type_.value.cython_class is not None:
            cython_event: TYPES.EVENTS.Cython_XClientMessageEvent = TYPES.EVENTS.Cython_XClientMessageEvent(
                cython_instance=getattr(TYPES.EVENTS.Cython_XClientMessageEvent, "_new_from_python_")(
                    type=type_.value.id,
                    serial=serial,
                    send_event=send_event,
                    display=display.cython_instance,
                    window=window,
                    message_type=message_type,
                    format=format_.value[0],
                    data=arr,
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
        self.data: array[int] = arr

    @classmethod
    def _new_from_cython_event_(
        cls, client_message_event: TYPES.EVENTS.Cython_XClientMessageEvent
    ) -> XClientMessageEvent:
        x_client_message_event = cls(
            display=TYPES.Cython_Display(cython_instance=client_message_event.get_attribute(attr_name="display")),
            window=TYPES.Cython_Window(client_message_event.get_attribute(attr_name="window")),
            message_type=TYPES.Cython_Atom(client_message_event.get_attribute(attr_name="message_type")),
            format_=PROPERTY_FORMAT.new_from_value(
                value=client_message_event.get_attribute(attr_name="format").value[0]
            ),
            data=client_message_event.get_attribute(attr_name="data").tolist(),
            serial=int(client_message_event.get_attribute(attr_name="serial")),
            send_event=bool(client_message_event.get_attribute(attr_name="send_event")),
            create_cython_event=False,
        )
        x_client_message_event._cython_event = client_message_event
        return x_client_message_event


class XScreenSaverInfo:
    class State(int, Enum):
        Off = int(_cython_wrapper.get(name="SCREENSAVER_STATE").ScreenSaverOff.value)
        On = int(_cython_wrapper.get(name="SCREENSAVER_STATE").ScreenSaverOn.value)
        Cycle = int(_cython_wrapper.get(name="SCREENSAVER_STATE").ScreenSaverCycle.value)
        Disabled = int(_cython_wrapper.get(name="SCREENSAVER_STATE").ScreenSaverDisabled.value)

    class Kind(int, Enum):
        Blanked = int(_cython_wrapper.get(name="SCREENSAVER_KIND").ScreenSaverBlanked.value)
        Internal = int(_cython_wrapper.get(name="SCREENSAVER_KIND").ScreenSaverInternal.value)
        External = int(_cython_wrapper.get(name="SCREENSAVER_KIND").ScreenSaverExternal.value)

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
        return cls(
            group=int(state.get_attribute(attr_name="group")),
            base_group=int(state.get_attribute(attr_name="base_group")),
            latched_group=int(state.get_attribute(attr_name="latched_group")),
            locked_group=int(state.get_attribute(attr_name="locked_group")),
            mods=int(state.get_attribute(attr_name="mods")),
            base_mods=int(state.get_attribute(attr_name="base_mods")),
            latched_mods=int(state.get_attribute(attr_name="latched_mods")),
            locked_mods=int(state.get_attribute(attr_name="locked_mods")),
            compat_state=int(state.get_attribute(attr_name="compat_state")),
            grab_mods=int(state.get_attribute(attr_name="grab_mods")),
            compat_grab_mods=int(state.get_attribute(attr_name="compat_grab_mods")),
            lookup_mods=int(state.get_attribute(attr_name="lookup_mods")),
            compat_lookup_mods=int(state.get_attribute(attr_name="compat_lookup_mods")),
            ptr_buttons=int(state.get_attribute(attr_name="ptr_buttons")),
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
        for member in cls:
            if value in member:
                return member
        raise ValueError(f"The value {value} is not in the enum members")


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
        return [x.decode() for x in self.property_data.tobytes().split(sep=null_byte) if len(x.decode())]


class DPMSInfo:
    class PowerLEvel(int, Enum):
        DPMSModeOn = int(_cython_wrapper.get(name="DPMS_POWER_LEVEL").DPMSModeOn.value)
        DPMSModeStandby = int(_cython_wrapper.get(name="DPMS_POWER_LEVEL").DPMSModeStandby.value)
        DPMSModeSuspend = int(_cython_wrapper.get(name="DPMS_POWER_LEVEL").DPMSModeSuspend.value)
        DPMSModeOff = int(_cython_wrapper.get(name="DPMS_POWER_LEVEL").DPMSModeOff.value)

    def __init__(self, dpms_info: TYPES.Cython_DPMSInfo) -> None:
        self.state: bool = bool(dpms_info.get_attribute(attr_name="state"))
        self.power_level: DPMSInfo.PowerLEvel = DPMSInfo.PowerLEvel(
            dpms_info.get_attribute(attr_name="power_level").value
        )

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items() if not k.startswith('_')])})"


def x_open_display(display_name: Optional[str] = None) -> TYPES.Cython_Display:
    """
    Connext to X server. Wrapper for `XOpenDisplay`. Returns a `orcsome3.xlib.TYPES.Cython_Display` object.

    Params:
    - `display_name`: Specifies the hardware display name, which determines the display and communications
                      domain to be used. On a POSIX-conformant system, if the display_name is `None`,
                      it defaults to the value of the `DISPLAY` environment variable.
    """
    display: TYPES.Cython_Display = TYPES.Cython_Display(
        cython_instance=_cython_wrapper.run_function(name="PyXOpenDisplay", params=[display_name])
    )
    if display.cython_instance is None:
        raise Exception("Can't open display")
    return display


def x_close_display(display: TYPES.Cython_Display) -> None:
    """Disconnect from X server. Wrapper for `XCloseDisplay`."""
    _cython_wrapper.run_function(name="PyXCloseDisplay", params=[display.cython_instance])


def get_default_root_window(display: TYPES.Cython_Display) -> TYPES.Cython_Window:
    """Returns the root window for `display`"""
    return TYPES.Cython_Window(
        _cython_wrapper.run_function(name="PyXDefaultRootWindow", params=[display.cython_instance])
    )


def get_connection_number(display: TYPES.Cython_Display) -> int:
    """
    Return a connection number for `display`.
    On a POSIX-conformant system, this is the file descriptor of the connection.
    """
    return int(_cython_wrapper.run_function(name="PyXConnectionNumber", params=[display.cython_instance]))


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
    _cython_wrapper.run_function(
        name="PyXGrabKey",
        params=[
            display.cython_instance,
            keycode,
            modifiers,
            window,
            owner_events,
            pointer_mode.value,
            keyboard_mode.value,
        ],
    )


def x_ungrab_key(
    display: TYPES.Cython_Display,
    keycode: int,
    modifiers: int,
    window: TYPES.Cython_Window,
) -> None:
    """Wrapper for `XUngrabKey`"""
    _cython_wrapper.run_function(
        name="PyXUngrabKey",
        params=[display.cython_instance, keycode, modifiers, window],
    )


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
    _cython_wrapper.run_function(name="PyXSelectInput", params=[display.cython_instance, window, mask])


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
    _cython_wrapper.run_function(
        name="PyXConfigureWindow",
        params=[
            display.cython_instance,
            window,
            value_mask_,
            window_changes._cython_xwindowchanges,  # pyright: ignore[reportPrivateUsage]
        ],
    )


def x_sync(display: TYPES.Cython_Display, discard: bool) -> None:
    """Wrapper for `XSync`"""
    _cython_wrapper.run_function(name="PyXSync", params=[display.cython_instance, discard])


def x_set_error_handler(
    handler: Callable[[TYPES.Cython_Display, TYPES.EVENTS.Cython_XErrorEvent], None],
) -> None:
    """Wrapper for `XSetErrorHandler`"""
    _cython_wrapper.run_function(name="PyXSetErrorHandler", params=[handler])


def x_get_window_property(
    display: TYPES.Cython_Display, window: TYPES.Cython_Window, property_: str
) -> Optional[WindowProperty]:
    """Wrapper for `XGetWindowProperty`"""
    result: Optional[tuple[array[int], TYPES.Cython_Atom, str]] = _cython_wrapper.run_function(
        name="PyXGetWindowProperty",
        params=[display.cython_instance, window, property_],
    )
    try:
        return (
            WindowProperty(
                window=window,
                property_name=property_,
                type_=result[2],
                atom_type=result[1],
                format_=PROPERTY_FORMAT.new_from_value(value=result[0].typecode),
                property_data=result[0],
            )
            if result is not None
            else None
        )
    except:
        return None


def x_change_window_property(
    display: TYPES.Cython_Display,
    window_property: WindowProperty,
    mode: SET_PROPERTY_MODE = SET_PROPERTY_MODE.PropModeReplace,
) -> bool:
    """Wrapper for `XChangeProperty`"""
    return bool(
        _cython_wrapper.run_function(
            name="PyXChangeProperty",
            params=[
                display.cython_instance,
                window_property.window,
                window_property.property_name,
                window_property.atom_type,
                window_property.format_.value[0],
                mode.value,
                window_property.property_data,
            ],
        )
    )


def x_get_window_attributes(display: TYPES.Cython_Display, window: TYPES.Cython_Window) -> Optional[XWindowAttributes]:
    """Wrapper for `XGetWindowAttributes`"""
    attrs: TYPES.Cython_XWindowAttributes = TYPES.Cython_XWindowAttributes(
        cython_instance=_cython_wrapper.run_function(
            name="PyXGetWindowAttributes", params=[display.cython_instance, window]
        )
    )
    if attrs.cython_instance is None:
        return None

    return XWindowAttributes._new_from_cython_xwindowattributes_(  # pyright:ignore[reportPrivateUsage]
        window=window, cython_xwindowattributes=attrs
    )


def x_get_window_tree(display: TYPES.Cython_Display, window: TYPES.Cython_Window) -> Optional[XWindowTree]:
    """Wrapper for `XQueryTree`"""
    result: TYPES.Cython_XWindowTree = TYPES.Cython_XWindowTree(
        cython_instance=_cython_wrapper.run_function(name="PyXQueryTree", params=[display.cython_instance, window])
    )
    if result.cython_instance is None:
        return None

    return XWindowTree(
        window=result.get_attribute(attr_name="window"),
        root=result.get_attribute(attr_name="root"),
        parent=result.get_attribute(attr_name="parent"),
        children=result.get_attribute(attr_name="children"),
    )


def x_get_window_geometry(display: TYPES.Cython_Display, window: TYPES.Cython_Window) -> Optional[XWindowGeometry]:
    """Wrapper for `XGetGeometry`"""
    window_geometry: TYPES.Cython_XWindowGeometry = TYPES.Cython_XWindowGeometry(
        cython_instance=_cython_wrapper.run_function(name="PyXGetGeometry", params=[display.cython_instance, window])
    )
    if window_geometry.cython_instance is None:
        return None

    return XWindowGeometry(
        window=window,
        root=window_geometry.get_attribute(attr_name="root"),
        x=window_geometry.get_attribute(attr_name="x"),
        y=window_geometry.get_attribute(attr_name="y"),
        width=window_geometry.get_attribute(attr_name="width"),
        height=window_geometry.get_attribute(attr_name="height"),
        border_width=window_geometry.get_attribute(attr_name="border_width"),
        depth=window_geometry.get_attribute(attr_name="depth"),
    )


def x_get_screen_saver_info(display: TYPES.Cython_Display, drawable: TYPES.Cython_Window) -> Optional[XScreenSaverInfo]:
    """Wrapper for `XScreenSaverQueryInfo`"""
    result: TYPES.Cython_XScreenSaverInfo = TYPES.Cython_XScreenSaverInfo(
        cython_instance=_cython_wrapper.run_function(
            name="PyXScreenSaverQueryInfo", params=[display.cython_instance, drawable]
        )
    )
    if result.cython_instance is None:
        return None

    return XScreenSaverInfo(
        window=result.get_attribute(attr_name="window"),
        state=result.get_attribute(attr_name="state"),
        kind=result.get_attribute(attr_name="kind"),
        til_or_since=result.get_attribute(attr_name="til_or_since"),
        idle=result.get_attribute(attr_name="idle"),
        event_mask=result.get_attribute(attr_name="event_mask"),
    )


def x_kb_get_state(display: TYPES.Cython_Display, device_spec: int = CONSTANTS.KB.X_KB_USE_CORE_KBD) -> XkbStateRec:
    """Wrapper for `XkbGetState`"""
    result: TYPES.Cython_XkbStateRec = TYPES.Cython_XkbStateRec(
        cython_instance=_cython_wrapper.run_function(
            name="PyXkbGetState", params=[display.cython_instance, device_spec]
        )
    )
    return XkbStateRec.new(state=result)


def x_kb_lock_group(
    display: TYPES.Cython_Display,
    group: KEYSYM_GROUPS,
    device_spec: int = CONSTANTS.KB.X_KB_USE_CORE_KBD,
) -> bool:
    """Wrapper for `XkbLockGroup`"""
    result: bool = bool(
        _cython_wrapper.run_function(
            name="PyXkbLockGroup",
            params=[display.cython_instance, device_spec, group.value],
        )
    )
    x_flush(display=display)
    return result


def x_flush(display: TYPES.Cython_Display) -> None:
    """Wrapper for `XFlush`"""
    _cython_wrapper.run_function(name="PyXFlush", params=[display.cython_instance])


def x_get_atom_name(display: TYPES.Cython_Display, atom: TYPES.Cython_Atom) -> Optional[str]:
    """
    Returns the name associated with an Atom if the Atom exists.

    Wrapper for `XGetAtomName`
    """
    result: str = str(_cython_wrapper.run_function(name="PyXGetAtomName", params=[display.cython_instance, atom]))
    return result if len(result.strip()) else None


def x_get_atom_from_name(
    display: TYPES.Cython_Display, atom_name: str, create_if_not_exists: bool
) -> TYPES.Cython_Atom:
    """Wrapper for XInternAtom"""
    atom: TYPES.Cython_Atom = _cython_wrapper.run_function(
        name="PyXInternAtom",
        params=[display.cython_instance, atom_name, not create_if_not_exists],
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

    _cython_wrapper.run_function(
        name="PyXSendEvent",
        params=[
            display.cython_instance,
            window,
            propagate,
            event_mask,
            xevent._cython_event,  # pyright: ignore[reportPrivateUsage]
        ],
    )


def set_window_icon(display: TYPES.Cython_Display, window: TYPES.Cython_Window, icon_path: Path) -> bool:
    return bool(
        _cython_wrapper.run_function(name="PySetWindowIcon", params=[display.cython_instance, window, icon_path])
    )


def x_string_to_keysym(string: str) -> TYPES.Cython_KeySym:
    """Wrapper for `XStringToKeysym`"""
    return TYPES.Cython_KeySym(_cython_wrapper.run_function(name="PyXStringToKeysym", params=[string]))


def x_keysym_to_keycode(display: TYPES.Cython_Display, keysym: TYPES.Cython_KeySym) -> TYPES.Cython_KeyCode:
    """Wrapper for `XKeysymToKeycode`"""
    return TYPES.Cython_KeyCode(
        _cython_wrapper.run_function(name="PyXKeysymToKeycode", params=[display.cython_instance, keysym])
    )


def x_pending(display: TYPES.Cython_Display) -> int:
    """Wrapper for `XPending`"""
    return int(_cython_wrapper.run_function(name="PyXPending", params=[display.cython_instance]))


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
    XPropertyEvent,
    XClientMessageEvent,
]:
    """Wrapper for `XNextEvent`"""
    cython_xevent: TYPES.EVENTS.Cython_XEvent = TYPES.EVENTS.Cython_XEvent(
        cython_instance=_cython_wrapper.run_function(name="PyXNextEvent", params=[display.cython_instance])
    )
    xevent: XEvent = XEvent()
    xevent._set_attributes_from_cython_event_(cython_event=cython_xevent)  # pyright: ignore[reportPrivateUsage]
    specific_event: Optional[
        Union[
            XEvent,
            XErrorEvent,
            XButtonEvent,
            XKeyEvent,
            XFocusChangeEvent,
            XCreateWindowEvent,
            XDestroyWindowEvent,
            XPropertyEvent,
            XClientMessageEvent,
        ]
    ] = xevent.get_specific_event()
    return specific_event if specific_event is not None else xevent


def dpms_info(display: TYPES.Cython_Display) -> DPMSInfo:
    """Wrapper for `DPMSInfo`"""
    return DPMSInfo(
        dpms_info=TYPES.Cython_DPMSInfo(
            cython_instance=_cython_wrapper.run_function(name="PyGetDPMSInfo", params=[display.cython_instance])
        )
    )


def dpms_enable(display: TYPES.Cython_Display) -> bool:
    """Wrapper for `DPMSEnable`"""
    return bool(_cython_wrapper.run_function(name="PyDPMSEnable", params=[display.cython_instance]))


def dpms_disable(display: TYPES.Cython_Display) -> bool:
    """Wrapper for `DPMSDisable`"""
    return bool(_cython_wrapper.run_function(name="PyDPMSDisable", params=[display.cython_instance]))


def reset_dpms(display: TYPES.Cython_Display) -> None:
    dpms_info_: DPMSInfo = dpms_info(display=display)
    if dpms_info_.state:
        _ = dpms_disable(display=display)
        _ = dpms_enable(display=display)


# Test code


def default_error_handler(__display__: TYPES.Cython_Display, error: TYPES.EVENTS.Cython_XErrorEvent) -> None:
    """Default callback for errors"""
    err: XErrorEvent = XErrorEvent(error_event=error)
    msg_resource: str = f"{'0x%0.2X' % int(err.resourceid)}:{int(err.resourceid)}"
    _logger.error(msg=f"{err.msg} ({msg_resource})")
