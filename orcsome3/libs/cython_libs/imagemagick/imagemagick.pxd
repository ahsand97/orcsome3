# External libraries

cdef extern from "MagickWand/MagickWand.h":  # pkg-config: MagickWand
    # Defined types
    ctypedef struct ImageInfo:
        pass
    ctypedef struct MagickWand:
        pass
    ctypedef struct PixelWand:
        pass
    
    # Functions
    void MagickWandGenesis()
    void MagickWandTerminus()
    MagickWand *NewMagickWand()
    PixelWand *NewPixelWand()
    MagickWand *DestroyMagickWand(MagickWand *wand)
    PixelWand *DestroyPixelWand(PixelWand *wand)
    int PixelSetColor(PixelWand *wand, const char *color)
    int MagickSetBackgroundColor(MagickWand *wand, const PixelWand *background)
    int MagickPingImage(MagickWand *wand, const char *filename)
    int MagickReadImage(MagickWand *wand, const char *filename)
    int MagickSetImageFormat(MagickWand *wand, const char *format)
    unsigned char *MagickGetImageBlob(MagickWand *wand, size_t *size)



