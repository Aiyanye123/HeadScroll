"""Compact hand-gesture page-turn panel."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .styles import COLORS


class FloatingPanel(QWidget):
    start_clicked = Signal()
    stop_clicked = Signal()
    pause_clicked = Signal()
    calibrate_clicked = Signal()
    settings_clicked = Signal()
    sensitivity_changed = Signal(int)

    def __init__(self, always_on_top: bool = True):
        super().__init__()
        self._setup_ui()
        self.setWindowTitle("手势翻页控制")
        flags = Qt.WindowType.Window
        if always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags | Qt.WindowType.WindowCloseButtonHint)
        self.setFixedWidth(320)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        status_group = QGroupBox("状态")
        status_layout = QVBoxLayout(status_group)
        self.mode_status = self._add_status_row(status_layout, "控制模式", "手势翻页")
        self.hand_status = self._add_status_row(status_layout, "手部检测", "--")
        self.gesture_status = self._add_status_row(status_layout, "识别状态", "WAITING")
        self.action_status = self._add_status_row(status_layout, "最近动作", "--")
        self.fps_label = self._add_status_row(status_layout, "FPS", "--")
        palm_row = QHBoxLayout()
        palm_row.addWidget(QLabel("掌心位置"))
        self.palm_bar = QProgressBar()
        self.palm_bar.setRange(0, 100)
        self.palm_bar.setValue(50)
        self.palm_bar.setTextVisible(False)
        self.palm_bar.setFixedHeight(8)
        palm_row.addWidget(self.palm_bar, 1)
        status_layout.addLayout(palm_row)
        layout.addWidget(status_group)

        control_group = QGroupBox("控制")
        control_layout = QHBoxLayout(control_group)
        self.start_btn = QPushButton("启动")
        self.start_btn.setCheckable(True)
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.clicked.connect(self._toggle_running)
        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.pause_clicked.emit)
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.pause_btn)
        layout.addWidget(control_group)

        self.sensitivity_group = QGroupBox("手势灵敏度")
        sensitivity_layout = QHBoxLayout(self.sensitivity_group)
        self.sensitivity_slider = QSlider(Qt.Orientation.Horizontal)
        self.sensitivity_slider.setRange(1, 10)
        self.sensitivity_slider.setValue(5)
        self.sensitivity_value = QLabel("5")
        self.sensitivity_slider.valueChanged.connect(
            lambda value: self.sensitivity_value.setText(str(value))
        )
        self.sensitivity_slider.valueChanged.connect(self.sensitivity_changed.emit)
        sensitivity_layout.addWidget(self.sensitivity_slider, 1)
        sensitivity_layout.addWidget(self.sensitivity_value)
        layout.addWidget(self.sensitivity_group)

        tools = QHBoxLayout()
        self.calibrate_btn = QPushButton("头部标定")
        self.calibrate_btn.clicked.connect(self.calibrate_clicked.emit)
        tools.addWidget(self.calibrate_btn)
        self.settings_btn = QPushButton("设置")
        self.settings_btn.clicked.connect(self.settings_clicked.emit)
        tools.addWidget(self.settings_btn)
        layout.addLayout(tools)

    @staticmethod
    def _add_status_row(layout: QVBoxLayout, name: str, value: str) -> QLabel:
        row = QHBoxLayout()
        row.addWidget(QLabel(name))
        row.addStretch()
        label = QLabel(value)
        label.setStyleSheet("font-weight: 600;")
        row.addWidget(label)
        layout.addLayout(row)
        return label

    def _toggle_running(self, checked: bool) -> None:
        if checked:
            self.start_clicked.emit()
        else:
            self.stop_clicked.emit()

    def set_running(self, running: bool) -> None:
        self.start_btn.setChecked(running)
        self.start_btn.setText("停止" if running else "启动")
        self.pause_btn.setEnabled(running)
        if not running:
            self.set_paused(False)

    def set_paused(self, paused: bool) -> None:
        self.pause_btn.setText("恢复" if paused else "暂停")

    def set_mode(self, mode: str) -> None:
        is_head = mode == "head"
        self.mode_status.setText("头部滚动" if is_head else "手势翻页")
        self.calibrate_btn.setEnabled(is_head)
        self.sensitivity_group.setTitle("滚动速度" if is_head else "手势灵敏度")
        self.action_status.setText("--")

    def update_hand_status(
        self,
        present: bool,
        gesture: str,
        confidence: float,
        handedness: str,
    ) -> None:
        if present:
            hand = f"{handedness} " if handedness else ""
            self.hand_status.setText(f"{hand}{gesture} {confidence:.0%}")
            self.hand_status.setStyleSheet(f"font-weight: 600; color: {COLORS['success']};")
        else:
            self.hand_status.setText("未检测")
            self.hand_status.setStyleSheet(f"font-weight: 600; color: {COLORS['danger']};")

    def update_palm(self, palm_x: float | None) -> None:
        self.palm_bar.setValue(50 if palm_x is None else int(palm_x * 100))

    def update_gesture_state(self, state: str) -> None:
        self.gesture_status.setText(state)

    def update_last_action(self, action: str) -> None:
        self.action_status.setText(action)

    def update_fps(self, fps: float) -> None:
        self.fps_label.setText(f"{fps:.1f}")

    def update_detection(
        self, present: bool, label: str, confidence: float
    ) -> None:
        self.update_hand_status(present, label, confidence, "")

    def update_position(self, position: float | None) -> None:
        self.update_palm(position)

    def update_control_state(self, state: str) -> None:
        self.update_gesture_state(state)
