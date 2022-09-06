from . import xlib_build as xlib_build
from ._xlib import ffi as ffi, lib as lib
from enum import Enum
from typing import Any, Dict, List, Optional, Union

Atom = int
Window = int
Display = Any
XEvent = Any
XErrorEvent = Any
XWindowAttributes = Any
ScreenSaverInfo = Any

class MASKS(Enum):
    Mod1Mask: Any
    ControlMask: Any
    ShiftMask: Any
    Mod2Mask: Any
    Mod4Mask: Any
    LockMask: Any

class EVENTS(Enum):
    KeyPress: Any
    KeyRelease: Any
    CreateNotify: Any
    DestroyNotify: Any
    FocusIn: Any
    FocusOut: Any
    PropertyNotify: Any
    MapNotify: Any
    UnmapNotify: Any

class AtomCache:
    dpy: Display
    def __init__(self, dpy: Display) -> None: ...
    def __getitem__(self, name: str) -> Atom: ...

class XEvent_:
    class Type(Enum):
        KeyPress: Any
        KeyRelease: Any
        CreateNotify: Any
        DestroyNotify: Any
        PropertyNotify: Any
        FocusIn: Any
        FocusOut: Any
        CirculateNotify: Any
        ConfigureNotify: Any
        GravityNotify: Any
        ReparentNotify: Any
        MapNotify: Any
        UnmapNotify: Any
    type: XEvent_.Type
    def __init__(self, xevent: XEvent, specific_event: Any) -> None: ...

class XKeyEvent(XEvent_):
    window: Window
    root: Window
    subwindow: Window
    time: float
    x: int
    y: int
    x_root: int
    y_root: int
    state: int
    keycode: int
    same_screen: bool
    def __init__(self, event: XEvent) -> None: ...

class XCreateWindowEvent(XEvent_):
    parent: Window
    window: Window
    x: int
    y: int
    width: int
    height: int
    border_width: int
    override_redirect: bool
    def __init__(self, event: XEvent) -> None: ...

class XDestroyWindowEvent(XEvent_):
    parent: Window
    window: Window
    def __init__(self, event: XEvent) -> None: ...

class XPropertyEvent(XEvent_):
    class State(Enum):
        PropertyNewValue: Any
        PropertyDelete: Any
    window: Window
    atom: Atom
    time: float
    state: int
    def __init__(self, event: XEvent) -> None: ...

class XFocusChangeEvent(XEvent_):
    class Mode(Enum):
        NotifyNormal: Any
        NotifyWhileGrabbed: Any
        NotifyGrab: Any
        NotifyUngrab: Any
    class Detail(Enum):
        NotifyAncestor: Any
        NotifyVirtual: Any
        NotifyInferior: Any
        NotifyNonlinear: Any
        NotifyNonlinearVirtual: Any
        NotifyPointer: Any
        NotifyPointerRoot: Any
        NotifyDetailNone: Any
    window: Window
    mode: XFocusChangeEvent.Mode
    detail: XFocusChangeEvent.Detail
    def __init__(self, event: XEvent) -> None: ...

class XErrorEvent_:
    type: XEvent_.Type
    display: Display
    resourceid: float
    serial: float
    error_code: str
    request_code: str
    minor_code: str
    def __init__(self, error: XErrorEvent) -> None: ...
    def get_message(self, size: int = ...) -> str: ...

def get_window_property(display: Display, window: Window, property: Atom, type: Atom = ..., split: bool = ...) -> Optional[Union[List[int], List[str]]]: ...
def get_window_attributes(display: Display, window: Window) -> Optional[XWindowAttributes]: ...
def get_screen_saver_info(display: Display, drawable: Window) -> Optional[ScreenSaverInfo]: ...
def set_window_property(display: Display, window: Window, property: Atom, type: Atom, format: int, values: Union[List[int], List[str]]) -> None: ...
def get_kbd_group(display: Display) -> str: ...
def set_kbd_group(display: Display, group: int) -> None: ...
def get_atom_name(display: Display, atom: Atom) -> str: ...
