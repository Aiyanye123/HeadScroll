"""
M9: 悬浮控制面板
轻量级悬浮窗，显示状态和控制按钮
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QProgressBar, QSlider, QGroupBox
)
from PySide6.QtCore import Qt, Signal

from .styles import COLORS


class FloatingPanel(QWidget):
    """悬浮控制面板"""

    # 信号
    start_clicked = Signal()
    stop_clicked = Signal()
    pause_clicked = Signal()
    calibrate_clicked = Signal()
    settings_clicked = Signal()
    speed_changed = Signal(int)

    def __init__(self, always_on_top: bool = True):
        super().__init__()
        self._setup_ui()
        self._is_running = False
        self._is_paused = False

        # 窗口属性
        self.setWindowTitle("眼动滚动控制")
        flags = Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint if always_on_top else Qt.WindowType.Window
        flags |= Qt.WindowType.WindowCloseButtonHint
        self.setWindowFlags(flags)
        self.setFixedWidth(300)

    def _setup_ui(self):
        """构建 UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # 状态区
        status_group = QGroupBox("状态")
        status_layout = QVBoxLayout(status_group)
        status_layout.setSpacing(8)

        face_row = QHBoxLayout()
        face_label = QLabel("人脸检测")
        face_label.setProperty("class", "secondary")
        face_row.addWidget(face_label)
        self.face_status = QLabel("--")
        self.face_status.setStyleSheet("font-weight: 600;")
        face_row.addStretch()
        face_row.addWidget(self.face_status)
        status_layout.addLayout(face_row)

        gaze_row = QHBoxLayout()
        gaze_label = QLabel("注视位置")
        gaze_label.setProperty("class", "secondary")
        gaze_row.addWidget(gaze_label)
        self.gaze_bar = QProgressBar()
        self.gaze_bar.setRange(0, 100)
        self.gaze_bar.setValue(50)
        self.gaze_bar.setTextVisible(False)
        self.gaze_bar.setFixedHeight(8)
        gaze_row.addWidget(self.gaze_bar, 1)
        status_layout.addLayout(gaze_row)

        fsm_row = QHBoxLayout()
        fsm_label = QLabel("滚动状态")
        fsm_label.setProperty("class", "secondary")
        fsm_row.addWidget(fsm_label)
        self.fsm_status = QLabel("IDLE")
        self.fsm_status.setStyleSheet("font-weight: 600;")
        fsm_row.addStretch()
        fsm_row.addWidget(self.fsm_status)
        status_layout.addLayout(fsm_row)

        fps_row = QHBoxLayout()
        fps_label = QLabel("FPS")
        fps_label.setProperty("class", "secondary")
        fps_row.addWidget(fps_label)
        self.fps_label = QLabel("--")
        fps_row.addStretch()
        fps_row.addWidget(self.fps_label)
        status_layout.addLayout(fps_row)

        layout.addWidget(status_group)

        # 控制按钮
        control_group = QGroupBox("控制")
        control_layout = QHBoxLayout(control_group)
        control_layout.setSpacing(8)

        self.start_btn = QPushButton("启动")
        self.start_btn.setCheckable(True)
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.clicked.connect(self._on_start_clicked)
        control_layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._on_pause_clicked)
        control_layout.addWidget(self.pause_btn)

        layout.addWidget(control_group)

        # 工具按钮
        tool_group = QGroupBox("工具")
        tool_layout = QHBoxLayout(tool_group)
        tool_layout.setSpacing(8)

        self.calibrate_btn = QPushButton("标定")
        self.calibrate_btn.clicked.connect(self.calibrate_clicked.emit)
        tool_layout.addWidget(self.calibrate_btn)

        self.settings_btn = QPushButton("设置")
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        tool_layout.addWidget(self.settings_btn)

        layout.addWidget(tool_group)

        # 滚动速度
        speed_group = QGroupBox("滚动速度")
        speed_layout = QHBoxLayout(speed_group)
        speed_layout.setSpacing(8)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 10)
        self.speed_slider.setValue(5)
        speed_layout.addWidget(self.speed_slider, 1)

        self.speed_label = QLabel("5")
        self.speed_label.setMinimumWidth(16)
        speed_layout.addWidget(self.speed_label)

        self.speed_slider.valueChanged.connect(
            lambda v: self.speed_label.setText(str(v))
        )
        self.speed_slider.valueChanged.connect(self.speed_changed.emit)

        layout.addWidget(speed_group)

    def _on_start_clicked(self):
        """启动/停止按钮点击"""
        if self.start_btn.isChecked():
            self.start_btn.setText("停止")
            self.pause_btn.setEnabled(True)
            self._is_running = True
            self.start_clicked.emit()
        else:
            self.start_btn.setText("启动")
            self.pause_btn.setEnabled(False)
            self._is_running = False
            self.stop_clicked.emit()

    def _on_pause_clicked(self):
        """暂停/恢复按钮点击"""
        self._is_paused = not self._is_paused
        if self._is_paused:
            self.pause_btn.setText("恢复")
        else:
            self.pause_btn.setText("暂停")
        self.pause_clicked.emit()

    def update_face_status(self, detected: bool, confidence: float = 0.0):
        """更新人脸检测状态"""
        if detected:
            self.face_status.setText(f"已检测 ({confidence:.0%})")
            self.face_status.setStyleSheet(f"font-weight: 600; color: {COLORS['success']};")
        else:
            self.face_status.setText("未检测")
            self.face_status.setStyleSheet(f"font-weight: 600; color: {COLORS['danger']};")

    def update_gaze(self, s_f: float):
        """更新注视位置"""
        self.gaze_bar.setValue(int(s_f * 100))

    def update_fsm_state(self, state_name: str, is_scrolling: bool = False):
        """更新状态机状态"""
        self.fsm_status.setText(state_name)
        if is_scrolling:
            self.fsm_status.setStyleSheet(f"font-weight: 600; color: {COLORS['primary']};")
        else:
            self.fsm_status.setStyleSheet(f"font-weight: 600; color: {COLORS['text_secondary']};")

    def update_fps(self, fps: float):
        """更新 FPS"""
        self.fps_label.setText(f"{fps:.1f}")

    def set_paused(self, paused: bool):
        """设置暂停状态"""
        self._is_paused = paused
        self.pause_btn.setText("恢复" if paused else "暂停")

    @property
    def speed_value(self) -> int:
        """获取速度滑块值"""
        return self.speed_slider.value()
