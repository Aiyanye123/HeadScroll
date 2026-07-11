"""Settings for hand page turning and head scrolling."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QKeySequenceEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("控制设置")
        self.setMinimumSize(460, 620)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.mode = QComboBox()
        self.mode.addItem("手势左右翻页", "hand")
        self.mode.addItem("抬头/低头上下滚动", "head")
        form.addRow("控制模式:", self.mode)

        self.mirror = QCheckBox("按镜像画面解释左右方向")
        form.addRow("摄像头:", self.mirror)

        self.confidence = QDoubleSpinBox()
        self.confidence.setRange(0.5, 0.95)
        self.confidence.setSingleStep(0.05)
        form.addRow("最低识别置信度:", self.confidence)

        self.distance = QDoubleSpinBox()
        self.distance.setRange(0.08, 0.35)
        self.distance.setSingleStep(0.01)
        form.addRow("最小横向位移:", self.distance)

        self.arm_duration = QSpinBox()
        self.arm_duration.setRange(50, 1000)
        self.arm_duration.setSuffix(" ms")
        form.addRow("手掌稳定时间:", self.arm_duration)

        self.vertical_drift = QDoubleSpinBox()
        self.vertical_drift.setRange(0.03, 0.30)
        self.vertical_drift.setSingleStep(0.01)
        form.addRow("最大垂直漂移:", self.vertical_drift)

        self.min_speed = QDoubleSpinBox()
        self.min_speed.setRange(0.1, 2.0)
        self.min_speed.setSingleStep(0.05)
        form.addRow("最小挥动速度:", self.min_speed)

        self.consistency = QDoubleSpinBox()
        self.consistency.setRange(0.5, 1.0)
        self.consistency.setSingleStep(0.05)
        form.addRow("方向一致性:", self.consistency)

        self.cooldown = QSpinBox()
        self.cooldown.setRange(200, 2000)
        self.cooldown.setSuffix(" ms")
        form.addRow("翻页冷却时间:", self.cooldown)

        self.fist_hold = QSpinBox()
        self.fist_hold.setRange(300, 2000)
        self.fist_hold.setSuffix(" ms")
        form.addRow("握拳暂停时间:", self.fist_hold)

        self.previous_key = self._key_combo()
        self.next_key = self._key_combo()
        form.addRow("上一页按键:", self.previous_key)
        form.addRow("下一页按键:", self.next_key)

        self.scroll_speed = QDoubleSpinBox()
        self.scroll_speed.setRange(0.5, 10.0)
        self.scroll_speed.setSingleStep(0.5)
        form.addRow("头部最大滚动速度:", self.scroll_speed)

        self.head_trigger = QDoubleSpinBox()
        self.head_trigger.setRange(0.1, 0.9)
        self.head_trigger.setSingleStep(0.05)
        form.addRow("头部触发阈值:", self.head_trigger)

        self.head_release = QDoubleSpinBox()
        self.head_release.setRange(0.05, 0.85)
        self.head_release.setSingleStep(0.05)
        form.addRow("头部释放阈值:", self.head_release)

        self.pause_hotkey = QKeySequenceEdit()
        form.addRow("暂停/恢复快捷键:", self.pause_hotkey)
        self.stop_hotkey = QKeySequenceEdit()
        form.addRow("紧急停止快捷键:", self.stop_hotkey)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._load()

    @staticmethod
    def _key_combo() -> QComboBox:
        combo = QComboBox()
        for label, value in (
            ("← Left", "Left"),
            ("→ Right", "Right"),
            ("Page Up", "PageUp"),
            ("Page Down", "PageDown"),
        ):
            combo.addItem(label, value)
        return combo

    @staticmethod
    def _select(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(max(0, index))

    def _load(self) -> None:
        cfg = self._config.gesture
        self._select(self.mode, self._config.mode)
        self.mirror.setChecked(cfg.mirror)
        self.confidence.setValue(cfg.min_confidence)
        self.distance.setValue(cfg.min_swipe_distance)
        self.arm_duration.setValue(int(cfg.arm_duration_ms))
        self.vertical_drift.setValue(cfg.max_vertical_drift)
        self.min_speed.setValue(cfg.min_swipe_speed)
        self.consistency.setValue(cfg.direction_consistency)
        self.cooldown.setValue(int(cfg.cooldown_ms))
        self.fist_hold.setValue(int(cfg.fist_hold_ms))
        self._select(self.previous_key, cfg.previous_key)
        self._select(self.next_key, cfg.next_key)
        self.pause_hotkey.setKeySequence(self._config.ui.hotkeys.toggle_pause)
        self.stop_hotkey.setKeySequence(self._config.ui.hotkeys.emergency_stop)
        self.scroll_speed.setValue(self._config.scroll.v_max)
        self.head_trigger.setValue(self._config.thresholds.th_on)
        self.head_release.setValue(self._config.thresholds.th_off)

    def _save(self) -> None:
        if self.previous_key.currentData() == self.next_key.currentData():
            QMessageBox.warning(self, "设置无效", "上一页和下一页按键不能相同")
            return
        if self.head_release.value() >= self.head_trigger.value():
            QMessageBox.warning(self, "设置无效", "头部释放阈值必须小于触发阈值")
            return
        cfg = self._config.gesture
        self._config.config.mode = self.mode.currentData()
        cfg.mirror = self.mirror.isChecked()
        cfg.min_confidence = self.confidence.value()
        cfg.min_swipe_distance = self.distance.value()
        cfg.arm_duration_ms = self.arm_duration.value()
        cfg.max_vertical_drift = self.vertical_drift.value()
        cfg.min_swipe_speed = self.min_speed.value()
        cfg.direction_consistency = self.consistency.value()
        cfg.cooldown_ms = self.cooldown.value()
        cfg.fist_hold_ms = self.fist_hold.value()
        cfg.previous_key = self.previous_key.currentData()
        cfg.next_key = self.next_key.currentData()
        self._config.ui.hotkeys.toggle_pause = self.pause_hotkey.keySequence().toString()
        self._config.ui.hotkeys.emergency_stop = self.stop_hotkey.keySequence().toString()
        self._config.scroll.v_max = self.scroll_speed.value()
        self._config.thresholds.th_on = self.head_trigger.value()
        self._config.thresholds.th_off = self.head_release.value()
        if not self._config.save():
            QMessageBox.critical(self, "保存失败", "无法写入用户配置文件")
            return
        self.accept()
