"""
M9: 头部中心校准对话框
"""

from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PySide6.QtCore import Qt


class HeadCenterCalibrationDialog(QDialog):
    """头部中心校准对话框"""

    def __init__(self, config, host_window, parent=None):
        super().__init__(parent)
        self._config = config
        self._host_window = host_window
        self._current_pitch: Optional[float] = None
        self._up_pitch: Optional[float] = None
        self._down_pitch: Optional[float] = None

        self.setWindowTitle("自动校准中心")
        self.setModal(True)
        self.setFixedSize(360, 220)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.info_label = QLabel("请抬头到最高处，点击‘记录抬头’，\n再低头到最低处，点击‘记录低头’。")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.info_label)

        self.current_label = QLabel("当前 head_pitch: --")
        layout.addWidget(self.current_label)

        btn_row = QHBoxLayout()
        self.capture_up_btn = QPushButton("记录抬头")
        self.capture_down_btn = QPushButton("记录低头")
        self.capture_up_btn.clicked.connect(self._capture_up)
        self.capture_down_btn.clicked.connect(self._capture_down)
        btn_row.addWidget(self.capture_up_btn)
        btn_row.addWidget(self.capture_down_btn)
        layout.addLayout(btn_row)

        self.result_label = QLabel("中心: --")
        layout.addWidget(self.result_label)

        action_row = QHBoxLayout()
        action_row.addStretch()
        self.save_btn = QPushButton("保存")
        self.cancel_btn = QPushButton("取消")
        self.save_btn.clicked.connect(self._on_save)
        self.cancel_btn.clicked.connect(self.reject)
        action_row.addWidget(self.save_btn)
        action_row.addWidget(self.cancel_btn)
        layout.addLayout(action_row)

        # 连接实时数据
        if self._host_window is not None:
            self._host_window.head_pitch_updated.connect(self._on_pitch_update)

    def _on_pitch_update(self, pitch: float):
        self._current_pitch = pitch
        self.current_label.setText(f"当前 head_pitch: {pitch:.4f}")

    def _capture_up(self):
        if self._current_pitch is None:
            return
        self._up_pitch = self._current_pitch
        self._update_result()

    def _capture_down(self):
        if self._current_pitch is None:
            return
        self._down_pitch = self._current_pitch
        self._update_result()

    def _update_result(self):
        if self._up_pitch is None or self._down_pitch is None:
            return
        center = (self._up_pitch + self._down_pitch) / 2.0
        self.result_label.setText(f"中心: {center:.4f}")

    def _on_save(self):
        if self._up_pitch is None or self._down_pitch is None:
            return
        center = (self._up_pitch + self._down_pitch) / 2.0
        self._config.calibration.head_pitch_center = center
        if not self._config.save():
            self.reject()
            return
        self.accept()

    def closeEvent(self, event):
        if self._host_window is not None:
            try:
                self._host_window.head_pitch_updated.disconnect(self._on_pitch_update)
            except TypeError:
                pass
        super().closeEvent(event)
