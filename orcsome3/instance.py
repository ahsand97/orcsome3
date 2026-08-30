"""One orcsome3 process per X `$DISPLAY`, not per machine and not per monitor.

Same X server (several monitors on `:0` / `:0.0`) → one lock, one process. A second X
server (Chrome Remote Desktop, VNC, `:1`) has a different `DISPLAY` → another process,
so grabs and event selection stay on that connection only.
"""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
from typing import Optional, TextIO

from orcsome3.common import APPNAME


def display_key(display: Optional[str] = None) -> str:
    """Host + display number, dropping a trailing `.screen` so `:0` and `:0.0` share a lock."""
    raw: str = display if display is not None else os.getenv(key="DISPLAY", default=":0")
    if "." in raw:
        host_display: str
        screen: str
        host_display, screen = raw.rsplit(sep=".", maxsplit=1)
        if screen.isdigit():
            raw = host_display
    return raw or ":0"


def _lock_name(key: str) -> str:
    safe: str = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in key)
    return f"{safe}.lock"


def acquire_display_lock() -> Optional[TextIO]:
    """Exclusive lock for this `DISPLAY`. Keep the returned file open for the process lifetime.

    Returns `None` if another orcsome3 already holds the lock.
    """
    xdg: Optional[str] = os.getenv(key="XDG_RUNTIME_DIR")
    base: Path = Path(xdg) / APPNAME if xdg else Path(f"/tmp/{APPNAME}-{os.getuid()}")
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    handle: TextIO = (base / _lock_name(key=display_key())).open(mode="w")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    print(os.getpid(), file=handle, flush=True)
    return handle


def _self_check() -> None:
    assert display_key(display=":0.0") == ":0"
    assert display_key(display=":0") == ":0"
    assert display_key(display=":1.0") == ":1"
    assert display_key(display="localhost:10.0") == "localhost:10"
    assert display_key(display=":0") != display_key(display=":1")


if __name__ == "__main__":
    _self_check()
    print("ok")
