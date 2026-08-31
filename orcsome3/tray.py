"""StatusNotifierItem (SNI) tray icon plus a dbusmenu on the session bus.

Clicks must not touch X/libev: Quit is SIGTERM, and picking a new config file via `zenity`/
`kdialog` is SIGUSR2 (`run.py` handles both). No menu entry for reload — the config file watcher
already reloads on any change; SIGUSR1 still triggers it for external/scripted use.

dbus-next takes D-Bus signatures from annotations (`"s"`, `"i"`, …). A void method is `-> ""`
(empty signature), not `-> None`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import signal as signal_module
from pathlib import Path
from typing import Any, Optional

from dbus_next.aio.message_bus import MessageBus
from dbus_next.constants import NameFlag, PropertyAccess, RequestNameReply
from dbus_next.service import ServiceInterface, dbus_property, method, signal
from dbus_next.signature import Variant

from orcsome3.common import APPNAME
from orcsome3.instance import display_key
from orcsome3.libs import xlib

_logger: logging.Logger = logging.getLogger(name=__name__)

_ICONS_DIR: Path = Path(__file__).resolve().parent / "icons"
_ICON_SVG: Path = _ICONS_DIR / "hicolor" / "scalable" / "apps" / f"{APPNAME}.svg"
_ERROR_ICON_SVG: Path = _ICONS_DIR / "hicolor" / "scalable" / "apps" / f"{APPNAME}-error.svg"

_ITEM_PATH: str = "/StatusNotifierItem"
_MENU_PATH: str = "/MenuBar"
_ID_QUIT: int = 2
_ID_ERROR: int = 3
_ID_CONFIG: int = 4
_ID_CHANGE_CONFIG: int = 5
_LABELS: dict[int, str] = {_ID_QUIT: "Quit", _ID_CHANGE_CONFIG: "Change config file..."}
_WATCHERS: tuple[tuple[str, str], ...] = (
    ("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher"),
    ("org.freedesktop.StatusNotifierWatcher", "/StatusNotifierWatcher"),
)


def _detect_file_picker() -> Optional[tuple[str, ...]]:
    """A GUI file-picker command, if one happens to be installed. No new dependency either way:
    the "Change config file..." menu row only appears when this finds something to run."""
    zenity: Optional[str] = shutil.which(cmd="zenity")
    if zenity is not None:
        return (zenity, "--file-selection", "--title=Select orcsome3 config file")
    kdialog: Optional[str] = shutil.which(cmd="kdialog")
    if kdialog is not None:
        return (kdialog, "--getopenfilename", str(Path.home()), "*.py|Python files")
    return None


_FILE_PICKER: Optional[tuple[str, ...]] = _detect_file_picker()

# Set once `start_status_notifier` registers on a watcher; read/written from any thread (plain
# assignment is atomic under the GIL). `_last_error` and `_config_path` are meaningful before
# that too: set during the very first config load, before the tray exists, and the item's
# properties are read fresh on registration, so they pick it up without needing a push signal.
_last_error: Optional[str] = None
_config_path: Optional[str] = None
_pending_config_path: Optional[Path] = None
_item: Optional[StatusNotifierItem] = None
_menu: Optional[DBusMenu] = None
_loop: Optional[asyncio.AbstractEventLoop] = None


_PIXMAP_SIZES: tuple[int, ...] = (24, 48)


def _render_pixmaps(svg_path: Path) -> list[list[Any]]:
    """Rasterize `svg_path` (via resvg, already a build dependency — no theme dir, no leftover
    files) at each of `_PIXMAP_SIZES` for the SNI `a(iiay)` icon-pixmap format. Empty if the file
    is missing or fails to parse, so a broken/missing SVG degrades to no icon rather than crashing.
    """
    pixmaps: list[list[Any]] = []
    for size in _PIXMAP_SIZES:
        argb: Optional[bytes] = xlib.render_svg_to_argb(svg_path=svg_path, size=size)
        if argb is not None:
            pixmaps.append([size, size, argb])
    return pixmaps


_ICON_PIXMAP: list[list[Any]] = _render_pixmaps(svg_path=_ICON_SVG)
_ATTENTION_ICON_PIXMAP: list[list[Any]] = _render_pixmaps(svg_path=_ERROR_ICON_SVG)


def _error_label() -> str:
    """Short menu-row text for the last config-load error, truncated for display."""
    text: str = _last_error or ""
    limit: int = 60
    return f"Error: {text[:limit]}{'…' if len(text) > limit else ''}"


def _config_label() -> str:
    """Menu-row text naming the config file currently in use."""
    return f"Config: {_config_path}" if _config_path is not None else "Config: (none loaded)"


def _bus_name(display: str, pid: int) -> str:
    safe: str = "".join(ch if ch.isalnum() else "_" for ch in display)
    return f"org.kde.StatusNotifierItem.{APPNAME}_{safe}_{pid}"


_INFO_ROW_LABELS: dict[int, Any] = {_ID_CONFIG: _config_label, _ID_ERROR: _error_label}


def _props(id_: int) -> dict[str, Variant]:
    if id_ in _INFO_ROW_LABELS:
        return {
            "type": Variant(signature="s", value="standard"),
            "label": Variant(signature="s", value=_INFO_ROW_LABELS[id_]()),
            "enabled": Variant(signature="b", value=False),
            "visible": Variant(signature="b", value=True),
        }
    return {
        "type": Variant(signature="s", value="standard"),
        "label": Variant(signature="s", value=_LABELS[id_]),
        "enabled": Variant(signature="b", value=True),
        "visible": Variant(signature="b", value=True),
    }


def _leaf(id_: int) -> Variant:
    return Variant(signature="(ia{sv}av)", value=[id_, _props(id_=id_), []])


def _layout(parent_id: int) -> list[Any]:
    if parent_id == 0:
        children: list[Variant] = [_leaf(id_=_ID_CONFIG)]
        if _last_error is not None:
            children.append(_leaf(id_=_ID_ERROR))
        if _FILE_PICKER is not None:
            children.append(_leaf(id_=_ID_CHANGE_CONFIG))
        children.append(_leaf(id_=_ID_QUIT))
        return [0, {"children-display": Variant(signature="s", value="submenu")}, children]
    if parent_id in _LABELS or parent_id in _INFO_ROW_LABELS:
        return [parent_id, _props(id_=parent_id), []]
    return [0, {}, []]


async def _pick_new_config() -> None:
    """Run the detected file picker; on a real selection, hand it to `run.py` via SIGUSR2."""
    if _FILE_PICKER is None:
        return
    proc: asyncio.subprocess.Process = await asyncio.create_subprocess_exec(
        *_FILE_PICKER, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
    )
    stdout, _stderr = await proc.communicate()
    if proc.returncode != 0:
        return  # cancelled
    selected: str = stdout.decode().strip()
    if not selected:
        return
    path: Path = Path(selected)
    if not path.is_file():
        _logger.warning(msg=f"File picker returned a non-file path: {path}")
        return
    global _pending_config_path
    _pending_config_path = path
    os.kill(os.getpid(), signal_module.SIGUSR2)


def _clicked(id_: int) -> None:
    """Quit goes through a real signal so `run.py`'s handler does the actual work; clicks must
    not touch X/libev directly from this (asyncio) thread. Reload has no menu entry — the config
    file watcher already reloads automatically on change (SIGUSR1 still works for external use)."""
    if id_ == _ID_QUIT:
        os.kill(os.getpid(), signal_module.SIGTERM)
        return
    if id_ == _ID_CHANGE_CONFIG:
        _ = asyncio.ensure_future(coro_or_future=_pick_new_config())


class StatusNotifierItem(ServiceInterface):
    """org.kde.StatusNotifierItem with a dbusmenu at `Menu`."""

    _display: str
    _menu_path: str

    def __init__(self, display: str, menu_path: str) -> None:
        super().__init__(name="org.kde.StatusNotifierItem")
        self._display = display
        self._menu_path = menu_path

    @dbus_property(access=PropertyAccess.READ)
    def Category(self) -> "s":
        return "ApplicationStatus"

    @dbus_property(access=PropertyAccess.READ)
    def Id(self) -> "s":
        return APPNAME

    @dbus_property(access=PropertyAccess.READ)
    def Title(self) -> "s":
        return APPNAME

    @dbus_property(access=PropertyAccess.READ)
    def Status(self) -> "s":
        return "NeedsAttention" if _last_error is not None else "Active"

    @dbus_property(access=PropertyAccess.READ)
    def WindowId(self) -> "i":
        return 0

    @dbus_property(access=PropertyAccess.READ)
    def IconName(self) -> "s":
        # Pixels go straight over D-Bus (IconPixmap below) — no theme name to register, so
        # nothing gets copied into ~/.local/share/icons and nothing is left behind on uninstall.
        return ""

    @dbus_property(access=PropertyAccess.READ)
    def IconThemePath(self) -> "s":
        return ""

    @dbus_property(access=PropertyAccess.READ)
    def IconPixmap(self) -> "a(iiay)":
        return _ICON_PIXMAP

    @dbus_property(access=PropertyAccess.READ)
    def OverlayIconName(self) -> "s":
        return ""

    @dbus_property(access=PropertyAccess.READ)
    def OverlayIconPixmap(self) -> "a(iiay)":
        return []

    @dbus_property(access=PropertyAccess.READ)
    def AttentionIconName(self) -> "s":
        return ""

    @dbus_property(access=PropertyAccess.READ)
    def AttentionIconPixmap(self) -> "a(iiay)":
        return _ATTENTION_ICON_PIXMAP if _last_error is not None else []

    @signal()
    def NewIcon(self) -> "":
        pass

    @signal()
    def NewAttentionIcon(self) -> "":
        pass

    @signal()
    def NewToolTip(self) -> "":
        pass

    @signal()
    def NewStatus(self, newStatus: str) -> "s":
        return newStatus

    @dbus_property(access=PropertyAccess.READ)
    def ItemIsMenu(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def Menu(self) -> "o":
        return self._menu_path

    @dbus_property(access=PropertyAccess.READ)
    def ToolTip(self) -> "(sa(iiay)ss)":
        description: str = _last_error if _last_error is not None else f"DISPLAY={self._display}"
        return ["", [], APPNAME, description]

    @method()
    def ContextMenu(self, x: "i", y: "i") -> "":
        _logger.debug(msg=f"ContextMenu x={x} y={y}")

    @method()
    def Activate(self, x: "i", y: "i") -> "":
        _logger.debug(msg=f"Activate x={x} y={y}")

    @method()
    def SecondaryActivate(self, x: "i", y: "i") -> "":
        _logger.debug(msg=f"SecondaryActivate x={x} y={y}")

    @method()
    def Scroll(self, delta: "i", orientation: "s") -> "":
        _logger.debug(msg=f"Scroll delta={delta} orientation={orientation}")


class DBusMenu(ServiceInterface):
    """com.canonical.dbusmenu: Quit, an always-visible config-path row, and (while `_last_error`
    is set) an error row."""

    _about_to_show: bool
    _revision: int

    def __init__(self) -> None:
        super().__init__(name="com.canonical.dbusmenu")
        self._about_to_show = False
        self._revision = 1

    @dbus_property(access=PropertyAccess.READ)
    def Version(self) -> "u":
        return 3

    @dbus_property(access=PropertyAccess.READ)
    def TextDirection(self) -> "s":
        return "ltr"

    @dbus_property(access=PropertyAccess.READ)
    def Status(self) -> "s":
        return "normal"

    @dbus_property(access=PropertyAccess.READ)
    def IconThemePath(self) -> "as":
        return []

    @method()
    def GetLayout(self, parentId: "i", recursionDepth: "i", propertyNames: "as") -> "u(ia{sv}av)":
        _logger.debug(msg=f"GetLayout parentId={parentId} about_to_show={self._about_to_show}")
        _ = (recursionDepth, propertyNames)
        return [self._revision, _layout(parent_id=parentId)]

    @method()
    def GetGroupProperties(self, ids: "ai", propertyNames: "as") -> "a(ia{sv})":
        _ = propertyNames
        known: list[int] = [_ID_CONFIG, *_LABELS] + ([_ID_ERROR] if _last_error is not None else [])
        wanted: list[int] = ids if ids else known
        return [[i, _props(id_=i)] for i in wanted if i in known]

    @method()
    def GetProperty(self, id: "i", name: "s") -> "v":
        if name != "label":
            return Variant(signature="s", value="")
        if id in _LABELS:
            return Variant(signature="s", value=_LABELS[id])
        if id == _ID_CONFIG:
            return Variant(signature="s", value=_config_label())
        if id == _ID_ERROR and _last_error is not None:
            return Variant(signature="s", value=_error_label())
        return Variant(signature="s", value="")

    @method()
    def Event(self, id: "i", eventId: "s", data: "v", timestamp: "u") -> "":
        # "clicked" is authoritative on its own per the dbusmenu spec; AboutToShow is a lazy-
        # populate hook, not a click gate. Gating on it here dropped real clicks: some hosts
        # don't reliably leave `_about_to_show` True by the time the click event arrives.
        _logger.debug(msg=f"Event id={id} eventId={eventId!r} labels={id in _LABELS}")
        _ = (data, timestamp)
        if eventId == "clicked" and id in _LABELS:
            _clicked(id_=id)

    @method()
    def AboutToShow(self, id: "i") -> "b":
        _logger.debug(msg=f"AboutToShow id={id}")
        self._about_to_show = True
        return False

    @signal()
    def LayoutUpdated(self, revision: int, parentId: int) -> "ui":
        return [revision, parentId]

    def layout_changed(self) -> None:
        """Bump the revision and tell the host to call `GetLayout` again (the error row appeared/disappeared)."""
        self._revision += 1
        self.LayoutUpdated(revision=self._revision, parentId=0)


def set_config_path(path: Path) -> None:
    """Record which config file is active, for the menu's "Config: ..." row. Safe from any thread."""
    global _config_path
    _config_path = str(path)
    if _loop is None:
        return
    _ = _loop.call_soon_threadsafe(callback=_refresh_config_path)


def _refresh_config_path() -> None:
    if _menu is not None:
        _menu.layout_changed()


def take_pending_config_path() -> Optional[Path]:
    """Pop the config path chosen via the tray's file picker, if any.

    Call from `run.py`'s SIGUSR2 handler (main thread) — that signal is what `_pick_new_config`
    sends after a real selection, so this is only ever non-`None` right when it fires.
    """
    global _pending_config_path
    path: Optional[Path] = _pending_config_path
    _pending_config_path = None
    return path


def report_error(message: Optional[str]) -> None:
    """Record the last config-load error (or clear it with `None`) and refresh the tray to match.

    Safe to call before the tray exists (e.g. the very first config load, before `NotificationBus`
    has started — the item's properties are read fresh once it does register, so they already
    reflect this) or from any thread: the D-Bus signal emission itself is marshalled onto the
    tray's own asyncio loop.
    """
    global _last_error
    _last_error = message
    if _loop is None:
        return
    _ = _loop.call_soon_threadsafe(callback=_refresh_error_state)


def _refresh_error_state() -> None:
    if _item is not None:
        _item.NewStatus(newStatus="NeedsAttention" if _last_error is not None else "Active")
        _item.NewAttentionIcon()
        _item.NewToolTip()
    if _menu is not None:
        _menu.layout_changed()


async def start_status_notifier(bus: MessageBus) -> None:
    """Export SNI + dbusmenu and register with a StatusNotifierWatcher if one is on this session bus."""
    global _item, _menu, _loop
    display: str = display_key()
    well_known: str = _bus_name(display=display, pid=os.getpid())
    item: StatusNotifierItem = StatusNotifierItem(display=display, menu_path=_MENU_PATH)
    menu: DBusMenu = DBusMenu()
    bus.export(path=_ITEM_PATH, interface=item)
    bus.export(path=_MENU_PATH, interface=menu)
    _logger.debug(msg=f"icon pixmaps: normal={len(_ICON_PIXMAP)} attention={len(_ATTENTION_ICON_PIXMAP)}")
    reply: RequestNameReply = await bus.request_name(name=well_known, flags=NameFlag.DO_NOT_QUEUE)
    unique: Optional[str] = bus.unique_name
    service: str = (
        well_known
        if reply in (RequestNameReply.PRIMARY_OWNER, RequestNameReply.ALREADY_OWNER)
        else unique or well_known
    )
    for watcher_name, watcher_path in _WATCHERS:
        try:
            proxy: Any = bus.get_proxy_object(
                bus_name=watcher_name,
                path=watcher_path,
                introspection=await bus.introspect(bus_name=watcher_name, path=watcher_path),
            )
            iface: Any = proxy.get_interface(name=watcher_name)
            await iface.call_register_status_notifier_item(service)
            item.NewIcon()
            _item = item
            _menu = menu
            _loop = asyncio.get_running_loop()
            _logger.info(msg=f"StatusNotifierItem registered on {watcher_name} ({service})")
            return
        except Exception:
            continue
    _logger.info(msg="No StatusNotifierWatcher on this session bus; tray icon skipped")
