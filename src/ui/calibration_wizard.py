"""
M9: 标定向导界面
引导用户完成三点标定
"""

from typing import Optional
import math

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QPainter, QColor, QPen

from .styles import COLORS
from calibration import Calibrator


class PositionIndicator(QFrame):
    """头部位置指示器"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 200)
        self._position = 0.5  # 0=上, 1=下
        self._target_position = 0.5
        self._show_target = False
    
    def set_position(self, pos: float):
        """设置当前位置"""
        self._position = max(0.0, min(1.0, pos))
        self.update()
    
    def set_target(self, pos: float, show: bool = True):
        """设置目标位置"""
        self._target_position = pos
        self._show_target = show
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 绘制背景
        painter.fillRect(self.rect(), QColor(COLORS["surface"]))
        
        # 绘制边框
        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        
        # 绘制目标区域
        if self._show_target:
            target_y = int(self._target_position * (self.height() - 20)) + 10
            target_color = QColor(COLORS["success"])
            target_color.setAlpha(60)
            painter.fillRect(5, target_y - 15, self.width() - 10, 30, target_color)
        
        # 绘制当前位置
        current_y = int(self._position * (self.height() - 20)) + 10
        painter.setBrush(QColor(COLORS["primary"]))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(self.width() // 2 - 8, current_y - 8, 16, 16)


class CalibrationWizard(QDialog):
    """标定向导对话框"""
    
    # 信号
    calibration_complete = Signal(float, float, float)  # r_top, r_mid, r_bottom
    calibration_cancelled = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("标定向导")
        self.setModal(True)
        self.setFixedSize(400, 450)
        
        self._current_step = 0
        self._samples = {"top": [], "mid": [], "bottom": []}
        self._sample_timer = QTimer(self)
        self._sample_timer.timeout.connect(self._on_sample_timeout)
        self._step_timer = QTimer(self)
        self._step_timer.setSingleShot(True)
        self._step_timer.timeout.connect(self._start_step)
        self._finish_timer = QTimer(self)
        self._finish_timer.setSingleShot(True)
        self._finish_timer.timeout.connect(self.accept)
        
        self._setup_ui()

    def _setup_ui(self):
        """构建 UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        
        # 标题
        title = QLabel("三点标定")
        title.setFont(QFont("", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 说明
        self.instruction = QLabel(
            "请按照提示抬头、保持自然姿势、低头。\n"
            "每个位置需要保持 1.5 秒。"
        )
        self.instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.instruction.setWordWrap(True)
        layout.addWidget(self.instruction)
        
        # 指示器区域
        indicator_layout = QHBoxLayout()
        indicator_layout.addStretch()
        
        self.indicator = PositionIndicator()
        indicator_layout.addWidget(self.indicator)
        
        indicator_layout.addStretch()
        layout.addLayout(indicator_layout)
        
        # 步骤提示
        self.step_label = QLabel("步骤 1/3: 请抬头")
        self.step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.step_label.setFont(QFont("", 12))
        layout.addWidget(self.step_label)
        
        # 进度条
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        
        # 状态文本
        self.status_label = QLabel("点击开始按钮开始标定")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("开始")
        self.start_btn.clicked.connect(self._start_calibration)
        btn_layout.addWidget(self.start_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self._cancel)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
    
    def _start_calibration(self):
        """开始标定"""
        self._current_step = 0
        self._samples = {"top": [], "mid": [], "bottom": []}
        
        self.start_btn.setEnabled(False)
        self._start_step()
    
    def _start_step(self):
        """开始当前步骤"""
        steps = [
            ("top", 0.15, "步骤 1/3: 请抬头"),
            ("mid", 0.5, "步骤 2/3: 请保持自然姿势"),
            ("bottom", 0.85, "步骤 3/3: 请低头"),
        ]
        
        if self._current_step >= len(steps):
            self._finish_calibration()
            return
        
        key, target_pos, label = steps[self._current_step]
        
        self.step_label.setText(label)
        self.indicator.set_target(target_pos, True)
        self.progress.setValue(0)
        self.status_label.setText("请保持姿势...")
        
        # 开始采样计时
        self._sample_start_time = 0
        self._current_key = key
        self._sample_timer.start(50)  # 50ms 采样间隔
    
    def _on_sample_timeout(self):
        """采样定时器回调"""
        self._sample_start_time += 50
        
        # 更新进度
        progress = min(100, int(self._sample_start_time / 1500 * 100))
        self.progress.setValue(progress)
        
        # 采样完成
        if self._sample_start_time >= 1500:
            self._sample_timer.stop()
            self._current_step += 1
            
            # 短暂延迟后进入下一步
            self._step_timer.start(300)
    
    def update_position(self, position: Optional[float], sample_value: Optional[float] = None):
        """更新头部位置（由外部调用）"""
        value = position if sample_value is None else sample_value
        if position is None or value is None or not math.isfinite(position) or not math.isfinite(value):
            if self._sample_timer.isActive():
                self.status_label.setText("未检测到有效人脸，请回到摄像头前")
            return
        self.indicator.set_position(position)
        
        # 添加采样（丢弃前 300ms）
        if self._sample_timer.isActive() and self._sample_start_time >= 300:
            self.status_label.setText("请保持姿势...")
            self._samples[self._current_key].append(value)
    
    def _finish_calibration(self):
        """完成标定"""
        import numpy as np
        
        self.indicator.set_target(0.5, False)
        
        # 计算各位置的参考值
        def compute_ref(values):
            if len(values) < 5:
                return None
            arr = np.array(values)
            lower = np.percentile(arr, 10)
            upper = np.percentile(arr, 90)
            trimmed = arr[(arr >= lower) & (arr <= upper)]
            return float(np.mean(trimmed)) if len(trimmed) > 0 else float(np.median(arr))
        
        r_top = compute_ref(self._samples["top"])
        r_mid = compute_ref(self._samples["mid"])
        r_bottom = compute_ref(self._samples["bottom"])
        
        if r_top is None or r_mid is None or r_bottom is None:
            self.status_label.setText("标定失败：采样数据不足")
            self.start_btn.setEnabled(True)
            return
        
        error_message = Calibrator.reference_error(r_top, r_mid, r_bottom)
        if error_message:
            self.status_label.setText(f"标定失败：{error_message}")
            self.start_btn.setEnabled(True)
            return
        
        self.status_label.setText("标定完成！")
        self.step_label.setText(f"参考值: 上={r_top:.2f}, 中={r_mid:.2f}, 下={r_bottom:.2f}")
        
        self.calibration_complete.emit(r_top, r_mid, r_bottom)
        
        self._finish_timer.start(1500)
    
    def _cancel(self):
        """取消标定"""
        self.reject()

    def done(self, result):
        self._sample_timer.stop()
        self._step_timer.stop()
        self._finish_timer.stop()
        if result != QDialog.DialogCode.Accepted:
            self.calibration_cancelled.emit()
        super().done(result)
