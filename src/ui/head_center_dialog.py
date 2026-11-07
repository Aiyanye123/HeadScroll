"""Record a head range from two fresh endpoint measurements."""

import math
import time

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from calibration import Calibrator


class HeadCenterCalibrationDialog(QDialog):
    def __init__(self, host_window, max_age: float, parent=None):
        super().__init__(parent)
        self._host_window = host_window
        self._max_age = max_age
        self._current_pitch = None
        self._pitch_timestamp = 0.0
        self._up_pitch = None
        self._down_pitch = None
        self.reference = None
        self.setWindowTitle("校准头部范围")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("抬头后记录上限，再低头记录下限。"))
        self.current_label = QLabel("等待有效头部姿态")
        layout.addWidget(self.current_label)
        row = QHBoxLayout()
        up = QPushButton("记录抬头")
        down = QPushButton("记录低头")
        up.clicked.connect(self._capture_up)
        down.clicked.connect(self._capture_down)
        row.addWidget(up)
        row.addWidget(down)
        layout.addLayout(row)
        self.result_label = QLabel("中心: --")
        self.result_label.setWordWrap(True)
        layout.addWidget(self.result_label)
        actions = QHBoxLayout()
        self.save_btn = QPushButton("使用范围")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.accept)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        actions.addWidget(self.save_btn)
        actions.addWidget(cancel)
        layout.addLayout(actions)
        host_window.head_pitch_updated.connect(self._on_pitch_update)

    def _on_pitch_update(self, pitch: float, timestamp: float):
        self._current_pitch = pitch if math.isfinite(pitch) else None
        self._pitch_timestamp = timestamp
        self.current_label.setText(
            f"当前角度: {pitch:.4f} rad" if self._current_pitch is not None
            else "未检测到有效头部姿态"
        )

    def _has_current_pitch(self):
        if (
            self._current_pitch is None
            or not 0 <= time.perf_counter() - self._pitch_timestamp <= self._max_age
        ):
            self.current_label.setText("未检测到有效头部姿态")
            return False
        return True

    def _capture_up(self):
        if self._has_current_pitch():
            self._up_pitch = self._current_pitch
            self._update_result()

    def _capture_down(self):
        if self._has_current_pitch():
            self._down_pitch = self._current_pitch
            self._update_result()

    def _update_result(self):
        if self._up_pitch is None or self._down_pitch is None:
            return
        middle = (self._up_pitch + self._down_pitch) / 2
        error = Calibrator.head_reference_error(self._up_pitch, middle, self._down_pitch)
        self.save_btn.setEnabled(not error)
        self.reference = None if error else (self._up_pitch, middle, self._down_pitch)
        self.result_label.setText(error or f"中心: {middle:.4f} rad")

    def done(self, result):
        self._host_window.head_pitch_updated.disconnect(self._on_pitch_update)
        super().done(result)
