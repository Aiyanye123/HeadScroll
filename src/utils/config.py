"""Validated, atomic application configuration."""

import json
import logging
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class CameraConfig:
    index: int = 0
    width: int = 640
    height: int = 480
    target_fps: int = 30


@dataclass
class CalibrationConfig:
    r_top: float = -0.12
    r_mid: float = 0.0
    r_bottom: float = 0.12
    timestamp: Optional[str] = None
    pose_source: str = "matrix"


@dataclass
class FilterConfig:
    ema_alpha: float = 0.75
    confidence_min: float = 0.4
    lost_face_timeout_ms: float = 500


@dataclass
class ThresholdsConfig:
    th_on: float = 0.45
    th_off: float = 0.35
    dwell_on_ms: float = 120
    dwell_off_ms: float = 80


@dataclass
class ScrollConfig:
    v_max: float = 3.0
    gamma: float = 1.8
    a_up: float = 8.0
    a_down: float = 16.0
    tick_hz: float = 90


@dataclass
class BlinkConfig:
    long_blink_ms: float = 900
    cooldown_ms: float = 2000


@dataclass
class HotkeysConfig:
    toggle_pause: str = "Ctrl+Shift+Space"
    emergency_stop: str = "Escape"


@dataclass
class UIConfig:
    always_on_top: bool = True
    hotkeys: HotkeysConfig = field(default_factory=HotkeysConfig)


@dataclass
class VoiceConfig:
    model_path: Optional[str] = None
    device: Optional[int] = None
    sample_rate: int = 16000
    cooldown_ms: float = 550
    latency_mode: str = "balanced"
    require_wake_word: bool = False
    wake_words: list[str] = field(default_factory=lambda: ["翻页"])
    previous_phrases: list[str] = field(
        default_factory=lambda: ["左", "左翻", "向左", "上一页", "往前"]
    )
    next_phrases: list[str] = field(
        default_factory=lambda: ["右", "右翻", "向右", "下一页", "往后"]
    )
    pause_phrases: list[str] = field(default_factory=lambda: ["暂停", "停止"])
    resume_phrases: list[str] = field(default_factory=lambda: ["继续", "开始"])
    previous_key: str = "Left"
    next_key: str = "Right"


@dataclass
class AppConfig:
    mode: str = "voice"
    camera: CameraConfig = field(default_factory=CameraConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    filter: FilterConfig = field(default_factory=FilterConfig)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    scroll: ScrollConfig = field(default_factory=ScrollConfig)
    blink: BlinkConfig = field(default_factory=BlinkConfig)
    ui: UIConfig = field(default_factory=UIConfig)


class Config:
    DEFAULT_CONFIG_NAME = "default_config.json"
    USER_CONFIG_NAME = "config.json"

    def __init__(self, app_dir: Optional[str] = None):
        if app_dir is not None:
            self.app_dir = Path(app_dir)
            self.config_dir = self.app_dir / "config"
            self.default_config_path = self.config_dir / self.DEFAULT_CONFIG_NAME
        elif getattr(sys, "frozen", False):
            resource_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
            self.app_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "HeadScroll"
            self.config_dir = self.app_dir
            self.default_config_path = resource_root / "config" / self.DEFAULT_CONFIG_NAME
        else:
            self.app_dir = Path(__file__).resolve().parents[2]
            self.config_dir = self.app_dir / "config"
            self.default_config_path = self.config_dir / self.DEFAULT_CONFIG_NAME
        self._config = AppConfig()
        self._config_path: Optional[Path] = None

    def load(self, config_path: Optional[str] = None) -> bool:
        if config_path:
            return self._load_from_file(Path(config_path))
        user_config = self.config_dir / self.USER_CONFIG_NAME
        if user_config.exists() and self._load_from_file(user_config):
            return True
        if self.default_config_path.exists():
            return self._load_from_file(self.default_config_path)
        return True

    def _load_from_file(self, path: Path) -> bool:
        try:
            with path.open("r", encoding="utf-8") as file:
                config = self._dict_to_config(json.load(file))
            self._validate(config)
            self._config = config
            self._config_path = path
            return True
        except Exception as exc:
            logging.getLogger("head_scroll.config").warning(
                "Failed to load config %s: %s", path, exc
            )
            return False

    @staticmethod
    def _dict_to_config(data: Dict[str, Any]) -> AppConfig:
        config = AppConfig()
        legacy_calibration = data.get("calibration", {})
        config.mode = data.get("mode") or (
            "head" if legacy_calibration.get("mode") == "head" else "voice"
        )
        if config.mode == "hand":
            config.mode = "voice"
        if "camera" in data:
            config.camera = CameraConfig(**data["camera"])
        if "voice" in data:
            config.voice = VoiceConfig(**data["voice"])
        if "calibration" in data:
            calibration = data["calibration"]
            config.calibration = CalibrationConfig(**{
                name: calibration[name]
                for name in ("r_top", "r_mid", "r_bottom", "timestamp", "pose_source")
                if name in calibration
            })
            if calibration.get("pose_source") != "matrix":
                config.calibration.timestamp = None
        if "filter" in data:
            config.filter = FilterConfig(**data["filter"])
        if "thresholds" in data:
            config.thresholds = ThresholdsConfig(**data["thresholds"])
        if "scroll" in data:
            config.scroll = ScrollConfig(**data["scroll"])
        if "blink" in data:
            config.blink = BlinkConfig(**data["blink"])
        if "ui" in data:
            ui = data["ui"]
            config.ui = UIConfig(
                always_on_top=ui.get("always_on_top", True),
                hotkeys=HotkeysConfig(**ui.get("hotkeys", {})),
            )
        return config

    def save(self, config_path: Optional[str] = None) -> bool:
        path = Path(config_path) if config_path else self.config_dir / self.USER_CONFIG_NAME
        try:
            self._validate(self._config)
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as file:
                    json.dump(asdict(self._config), file, indent=2, ensure_ascii=False)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(temp_name, path)
            except Exception:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
                raise
            self._config_path = path
            return True
        except Exception as exc:
            logging.getLogger("head_scroll.config").error(
                "Failed to save config %s: %s", path, exc
            )
            return False

    @staticmethod
    def _validate(config: AppConfig) -> None:
        voice = config.voice
        if config.mode not in {"voice", "head"}:
            raise ValueError("mode must be voice or head")
        if config.camera.index < 0:
            raise ValueError("camera.index must be non-negative")
        if min(config.camera.width, config.camera.height, config.camera.target_fps) <= 0:
            raise ValueError("camera dimensions and FPS must be positive")
        if voice.sample_rate <= 0 or voice.cooldown_ms < 0:
            raise ValueError("voice sample rate and cooldown are invalid")
        if voice.latency_mode not in {"fast", "balanced", "accurate"}:
            raise ValueError("voice latency mode is invalid")
        if voice.device is not None and voice.device < 0:
            raise ValueError("voice device index must be non-negative")
        phrase_groups = (
            voice.previous_phrases,
            voice.next_phrases,
            voice.pause_phrases,
            voice.resume_phrases,
        )
        if any(not group or any(not phrase.strip() for phrase in group) for group in phrase_groups):
            raise ValueError("voice command phrase groups cannot be empty")
        flattened = [phrase.strip() for group in phrase_groups for phrase in group]
        if len(flattened) != len(set(flattened)):
            raise ValueError("voice command phrases must be unique across actions")
        if voice.require_wake_word and not any(word.strip() for word in voice.wake_words):
            raise ValueError("wake word is required but none is configured")
        supported_keys = {"Left", "Right", "PageUp", "PageDown"}
        if voice.previous_key not in supported_keys or voice.next_key not in supported_keys:
            raise ValueError("unsupported page key")
        if voice.previous_key == voice.next_key:
            raise ValueError("previous and next page keys must differ")
        if not config.ui.hotkeys.toggle_pause or not config.ui.hotkeys.emergency_stop:
            raise ValueError("hotkeys cannot be empty")
        if voice.model_path and not Path(voice.model_path).is_dir():
            raise ValueError("voice.model_path must point to a model directory")
        if not 0.0 < config.filter.ema_alpha < 1.0:
            raise ValueError("filter.ema_alpha must be between 0 and 1")
        if not 0.0 <= config.filter.confidence_min <= 1.0:
            raise ValueError("filter.confidence_min must be between 0 and 1")
        if not 0.0 <= config.thresholds.th_off < config.thresholds.th_on <= 1.0:
            raise ValueError("head scroll thresholds are invalid")
        if min(config.scroll.v_max, config.scroll.gamma, config.scroll.tick_hz) <= 0:
            raise ValueError("scroll speed, gamma, and tick rate must be positive")
        if config.calibration.pose_source != "matrix":
            raise ValueError("unsupported head pose source")

    @property
    def config(self) -> AppConfig:
        return self._config

    @property
    def camera(self) -> CameraConfig:
        return self._config.camera

    @property
    def voice(self) -> VoiceConfig:
        return self._config.voice

    @property
    def mode(self) -> str:
        return self._config.mode

    @property
    def calibration(self) -> CalibrationConfig:
        return self._config.calibration

    @property
    def filter(self) -> FilterConfig:
        return self._config.filter

    @property
    def thresholds(self) -> ThresholdsConfig:
        return self._config.thresholds

    @property
    def scroll(self) -> ScrollConfig:
        return self._config.scroll

    @property
    def blink(self) -> BlinkConfig:
        return self._config.blink

    @property
    def ui(self) -> UIConfig:
        return self._config.ui
