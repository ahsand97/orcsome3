"""StatusNotifierItem (SNI) tray icon plus a dbusmenu on the session bus.

Clicks must not touch X/libev: Reload is SIGUSR1, Quit is SIGTERM (`run.py` handles both).

dbus-next takes D-Bus signatures from annotations (`"s"`, `"i"`, …). A void method is `-> ""`
(empty signature), not `-> None`.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from signal import SIGTERM, SIGUSR1
from typing import Any, Optional

from dbus_next.aio.message_bus import MessageBus
from dbus_next.constants import NameFlag, PropertyAccess, RequestNameReply
from dbus_next.service import ServiceInterface, dbus_property, method
from dbus_next.signature import Variant

from orcsome3.common import APPNAME
from orcsome3.instance import display_key

_logger: logging.Logger = logging.getLogger(name=__name__)

_ICONS_DIR: Path = Path(__file__).resolve().parent / "icons"
_ICON_SVG: Path = _ICONS_DIR / "hicolor" / "scalable" / "apps" / f"{APPNAME}.svg"

_ITEM_PATH: str = "/StatusNotifierItem"
_MENU_PATH: str = "/MenuBar"
_ID_RELOAD: int = 1
_ID_QUIT: int = 2
_LABELS: dict[int, str] = {_ID_RELOAD: "Reload config", _ID_QUIT: "Quit"}
_WATCHERS: tuple[tuple[str, str], ...] = (
    ("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher"),
    ("org.freedesktop.StatusNotifierWatcher", "/StatusNotifierWatcher"),
)


def _bus_name(display: str, pid: int) -> str:
    safe: str = "".join(ch if ch.isalnum() else "_" for ch in display)
    return f"org.kde.StatusNotifierItem.{APPNAME}_{safe}_{pid}"


def _props(id_: int) -> dict[str, Variant]:
    return {"label": Variant(signature="s", value=_LABELS[id_]), "enabled": Variant(signature="b", value=True)}


def _leaf(id_: int) -> Variant:
    return Variant(signature="(ia{sv}av)", value=[id_, _props(id_=id_), []])


def _layout(parent_id: int) -> list[Any]:
    if parent_id == 0:
        return [
            0,
            {"children-display": Variant(signature="s", value="submenu")},
            [_leaf(id_=_ID_RELOAD), _leaf(id_=_ID_QUIT)],
        ]
    if parent_id in _LABELS:
        return [parent_id, _props(id_=parent_id), []]
    return [0, {}, []]


def _clicked(id_: int) -> None:
    if id_ == _ID_RELOAD:
        os.kill(os.getpid(), SIGUSR1)
    elif id_ == _ID_QUIT:
        os.kill(os.getpid(), SIGTERM)


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
        return "Active"

    @dbus_property(access=PropertyAccess.READ)
    def WindowId(self) -> "i":
        return 0

    @dbus_property(access=PropertyAccess.READ)
    def IconName(self) -> "s":
        return str(_ICON_SVG) if _ICON_SVG.is_file() else "preferences-desktop-display"

    @dbus_property(access=PropertyAccess.READ)
    def IconThemePath(self) -> "s":
        return str(_ICONS_DIR)

    @dbus_property(access=PropertyAccess.READ)
    def OverlayIconName(self) -> "s":
        return ""

    @dbus_property(access=PropertyAccess.READ)
    def AttentionIconName(self) -> "s":
        return ""

    @dbus_property(access=PropertyAccess.READ)
    def ItemIsMenu(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def Menu(self) -> "o":
        return self._menu_path

    @dbus_property(access=PropertyAccess.READ)
    def ToolTip(self) -> "(sa(iiay)ss)":
        return ["", [], APPNAME, f"DISPLAY={self._display}"]

    @method()
    def ContextMenu(self, x: "i", y: "i") -> "":
        _ = (x, y)

    @method()
    def Activate(self, x: "i", y: "i") -> "":
        _ = (x, y)

    @method()
    def SecondaryActivate(self, x: "i", y: "i") -> "":
        _ = (x, y)

    @method()
    def Scroll(self, delta: "i", orientation: "s") -> "":
        _ = (delta, orientation)


class DBusMenu(ServiceInterface):
    """com.canonical.dbusmenu: Reload config and Quit."""

    def __init__(self) -> None:
        super().__init__(name="com.canonical.dbusmenu")

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
        _ = (recursionDepth, propertyNames)
        return [1, _layout(parent_id=parentId)]

    @method()
    def GetGroupProperties(self, ids: "ai", propertyNames: "as") -> "a(ia{sv})":
        _ = propertyNames
        wanted: list[int] = ids if ids else list(_LABELS)
        return [[i, _props(id_=i)] for i in wanted if i in _LABELS]

    @method()
    def GetProperty(self, id: "i", name: "s") -> "v":
        if name == "label" and id in _LABELS:
            return Variant(signature="s", value=_LABELS[id])
        return Variant(signature="s", value="")

    @method()
    def Event(self, id: "i", eventId: "s", data: "v", timestamp: "u") -> "":
        _ = (data, timestamp)
        if eventId == "clicked":
            _clicked(id_=id)

    @method()
    def AboutToShow(self, id: "i") -> "b":
        _ = id
        return False


async def start_status_notifier(bus: MessageBus) -> None:
    """Export SNI + dbusmenu and register with a StatusNotifierWatcher if one is on this session bus."""
    display: str = display_key()
    well_known: str = _bus_name(display=display, pid=os.getpid())
    bus.export(path=_ITEM_PATH, interface=StatusNotifierItem(display=display, menu_path=_MENU_PATH))
    bus.export(path=_MENU_PATH, interface=DBusMenu())
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
            _logger.info(msg=f"StatusNotifierItem registered on {watcher_name} ({service})")
            return
        except Exception:
            continue
    _logger.info(msg="No StatusNotifierWatcher on this session bus; tray icon skipped")
