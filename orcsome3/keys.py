"""Hotkey and window-match types used by WindowManager without importing it."""

from __future__ import annotations

from enum import Enum
from typing import Any, NamedTuple, Optional, Union

from typing_extensions import override

import orcsome3.libs.xlib as xlib
from orcsome3.aliases import KEYS as KEY_ALIASES


class KeyboardModifiers(int, Enum):
    """Enum representation of keyboard modifiers. A modifier is a key associated with a keyboard modifier mask."""

    NoModifiers = xlib.KEY_MASKS.NoModifiers.value
    AnyModifier = xlib.KEY_MASKS.AnyModifier.value
    Alt = xlib.KEY_MASKS.Mod1Mask.value
    Meta = Alt
    Control = xlib.KEY_MASKS.ControlMask.value
    Ctrl = Control
    Shift = xlib.KEY_MASKS.ShiftMask.value
    Win = xlib.KEY_MASKS.Mod4Mask.value
    Windows = Win
    Hyper = Win
    Super = Win


class WindowMatchers(NamedTuple):
    """
    Class representing matchers for a window. All attributes can be `None`

    Attrs:
    - `name`: Window name. The first part of `WM_CLASS` property.
    - `class_`: Window class. The second part of `WM_CLASS` property.
    - `role`: Window role. Value of `WM_WINDOW_ROLE` property.
    - `desktop`: Matches windows placed on specific desktop. Value of `_NET_WM_DESKTOP` property.
    - `title`: Window title. Value of `_NET_WM_NAME` property.
    - `window_type`: Window type/s. Value/s of `_NET_WM_WINDOW_TYPE` property.

    `name`, `class_`, `title`, `role` and the elements of `window_type` can be regular expressions.
    """

    name: Optional[str] = None
    class_: Optional[str] = None
    role: Optional[str] = None
    desktop: Optional[int] = None
    title: Optional[str] = None
    window_type: Optional[list[str]] = None

    def is_empty(self) -> bool:
        """Check if all attributes are `None`"""
        attrs: list[str] = ["name", "class_", "role", "desktop", "title", "window_type"]
        values: list[Any] = [getattr(self, x) for x in attrs]
        return all(value is None for value in values)


def keycode_from_string_or_keysym(
    display: xlib.TYPES.Cython_Display, key: Union[str, xlib.TYPES.Cython_KeySym]
) -> Optional[xlib.TYPES.Cython_KeyCode]:
    """Resolve a key name or KeySym to a KeyCode on `display`."""
    keysym: xlib.TYPES.Cython_KeySym = xlib.CONSTANTS.KB.NO_SYMBOL
    if isinstance(key, str):
        keysym = xlib.x_string_to_keysym(string=KEY_ALIASES.get(key, key))
    else:
        keysym = key
    if keysym == xlib.CONSTANTS.KB.NO_SYMBOL:
        return None
    return xlib.x_keysym_to_keycode(display=display, keysym=keysym)


class KeyDefinition:
    """
    Class representing a key definition for a global hotkey. A key definition consists of modifiers and a key.

    Attrs:
    - `modifiers`: Specifies the set of modifiers for the global hotkey.

        It can be an instance of `int` representing a valid value for a keymask bit or the value of the
         bitwise inclusive OR of valid keymask bits.

        Also, it can be a value from enum :class:`orcsome3.keys.KeyboardModifiers`
         or a list of values from same enum.

        For all possible modifiers combination use `orcsome3.keys.KeyboardModifiers.AnyModifier`.

    - `key`: Key for the global hotkey. See class :class:`orcsome3.keys.KeyDefinition.Key`


    More information about keyboard modifiers can be found using utility `xmodmap`.

    More information about keys, keycodes and keysyms can be found using utility `xev`.
    """

    class Key:
        """
        Class representing a key. a Key can be represented by its keycode, keysym or name. Only one attribute is allowed.

        For all possible keys use keycode `orcsome3.xlib.CONSTANTS.KB.ANY_KEY`

        Attrs:
        - `name`: Key name. Valid names can be obtained from `X11/keysymdef.h` by removing the "XK_" prefix from each.
         Defaults to `None`.
        - `keycode`: KeyCode of key. Defaults to `None`.
        - `keysym`: KeySym of key. Defaults to `None`.
        """

        def __init__(
            self,
            name: Optional[str] = None,
            keycode: Optional[xlib.TYPES.Cython_KeyCode] = None,
            keysym: Optional[xlib.TYPES.Cython_KeySym] = None,
        ) -> None:
            """Exactly one of `name`, `keycode`, or `keysym` must be set; `name` must be non-empty if used."""
            self.name: Optional[str] = name
            self.keycode: Optional[Union[int, xlib.TYPES.Cython_KeyCode]] = keycode
            self.keysym: Optional[Union[int, xlib.TYPES.Cython_KeySym]] = keysym

            non_none_attrs: int = 0
            for attr in ["name", "keycode", "keysym"]:
                if getattr(self, attr) is not None:
                    non_none_attrs += 1
            if non_none_attrs == 0:
                raise Exception("Provide one attribute to create a Key object")
            elif non_none_attrs > 1:
                raise Exception("Only one attribute can be specified when creating a Key object")

            if self.name is not None and not len(self.name.strip()):
                raise Exception("Key name cannot be empty")

        def get_keycode(self, display: xlib.TYPES.Cython_Display) -> Optional[xlib.TYPES.Cython_KeyCode]:
            """Resolve this key to a KeyCode on `display`. `name="any_key"` maps to `CONSTANTS.KB.ANY_KEY`."""
            if self.keycode is not None:
                return self.keycode
            if self.keysym is not None:
                return keycode_from_string_or_keysym(display=display, key=self.keysym)
            if self.name is not None:
                if self.name.lower() == "any_key":
                    return xlib.CONSTANTS.KB.ANY_KEY
                return keycode_from_string_or_keysym(display=display, key=self.name)
            return None

        @override
        def __repr__(self) -> str:
            return f"{self.__class__.__name__}({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items() if not k.startswith('_')])})"

    def __init__(self, modifiers: Union[int, KeyboardModifiers, list[KeyboardModifiers]], key: Key) -> None:
        """Store `modifiers` (mask, enum, or list of enums) and `key` without resolving them yet."""
        self.modifiers: Union[int, KeyboardModifiers, list[KeyboardModifiers]] = modifiers
        self.key: KeyDefinition.Key = key

    @classmethod
    def new_from_string(cls, keydef: str) -> KeyDefinition:
        """Parse `"Modifier + Modifier + key"` (spaces ignored). Last `+` segment is the key name."""
        parts: list[str] = ["".join(x.split()) for x in keydef.split(sep="+") if len(x.strip())]
        modifiers: list[str] = parts[:-1]
        key: str = parts[-1]
        modifiers_for_key_definition: list[KeyboardModifiers] = []
        for modifier in modifiers:
            for keyboard_modifier in KeyboardModifiers:
                if modifier.lower() == keyboard_modifier.name.lower():
                    modifiers_for_key_definition.append(keyboard_modifier)
                    break
        return KeyDefinition(modifiers=modifiers_for_key_definition, key=KeyDefinition.Key(name=key))

    def get_modifiers_value(self) -> int:
        """OR together modifier masks. An empty list is `KeyboardModifiers.NoModifiers`."""
        if isinstance(self.modifiers, int):
            return self.modifiers
        elif isinstance(self.modifiers, KeyboardModifiers):
            return self.modifiers.value
        else:
            new_modifier: int = KeyboardModifiers.NoModifiers.value
            if not len(self.modifiers):
                return new_modifier
            for modifier in self.modifiers:
                new_modifier |= modifier.value
            return new_modifier

    def get_modifiers_value_and_keycode(
        self, display: xlib.TYPES.Cython_Display
    ) -> tuple[int, xlib.TYPES.Cython_KeyCode]:
        """Returns modifiers value and keycode for the key definition. Raise an exception if no keycode is found for attribute `key`."""

        modifiers_value: int = self.get_modifiers_value()
        keycode_of_key: Optional[xlib.TYPES.Cython_KeyCode] = self.key.get_keycode(display=display)
        if keycode_of_key is None:
            raise Exception(f"Error obtaining KeyCode for {self.key}")
        return modifiers_value, keycode_of_key

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join([f'{k}={v!r}' for k, v in self.__dict__.items() if not k.startswith('_')])})"
