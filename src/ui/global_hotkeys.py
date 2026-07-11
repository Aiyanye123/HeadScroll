"""Native Windows global hotkeys integrated with Qt's event loop."""

import ctypes
from ctypes import wintypes
from typing import Optional

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal
from PySide6.QtWidgets import QApplication


MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
PAUSE_HOTKEY_ID = 0xB001
STOP_HOTKEY_ID = 0xB002

MODIFIERS = {
    "Alt": MOD_ALT,
    "Ctrl": MOD_CONTROL,
    "Shift": MOD_SHIFT,
    "Meta": MOD_WIN,
    "Win": MOD_WIN,
}
KEYS = {
    "Space": 0x20,
    "Escape": 0x1B,
    "Esc": 0x1B,
    "Left": 0x25,
    "Up": 0x26,
    "Right": 0x27,
    "Down": 0x28,
    "PageUp": 0x21,
    "PgUp": 0x21,
    "PageDown": 0x22,
    "PgDown": 0x22,
    "Home": 0x24,
    "End": 0x23,
    "Insert": 0x2D,
    "Ins": 0x2D,
    "Delete": 0x2E,
    "Del": 0x2E,
    "Return": 0x0D,
    "Enter": 0x0D,
    "Tab": 0x09,
    "Backspace": 0x08,
}


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


def parse_hotkey(sequence: str) -> tuple[int, int]:
    parts = [part.strip() for part in sequence.split("+") if part.strip()]
    if not parts:
        raise ValueError("hotkey cannot be empty")
    modifiers = 0
    for part in parts[:-1]:
        if part not in MODIFIERS:
            raise ValueError(f"unsupported hotkey modifier: {part}")
        modifiers |= MODIFIERS[part]

    key_name = parts[-1]
    if len(key_name) == 1 and key_name.isalnum():
        virtual_key = ord(key_name.upper())
    elif key_name.startswith("F") and key_name[1:].isdigit() and 1 <= int(key_name[1:]) <= 24:
        virtual_key = 0x70 + int(key_name[1:]) - 1
    else:
        virtual_key = KEYS.get(key_name, 0)
    if not virtual_key:
        raise ValueError(f"unsupported hotkey key: {key_name}")
    return modifiers, virtual_key


class GlobalHotkeys(QObject, QAbstractNativeEventFilter):
    pause_pressed = Signal()
    stop_pressed = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        QObject.__init__(self, parent)
        QAbstractNativeEventFilter.__init__(self)
        self._user32 = ctypes.windll.user32
        self._registered: set[int] = set()
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("QApplication must exist before global hotkeys")
        app.installNativeEventFilter(self)

    def update(self, pause_sequence: str, stop_sequence: str) -> None:
        self.unregister()
        try:
            self._register(PAUSE_HOTKEY_ID, pause_sequence)
            self._register(STOP_HOTKEY_ID, stop_sequence)
        except Exception:
            self.unregister()
            raise

    def _register(self, hotkey_id: int, sequence: str) -> None:
        modifiers, virtual_key = parse_hotkey(sequence)
        if not self._user32.RegisterHotKey(
            None, hotkey_id, modifiers | MOD_NOREPEAT, virtual_key
        ):
            raise OSError(ctypes.get_last_error(), f"无法注册全局快捷键 {sequence}")
        self._registered.add(hotkey_id)

    def unregister(self) -> None:
        for hotkey_id in self._registered:
            self._user32.UnregisterHotKey(None, hotkey_id)
        self._registered.clear()

    def close(self) -> None:
        self.unregister()
        app = QApplication.instance()
        if app is not None:
            app.removeNativeEventFilter(self)

    def nativeEventFilter(self, event_type, message):
        try:
            msg = ctypes.cast(int(message), ctypes.POINTER(MSG)).contents
        except (TypeError, ValueError):
            return False, 0
        if msg.message != WM_HOTKEY:
            return False, 0
        if msg.wParam == PAUSE_HOTKEY_ID:
            self.pause_pressed.emit()
        elif msg.wParam == STOP_HOTKEY_ID:
            self.stop_pressed.emit()
        return False, 0
