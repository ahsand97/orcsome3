import logging
from . import VERSION as VERSION, ev as ev, update_wm as update_wm
from .wm import WM as WM
from pathlib import Path
from typing import Any, Dict, Optional

logger: logging.Logger

def execfile(filepath: Path, globales: Optional[Dict[str, Any]] = ...) -> None: ...
def load_config(wm: WM, config: Path) -> None: ...
def run() -> None: ...
