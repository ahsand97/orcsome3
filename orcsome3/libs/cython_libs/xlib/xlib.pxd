# External libraries

cdef extern from "<X11/Xlib.h>": # pkg-config: x11
    # This library includes automatically:
    # - <X11/X.h>

    # Constants
    long CurrentTime
    long AnyPropertyType
    long NoSymbol # special keysym
    long AnyKey # special keycode

    # Input Event Masks
    long NoEventMask
    long StructureNotifyMask
    long SubstructureNotifyMask
    long SubstructureRedirectMask
    long PropertyChangeMask
    long FocusChangeMask
    long KeyPressMask
    long KeyReleaseMask
    long ButtonPressMask
    long ButtonReleaseMask

    # GrabPointer, GrabButton, GrabKeyboard, GrabKey Modes
    int GrabModeSync
    int GrabModeAsync

    # Key Masks
    int AnyModifier
    int Mod1Mask
    int ControlMask
    int ShiftMask
    int Mod2Mask
    int Mod4Mask
    int LockMask

    # Button Masks
    int Button1Mask
    int Button2Mask
    int Button3Mask
    int Button4Mask
    int Button5Mask

    # Button names
    int AnyButton
    int Button1
    int Button2
    int Button3
    int Button4
    int Button5

    # ConfigureWindow Window value mask bits
    int CWX
    int CWY
    int CWWidth
    int CWHeight
    int CWBorderWidth
    int CWSibling
    int CWStackMode

    # Window stacking method (in configureWindow)
    int Above
    int Below
    int TopIf
    int BottomIf
    int Opposite

    # Property modes
    int PropModeReplace
    int PropModePrepend
    int PropModeAppend

    # Map State Used in GetWindowAttributes reply
    int IsUnmapped
    int IsUnviewable
    int IsViewable

    # CreateWindow
    int InputOutput
    int InputOnly
    long CopyFromParent
    unsigned long CWOverrideRedirect

    # SetInputFocus / GetInputFocus
    int RevertToNone
    int RevertToPointerRoot
    int RevertToParent

    # Event names. Used in "type" field in XEvent structures
    int KeyPress
    int KeyRelease
    int ButtonPress
    int ButtonRelease
    int MotionNotify
    int EnterNotify
    int LeaveNotify
    int FocusIn
    int FocusOut
    int Expose
    int GraphicsExpose
    int NoExpose
    int VisibilityNotify
    int CreateNotify
    int DestroyNotify
    int UnmapNotify
    int MapNotify
    int MapRequest
    int ReparentNotify
    int ConfigureNotify
    int GravityNotify
    int ResizeRequest
    int ConfigureRequest
    int CirculateNotify
    int CirculateRequest
    int PropertyNotify
    int SelectionClear
    int SelectionRequest
    int SelectionNotify
    int ColormapNotify
    int ClientMessage
    int MappingNotify
    int KeymapNotify
    int GenericEvent

    # Notify Modes
    int NotifyNormal
    int NotifyGrab
    int NotifyUngrab
    int NotifyWhileGrabbed

    # Notify Details
    int NotifyAncestor
    int NotifyVirtual
    int NotifyInferior
    int NotifyNonlinear
    int NotifyNonlinearVirtual
    int NotifyPointer
    int NotifyPointerRoot
    int NotifyDetailNone

    # Property notification
    int PropertyNewValue
    int PropertyDelete

    # Defined types
    ctypedef struct Display:
        pass
    ctypedef unsigned long Time
    ctypedef unsigned long XID
    ctypedef XID Window
    ctypedef XID Cursor
    ctypedef XID Drawable
    ctypedef XID Pixmap
    ctypedef XID Colormap
    ctypedef struct Visual:
        pass
    ctypedef struct XSetWindowAttributes:
        Pixmap background_pixmap
        unsigned long background_pixel
        Pixmap border_pixmap
        unsigned long border_pixel
        int bit_gravity
        int win_gravity
        int backing_store
        unsigned long backing_planes
        unsigned long backing_pixel
        int save_under
        long event_mask
        long do_not_propagate_mask
        int override_redirect
        Colormap colormap
        Cursor cursor
    ctypedef XID KeySym
    ctypedef unsigned char KeyCode
    ctypedef unsigned long Atom
    ctypedef struct XWindowChanges:
        int x, y
        int width, height
        int border_width
        Window sibling
        int stack_mode
    ctypedef struct XAnyEvent:
        int type
        unsigned long serial
        int send_event
        Display *display
        Window window
    ctypedef struct XKeyEvent:
        int type
        unsigned long serial
        int send_event
        Display *display
        Window window
        Window root
        Window subwindow
        Time time
        int x, y
        int x_root, y_root
        unsigned int state
        unsigned int keycode
        int same_screen
    ctypedef struct XButtonEvent:
        int type
        unsigned long serial
        int send_event
        Display *display
        Window window
        Window root
        Window subwindow
        Time time
        int x, y
        int x_root, y_root
        unsigned int state
        unsigned int button
        int same_screen
    ctypedef struct XFocusChangeEvent:
        int type
        unsigned long serial
        int send_event
        Display *display
        Window window
        int mode
        int detail
    ctypedef struct XCreateWindowEvent:
        int type
        unsigned long serial
        int send_event
        Display *display
        Window parent
        Window window
        int x, y
        int width, height
        int border_width
        int override_redirect
    ctypedef struct XDestroyWindowEvent:
        int type
        unsigned long serial
        int send_event
        Display *display
        Window event
        Window window
    ctypedef struct XMapEvent:
        int type
        unsigned long serial
        int send_event
        Display *display
        Window event
        Window window
        int override_redirect
    ctypedef struct XUnmapEvent:
        int type
        unsigned long serial
        int send_event
        Display *display
        Window event
        Window window
        int from_configure
    ctypedef struct XConfigureEvent:
        int type
        unsigned long serial
        int send_event
        Display *display
        Window event
        Window window
        int x, y
        int width, height
        int border_width
        Window above
        int override_redirect
    ctypedef struct XPropertyEvent:
        int type
        unsigned long serial
        int send_event
        Display *display
        Window window
        Atom atom
        Time time
        int state
    ctypedef struct XClientMessageEvent:
        int type
        unsigned long serial
        int send_event
        Display *display
        Window window
        Atom message_type
        int format
        char[20] b "data.b"
        short[10] s "data.s"
        long[5] l "data.l"
    ctypedef struct XErrorEvent:
        int type
        Display *display
        XID resourceid
        unsigned long serial
        unsigned char error_code
        unsigned char request_code
        unsigned char minor_code
    ctypedef union XEvent:
        int type
        XAnyEvent xany
        XKeyEvent xkey
        XButtonEvent xbutton
        XFocusChangeEvent xfocus
        XCreateWindowEvent xcreatewindow
        XDestroyWindowEvent xdestroywindow
        XMapEvent xmap
        XUnmapEvent xunmap
        XConfigureEvent xconfigure
        XPropertyEvent xproperty
        XErrorEvent xerror
        XClientMessageEvent xclient
    ctypedef int (*XErrorHandler)(Display *display, XErrorEvent *error_event)  # type: ignore
    ctypedef struct XWindowAttributes:
        int x, y
        int width, height
        int border_width
        int depth
        Window root
        int map_state
        long all_event_masks
        long your_event_mask
        long do_not_propagate_mask
        int override_redirect
    
    # Functions
    Display *XOpenDisplay(char *display_name)
    int XCloseDisplay(Display *display)
    Window XDefaultRootWindow(Display *display)
    int XConnectionNumber(Display *display)
    Window XCreateWindow(
        Display *display,
        Window parent,
        int x,
        int y,
        unsigned int width,
        unsigned int height,
        unsigned int border_width,
        int depth,
        unsigned int clazz,
        Visual *visual,
        unsigned long valuemask,
        XSetWindowAttributes *attributes
    )
    int XMapWindow(Display *display, Window window)
    int XDestroyWindow(Display *display, Window window)
    int XSetInputFocus(Display *display, Window focus, int revert_to, Time time)
    int XGetInputFocus(Display *display, Window *focus_return, int *revert_to_return)
    int XGrabKey(
        Display *display,
        int keycode,
        unsigned int modifiers,
        Window grab_window,
        int owner_events,
        int pointer_mode,
        int keyboard_mode
    )
    int XUngrabKey(Display *display, int keycode, unsigned int modifiers, Window window)
    int XGrabButton(
        Display *display,
        unsigned int button,
        unsigned int modifiers,
        Window grab_window,
        int owner_events,
        unsigned int event_mask,
        int pointer_mode,
        int keyboard_mode,
        Window confine_to,
        Cursor cursor
    )
    int XUngrabButton(Display *display, unsigned int button, unsigned int modifiers, Window grab_window)
    int XSelectInput(Display *display, Window window, long event_mask)
    int XConfigureWindow(
        Display *display,
        Window window,
        unsigned int value_mask,
        XWindowChanges *values
    )
    int XSync(Display *display, int discard)
    XErrorHandler XSetErrorHandler(XErrorHandler handler)
    int XGetWindowProperty(
        Display *display,
        Window window,
        Atom property,
        long offset, long length,
        int delete,
        Atom req_type,
        Atom *actual_type_return,
        int *actual_format_return,
        unsigned long *nitems_return,
        unsigned long *bytes_after_return,
        unsigned char **prop_return
    )
    int XChangeProperty(
        Display *display,
        Window window,
        Atom property,
        Atom type,
        int format,
        int mode,
        const unsigned char *data,
        int nelements
    )
    Atom XInternAtom(Display *display, char *atom_name, int only_if_exists)
    int XFree(void *data)
    int XGetWindowAttributes(
        Display *display, Window window, XWindowAttributes *window_attributes_return
    )
    int XQueryTree(
        Display *display,
        Window window,
        Window *root_return,
        Window *parent_return,
        Window **children_return,
        unsigned int *nchildren_return
    )
    int XGetGeometry(
        Display *display,
        Drawable window,
        Window *root_return,
        int *x_return,
        int *y_return,
        unsigned int *width_return,
        unsigned int *height_return,
        unsigned int *border_width_return,
        unsigned int *depth_return
    )
    int XFlush(Display *display)
    char *XGetAtomName(Display *display, Atom atom)
    int XSendEvent(Display *display, Window window, int propagate, long event_mask, XEvent *event_send)
    KeySym XStringToKeysym(const char *string)
    KeyCode XKeysymToKeycode(Display *display, KeySym keysym)
    int XPending(Display *display)
    int XNextEvent(Display *display, XEvent *event_return)
    int XGetErrorText(Display *display, int code, char *buffer_return, int length)

cdef extern from "<X11/extensions/scrnsaver.h>": # pkg-config: xscrnsaver
    # Constants
    # State of screensaver
    int ScreenSaverOff
    int ScreenSaverOn
    int ScreenSaverCycle
    int ScreenSaverDisabled

    # Kind of screensaver
    int ScreenSaverBlanked
    int ScreenSaverInternal
    int ScreenSaverExternal

    # Defined types
    ctypedef struct XScreenSaverInfo:
        Window window
        int state
        int kind
        unsigned long til_or_since
        unsigned long idle
        unsigned long eventMask

    # Functions
    int XScreenSaverQueryInfo(Display *display, Drawable drawable, XScreenSaverInfo *saver_info)

cdef extern from "<X11/XKBlib.h>": # pkg-config: xext
    # This library includes automatically:
    # - <X11/extensions/XKBstr.h>
    # - <X11/extensions/XKB.h>

    # Constants
    int XkbUseCoreKbd

    # Group index
    int XkbGroup1Index
    int XkbGroup2Index
    int XkbGroup3Index
    int XkbGroup4Index
    int XkbAnyGroup
    int XkbAllGroups

    # Defined types
    ctypedef struct XkbStateRec:
        unsigned char group
        unsigned char locked_group
        unsigned short base_group
        unsigned short latched_group
        unsigned char mods
        unsigned char base_mods
        unsigned char latched_mods
        unsigned char locked_mods
        unsigned char compat_state
        unsigned char grab_mods
        unsigned char compat_grab_mods
        unsigned char lookup_mods
        unsigned char compat_lookup_mods
        unsigned short ptr_buttons
    
    # Functions
    int XkbGetState(Display *display, unsigned int device_spec, XkbStateRec *state_return)
    int XkbLockGroup(Display *display, unsigned int device_spec, unsigned int group)

cdef extern from "<X11/extensions/dpms.h>": # pkg-config: xext
    # Constants
    int DPMSModeOn
    int DPMSModeStandby
    int DPMSModeSuspend
    int DPMSModeOff

    # Defined types
    ctypedef unsigned short CARD16
    ctypedef unsigned char CARD8
    ctypedef CARD8 BOOL

    # Functions
    int DPMSInfo(Display *display, CARD16 *power_level, BOOL *state)
    int DPMSEnable(Display *display)
    int DPMSDisable(Display *display)

cdef extern from "<X11/extensions/XTest.h>": # pkg-config: xtst
    int XTestQueryExtension(Display *display, int *event_basep, int *error_basep, int *majorp, int *minorp)
    int XTestFakeKeyEvent(Display *display, unsigned int keycode, int is_press, unsigned long delay)
    int XTestFakeButtonEvent(Display *display, unsigned int button, int is_press, unsigned long delay)
    int XTestFakeMotionEvent(Display *display, int screen, int x, int y, unsigned long delay)
