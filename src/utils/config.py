"""
M10: 配置管理模块
配置加载保存
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any
from pathlib import Path


@dataclass
class CameraConfig:
    """摄像头配置"""
    index: int = 0
    width: int = 640
    height: int = 480
    target_fps: int = 30


@dataclass
class CalibrationConfig:
    """标定配置"""
    r_top: float = 0.25
    r_mid: float = 0.50
    r_bottom: float = 0.75
    method: str = "linear"
    mode: str = "head"
    head_pitch_min: float = -0.15
    head_pitch_max: float = 0.15
    head_pitch_center: float = 0.0
    timestamp: Optional[str] = None


@dataclass
class FusionConfig:
    """融合配置"""
    w_gaze: float = 0.8
    w_pitch: float = 0.2


@dataclass
class FilterConfig:
    """滤波配置"""
    ema_alpha: float = 0.85
    confidence_min: float = 0.6
    lost_face_timeout_ms: float = 500


@dataclass
class ThresholdsConfig:
    """阈值配置"""
    th_on: float = 0.78
    th_off: float = 0.70
    dwell_on_ms: float = 400
    dwell_off_ms: float = 100


@dataclass
class ScrollConfig:
    """滚动配置"""
    v_max: float = 5.0
    gamma: float = 1.5
    a_up: float = 10.0
    a_down: float = 20.0
    tick_hz: float = 60


@dataclass
class BlinkConfig:
    """眨眼配置"""
    long_blink_ms: float = 600
    cooldown_ms: float = 1500


@dataclass
class HotkeysConfig:
    """快捷键配置"""
    toggle_pause: str = "Ctrl+Shift+Space"
    emergency_stop: str = "Escape"


@dataclass
class UIConfig:
    """UI 配置"""
    always_on_top: bool = True
    show_overlay: bool = False
    hotkeys: HotkeysConfig = field(default_factory=HotkeysConfig)


@dataclass
class InjectionConfig:
    """输入注入配置"""
    target: str = "cursor"  # cursor / foreground / process
    process_name: Optional[str] = None
    smooth_scroll: bool = True


@dataclass
class AppConfig:
    """应用程序完整配置"""
    camera: CameraConfig = field(default_factory=CameraConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    fusion: FusionConfig = field(default_factory=FusionConfig)
    filter: FilterConfig = field(default_factory=FilterConfig)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    scroll: ScrollConfig = field(default_factory=ScrollConfig)
    blink: BlinkConfig = field(default_factory=BlinkConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    injection: InjectionConfig = field(default_factory=InjectionConfig)


class Config:
    """配置管理器"""
    
    DEFAULT_CONFIG_NAME = "default_config.json"
    USER_CONFIG_NAME = "config.json"
    
    def __init__(self, app_dir: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            app_dir: 应用程序目录，None 则使用脚本所在目录
        """
        if app_dir is None:
            # 默认使用项目根目录
            app_dir = str(Path(__file__).parent.parent.parent)
        
        self.app_dir = Path(app_dir)
        self.config_dir = self.app_dir / "config"
        
        self._config = AppConfig()
        self._config_path: Optional[Path] = None
    
    def load(self, config_path: Optional[str] = None) -> bool:
        """
        加载配置文件
        
        Args:
            config_path: 配置文件路径，None 则依次尝试用户配置和默认配置
            
        Returns:
            是否成功加载
        """
        if config_path:
            return self._load_from_file(Path(config_path))
        
        # 尝试加载用户配置
        user_config = self.config_dir / self.USER_CONFIG_NAME
        if user_config.exists():
            if self._load_from_file(user_config):
                return True
        
        # 尝试加载默认配置
        default_config = self.config_dir / self.DEFAULT_CONFIG_NAME
        if default_config.exists():
            return self._load_from_file(default_config)
        
        # 使用默认值
        self._config = AppConfig()
        return True
    
    def _load_from_file(self, path: Path) -> bool:
        """从文件加载配置"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self._config = self._dict_to_config(data)
            self._config_path = path
            return True
        except Exception:
            return False
    
    def _dict_to_config(self, data: Dict[str, Any]) -> AppConfig:
        """将字典转换为配置对象"""
        config = AppConfig()
        
        if "camera" in data:
            config.camera = CameraConfig(**data["camera"])
        if "calibration" in data:
            config.calibration = CalibrationConfig(**data["calibration"])
        if "fusion" in data:
            config.fusion = FusionConfig(**data["fusion"])
        if "filter" in data:
            config.filter = FilterConfig(**data["filter"])
        if "thresholds" in data:
            config.thresholds = ThresholdsConfig(**data["thresholds"])
        if "scroll" in data:
            config.scroll = ScrollConfig(**data["scroll"])
        if "blink" in data:
            config.blink = BlinkConfig(**data["blink"])
        if "ui" in data:
            ui_data = data["ui"]
            hotkeys = HotkeysConfig(**ui_data.get("hotkeys", {}))
            config.ui = UIConfig(
                always_on_top=ui_data.get("always_on_top", True),
                show_overlay=ui_data.get("show_overlay", False),
                hotkeys=hotkeys
            )
        if "injection" in data:
            config.injection = InjectionConfig(**data["injection"])
        
        return config
    
    def save(self, config_path: Optional[str] = None) -> bool:
        """
        保存配置文件
        
        Args:
            config_path: 配置文件路径，None 则保存为用户配置
            
        Returns:
            是否成功保存
        """
        if config_path:
            path = Path(config_path)
        else:
            path = self.config_dir / self.USER_CONFIG_NAME
        
        try:
            # 确保目录存在
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # 转换为字典
            data = self._config_to_dict(self._config)
            
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self._config_path = path
            return True
        except Exception:
            return False
    
    def _config_to_dict(self, config: AppConfig) -> Dict[str, Any]:
        """将配置对象转换为字典"""
        return {
            "camera": asdict(config.camera),
            "calibration": asdict(config.calibration),
            "fusion": asdict(config.fusion),
            "filter": asdict(config.filter),
            "thresholds": asdict(config.thresholds),
            "scroll": asdict(config.scroll),
            "blink": asdict(config.blink),
            "ui": {
                "always_on_top": config.ui.always_on_top,
                "show_overlay": config.ui.show_overlay,
                "hotkeys": asdict(config.ui.hotkeys)
            },
            "injection": asdict(config.injection),
        }
    
    def update_calibration(
        self,
        r_top: float,
        r_mid: float,
        r_bottom: float,
        timestamp: str
    ) -> None:
        """更新标定参数"""
        self._config.calibration.r_top = r_top
        self._config.calibration.r_mid = r_mid
        self._config.calibration.r_bottom = r_bottom
        self._config.calibration.timestamp = timestamp
    
    @property
    def config(self) -> AppConfig:
        """获取配置对象"""
        return self._config
    
    @property
    def camera(self) -> CameraConfig:
        return self._config.camera
    
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

    @property
    def injection(self) -> InjectionConfig:
        return self._config.injection
