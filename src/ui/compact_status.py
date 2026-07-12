"""Compact status window shown while the full control panel is hidden."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .styles import COLORS


class CompactStatusWindow(QWidget):
    restore_requested = Signal()

    def __init__(self, always_on_top: bool = True) -> None:
        super().__init__()
        self._always_on_top = always_on_top
        self._setup_ui()
        self.setWindowTitle("HeadScroll 状态")
        self.setFixedWidth(300)
        self._apply_window_flags()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("HeadScroll")
        title.setStyleSheet("font-size: 11pt; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()

        self.pin_btn = QPushButton("置顶")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setChecked(self._always_on_top)
        self.pin_btn.setToolTip("保持窗口显示在其他窗口上方")
        self.pin_btn.setFixedHeight(28)
        self.pin_btn.toggled.connect(self.set_always_on_top)
        header.addWidget(self.pin_btn)

        restore_btn = QPushButton("完整面板")
        restore_btn.setToolTip("恢复完整控制面板")
        restore_btn.setFixedHeight(28)
        restore_btn.clicked.connect(self.restore_requested.emit)
        header.addWidget(restore_btn)
        layout.addLayout(header)

        self.mode_status = self._add_status_row(layout, "模式", "语音翻页")
        self.detection_status = self._add_status_row(layout, "识别", "--")
        self.control_status = self._add_status_row(layout, "状态", "WAITING")
        self.action_status = self._add_status_row(layout, "动作", "--")
        self.fps_label = self._add_status_row(layout, "FPS", "--")

        position_row = QHBoxLayout()
        self.position_label = QLabel("位置")
        position_row.addWidget(self.position_label)
        self.position_bar = QProgressBar()
        self.position_bar.setRange(0, 100)
        self.position_bar.setValue(50)
        self.position_bar.setTextVisible(False)
        self.position_bar.setFixedHeight(7)
        position_row.addWidget(self.position_bar, 1)
        layout.addLayout(position_row)

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

    def _apply_window_flags(self) -> None:
        flags = Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint
        flags |= Qt.WindowType.WindowMinimizeButtonHint
        if self._always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def set_always_on_top(self, enabled: bool) -> None:
        if enabled == self._always_on_top:
            return
        was_visible = self.isVisible()
        position = self.pos()
        self._always_on_top = enabled
        self._apply_window_flags()
        if was_visible:
            self.move(position)
            self.show()

    def set_mode(self, mode: str) -> None:
        is_head = mode == "head"
        self.mode_status.setText("头部滚动" if is_head else "语音翻页")
        self.position_label.setVisible(is_head)
        self.position_bar.setVisible(is_head)

    def update_detection(self, present: bool, label: str, confidence: float) -> None:
        if present:
            self.detection_status.setText(f"{label} {confidence:.0%}")
            color = COLORS["success"]
        else:
            self.detection_status.setText("未检测")
            color = COLORS["danger"]
        self.detection_status.setStyleSheet(f"font-weight: 600; color: {color};")

    def update_transcript(self, transcript: str) -> None:
        self.detection_status.setText(transcript or "--")
        self.detection_status.setStyleSheet(
            f"font-weight: 600; color: {COLORS['success']};"
        )

    def update_position(self, position: float | None) -> None:
        self.position_bar.setValue(50 if position is None else int(position * 100))

    def update_control_state(self, state: str) -> None:
        self.control_status.setText(state)

    def update_last_action(self, action: str) -> None:
        self.action_status.setText(action)

    def update_fps(self, fps: float) -> None:
        self.fps_label.setText(f"{fps:.1f}")
