"""Settings for voice page turning and head scrolling."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QKeySequenceEdit,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("控制设置")
        self.setMinimumSize(500, 580)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.mode = QComboBox()
        self.mode.addItem("语音左右翻页", "voice")
        self.mode.addItem("抬头/低头上下滚动", "head")
        form.addRow("控制模式:", self.mode)

        model_row = QHBoxLayout()
        self.model_path = QLineEdit()
        self.model_path.setPlaceholderText("留空使用内置中文模型")
        pick = QPushButton("选择")
        pick.clicked.connect(self._pick_model)
        model_row.addWidget(self.model_path)
        model_row.addWidget(pick)
        form.addRow("语音模型目录:", model_row)

        self.device = QComboBox()
        self.device.addItem("系统默认麦克风", None)
        try:
            import sounddevice as sd

            for index, info in enumerate(sd.query_devices()):
                if info["max_input_channels"] > 0:
                    self.device.addItem(f"{index}: {info['name']}", index)
        except Exception:
            pass
        form.addRow("麦克风:", self.device)
        self.require_wake = QCheckBox("必须先说唤醒词")
        form.addRow("防误触:", self.require_wake)
        self.latency_mode = QComboBox()
        self.latency_mode.addItem("均衡（推荐）", "balanced")
        self.latency_mode.addItem("快速", "fast")
        self.latency_mode.addItem("准确", "accurate")
        form.addRow("响应速度:", self.latency_mode)
        self.wake_words = QLineEdit()
        form.addRow("唤醒词:", self.wake_words)
        self.previous_phrases = QLineEdit()
        form.addRow("上一页指令:", self.previous_phrases)
        self.next_phrases = QLineEdit()
        form.addRow("下一页指令:", self.next_phrases)
        self.pause_phrases = QLineEdit()
        form.addRow("暂停指令:", self.pause_phrases)
        self.resume_phrases = QLineEdit()
        form.addRow("恢复指令:", self.resume_phrases)
        self.cooldown = QSpinBox()
        self.cooldown.setRange(200, 3000)
        self.cooldown.setSuffix(" ms")
        form.addRow("翻页冷却时间:", self.cooldown)
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
        for label, value in (("← Left", "Left"), ("→ Right", "Right"),
                             ("Page Up", "PageUp"), ("Page Down", "PageDown")):
            combo.addItem(label, value)
        return combo

    @staticmethod
    def _select(combo: QComboBox, value: str) -> None:
        combo.setCurrentIndex(max(0, combo.findData(value)))

    @staticmethod
    def _phrases(text: str) -> list[str]:
        return [item.strip() for item in text.replace("，", ",").split(",") if item.strip()]

    def _pick_model(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择 Vosk 模型目录")
        if path:
            self.model_path.setText(path)

    def _load(self) -> None:
        voice = self._config.voice
        self._select(self.mode, self._config.mode)
        self.model_path.setText(voice.model_path or "")
        self._select(self.device, voice.device)
        self.require_wake.setChecked(voice.require_wake_word)
        self._select(self.latency_mode, voice.latency_mode)
        for widget, values in (
            (self.wake_words, voice.wake_words),
            (self.previous_phrases, voice.previous_phrases),
            (self.next_phrases, voice.next_phrases),
            (self.pause_phrases, voice.pause_phrases),
            (self.resume_phrases, voice.resume_phrases),
        ):
            widget.setText("，".join(values))
        self.cooldown.setValue(int(voice.cooldown_ms))
        self._select(self.previous_key, voice.previous_key)
        self._select(self.next_key, voice.next_key)
        self.scroll_speed.setValue(self._config.scroll.v_max)
        self.head_trigger.setValue(self._config.thresholds.th_on)
        self.head_release.setValue(self._config.thresholds.th_off)
        self.pause_hotkey.setKeySequence(self._config.ui.hotkeys.toggle_pause)
        self.stop_hotkey.setKeySequence(self._config.ui.hotkeys.emergency_stop)

    def _save(self) -> None:
        groups = [self._phrases(widget.text()) for widget in (
            self.previous_phrases, self.next_phrases, self.pause_phrases, self.resume_phrases
        )]
        if any(not group for group in groups):
            QMessageBox.warning(self, "设置无效", "四组语音指令都不能为空")
            return
        if self.require_wake.isChecked() and not self._phrases(self.wake_words.text()):
            QMessageBox.warning(self, "设置无效", "启用唤醒词后必须填写唤醒词")
            return
        if self.previous_key.currentData() == self.next_key.currentData():
            QMessageBox.warning(self, "设置无效", "上一页和下一页按键不能相同")
            return
        if self.head_release.value() >= self.head_trigger.value():
            QMessageBox.warning(self, "设置无效", "头部释放阈值必须小于触发阈值")
            return
        voice = self._config.voice
        self._config.config.mode = self.mode.currentData()
        voice.model_path = self.model_path.text().strip() or None
        voice.device = self.device.currentData()
        voice.require_wake_word = self.require_wake.isChecked()
        voice.latency_mode = self.latency_mode.currentData()
        voice.wake_words = self._phrases(self.wake_words.text())
        (voice.previous_phrases, voice.next_phrases,
         voice.pause_phrases, voice.resume_phrases) = groups
        voice.cooldown_ms = self.cooldown.value()
        voice.previous_key = self.previous_key.currentData()
        voice.next_key = self.next_key.currentData()
        self._config.scroll.v_max = self.scroll_speed.value()
        self._config.thresholds.th_on = self.head_trigger.value()
        self._config.thresholds.th_off = self.head_release.value()
        self._config.ui.hotkeys.toggle_pause = self.pause_hotkey.keySequence().toString()
        self._config.ui.hotkeys.emergency_stop = self.stop_hotkey.keySequence().toString()
        if not self._config.save():
            QMessageBox.critical(self, "保存失败", "无法写入用户配置文件")
            return
        self.accept()
