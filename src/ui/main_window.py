"""
M9: 主窗口
整合所有 UI 组件
"""

import sys
import logging
from typing import Optional
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PySide6.QtCore import Qt, Signal, Slot

from .floating_panel import FloatingPanel
from .tray_icon import TrayIcon
from .calibration_wizard import CalibrationWizard
from .global_hotkeys import GlobalHotkeys


class MainWindow(QMainWindow):
    """主窗口 - 整合所有 UI 组件"""
    
    # 信号
    start_requested = Signal()
    stop_requested = Signal()
    pause_requested = Signal()
    calibrate_requested = Signal()
    settings_requested = Signal()
    speed_changed = Signal(int)
    head_pitch_updated = Signal(float)
    exit_requested = Signal()
    
    def __init__(
        self,
        always_on_top: bool = True,
        toggle_pause_hotkey: Optional[str] = None,
        emergency_stop_hotkey: Optional[str] = None,
    ):
        super().__init__()
        
        self._always_on_top = always_on_top
        self._logger = logging.getLogger("ui.hotkeys")
        
        # 创建 UI 组件
        self.panel = FloatingPanel(always_on_top)
        self.tray = TrayIcon(self)
        self.calibration_wizard: Optional[CalibrationWizard] = None
        
        # 连接信号
        self._connect_signals()
        
        # 设置快捷键
        self._toggle_pause_hotkey = toggle_pause_hotkey or "Ctrl+Shift+Space"
        self._emergency_stop_hotkey = emergency_stop_hotkey or "Escape"
        self._global_hotkeys = None
        self._hotkey_errors = []
        self._register_global_hotkeys()
        
        # 隐藏主窗口，只显示悬浮面板
        self.hide()
    
    def _connect_signals(self):
        """连接 UI 信号"""
        # 悬浮面板信号
        self.panel.start_clicked.connect(self.start_requested.emit)
        self.panel.stop_clicked.connect(self.stop_requested.emit)
        self.panel.pause_clicked.connect(self.pause_requested.emit)
        self.panel.calibrate_clicked.connect(self._show_calibration)
        self.panel.settings_clicked.connect(self._show_settings)
        self.panel.speed_changed.connect(self.speed_changed.emit)
        
        # 托盘信号
        self.tray.show_panel_clicked.connect(self._show_panel)
        self.tray.start_clicked.connect(self.start_requested.emit)
        self.tray.stop_clicked.connect(self.stop_requested.emit)
        self.tray.pause_clicked.connect(self.pause_requested.emit)
        self.tray.calibrate_clicked.connect(self._show_calibration)
        self.tray.exit_clicked.connect(self._on_exit)
    
    def _register_global_hotkeys(self):
        if self._global_hotkeys is None:
            self._global_hotkeys = GlobalHotkeys(self)
            self._global_hotkeys.pause_requested.connect(
                self._on_global_pause, Qt.ConnectionType.QueuedConnection
            )
            self._global_hotkeys.stop_requested.connect(
                self._emergency_stop, Qt.ConnectionType.QueuedConnection
            )
        self._hotkey_errors = self._global_hotkeys.update(
            self._toggle_pause_hotkey, self._emergency_stop_hotkey
        )
        if self._hotkey_errors:
            self._logger.error("Global hotkey registration failed: %s", "; ".join(self._hotkey_errors))
            if self.tray.isVisible():
                self._show_hotkey_errors()

    def _show_hotkey_errors(self):
        self.tray.show_message("全局快捷键不可用", "\n".join(self._hotkey_errors))

    @Slot()
    def _on_global_pause(self):
        self.pause_requested.emit()

    def update_hotkeys(self, toggle_pause: str, emergency_stop: str = "Escape"):
        """Update hotkey bindings."""
        self._toggle_pause_hotkey = toggle_pause or self._toggle_pause_hotkey
        self._emergency_stop_hotkey = emergency_stop or self._emergency_stop_hotkey
        self._register_global_hotkeys()

    def shutdown_hotkeys(self):
        """Cleanup global hotkeys on exit."""
        if self._global_hotkeys is not None:
            for error in self._global_hotkeys.close():
                self._logger.error(error)
            self._global_hotkeys = None

    def _show_panel(self):
        """显示悬浮面板"""
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()
    
    def _show_calibration(self):
        """显示标定向导"""
        if self.calibration_wizard is None:
            self.calibration_wizard = CalibrationWizard(self.panel)
        
        self.calibrate_requested.emit()
        self.calibration_wizard.exec()
    
    @Slot()
    def _emergency_stop(self):
        """紧急停止"""
        self.stop_requested.emit()
        self.tray.show_message("紧急停止", "已停止头部滚动控制")
    
    def _on_exit(self):
        """退出程序"""
        reply = QMessageBox.question(
            self.panel,
            "确认退出",
            "确定要退出头部滚动控制吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.exit_requested.emit()
            QApplication.quit()
    
    def show(self):
        """显示窗口"""
        self.panel.show()
        self.tray.show()
        if self._hotkey_errors:
            self._show_hotkey_errors()
    
    def hide_to_tray(self):
        """隐藏到托盘"""
        self.panel.hide()
        self.tray.show_message("最小化", "程序已最小化到托盘")
    
    # 状态更新方法（供外部调用）
    
    def update_face_status(self, detected: bool, confidence: float = 0.0):
        """更新人脸检测状态"""
        self.panel.update_face_status(detected, confidence)
    
    def update_position(self, s_f: float):
        """更新头部位置"""
        self.panel.update_position(s_f)

    def _show_settings(self):
        """显示设置"""
        self.settings_requested.emit()


    def update_calibration_position(
        self,
        display_value: Optional[float],
        sample_value: Optional[float] = None,
    ):
        """更新标定采样用的头部位置"""
        if self.calibration_wizard and self.calibration_wizard.isVisible():
            self.calibration_wizard.update_position(display_value, sample_value)

    def update_fsm_state(self, state_name: str, is_scrolling: bool = False):
        """更新状态机状态"""
        self.panel.update_fsm_state(state_name, is_scrolling)
    
    def update_fps(self, fps: float):
        """更新 FPS"""
        self.panel.update_fps(fps)
    
    def set_running(self, running: bool):
        """设置运行状态"""
        self.tray.set_running(running)
    
    def set_paused(self, paused: bool):
        """设置暂停状态"""
        self.panel.set_paused(paused)
        self.tray.set_paused(paused)
    
    def show_error(self, title: str, message: str):
        """显示错误对话框"""
        QMessageBox.critical(self.panel, title, message)
    
    def show_info(self, title: str, message: str):
        """显示信息对话框"""
        QMessageBox.information(self.panel, title, message)
    
    @property
    def speed_value(self) -> int:
        """获取速度滑块值"""
        return self.panel.speed_value
