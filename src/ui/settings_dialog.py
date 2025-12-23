"""
M9: 设置对话框
用于切换控制模式
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QLineEdit,
    QKeySequenceEdit
)
from PySide6.QtCore import Qt
from .process_picker_dialog import ProcessPickerDialog
from .head_center_dialog import HeadCenterCalibrationDialog


class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self, config, host_window=None, parent=None):
        super().__init__(parent)
        self._config = config
        self._host_window = host_window
        self.setWindowTitle("设置")
        self.setModal(True)
        self.setMinimumSize(420, 360)
        self.resize(520, 420)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("控制模式")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel("模式:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("眼动(eye)", "eye")
        self.mode_combo.addItem("抬头/低头(head)", "head")
        row.addWidget(self.mode_combo)
        layout.addLayout(row)

        hint = QLabel("切换模式后请重新标定")
        hint.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(hint)

        self.auto_center_btn = QPushButton("自动校准中心")
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
        dialog = HeadCenterCalibrationDialog(self._config, self._host_window, self)
        if dialog.exec():
            self._load_from_config()

    def _load_from_config(self):
        mode = getattr(self._config.calibration, "mode", "eye")
        index = 0 if mode != "head" else 1
        self.mode_combo.setCurrentIndex(index)

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
        mode = self.mode_combo.currentData()
        self._config.calibration.mode = mode
        self._config.ui.hotkeys.toggle_pause = self.pause_hotkey_edit.keySequence().toString()
        self._config.injection.target = self.target_combo.currentData()
        self._config.injection.process_name = self.process_edit.text().strip() or None
        if not self._config.save():
            self.reject()
            return
        self.accept()
