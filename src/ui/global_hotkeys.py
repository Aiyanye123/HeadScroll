"""Global keyboard hooks with QObject notifications."""

from PySide6.QtCore import QObject, Signal

try:
    import keyboard
except Exception as exc:
    keyboard = None
    _import_error = str(exc)


class GlobalHotkeys(QObject):
    pause_requested = Signal()
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._handles = []

    def update(self, toggle_pause, emergency_stop):
        errors = self.clear()
        if keyboard is None:
            errors.append(f"无法加载全局快捷键组件：{_import_error}")
            return errors
        for shortcut, signal in (
            (toggle_pause, self.pause_requested),
            (emergency_stop, self.stop_requested),
        ):
            try:
                # Hooks run on keyboard's worker thread; only emit Qt signals here.
                handle = keyboard.add_hotkey(shortcut, signal.emit, suppress=False)
                self._handles.append(handle)
            except Exception as exc:
                errors.append(f"{shortcut}：{exc}")
        return errors

    def clear(self):
        errors = []
        if keyboard is not None:
            for handle in self._handles:
                try:
                    keyboard.remove_hotkey(handle)
                except Exception as exc:
                    errors.append(f"注销快捷键失败：{exc}")
        self._handles.clear()
        return errors

    def close(self):
        return self.clear()
