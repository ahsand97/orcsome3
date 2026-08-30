"""CLI entrypoint and the process-wide WindowManager singleton.

`get_wm()` is the public way to reach the running manager from `rc.py`.
`run()` parses argv, loads the config, and starts the libev loop.
"""

from __future__ import annotations

import logging
import os
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from signal import Signals
from typing import Callable, Optional, TextIO, Union, cast

from orcsome3.common import APPNAME, VERSION
from orcsome3.instance import acquire_display_lock, display_key
from orcsome3.libs.ev import Loop, SignalWatcher, StatWatcher, TimerWatcher
from orcsome3.notify import NotificationBus
from orcsome3.utils import SingletonMixin, execfile
from orcsome3.window_manager import WindowManager

_RC_DEBOUNCE_SECONDS: float = 0.3


class _Orcsome3(SingletonMixin):
    """Process-wide runtime: event loop, WindowManager, and config path."""

    def __init__(self) -> None:
        if type(self)._singleton_init_done():
            return
        self._wm: Optional[WindowManager] = None
        self._config_file: Optional[Path] = None
        self._loop: Optional[Loop] = None
        self._lock_file: Optional[TextIO] = None
        self._signal_watchers: list[SignalWatcher] = []
        self._rc_watcher: Optional[StatWatcher] = None
        self._rc_debounce: Optional[TimerWatcher] = None
        self._restarting: bool = False

    @property
    def wm(self) -> WindowManager:
        """The singleton WindowManager created in `run()`."""
        return cast(WindowManager, self._wm)

    @property
    def config_file(self) -> Path:
        """Resolved path of the loaded `rc.py`."""
        return cast(Path, self._config_file)

    @property
    def loop(self) -> Loop:
        """libev loop that drives X events and timers."""
        return cast(Loop, self._loop)

    def run(self, config_file: Path) -> None:
        """Take the DISPLAY lock, load `config_file`, connect D-Bus, then run the event loop until stop."""
        self._lock_file = acquire_display_lock()
        if self._lock_file is None:
            _logger.error(msg=f"orcsome3 already running on DISPLAY={display_key()}")
            sys.exit(1)

        self._config_file = config_file.resolve()
        self._loop = Loop.new()
        self._wm = WindowManager(loop=self.loop)

        self.wm.set_restart_handler(handler=self.restart)
        self._watch_signal(signal_number=Signals.SIGINT, callback=lambda __loop__, __watcher__, __events__: self.stop())
        self._watch_signal(
            signal_number=Signals.SIGTERM, callback=lambda __loop__, __watcher__, __events__: self.stop()
        )
        self._watch_signal(
            signal_number=Signals.SIGUSR1, callback=lambda __loop__, __watcher__, __events__: self.restart()
        )

        _ = self.load_config(fatal=True)
        self._start_rc_watcher()

        _ = NotificationBus()

        self.wm.init()
        self.loop.run()

    def _watch_signal(self, signal_number: Signals, callback: Callable[[Loop, SignalWatcher, int], None]) -> None:
        watcher: SignalWatcher = SignalWatcher.new(callback=callback, signal_number=signal_number)
        watcher.start(loop=self.loop)
        self._signal_watchers.append(watcher)

    def _start_rc_watcher(self) -> None:
        """Watch `rc.py` via `ev_stat` (inotify, with a libev `stat` fallback)."""
        self._rc_watcher = StatWatcher.new(callback=self._on_rc_stat, path=str(self.config_file), interval=0.0)
        self._rc_watcher.start(loop=self.loop)
        self._rc_debounce = TimerWatcher.new(callback=self._on_rc_debounce, after=_RC_DEBOUNCE_SECONDS, repeat=0.0)

    def _on_rc_stat(self, __loop__: Loop, __watcher__: StatWatcher, __events__: int) -> None:
        if self._rc_debounce is None:
            return
        self._rc_debounce.stop(loop=self.loop)
        self._rc_debounce.start(loop=self.loop, after=_RC_DEBOUNCE_SECONDS)

    def _on_rc_debounce(self, __loop__: Loop, __watcher__: TimerWatcher, __events__: int) -> None:
        self.restart()

    def restart(self) -> None:
        """Reload `rc.py` and re-init the window manager without exiting the process."""
        if self._restarting:
            return
        self._restarting = True
        try:
            self.wm.stop()
            _logger.info(msg="Restarting...")
            loaded: bool = self.load_config(fatal=False)
            self.wm.init()
            if loaded:
                _logger.info(msg="Restarted successfully")
            else:
                _logger.error(msg="Reload failed; running with no rc.py handlers")
        finally:
            self._restarting = False

    def stop(self) -> None:
        """Ungrab keys, close the display, disconnect D-Bus, and break the event loop."""
        print("Stopping orcsome3...")
        for watcher in self._signal_watchers:
            watcher.close(loop=self.loop)
        self._signal_watchers = []
        if self._rc_watcher is not None:
            self._rc_watcher.close(loop=self.loop)
            self._rc_watcher = None
        if self._rc_debounce is not None:
            self._rc_debounce.close(loop=self.loop)
            self._rc_debounce = None
        if self._wm is not None:
            self.wm.stop(exit=True)
        NotificationBus.stop()
        if self._lock_file is not None:
            self._lock_file.close()
            self._lock_file = None
        if self._loop is not None:
            self.loop.break_(how=Loop.BreakFlags.EVBREAK_ALL)
            self.loop.destroy()
            self._loop = None

    def load_config(self, *, fatal: bool = True) -> bool:
        """Exec `rc.py` with `__file__` / `__name__` set. Initial load exits on error; reload does not."""
        config_dir: str = str(self.config_file.parent)
        config_globals: dict[str, object] = {
            "__file__": str(self.config_file),
            "__name__": "__orcsome3_config__",
        }
        try:
            sys.path.insert(0, config_dir)
            execfile(filepath=self.config_file, globals_=config_globals)
        except Exception:
            _logger.exception(msg=f"Error on loading {self.config_file}")
            if fatal:
                sys.exit(1)
            return False
        finally:
            if sys.path and sys.path[0] == config_dir:
                _ = sys.path.pop(0)
        return True


# Globals
_logger: logging.Logger = logging.getLogger(name=__name__)
_orcsome3: _Orcsome3 = _Orcsome3()  # global _Orcsome3 single instance


def get_wm() -> WindowManager:
    """Return the process-wide WindowManager.

    Call this from `rc.py` (or any code running after `orcsome3` has started).
    Constructing `WindowManager()` yourself returns the same singleton once `run()` has created it.
    """
    return _orcsome3.wm


def run() -> None:
    """CLI entry: parse `--config` / logging flags and start the orcsome3 process."""

    parser: ArgumentParser = ArgumentParser(prog=APPNAME)
    _ = parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    _ = parser.add_argument(
        "-l", "--log-file", dest="log", help="Path to log file (log to stdout by default)", type=Path
    )
    _ = parser.add_argument("--log-level", default="INFO", help="log level, default is INFO")
    _ = parser.add_argument(
        "-c",
        "--config",
        default=Path(os.getenv(key="XDG_CONFIG_HOME", default=str(Path("~/.config").expanduser()))).joinpath(
            "orcsome3", "rc.py"
        ),
        help="Path to config file",
        type=Path,
        required=False,
    )

    args: Namespace = parser.parse_args()

    logger_handler: Union[logging.FileHandler, logging.StreamHandler[TextIO]] = (
        logging.FileHandler(filename=str(args.log)) if args.log is not None else logging.StreamHandler()
    )
    logger_handler.setFormatter(
        fmt=logging.Formatter(fmt="%(asctime)s %(name)s %(levelname)s: %(message)s", datefmt="%d/%m/%Y %H:%M:%S")
    )
    root_logger: logging.Logger = logging.getLogger()
    root_logger.setLevel(level=args.log_level)
    root_logger.addHandler(hdlr=logger_handler)

    config_path: Path = cast(Path, args.config).expanduser().resolve()
    if not config_path.is_file():
        _logger.error(msg="The config file provided is not valid, exiting...")
        return

    _orcsome3.run(config_file=config_path)


if __name__ == "__main__":
    run()
