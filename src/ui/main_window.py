"""Main window wiring for the control panel and tray."""

import logging
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

from .floating_panel import FloatingPanel
from .calibration_wizard import CalibrationWizard
from .global_hotkeys import GlobalHotkeys
from .tray_icon import TrayIcon


class MainWindow(QMainWindow):
    start_requested = Signal()
    stop_requested = Signal()
    pause_requested = Signal()
    calibrate_requested = Signal()
    calibration_complete = Signal(float, float, float)
    calibration_cancelled = Signal()
    settings_requested = Signal()
    sensitivity_changed = Signal(int)
    exit_requested = Signal()

    def __init__(
        self,
        always_on_top: bool = True,
        toggle_pause_hotkey: Optional[str] = None,
        emergency_stop_hotkey: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.panel = FloatingPanel(always_on_top)
        self.tray = TrayIcon(self)
        self.calibration_wizard = CalibrationWizard(self.panel)
        self.calibration_wizard.calibration_complete.connect(
            self.calibration_complete.emit
        )
        self.calibration_wizard.calibration_cancelled.connect(
            self.calibration_cancelled.emit
        )
        self._toggle_pause_hotkey = toggle_pause_hotkey or "Ctrl+Shift+Space"
        self._emergency_stop_hotkey = emergency_stop_hotkey or "Escape"
        self._connect_signals()
        self._setup_shortcuts()
        self._global_hotkeys = GlobalHotkeys(self)
        self._global_hotkeys.pause_pressed.connect(self.pause_requested.emit)
        self._global_hotkeys.stop_pressed.connect(self._emergency_stop)
        try:
            self._global_hotkeys.update(
                self._toggle_pause_hotkey, self._emergency_stop_hotkey
            )
        except OSError as exc:
            logging.getLogger("ui.hotkeys").warning(
                "Global hotkeys unavailable; in-app shortcuts remain active: %s", exc
            )
        self.hide()

    def _connect_signals(self) -> None:
        self.panel.start_clicked.connect(self.start_requested.emit)
        self.panel.stop_clicked.connect(self.stop_requested.emit)
        self.panel.pause_clicked.connect(self.pause_requested.emit)
        self.panel.calibrate_clicked.connect(self._show_calibration)
        self.panel.settings_clicked.connect(self.settings_requested.emit)
        self.panel.sensitivity_changed.connect(self.sensitivity_changed.emit)
        self.tray.show_panel_clicked.connect(self._show_panel)
        self.tray.start_clicked.connect(self.start_requested.emit)
        self.tray.stop_clicked.connect(self.stop_requested.emit)
        self.tray.pause_clicked.connect(self.pause_requested.emit)
        self.tray.exit_clicked.connect(self._on_exit)

    def _setup_shortcuts(self) -> None:
        self._pause_shortcut = QShortcut(QKeySequence(self._toggle_pause_hotkey), self.panel)
        self._pause_shortcut.activated.connect(self.pause_requested.emit)
        self._stop_shortcut = QShortcut(QKeySequence(self._emergency_stop_hotkey), self.panel)
        self._stop_shortcut.activated.connect(self._emergency_stop)

    def shutdown_hotkeys(self) -> None:
        self._global_hotkeys.close()

    def update_hotkeys(self, toggle_pause: str, emergency_stop: str) -> None:
        self._toggle_pause_hotkey = toggle_pause or self._toggle_pause_hotkey
        self._emergency_stop_hotkey = emergency_stop or self._emergency_stop_hotkey
        self._pause_shortcut.setKey(QKeySequence(self._toggle_pause_hotkey))
        self._stop_shortcut.setKey(QKeySequence(self._emergency_stop_hotkey))
        try:
            self._global_hotkeys.update(
                self._toggle_pause_hotkey, self._emergency_stop_hotkey
            )
        except OSError as exc:
            QMessageBox.warning(self.panel, "快捷键冲突", str(exc))

    def _show_panel(self) -> None:
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

    def _show_calibration(self) -> None:
        self.calibration_wizard.prepare()
        self.calibrate_requested.emit()
        self.calibration_wizard.exec()

    def _emergency_stop(self) -> None:
        self.stop_requested.emit()
        self.tray.show_message("紧急停止", "HeadScroll 已停止")

    def _on_exit(self) -> None:
        reply = QMessageBox.question(
            self.panel,
            "确认退出",
            "确定要退出 HeadScroll 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.exit_requested.emit()
            QApplication.quit()

    def show(self) -> None:
        self.panel.show()
        self.tray.show()

    def set_running(self, running: bool) -> None:
        self.panel.set_running(running)
        self.tray.set_running(running)

    def set_paused(self, paused: bool) -> None:
        self.panel.set_paused(paused)
        self.tray.set_paused(paused)

    def set_mode(self, mode: str) -> None:
        self.panel.set_mode(mode)

    def update_palm(self, palm_x: float | None) -> None:
        self.panel.update_palm(palm_x)

    def update_last_action(self, action: str) -> None:
        self.panel.update_last_action(action)

    def update_fps(self, fps: float) -> None:
        self.panel.update_fps(fps)

    def update_detection(self, present: bool, label: str, confidence: float) -> None:
        self.panel.update_detection(present, label, confidence)

    def update_position(self, position: float | None) -> None:
        self.panel.update_position(position)

    def update_control_state(self, state: str) -> None:
        self.panel.update_control_state(state)

    def update_transcript(self, transcript: str) -> None:
        self.panel.update_transcript(transcript)

    def update_calibration_value(self, position: float, raw_value: float) -> None:
        if self.calibration_wizard.isVisible():
            self.calibration_wizard.update_gaze(position, raw_value)

    def show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self.panel, title, message)

    def show_info(self, title: str, message: str) -> None:
        QMessageBox.information(self.panel, title, message)
