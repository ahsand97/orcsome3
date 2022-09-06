from typing import List, Tuple

import cffi
from cffi.api import FFI

from orcsome3.orcsome import utils

source: str = """
#include <X11/Xlib.h>
#include <X11/XKBlib.h>
#include <X11/extensions/scrnsaver.h>
#include <X11/extensions/dpms.h>
#include <X11/extensions/XKB.h>
#include <X11/extensions/XKBstr.h>
#include <MagickWand/MagickWand.h>

#define gdMaxColors 256
#define gdImageSX(im) ((im)->sx)
#define gdImageSY(im) ((im)->sy)
#define gdTrueColorGetBlue(c) ((c) & 0x0000FF)
#define gdTrueColorGetGreen(c) (((c) & 0x00FF00) >> 8)
#define gdTrueColorGetRed(c) (((c) & 0xFF0000) >> 16)
#define gdTrueColorGetAlpha(c) (((c) & 0x7F000000) >> 24)
#define gdImageBlue(im, c) ((im)->trueColor ? gdTrueColorGetBlue(c) : (im)->blue[(c)])
#define gdImageGreen(im, c) ((im)->trueColor ? gdTrueColorGetGreen(c) : (im)->green[(c)])
#define gdImageRed(im, c) ((im)->trueColor ? gdTrueColorGetRed(c) : (im)->red[(c)])
#define gdImageAlpha(im, c) ((im)->trueColor ? gdTrueColorGetAlpha(c) : (im)->alpha[(c)])

typedef enum {
    GD_DEFAULT = 0,
    GD_BELL,
    GD_BESSEL,
    GD_BILINEAR_FIXED,
    GD_BICUBIC,
    GD_BICUBIC_FIXED,
    GD_BLACKMAN,
    GD_BOX,
    GD_BSPLINE,
    GD_CATMULLROM,
    GD_GAUSSIAN,
    GD_GENERALIZED_CUBIC,
    GD_HERMITE,
    GD_HAMMING,
    GD_HANNING,
    GD_MITCHELL,
    GD_NEAREST_NEIGHBOUR,
    GD_POWER,
    GD_QUADRATIC,
    GD_SINC,
    GD_TRIANGLE,
    GD_WEIGHTED4,
    GD_LINEAR,
    GD_LANCZOS3,
    GD_LANCZOS8,
    GD_BLACKMAN_BESSEL,
    GD_BLACKMAN_SINC,
    GD_QUADRATIC_BSPLINE,
    GD_CUBIC_SPLINE,
    GD_COSINE,
    GD_WELSH,
    GD_METHOD_COUNT = 30
    } gdInterpolationMethod;

typedef double (* interpolation_method )(double, double);

typedef struct gdImageStruct {
    /* Palette-based image pixels */
    unsigned char **pixels;
    int sx;
    int sy;
    /* These are valid in palette images only. See also
        'alpha', which appears later in the structure to
        preserve binary backwards compatibility */
    int colorsTotal;
    int red[gdMaxColors];
    int green[gdMaxColors];
    int blue[gdMaxColors];
    int open[gdMaxColors];
    /* For backwards compatibility, this is set to the
        first palette entry with 100% transparency,
        and is also set and reset by the
        gdImageColorTransparent function. Newer
        applications can allocate palette entries
        with any desired level of transparency; however,
        bear in mind that many viewers, notably
        many web browsers, fail to implement
        full alpha channel for PNG and provide
        support for full opacity or transparency only. */
    int transparent;
    int *polyInts;
    int polyAllocated;
    struct gdImageStruct *brush;
    struct gdImageStruct *tile;
    int brushColorMap[gdMaxColors];
    int tileColorMap[gdMaxColors];
    int styleLength;
    int stylePos;
    int *style;
    int interlace;
    /* New in 2.0: thickness of line. Initialized to 1. */
    int thick;
    /* New in 2.0: alpha channel for palettes. Note that only
        Macintosh Internet Explorer and (possibly) Netscape 6
        really support multiple levels of transparency in
        palettes, to my knowledge, as of 2/15/01. Most
        common browsers will display 100% opaque and
        100% transparent correctly, and do something
        unpredictable and/or undesirable for levels
        in between. TBB */
    int alpha[gdMaxColors];
    /* Truecolor flag and pixels. New 2.0 fields appear here at the
        end to minimize breakage of existing object code. */
    int trueColor;
    int **tpixels;
    /* Should alpha channel be copied, or applied, each time a
        pixel is drawn? This applies to truecolor images only.
        No attempt is made to alpha-blend in palette images,
        even if semitransparent palette entries exist.
        To do that, build your image as a truecolor image,
        then quantize down to 8 bits. */
    int alphaBlendingFlag;
    /* Should the alpha channel of the image be saved? This affects
        PNG at the moment; other future formats may also
        have that capability. JPEG doesn't. */
    int saveAlphaFlag;

    /* There should NEVER BE ACCESSOR MACROS FOR ITEMS BELOW HERE, so this
        part of the structure can be safely changed in new releases. */

    /* 2.0.12: anti-aliased globals. 2.0.26: just a few vestiges after
        switching to the fast, memory-cheap implementation from PHP-gd. */
    int AA;
    int AA_color;
    int AA_dont_blend;

    /* 2.0.12: simple clipping rectangle. These values
        must be checked for safety when set; please use
        gdImageSetClip */
    int cx1;
    int cy1;
    int cx2;
    int cy2;

    /* 2.1.0: allows to specify resolution in dpi */
    unsigned int res_x;
    unsigned int res_y;

    /* Selects quantization method, see gdImageTrueColorToPaletteSetMethod() and gdPaletteQuantizationMethod enum. */
    int paletteQuantizationMethod;
    /* speed/quality trade-off. 1 = best quality, 10 = best speed. 0 = method-specific default.
        Applicable to GD_QUANT_LIQ and GD_QUANT_NEUQUANT. */
    int paletteQuantizationSpeed;
    /* Image will remain true-color if conversion to palette cannot achieve given quality.
        Value from 1 to 100, 1 = ugly, 100 = perfect. Applicable to GD_QUANT_LIQ.*/
    int paletteQuantizationMinQuality;
    /* Image will use minimum number of palette colors needed to achieve given quality. Must be higher than paletteQuantizationMinQuality
        Value from 1 to 100, 1 = ugly, 100 = perfect. Applicable to GD_QUANT_LIQ.*/
    int paletteQuantizationMaxQuality;
    gdInterpolationMethod interpolation_id;
    interpolation_method interpolation;
} gdImage;

typedef gdImage *gdImagePtr;

/* We can't use the one defined in Xmd.h because that's an "unsigned int",
 * which comes out as a 32bit type always. We need this to be 64bit on 64bit
 * machines.
 */
typedef unsigned long int CARD32_;

gdImagePtr gdImageCreateFromPngPtr (int size, void* data);
void gdImageDestroy(gdImagePtr im);
int gdImageGetPixel(gdImagePtr im, int x, int y);

void set_window_icon(Display *display, Window window, char *filepath) {
    gdImagePtr imagePtr = NULL; // Default value, if the image can't be loaded then the result is going to be NULL
    MagickWand *wand = NewMagickWand();
    PixelWand *pixelWand = NewPixelWand();
    
    PixelSetColor(pixelWand, "transparent"); // Color for the background
    // The background has to be assigned before loading the file image
    // to avoid white backgrounds (happens with svg files)
    MagickSetBackgroundColor(wand, pixelWand);
    
    int result = 0;
    result = MagickReadImage(wand, filepath); // Reads the file
    if (!result) {
        return;
    }
    result = MagickSetImageFormat(wand, "png"); // Converts the wand (image) to PNG format
    if (!result) {
        return;
    }
    // If the conversion is successful then it creates an imagePtr from the content of the wand
    size_t length;
    unsigned char *info = MagickGetImageBlob(wand, &length); // Gets image data and size from the wand
    imagePtr = gdImageCreateFromPngPtr((int) length, info); // Creates imagePtr from png data
    if (imagePtr == NULL) {
        return;
    }
    
    DestroyMagickWand(wand);
    DestroyPixelWand(pixelWand);

    int width, height;
    width = gdImageSX(imagePtr);
    height = gdImageSY(imagePtr);

    unsigned int ndata = (width * height) + 2;
    CARD32_* data = (CARD32_*) calloc(ndata, sizeof(CARD32_));

    int i = 0;
    data[i++] = width;
    data[i++] = height;

    int x, y;
    for(y = 0; y < height; y++) {
        for(x = 0; x < width; x++) {
            // data is RGBA
            // We'll do some horrible data-munging here
            unsigned char* cols = (unsigned char*) &(data[i++]);
            int pixcolour = gdImageGetPixel(imagePtr, x, y);

            cols[0] = gdImageBlue(imagePtr, pixcolour);
            cols[1] = gdImageGreen(imagePtr, pixcolour);
            cols[2] = gdImageRed(imagePtr, pixcolour);

            /* Alpha is more difficult */
            int alpha = 127 - gdImageAlpha(imagePtr, pixcolour); // 0 to 127
            // Scale it up to 0 to 255; remembering that 2*127 should be max
            cols[3] = alpha == 127 ? 255 : (alpha *= 2);
        }
    }
    gdImageDestroy(imagePtr);

    Atom property = XInternAtom(display, "_NET_WM_ICON", 0);
    Atom type = XInternAtom(display, "CARDINAL", 0);
    result = XChangeProperty(display, window, property, type, 32, PropModeReplace, (unsigned char*) data, (int) ndata);
    if (result) {
        XFlush(display);
    }
    XFree(data);
}
"""

export_source: str = """
static const long StructureNotifyMask;
static const long SubstructureNotifyMask;
static const long SubstructureRedirectMask;
static const long PropertyChangeMask;
static const long FocusChangeMask;
static const long KeyPressMask;
static const long KeyReleaseMask;

static const long CurrentTime;

static const int KeyPress;
static const int KeyRelease;
static const int CreateNotify;
static const int DestroyNotify;
static const int FocusIn;
static const int FocusOut;
static const int PropertyNotify;
static const int ClientMessage;

static const int CWX;
static const int CWY;
static const int CWWidth;
static const int CWHeight;
static const int CWBorderWidth;
static const int CWSibling;
static const int CWStackMode;

static const int Above;
static const int Below;

static const int ShiftMask;
static const int LockMask;
static const int ControlMask;
static const int Mod1Mask;
static const int Mod2Mask;
static const int Mod3Mask;
static const int Mod4Mask;
static const int Mod5Mask;
static const int AnyKey;
static const int AnyModifier;

static const long NoSymbol;

static const int GrabModeSync;
static const int GrabModeAsync;

static const int PropModeReplace;
static const int PropModePrepend;
static const int PropModeAppend;

static const int XkbUseCoreKbd;

static const int ScreenSaverOff;
static const int ScreenSaverOn;
static const int ScreenSaverDisabled;
static const int ScreenSaverBlanked;
static const int ScreenSaverInternal;
static const int ScreenSaverExternal;

static const int IsUnmapped;
static const int IsUnviewable;
static const int IsViewable;

static const int PropertyNewValue;
static const int PropertyDelete;

static const int NotifyNormal;
static const int NotifyWhileGrabbed;
static const int NotifyGrab;
static const int NotifyUngrab;

static const int NotifyAncestor;
static const int NotifyVirtual;
static const int NotifyInferior;
static const int NotifyNonlinear;
static const int NotifyNonlinearVirtual;
static const int NotifyPointer;
static const int NotifyPointerRoot;
static const int NotifyDetailNone;

static const int AnyPropertyType;

// Events related with SubstructureRedirectMask
static const int CirculateNotify;
static const int ConfigureNotify;
static const int GravityNotify;
static const int MapNotify;
static const int ReparentNotify;
static const int UnmapNotify;

typedef int Bool;
typedef int Status;
typedef unsigned long XID;
typedef unsigned long Time;
typedef unsigned long Atom;
typedef XID Window;
typedef XID Drawable;
typedef XID KeySym;
typedef XID Cursor;
typedef unsigned char KeyCode;
typedef ... Display;
typedef ... Visual;
typedef XID Colormap;
typedef ... Screen;

typedef struct {
    int type;
    unsigned long serial;   /* # of last request processed by server */
    Bool send_event;        /* true if this came from a SendEvent request */
    Display *display;       /* Display the event was read from */
    Window window;          /* window on which event was requested in event mask */
} XAnyEvent;

typedef struct {
    int type;
    unsigned long serial;   /* # of last request processed by server */
    Bool send_event;        /* true if this came from a SendEvent request */
    Display *display;       /* Display the event was read from */
    Window window;
    Atom message_type;
    int format;
    union {
        char b[20];
        short s[10];
        long l[5];
    } data;
} XClientMessageEvent;

typedef struct {
    int type;               /* of event */
    unsigned long serial;   /* # of last request processed by server */
    Bool send_event;        /* true if this came from a SendEvent request */
    Display *display;       /* Display the event was read from */
    Window window;          /* "event" window it is reported relative to */
    Window root;            /* root window that the event occurred on */
    Window subwindow;       /* child window */
    Time time;              /* milliseconds */
    int x, y;               /* pointer x, y coordinates in event window */
    int x_root, y_root;     /* coordinates relative to root */
    unsigned int state;     /* key or button mask */
    unsigned int keycode;   /* detail */
    Bool same_screen;       /* same screen flag */
} XKeyEvent;

typedef struct {
    int type;
    unsigned long serial;   /* # of last request processed by server */
    Bool send_event;        /* true if this came from a SendEvent request */
    Display *display;       /* Display the event was read from */
    Window parent;          /* parent of the window */
    Window window;          /* window id of window created */
    int x, y;               /* window location */
    int width, height;      /* size of window */
    int border_width;       /* border width */
    Bool override_redirect; /* creation should be overridden */
} XCreateWindowEvent;

typedef struct {
    int type;
    unsigned long serial;   /* # of last request processed by server */
    Bool send_event;        /* true if this came from a SendEvent request */
    Display *display;       /* Display the event was read from */
    Window event;
    Window window;
} XDestroyWindowEvent;

typedef struct {
    int type;               /* FocusIn or FocusOut */
    unsigned long serial;   /* # of last request processed by server */
    Bool send_event;        /* true if this came from a SendEvent request */
    Display *display;       /* Display the event was read from */
    Window window;          /* window of event */
    int mode;               /* NotifyNormal, NotifyWhileGrabbed, NotifyGrab, NotifyUngrab */
    int detail;             /* NotifyAncestor, NotifyVirtual, NotifyInferior,
                            * NotifyNonlinear,NotifyNonlinearVirtual, NotifyPointer,
                            * NotifyPointerRoot, NotifyDetailNone
                            */
} XFocusChangeEvent;

typedef struct {
    int type;
    unsigned long serial;   /* # of last request processed by server */
    Bool send_event;        /* true if this came from a SendEvent request */
    Display *display;       /* Display the event was read from */
    Window window;
    Atom atom;
    Time time;
    int state;              /* NewValue, Deleted */
} XPropertyEvent;

typedef struct {
    int type;
    Display *display;           /* Display the event was read from */
    XID resourceid;             /* resource id */
    unsigned long serial;       /* serial number of failed request */
    unsigned char error_code;   /* error code of failed request */
    unsigned char request_code; /* Major op-code of failed request */
    unsigned char minor_code;   /* Minor op-code of failed request */
} XErrorEvent;

typedef int (*XErrorHandler) (Display* display, XErrorEvent* event);
int XGetErrorText(Display *display, int code, char *buffer_return, int length);

typedef union {
    int type;
    XAnyEvent xany;
    XErrorEvent xerror;
    XKeyEvent xkey;
    XCreateWindowEvent xcreatewindow;
    XDestroyWindowEvent xdestroywindow;
    XFocusChangeEvent xfocus;
    XPropertyEvent xproperty;
    ...;
} XEvent;

typedef struct {
    int x, y;
    int width, height;
    int border_width;
    Window sibling;
    int stack_mode;
} XWindowChanges;

typedef struct {
    Window window;                 /* screen saver window */
    int state;                     /* ScreenSaver{Off,On,Disabled} */
    int kind;                      /* ScreenSaver{Blanked,Internal,External} */
    unsigned long til_or_since;    /* milliseconds */
    unsigned long idle;            /* milliseconds */
    unsigned long eventMask;       /* events */
} XScreenSaverInfo;


XErrorHandler XSetErrorHandler (XErrorHandler handler);

Display* XOpenDisplay(char *display_name);
int XCloseDisplay(Display *display);
int XFree(void *data);
Atom XInternAtom(Display *display, char *atom_name, Bool only_if_exists);
char* XGetAtomName(Display *display, Atom atom);

int XPending(Display *display);
int XNextEvent(Display *display, XEvent *event_return);
int XSelectInput(Display *display, Window w, long event_mask);
int XFlush(Display *display);
int XSync(Display *display, Bool discard);
Status XSendEvent(Display *display, Window w, Bool propagate, long event_mask, XEvent *event_send);

KeySym XStringToKeysym(char *string);
KeyCode XKeysymToKeycode(Display *display, KeySym keysym);

int XGrabKey(Display *display, int keycode, unsigned int modifiers,
    Window grab_window, Bool owner_events, int pointer_mode, int keyboard_mode);
int XUngrabKey(Display *display, int keycode, unsigned int modifiers, Window grab_window);

int XGetWindowProperty(Display *display, Window w, Atom property,
    long long_offset, long long_length, Bool delete, Atom req_type,
    Atom *actual_type_return, int *actual_format_return,
    unsigned long *nitems_return, unsigned long *bytes_after_return,
    unsigned char **prop_return);
int XChangeProperty(Display *display, Window w, Atom property, Atom type,
    int format, int mode, unsigned char *data, int nelements);
int XDeleteProperty(Display *display, Window w, Atom property);
int XConfigureWindow(Display *display, Window w, unsigned int value_mask,
    XWindowChanges *changes);

Status XGetGeometry(Display *display, Drawable d, Window *root_return,
    int *x_return, int *y_return, unsigned int *width_return,
    unsigned int *height_return, unsigned int *border_width_return, unsigned int *depth_return);

Status XScreenSaverQueryInfo(Display *dpy, Drawable drawable, XScreenSaverInfo *saver_info);

Status DPMSInfo (Display *display, unsigned short *power_level, unsigned char *state);
Status DPMSEnable (Display *display);
Status DPMSDisable (Display *display);

Window DefaultRootWindow(Display *display);
int ConnectionNumber(Display *display);

typedef struct {
    unsigned char   group;
    unsigned char   locked_group;
    unsigned short  base_group;
    unsigned short  latched_group;
    unsigned char   mods;
    unsigned char   base_mods;
    unsigned char   latched_mods;
    unsigned char   locked_mods;
    unsigned char   compat_state;
    unsigned char   grab_mods;
    unsigned char   compat_grab_mods;
    unsigned char   lookup_mods;
    unsigned char   compat_lookup_mods;
    unsigned short  ptr_buttons;
} XkbStateRec;

Status XkbGetState (Display *display, unsigned int device_spec, XkbStateRec *state_return);
Bool XkbLockGroup (Display *display, unsigned int device_spec, unsigned int group);

typedef struct {
    int x, y;                       /* location of window */
    int width, height;              /* width and height of window */
    int border_width;               /* border width of window */
    int depth;                      /* depth of window */
    Visual *visual;                 /* the associated visual structure */
    Window root;                    /* root of screen containing window */
    int class;                      /* InputOutput, InputOnly*/
    int bit_gravity;                /* one of the bit gravity values */
    int win_gravity;                /* one of the window gravity values */
    int backing_store;              /* NotUseful, WhenMapped, Always */
    unsigned long backing_planes;   /* planes to be preserved if possible */
    unsigned long backing_pixel;    /* value to be used when restoring planes */
    Bool save_under;                /* boolean, should bits under be saved? */
    Colormap colormap;              /* color map to be associated with window */
    Bool map_installed;             /* boolean, is color map currently installed*/
    int map_state;                  /* IsUnmapped, IsUnviewable, IsViewable */
    long all_event_masks;           /* set of events all people have interest in*/
    long your_event_mask;           /* my event mask */
    long do_not_propagate_mask;     /* set of events that should not propagate */
    Bool override_redirect;         /* boolean value for override-redirect */
    Screen *screen;                 /* back pointer to correct screen */
} XWindowAttributes;

Status XGetWindowAttributes(Display *display, Window w, XWindowAttributes *window_attributes_return);

void set_window_icon(Display *display, Window window, char *filepath);
void MagickWandGenesis(void);
void MagickWandTerminus(void);
extern "Python" int error_handler(Display* display, XErrorEvent* event);
Status XQueryTree(
    Display *display,
    Window window,
    Window *root_return,
    Window *parent_return,
    Window **children_return,
    unsigned int *nchildren_return
);
"""

LIBRARIES: List[str] = ["x11", "xscrnsaver", "xext", "MagickWand", "gdlib"]
compiler_args: Tuple[List[str], List[str]] = utils.get_compiler_args(*LIBRARIES)

ffibuilder: FFI = cffi.FFI()

ffibuilder.set_source(
    module_name="orcsome3.orcsome._xlib", source=source, extra_compile_args=compiler_args[0], libraries=compiler_args[1]
)

ffibuilder.cdef(csource=export_source, override=True)


def main(verbose: bool = False) -> None:
    ffibuilder.compile(verbose=verbose)


if __name__ == "__main__":
    main(verbose=True)
