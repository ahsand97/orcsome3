import math
from array import array
from enum import Enum
from typing import Any, Dict, List, Optional, Union, cast

try:
    from ._xlib import ffi, lib  # type: ignore
except ModuleNotFoundError:
    from . import xlib_build

    xlib_build.main()
finally:
    from ._xlib import ffi, lib  # type: ignore

# Type Aliases
Atom = int
Window = int
Display = Any
XEvent = Any
XErrorEvent = Any
XWindowAttributes = Any
ScreenSaverInfo = Any


class MASKS(Enum):
    Mod1Mask = int(lib.Mod1Mask)
    ControlMask = int(lib.ControlMask)
    ShiftMask = int(lib.ShiftMask)
    Mod2Mask = int(lib.Mod2Mask)
    Mod4Mask = int(lib.Mod4Mask)
    LockMask = int(lib.LockMask)


class EVENTS(Enum):
    KeyPress = int(lib.KeyPress)
    KeyRelease = int(lib.KeyRelease)
    CreateNotify = int(lib.CreateNotify)
    DestroyNotify = int(lib.DestroyNotify)
    FocusIn = int(lib.FocusIn)
    FocusOut = int(lib.FocusOut)
    PropertyNotify = int(lib.PropertyNotify)
    # Unimplemented
    MapNotify = int(lib.MapNotify)
    UnmapNotify = int(lib.UnmapNotify)


class AtomCache(object):
    def __init__(self, dpy: Display):
        self.dpy: Display = dpy
        self._cache: Dict[str, Atom] = {}

    def __getitem__(self, name: str) -> Atom:
        try:
            return self._cache[name]
        except KeyError:
            pass
        finally:
            atom: Atom = lib.XInternAtom(self.dpy, str.encode(name), False)
            self._cache[name] = atom
            return atom


class XEvent_:
    class Type(Enum):
        # Types for XKeyEvent
        KeyPress = int(lib.KeyPress)
        KeyRelease = int(lib.KeyRelease)
        # Types for XCreateWindowEvent
        CreateNotify = int(lib.CreateNotify)
        # Types for XDestroyWindowEvent
        DestroyNotify = int(lib.DestroyNotify)
        # Types for XPropertyEvent
        PropertyNotify = int(lib.PropertyNotify)
        # Types for XFocusChangeEvent
        FocusIn = int(lib.FocusIn)
        FocusOut = int(lib.FocusOut)
        # Types for XCirculateEvent
        CirculateNotify = int(lib.CirculateNotify)
        # Types for XConfigureEvent
        ConfigureNotify = int(lib.ConfigureNotify)
        # Types for XGravityEvent
        GravityNotify = int(lib.GravityNotify)
        # Types for XReparentEvent
        ReparentNotify = int(lib.ReparentNotify)
        # Types for XMapEvent
        MapNotify = int(lib.MapNotify)
        # Types for XUnmapEvent
        UnmapNotify = int(lib.UnmapNotify)

    def __init__(self, xevent: XEvent, specific_event: Any) -> None:
        self._xevent: XEvent = xevent
        self.type: XEvent_.Type = self.Type(specific_event.type)


class XKeyEvent(XEvent_):
    def __init__(self, event: XEvent) -> None:
        self._xkeyevent: lib.XKeyEvent = event.xkey
        super().__init__(xevent=event, specific_event=self._xkeyevent)
        self.window: Window = self._xkeyevent.window  # "event" window it is reported relative to
        self.root: Window = self._xkeyevent.root  # root window that the event occurred on
        self.subwindow: Window = self._xkeyevent.subwindow  # child window
        self.time: float = float(self._xkeyevent.time)  # milliseconds
        self.x: int = self._xkeyevent.x  # coordinates in event window
        self.y: int = self._xkeyevent.y  # coordinates in event window
        self.x_root: int = self._xkeyevent.x_root  # coordinates relative to root
        self.y_root: int = self._xkeyevent.y_root  # coordinates relative to root
        self.state: int = self._xkeyevent.state  # key or button mask
        self.keycode: int = self._xkeyevent.keycode  # detail
        self.same_screen: bool = bool(self._xkeyevent.same_screen)  # same screen flag


class XCreateWindowEvent(XEvent_):
    def __init__(self, event: XEvent) -> None:
        self._xcreatewindowevent: lib.XCreateWindowEvent = event.xcreatewindow
        super().__init__(xevent=event, specific_event=self._xcreatewindowevent)
        self.parent: Window = self._xcreatewindowevent.parent  # parent of the window
        self.window: Window = self._xcreatewindowevent.window  # window id of window created
        self.x: int = self._xcreatewindowevent.x  # window location
        self.y: int = self._xcreatewindowevent.y  # window location
        self.width: int = self._xcreatewindowevent.width  # size of window
        self.height: int = self._xcreatewindowevent.height  # size of window
        self.border_width: int = self._xcreatewindowevent.border_width  # border width
        self.override_redirect: bool = bool(self._xcreatewindowevent.override_redirect)  # creation should be overriden


class XDestroyWindowEvent(XEvent_):
    def __init__(self, event: XEvent) -> None:
        self._xdestroywindowevent: lib.XDestroyWindowEvent = event.xdestroywindow
        super().__init__(xevent=event, specific_event=self._xdestroywindowevent)
        self.parent: Window = self._xdestroywindowevent.event
        self.window: Window = self._xdestroywindowevent.window


class XPropertyEvent(XEvent_):
    class State(Enum):
        PropertyNewValue = int(lib.PropertyNewValue)
        PropertyDelete = int(lib.PropertyDelete)

    def __init__(self, event: XEvent) -> None:
        self._xpropertyevent: lib.XPropertyEvent = event.xproperty
        super().__init__(xevent=event, specific_event=self._xpropertyevent)
        self.window: Window = self._xpropertyevent.window
        self.atom: Atom = self._xpropertyevent.atom
        self.time: float = float(self._xpropertyevent.time)
        self.state: XPropertyEvent.State = self.State(self._xpropertyevent.state)


class XFocusChangeEvent(XEvent_):
    class Mode(Enum):
        NotifyNormal = int(lib.NotifyNormal)
        NotifyWhileGrabbed = int(lib.NotifyWhileGrabbed)
        NotifyGrab = int(lib.NotifyGrab)
        NotifyUngrab = int(lib.NotifyUngrab)

    class Detail(Enum):
        NotifyAncestor = int(lib.NotifyAncestor)
        NotifyVirtual = int(lib.NotifyVirtual)
        NotifyInferior = int(lib.NotifyInferior)
        NotifyNonlinear = int(lib.NotifyNonlinear)
        NotifyNonlinearVirtual = int(lib.NotifyNonlinearVirtual)
        NotifyPointer = int(lib.NotifyPointer)
        NotifyPointerRoot = int(lib.NotifyPointerRoot)
        NotifyDetailNone = int(lib.NotifyDetailNone)

    def __init__(self, event: XEvent) -> None:
        self._xfocuschangeevent: lib.XFocusChangeEvent = event.xfocus
        super().__init__(xevent=event, specific_event=self._xfocuschangeevent)
        self.window: Window = self._xfocuschangeevent.window
        self.mode: XFocusChangeEvent.Mode = self.Mode(self._xfocuschangeevent.mode)
        self.detail: XFocusChangeEvent.Detail = self.Detail(self._xfocuschangeevent.detail)


class XErrorEvent_:
    def __init__(self, error: XErrorEvent) -> None:
        self.type: int = error.type
        self.display: Display = error.display  # Display the event was read from
        self.resourceid: float = float(error.resourceid)  # resource id
        self.serial: float = float(error.serial)  # serial number of failed request
        self.error_code: str = str(error.error_code)  # error code of failed request
        self.request_code: str = str(error.request_code)  # Major op-code of failed request
        self.minor_code: str = str(error.minor_code)  # Minor op-code of failed request

    def get_message(self, size: int = 100) -> str:
        msg = ffi.new(f"char[{size}]")
        lib.XGetErrorText(self.display, int(self.error_code), msg, size)
        pymsg: bytes = ffi.string(msg)
        return pymsg.decode()


def get_window_property(
    display: Display, window: Window, property: Atom, type: Atom = 0, split: bool = False
) -> Optional[Union[List[int], List[str]]]:
    # Default values
    # Specifies the offset in the specified property (in 32-bit quantities) where the data is to be retrieved.
    long_offset: int = 0
    long_length: int = 50  # Specifies the length in 32-bit multiples of the data to be retrieved.
    delete: bool = False  # Specifies a Boolean value that determines whether the property is deleted.

    # Params to C function XGetWindowProperty
    type_return_ = ffi.new("Atom *")
    format_return_ = ffi.new("int *")
    nitems_return_ = ffi.new("unsigned long *")
    bytes_after_ = ffi.new("unsigned long *")
    data_ = ffi.new("unsigned char **")

    result: bytes = b""

    offset: int = long_offset
    length: int = long_length
    while True:
        lib.XGetWindowProperty(
            display,
            window,
            property,
            offset,
            length,
            delete,
            type,
            type_return_,
            format_return_,
            nitems_return_,
            bytes_after_,
            data_,
        )
        format: int = format_return_[0]
        bytes_after_return: int = bytes_after_[0]
        if format == 8:  # array of usigned char
            result += ffi.buffer(data_[0], nitems_return_[0] * array("B").itemsize)
        elif format == 16:  # array of unsigned short
            result += ffi.buffer(data_[0], nitems_return_[0] * array("H").itemsize)
        elif format == 32:  # array of unsigned long
            result += ffi.buffer(data_[0], nitems_return_[0] * array("L").itemsize)
        elif not format:
            return None
        else:
            raise Exception(f"Unknown format: {format}")
        if bytes_after_return:
            lib.XFree(data_[0])
            offset = long_length
            length = math.ceil(bytes_after_return / 4 + 1)
        else:
            break

    format = format_return_[0]
    final_result: Optional[Union[List[int], List[str]]] = None
    if format == 8:
        final_result = [result.rstrip(b"\x00").decode()]
        if split:
            final_result = [x.decode() for x in result.split(b"\x00") if len(x.decode())]
    elif format == 16:
        final_result = array("H", result).tolist()
    elif format == 32:
        final_result = array("L", result).tolist()
    else:
        raise Exception(f"Unknown format: {format}")

    lib.XFree(data_[0])
    return final_result


def get_window_attributes(display: Display, window: Window) -> Optional[XWindowAttributes]:
    data_ = ffi.new("XWindowAttributes *")
    status: int = lib.XGetWindowAttributes(display, window, data_)
    if not status:
        return None
    return data_[0]


def get_screen_saver_info(display: Display, drawable: Window) -> Optional[ScreenSaverInfo]:
    data_ = ffi.new("XScreenSaverInfo *")
    status: int = lib.XScreenSaverQueryInfo(display, drawable, data_)
    if not status:
        return None
    return data_[0]


def set_window_property(
    display: Display, window: Window, property: Atom, type: Atom, format: int, values: Union[List[int], List[str]]
) -> None:
    data: Any = None
    if format == 8:  # array of usigned char
        data = cast(List[str], values)
    elif format == 16:  # array of unsigned short
        data = ffi.cast("unsigned char *", ffi.new("unsigned short[]", cast(List[int], values)))
    elif format == 32:  # array of unsigned long
        data = ffi.cast("unsigned char *", ffi.new("unsigned long[]", cast(List[int], values)))
    else:
        raise Exception(f"Unknown format {format}")

    lib.XChangeProperty(display, window, property, type, format, lib.PropModeReplace, data, len(values))


def get_kbd_group(display: Display) -> str:
    state = ffi.new("XkbStateRec *")
    lib.XkbGetState(display, lib.XkbUseCoreKbd, state)
    return str(state[0].group)


def set_kbd_group(display: Display, group: int) -> None:
    lib.XkbLockGroup(display, lib.XkbUseCoreKbd, group)
    lib.XFlush(display)


def get_atom_name(display: Display, atom: Atom) -> str:
    """
    Returns the name associated with an Atom if the Atom exists
    """
    atom_name = lib.XGetAtomName(display, atom)
    if not atom_name:
        return ""
    return bytes(ffi.string(atom_name)).decode()
