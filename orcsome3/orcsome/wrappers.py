from __future__ import annotations

from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import List, Optional, Tuple, Union, cast

from . import utils, wm, xlib


class WindowTree:
    def __init__(self, window: Window, root: Window, parent: Window, children: List[Window]) -> None:
        self.window: Window = window
        self.root: Window = root
        self.parent: Window = parent
        self.children: List[Window] = children


class XWindowAttributes:
    class MapState(Enum):
        IsUnmapped = int(xlib.lib.IsUnmapped)
        IsUnviewable = int(xlib.lib.IsUnviewable)
        IsViewable = int(xlib.lib.IsViewable)

    def __init__(self, attributes: xlib.XWindowAttributes) -> None:
        self.x: int = attributes.x  # location of window
        self.y: int = attributes.y  # location of window
        self.width: int = attributes.width  # width of window
        self.height: int = attributes.width  # height of window
        self.border_width: int = attributes.border_width  # border width of window
        self.depth: int = attributes.depth  # depth of window
        self.root: xlib.Window = attributes.root  # root of screen containing window
        self.override_redirect: bool = bool(attributes.override_redirect)  # boolean value for override-redirect
        self.map_state: XWindowAttributes.MapState = self.MapState(attributes.map_state)


class XScreenSaverInfo:
    class State(Enum):
        Off = int(xlib.lib.ScreenSaverOff)
        On = int(xlib.lib.ScreenSaverOn)
        Disabled = int(xlib.lib.ScreenSaverDisabled)

    class Kind(Enum):
        Blanked = int(xlib.lib.ScreenSaverBlanked)
        Internal = int(xlib.lib.ScreenSaverInternal)
        External = int(xlib.lib.ScreenSaverExternal)

    def __init__(self, screensaverinfo: xlib.ScreenSaverInfo) -> None:
        self.window: xlib.Window = screensaverinfo.window  # screen saver window
        self.state: XScreenSaverInfo.State = self.State(screensaverinfo.state)  # ScreenSaver{Off,On,Disabled}
        self.kind: XScreenSaverInfo.Kind = self.Kind(screensaverinfo.kind)  # ScreenSaver{Blanked,Internal,External}
        self.til_or_since: int = screensaverinfo.til_or_since  # time til or since screen saver (milliseconds)
        self.idle: int = screensaverinfo.idle  # total time since last user input (milliseconds)
        self.event_mask: int = screensaverinfo.eventMask  # currently selected events for this client


class Window(int):
    wm: wm.WM

    @cached_property
    def desktop(self) -> Optional[int]:
        """Return window desktop.

        Result is:

        * number from 0 to desktop_count - 1
        * -1 if window placed on all desktops
        * None if window does not have desktop property

        """
        result = self.get_property(property="_NET_WM_DESKTOP", type="CARDINAL")
        if not result:
            return None
        desktop = cast(List[int], result)[0]
        if desktop == 0xFFFFFFF or desktop == 0xFFFFFFFFFFFFFFFF:
            desktop = -1
        return desktop

    @cached_property
    def role(self) -> Optional[str]:
        """Return WM_WINDOW_ROLE property"""
        result = self.get_property(property="WM_WINDOW_ROLE", type="STRING")
        if not result or not len(result):
            return None
        return str(result[0])

    @cached_property
    def cls(self) -> Optional[str]:
        """Return second part from WM_CLASS property"""
        name, _class = self.get_name_and_class()
        if name:
            setattr(self, "name", name)
        return _class if _class else None

    @cached_property
    def name(self) -> Optional[str]:
        """Return first part from WM_CLASS property"""
        name, _class = self.get_name_and_class()
        if _class:
            setattr(self, "cls", _class)
        return name if name else None

    @cached_property
    def title(self) -> Optional[str]:
        """Return _NET_WM_NAME property"""
        result = self.get_property(property="_NET_WM_NAME", type="UTF8_STRING")
        if not result:
            return None
        return cast(List[str], result)[0]

    def get_name_and_class(self) -> Tuple[Optional[str], Optional[str]]:
        """Return WM_CLASS property"""
        result = self.get_property(property="WM_CLASS", type="STRING", split=True)
        if not result or len(result) != 2:
            return None, None
        result = cast(List[str], result)
        return result[0], result[1]

    def matches(
        self,
        name: Optional[str] = None,
        cls: Optional[str] = None,
        role: Optional[str] = None,
        desktop: Optional[int] = None,
        title: Optional[str] = None,
    ) -> bool:
        """Check if window suits given matchers.

        Matchers keyword arguments are used in :meth:`on_create`,
        :func:`actions.spawn_or_raise`. :meth:`find_clients` and
        :meth:`find_client`.

        name
          window name (also referenced as `instance`).
          The first part of ``WM_CLASS`` property.

        cls
          window class. The second part of ``WM_CLASS`` property.

        role
          window role. Value of ``WM_WINDOW_ROLE`` property.

        desktop
          matches windows placed on specific desktop. Must be int.

        title
          window title.

        `name`, `cls`, `title` and `role` can be regular expressions.

        """
        if name and not utils.match_string(pattern=name, data=self.name or ""):
            return False
        if cls and not utils.match_string(pattern=cls, data=self.cls or ""):
            return False
        if role and not utils.match_string(pattern=role, data=self.role or ""):
            return False
        if title and not utils.match_string(pattern=title, data=self.title or ""):
            return False
        if desktop is not None and desktop != self.desktop:
            return False

        return True

    def get_property(
        self, property: str, type: Optional[str] = None, split: bool = False
    ) -> Optional[Union[List[int], List[str]]]:
        """
        This function is a wrapper for `XGetWindowProperty`. Returns a property for the window, the result can be `None` if no property was found, a `List[int]`or a `List[str]`.
        """
        return xlib.get_window_property(
            display=self.wm.dpy,
            window=self,
            property=self.wm.atom[property],
            type=self.wm.atom[type] if type else xlib.lib.AnyPropertyType,
            split=split,
        )

    def set_property(
        self, property: str, format: int, data: Union[List[int], List[str]], type: Optional[str] = None
    ) -> None:
        """
        This functions is a wrapper for `XChangeProperty`, it alters the property for the specified window.

        If the specified format is 8, the property data must be a char array. (List[str] on python)

        If the specified format is 16, the property data must be a short array. (List[int] on python)

        If the specified format is 32, the property data must be a long array. (List[int] on python)
        """
        xlib.set_window_property(
            display=self.wm.dpy,
            window=self,
            property=self.wm.atom[property],
            type=self.wm.atom[type] if type else xlib.lib.AnyPropertyType,
            format=format,
            values=data,
        )

    def get_windows_same_pid(self) -> List[Window]:
        """
        This function returns a List[Window] that has the same pid of `self`
        """
        windows_associated: List[Window] = []
        window_tree: Optional[Tuple[Window, Window, List[Window], int]] = self.wm._get_window_tree(
            window=self.wm.create_window(window_id=self.wm.root)
        )
        if not window_tree or not len(window_tree[2]) or not self.pid:
            return windows_associated
        for window in window_tree[2]:
            if window.pid == self.pid:
                windows_associated.append(window)
        return windows_associated

    def get_window_tree(self) -> Optional[WindowTree]:
        """
        This function is a wrapper for `XQueryTree`. Returns a WindowTree instance containing
        the window, the root window, the parent window and a list of children windows (empty if there's none)
        """
        window_tree: Optional[Tuple[Window, Window, List[Window], int]] = self.wm._get_window_tree(window=self)
        if not window_tree:
            return None
        return WindowTree(window=self, root=window_tree[0], parent=window_tree[1], children=window_tree[2])

    def set_window_icon(self, icon: Union[Path, str]) -> None:
        """
        This function sets the window's icon, the maximum icon size is 2Mb
        """
        if isinstance(icon, str):
            icon = Path(icon)
        if not icon.is_file():
            print("The path is not a valid file")
            return
        if icon.stat().st_size > 2000000:
            print("The maximum icon size is 2Mb")
            return
        self.wm._set_window_icon(window=self, icon=str(icon))

    @cached_property
    def attributes(self) -> XWindowAttributes:
        """
        This function is a wrapper for `XGetWindowAttributes`. Returns the current attributes for the window
        """
        attrs = xlib.get_window_attributes(display=self.wm.dpy, window=self)
        return XWindowAttributes(attributes=attrs)

    @cached_property
    def state(self) -> List[str]:
        """Return _NET_WM_STATE"""
        states = self.get_property(property="_NET_WM_STATE", type="ATOM")
        if not states:
            return []
        states = cast(List[xlib.Atom], states)
        return [self.wm.get_atom_name(atom=state) for state in states if self.wm.get_atom_name(atom=state)]

    @cached_property
    def maximized_vert(self) -> bool:
        return "_NET_WM_STATE_MAXIMIZED_VERT" in self.state

    @cached_property
    def maximized_horz(self) -> bool:
        return "_NET_WM_STATE_MAXIMIZED_HORZ" in self.state

    @cached_property
    def decorated(self) -> bool:
        """
        Returns False if the window is not decorated otherwise True

        A non-decorated window is considered when:
        - There's no window manager running
        - It has the attribute override-redirect
        - It has a 0 in the third bit on the property `_MOTIF_WM_HINTS`
        """
        decorated: bool = True
        try:
            if not self.wm.wm_name:  # If the window manager is not running window can't be decorated
                decorated = False
            else:
                # If the window has the attribute override-redirect it can't be decorated
                if self.attributes.override_redirect:
                    decorated = False
                # If the window manager running is Openbox then it checks if window has the state '_OB_WM_STATE_UNDECORATED'
                elif self.wm.wm_name == "Openbox":
                    if "_OB_WM_STATE_UNDECORATED" in self.state:
                        decorated = False
                # If the window manager is not Openbox then it looks for the third bit on the property '_MOTIF_WM_HINTS'
                # to determine the decorations
                else:
                    """
                    {
                        int     flags;
                        int     functions;
                        int     decorations;
                        int     input_mode;
                        int     status;
                    } MotifWmHints;
                    """
                    motif_hints = self.get_property(property="_MOTIF_WM_HINTS", type="_MOTIF_WM_HINTS")
                    # If the decorations bit in the _MOTIF_WM_HINTS (position 2) is 0 then we can assume
                    # the window is not decorated
                    if motif_hints is not None and cast(List[int], motif_hints)[2] == 0:
                        decorated = False
        except:
            decorated = False
        return decorated

    @cached_property
    def urgent(self) -> bool:
        return "_NET_WM_STATE_DEMANDS_ATTENTION" in self.state

    @cached_property
    def fullscreen(self) -> bool:
        return "_NET_WM_STATE_FULLSCREEN" in self.state

    @cached_property
    def pid(self) -> Optional[int]:
        result = self.get_property(property="_NET_WM_PID", type="CARDINAL")
        if not result:
            return None
        return cast(List[int], result)[0]
