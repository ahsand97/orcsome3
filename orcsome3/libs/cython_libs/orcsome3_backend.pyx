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
from libc.stdlib cimport calloc, malloc, realloc
from libc.string cimport memcpy
from pathlib import Path
from libc.stdint cimport uint32_t
from cython.operator cimport dereference


# Structs

ctypedef struct IconData:
    int length
    unsigned char *data


# Classes

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
    def type(self, type: EVENT_TYPES):
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
    
    def _get_specific_event_(self):
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
        # Get the error message using XGetErrorText
        cdef int length = 1024
        cdef char *buffer = <char *>malloc(size=<size_t>(sizeof(char) * length))
        xlib.XGetErrorText(display=self.display._display, code=<int>self.error_code, buffer_return=buffer, length=length)
        cdef bytes buffer_bytes = <bytes>buffer
        self.msg = buffer_bytes.decode()
        xlib.XFree(data=<void *>buffer)

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
        cdef xlib.XClientMessageEvent xClientMessageEvent = xlib.XClientMessageEvent(  # type: ignore
            type=type,
            serial=serial,
            send_event=<int>send_event,
            display=display._display,
            window=window,
            message_type=message_type,
            format=format,
        )
        cdef char[20] b
        cdef short[10] s
        cdef long[5] l
        pyformat: PROPERTY_FORMAT = PROPERTY_FORMAT.new_from_value(value=format)
        if pyformat == PROPERTY_FORMAT.CHAR:
            for i in range(20):
                b[i] = data[i]
        elif pyformat == PROPERTY_FORMAT.SHORT:
            for i in range(10):
                s[i] = data[i]
        elif pyformat == PROPERTY_FORMAT.LONG:
            for i in range(5):
                l[i] = data[i]
        xClientMessageEvent.b = b
        xClientMessageEvent.s = s
        xClientMessageEvent.l = l
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

    cpdef run(self, flags: Union[int, list[int]]):
        cdef int run_flags = PYLOOP_RUN_LOOP_FLAGS.EVRUN_ALWAYS.value
        if isinstance(flags, list):
            run_flags = flags[0]
            for flag in flags:
                run_flags |= flag
        else:
            run_flags = flags
        libev.ev_run(loop=self.loop, flags=run_flags)

    cpdef break_(self, int how_to_break_flag):
        libev.ev_break(loop=self.loop, how=how_to_break_flag)

    cpdef destroy(self):
        libev.ev_loop_destroy(loop=self.loop)

cdef class PyIOWatcher:
    cdef libev.ev_io *io_watcher
    _callbacks: dict[str, Callable[..., Any]]

    @property
    def callbacks(self) -> dict[str, Callable[..., Any]]:
        return self._callbacks

    @callbacks.setter
    def callbacks(self, callbacks: dict[str, Callable[..., Any]]) -> None:
        self._callbacks = callbacks

    @staticmethod
    cdef PyIOWatcher _new_(libev.ev_io *io_watcher = NULL, callbacks: Optional[dict[str, Callable[..., Any]]] = None):
        if io_watcher == NULL:
            io_watcher = <libev.ev_io *>malloc(size=<size_t>sizeof(libev.ev_io))
        cdef PyIOWatcher py_io_watcher = PyIOWatcher()
        py_io_watcher.io_watcher = io_watcher
        if callbacks is not None:
            py_io_watcher.callbacks = callbacks
        return py_io_watcher

    @staticmethod
    def _new_from_python_() -> PyIOWatcher:
        return PyIOWatcher._new_()

    cpdef init(self, callbacks: dict[str, Callable[..., Any]], int file_descriptor, int events):
        self.callbacks = callbacks
        self.io_watcher.data = <void *>self.callbacks
        libev.ev_io_init(
            ev_io=self.io_watcher, callback=<libev.io_cb>PyIOWatcher.default_callback, fd=file_descriptor, events=events
        )

    cpdef start(self, PyLoop loop):
        libev.ev_io_start(loop=loop.loop, watcher=self.io_watcher)

    cpdef stop(self, PyLoop loop):
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
    _callbacks: dict[str, Callable[..., Any]]

    @property
    def callbacks(self) -> dict[str, Callable[..., Any]]:
        return self._callbacks

    @callbacks.setter
    def callbacks(self, callbacks: dict[str, Callable[..., Any]]) -> None:
        self._callbacks = callbacks

    @staticmethod
    cdef PySignalWatcher _new_(libev.ev_signal *signal_watcher = NULL, callbacks: Optional[dict[str, Callable[..., Any]]] = None):
        if signal_watcher == NULL:
            signal_watcher = <libev.ev_signal *>malloc(size=<size_t>sizeof(libev.ev_signal))
        cdef PySignalWatcher py_signal_watcher = PySignalWatcher()
        py_signal_watcher.signal_watcher = signal_watcher
        if callbacks is not None:
            py_signal_watcher.callbacks = callbacks
        return py_signal_watcher

    @staticmethod
    def _new_from_python_() -> PySignalWatcher:
        return PySignalWatcher._new_()

    cpdef init(self, callbacks: dict[str, Callable[..., Any]], int signum):
        self.callbacks = callbacks
        self.signal_watcher.data = <void *>self.callbacks
        libev.ev_signal_init(
            signal=self.signal_watcher, callback=<libev.signal_cb>PySignalWatcher.default_callback, signum=signum
        )

    cpdef start(self, PyLoop loop):
        libev.ev_signal_start(loop=loop.loop, signal=self.signal_watcher)

    cpdef stop(self, PyLoop loop):
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
    _callbacks: dict[str, Callable[..., Any]]

    @property
    def callbacks(self) -> dict[str, Callable[..., Any]]:
        return self._callbacks

    @callbacks.setter
    def callbacks(self, callbacks: dict[str, Callable[..., Any]]) -> None:
        self._callbacks = callbacks

    @staticmethod
    cdef PyTimerWatcher _new_(libev.ev_timer *timer_watcher = NULL, callbacks: Optional[dict[str, Callable[..., Any]]] = None):
        if timer_watcher == NULL:
            timer_watcher = <libev.ev_timer *>malloc(size=<size_t>sizeof(libev.ev_timer))
        cdef PyTimerWatcher py_timer_watcher = PyTimerWatcher()
        py_timer_watcher.timer_watcher = timer_watcher
        if callbacks is not None:
            py_timer_watcher.callbacks = callbacks
        return py_timer_watcher

    @staticmethod
    def _new_from_python_() -> PyTimerWatcher:
        return PyTimerWatcher._new_()

    cpdef init(self, callbacks: dict[str, Callable[..., Any]], float after, float repeat):
        self.callbacks = callbacks
        self.timer_watcher.data = <void *>self.callbacks
        libev.ev_timer_init(
            timer=self.timer_watcher, callback=<libev.timer_cb>PyTimerWatcher.default_callback, after=<libev.ev_tstamp>after, repeat=<libev.ev_tstamp>repeat
        )

    cpdef set_timer(self, float after, float repeat):
        libev.ev_timer_set(timer=self.timer_watcher, after=<libev.ev_tstamp>after, repeat=<libev.ev_tstamp>repeat)

    cpdef start(self, PyLoop loop):
        libev.ev_timer_start(loop=loop.loop, timer=self.timer_watcher)

    cpdef stop(self, PyLoop loop):
        libev.ev_timer_stop(loop=loop.loop, timer=self.timer_watcher)

    cpdef again(self, PyLoop loop):
        libev.ev_timer_again(loop=loop.loop, timer=self.timer_watcher)

    cpdef float remaining(self, PyLoop loop):
        return float(libev.ev_timer_remaining(loop=loop.loop, timer=self.timer_watcher))
    
    @staticmethod
    cdef default_callback(libev.ev_loop *ev_loop, libev.ev_timer *timer_watcher, int revents):
        callbacks_dict: dict[str, Callable[..., Any]] = <dict>timer_watcher.data
        callbacks_dict["default"](
            PyLoop._new_(loop=ev_loop),
            PyTimerWatcher._new_(timer_watcher=timer_watcher, callbacks=callbacks_dict),
            revents
        )


# Enums

class CONSTANTS(pyenum.Enum):
    CurrentTime = xlib.CurrentTime
    AnyPropertyType = xlib.AnyPropertyType
    NoSymbol = xlib.NoSymbol
    AnyKey = xlib.AnyKey
    XkbUseCoreKbd = xlib.XkbUseCoreKbd

class EVENT_TYPES(pyenum.Enum):
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

class INPUT_EVENT_MASKS(pyenum.Enum):
    NoEventMask = xlib.NoEventMask
    StructureNotifyMask = xlib.StructureNotifyMask
    SubstructureNotifyMask = xlib.SubstructureNotifyMask
    SubstructureRedirectMask = xlib.SubstructureRedirectMask
    PropertyChangeMask = xlib.PropertyChangeMask
    FocusChangeMask = xlib.FocusChangeMask
    KeyPressMask = xlib.KeyPressMask
    KeyReleaseMask = xlib.KeyReleaseMask

class KEY_MASKS(pyenum.Enum):
    AnyModifier = xlib.AnyModifier
    Mod1Mask = xlib.Mod1Mask
    ControlMask = xlib.ControlMask
    ShiftMask = xlib.ShiftMask
    Mod2Mask = xlib.Mod2Mask
    Mod4Mask = xlib.Mod4Mask
    LockMask = xlib.LockMask

class BUTTON_MASKS(pyenum.Enum):
    AnyModifier = xlib.AnyModifier
    Button1Mask = xlib.Button1Mask
    Button2Mask = xlib.Button2Mask
    Button3Mask = xlib.Button3Mask
    Button4Mask = xlib.Button4Mask
    Button5Mask = xlib.Button5Mask

class BUTTONS(pyenum.Enum):
    Button1 = xlib.Button1
    Button2 = xlib.Button2
    Button3 = xlib.Button3
    Button4 = xlib.Button4
    Button5 = xlib.Button5

class GRAB_MODE(pyenum.Enum):
    GrabModeSync = xlib.GrabModeSync
    GrabModeAsync = xlib.GrabModeAsync

class WINDOW_VALUE_MASK(pyenum.Enum):
    CWX = xlib.CWX
    CWY = xlib.CWY
    CWWidth = xlib.CWWidth
    CWHeight = xlib.CWHeight
    CWBorderWidth = xlib.CWBorderWidth
    CWSibling = xlib.CWSibling
    CWStackMode = xlib.CWStackMode

class WINDOW_STACKING_METHOD(pyenum.Enum):
    Above = xlib.Above
    Below = xlib.Below
    TopIf = xlib.TopIf
    BottomIf = xlib.BottomIf
    Opposite = xlib.Opposite

class SET_PROPERTY_MODE(pyenum.Enum):
    PropModeReplace = xlib.PropModeReplace
    PropModePrepend = xlib.PropModePrepend
    PropModeAppend = xlib.PropModeAppend

class WINDOW_MAP_STATE(pyenum.Enum):
    IsUnmapped = xlib.IsUnmapped
    IsUnviewable = xlib.IsUnviewable
    IsViewable = xlib.IsViewable

class SCREENSAVER_STATE(pyenum.Enum):
    ScreenSaverOff = xlib.ScreenSaverOff
    ScreenSaverOn = xlib.ScreenSaverOn
    ScreenSaverCycle = xlib.ScreenSaverCycle
    ScreenSaverDisabled = xlib.ScreenSaverDisabled

class SCREENSAVER_KIND(pyenum.Enum):
    ScreenSaverBlanked = xlib.ScreenSaverBlanked
    ScreenSaverInternal = xlib.ScreenSaverInternal
    ScreenSaverExternal = xlib.ScreenSaverExternal

class KB_GROUP_INDEX(pyenum.Enum):
    XkbGroup1Index = xlib.XkbGroup1Index
    XkbGroup2Index = xlib.XkbGroup2Index
    XkbGroup3Index = xlib.XkbGroup3Index
    XkbGroup4Index = xlib.XkbGroup4Index
    XkbAnyGroup = xlib.XkbAnyGroup
    XkbAllGroups = xlib.XkbAllGroups

class NOTIFY_MODES(pyenum.Enum):
    NotifyNormal = xlib.NotifyNormal
    NotifyGrab = xlib.NotifyGrab
    NotifyUngrab = xlib.NotifyUngrab
    NotifyWhileGrabbed = xlib.NotifyWhileGrabbed

class NOTIFY_DETAILS(pyenum.Enum):
    NotifyAncestor = xlib.NotifyAncestor
    NotifyVirtual = xlib.NotifyVirtual
    NotifyInferior = xlib.NotifyInferior
    NotifyNonlinear = xlib.NotifyNonlinear
    NotifyNonlinearVirtual = xlib.NotifyNonlinearVirtual
    NotifyPointer = xlib.NotifyPointer
    NotifyPointerRoot = xlib.NotifyPointerRoot
    NotifyDetailNone = xlib.NotifyDetailNone

class PROPERTY_NOTIFICATION(pyenum.Enum):
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

class DPMS_POWER_LEVEL(pyenum.Enum):
    DPMSModeOn = xlib.DPMSModeOn
    DPMSModeStandby = xlib.DPMSModeStandby
    DPMSModeSuspend = xlib.DPMSModeSuspend
    DPMSModeOff = xlib.DPMSModeOff

class PYLOOP_NEW_LOOP_FLAGS(pyenum.Enum):
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

class PYLOOP_RUN_LOOP_FLAGS(pyenum.Enum):
    EVRUN_ALWAYS = 0  # Keep handling events until either no event watchers are active anymore or "ev_break" was called
    EVRUN_ONCE = libev.EVRUN_ONCE
    EVRUN_NOWAIT = libev.EVRUN_NOWAIT

class PYLOOP_BREAK_LOOP_FLAGS(pyenum.Enum):
    EVBREAK_ALL = libev.EVBREAK_ALL
    EVBREAK_ONE = libev.EVBREAK_ONE
    EVBREAK_CANCEL = libev.EVBREAK_CANCEL

class PYIOWATCHER_INIT_FLAGS(pyenum.Enum):
    EV_READ = libev.EV_READ
    EV_WRITE = libev.EV_WRITE
    EV_READ_WRITE = libev.EV_READ | libev.EV_WRITE


# Functions

cdef char *get_char_from_py_string(str string):
    """Auxiliar function to convert python string to C char *"""
    cdef bytes py_bytes = string.encode()
    cdef char *c_string = <char *>py_bytes
    return c_string

cpdef PyXOpenDisplay(py_display_name: Optional[str]):
    cdef xlib.Display *display
    cdef char *display_name = NULL
    if py_display_name is not None:
        display_name = get_char_from_py_string(string=py_display_name)
    display = xlib.XOpenDisplay(display_name=display_name)
    if display == NULL:
        return None
    return PyDisplay._new_(display=display)

cpdef PyXCloseDisplay(PyDisplay display):
    if display._display == NULL:
        return
    xlib.XCloseDisplay(display=display._display)

cpdef xlib.Window PyXDefaultRootWindow(PyDisplay display):
    return xlib.XDefaultRootWindow(display=display._display)

cpdef int PyXConnectionNumber(PyDisplay display):
    return xlib.XConnectionNumber(display=display._display)

cpdef int PyXGrabKey(
        PyDisplay display, int keycode, unsigned int modifiers,
        xlib.Window grab_window, owner_events: bool, int pointer_mode,
        int keyboard_mode
    ):
    return xlib.XGrabKey(
        display=display._display,
        keycode=keycode,
        modifiers=modifiers,
        grab_window=grab_window,
        owner_events=<int>owner_events,
        pointer_mode=pointer_mode,
        keyboard_mode=keyboard_mode
    )

cpdef int PyXUngrabKey(PyDisplay display, int keycode, unsigned int modifiers, xlib.Window window):
    return xlib.XUngrabKey(display=display._display, keycode=keycode, modifiers=modifiers, window=window)

cpdef int PyXSelectInput(PyDisplay display, xlib.Window window, long event_mask):
    return xlib.XSelectInput(display=display._display, window=window, event_mask=event_mask)

cpdef int PyXConfigureWindow(PyDisplay display, xlib.Window window, unsigned int value_mask, pyXWindowChanges: PyXWindowChanges):
    return xlib.XConfigureWindow(
        display=display._display, window=window, value_mask=value_mask, values=&pyXWindowChanges._xwindowchanges
    )

cpdef int PyXSync(PyDisplay display, discard: bool):
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
):
    global _pydefault_x_error_handler
    _pydefault_x_error_handler = handler

    xlib.XSetErrorHandler(handler=<xlib.XErrorHandler>default_x_error_handler)
    return handler

cpdef xlib.Atom PyXInternAtom(PyDisplay display, str atom_name, only_if_exists: bool):
    return xlib.XInternAtom(
        display=display._display, atom_name=get_char_from_py_string(string=atom_name), only_if_exists=<int>only_if_exists
    )

cpdef PyXGetWindowProperty(PyDisplay display, xlib.Window window, str property_):
    # Default values
    cdef long offset = <long>0  # Specifies the offset in the specified property where the data is to be retrieved.
    cdef long length = <long>1024  # Specifies the length in 32-bit multiples of the data to be retrieved.
    cdef int delete = <int>False  # Specifies a boolean value that determines whether the property is going to be deleted.

    # Params to C function XGetWindowProperty
    cdef xlib.Atom actual_type_return
    cdef int actual_format_return
    cdef unsigned long nitems_return
    cdef unsigned long bytes_after_return
    cdef unsigned char *prop_return

    buffer_list: list[int] = []  # list containing the final result
    pyformat: Optional[PROPERTY_FORMAT] = None  # format of the result

    # Pointers to cast the final result to the correct type
    cdef char *result_as_char
    cdef short *result_as_short
    cdef long *result_as_long

    while True:
        xlib.XGetWindowProperty(
            display=display._display,
            window=window,
            property=PyXInternAtom(display=display, atom_name=property_, only_if_exists=False),
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
            # If the returned format is 8, the returned data is represented as a char array.
    
            # If the returned format is 16, the returned data is represented as a short array and
            # should be cast to that type to obtain the elements.
            
            # If the returned format is 32, the returned data is represented as a long array and
            # should be cast to that type to obtain the elements.
            pyformat = PROPERTY_FORMAT.new_from_value(value=actual_format_return)
            if pyformat == PROPERTY_FORMAT.CHAR:
                result_as_char = <char *>prop_return
                for i in range(nitems_return):
                    buffer_list.append(result_as_char[i])
                xlib.XFree(data=<void *>result_as_char)
            elif pyformat == PROPERTY_FORMAT.SHORT:
                result_as_short = <short *>prop_return
                for i in range(nitems_return):
                    buffer_list.append(result_as_short[i])
                xlib.XFree(data=<void *>result_as_short)
            elif pyformat == PROPERTY_FORMAT.LONG:
                result_as_long = <long *>prop_return
                for i in range(nitems_return):
                    buffer_list.append(result_as_long[i])
                xlib.XFree(data=<void *>result_as_long)
        except ValueError:
            return None
        if bytes_after_return:
            xlib.XFree(data=<void *>prop_return)
            offset = length
            length = <long>ceil(x=<double>(bytes_after_return / 4 + 1))
        else:
            break
    return (
        pyarray.array(cast(PROPERTY_FORMAT, pyformat).value[1], buffer_list),
        actual_type_return,
        PyXGetAtomName(display=display, atom=actual_type_return).strip()
    )

cpdef int PyXChangeProperty(
    PyDisplay display,
    xlib.Window window,
    str property_,
    xlib.Atom type_,
    int format_,
    int mode,
    data: pyarray.array[int],
):
    cdef carray.array data_ = carray.array("B", data.tobytes())  # Array of unsigned char
    return xlib.XChangeProperty(
        display=display._display,
        window=window,
        property=PyXInternAtom(display=display, atom_name=property_, only_if_exists=False),
        type=type_,
        format=format_,
        mode=mode,
        data=data_.data.as_uchars,
        nelements=len(data_)
    )

cpdef PyXGetWindowAttributes(PyDisplay display, xlib.Window window):
    cdef xlib.XWindowAttributes window_attributes
    cdef int result = xlib.XGetWindowAttributes(
        display=display._display, window=window, window_attributes_return=&window_attributes
    )
    if not result:
        return None
    return PyXWindowAttributes._new_(window_attributes=window_attributes)

cpdef PyXQueryTree(PyDisplay display, xlib.Window window):
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

cpdef PyXGetGeometry(PyDisplay display, xlib.Window window):
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

cpdef PyXScreenSaverQueryInfo(PyDisplay display, xlib.Window window):
    cdef xlib.XScreenSaverInfo info
    cdef int result = xlib.XScreenSaverQueryInfo(
        display=display._display, drawable=window, saver_info=&info
    )
    if not result:
        return None
    return PyXScreenSaverInfo._new_(info=info)

cpdef PyXkbStateRec PyXkbGetState(PyDisplay display, int device_spec):
    cdef xlib.XkbStateRec state
    xlib.XkbGetState(
        display=display._display, device_spec=device_spec, state_return=&state
    )
    return PyXkbStateRec._new_(kb_state=state)

cpdef int PyXkbLockGroup(PyDisplay display, int device_spec, int group):
    return xlib.XkbLockGroup(display=display._display, device_spec=device_spec, group=group)

cpdef int PyXFlush(PyDisplay display):
    return xlib.XFlush(display=display._display)

cpdef str PyXGetAtomName(PyDisplay display, xlib.Atom atom):
    cdef char *name = xlib.XGetAtomName(display=display._display, atom=atom)
    cdef bytes pybytes = <bytes>name
    cdef str result = pybytes.decode().strip()
    xlib.XFree(data=<void *>name)
    return result

cpdef int PyXSendEvent(
    PyDisplay display, xlib.Window window, propagate: bool, int event_mask, PyXEvent event
):
    return xlib.XSendEvent(
        display=display._display,
        window=window,
        propagate=<int>propagate,
        event_mask=<long>event_mask,
        event_send=&event._native_event
    )

cdef cairo.cairo_status_t writePngStream(void *closure, const unsigned char *data, unsigned int length):
    cdef IconData *png_buffer = <IconData *>closure
    png_buffer.data = <unsigned char *>realloc(ptr=<void *>png_buffer.data, newsize=<size_t>(sizeof(unsigned char) * (png_buffer.length + length)))
    memcpy(pto=<void *>&png_buffer.data[png_buffer.length], pfrom=<void *>data, size=<size_t>(sizeof(unsigned char) * length))
    png_buffer.length += length
    return cairo.cairo_status_t.CAIRO_STATUS_SUCCESS

cdef IconData readSvgIcon(str iconPath):
    cdef IconData iconData = IconData(length=0, data=NULL)  # type: ignore
    cdef resvg.resvg_options *options = resvg.resvg_options_create()
    cdef resvg.resvg_render_tree *tree
    cdef int result = resvg.resvg_parse_tree_from_file(file_path=get_char_from_py_string(string=iconPath), opt=options, tree=&tree)
    resvg.resvg_options_destroy(opt=options)
    if result != resvg.resvg_error.RESVG_OK:
        print(f"An error occurred reading the .svg file {iconPath}")
        return iconData
    
    cdef resvg.resvg_size size = resvg.resvg_get_image_size(tree=tree)
    cdef cairo.cairo_surface_t *surface = cairo.cairo_image_surface_create(
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
        iconData.length = 0
        iconData.data = NULL

    return iconData

cdef IconData readIconWithImageMagick(str iconPath):
    cdef IconData iconData = IconData(length=0, data=NULL)  # type: ignore
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

    iconData.length=<int>iconRawDataSize
    iconData.data=iconRawData
    return iconData

cdef readIconWithImageMagickFinalizer(imagemagick.MagickWand *wand, imagemagick.PixelWand *pixelWand):
    if wand != NULL:
        imagemagick.DestroyMagickWand(wand=wand)
    if pixelWand != NULL:
        imagemagick.DestroyPixelWand(wand=pixelWand)
    imagemagick.MagickWandTerminus()

cpdef bint PySetWindowIcon(PyDisplay display, xlib.Window window, filepath: Path) except False:
    cdef libgd.gdImagePtr imagePtr = NULL
    cdef IconData iconData
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
        return <bint>False
    if iconData.length and iconData.data != NULL:
        imagePtr = libgd.gdImageCreateFromPngPtr(size=iconData.length, data=<void *>iconData.data) # Creates imagePtr from png data
    if imagePtr == NULL:
        return <bint>False

    cdef int width = libgd.gdImageSX(im=imagePtr)
    cdef int height = libgd.gdImageSY(im=imagePtr)
    cdef unsigned int ndata = (width * height) + 2
    cdef libgd.CARD32 *_net_wm_icon_data = <libgd.CARD32 *>calloc(count=<size_t>ndata, eltsize=<size_t>sizeof(libgd.CARD32))
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

            # Alpha is more difficult
            alpha = 127 - libgd.gdImageAlpha(im=imagePtr, color=pixcolour) # 0 to 127
            # Scale it up to 0 to 255; remembering that 2*127 should be max
            if alpha == 127:
                alpha *= 2
            cols[3] = 255 if alpha == 127 else alpha
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
    xlib.XFree(data=<void *>_net_wm_icon_data)
    return <bint>True

cpdef xlib.KeySym PyXStringToKeysym(str string):
    return xlib.XStringToKeysym(string=get_char_from_py_string(string=string))

cpdef xlib.KeyCode PyXKeysymToKeycode(PyDisplay display, xlib.KeySym keysym):
    return xlib.XKeysymToKeycode(display=display._display, keysym=keysym)

cpdef int PyXPending(PyDisplay display):
    return xlib.XPending(display=display._display)

cpdef PyXNextEvent(PyDisplay display):
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

cpdef PyDPMSInfo PyGetDPMSInfo(PyDisplay display):
    cdef xlib.BOOL state
    cdef xlib.CARD16 power_level
    xlib.DPMSInfo(display=display._display, power_level=&power_level, state=&state)
    return PyDPMSInfo._new_(state=state, power_level=power_level)

cpdef bint PyDPMSEnable(PyDisplay display):
    return <bint>xlib.DPMSEnable(display=display._display)

cpdef bint PyDPMSDisable(PyDisplay display):
    return <bint>xlib.DPMSDisable(display=display._display)