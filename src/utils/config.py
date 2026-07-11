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
class GestureConfig:
    mirror: bool = True
    min_confidence: float = 0.7
    arm_duration_ms: float = 150
    arm_stability_radius: float = 0.04
    min_swipe_distance: float = 0.18
    min_swipe_duration_ms: float = 120
    min_swipe_speed: float = 0.35
    max_vertical_drift: float = 0.10
    max_swipe_duration_ms: float = 700
    direction_consistency: float = 0.75
    cooldown_ms: float = 600
    fist_hold_ms: float = 700
    previous_key: str = "Left"
    next_key: str = "Right"


@dataclass
class AppConfig:
    mode: str = "hand"
    camera: CameraConfig = field(default_factory=CameraConfig)
    gesture: GestureConfig = field(default_factory=GestureConfig)
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
            self.app_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "HandPage"
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
            "head" if legacy_calibration.get("mode") == "head" else "hand"
        )
        if "camera" in data:
            config.camera = CameraConfig(**data["camera"])
        if "gesture" in data:
            config.gesture = GestureConfig(**data["gesture"])
        if "calibration" in data:
            calibration = data["calibration"]
            config.calibration = CalibrationConfig(**{
                name: calibration[name]
                for name in ("r_top", "r_mid", "r_bottom", "timestamp")
                if name in calibration
            })
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
        gesture = config.gesture
        if config.mode not in {"hand", "head"}:
            raise ValueError("mode must be hand or head")
        if config.camera.index < 0:
            raise ValueError("camera.index must be non-negative")
        if min(config.camera.width, config.camera.height, config.camera.target_fps) <= 0:
            raise ValueError("camera dimensions and FPS must be positive")
        if not 0.0 <= gesture.min_confidence <= 1.0:
            raise ValueError("gesture.min_confidence must be between 0 and 1")
        for name in ("min_swipe_distance", "max_vertical_drift", "arm_stability_radius"):
            if not 0.0 < getattr(gesture, name) < 1.0:
                raise ValueError(f"gesture.{name} must be between 0 and 1")
        if not 0.5 <= gesture.direction_consistency <= 1.0:
            raise ValueError("gesture.direction_consistency must be between 0.5 and 1")
        if gesture.min_swipe_speed <= 0:
            raise ValueError("gesture.min_swipe_speed must be positive")
        if gesture.min_swipe_duration_ms >= gesture.max_swipe_duration_ms:
            raise ValueError("minimum swipe duration must be less than maximum")
        for name in ("arm_duration_ms", "cooldown_ms", "fist_hold_ms"):
            if getattr(gesture, name) < 0:
                raise ValueError(f"gesture.{name} must be non-negative")
        supported_keys = {"Left", "Right", "PageUp", "PageDown"}
        if gesture.previous_key not in supported_keys or gesture.next_key not in supported_keys:
            raise ValueError("unsupported page key")
        if gesture.previous_key == gesture.next_key:
            raise ValueError("previous and next page keys must differ")
        if not config.ui.hotkeys.toggle_pause or not config.ui.hotkeys.emergency_stop:
            raise ValueError("hotkeys cannot be empty")
        if not 0.0 < config.filter.ema_alpha < 1.0:
            raise ValueError("filter.ema_alpha must be between 0 and 1")
        if not 0.0 <= config.filter.confidence_min <= 1.0:
            raise ValueError("filter.confidence_min must be between 0 and 1")
        if not 0.0 <= config.thresholds.th_off < config.thresholds.th_on <= 1.0:
            raise ValueError("head scroll thresholds are invalid")
        if min(config.scroll.v_max, config.scroll.gamma, config.scroll.tick_hz) <= 0:
            raise ValueError("scroll speed, gamma, and tick rate must be positive")

    @property
    def config(self) -> AppConfig:
        return self._config

    @property
    def camera(self) -> CameraConfig:
        return self._config.camera

    @property
    def gesture(self) -> GestureConfig:
        return self._config.gesture

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
