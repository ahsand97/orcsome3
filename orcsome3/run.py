import logging
import os
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from signal import Signals
from typing import Optional, TextIO, Union, cast

from orcsome3.common import APPNAME, VERSION
from orcsome3.libs.ev import Loop, SignalWatcher
from orcsome3.notify import NotificationBus
from orcsome3.utils import Singleton, execfile
from orcsome3.window_manager import WindowManager


class _Orcsome3(metaclass=Singleton["_Orcsome3"]):
    """Orcsome3 main class"""

    def __init__(self) -> None:
        self._wm: Optional[WindowManager] = None
        self._config_file: Optional[Path] = None
        self._loop: Optional[Loop] = None

    @property
    def wm(self) -> WindowManager:
        return cast(WindowManager, self._wm)

    @property
    def config_file(self) -> Path:
        return cast(Path, self._config_file)

    @property
    def loop(self) -> Loop:
        return cast(Loop, self._loop)

    def run(self, config_file: Path) -> None:
        """Start orcsome3"""
        self._config_file = config_file
        self._loop = Loop.new()
        # self._wm = WindowManager(loop=self.loop)

        # Assign wm restart handler
        # self.wm.set_restart_handler(handler=self.restart)

        # Signal watcher to stop event loop when a SIGINT arrives
        signal_watcher: SignalWatcher = SignalWatcher.new(
            callback=lambda __loop__, __watcher__, __events__: self.stop(), signal_number=Signals.SIGINT
        )
        signal_watcher.start(loop=self.loop)

        # Load configuration file
        # self.load_config()

        # Start notification thread
        _ = NotificationBus()

        # Start orcsome3 execution
        # self.wm.init()
        self.loop.run()

    def restart(self) -> None:
        """Restart orcsome3"""
        self.wm.stop()
        _logger.info(msg="Restarting...")
        self.load_config()
        self.wm.init()
        _logger.info(msg="Restarted successfully")

    def stop(self) -> None:
        """Stop orcsome3"""
        print("Stopping orcsome3...")
        # self.wm.stop(exit=True)
        self.loop.break_(how=Loop.BreakFlags.EVBREAK_ALL)
        self.loop.destroy()
        # NotificationBus.stop()

    def load_config(self) -> None:
        """Load configuration file"""
        try:
            sys.path.insert(0, str(self.config_file))
            execfile(filepath=self.config_file)
        except Exception:
            _logger.exception(msg=f"Error on loading {self.config_file}")
            sys.exit(1)
        finally:
            _ = sys.path.pop(0)


# Globals
_logger: logging.Logger = logging.getLogger(name=__name__)
_orcsome3: _Orcsome3 = _Orcsome3()  # global _Orcsome3 single instance


def get_wm() -> WindowManager:
    """Get global wm"""
    return _orcsome3.wm


def run() -> None:
    """Orcsome3 main function. This function is the first one executed when starting the app."""

    # CLI arguments
    parser: ArgumentParser = ArgumentParser(prog=APPNAME)
    _ = parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    _ = parser.add_argument(
        "-l", "--log-file", dest="log", help="Path to log file (log to stdout by default)", type=Path
    )
    _ = parser.add_argument("--log-level", default="INFO", help="log level, default is INFO")
    # config_file = Path(__file__).parent.parent.joinpath("prueba.py")  # FALTA QUITAR ESTA LINEA
    _ = parser.add_argument(
        "-c",
        "--config",
        default=Path(os.getenv(key="XDG_CONFIG_HOME", default=str(Path("~/.config").expanduser()))).joinpath(
            "orcsome3", "rc.py"
        ),
        help="Path to config file",
        type=Path,
        required=False,
    )  # Change required to True

    # Parse arguments
    args: Namespace = parser.parse_args()

    # Setup logger
    logger_handler: Union[logging.FileHandler, logging.StreamHandler[TextIO]] = (
        logging.FileHandler(filename=str(args.log)) if args.log is not None else logging.StreamHandler()
    )
    logger_handler.setFormatter(
        fmt=logging.Formatter(fmt="%(asctime)s %(name)s %(levelname)s: %(message)s", datefmt="%d/%m/%Y %H:%M:%S")
    )
    root_logger: logging.Logger = logging.getLogger()
    root_logger.setLevel(level=args.log_level)
    root_logger.addHandler(hdlr=logger_handler)

    # Exit if there's no config file
    """if not cast(Path, args.config).is_file():
        _logger.error(msg="The config file provided is not valid, exiting...")
        return"""

    # Start orcsome3 execution
    _orcsome3.run(config_file=cast(Path, args.config))


if __name__ == "__main__":
    run()
