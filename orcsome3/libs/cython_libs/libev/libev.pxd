# External libraries

cdef extern from "ev.h":
    int EV_READ
    int EV_WRITE

    int EVBREAK_ALL
    int EVBREAK_ONE
    int EVBREAK_CANCEL

    int EVFLAG_AUTO
    int EVFLAG_NOENV
    int EVFLAG_FORKCHECK
    int EVFLAG_NOINOTIFY
    int EVFLAG_SIGNALFD
    int EVFLAG_NOSIGMASK
    int EVBACKEND_SELECT
    int EVBACKEND_POLL
    int EVBACKEND_EPOLL
    int EVBACKEND_KQUEUE
    int EVBACKEND_DEVPOLL
    int EVBACKEND_PORT
    int EVBACKEND_ALL
    int EVBACKEND_MASK

    int EVRUN_ONCE
    int EVRUN_NOWAIT

    ctypedef double ev_tstamp
    cdef struct ev_loop:
        pass
    ctypedef struct ev_io:
        void *data
    ctypedef struct ev_signal:
        void *data
    ctypedef struct ev_timer:
        void *data
    ctypedef struct ev_stat:
        void *data

    ev_loop *ev_loop_new(unsigned int flags)
    void ev_loop_destroy(ev_loop *loop)
    void ev_break(ev_loop *loop, int how)
    int ev_run(ev_loop *loop, int flags) nogil
    void ev_io_start(ev_loop *loop, ev_io *watcher)
    void ev_io_stop(ev_loop *loop, ev_io *watcher)
    void ev_signal_start(ev_loop *loop, ev_signal *signal)
    void ev_signal_stop(ev_loop *loop, ev_signal *signal)
    void ev_timer_set(ev_timer *timer, ev_tstamp after, ev_tstamp repeat)
    void ev_timer_start(ev_loop *loop, ev_timer *timer)
    void ev_timer_again(ev_loop *loop, ev_timer *timer)
    void ev_timer_stop(ev_loop *loop, ev_timer *timer)
    ev_tstamp ev_timer_remaining(ev_loop *loop, ev_timer *timer)
    void ev_stat_start(ev_loop *loop, ev_stat *watcher)
    void ev_stat_stop(ev_loop *loop, ev_stat *watcher)

ctypedef ev_loop evLoop
ctypedef void (*io_cb)(ev_loop *loop, ev_io *watcher, int revents) noexcept nogil  # type: ignore
ctypedef void (*signal_cb)(ev_loop *loop, ev_signal *watcher, int revents) noexcept nogil  # type: ignore
ctypedef void (*timer_cb)(ev_loop *loop, ev_timer *watcher, int revents) noexcept nogil  # type: ignore
ctypedef void (*stat_cb)(ev_loop *loop, ev_stat *watcher, int revents) noexcept nogil  # type: ignore

cdef extern from "ev.h":
    void ev_io_init(ev_io *ev_io, io_cb callback, int fd, int events)
    void ev_signal_init(ev_signal *signal, signal_cb callback, int signum)
    void ev_timer_init(ev_timer *timer, timer_cb callback, ev_tstamp after, ev_tstamp repeat)
    void ev_stat_init(ev_stat *watcher, stat_cb callback, const char *path, ev_tstamp interval)
