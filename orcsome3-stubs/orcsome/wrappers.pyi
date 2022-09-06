from . import utils as utils, wm as wm, xlib as xlib
from enum import Enum
from functools import cached_property as cached_property
from pathlib import Path
from typing import List, Optional, Tuple, Union

class WindowTree:
    window: Window
    root: Window
    parent: Window
    children: List[Window]
    def __init__(self, window: Window, root: Window, parent: Window, children: List[Window]) -> None: ...

class XWindowAttributes:
    class MapState(Enum):
        IsUnmapped: Any
        IsUnviewable: Any
        IsViewable: Any
    x: int
    y: int
    width: int
    height: int
    border_width: int
    depth: int
    root: Window
    override_redirect: bool
    map_state: XWindowAttributes.MapState
    def __init__(self, attributes: xlib.XWindowAttributes) -> None: ...

class XScreenSaverInfo:
    class State(Enum):
        Off: Any
        On: Any
        Disabled: Any
    class Kind(Enum):
        Blanked: Any
        Internal: Any
        External: Any
    window: Window
    state: XScreenSaverInfo.State
    kind: XScreenSaverInfo.Kind
    til_or_since: int
    idle: int
    event_mask: int
    def __init__(self, screensaverinfo: xlib.ScreenSaverInfo) -> None: ...

class Window(int):
    wm: wm.WM
    @cached_property
    def desktop(self) -> Optional[int]: ...
    @cached_property
    def role(self) -> Optional[str]: ...
    @cached_property
    def cls(self) -> Optional[str]: ...
    @cached_property
    def name(self) -> Optional[str]: ...
    @cached_property
    def title(self) -> Optional[str]: ...
    def get_name_and_class(self) -> Tuple[Optional[str], Optional[str]]: ...
    def matches(self, name: Optional[str] = ..., cls: Optional[str] = ..., role: Optional[str] = ..., desktop: Optional[int] = ..., title: Optional[str] = ...) -> bool: ...
    def get_property(self, property: str, type: Optional[str] = ..., split: bool = ...) -> Optional[Union[List[int], List[str]]]: ...
    def set_property(self, property: str, format: int, data: Union[List[int], List[str]], type: Optional[str] = ...) -> None: ...
    def get_windows_same_pid(self) -> List[Window]: ...
    def get_window_tree(self) -> Optional[WindowTree]: ...
    def set_window_icon(self, icon: Union[Path, str]) -> None: ...
    @cached_property
    def attributes(self) -> XWindowAttributes: ...
    @cached_property
    def state(self) -> List[str]: ...
    @cached_property
    def maximized_vert(self) -> bool: ...
    @cached_property
    def maximized_horz(self) -> bool: ...
    @cached_property
    def decorated(self) -> bool: ...
    @cached_property
    def urgent(self) -> bool: ...
    @cached_property
    def fullscreen(self) -> bool: ...
    @cached_property
    def pid(self) -> Optional[int]: ...
