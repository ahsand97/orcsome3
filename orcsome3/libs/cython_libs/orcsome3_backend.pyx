import enum as pyenum
from typing import Any, Callable, Optional, Union, cast
from cpython cimport array as carray
import array as pyarray
cimport cairo.cairo as cairo
cimport imagemagick.imagemagick as imagemagick
cimport libgd.libgd as libgd
cimport libev.libev as libev
cimport resvg.resvg as resvg
cimport xlib.xlib as xlib
from libc.math cimport ceil
from libc.stddef cimport size_t
from libc.stdlib cimport calloc, free, malloc, realloc
from libc.string cimport memcpy, memset
from pathlib import Path
from libc.stdint cimport uint32_t, uintptr_t
from cython.operator cimport dereference


# Structs

ctypedef struct IconData:
    int length
    unsigned char *data
    bint magick_memory


_c_string_cache: dict[str, bytes] = {}
_intern_cache: dict[tuple[int, str, bool], int] = {}
_atom_name_cache: dict[tuple[int, int], str] = {}


cdef char *get_char_from_py_string(str string):
    """Return a stable C string pointer backed by a module-level bytes cache."""
    cdef bytes py_bytes = _c_string_cache.get(string)
    if py_bytes is None:
        py_bytes = string.encode()
        _c_string_cache[string] = py_bytes
    return <char *>py_bytes


cdef void release_icon_data(IconData *icon_data):
    if icon_data.data == NULL:
        return
    if icon_data.magick_memory:
        imagemagick.MagickRelinquishMemory(icon_data.data)
    else:
        free(icon_data.data)
    icon_data.data = NULL
    icon_data.length = 0
    icon_data.magick_memory = False

cdef class PyDisplay:
    cdef xlib.Display *_display

    @staticmethod
    cdef PyDisplay _new_(xlib.Display *display):
        cdef PyDisplay pydisplay = PyDisplay()
        pydisplay._display = display
        return pydisplay

cdef class PyXEvent:
    _type: EVENT_TYPES
    cdef xlib.XEvent _native_event
    cdef public unsigned long serial
    cdef public int send_event
    cdef public PyDisplay display
    cdef public xlib.Window window

    @property
    def type(self) -> EVENT_TYPES:
        return self._type

    @type.setter
    def type(self, type: EVENT_TYPES) -> None:
        self._type = type

    @staticmethod
    cdef PyXEvent _new_(xlib.XEvent *event):
        cdef PyXEvent pyXEvent = PyXEvent()
        pyXEvent._set_attributes_from_event_(
            event=dereference(event), serial=event.xany.serial, display=event.xany.display, window=event.xany.window
        )
        return pyXEvent

    cdef _set_attributes_from_event_(self, xlib.XEvent event, unsigned long serial, xlib.Display *display, xlib.Window window):
        """
        Method used to set the common attributes of all XEvents
        """
        self._native_event = event
        self.type = EVENT_TYPES(event.type)
        self.serial = serial
        self.send_event = event.xany.send_event
        self.display = PyDisplay._new_(display=display)
        self.window = window
    
    def _get_specific_event_(self) -> PyXEvent:
        """
        Method used to retrieve the specific event based in the TYPE
        """
        if self.type == EVENT_TYPES.ErrorEvent:
            return PyXErrorEvent._new_(error_event=&self._native_event.xerror)
        elif self.type == EVENT_TYPES.KeyPress or self.type == EVENT_TYPES.KeyRelease:
            return PyXKeyEvent._new_(key_event=&self._native_event.xkey)
        elif self.type == EVENT_TYPES.ButtonPress or self.type == EVENT_TYPES.ButtonRelease:
            return PyXButtonEvent._new_(button_event=&self._native_event.xbutton)
        elif self.type == EVENT_TYPES.FocusIn or self.type == EVENT_TYPES.FocusOut:
            return PyXFocusChangeEvent._new_(focus_change_event=&self._native_event.xfocus)
        elif self.type == EVENT_TYPES.CreateNotify:
            return PyXCreateWindowEvent._new_(create_window_event=&self._native_event.xcreatewindow)
        elif self.type == EVENT_TYPES.DestroyNotify:
            return PyXDestroyWindowEvent._new_(destroy_window_event=&self._native_event.xdestroywindow)
        elif self.type == EVENT_TYPES.PropertyNotify:
            return PyXPropertyEvent._new_(property_event=&self._native_event.xproperty)
        elif self.type == EVENT_TYPES.ClientMessage:
            return PyXClientMessageEvent._new_(client_message_event=&self._native_event.xclient)
        return self

cdef class PyXErrorEvent(PyXEvent):
    cdef public xlib.XID resourceid
    cdef public unsigned char error_code
    cdef public unsigned char request_code
    cdef public unsigned char minor_code
    _msg: str

    @property
    def msg(self) -> str:
        return self._msg

    @msg.setter
    def msg(self, msg: str) -> None:
        self._msg = msg

    @staticmethod
    cdef PyXErrorEvent _new_(xlib.XErrorEvent *error_event):
        cdef PyXErrorEvent pyXErrorEvent = PyXErrorEvent()
        pyXErrorEvent._set_attributes_from_event_(
            event=<xlib.XEvent>dereference(error_event), serial=error_event.serial, display=error_event.display, window=(<xlib.XEvent *>error_event).xany.window
        )
        pyXErrorEvent.resourceid = error_event.resourceid
        pyXErrorEvent.error_code = error_event.error_code
        pyXErrorEvent.request_code = error_event.request_code
        pyXErrorEvent.minor_code = error_event.minor_code
        pyXErrorEvent.get_message()
        return pyXErrorEvent

    cdef get_message(self):
        cdef int length = 1024
        cdef char *buffer = <char *>malloc(size=<size_t>(sizeof(char) * length))
        if buffer == NULL:
            self.msg = ""
            return
        xlib.XGetErrorText(display=self.display._display, code=<int>self.error_code, buffer_return=buffer, length=length)
        self.msg = buffer[:length].decode(errors="replace")
        free(buffer)

cdef class PyXKeyEvent(PyXEvent):
    cdef public xlib.Window root
    cdef public xlib.Window subwindow
    cdef public xlib.Time time
    cdef public int x, y
    cdef public int x_root, y_root
    cdef public unsigned int state
    cdef public unsigned int keycode
    cdef public int same_screen

    @staticmethod
    cdef PyXKeyEvent _new_(xlib.XKeyEvent *key_event):
        cdef PyXKeyEvent pyXKeyEvent = PyXKeyEvent()
        pyXKeyEvent._set_attributes_from_event_(
            event=<xlib.XEvent>dereference(key_event), serial=key_event.serial, display=key_event.display, window=key_event.window
        )
        pyXKeyEvent.root = key_event.root
        pyXKeyEvent.subwindow = key_event.subwindow
        pyXKeyEvent.time = key_event.time
        pyXKeyEvent.x = key_event.x
        pyXKeyEvent.y = key_event.y
        pyXKeyEvent.x_root = key_event.x_root
        pyXKeyEvent.y_root = key_event.y_root
        pyXKeyEvent.state = key_event.state
        pyXKeyEvent.keycode = key_event.keycode
        pyXKeyEvent.same_screen = key_event.same_screen
        return pyXKeyEvent

    @staticmethod
    def _new_from_python_(
        int type,
        unsigned long serial,
        send_event: bool,
        PyDisplay display,
        xlib.Window window,
        xlib.Window root,
        xlib.Window subwindow,
        xlib.Time time,
        int x,
        int y,
        int x_root,
        int y_root,
        unsigned int state,
        unsigned int keycode,
        same_screen: bool
    ) -> PyXKeyEvent:
        cdef xlib.XKeyEvent xKeyEvent = xlib.XKeyEvent(  # type: ignore
            type=type,
            serial=serial,
            send_event=<int>send_event,
            display=display._display,
            window=window,
            root=root,
            subwindow=subwindow,
            time=time,
            x=x,
            y=y,
            x_root=x_root,
            y_root=y_root,
            state=state,
            keycode=keycode,
            same_screen=<int>same_screen
        )
        return PyXKeyEvent._new_(key_event=&xKeyEvent)

cdef class PyXButtonEvent(PyXEvent):
    cdef public xlib.Window root
    cdef public xlib.Window subwindow
    cdef public xlib.Time time
    cdef public int x, y
    cdef public int x_root, y_root
    cdef public unsigned int state
    _button: BUTTONS
    cdef public int same_screen

    @property
    def button(self) -> BUTTONS:
        return self._button

    @button.setter
    def button(self, button: BUTTONS) -> None:
        self._button = button

    @staticmethod
    cdef PyXButtonEvent _new_(xlib.XButtonEvent *button_event):
        cdef PyXButtonEvent pyXButtonEvent = PyXButtonEvent()
        pyXButtonEvent._set_attributes_from_event_(
            event=<xlib.XEvent>dereference(button_event), serial=button_event.serial, display=button_event.display, window=button_event.window
        )
        pyXButtonEvent.root = button_event.root
        pyXButtonEvent.subwindow = button_event.subwindow
        pyXButtonEvent.time = button_event.time
        pyXButtonEvent.x = button_event.x
        pyXButtonEvent.y = button_event.y
        pyXButtonEvent.x_root = button_event.x_root
        pyXButtonEvent.y_root = button_event.y_root
        pyXButtonEvent.state = button_event.state
        pyXButtonEvent.button = BUTTONS(button_event.button)
        pyXButtonEvent.same_screen = button_event.same_screen
        return pyXButtonEvent

    @staticmethod
    def _new_from_python_(
        int type,
        unsigned long serial,
        send_event: bool,
        PyDisplay display,
        xlib.Window window,
        xlib.Window root,
        xlib.Window subwindow,
        xlib.Time time,
        int x,
        int y,
        int x_root,
        int y_root,
        unsigned int state,
        unsigned int button,
        same_screen: bool
    ) -> PyXButtonEvent:
        cdef xlib.XButtonEvent xButtonEvent = xlib.XButtonEvent(  # type: ignore
            type=type,
            serial=serial,
            send_event=<int>send_event,
            display=display._display,
            window=window,
            root=root,
            subwindow=subwindow,
            time=time,
            x=x,
            y=y,
            x_root=x_root,
            y_root=y_root,
            state=state,
            button=button,
            same_screen=<int>same_screen
        )
        return PyXButtonEvent._new_(button_event=&xButtonEvent)

cdef class PyXFocusChangeEvent(PyXEvent):
    _mode: NOTIFY_MODES
    _detail: NOTIFY_DETAILS

    @property
    def mode(self) -> NOTIFY_MODES:
        return self._mode

    @mode.setter
    def mode(self, mode: NOTIFY_MODES) -> None:
        self._mode = mode

    @property
    def detail(self) -> NOTIFY_DETAILS:
        return self._detail

    @detail.setter
    def detail(self, detail: NOTIFY_DETAILS) -> None:
        self._detail = detail

    @staticmethod
    cdef PyXFocusChangeEvent _new_(xlib.XFocusChangeEvent *focus_change_event):
        cdef PyXFocusChangeEvent pyXFocusChangeEvent = PyXFocusChangeEvent()
        pyXFocusChangeEvent._set_attributes_from_event_(
            event=<xlib.XEvent>dereference(focus_change_event), serial=focus_change_event.serial, display=focus_change_event.display, window=focus_change_event.window
        )
        pyXFocusChangeEvent.mode = NOTIFY_MODES(focus_change_event.mode)
        pyXFocusChangeEvent.detail = NOTIFY_DETAILS(focus_change_event.detail)
        return pyXFocusChangeEvent

    @staticmethod
    def _new_from_python_(
        int type,
        unsigned long serial,
        send_event: bool,
        PyDisplay display,
        xlib.Window window,
        int mode,
        int detail
    ) -> PyXFocusChangeEvent:
        cdef xlib.XFocusChangeEvent xFocusChangeEvent = xlib.XFocusChangeEvent(  # type: ignore
            type=type,
            serial=serial,
            send_event=<int>send_event,
            display=display._display,
            window=window,
            mode=mode,
            detail=detail
        )
        return PyXFocusChangeEvent._new_(focus_change_event=&xFocusChangeEvent)

cdef class PyXCreateWindowEvent(PyXEvent):
    cdef public xlib.Window parent
    cdef public int x, y
    cdef public int width, height
    cdef public int border_width
    cdef public int override_redirect

    @staticmethod
    cdef PyXCreateWindowEvent _new_(xlib.XCreateWindowEvent *create_window_event):
        cdef PyXCreateWindowEvent pyXCreateWindowEvent = PyXCreateWindowEvent()
        pyXCreateWindowEvent._set_attributes_from_event_(
            event=<xlib.XEvent>dereference(create_window_event), serial=create_window_event.serial, display=create_window_event.display, window=create_window_event.window
        )
        pyXCreateWindowEvent.parent = create_window_event.parent
        pyXCreateWindowEvent.x = create_window_event.x
        pyXCreateWindowEvent.y = create_window_event.y
        pyXCreateWindowEvent.width = create_window_event.width
        pyXCreateWindowEvent.height = create_window_event.height
        pyXCreateWindowEvent.border_width = create_window_event.border_width
        pyXCreateWindowEvent.override_redirect = create_window_event.override_redirect
        return pyXCreateWindowEvent

    @staticmethod
    def _new_from_python_(
        int type,
        unsigned long serial,
        send_event: bool,
        PyDisplay display,
        xlib.Window parent,
        xlib.Window window,
        int x,
        int y,
        int width,
        int height,
        int border_width,
        override_redirect: bool
    ) -> PyXCreateWindowEvent:
        cdef xlib.XCreateWindowEvent xCreateWindowEvent = xlib.XCreateWindowEvent(  # type: ignore
            type=type,
            serial=serial,
            send_event=<int>send_event,
            display=display._display,
            parent=parent,
            window=window,
            x=x,
            y=y,
            width=width,
            height=height,
            border_width=border_width,
            override_redirect=<int>override_redirect
        )
        return PyXCreateWindowEvent._new_(create_window_event=&xCreateWindowEvent)

cdef class PyXDestroyWindowEvent(PyXEvent):
    cdef public xlib.Window event

    @staticmethod
    cdef PyXDestroyWindowEvent _new_(xlib.XDestroyWindowEvent *destroy_window_event):
        cdef PyXDestroyWindowEvent pyXDestroyWindowEvent = PyXDestroyWindowEvent()
        pyXDestroyWindowEvent._set_attributes_from_event_(
            event=<xlib.XEvent>dereference(destroy_window_event), serial=destroy_window_event.serial, display=destroy_window_event.display, window=destroy_window_event.window
        )
        pyXDestroyWindowEvent.event = destroy_window_event.event
        return pyXDestroyWindowEvent

    @staticmethod
    def _new_from_python_(
        int type,
        unsigned long serial,
        send_event: bool,
        PyDisplay display,
        xlib.Window event,
        xlib.Window window
    ) -> PyXDestroyWindowEvent:
        cdef xlib.XDestroyWindowEvent xDestroyWindowEvent = xlib.XDestroyWindowEvent(  # type: ignore
            type=type,
            serial=serial,
            send_event=<int>send_event,
            display=display._display,
            event=event,
            window=window
        )
        return PyXDestroyWindowEvent._new_(destroy_window_event=&xDestroyWindowEvent)

cdef class PyXPropertyEvent(PyXEvent):
    cdef public xlib.Atom atom
    cdef public xlib.Time time
    _state: PROPERTY_NOTIFICATION

    @property
    def state(self) -> PROPERTY_NOTIFICATION:
        return self._state

    @state.setter
    def state(self, state: PROPERTY_NOTIFICATION) -> None:
        self._state = state

    @staticmethod
    cdef PyXPropertyEvent _new_(xlib.XPropertyEvent *property_event):
        cdef PyXPropertyEvent pyXPropertyEvent = PyXPropertyEvent()
        pyXPropertyEvent._set_attributes_from_event_(
            event=<xlib.XEvent>dereference(property_event), serial=property_event.serial, display=property_event.display, window=property_event.window
        )
        pyXPropertyEvent.atom = property_event.atom
        pyXPropertyEvent.time = property_event.time
        pyXPropertyEvent.state = PROPERTY_NOTIFICATION(property_event.state)
        return pyXPropertyEvent

    @staticmethod
    def _new_from_python_(
        int type,
        unsigned long serial,
        send_event: bool,
        PyDisplay display,
        xlib.Window window,
        xlib.Atom atom,
        xlib.Time time,
        int state
    ) -> PyXPropertyEvent:
        cdef xlib.XPropertyEvent xPropertyEvent = xlib.XPropertyEvent(  # type: ignore
            type=type,
            serial=serial,
            send_event=<int>send_event,
            display=display._display,
            window=window,
            atom=atom,
            time=time,
            state=state,
        )
        return PyXPropertyEvent._new_(property_event=&xPropertyEvent)

cdef class PyXClientMessageEvent(PyXEvent):
    cdef public xlib.Atom message_type
    _format: PROPERTY_FORMAT
    cdef public carray.array data

    @property
    def format(self) -> PROPERTY_FORMAT:
        return self._format

    @format.setter
    def format(self, format: PROPERTY_FORMAT) -> None:
        self._format = format

    @staticmethod
    cdef PyXClientMessageEvent _new_(xlib.XClientMessageEvent *client_message_event):
        cdef PyXClientMessageEvent pyXClientMessageEvent = PyXClientMessageEvent()
        pyXClientMessageEvent._set_attributes_from_event_(
            event=<xlib.XEvent>dereference(client_message_event), serial=client_message_event.serial, display=client_message_event.display, window=client_message_event.window
        )
        pyXClientMessageEvent.message_type = client_message_event.message_type
        pyXClientMessageEvent.format = PROPERTY_FORMAT.new_from_value(value=client_message_event.format)
        list_with_data: list[int] = []
        if pyXClientMessageEvent.format == PROPERTY_FORMAT.CHAR:
            for i in range(20):
                list_with_data.append(client_message_event.b[i])
        elif pyXClientMessageEvent.format == PROPERTY_FORMAT.SHORT:
            for i in range(10):
                list_with_data.append(client_message_event.s[i])
        elif pyXClientMessageEvent.format == PROPERTY_FORMAT.LONG:
            for i in range(5):
                list_with_data.append(client_message_event.l[i])
        pyXClientMessageEvent.data = carray.array(pyXClientMessageEvent.format.value[1], list_with_data)
        return pyXClientMessageEvent

    @staticmethod
    def _new_from_python_(
        int type,
        unsigned long serial,
        send_event: bool,
        PyDisplay display,
        xlib.Window window,
        xlib.Atom message_type,
        int format,
        data: pyarray.array[int]
    ) -> PyXClientMessageEvent:
        cdef xlib.XClientMessageEvent xClientMessageEvent
        memset(&xClientMessageEvent, 0, sizeof(xClientMessageEvent))
        xClientMessageEvent.type = type
        xClientMessageEvent.serial = serial
        xClientMessageEvent.send_event = <int>send_event
        xClientMessageEvent.display = display._display
        xClientMessageEvent.window = window
        xClientMessageEvent.message_type = message_type
        xClientMessageEvent.format = format
        pyformat: PROPERTY_FORMAT = PROPERTY_FORMAT.new_from_value(value=format)
        if pyformat == PROPERTY_FORMAT.CHAR:
            for i in range(min(20, len(data))):
                xClientMessageEvent.b[i] = <char>data[i]
        elif pyformat == PROPERTY_FORMAT.SHORT:
            for i in range(min(10, len(data))):
                xClientMessageEvent.s[i] = <short>data[i]
        elif pyformat == PROPERTY_FORMAT.LONG:
            for i in range(min(5, len(data))):
                xClientMessageEvent.l[i] = <long>data[i]
        return PyXClientMessageEvent._new_(client_message_event=&xClientMessageEvent)

cdef class PyXWindowChanges:
    cdef xlib.XWindowChanges _xwindowchanges
    cdef public int x
    cdef public int y
    cdef public int width
    cdef public int height
    cdef public int border_width
    cdef public int sibling_window
    _stack_mode: WINDOW_STACKING_METHOD

    @property
    def stack_mode(self) -> WINDOW_STACKING_METHOD:
        return self._stack_mode

    @stack_mode.setter
    def stack_mode(self, stack_mode: WINDOW_STACKING_METHOD) -> None:
        self._stack_mode = stack_mode

    @staticmethod
    cdef PyXWindowChanges _new_(xlib.XWindowChanges window_changes):
        cdef PyXWindowChanges pyXWindowChanges = PyXWindowChanges()
        pyXWindowChanges._xwindowchanges = window_changes
        pyXWindowChanges.x = window_changes.x
        pyXWindowChanges.y = window_changes.y
        pyXWindowChanges.width = window_changes.width
        pyXWindowChanges.height = window_changes.height
        pyXWindowChanges.border_width = window_changes.border_width
        pyXWindowChanges.sibling_window = window_changes.sibling
        pyXWindowChanges.stack_mode = WINDOW_STACKING_METHOD(window_changes.stack_mode)
        return pyXWindowChanges

    @staticmethod
    def _new_from_python_(int x, int y, int width, int height, int border_width, int sibling_window, int stack_mode) -> PyXWindowChanges:
        cdef xlib.XWindowChanges xWindowChanges = xlib.XWindowChanges(  # type: ignore
            x=x,
            y=y,
            width=width,
            height=height,
            border_width=border_width,
            sibling=sibling_window,
            stack_mode=stack_mode
        )
        return PyXWindowChanges._new_(window_changes=xWindowChanges)

cdef class PyXWindowAttributes:
    cdef public int x
    cdef public int y
    cdef public int width
    cdef public int height
    cdef public int border_width
    cdef public int depth
    cdef public xlib.Window root
    cdef public int map_state
    cdef public int override_redirect

    @staticmethod
    cdef PyXWindowAttributes _new_(xlib.XWindowAttributes window_attributes):
        cdef PyXWindowAttributes pyXWindowAttributes = PyXWindowAttributes()
        pyXWindowAttributes.x = window_attributes.x
        pyXWindowAttributes.y = window_attributes.y
        pyXWindowAttributes.width = window_attributes.width
        pyXWindowAttributes.height = window_attributes.height
        pyXWindowAttributes.border_width = window_attributes.border_width
        pyXWindowAttributes.depth = window_attributes.depth
        pyXWindowAttributes.root = window_attributes.root
        pyXWindowAttributes.map_state = window_attributes.map_state
        pyXWindowAttributes.override_redirect = window_attributes.override_redirect
        return pyXWindowAttributes

cdef class PyXWindowTree:
    cdef public xlib.Window window
    cdef public xlib.Window root
    cdef public xlib.Window parent
    _children: list[int]

    @property
    def children(self) -> list[int]:
        return self._children

    @children.setter
    def children(self, children: list[int]) -> None:
        self._children = children

    @staticmethod
    cdef PyXWindowTree _new_(xlib.Window window, xlib.Window root, xlib.Window parent, children: list[int]):
        cdef PyXWindowTree pyXWindowTree = PyXWindowTree()
        pyXWindowTree.window = window
        pyXWindowTree.root = root
        pyXWindowTree.parent = parent
        pyXWindowTree.children = children
        return pyXWindowTree

cdef class PyXWindowGeometry:
    cdef public xlib.Window window
    cdef public xlib.Window root
    cdef public int x, y
    cdef public unsigned int width, height
    cdef public unsigned int border_width
    cdef public unsigned int depth

    @staticmethod
    cdef PyXWindowGeometry _new_(
        xlib.Window window,
        xlib.Window root,
        int x, int y,
        unsigned int width, unsigned int height,
        unsigned int border_width,
        unsigned int depth
    ):
        cdef PyXWindowGeometry pyXWindowGeometry = PyXWindowGeometry()
        pyXWindowGeometry.window = window
        pyXWindowGeometry.root = root
        pyXWindowGeometry.x = x
        pyXWindowGeometry.y = y
        pyXWindowGeometry.width = width
        pyXWindowGeometry.height = height
        pyXWindowGeometry.border_width = border_width
        pyXWindowGeometry.depth = depth
        return pyXWindowGeometry

cdef class PyXScreenSaverInfo:
    cdef public xlib.Window window
    cdef public int state
    cdef public int kind
    cdef public unsigned long til_or_since
    cdef public unsigned long idle
    cdef public unsigned long event_mask

    @staticmethod
    cdef PyXScreenSaverInfo _new_(xlib.XScreenSaverInfo info):
        cdef PyXScreenSaverInfo pyXScreenSaverInfo = PyXScreenSaverInfo()
        pyXScreenSaverInfo.window = info.window
        pyXScreenSaverInfo.state = info.state
        pyXScreenSaverInfo.kind = info.kind
        pyXScreenSaverInfo.til_or_since = info.til_or_since
        pyXScreenSaverInfo.idle = info.idle
        pyXScreenSaverInfo.event_mask = info.eventMask
        return pyXScreenSaverInfo

cdef class PyXkbStateRec:
    cdef public unsigned char group
    cdef public unsigned char locked_group
    cdef public unsigned short base_group
    cdef public unsigned short latched_group
    cdef public unsigned char mods
    cdef public unsigned char base_mods
    cdef public unsigned char latched_mods
    cdef public unsigned char locked_mods
    cdef public unsigned char compat_state
    cdef public unsigned char grab_mods
    cdef public unsigned char compat_grab_mods
    cdef public unsigned char lookup_mods
    cdef public unsigned char compat_lookup_mods
    cdef public unsigned short ptr_buttons

    @staticmethod
    cdef PyXkbStateRec _new_(xlib.XkbStateRec kb_state):
        cdef PyXkbStateRec pyXkbStateRec = PyXkbStateRec()
        pyXkbStateRec.group = kb_state.group
        pyXkbStateRec.locked_group = kb_state.locked_group
        pyXkbStateRec.base_group = kb_state.base_group
        pyXkbStateRec.latched_group = kb_state.latched_group
        pyXkbStateRec.mods = kb_state.mods
        pyXkbStateRec.base_mods = kb_state.base_mods
        pyXkbStateRec.latched_mods = kb_state.latched_mods
        pyXkbStateRec.locked_mods = kb_state.locked_mods
        pyXkbStateRec.compat_state = kb_state.compat_state
        pyXkbStateRec.grab_mods = kb_state.grab_mods
        pyXkbStateRec.compat_grab_mods = kb_state.compat_grab_mods
        pyXkbStateRec.lookup_mods = kb_state.lookup_mods
        pyXkbStateRec.compat_lookup_mods = kb_state.compat_lookup_mods
        pyXkbStateRec.ptr_buttons = kb_state.ptr_buttons
        return pyXkbStateRec

cdef class PyDPMSInfo:
    cdef public xlib.BOOL state
    _power_level: DPMS_POWER_LEVEL

    @property
    def power_level(self) -> DPMS_POWER_LEVEL:
        return self._power_level

    @power_level.setter
    def power_level(self, power_level: DPMS_POWER_LEVEL) -> None:
        self._power_level = power_level

    @staticmethod
    cdef PyDPMSInfo _new_(xlib.BOOL state, xlib.CARD16 power_level):
        cdef PyDPMSInfo pyDPMSInfo = PyDPMSInfo()
        pyDPMSInfo.state = state
        pyDPMSInfo.power_level = DPMS_POWER_LEVEL(power_level)
        return pyDPMSInfo

cdef class PyLoop:
    cdef libev.evLoop *loop

    @staticmethod
    cdef PyLoop _new_(libev.ev_loop *loop):
        cdef PyLoop pyloop = PyLoop()
        pyloop.loop = loop
        return pyloop

    @staticmethod
    def _new_from_python_(flags: Union[int, list[int]]) -> PyLoop:
        cdef int new_flags = PYLOOP_NEW_LOOP_FLAGS.EVFLAG_AUTO.value
        if isinstance(flags, list):
            new_flags = flags[0]
            for flag in flags:
                new_flags |= flag
        else:
            new_flags = flags
        cdef libev.evLoop *loop = libev.ev_loop_new(flags=<unsigned int>new_flags)
        return PyLoop._new_(loop=loop)

    def run(self, flags: Union[int, list[int]]) -> None:
        cdef int run_flags = PYLOOP_RUN_LOOP_FLAGS.EVRUN_ALWAYS.value
        if isinstance(flags, list):
            run_flags = flags[0]
            for flag in flags:
                run_flags |= flag
        else:
            run_flags = flags
        libev.ev_run(loop=self.loop, flags=run_flags)

    def break_(self, how_to_break_flag: int) -> None:
        libev.ev_break(loop=self.loop, how=how_to_break_flag)

    def destroy(self) -> None:
        libev.ev_loop_destroy(loop=self.loop)

cdef class PyIOWatcher:
    cdef libev.ev_io *io_watcher
    cdef bint _owns_watcher
    _callbacks: dict[str, Callable[..., Any]]

    @property
    def callbacks(self) -> dict[str, Callable[..., Any]]:
        return self._callbacks

    @callbacks.setter
    def callbacks(self, callbacks: dict[str, Callable[..., Any]]) -> None:
        self._callbacks = callbacks

    @staticmethod
    cdef PyIOWatcher _new_(libev.ev_io *io_watcher = NULL, callbacks: Optional[dict[str, Callable[..., Any]]] = None):
        cdef PyIOWatcher py_io_watcher = PyIOWatcher()
        if io_watcher == NULL:
            io_watcher = <libev.ev_io *>malloc(size=<size_t>sizeof(libev.ev_io))
            py_io_watcher._owns_watcher = True
        else:
            py_io_watcher._owns_watcher = False
        py_io_watcher.io_watcher = io_watcher
        if callbacks is not None:
            py_io_watcher.callbacks = callbacks
        return py_io_watcher

    def __dealloc__(self):
        if self._owns_watcher and self.io_watcher != NULL:
            free(self.io_watcher)
            self.io_watcher = NULL

    @staticmethod
    def _new_from_python_() -> PyIOWatcher:
        return PyIOWatcher._new_()

    def init(self, callbacks: dict[str, Callable[..., Any]], file_descriptor: int, events: int) -> None:
        self.callbacks = callbacks
        self.io_watcher.data = <void *>self.callbacks
        libev.ev_io_init(
            ev_io=self.io_watcher, callback=<libev.io_cb>PyIOWatcher.default_callback, fd=file_descriptor, events=events
        )

    def start(self, loop: PyLoop) -> None:
        libev.ev_io_start(loop=loop.loop, watcher=self.io_watcher)

    def stop(self, loop: PyLoop) -> None:
        libev.ev_io_stop(loop=loop.loop, watcher=self.io_watcher)

    @staticmethod
    cdef default_callback(libev.ev_loop *ev_loop, libev.ev_io *io_watcher, int revents):
        callbacks_dict: dict[str, Callable[..., Any]] = <dict>io_watcher.data
        callbacks_dict["default"](
            PyLoop._new_(loop=ev_loop),
            PyIOWatcher._new_(io_watcher=io_watcher, callbacks=callbacks_dict),
            revents
        )

cdef class PySignalWatcher:
    cdef libev.ev_signal *signal_watcher
    cdef bint _owns_watcher
    _callbacks: dict[str, Callable[..., Any]]

    @property
    def callbacks(self) -> dict[str, Callable[..., Any]]:
        return self._callbacks

    @callbacks.setter
    def callbacks(self, callbacks: dict[str, Callable[..., Any]]) -> None:
        self._callbacks = callbacks

    @staticmethod
    cdef PySignalWatcher _new_(libev.ev_signal *signal_watcher = NULL, callbacks: Optional[dict[str, Callable[..., Any]]] = None):
        cdef PySignalWatcher py_signal_watcher = PySignalWatcher()
        if signal_watcher == NULL:
            signal_watcher = <libev.ev_signal *>malloc(size=<size_t>sizeof(libev.ev_signal))
            py_signal_watcher._owns_watcher = True
        else:
            py_signal_watcher._owns_watcher = False
        py_signal_watcher.signal_watcher = signal_watcher
        if callbacks is not None:
            py_signal_watcher.callbacks = callbacks
        return py_signal_watcher

    def __dealloc__(self):
        if self._owns_watcher and self.signal_watcher != NULL:
            free(self.signal_watcher)
            self.signal_watcher = NULL

    @staticmethod
    def _new_from_python_() -> PySignalWatcher:
        return PySignalWatcher._new_()

    def init(self, callbacks: dict[str, Callable[..., Any]], signal_number: int) -> None:
        self.callbacks = callbacks
        self.signal_watcher.data = <void *>self.callbacks
        libev.ev_signal_init(
            signal=self.signal_watcher,
            callback=<libev.signal_cb>PySignalWatcher.default_callback,
            signum=signal_number,
        )

    def start(self, loop: PyLoop) -> None:
        libev.ev_signal_start(loop=loop.loop, signal=self.signal_watcher)

    def stop(self, loop: PyLoop) -> None:
        libev.ev_signal_stop(loop=loop.loop, signal=self.signal_watcher)

    @staticmethod
    cdef default_callback(libev.ev_loop *ev_loop, libev.ev_signal *signal_watcher, int revents):
        callbacks_dict: dict[str, Callable[..., Any]] = <dict>signal_watcher.data
        callbacks_dict["default"](
            PyLoop._new_(loop=ev_loop),
            PySignalWatcher._new_(signal_watcher=signal_watcher, callbacks=callbacks_dict),
            revents
        )

cdef class PyTimerWatcher:
    cdef libev.ev_timer *timer_watcher
    cdef bint _owns_watcher
    _callbacks: dict[str, Callable[..., Any]]

    @property
    def callbacks(self) -> dict[str, Callable[..., Any]]:
        return self._callbacks

    @callbacks.setter
    def callbacks(self, callbacks: dict[str, Callable[..., Any]]) -> None:
        self._callbacks = callbacks

    @staticmethod
    cdef PyTimerWatcher _new_(libev.ev_timer *timer_watcher = NULL, callbacks: Optional[dict[str, Callable[..., Any]]] = None):
        cdef PyTimerWatcher py_timer_watcher = PyTimerWatcher()
        if timer_watcher == NULL:
            timer_watcher = <libev.ev_timer *>malloc(size=<size_t>sizeof(libev.ev_timer))
            py_timer_watcher._owns_watcher = True
        else:
            py_timer_watcher._owns_watcher = False
        py_timer_watcher.timer_watcher = timer_watcher
        if callbacks is not None:
            py_timer_watcher.callbacks = callbacks
        return py_timer_watcher

    def __dealloc__(self):
        if self._owns_watcher and self.timer_watcher != NULL:
            free(self.timer_watcher)
            self.timer_watcher = NULL

    @staticmethod
    def _new_from_python_() -> PyTimerWatcher:
        return PyTimerWatcher._new_()

    def init(self, callbacks: dict[str, Callable[..., Any]], after: float, repeat: float) -> None:
        self.callbacks = callbacks
        self.timer_watcher.data = <void *>self.callbacks
        libev.ev_timer_init(
            timer=self.timer_watcher,
            callback=<libev.timer_cb>PyTimerWatcher.default_callback,
            after=<libev.ev_tstamp>after,
            repeat=<libev.ev_tstamp>repeat,
        )

    def set_timer(self, after: float, repeat: float) -> None:
        libev.ev_timer_set(timer=self.timer_watcher, after=<libev.ev_tstamp>after, repeat=<libev.ev_tstamp>repeat)

    def start(self, loop: PyLoop) -> None:
        libev.ev_timer_start(loop=loop.loop, timer=self.timer_watcher)

    def stop(self, loop: PyLoop) -> None:
        libev.ev_timer_stop(loop=loop.loop, timer=self.timer_watcher)

    def again(self, loop: PyLoop) -> None:
        libev.ev_timer_again(loop=loop.loop, timer=self.timer_watcher)

    def remaining(self, loop: PyLoop) -> float:
        return float(libev.ev_timer_remaining(loop=loop.loop, timer=self.timer_watcher))
    
    @staticmethod
    cdef default_callback(libev.ev_loop *ev_loop, libev.ev_timer *timer_watcher, int revents):
        callbacks_dict: dict[str, Callable[..., Any]] = <dict>timer_watcher.data
        callbacks_dict["default"](
            PyLoop._new_(loop=ev_loop),
            PyTimerWatcher._new_(timer_watcher=timer_watcher, callbacks=callbacks_dict),
            revents
        )


cdef class PyStatWatcher:
    cdef libev.ev_stat *stat_watcher
    cdef bint _owns_watcher
    _callbacks: dict[str, Callable[..., Any]]

    @property
    def callbacks(self) -> dict[str, Callable[..., Any]]:
        return self._callbacks

    @callbacks.setter
    def callbacks(self, callbacks: dict[str, Callable[..., Any]]) -> None:
        self._callbacks = callbacks

    @staticmethod
    cdef PyStatWatcher _new_(libev.ev_stat *stat_watcher = NULL, callbacks: Optional[dict[str, Callable[..., Any]]] = None):
        cdef PyStatWatcher py_stat_watcher = PyStatWatcher()
        if stat_watcher == NULL:
            stat_watcher = <libev.ev_stat *>malloc(size=<size_t>sizeof(libev.ev_stat))
            py_stat_watcher._owns_watcher = True
        else:
            py_stat_watcher._owns_watcher = False
        py_stat_watcher.stat_watcher = stat_watcher
        if callbacks is not None:
            py_stat_watcher.callbacks = callbacks
        return py_stat_watcher

    def __dealloc__(self):
        if self._owns_watcher and self.stat_watcher != NULL:
            free(self.stat_watcher)
            self.stat_watcher = NULL

    @staticmethod
    def _new_from_python_() -> PyStatWatcher:
        return PyStatWatcher._new_()

    def init(self, callbacks: dict[str, Callable[..., Any]], path: str, interval: float) -> None:
        self.callbacks = callbacks
        self.stat_watcher.data = <void *>self.callbacks
        libev.ev_stat_init(
            watcher=self.stat_watcher,
            callback=<libev.stat_cb>PyStatWatcher.default_callback,
            path=get_char_from_py_string(string=path),
            interval=<libev.ev_tstamp>interval,
        )

    def start(self, loop: PyLoop) -> None:
        libev.ev_stat_start(loop=loop.loop, watcher=self.stat_watcher)

    def stop(self, loop: PyLoop) -> None:
        libev.ev_stat_stop(loop=loop.loop, watcher=self.stat_watcher)

    @staticmethod
    cdef default_callback(libev.ev_loop *ev_loop, libev.ev_stat *stat_watcher, int revents):
        callbacks_dict: dict[str, Callable[..., Any]] = <dict>stat_watcher.data
        callbacks_dict["default"](
            PyLoop._new_(loop=ev_loop),
            PyStatWatcher._new_(stat_watcher=stat_watcher, callbacks=callbacks_dict),
            revents
        )


# Enums

class CONSTANTS(pyenum.IntEnum):
    CurrentTime = xlib.CurrentTime
    AnyPropertyType = xlib.AnyPropertyType
    NoSymbol = xlib.NoSymbol
    AnyKey = xlib.AnyKey
    XkbUseCoreKbd = xlib.XkbUseCoreKbd

class EVENT_TYPES(pyenum.IntEnum):
    # Generic event
    GenericEvent = xlib.GenericEvent
    # XErrorEvent
    ErrorEvent = 0
    # XKeyEvent
    KeyPress = xlib.KeyPress
    KeyRelease = xlib.KeyRelease
    # XButtonEvent
    ButtonPress = xlib.ButtonPress
    ButtonRelease = xlib.ButtonRelease
    # XMotionEvent
    MotionNotify = xlib.MotionNotify
    # XCrossingEvent
    EnterNotify = xlib.EnterNotify
    LeaveNotify = xlib.LeaveNotify
    # XFocusChangeEvent
    FocusIn = xlib.FocusIn
    FocusOut = xlib.FocusOut
    # XExposeEvent
    Expose = xlib.Expose
    # XGraphicsExposeEvent
    GraphicsExpose = xlib.GraphicsExpose
    # XNoExposeEvent
    NoExpose = xlib.NoExpose
    # XVisibilityEvent
    VisibilityNotify = xlib.VisibilityNotify
    # XCreateWindowEvent
    CreateNotify = xlib.CreateNotify
    # XDestroyWindowEvent
    DestroyNotify = xlib.DestroyNotify
    # XUnmapEvent
    UnmapNotify = xlib.UnmapNotify
    # XMapEvent
    MapNotify = xlib.MapNotify
    # XMapRequestEvent
    MapRequest = xlib.MapRequest
    # XReparentEvent
    ReparentNotify = xlib.ReparentNotify
    # XConfigureEvent
    ConfigureNotify = xlib.ConfigureNotify
    # XGravityEvent
    GravityNotify = xlib.GravityNotify
    # XResizeRequestEvent
    ResizeRequest = xlib.ResizeRequest
    # XConfigureRequestEvent
    ConfigureRequest = xlib.ConfigureRequest
    # XCirculateEvent
    CirculateNotify = xlib.CirculateNotify
    # XCirculateRequestEvent
    CirculateRequest = xlib.CirculateRequest
    # XPropertyEvent
    PropertyNotify = xlib.PropertyNotify
    # XSelectionClearEvent
    SelectionClear = xlib.SelectionClear
    # XSelectionRequestEvent
    SelectionRequest = xlib.SelectionRequest
    # XSelectionEvent
    SelectionNotify = xlib.SelectionNotify
    # XColormapEvent
    ColormapNotify = xlib.ColormapNotify
    # XClientMessageEvent
    ClientMessage = xlib.ClientMessage
    # XMappingEvent
    MappingNotify = xlib.MappingNotify
    # XKeymapEvent
    KeymapNotify = xlib.KeymapNotify

class INPUT_EVENT_MASKS(pyenum.IntEnum):
    NoEventMask = xlib.NoEventMask
    StructureNotifyMask = xlib.StructureNotifyMask
    SubstructureNotifyMask = xlib.SubstructureNotifyMask
    SubstructureRedirectMask = xlib.SubstructureRedirectMask
    PropertyChangeMask = xlib.PropertyChangeMask
    FocusChangeMask = xlib.FocusChangeMask
    KeyPressMask = xlib.KeyPressMask
    KeyReleaseMask = xlib.KeyReleaseMask

class KEY_MASKS(pyenum.IntEnum):
    AnyModifier = xlib.AnyModifier
    Mod1Mask = xlib.Mod1Mask
    ControlMask = xlib.ControlMask
    ShiftMask = xlib.ShiftMask
    Mod2Mask = xlib.Mod2Mask
    Mod4Mask = xlib.Mod4Mask
    LockMask = xlib.LockMask

class BUTTON_MASKS(pyenum.IntEnum):
    AnyModifier = xlib.AnyModifier
    Button1Mask = xlib.Button1Mask
    Button2Mask = xlib.Button2Mask
    Button3Mask = xlib.Button3Mask
    Button4Mask = xlib.Button4Mask
    Button5Mask = xlib.Button5Mask

class BUTTONS(pyenum.IntEnum):
    Button1 = xlib.Button1
    Button2 = xlib.Button2
    Button3 = xlib.Button3
    Button4 = xlib.Button4
    Button5 = xlib.Button5

class GRAB_MODE(pyenum.IntEnum):
    GrabModeSync = xlib.GrabModeSync
    GrabModeAsync = xlib.GrabModeAsync

class WINDOW_VALUE_MASK(pyenum.IntEnum):
    CWX = xlib.CWX
    CWY = xlib.CWY
    CWWidth = xlib.CWWidth
    CWHeight = xlib.CWHeight
    CWBorderWidth = xlib.CWBorderWidth
    CWSibling = xlib.CWSibling
    CWStackMode = xlib.CWStackMode

class WINDOW_STACKING_METHOD(pyenum.IntEnum):
    Above = xlib.Above
    Below = xlib.Below
    TopIf = xlib.TopIf
    BottomIf = xlib.BottomIf
    Opposite = xlib.Opposite

class SET_PROPERTY_MODE(pyenum.IntEnum):
    PropModeReplace = xlib.PropModeReplace
    PropModePrepend = xlib.PropModePrepend
    PropModeAppend = xlib.PropModeAppend

class WINDOW_MAP_STATE(pyenum.IntEnum):
    IsUnmapped = xlib.IsUnmapped
    IsUnviewable = xlib.IsUnviewable
    IsViewable = xlib.IsViewable

class SCREENSAVER_STATE(pyenum.IntEnum):
    ScreenSaverOff = xlib.ScreenSaverOff
    ScreenSaverOn = xlib.ScreenSaverOn
    ScreenSaverCycle = xlib.ScreenSaverCycle
    ScreenSaverDisabled = xlib.ScreenSaverDisabled

class SCREENSAVER_KIND(pyenum.IntEnum):
    ScreenSaverBlanked = xlib.ScreenSaverBlanked
    ScreenSaverInternal = xlib.ScreenSaverInternal
    ScreenSaverExternal = xlib.ScreenSaverExternal

class KB_GROUP_INDEX(pyenum.IntEnum):
    XkbGroup1Index = xlib.XkbGroup1Index
    XkbGroup2Index = xlib.XkbGroup2Index
    XkbGroup3Index = xlib.XkbGroup3Index
    XkbGroup4Index = xlib.XkbGroup4Index
    XkbAnyGroup = xlib.XkbAnyGroup
    XkbAllGroups = xlib.XkbAllGroups

class NOTIFY_MODES(pyenum.IntEnum):
    NotifyNormal = xlib.NotifyNormal
    NotifyGrab = xlib.NotifyGrab
    NotifyUngrab = xlib.NotifyUngrab
    NotifyWhileGrabbed = xlib.NotifyWhileGrabbed

class NOTIFY_DETAILS(pyenum.IntEnum):
    NotifyAncestor = xlib.NotifyAncestor
    NotifyVirtual = xlib.NotifyVirtual
    NotifyInferior = xlib.NotifyInferior
    NotifyNonlinear = xlib.NotifyNonlinear
    NotifyNonlinearVirtual = xlib.NotifyNonlinearVirtual
    NotifyPointer = xlib.NotifyPointer
    NotifyPointerRoot = xlib.NotifyPointerRoot
    NotifyDetailNone = xlib.NotifyDetailNone

class PROPERTY_NOTIFICATION(pyenum.IntEnum):
    PropertyNewValue = xlib.PropertyNewValue
    PropertyDelete = xlib.PropertyDelete

class PROPERTY_FORMAT(pyenum.Enum):
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
    def new_from_value(cls, value: Union[str, int]) -> "PROPERTY_FORMAT":
        for member in cls:
            if value in member.value:
                return member
        raise ValueError(f"The value {value} is not in the enum members")

class DPMS_POWER_LEVEL(pyenum.IntEnum):
    DPMSModeOn = xlib.DPMSModeOn
    DPMSModeStandby = xlib.DPMSModeStandby
    DPMSModeSuspend = xlib.DPMSModeSuspend
    DPMSModeOff = xlib.DPMSModeOff

class PYLOOP_NEW_LOOP_FLAGS(pyenum.IntEnum):
    EVFLAG_AUTO = libev.EVFLAG_AUTO
    EVFLAG_NOENV = libev.EVFLAG_NOENV
    EVFLAG_FORKCHECK = libev.EVFLAG_FORKCHECK
    EVFLAG_NOINOTIFY = libev.EVFLAG_NOINOTIFY
    EVFLAG_SIGNALFD = libev.EVFLAG_SIGNALFD
    EVFLAG_NOSIGMASK = libev.EVFLAG_NOSIGMASK
    EVBACKEND_SELECT = libev.EVBACKEND_SELECT
    EVBACKEND_POLL = libev.EVBACKEND_POLL
    EVBACKEND_EPOLL = libev.EVBACKEND_EPOLL
    EVBACKEND_KQUEUE = libev.EVBACKEND_KQUEUE
    EVBACKEND_DEVPOLL = libev.EVBACKEND_DEVPOLL
    EVBACKEND_PORT = libev.EVBACKEND_PORT
    EVBACKEND_ALL = libev.EVBACKEND_ALL
    EVBACKEND_MASK = libev.EVBACKEND_MASK

class PYLOOP_RUN_LOOP_FLAGS(pyenum.IntEnum):
    EVRUN_ALWAYS = 0  # Keep handling events until either no event watchers are active anymore or "ev_break" was called
    EVRUN_ONCE = libev.EVRUN_ONCE
    EVRUN_NOWAIT = libev.EVRUN_NOWAIT

class PYLOOP_BREAK_LOOP_FLAGS(pyenum.IntEnum):
    EVBREAK_ALL = libev.EVBREAK_ALL
    EVBREAK_ONE = libev.EVBREAK_ONE
    EVBREAK_CANCEL = libev.EVBREAK_CANCEL

class PYIOWATCHER_INIT_FLAGS(pyenum.IntEnum):
    EV_READ = libev.EV_READ
    EV_WRITE = libev.EV_WRITE
    EV_READ_WRITE = libev.EV_READ | libev.EV_WRITE


# Functions

def PyXOpenDisplay(display_name: Optional[str]) -> Optional[PyDisplay]:
    cdef xlib.Display *display
    cdef char *display_name_c = NULL
    if display_name is not None:
        display_name_c = get_char_from_py_string(string=display_name)
    display = xlib.XOpenDisplay(display_name=display_name_c)
    if display == NULL:
        return None
    return PyDisplay._new_(display=display)

def PyXCloseDisplay(display: PyDisplay) -> None:
    if display._display == NULL:
        return
    xlib.XCloseDisplay(display=display._display)

def PyXDefaultRootWindow(display: PyDisplay) -> int:
    return xlib.XDefaultRootWindow(display=display._display)

def PyXConnectionNumber(display: PyDisplay) -> int:
    return xlib.XConnectionNumber(display=display._display)

def PyXGrabKey(
    display: PyDisplay,
    keycode: int,
    modifiers: int,
    window: int,
    owner_events: bool,
    pointer_mode: int,
    keyboard_mode: int,
) -> int:
    return xlib.XGrabKey(
        display=display._display,
        keycode=keycode,
        modifiers=modifiers,
        grab_window=window,
        owner_events=<int>owner_events,
        pointer_mode=pointer_mode,
        keyboard_mode=keyboard_mode,
    )

def PyXUngrabKey(display: PyDisplay, keycode: int, modifiers: int, window: int) -> int:
    return xlib.XUngrabKey(display=display._display, keycode=keycode, modifiers=modifiers, window=window)

def PyXSelectInput(display: PyDisplay, window: int, event_mask: int) -> int:
    return xlib.XSelectInput(display=display._display, window=window, event_mask=event_mask)

def PyXConfigureWindow(display: PyDisplay, window: int, value_mask: int, window_changes: PyXWindowChanges) -> int:
    return xlib.XConfigureWindow(
        display=display._display, window=window, value_mask=value_mask, values=&window_changes._xwindowchanges
    )

def PyXSync(display: PyDisplay, discard: bool) -> int:
    return xlib.XSync(display=display._display, discard=<int>discard)

# Global reference to python callback
_pydefault_x_error_handler: Callable[[PyDisplay, PyXErrorEvent], None] = lambda __display__, __event__: None

cdef int default_x_error_handler(xlib.Display *display, xlib.XErrorEvent *error_event):
    _pydefault_x_error_handler(
        PyDisplay._new_(display=display), PyXErrorEvent._new_(error_event=error_event)
    )
    return 0

def PyXSetErrorHandler(
    handler: Callable[[PyDisplay, PyXErrorEvent], None]
) -> Callable[[PyDisplay, PyXErrorEvent], None]:
    global _pydefault_x_error_handler
    _pydefault_x_error_handler = handler

    xlib.XSetErrorHandler(handler=<xlib.XErrorHandler>default_x_error_handler)
    return handler

def PyXInternAtom(display: PyDisplay, atom_name: str, only_if_exists: bool) -> int:
    key: tuple[int, str, bool] = (<uintptr_t>display._display, atom_name, only_if_exists)
    cached: Optional[int] = _intern_cache.get(key)
    if cached is not None:
        return cached
    cdef xlib.Atom atom = xlib.XInternAtom(
        display=display._display, atom_name=get_char_from_py_string(string=atom_name), only_if_exists=<int>only_if_exists
    )
    if atom != 0 or not only_if_exists:
        _intern_cache[key] = atom
    return atom

def PyXGetWindowProperty(
    display: PyDisplay, window: int, property_: str
) -> Optional[tuple[pyarray.array[int], int, str]]:
    cdef long offset = <long>0
    cdef long length = <long>1024
    cdef int delete = <int>False
    cdef xlib.Atom actual_type_return
    cdef int actual_format_return
    cdef unsigned long nitems_return
    cdef unsigned long bytes_after_return
    cdef unsigned char *prop_return
    cdef xlib.Atom property_atom = PyXInternAtom(display=display, atom_name=property_, only_if_exists=False)
    cdef Py_ssize_t filled = 0
    cdef Py_ssize_t nitems
    cdef Py_ssize_t itemsize
    result_buf: Optional[carray.array] = None
    pyformat: Optional[PROPERTY_FORMAT] = None

    while True:
        xlib.XGetWindowProperty(
            display=display._display,
            window=window,
            property=property_atom,
            offset=offset,
            length=length,
            delete=delete,
            req_type=xlib.AnyPropertyType,
            actual_type_return=&actual_type_return,
            actual_format_return=&actual_format_return,
            nitems_return=&nitems_return,
            bytes_after_return=&bytes_after_return,
            prop_return=&prop_return
        )
        if not nitems_return:
            return None
        try:
            pyformat = PROPERTY_FORMAT.new_from_value(value=actual_format_return)
            if result_buf is None:
                result_buf = pyarray.array(pyformat.value[1])
            nitems = <Py_ssize_t>nitems_return
            itemsize = result_buf.itemsize
            filled += nitems
            carray.resize(result_buf, filled)
            memcpy(
                <char *>result_buf.data.as_voidptr + (filled - nitems) * itemsize,
                <void *>prop_return,
                <size_t>(nitems * itemsize),
            )
            xlib.XFree(data=<void *>prop_return)
            prop_return = NULL
        except ValueError:
            if prop_return != NULL:
                xlib.XFree(data=<void *>prop_return)
            return None
        if bytes_after_return:
            offset += <long>((nitems_return * actual_format_return + 31) // 32)
            length = <long>ceil(x=<double>(bytes_after_return / 4.0))
            if length < 1:
                length = 1
        else:
            break
    return (result_buf, actual_type_return, "")

def PyXChangeProperty(
    display: PyDisplay,
    window: int,
    property_name: str,
    atom_type: int,
    format_: int,
    mode: int,
    property_data: pyarray.array[int],
) -> int:
    pyformat = PROPERTY_FORMAT.new_from_value(value=format_)
    cdef carray.array data_ = carray.array(pyformat.value[1], property_data)
    return xlib.XChangeProperty(
        display=display._display,
        window=window,
        property=PyXInternAtom(display=display, atom_name=property_name, only_if_exists=False),
        type=atom_type,
        format=format_,
        mode=mode,
        data=<unsigned char *>data_.data.as_voidptr,
        nelements=len(data_)
    )

def PyXGetWindowAttributes(display: PyDisplay, window: int) -> Optional[PyXWindowAttributes]:
    cdef xlib.XWindowAttributes window_attributes
    cdef int result = xlib.XGetWindowAttributes(
        display=display._display, window=window, window_attributes_return=&window_attributes
    )
    if not result:
        return None
    return PyXWindowAttributes._new_(window_attributes=window_attributes)

def PyXQueryTree(display: PyDisplay, window: int) -> Optional[PyXWindowTree]:
    cdef xlib.Window root_return
    cdef xlib.Window parent_return
    cdef xlib.Window *children_return
    cdef unsigned int nchildren_return

    cdef int result = xlib.XQueryTree(
        display=display._display,
        window=window,
        root_return=&root_return,
        parent_return=&parent_return,
        children_return=&children_return,
        nchildren_return=&nchildren_return
    )
    if not result:
        return None
    children: list[int] = []
    for i in range(nchildren_return):
        children.append(children_return[i])
    xlib.XFree(data=<void *>children_return)
    return PyXWindowTree._new_(
        window=window, root=root_return, parent=parent_return, children=children
    )

def PyXGetGeometry(display: PyDisplay, window: int) -> Optional[PyXWindowGeometry]:
    cdef xlib.Window root_return
    cdef int x_return, y_return
    cdef unsigned int width_return, height_return
    cdef unsigned int border_width_return
    cdef unsigned int depth_return

    cdef int result = xlib.XGetGeometry(
        display=display._display,
        window=window,
        root_return=&root_return,
        x_return=&x_return, y_return=&y_return,
        width_return=&width_return, height_return=&height_return,
        border_width_return=&border_width_return,
        depth_return=&depth_return
    )
    if not result:
        return None
    return PyXWindowGeometry._new_(
        window=window,
        root=root_return,
        x=x_return, y=y_return,
        width=width_return, height=height_return,
        border_width=border_width_return,
        depth=depth_return
    )

def PyXScreenSaverQueryInfo(display: PyDisplay, window: int) -> Optional[PyXScreenSaverInfo]:
    cdef xlib.XScreenSaverInfo info
    cdef int result = xlib.XScreenSaverQueryInfo(
        display=display._display, drawable=window, saver_info=&info
    )
    if not result:
        return None
    return PyXScreenSaverInfo._new_(info=info)

def PyXkbGetState(display: PyDisplay, device_spec: int) -> PyXkbStateRec:
    cdef xlib.XkbStateRec state
    xlib.XkbGetState(
        display=display._display, device_spec=device_spec, state_return=&state
    )
    return PyXkbStateRec._new_(kb_state=state)

def PyXkbLockGroup(display: PyDisplay, device_spec: int, group: int) -> int:
    return xlib.XkbLockGroup(display=display._display, device_spec=device_spec, group=group)

def PyXFlush(display: PyDisplay) -> int:
    return xlib.XFlush(display=display._display)

def PyXGetAtomName(display: PyDisplay, atom: int) -> str:
    key: tuple[int, int] = (<uintptr_t>display._display, atom)
    cached: Optional[str] = _atom_name_cache.get(key)
    if cached is not None:
        return cached
    cdef char *name = xlib.XGetAtomName(display=display._display, atom=atom)
    if name == NULL:
        return ""
    cdef bytes pybytes = <bytes>name
    cdef str result = pybytes.decode().strip()
    xlib.XFree(data=<void *>name)
    _atom_name_cache[key] = result
    return result

def PyXSendEvent(
    display: PyDisplay, window: int, propagate: bool, event_mask: int, xevent: PyXEvent
) -> int:
    return xlib.XSendEvent(
        display=display._display,
        window=window,
        propagate=<int>propagate,
        event_mask=<long>event_mask,
        event_send=&xevent._native_event,
    )

cdef cairo.cairo_status_t writePngStream(void *closure, const unsigned char *data, unsigned int length):
    cdef IconData *png_buffer = <IconData *>closure
    png_buffer.data = <unsigned char *>realloc(ptr=<void *>png_buffer.data, newsize=<size_t>(sizeof(unsigned char) * (png_buffer.length + length)))
    memcpy(pto=<void *>&png_buffer.data[png_buffer.length], pfrom=<void *>data, size=<size_t>(sizeof(unsigned char) * length))
    png_buffer.length += length
    return cairo.cairo_status_t.CAIRO_STATUS_SUCCESS

cdef IconData readSvgIcon(str iconPath):
    cdef IconData iconData = IconData(length=0, data=NULL, magick_memory=False)  # type: ignore
    cdef resvg.resvg_options *options = resvg.resvg_options_create()
    cdef resvg.resvg_render_tree *tree = NULL
    cdef cairo.cairo_surface_t *surface = NULL
    cdef int result = resvg.resvg_parse_tree_from_file(
        file_path=get_char_from_py_string(string=iconPath), opt=options, tree=&tree
    )
    resvg.resvg_options_destroy(opt=options)
    if result != resvg.resvg_error.RESVG_OK:
        print(f"An error occurred reading the .svg file {iconPath}")
        return iconData

    cdef resvg.resvg_size size = resvg.resvg_get_image_size(tree=tree)
    surface = cairo.cairo_image_surface_create(
        format=cairo.cairo_format_t.CAIRO_FORMAT_ARGB32, width=<int>size.width, height=<int>size.height
    )
    cdef unsigned char *surface_data = cairo.cairo_image_surface_get_data(surface=surface)
    resvg.resvg_render(
        tree=tree,
        fit_to=resvg.resvg_fit_to(type=resvg.resvg_fit_to_type.RESVG_FIT_TO_TYPE_ORIGINAL, value=1.0),  # type: ignore
        transform=resvg.resvg_transform_identity(),
        width=<uint32_t>size.width,
        height=<uint32_t>size.height,
        pixmap=<char *>surface_data
    )

    # Transform RGBA to BGRA
    cdef unsigned char R
    cdef unsigned char B
    for i in range(0, <int>(size.width * size.height * 4), 4):
        R = surface_data[i]
        B = surface_data[i + 2]
        surface_data[i] = B
        surface_data[i + 2] = R

    if cairo.cairo_surface_write_to_png_stream(
        surface=surface, write_func=<cairo.cairo_write_func_t>writePngStream, closure=<void *>&iconData
    ) != cairo.cairo_status_t.CAIRO_STATUS_SUCCESS:
        release_icon_data(&iconData)

    resvg.resvg_tree_destroy(tree=tree)
    cairo.cairo_surface_destroy(surface=surface)
    return iconData

cdef IconData readIconWithImageMagick(str iconPath):
    cdef IconData iconData = IconData(length=0, data=NULL, magick_memory=False)  # type: ignore
    imagemagick.MagickWandGenesis()
    cdef imagemagick.MagickWand *wand = imagemagick.NewMagickWand()
    cdef imagemagick.PixelWand *pixelWand = imagemagick.NewPixelWand()
    imagemagick.PixelSetColor(
        wand=pixelWand, color=get_char_from_py_string(string="transparent")  # Color for the background
    )
    # The background has to be assigned before loading the file image to avoid white backgrounds
    imagemagick.MagickSetBackgroundColor(wand=wand, background=pixelWand)
    
    cdef int result = imagemagick.MagickPingImage(
        wand=wand, filename=get_char_from_py_string(string=iconPath)
    )
    if not result:
        print(f"An error occurred pinging the file {iconPath}")
        readIconWithImageMagickFinalizer(wand=wand, pixelWand=pixelWand)
        return iconData
    result = imagemagick.MagickReadImage(
        wand=wand, filename=get_char_from_py_string(string=iconPath)  # Read the file
    )
    if not result:
        print(f"An error occurred reading the file {iconPath}")
        readIconWithImageMagickFinalizer(wand=wand, pixelWand=pixelWand)
        return iconData
    result = imagemagick.MagickSetImageFormat(
        wand=wand, format=get_char_from_py_string(string="png")  # Convert the wand (image) to PNG format
    )
    if not result:
        print("An error occurred converting the file to png format")
        readIconWithImageMagickFinalizer(wand=wand, pixelWand=pixelWand)
        return iconData

    cdef size_t iconRawDataSize
    cdef unsigned char *iconRawData = imagemagick.MagickGetImageBlob(wand=wand, size=&iconRawDataSize)
    readIconWithImageMagickFinalizer(wand=wand, pixelWand=pixelWand)

    iconData.length = <int>iconRawDataSize
    iconData.data = iconRawData
    iconData.magick_memory = True
    return iconData

cdef readIconWithImageMagickFinalizer(imagemagick.MagickWand *wand, imagemagick.PixelWand *pixelWand):
    if wand != NULL:
        imagemagick.DestroyMagickWand(wand=wand)
    if pixelWand != NULL:
        imagemagick.DestroyPixelWand(wand=pixelWand)
    imagemagick.MagickWandTerminus()

def PySetWindowIcon(display: PyDisplay, window: int, filepath: Path) -> bool:
    cdef libgd.gdImagePtr imagePtr = NULL
    cdef IconData iconData = IconData(length=0, data=NULL, magick_memory=False)  # type: ignore
    icon_read: bool = False
    if filepath.suffix == ".svg":  # Read image with resvg if it has .svg extension or with MagickWand (ImageMagick) for all other extensions
        try:
            iconData = readSvgIcon(iconPath=str(filepath))
            if iconData.length:
                icon_read = True
        except:
            icon_read = False
    if not icon_read:
        try:
            iconData = readIconWithImageMagick(iconPath=str(filepath))
            if iconData.length:
                icon_read = True
        except:
            pass

    if not icon_read:
        return False
    if iconData.length and iconData.data != NULL:
        imagePtr = libgd.gdImageCreateFromPngPtr(size=iconData.length, data=<void *>iconData.data)
    release_icon_data(&iconData)
    if imagePtr == NULL:
        return False

    cdef int width = libgd.gdImageSX(im=imagePtr)
    cdef int height = libgd.gdImageSY(im=imagePtr)
    cdef unsigned int ndata = (width * height) + 2
    cdef libgd.CARD32 *_net_wm_icon_data = <libgd.CARD32 *>calloc(count=<size_t>ndata, eltsize=<size_t>sizeof(libgd.CARD32))
    if _net_wm_icon_data == NULL:
        libgd.gdImageDestroy(im=imagePtr)
        return False
    _net_wm_icon_data[0] = width
    _net_wm_icon_data[1] = height
    cdef unsigned char *cols = NULL
    cdef int pixcolour
    cdef int alpha
    cdef int index = 2  # Start at 2 cause 0 contains the width and 1 the height
    # Transform data from RGBA to BGRA
    for y in range(height):
        for x in range(width):
            cols = <unsigned char *>&_net_wm_icon_data[index]
            index += 1
            pixcolour = libgd.gdImageGetPixel(im=imagePtr, x=x, y=y)
            cols[0] = libgd.gdImageBlue(im=imagePtr, color=pixcolour)
            cols[1] = libgd.gdImageGreen(im=imagePtr, color=pixcolour)
            cols[2] = libgd.gdImageRed(im=imagePtr, color=pixcolour)

            # gd alpha: 0 opaque, 127 transparent -> scale to 0..255 for _NET_WM_ICON
            alpha = 127 - libgd.gdImageAlpha(im=imagePtr, color=pixcolour)
            cols[3] = <unsigned char>(255 if alpha >= 127 else (alpha * 255) // 127)
    libgd.gdImageDestroy(im=imagePtr)

    # Change icon using _NET_WM_ICON property, data is BGRA
    cdef xlib.Atom property_ = PyXInternAtom(display=display, atom_name="_NET_WM_ICON", only_if_exists=False)
    cdef xlib.Atom type_ = PyXInternAtom(display=display, atom_name="CARDINAL", only_if_exists=False)
    cdef int result = xlib.XChangeProperty(
        display=display._display,
        window=window,
        property=property_,
        type=type_,
        format=32,
        mode=xlib.PropModeReplace,
        data=<unsigned char*>_net_wm_icon_data,
        nelements=<int>ndata
    )
    if result:
        xlib.XFlush(display=display._display)
    free(_net_wm_icon_data)
    return True

def PyXStringToKeysym(string: str) -> int:
    return xlib.XStringToKeysym(string=get_char_from_py_string(string=string))

def PyXKeysymToKeycode(display: PyDisplay, keysym: int) -> int:
    return xlib.XKeysymToKeycode(display=display._display, keysym=keysym)

def PyXPending(display: PyDisplay) -> int:
    return xlib.XPending(display=display._display)

def PyXNextEvent(display: PyDisplay) -> PyXEvent:
    cdef xlib.XEvent event
    xlib.XNextEvent(display=display._display, event_return=&event)
    try:
        event_type: EVENT_TYPES = EVENT_TYPES(event.type)
        if event_type == EVENT_TYPES.ErrorEvent:
            return PyXErrorEvent._new_(error_event=&event.xerror)
        elif event_type == EVENT_TYPES.KeyPress or event_type == EVENT_TYPES.KeyRelease:
            return PyXKeyEvent._new_(key_event=&event.xkey)
        elif event_type == EVENT_TYPES.ButtonPress or event_type == EVENT_TYPES.ButtonRelease:
            return PyXButtonEvent._new_(button_event=&event.xbutton)
        elif event_type == EVENT_TYPES.FocusIn or event_type == EVENT_TYPES.FocusOut:
            return PyXFocusChangeEvent._new_(focus_change_event=&event.xfocus)
        elif event_type == EVENT_TYPES.CreateNotify:
            return PyXCreateWindowEvent._new_(create_window_event=&event.xcreatewindow)
        elif event_type == EVENT_TYPES.DestroyNotify:
            return PyXDestroyWindowEvent._new_(destroy_window_event=&event.xdestroywindow)
        elif event_type == EVENT_TYPES.PropertyNotify:
            return PyXPropertyEvent._new_(property_event=&event.xproperty)
        elif event_type == EVENT_TYPES.ClientMessage:
            return PyXClientMessageEvent._new_(client_message_event=&event.xclient)
        return PyXEvent._new_(event=&event)
    except ValueError:
        return PyXEvent._new_(event=&event)

def PyGetDPMSInfo(display: PyDisplay) -> PyDPMSInfo:
    cdef xlib.BOOL state
    cdef xlib.CARD16 power_level
    xlib.DPMSInfo(display=display._display, power_level=&power_level, state=&state)
    return PyDPMSInfo._new_(state=state, power_level=power_level)

def PyDPMSEnable(display: PyDisplay) -> bool:
    return bool(xlib.DPMSEnable(display=display._display))

def PyDPMSDisable(display: PyDisplay) -> bool:
    return bool(xlib.DPMSDisable(display=display._display))