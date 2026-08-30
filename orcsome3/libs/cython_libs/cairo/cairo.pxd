# External libraries

cdef extern from "cairo.h":  # pkg-config: cairo
    """
    #define gdImageSX(im) ((im)->sx)
    #define gdImageSY(im) ((im)->sy)

    #define gdTrueColorGetBlue(c) ((c) & 0x0000FF)
    #define gdImageBlue(im, c) ((im)->trueColor ? gdTrueColorGetBlue(c) : (im)->blue[(c)])
    #define gdImageGreen(im, c) ((im)->trueColor ? gdTrueColorGetGreen(c) : (im)->green[(c)])
    #define gdImageRed(im, c) ((im)->trueColor ? gdTrueColorGetRed(c) : (im)->red[(c)])
    #define gdImageAlpha(im, c) ((im)->trueColor ? gdTrueColorGetAlpha(c) : (im)->alpha[(c)])
    """
    # Defined types
    ctypedef struct cairo_surface_t:
        pass
    ctypedef enum resvg_fit_to_type:
        RESVG_FIT_TO_TYPE_ORIGINAL
        RESVG_FIT_TO_TYPE_WIDTH
        RESVG_FIT_TO_TYPE_HEIGHT
        RESVG_FIT_TO_TYPE_ZOOM
    ctypedef enum cairo_format_t:
        CAIRO_FORMAT_INVALID
        CAIRO_FORMAT_ARGB32
        CAIRO_FORMAT_RGB24
        CAIRO_FORMAT_A8
        CAIRO_FORMAT_A1
        CAIRO_FORMAT_RGB16_565
        CAIRO_FORMAT_RGB30
        CAIRO_FORMAT_RGB96F
        CAIRO_FORMAT_RGBA128F
    ctypedef struct resvg_fit_to:
        resvg_fit_to_type type
        float value
    ctypedef enum cairo_status_t:
        CAIRO_STATUS_SUCCESS
    ctypedef cairo_status_t (*cairo_write_func_t)(void *closure, const unsigned char *data, unsigned int length)  # type: ignore
    
    # Functions
    cairo_surface_t *cairo_image_surface_create(cairo_format_t format, int width, int height)
    unsigned char *cairo_image_surface_get_data (cairo_surface_t *surface)
    cairo_status_t cairo_surface_write_to_png_stream (cairo_surface_t *surface, cairo_write_func_t write_func, void *closure)
