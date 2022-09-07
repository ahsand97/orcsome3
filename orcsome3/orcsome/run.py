import logging
import os
import signal
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any, Dict, Optional, Union

from ..version import VERSION
from . import ev, update_wm
from .wm import WM

logger: logging.Logger = logging.getLogger(name=__name__)


def execfile(filepath: Path, globales: Optional[Dict[str, Any]] = None) -> None:
    if globales is None:
        globales = globals()
    with filepath.open(mode="r") as fh:
        exec(fh.read() + "\n", globales)


def load_config(wm: WM, config: Path) -> None:
    update_wm(new_wm=wm)
    sys.path.insert(0, str(config.parent))
    try:
        execfile(filepath=config)
    except:
        logger.exception(msg=f"Error on loading {config}")
        sys.exit(1)
    finally:
        sys.path.pop(0)


"""def check_config(config: Path) -> bool:
    wm: TestWM = TestWM() # Mock class
    _update_wm(new_wm=wm)
    sys.path.insert(0, str(config.parent))
    try:
        execfile(filepath=config)
    except:
        logger.exception(msg=f"Config file check failed {config}")
        return False
    finally:
        sys.path.pop(0)

    return True"""


def run() -> None:
    parser: ArgumentParser = ArgumentParser()
    parser.add_argument("--version", action="version", version="%(prog)s " + VERSION)
    parser.add_argument("-l", "--log", dest="log", metavar="FILE", help="Path to log file (log to stdout by default)")
    parser.add_argument("--log-level", metavar="LOGLEVEL", default="INFO", help="log level, default is INFO")

    config_dir: str = os.getenv(key="XDG_CONFIG_HOME", default=str(Path("~/.config").expanduser()))
    default_rcfile: str = str(Path(config_dir).joinpath("orcsome3", "rc.py"))
    parser.add_argument(
        "-c",
        "--config",
        dest="config",
        metavar="FILE",
        default=default_rcfile,
        help="Path to config file (%(default)s)",
    )

    args: Namespace = parser.parse_args()
    handler: Optional[Union[logging.FileHandler, logging.StreamHandler]] = None
    if args.log:
        handler = logging.FileHandler(filename=args.log)
    else:
        handler = logging.StreamHandler()

    root_logger: logging.Logger = logging.getLogger()
    root_logger.setLevel(level=args.log_level)
    handler.setFormatter(fmt=logging.Formatter(fmt="%(asctime)s %(name)s %(levelname)s: %(message)s"))
    root_logger.addHandler(hdlr=handler)

    if not Path(args.config).is_file():
        logger.info(msg="There is no config file available, exiting...")
        return

    loop: ev.Loop = ev.Loop()
    wm: WM = WM(loop=loop)

    def stop(loop_: Any, watcher: Any, events: int) -> None:
        wm.stop(is_exit=True)
        loop.break_()

    signal_watcher = ev.SignalWatcher(callback=stop, signum=signal.SIGINT)
    signal_watcher.start(loop=loop)

    def on_restart() -> None:
        wm.stop()
        logger.info(msg="Restarting...")
        load_config(wm=wm, config=Path(args.config))
        wm.init()
        logger.info(msg="Started successfully")

    wm._restart_handler = on_restart

    load_config(wm=wm, config=Path(args.config))
    wm.init()
    loop.run()
