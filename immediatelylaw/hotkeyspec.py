# -*- coding: utf-8 -*-
"""Global summon hotkey spec.

The canonical stored form is a plain string such as ``"ctrl+alt+l"``
(config.json key ``hotkey``). This module converts that string to the
Win32 ``RegisterHotKey`` arguments and back, and turns a captured Qt key
event into the canonical form. Pure conversions only -- widget capture
lives in settingsdlg, registration in app.

Validation rules:
- At least one of Ctrl / Alt / Win must be held for ordinary keys.
  Shift alone or a bare key would swallow normal typing system-wide.
- F1..F24 may stand alone (a widely accepted convention).
- Canonical order is ctrl+alt+shift+win+key; parsing tolerates any order.
"""
from PySide6.QtCore import Qt

# winuser.h modifier flags
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x80000
MOD_NOREPEAT = 0x4000          # Win7+: fire once, not on key auto-repeat
MOD_REQUIRED_ANY = MOD_ALT | MOD_CONTROL | MOD_WIN

DEFAULT_SPEC = "ctrl+alt+l"


def qint(x):
    """int for any Qt enum/flag: PySide6 6.x blocks int() on enum
    instances (single AND combined flags) but always exposes .value.
    QKeyCombination (Key | Modifier) carries toCombined()."""
    comb = getattr(x, "toCombined", None)
    if comb is not None:
        return int(comb())
    v = getattr(x, "value", None)
    if v is not None:
        return int(v)
    return int(x)


# canonical key token -> Win32 virtual-key code
VK = {}
for _i in range(26):
    VK[chr(ord("a") + _i)] = 0x41 + _i           # A..Z
for _i in range(10):
    VK[str(_i)] = 0x30 + _i                      # top-row digits
for _i in range(1, 25):
    VK["f%d" % _i] = 0x70 + _i - 1               # F1..F24
VK.update({"space": 0x20, "pgup": 0x21, "pgdn": 0x22, "end": 0x23,
           "home": 0x24, "left": 0x25, "up": 0x26, "right": 0x27,
           "down": 0x28, "insert": 0x2D, "delete": 0x2E})

_MOD_CANON = (("ctrl", MOD_CONTROL), ("alt", MOD_ALT),
              ("shift", MOD_SHIFT), ("win", MOD_WIN))
_MOD_DISPLAY = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift",
                "win": "Win"}
_KEY_DISPLAY = {"space": "Space", "pgup": "PgUp", "pgdn": "PgDn",
                "insert": "Insert", "delete": "Delete", "home": "Home",
                "end": "End", "left": "Left", "up": "Up", "right": "Right",
                "down": "Down"}

# Qt key codes for the named (non-text) keys we allow as hotkeys
_QT_NAMED = {qint(Qt.Key_Left): "left", qint(Qt.Key_Up): "up",
             qint(Qt.Key_Right): "right", qint(Qt.Key_Down): "down",
             qint(Qt.Key_Home): "home", qint(Qt.Key_End): "end",
             qint(Qt.Key_PageUp): "pgup", qint(Qt.Key_PageDown): "pgdn",
             qint(Qt.Key_Insert): "insert", qint(Qt.Key_Delete): "delete",
             qint(Qt.Key_Space): "space"}
_QT_A, _QT_Z = qint(Qt.Key_A), qint(Qt.Key_Z)
_QT_0, _QT_9 = qint(Qt.Key_0), qint(Qt.Key_9)
_QT_F1, _QT_F24 = qint(Qt.Key_F1), qint(Qt.Key_F24)
_QT_KEYPAD_BIT = 0x20000000     # Qt.KeypadModifier (0x20000000; note that
# Qt.ShiftModifier is 0x02000000 -- different bit) inside combined key codes
# Pre-extracted ints: PySide6 6.x raises on int(KeyboardModifier...).
_QT_CTRL = qint(Qt.ControlModifier)
_QT_ALT = qint(Qt.AltModifier)
_QT_SHIFT = qint(Qt.ShiftModifier)
_QT_META = qint(Qt.MetaModifier)


def parse_spec(spec):
    """Return ``(fsModifiers, vk)`` with MOD_NOREPEAT, or None if invalid."""
    if not spec:
        return None
    parts = [p for p in str(spec).strip().lower().replace(" ", "")
             .split("+") if p]
    if not parts:
        return None
    mods = 0
    for p in parts[:-1]:
        for name, flag in _MOD_CANON:
            if p == name:
                mods |= flag
                break
        else:
            return None
    vk = VK.get(parts[-1])
    if vk is None:
        return None
    if vk < 0x70 and not (mods & MOD_REQUIRED_ANY):
        return None              # bare/shift-only alnum or named key
    return mods | MOD_NOREPEAT, vk


def format_spec(spec, sep="+"):
    """Human-readable form ('Ctrl+Alt+L'). Invalid input renders the default."""
    if parse_spec(spec) is None:
        spec = DEFAULT_SPEC
    parts = [p for p in str(spec).strip().lower().replace(" ", "")
             .split("+") if p]
    have = set(parts[:-1])
    token = parts[-1]
    names = [_MOD_DISPLAY[name] for name, _flag in _MOD_CANON
             if name in have]
    if token in _KEY_DISPLAY:
        key_disp = _KEY_DISPLAY[token]
    elif token.startswith("f") and token[1:].isdigit():
        key_disp = token.capitalize()          # f12 -> F12
    else:
        key_disp = token.upper()               # l -> L, 5 -> 5
    return sep.join(names + [key_disp])


def spec_from_key_event(mods_qt, key_qt):
    """Convert a Qt key press into the canonical spec, or None if unusable.

    Pass ``event.modifiers()`` and ``event.key()`` (enum objects or ints).
    """
    mods = qint(mods_qt)
    key = qint(key_qt) & ~_QT_KEYPAD_BIT
    if _QT_A <= key <= _QT_Z:
        token = chr(key).lower()
    elif _QT_0 <= key <= _QT_9:
        token = chr(key)
    elif _QT_F1 <= key <= _QT_F24:
        token = "f%d" % (key - _QT_F1 + 1)
    else:
        token = _QT_NAMED.get(key)
    if token is None:
        return None
    canon = []
    if mods & _QT_CTRL:
        canon.append("ctrl")
    if mods & _QT_ALT:
        canon.append("alt")
    if mods & _QT_SHIFT:
        canon.append("shift")
    if mods & _QT_META:
        canon.append("win")
    spec = "+".join(canon + [token])
    return spec if parse_spec(spec) else None
