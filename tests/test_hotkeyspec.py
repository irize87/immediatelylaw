# -*- coding: utf-8 -*-
"""hotkeyspec regression: canonical spec <-> Win32 RegisterHotKey args,
Qt key-event capture. ASCII-only source (no Korean needed here)."""
from PySide6.QtCore import Qt

from immediatelylaw import hotkeyspec as hk


def test_default_parses_to_win32_args():
    mods, vk = hk.parse_spec(hk.DEFAULT_SPEC)
    assert mods == hk.MOD_CONTROL | hk.MOD_ALT | hk.MOD_NOREPEAT
    assert vk == 0x4C


def test_tolerates_order_case_space():
    assert hk.parse_spec(" Alt + CTRL + L ") == hk.parse_spec("ctrl+alt+l")


def test_win_and_function_keys():
    mods, vk = hk.parse_spec("win+d")
    assert mods == hk.MOD_WIN | hk.MOD_NOREPEAT and vk == 0x44
    mods, vk = hk.parse_spec("ctrl+shift+f12")
    assert vk == 0x7B and mods & hk.MOD_SHIFT and mods & hk.MOD_CONTROL


def test_function_key_alone_allowed():
    assert hk.parse_spec("f7") == (hk.MOD_NOREPEAT, 0x76)


def test_bare_and_shift_only_rejected():
    assert hk.parse_spec("l") is None
    assert hk.parse_spec("shift+l") is None
    assert hk.parse_spec("ctrl+alt+shift") is None   # modifiers only
    assert hk.parse_spec("") is None
    assert hk.parse_spec(None) is None


def test_unknown_tokens_rejected():
    assert hk.parse_spec("ctrl+`") is None
    assert hk.parse_spec("hyper+k") is None
    assert hk.parse_spec("ctrl+alt+25") is None


def test_named_keys():
    assert hk.parse_spec("ctrl+home")[1] == 0x24
    assert hk.parse_spec("alt+pgdn")[1] == 0x22
    assert hk.parse_spec("win+space")[1] == 0x20


def test_format_display():
    assert hk.format_spec("ctrl+alt+l") == "Ctrl+Alt+L"
    assert hk.format_spec("f12") == "F12"
    assert hk.format_spec("ctrl+pgup") == "Ctrl+PgUp"
    assert hk.format_spec("garbage") == "Ctrl+Alt+L"        # fallback
    assert hk.format_spec(None) == "Ctrl+Alt+L"
    assert hk.format_spec("alt+shift+f5", " + ") == "Alt + Shift + F5"


def test_spec_from_key_event():
    make = hk.spec_from_key_event                      # accepts raw Qt flags
    assert make(Qt.ControlModifier | Qt.AltModifier, Qt.Key_L) == "ctrl+alt+l"
    assert make(Qt.MetaModifier, Qt.Key_D) == "win+d"
    assert make(Qt.NoModifier, Qt.Key_F12) == "f12"
    assert make(Qt.NoModifier, Qt.Key_L) is None            # bare key
    assert make(Qt.ShiftModifier, Qt.Key_5) is None         # shift alone
    assert make(Qt.ControlModifier, Qt.Key_Home) == "ctrl+home"
    assert make(Qt.ControlModifier, Qt.Key_Z) == "ctrl+z"
    # keypad flag inside the key code must not leak into the spec
    # (real QKeyEvent.key() ORs the bit into the int keycode)
    assert make(Qt.ControlModifier | Qt.KeypadModifier,
                hk.qint(Qt.Key_1) | hk._QT_KEYPAD_BIT) == "ctrl+1"
    # and the binding-level QKeyCombination form must not crash it either
    assert make(Qt.ControlModifier,
                Qt.Key_1 | Qt.KeypadModifier) == "ctrl+1"
    assert make(Qt.AltModifier, Qt.Key_Escape) is None      # control keys
