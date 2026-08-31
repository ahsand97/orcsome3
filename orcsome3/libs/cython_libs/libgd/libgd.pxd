ctypedef unsigned long int CARD32

# External libraries

cdef extern from "gd.h":  # pkg-config: gdlib
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
    ctypedef struct gdImage:
        pass
    ctypedef gdImage *gdImagePtr

    # Functions
    gdImagePtr gdImageCreateFromPngPtr(int size, void *data)
    int gdImageSX(gdImagePtr im)
    int gdImageSY(gdImagePtr im)
    int gdImageGetPixel(gdImagePtr im, int x, int y)
    int gdImageBlue(gdImagePtr im, int color)
    int gdImageGreen(gdImagePtr im, int color)
    int gdImageRed(gdImagePtr im, int color)
    int gdImageAlpha(gdImagePtr im, int color)
    void gdImageDestroy(gdImagePtr im)
