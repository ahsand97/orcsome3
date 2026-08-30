from orcsome3.libs.xlib import XKeyEvent
from orcsome3.window_manager import KeyboardModifiers, KeyDefinition, Window, WindowManager, WindowMatchers

"""def decorator(function: Callable[[], None]) -> Callable[[], None]:
            @wraps(wrapped=function)
            def wrapper() -> None:
                function()
                if not propagate_event:
                    return

                keypress_event = cast(xlib.XKeyEvent, self.event)
                # FALTA
                print(keypress_event.__dict__)
                xlib.x_ungrab_key(
                    display=self.display,
                    window=keypress_event.window,
                    keycode=keypress_event.keycode,
                    modifiers=keypress_event.state,
                )
                xlib.x_send_event(
                    display=self.display,
                    window=keypress_event.window,
                    propagate=False,
                    event_masks=[xlib.CONSTANTS.EVENT_MASKS.KeyReleaseMask],
                    xevent=keypress_event._xevent,
                )
                self._flush()

            window_ = window or self.root
            try:
                original_modifier, original_keycode = self._parse_keydef(keydef=keydef)
            except Exception as e:
                _logger.error(msg=f"Invalid key definition {keydef}\n{e}")
                return wrapper

            key_definitions: list[KeyDefinition] = []
            for ignored_key_mask in _IGNORED_KEY_MASKS:
                new_keydef: KeyDefinition = KeyDefinition(
                    modifiers=original_modifier | ignored_key_mask, key=KeyDefinition.Key(keycode=original_keycode)
                )
                xlib.x_grab_key(
                    display=self.display,
                    keycode=cast(xlib.TYPES.C_KeyCode, new_keydef.key.keycode),
                    modifiers=new_keydef.get_modifiers_value(),
                    window=window_,
                    owner_events=False,
                    pointer_mode=xlib.GRAB_MODE.GrabModeAsync,
                    keyboard_mode=xlib.GRAB_MODE.GrabModeAsync,
                )  # FALTA
                self._key_handlers.setdefault(window_, {})[new_keydef] = wrapper
                key_definitions.append(new_keydef)

            def remove() -> None:
                try:
                    for key in key_definitions:
                        _ = self._key_handlers[window_].pop(key, None)
                except Exception:
                    _logger.exception(msg="An exception occurred removing the function.")

            setattr(wrapper, "remove", remove)
            return wrapper

        return decorator"""


wm: WindowManager = WindowManager()


@wm.on_key(key_definition=KeyDefinition(modifiers=KeyboardModifiers.Control, key=KeyDefinition.Key(name="a")))
def test_hotkey(window: Window, event: XKeyEvent) -> None:
    print("hotkey Control + a pressed")


# Custom key to close only urxvt windows when Control + d is pressed
@wm.on_key(
    key_definition=KeyDefinition(modifiers=KeyboardModifiers.Control, key=KeyDefinition.Key(name="d")),
    window=WindowMatchers(class_="URxvt"),
)
def close_urxvt_window(window: Window, event: XKeyEvent) -> None:
    window.close()


@wm.on_key(key_definition="Control + d")
def change_window_desktop(window: Window, event: XKeyEvent) -> None:
    window.change_desktop(desktop=1)
