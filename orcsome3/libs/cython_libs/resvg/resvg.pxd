from libc.stdint cimport uint32_t

# External libraries

cdef extern from "resvg.h":
    # Defined types
    ctypedef struct resvg_options:
        pass
    ctypedef struct resvg_render_tree:
        pass
    ctypedef struct resvg_transform:
        pass
    ctypedef struct resvg_size:
        double width
        double height
    ctypedef enum resvg_error:
        RESVG_OK
        RESVG_ERROR_NOT_AN_UTF8_STR
        RESVG_ERROR_FILE_OPEN_FAILED
        RESVG_ERROR_MALFORMED_GZIP
        RESVG_ERROR_ELEMENTS_LIMIT_REACHED
        RESVG_ERROR_INVALID_SIZE
        RESVG_ERROR_PARSING_FAILED
    ctypedef enum resvg_fit_to_type:
        RESVG_FIT_TO_TYPE_ORIGINAL
        RESVG_FIT_TO_TYPE_WIDTH
        RESVG_FIT_TO_TYPE_HEIGHT
        RESVG_FIT_TO_TYPE_ZOOM
    ctypedef struct resvg_fit_to:
        resvg_fit_to_type type
        float value

    # Functions
    resvg_options *resvg_options_create()
    int resvg_parse_tree_from_file(const char *file_path, const resvg_options *opt, resvg_render_tree **tree)
    void resvg_options_destroy(resvg_options *opt)
    resvg_size resvg_get_image_size(const resvg_render_tree *tree)
    resvg_transform resvg_transform_identity()
    void resvg_render(const resvg_render_tree *tree, resvg_fit_to fit_to, resvg_transform transform, uint32_t width, uint32_t height, char *pixmap)
    void resvg_tree_destroy(resvg_render_tree *tree)