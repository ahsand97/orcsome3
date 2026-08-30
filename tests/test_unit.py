"""Tests that do not need an X server."""

from __future__ import annotations

import unittest

from orcsome3.instance import _self_check, display_key
from orcsome3.keys import KeyboardModifiers, KeyDefinition, WindowMatchers
from orcsome3.libs.xlib import BUTTON_MASKS, KEY_MASKS
from orcsome3.utils import match_string
from orcsome3.window_manager import _BUTTON_STATE_MASK, _modifiers_mask


class TestDisplayKey(unittest.TestCase):
    def test_screen_suffix_dropped(self) -> None:
        _self_check()
        self.assertEqual(display_key(display=":0.0"), ":0")
        self.assertNotEqual(display_key(display=":0"), display_key(display=":1"))


class TestKeyDefinition(unittest.TestCase):
    def test_parse_control_d(self) -> None:
        parsed: KeyDefinition = KeyDefinition.new_from_string(keydef="Control + d")
        self.assertEqual(parsed.key.name, "d")
        self.assertEqual(parsed.get_modifiers_value(), KeyboardModifiers.Control.value)

    def test_parse_multi_modifier(self) -> None:
        parsed: KeyDefinition = KeyDefinition.new_from_string(keydef="Control + Shift + a")
        self.assertEqual(
            parsed.get_modifiers_value(),
            KeyboardModifiers.Control.value | KeyboardModifiers.Shift.value,
        )

    def test_key_requires_one_attr(self) -> None:
        with self.assertRaises(Exception):
            KeyDefinition.Key()
        with self.assertRaises(Exception):
            KeyDefinition.Key(name="a", keycode=38)


class TestModifiersMask(unittest.TestCase):
    def test_enum_and_list(self) -> None:
        self.assertEqual(_modifiers_mask(modifiers=KeyboardModifiers.Alt), int(KeyboardModifiers.Alt))
        self.assertEqual(
            _modifiers_mask(modifiers=[KeyboardModifiers.Control, KeyboardModifiers.Shift]),
            int(KeyboardModifiers.Control) | int(KeyboardModifiers.Shift),
        )

    def test_button_state_mask_strips_buttons_not_keys(self) -> None:
        mixed: int = KEY_MASKS.ControlMask.value | BUTTON_MASKS.Button2Mask.value
        self.assertEqual(mixed & ~_BUTTON_STATE_MASK, KEY_MASKS.ControlMask.value)


class TestWindowMatchers(unittest.TestCase):
    def test_empty(self) -> None:
        self.assertTrue(WindowMatchers().is_empty())
        self.assertFalse(WindowMatchers(class_="URxvt").is_empty())


class TestMatchString(unittest.TestCase):
    def test_regex_search(self) -> None:
        self.assertTrue(match_string(pattern="fox", string="the firefox window"))
        self.assertFalse(match_string(pattern="^chrome$", string="chromium"))


if __name__ == "__main__":
    unittest.main()
