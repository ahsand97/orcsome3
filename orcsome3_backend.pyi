"""Type stub for the compiled orcsome3_backend extension (generated from orcsome3_backend.pyx)."""

from __future__ import annotations

from array import array
from collections.abc import Callable
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Optional, Union

class CONSTANTS(IntEnum):
    CurrentTime = 0
    AnyPropertyType = 0
    NoSymbol = 0
    AnyKey = 0
    XkbUseCoreKbd = 256
    RevertToNone = 0
    RevertToPointerRoot = 1
    RevertToParent = 2

class EVENT_TYPES(IntEnum):
    GenericEvent = 35
    ErrorEvent = 0
    KeyPress = 2
    KeyRelease = 3
    ButtonPress = 4
    ButtonRelease = 5
    MotionNotify = 6
    EnterNotify = 7
    LeaveNotify = 8
    FocusIn = 9
    FocusOut = 10
    Expose = 12
    GraphicsExpose = 13
    NoExpose = 14
    VisibilityNotify = 15
    CreateNotify = 16
    DestroyNotify = 17
    UnmapNotify = 18
    MapNotify = 19
    MapRequest = 20
    ReparentNotify = 21
    ConfigureNotify = 22
    GravityNotify = 24
    ResizeRequest = 25
    ConfigureRequest = 23
    CirculateNotify = 26
    CirculateRequest = 27
    PropertyNotify = 28
    SelectionClear = 29
    SelectionRequest = 30
    SelectionNotify = 31
    ColormapNotify = 32
    ClientMessage = 33
    MappingNotify = 34
    KeymapNotify = 11

class INPUT_EVENT_MASKS(IntEnum):
    NoEventMask = 0
    StructureNotifyMask = 131072
    SubstructureNotifyMask = 524288
    SubstructureRedirectMask = 1048576
    PropertyChangeMask = 4194304
    FocusChangeMask = 2097152
    KeyPressMask = 1
    KeyReleaseMask = 2
    ButtonPressMask = 4
    ButtonReleaseMask = 8

class KEY_MASKS(IntEnum):
    AnyModifier = 32768
    Mod1Mask = 8
    ControlMask = 4
    ShiftMask = 1
    Mod2Mask = 16
    Mod4Mask = 64
    LockMask = 2

class BUTTON_MASKS(IntEnum):
    AnyModifier = 32768
    Button1Mask = 256
    Button2Mask = 512
    Button3Mask = 1024
    Button4Mask = 2048
    Button5Mask = 4096

class BUTTONS(IntEnum):
    AnyButton = 0
    Button1 = 1
    Button2 = 2
    Button3 = 3
    Button4 = 4
    Button5 = 5

class GRAB_MODE(IntEnum):
    GrabModeSync = 0
    GrabModeAsync = 1

class WINDOW_VALUE_MASK(IntEnum):
    CWX = 1
    CWY = 2
    CWWidth = 4
    CWHeight = 8
    CWBorderWidth = 16
    CWSibling = 32
    CWStackMode = 64

class WINDOW_STACKING_METHOD(IntEnum):
    Above = 0
    Below = 1
    TopIf = 2
    BottomIf = 3
    Opposite = 4

class SET_PROPERTY_MODE(IntEnum):
    PropModeReplace = 0
    PropModePrepend = 1
    PropModeAppend = 2

class WINDOW_MAP_STATE(IntEnum):
    IsUnmapped = 0
    IsUnviewable = 1
    IsViewable = 2

class SCREENSAVER_STATE(IntEnum):
    ScreenSaverOff = 0
    ScreenSaverOn = 1
    ScreenSaverCycle = 2
    ScreenSaverDisabled = 3

class SCREENSAVER_KIND(IntEnum):
    ScreenSaverBlanked = 0
    ScreenSaverInternal = 1
    ScreenSaverExternal = 2

class KB_GROUP_INDEX(IntEnum):
    XkbGroup1Index = 0
    XkbGroup2Index = 1
    XkbGroup3Index = 2
    XkbGroup4Index = 3
    XkbAnyGroup = 254
    XkbAllGroups = 255

class NOTIFY_MODES(IntEnum):
    NotifyNormal = 0
    NotifyGrab = 1
    NotifyUngrab = 2
    NotifyWhileGrabbed = 3

class NOTIFY_DETAILS(IntEnum):
    NotifyAncestor = 0
    NotifyVirtual = 1
    NotifyInferior = 2
    NotifyNonlinear = 3
    NotifyNonlinearVirtual = 4
    NotifyPointer = 5
    NotifyPointerRoot = 6
    NotifyDetailNone = 7

class PROPERTY_NOTIFICATION(IntEnum):
    PropertyNewValue = 0
    PropertyDelete = 1

class PROPERTY_FORMAT(Enum):
    CHAR = (8, "b")
    SHORT = (16, "h")
    LONG = (32, "l")

    @classmethod
    def new_from_value(cls, value: Union[str, int]) -> PROPERTY_FORMAT: ...

class DPMS_POWER_LEVEL(IntEnum):
    DPMSModeOn = 0
    DPMSModeStandby = 1
    DPMSModeSuspend = 2
    DPMSModeOff = 3

class PYLOOP_NEW_LOOP_FLAGS(IntEnum):
    EVFLAG_AUTO = 0
    EVFLAG_NOENV = 16777216
    EVFLAG_FORKCHECK = 33554432
    EVFLAG_NOINOTIFY = 1048576
    EVFLAG_SIGNALFD = 2097152
    EVFLAG_NOSIGMASK = 4194304
    EVBACKEND_SELECT = 1
    EVBACKEND_POLL = 2
    EVBACKEND_EPOLL = 4
    EVBACKEND_KQUEUE = 8
    EVBACKEND_DEVPOLL = 16
    EVBACKEND_PORT = 32
    EVBACKEND_ALL = 255
    EVBACKEND_MASK = 65535

class PYLOOP_RUN_LOOP_FLAGS(IntEnum):
    EVRUN_ALWAYS = 0
    EVRUN_ONCE = 2
    EVRUN_NOWAIT = 1

class PYLOOP_BREAK_LOOP_FLAGS(IntEnum):
    EVBREAK_ALL = 2
    EVBREAK_ONE = 1
    EVBREAK_CANCEL = 0

class PYIOWATCHER_INIT_FLAGS(IntEnum):
    EV_READ = 1
    EV_WRITE = 2
    EV_READ_WRITE = 3

class PyDisplay: ...

class PyXEvent:
    serial: int
    send_event: int
    display: PyDisplay
    window: int
    type: EVENT_TYPES
    def _get_specific_event_(self) -> PyXEvent: ...

class PyXErrorEvent(PyXEvent):
    resourceid: int
    error_code: int
    request_code: int
    minor_code: int
    msg: str

class PyXKeyEvent(PyXEvent):
    root: int
    subwindow: int
    time: int
    x: int
    y: int
    x_root: int
    y_root: int
    state: int
    keycode: int
    same_screen: int
    @staticmethod
    def _new_from_python_(
        type: int,
        serial: int,
        send_event: bool,
        display: PyDisplay,
        window: int,
        root: int,
        subwindow: int,
        time: int,
        x: int,
        y: int,
        x_root: int,
        y_root: int,
        state: int,
        keycode: int,
        same_screen: bool,
    ) -> PyXKeyEvent: ...

class PyXButtonEvent(PyXEvent):
    root: int
    subwindow: int
    time: int
    x: int
    y: int
    x_root: int
    y_root: int
    state: int
    same_screen: int
    button: BUTTONS
    @staticmethod
    def _new_from_python_(
        type: int,
        serial: int,
        send_event: bool,
        display: PyDisplay,
        window: int,
        root: int,
        subwindow: int,
        time: int,
        x: int,
        y: int,
        x_root: int,
        y_root: int,
        state: int,
        button: int,
        same_screen: bool,
    ) -> PyXButtonEvent: ...

class PyXFocusChangeEvent(PyXEvent):
    mode: NOTIFY_MODES
    detail: NOTIFY_DETAILS
    @staticmethod
    def _new_from_python_(
        type: int,
        serial: int,
        send_event: bool,
        display: PyDisplay,
        window: int,
        mode: int,
        detail: int,
    ) -> PyXFocusChangeEvent: ...

class PyXCreateWindowEvent(PyXEvent):
    parent: int
    x: int
    y: int
    width: int
    height: int
    border_width: int
    override_redirect: int
    @staticmethod
    def _new_from_python_(
        type: int,
        serial: int,
        send_event: bool,
        display: PyDisplay,
        parent: int,
        window: int,
        x: int,
        y: int,
        width: int,
        height: int,
        border_width: int,
        override_redirect: bool,
    ) -> PyXCreateWindowEvent: ...

class PyXDestroyWindowEvent(PyXEvent):
    event: int
    @staticmethod
    def _new_from_python_(
        type: int,
        serial: int,
        send_event: bool,
        display: PyDisplay,
        event: int,
        window: int,
    ) -> PyXDestroyWindowEvent: ...

class PyXMapEvent(PyXEvent):
    event: int
    override_redirect: int
    @staticmethod
    def _new_from_python_(
        type: int,
        serial: int,
        send_event: bool,
        display: PyDisplay,
        event: int,
        window: int,
        override_redirect: bool,
    ) -> PyXMapEvent: ...

class PyXUnmapEvent(PyXEvent):
    event: int
    from_configure: int
    @staticmethod
    def _new_from_python_(
        type: int,
        serial: int,
        send_event: bool,
        display: PyDisplay,
        event: int,
        window: int,
        from_configure: bool,
    ) -> PyXUnmapEvent: ...

class PyXConfigureEvent(PyXEvent):
    event: int
    x: int
    y: int
    width: int
    height: int
    border_width: int
    above: int
    override_redirect: int
    @staticmethod
    def _new_from_python_(
        type: int,
        serial: int,
        send_event: bool,
        display: PyDisplay,
        event: int,
        window: int,
        x: int,
        y: int,
        width: int,
        height: int,
        border_width: int,
        above: int,
        override_redirect: bool,
    ) -> PyXConfigureEvent: ...

class PyXPropertyEvent(PyXEvent):
    atom: int
    time: int
    state: PROPERTY_NOTIFICATION
    @staticmethod
    def _new_from_python_(
        type: int,
        serial: int,
        send_event: bool,
        display: PyDisplay,
        window: int,
        atom: int,
        time: int,
        state: int,
    ) -> PyXPropertyEvent: ...

class PyXClientMessageEvent(PyXEvent):
    message_type: int
    data: array[int]
    format: PROPERTY_FORMAT
    @staticmethod
    def _new_from_python_(
        type: int,
        serial: int,
        send_event: bool,
        display: PyDisplay,
        window: int,
        message_type: int,
        format: int,
        data: array[int],
    ) -> PyXClientMessageEvent: ...

class PyXWindowChanges:
    x: int
    y: int
    width: int
    height: int
    border_width: int
    sibling_window: int
    stack_mode: WINDOW_STACKING_METHOD
    @staticmethod
    def _new_from_python_(
        x: int,
        y: int,
        width: int,
        height: int,
        border_width: int,
        sibling_window: int,
        stack_mode: int,
    ) -> PyXWindowChanges: ...

class PyXWindowAttributes:
    x: int
    y: int
    width: int
    height: int
    border_width: int
    depth: int
    root: int
    map_state: int
    override_redirect: int

class PyXWindowTree:
    window: int
    root: int
    parent: int
    children: list[int]

class PyXWindowGeometry:
    window: int
    root: int
    x: int
    y: int
    width: int
    height: int
    border_width: int
    depth: int

class PyXScreenSaverInfo:
    window: int
    state: int
    kind: int
    til_or_since: int
    idle: int
    event_mask: int

class PyXkbStateRec:
    group: int
    locked_group: int
    base_group: int
    latched_group: int
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

class PyDPMSInfo:
    state: bool
    power_level: DPMS_POWER_LEVEL

class PyLoop:
    @staticmethod
    def _new_from_python_(flags: Union[int, list[int]]) -> PyLoop: ...
    def run(self, flags: Union[int, list[int]]) -> None: ...
    def break_(self, how_to_break_flag: int) -> None: ...
    def destroy(self) -> None: ...

class PyIOWatcher:
    callbacks: dict[str, Callable[..., Any]]
    @staticmethod
    def _new_from_python_() -> PyIOWatcher: ...
    def init(self, callbacks: dict[str, Callable[..., Any]], file_descriptor: int, events: int) -> None: ...
    def start(self, loop: PyLoop) -> None: ...
    def stop(self, loop: PyLoop) -> None: ...

class PySignalWatcher:
    callbacks: dict[str, Callable[..., Any]]
    @staticmethod
    def _new_from_python_() -> PySignalWatcher: ...
    def init(self, callbacks: dict[str, Callable[..., Any]], signal_number: int) -> None: ...
    def start(self, loop: PyLoop) -> None: ...
    def stop(self, loop: PyLoop) -> None: ...

class PyTimerWatcher:
    callbacks: dict[str, Callable[..., Any]]
    @staticmethod
    def _new_from_python_() -> PyTimerWatcher: ...
    def init(self, callbacks: dict[str, Callable[..., Any]], after: float, repeat: float) -> None: ...
    def set_timer(self, after: float, repeat: float) -> None: ...
    def start(self, loop: PyLoop) -> None: ...
    def stop(self, loop: PyLoop) -> None: ...
    def again(self, loop: PyLoop) -> None: ...
    def remaining(self, loop: PyLoop) -> float: ...

class PyStatWatcher:
    callbacks: dict[str, Callable[..., Any]]
    @staticmethod
    def _new_from_python_() -> PyStatWatcher: ...
    def init(self, callbacks: dict[str, Callable[..., Any]], path: str, interval: float) -> None: ...
    def start(self, loop: PyLoop) -> None: ...
    def stop(self, loop: PyLoop) -> None: ...

def PyXOpenDisplay(display_name: Optional[str]) -> Optional[PyDisplay]: ...
def PyXCloseDisplay(display: PyDisplay) -> None: ...
def PyXDefaultRootWindow(display: PyDisplay) -> int: ...
def PyXConnectionNumber(display: PyDisplay) -> int: ...
def PyXGrabKey(
    display: PyDisplay,
    keycode: int,
    modifiers: int,
    window: int,
    owner_events: bool,
    pointer_mode: int,
    keyboard_mode: int,
) -> int: ...
def PyXUngrabKey(display: PyDisplay, keycode: int, modifiers: int, window: int) -> int: ...
def PyXCreateOverrideRedirectWindow(display: PyDisplay, parent: int, width: int, height: int) -> int: ...
def PyXMapWindow(display: PyDisplay, window: int) -> int: ...
def PyXDestroyWindow(display: PyDisplay, window: int) -> int: ...
def PyXSetInputFocus(display: PyDisplay, window: int, revert_to: int) -> int: ...
def PyXGetInputFocus(display: PyDisplay) -> tuple[int, int]: ...
def PyXGrabButton(
    display: PyDisplay,
    button: int,
    modifiers: int,
    window: int,
    owner_events: bool,
    event_mask: int,
    pointer_mode: int,
    keyboard_mode: int,
    confine_to: int,
    cursor: int,
) -> int: ...
def PyXUngrabButton(display: PyDisplay, button: int, modifiers: int, window: int) -> int: ...
def PyXSelectInput(display: PyDisplay, window: int, event_mask: int) -> int: ...
def PyXConfigureWindow(display: PyDisplay, window: int, value_mask: int, window_changes: PyXWindowChanges) -> int: ...
def PyXSync(display: PyDisplay, discard: bool) -> int: ...
def PyXSetErrorHandler(
    handler: Callable[[PyDisplay, PyXErrorEvent], None],
) -> Callable[[PyDisplay, PyXErrorEvent], None]: ...
def PyXInternAtom(display: PyDisplay, atom_name: str, only_if_exists: bool) -> int: ...
def PyXGetWindowProperty(display: PyDisplay, window: int, property_: str) -> Optional[tuple[array[int], int, str]]: ...
def PyXChangeProperty(
    display: PyDisplay,
    window: int,
    property_name: str,
    atom_type: int,
    format_: int,
    mode: int,
    property_data: array[int],
) -> int: ...
def PyXGetWindowAttributes(display: PyDisplay, window: int) -> Optional[PyXWindowAttributes]: ...
def PyXQueryTree(display: PyDisplay, window: int) -> Optional[PyXWindowTree]: ...
def PyXGetGeometry(display: PyDisplay, window: int) -> Optional[PyXWindowGeometry]: ...
def PyXScreenSaverQueryInfo(display: PyDisplay, window: int) -> Optional[PyXScreenSaverInfo]: ...
def PyXkbGetState(display: PyDisplay, device_spec: int) -> PyXkbStateRec: ...
def PyXkbLockGroup(display: PyDisplay, device_spec: int, group: int) -> int: ...
def PyXFlush(display: PyDisplay) -> int: ...
def PyXTestQueryExtension(display: PyDisplay) -> bool: ...
def PyXTestFakeKeyEvent(display: PyDisplay, keycode: int, press: bool, delay: int) -> int: ...
def PyXTestFakeButtonEvent(display: PyDisplay, button: int, press: bool, delay: int) -> int: ...
def PyXTestFakeMotionEvent(display: PyDisplay, screen: int, x: int, y: int, delay: int) -> int: ...
def PyXGetAtomName(display: PyDisplay, atom: int) -> str: ...
def PyXSendEvent(display: PyDisplay, window: int, propagate: bool, event_mask: int, xevent: PyXEvent) -> int: ...
def PyRenderSvgToArgb(filepath: str, size: int) -> Optional[bytes]: ...
def PySetWindowIcon(display: PyDisplay, window: int, filepath: Path) -> bool: ...
def PyXStringToKeysym(string: str) -> int: ...
def PyXKeysymToKeycode(display: PyDisplay, keysym: int) -> int: ...
def PyXPending(display: PyDisplay) -> int: ...
def PyXNextEvent(display: PyDisplay) -> PyXEvent: ...
def PyGetDPMSInfo(display: PyDisplay) -> PyDPMSInfo: ...
def PyDPMSEnable(display: PyDisplay) -> bool: ...
def PyDPMSDisable(display: PyDisplay) -> bool: ...
