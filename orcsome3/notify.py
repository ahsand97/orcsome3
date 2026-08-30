from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import Future
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, Union, cast, override

from dbus_next.aio.message_bus import MessageBus
from dbus_next.aio.proxy_object import ProxyInterface, ProxyObject
from dbus_next.signature import Variant

from orcsome3.common import APPNAME
from orcsome3.utils import Singleton

# Globals
_logger: logging.Logger = logging.getLogger(name=__name__)
_visible_notifications: dict[int, Notification] = {}


class CONSTANTS(str, Enum):
    """Constants"""

    NOTIFICATIONS_BUS_NAME = "org.freedesktop.Notifications"
    NOTIFICATIONS_OBJECT_PATH = "/org/freedesktop/Notifications"
    NOTIFICATIONS_INTERFACE = "org.freedesktop.Notifications"


class ServerCapabilities(str, Enum):
    """
    Enum representation of server capabilities.

    - "action-icons": Supports using icons instead of text for displaying actions. Using icons for actions
                      must be enabled on a per-notification basis using the "action-icons" hint.
    - "actions": The server will provide the specified actions to the user. Even if this cap is missing,
                 actions may still be specified by the client, however the server is free to ignore them.
    - "body": Supports body text.
              Some implementations may only show the summary (for instance, onscreen displays, marquee/scrollers)
    - "body-hyperlinks": The server supports hyperlinks in the notifications.
    - "body-images": The server supports images in the notifications.
    - "body-markup": Supports markup in the body text. If marked up text is sent to a server that does not give this cap,
                     the markup will show through as regular text so must be stripped clientside.
    - "icon-multi": The server will render an animation of all the frames in a given image array.
                    The client may still specify multiple frames even if this cap and/or "icon-static" is missing,
                    however the server is free to ignore them and use only the primary frame.
    - "icon-static": Supports display of exactly 1 frame of any given image array. This value is mutually exclusive
                     with "icon-multi", it is a protocol error for the server to specify both.
    - "persistence": The server supports persistence of notifications. Notifications will be retained until they are
                    acknowledged or removed by the user or recalled by the sender. The presence of this
                    capability allows clients to depend on the server to ensure a notification is seen and eliminate
                    the need for the client to display a reminding function (such as a status icon) of its own.
    - "sound": The server supports sounds on notifications. If returned, the server must support the
              "sound-file" and "suppress-sound" hints.
    """

    ACTION_ICONS = "action-icons"
    ACTIONS = "actions"
    BODY = "body"
    BODY_HYPERLINKS = "body-hyperlinks"
    BODY_IMAGES = "body-images"
    BODY_MARKUP = "body-markup"
    ICON_MULTI = "icon-multi"
    ICON_STATIC = "icon-static"
    PERSISTENCE = "persistence"
    SOUND = "sound"


class NotificationBus(threading.Thread, metaclass=Singleton["NotificationBus"]):
    """Class wrapper mainly to call methods from Desktop Notifications Specification D-Bus Protocol (`org.freedesktop.Notifications`)."""

    session_bus: Optional[MessageBus] = None
    notification_proxy: Optional[ProxyObject] = None
    notification_interface: Optional[ProxyInterface] = None
    can_show_notifications: bool = False

    class ReasonNotificationClosed(int, Enum):
        """
        Enum representing the reason why a notification was closed.

        - 1 - The notification expired.
        - 2 - The notification was dismissed by the user.
        - 3 - The notification was closed by a call to CloseNotification.
        - 4 - Undefined/reserved reasons.
        """

        NOTIFICATION_EXPIRED = 1
        NOTIFICATION_DISMISSED = 2
        NOTIFICACION_CLOSED = 3
        UNDEFINED = 4

    def __init__(self) -> None:
        try:
            super().__init__(daemon=True)
            self._event_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop=self._event_loop)
            self._event_loop.run_until_complete(future=NotificationBus.initialize_notification_bus())
            Notification.notification_bus = self  # Share state for all Notification objects
            self.start()
        except Exception as e:
            _logger.error(msg="An error occurred starting dbus. Notifications can't be shown.")
            _logger.error(msg=e)

    @override
    def run(self) -> None:
        """Start thread's activity"""
        if self.session_bus is None:
            return

        # Connect to signals
        self.connect_to_signal(signal_name="NotificationClosed", callback=self._on_notification_closed)
        self.connect_to_signal(signal_name="ActionInvoked", callback=self._on_action_invoked)
        self._event_loop.run_forever()

        # Loop forever until disconnection from the bus
        self._event_loop.run_until_complete(future=self.session_bus.wait_for_disconnect())

    @classmethod
    async def initialize_notification_bus(cls) -> None:
        cls.session_bus = await MessageBus().connect()
        cls.notification_proxy = cls.session_bus.get_proxy_object(
            bus_name=CONSTANTS.NOTIFICATIONS_BUS_NAME.value,
            path=CONSTANTS.NOTIFICATIONS_OBJECT_PATH,
            introspection=await cls.session_bus.introspect(
                bus_name=CONSTANTS.NOTIFICATIONS_BUS_NAME, path=CONSTANTS.NOTIFICATIONS_OBJECT_PATH
            ),
        )
        cls.notification_interface = cls.notification_proxy.get_interface(name=CONSTANTS.NOTIFICATIONS_INTERFACE)
        cls.can_show_notifications = True

    @classmethod
    def stop(cls) -> None:
        if cls.session_bus is not None:
            cls.session_bus.disconnect()

    @classmethod
    def restart(cls) -> None:
        cls.delete_instance(instance=NotificationBus)
        _ = super().__new__(cls=cls)

    def run_method(self, method_name: str, params: Optional[list[Any]] = None, wait_for_result: bool = True) -> Any:
        """
        Run method from dbus interface.

        Params:
        - `method_name`: Method name
        - `params`: Params to pass to method. Defaults to `None`
        - `wait_for_result`: Wether to return the result of `method_name` or an instance of `concurrent.futures.Future`.
                             Defaults to `True`
        """

        async def run_method_() -> Any:
            """Run method from dbus interface and wait for result"""
            try:
                result: Any = None
                if params is None:
                    result = await getattr(self.notification_interface, f"call_{snake_case_method_name}")()
                else:
                    result = await getattr(self.notification_interface, f"call_{snake_case_method_name}")(*params)
                return result
            except Exception as e:
                _logger.error(msg=f"An exception occured running method '{method_name}' from dbus interface: {e}")
                if f"The name {CONSTANTS.NOTIFICATIONS_BUS_NAME} was not provided by any .service files" in str(e):
                    if len(_visible_notifications):
                        _visible_notifications.clear()

        if not hasattr(self, "interface"):
            return

        snake_case_method_name: str = getattr(self.notification_interface, "_to_snake_case")(member=method_name)
        future: Future[Any] = asyncio.run_coroutine_threadsafe(coro=run_method_(), loop=self._event_loop)
        return future.result() if wait_for_result else future

    def connect_to_signal(self, signal_name: str, callback: Callable[..., Any]) -> None:
        """
        Connect to signal.

        Params:
        - `signal_name`: Name of signal to connect
        - `callback`: Callback to run
        """
        getattr(
            self.notification_interface, f"on_{getattr(self.notification_interface, '_to_snake_case')(signal_name)}"
        )(callback)

    def get_server_capabilities(self) -> list[ServerCapabilities]:
        """Wrapper for ` org.freedesktop.Notifications.GetCapabilities`"""
        capabilities: Optional[list[str]] = self.run_method(method_name="GetCapabilities")
        if capabilities is None or not len(capabilities):
            return []
        return [ServerCapabilities(cap) for cap in capabilities]

    def notify(
        self,
        app_name: str,
        replaces_id: int,
        app_icon: str,
        summary: str,
        body: str,
        actions: list[str],
        hints: dict[str, Any],
        expire_timeout: int,
    ) -> int:
        """Wrapper for `org.freedesktop.Notifications.Notify`"""
        try:
            return int(
                self.run_method(
                    method_name="Notify",
                    params=[app_name, replaces_id, app_icon, summary, body, actions, hints, expire_timeout],
                )
            )
        except:
            return -1

    def close(self, notification_id: int, wait: bool = False) -> None:
        """Wrapper for `org.freedesktop.Notifications.CloseNotification`"""
        self.run_method(method_name="CloseNotification", params=[notification_id], wait_for_result=wait)

    def _on_notification_closed(self, notification_id: int, __reason__: int) -> None:
        """Callback of signal `org.freedesktop.Notifications.NotificationClosed`"""
        try:
            notification: Notification = _visible_notifications[notification_id]
            if notification.on_close is not None:
                notification.on_close()
            del _visible_notifications[notification_id]
        except:
            pass

    def _on_action_invoked(self, notification_id: int, action_key: str) -> None:
        """Callback of signal `org.freedesktop.Notifications.ActionInvoked`"""
        try:
            notification: Notification = _visible_notifications[notification_id]
            for action in notification.actions:
                if action.id == action_key:
                    if action.callback is not None:
                        action.callback()
                    break
        except:
            pass


class Notification:
    """Class representation of a notification"""

    notification_bus: Optional[NotificationBus] = None

    class Hints:
        """Class representing hints for a notification."""

        class Categories(str, Enum):
            """
            Categories

            Notifications can optionally have a type indicator.
            Although neither client or nor server must support this, some may choose to. Those servers implementing
            categories may use them to intelligently display the notification in a certain way,
            or group notifications of similar types.

            - "device": A generic device-related notification that doesn't fit into any other category.
            - "device.added": A device, such as a USB device, was added to the system.
            - "device.error": A device had some kind of error.
            - "device.removed": A device, such as a USB device, was removed from the system.
            - "email": A generic e-mail-related notification that doesn't fit into any other category.
            - "email.arrived": A new e-mail notification.
            - "email.bounced": A notification stating that an e-mail has bounced.
            - "im": A generic instant message-related notification that doesn't fit into any other category.
            - "im.error": An instant message error notification.
            - "im.received": A received instant message notification.
            - "network": A generic network notification that doesn't fit into any other category.
            - "network.connected": A network connection notification, such as successful sign-on to a network service.
                                This should not be confused with device.added for new network devices.
            - "network.disconnected": A network disconnected notification.
                                This should not be confused with device.removed for disconnected network devices.
            - "network.error": A network-related or connection-related error.
            - "presence": A generic presence change notification that doesn't fit into any other category,
                        such as going away or idle.
            - "presence.offline": An offline presence change notification.
            - "presence.online": An online presence change notification.
            - "transfer": A generic file transfer or download notification that doesn't fit into any other category.
            - "transfer.complete": A file transfer or download complete notification.
            - "transfer.error": A file transfer or download error.
            """

            # device
            DEVICE = "device"
            DEVICE_ADDED = "device.added"
            DEVICE_ERROR = "device.error"
            DEVICE_REMOVED = "device.removed"

            # email
            EMAIL = "email"
            EMAIL_ARRIVED = "email.arrived"
            EMAIL_BOUNCED = "email.bounced"

            # im
            IM = "im"
            IM_ERROR = "im.error"
            IM_RECEIVED = "im.received"

            # network
            NETWORK = "network"
            NETWORK_CONNECTED = "network.connected"
            NETWORK_DISCONNECTED = "network.disconnected"
            NETWORK_ERROR = "network.error"

            # presence
            PRESENCE = "presence"
            PRESENCE_OFFLINE = "presence.offline"
            PRESENCE_ONLINE = "presence.online"

            # transfer
            TRANSFER = "transfer"
            TRANSFER_COMPLETE = "transfer.complete"
            TRANSFER_ERROR = "transfer.error"

        class Urgency(int, Enum):
            """
            Urgency levels.

            - 0: Low
            - 1: Normal
            - 2: Critical
            """

            LOW = 0
            NORMAL = 1
            CRITICAL = 2

        def __init__(
            self,
            action_icons: Optional[bool] = None,
            category: Optional[Categories] = None,
            desktop_entry: Optional[str] = None,
            resident: Optional[bool] = None,
            sound_file: Optional[Union[str, Path]] = None,
            sound_name: Optional[str] = None,
            suppress_sound: Optional[bool] = None,
            transient: Optional[bool] = None,
            x: Optional[int] = None,
            y: Optional[int] = None,
            urgency: Optional[Urgency] = None,
        ) -> None:
            """
            Params:
            - `action-icons`: When set, a server that has the "action-icons" capability will attempt to interpret any
                            action identifier as a named icon. The icon name should be compliant with the
                            Freedesktop.org Icon Naming Specification.
            - `category`: The type of notification this is. See enum `orcsome3.notify.Notification.Hints.Categories`.
            - `desktop-entry`: This specifies the name of the desktop filename representing the calling program.
                            This should be the same as the prefix used for the application's .desktop file.
            - `image-path`: Alternative way to define the notification image.
            - `resident`: When set the server will not automatically remove the notification when an
                        action has been invoked. The notification will remain resident in the server until it
                        is explicitly removed by the user or by the sender.
                        This hint is likely only useful when the server has the "persistence" capability.
            - `sound-file`: The path to a sound file to play when the notification pops up.
            - `sound-name`: A themeable named sound from the freedesktop.org sound naming specification to play
                            when the notification pops up. Similar to icon-name, only for sounds.
                            An example would be "message-new-instant".
            - `suppress-sound`: Causes the server to suppress playing any sounds, if it has that ability.
                                This is usually set when the client itself is going to play its own sound.
            - `transient`: When set the server will treat the notification as transient and by-pass the server's
                        persistence capability, if it should exist.
            - `x`: Specifies the X location on the screen that the notification should point to.
                The `y` hint must also be specified.
            - `y`: Specifies the Y location on the screen that the notification should point to.
                The `x` hint must also be specified.
            - `urgency`: Urgency Level. See enum `orcsome3.notify.Notifications.Hints.Urgency`
            """
            self.action_icons: Optional[bool] = action_icons
            self.category: Optional[Notification.Hints.Categories] = category
            self.desktop_entry: Optional[str] = desktop_entry
            self.resident: Optional[bool] = resident
            self.sound_file: Optional[Union[str, Path]] = sound_file
            self.sound_name: Optional[str] = sound_name
            self.suppress_sound: Optional[bool] = suppress_sound
            self.transient: Optional[bool] = transient
            self.x: Optional[int] = x
            self.y: Optional[int] = y
            self.urgency: Optional[Notification.Hints.Urgency] = urgency

        def get_dict(self) -> dict[str, Variant]:
            final_dict: dict[str, Variant] = {}
            attrs: list[str] = [
                "action_icons",
                "category",
                "desktop_entry",
                "resident",
                "sound_file",
                "sound_name",
                "suppress_sound",
                "transient",
                "x",
                "y",
                "urgency",
            ]
            for attr in attrs:
                value = getattr(self, attr)
                if value is not None:
                    if isinstance(value, Enum):
                        value = value.value
                    elif isinstance(value, Path):
                        value = str(value)
                    final_dict[attr.replace("_", "-")] = Variant(signature=type(value).__name__[0], value=value)
            return final_dict

    class Action:
        """Class representing a notification action"""

        def __init__(self, visible_name: str, callback: Optional[Callable[[], None]]) -> None:
            """
            Create Action for a Notification

            Params:
            - `visible_name`: Localized string displayed to the user
            - `callback`: Optional callback to run when action activated. Defaults to `None`
            """
            self.id: str = str(id(self))
            self.visible_name: str = visible_name
            self.callback: Optional[Callable[[], None]] = callback

    def __init__(
        self,
        summary: str,
        body: str,
        app_name: Optional[str] = None,
        replaces_id: int = 0,
        app_icon: Optional[Union[str, Path]] = None,
        actions: Optional[list[Action]] = None,
        hints: Optional[Hints] = None,
        expire_timeout: int = -1,
        on_close: Optional[Callable[[], None]] = None,
        show: bool = False,
    ) -> None:
        """
        Create a Notification.

        Params:
        - `summary`: The summary text briefly describing the notification.
        - `body`: The optional detailed body text. Can be empty.
                The body markup is XML-based, and consists of a small subset of HTML along with a few additional tags.
                Supported tags:
                - <b> ... </b> Bold
                - <i> ... </i> Italic
                - <u> ... </u> Underline
                - <a href="..."> ... </a> Hyperlink
                - <img src="..." alt="..."/> Image\n
                If the server doesn't have the "body-markup" capability then `body` should only contain text.
        - `app_name`: The optional name of the application sending the notification.
                    Defaults to `orcsome3` if blank, empty or `None`.
        - `replaces_id`: The optional notification ID that this notification replaces. The server must atomically replace
                        the given notification with this one. This allows clients to effectively modify the notification
                        while it's active. A value of value of `0` means that this notification won't replace any
                        existing notifications.
        - `app_icon`: The optional program icon of the calling application.
        - `actions`: List of actions. See class `orcsome3.notify.Notification.Action`.
        - `hints`: Hints for the notification. See class `orcsome3.notify.Notification.Hints`.
        - `expire_timeout`: The timeout time in milliseconds since the display of the notification at which the
                            notification should automatically close.
                            If `-1`, the notification's expiration time is dependent on the notification server's settings,
                            and may vary for the type of notification. If `0`, never expire.
        - `on_close`: Optional function to run when closing the notification. Defaults to `None`.
        - `show`: Wether to show or not the notification immediately. See method `show()` for more details. Defaults to `False`.
        """
        self.id: int = -1
        self.summary: str = summary.lstrip("-")
        self.body: str = body
        self.app_name: str = app_name if app_name is not None and len(app_name.strip()) else APPNAME
        self.replaces_id: int = replaces_id

        self._app_icon: Optional[Union[str, Path]] = app_icon
        self._actions: list[Notification.Action] = actions if actions is not None else []
        self._hints: Optional[Notification.Hints] = hints
        self._expire_timeout: int = expire_timeout
        self.on_close: Optional[Callable[[], None]] = on_close
        if show:
            self.show()

    @property
    def actions(self) -> list[Notification.Action]:
        return self._actions

    @property
    def app_icon(self) -> Union[str, Path]:
        return cast(Union[str, Path], self._app_icon)

    @property
    def hints(self) -> Notification.Hints:
        return cast(Notification.Hints, self._hints)

    def __getattr__(self, __name: str) -> Any:
        if __name == "notification_bus":
            try:
                notification_bus: Optional[NotificationBus] = Notification.__dict__[__name]
                if notification_bus is None:
                    NotificationBus.restart()
                    self.notification_bus = NotificationBus()
            except KeyError:
                pass
        return super().__getattribute__(__name)

    def show(self) -> None:
        """
        Show notification.

        If a visible notification already have the same `summary`, `body`, and `app_name` of `self` (the notification
        that is requesting to show), then the visible notification gets closed and replaced with `self` (the new notification).
        """
        if not (self.notification_bus is not None and self.notification_bus.can_show_notifications):
            return

        props: list[str] = ["summary", "body", "app_name"]
        for visible_notification in _visible_notifications.values():
            if all(getattr(visible_notification, prop) == getattr(self, prop) for prop in props):
                self.replaces_id = visible_notification.id
                cb_close_visible_notification: Optional[Callable[[], None]] = visible_notification.on_close
                visible_notification.on_close = None
                self.notification_bus.close(notification_id=visible_notification.id, wait=True)
                visible_notification.on_close = cb_close_visible_notification
                break

        param_app_icon: str = ""
        if self._app_icon is not None:
            if isinstance(self._app_icon, str):
                self._app_icon = Path(self._app_icon)
            if self._app_icon.is_file():
                param_app_icon = str(self._app_icon)

        param_actions: list[str] = []
        for action in self._actions:
            param_actions.append(action.id)
            param_actions.append(action.visible_name)

        self.id = self.notification_bus.notify(
            app_name=self.app_name,
            replaces_id=self.replaces_id if not (self.replaces_id == 0 and self.id != -1) else self.id,
            app_icon=param_app_icon,
            summary=self.summary,
            body=self.body,
            actions=param_actions,
            hints=self.hints.get_dict() if self._hints is not None else {},
            expire_timeout=self._expire_timeout,
        )
        if self.id != -1:
            _visible_notifications[self.id] = self

    def close(self) -> None:
        """Close notification"""
        if not (self.notification_bus is not None and self.notification_bus.can_show_notifications):
            return
        if self.id != -1:
            self.notification_bus.close(notification_id=self.id)
