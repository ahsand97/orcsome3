import threading
import time
from pathlib import Path
from tempfile import gettempdir

from orcsome3.notify import Notification
from orcsome3.run import get_wm
from orcsome3.window_manager import KeyboardModifiers, KeyDefinition, WindowManager, WindowMatchers
from orcsome3.wrappers import Window

wm: WindowManager = get_wm()


"""wm.on_key(keydef=KeyDefinition(modifiers=KeyboardModifiers.Control, key=KeyDefinition.Key(name="a")))(
    lambda: print("hotkey Control + a pressed")
)"""


@wm.on_create(WindowMatchers(name="kcalc", cls="kcalc", window_type=["_NET_WM_WINDOW_TYPE_NORMAL"]))
def show_notification_firefox_open() -> None:
    print("kcalc open")


@wm.on_property_change(property="_NET_WM_STATE")
def window_state_changed() -> None:
    if wm.event_window.maximized_horz and wm.event_window.maximized_vert:
        if wm.event_window.decorated:
            wm.event_window.set_state(decorate=False)
    else:
        if not wm.event_window.decorated:
            wm.event_window.set_state(decorate=True)
    if wm.event_window.matches(matcher=WindowMatchers(name="Navigator", cls="firefox")):
        if wm.event_window.fullscreen:
            wm.event_window.set_state(fullscreen=False)
