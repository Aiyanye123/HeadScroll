"""
M9: 设置对话框
用于设置头部范围、快捷键和滚轮目标
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QLineEdit,
    QKeySequenceEdit, QMessageBox
)
from .process_picker_dialog import ProcessPickerDialog
from .head_center_dialog import HeadCenterCalibrationDialog


class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self, config, host_window=None, parent=None, *, camera_running=False):
        super().__init__(parent)
        self._config = config
        self._host_window = host_window
        self._camera_running = camera_running
        self.setWindowTitle("设置")
        self.setModal(True)
        self.setMinimumSize(420, 360)
        self.resize(520, 420)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        self.auto_center_btn = QPushButton("校准头部范围")
        self.auto_center_btn.clicked.connect(self._auto_calibrate_center)
        layout.addWidget(self.auto_center_btn)

        layout.addWidget(QLabel("快捷键"))
        hotkey_row = QHBoxLayout()
        hotkey_row.setSpacing(8)
        hotkey_row.addWidget(QLabel("暂停/恢复:"))
        self.pause_hotkey_edit = QKeySequenceEdit()
        hotkey_row.addWidget(self.pause_hotkey_edit)
        layout.addLayout(hotkey_row)

        layout.addWidget(QLabel("滚轮发送目标"))
        target_row = QHBoxLayout()
        target_row.setSpacing(8)
        target_row.addWidget(QLabel("目标:"))
        self.target_combo = QComboBox()
        self.target_combo.addItem("鼠标所在窗口", "cursor")
        self.target_combo.addItem("前台窗口", "foreground")
        self.target_combo.addItem("指定进程", "process")
        target_row.addWidget(self.target_combo)
        layout.addLayout(target_row)

        process_row = QHBoxLayout()
        process_row.setSpacing(8)
        process_row.addWidget(QLabel("进程名:"))
        self.process_edit = QLineEdit()
        self.process_edit.setPlaceholderText("例如 chrome.exe")
        process_row.addWidget(self.process_edit)
        self.pick_process_btn = QPushButton("选择")
        self.pick_process_btn.clicked.connect(self._pick_process)
        process_row.addWidget(self.pick_process_btn)
        layout.addLayout(process_row)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.save_btn = QPushButton("保存")
        self.cancel_btn = QPushButton("取消")
        self.save_btn.clicked.connect(self._on_save)
        self.cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        self._load_from_config()

    def _pick_process(self):
        dialog = ProcessPickerDialog(self)
        if dialog.exec() and dialog.selected_process:
            self.process_edit.setText(dialog.selected_process)

    def _auto_calibrate_center(self):
        if not self._camera_running:
            QMessageBox.information(self, "头部范围校准", "请先启动摄像头，再校准头部范围。")
            return
        dialog = HeadCenterCalibrationDialog(self._config, self._host_window, self)
        dialog.exec()

    def _load_from_config(self):
        pause_hotkey = getattr(self._config.ui.hotkeys, "toggle_pause", "Ctrl+Shift+Space")
        self.pause_hotkey_edit.setKeySequence(pause_hotkey)

        target = getattr(self._config.injection, "target", "cursor")
        target_index = 0
        if target == "foreground":
            target_index = 1
        elif target == "process":
            target_index = 2
        self.target_combo.setCurrentIndex(target_index)

        process_name = getattr(self._config.injection, "process_name", "") or ""
        self.process_edit.setText(process_name)

    def _on_save(self):
        self._config.ui.hotkeys.toggle_pause = self.pause_hotkey_edit.keySequence().toString()
        self._config.injection.target = self.target_combo.currentData()
        self._config.injection.process_name = self.process_edit.text().strip() or None
        if not self._config.save():
            self.reject()
            return
        self.accept()
