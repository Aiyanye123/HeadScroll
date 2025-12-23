"""
M4: 标定模块
三点标定采样、映射拟合、参数持久化
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Callable
import time
import numpy as np


class CalibrationPosition(Enum):
    """标定位置"""
    TOP = auto()     # 屏幕上方
    MIDDLE = auto()  # 屏幕中部
    BOTTOM = auto()  # 屏幕下方


@dataclass
class CalibrationResult:
    """标定结果"""
    r_top: float          # 上方位置原始值
    r_mid: float          # 中部位置原始值
    r_bottom: float       # 下方位置原始值
    is_valid: bool        # 标定是否有效
    error_message: str = ""   # 错误信息
    timestamp: str = ""   # 标定时间戳


@dataclass
class CalibrationSample:
    """标定采样数据"""
    position: CalibrationPosition
    values: List[float] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)


class Calibrator:
    """标定器 - 三点标定"""
    
    # 采样参数
    SAMPLE_DURATION_SEC = 1.5    # 每个位置采样时长
    DISCARD_DURATION_SEC = 0.3   # 丢弃前 N 秒（避免眼动过渡）
    MIN_SAMPLES = 10             # 最小有效采样数
    MIN_RANGE = 0.05             # 最小有效范围（r_bottom - r_top）
    
    def __init__(self):
        """初始化标定器"""
        self._is_calibrating = False
        self._current_position: Optional[CalibrationPosition] = None
        self._samples: dict = {}
        self._start_time = 0.0
        
        # 标定结果
        self._r_top = 0.25
        self._r_mid = 0.50
        self._r_bottom = 0.75
        self._is_calibrated = False
        
        # 回调
        self._on_position_complete: Optional[Callable] = None
        self._on_calibration_complete: Optional[Callable] = None
    
    def start_calibration(self) -> None:
        """开始标定流程"""
        self._is_calibrating = True
        self._samples = {
            CalibrationPosition.TOP: CalibrationSample(CalibrationPosition.TOP),
            CalibrationPosition.MIDDLE: CalibrationSample(CalibrationPosition.MIDDLE),
            CalibrationPosition.BOTTOM: CalibrationSample(CalibrationPosition.BOTTOM),
        }
        self._current_position = None
    
    def start_position(self, position: CalibrationPosition) -> None:
        """开始采样指定位置"""
        if not self._is_calibrating:
            return
        
        self._current_position = position
        self._start_time = time.perf_counter()
        self._samples[position] = CalibrationSample(position)
    
    def add_sample(self, gaze_y_raw: float, timestamp: float) -> bool:
        """
        添加采样数据
        
        Args:
            gaze_y_raw: 原始注视高度
            timestamp: 时间戳
            
        Returns:
            当前位置采样是否完成
        """
        if not self._is_calibrating or self._current_position is None:
            return False
        
        elapsed = time.perf_counter() - self._start_time
        
        # 丢弃初始阶段
        if elapsed < self.DISCARD_DURATION_SEC:
            return False
        
        # 添加采样
        sample = self._samples[self._current_position]
        sample.values.append(gaze_y_raw)
        sample.timestamps.append(timestamp)
        
        # 检查是否采样完成
        if elapsed >= self.SAMPLE_DURATION_SEC:
            if self._on_position_complete:
                self._on_position_complete(self._current_position)
            return True
        
        return False
    
    def finish_position(self) -> None:
        """完成当前位置采样"""
        self._current_position = None
    
    def finish(self) -> CalibrationResult:
        """
        完成标定，计算映射参数
        
        Returns:
            标定结果
        """
        self._is_calibrating = False
        self._current_position = None
        
        # 计算各位置的参考值
        r_top = self._compute_reference(CalibrationPosition.TOP)
        r_mid = self._compute_reference(CalibrationPosition.MIDDLE)
        r_bottom = self._compute_reference(CalibrationPosition.BOTTOM)
        
        # 验证标定结果
        if r_top is None or r_mid is None or r_bottom is None:
            return CalibrationResult(
                r_top=0.0, r_mid=0.0, r_bottom=0.0,
                is_valid=False,
                error_message="采样数据不足，请重新标定"
            )
        
        # 检查范围是否足够
        if r_bottom - r_top < self.MIN_RANGE:
            return CalibrationResult(
                r_top=r_top, r_mid=r_mid, r_bottom=r_bottom,
                is_valid=False,
                error_message="标定范围过小，请调整坐姿或摄像头位置后重新标定"
            )
        
        # 保存结果
        self._r_top = r_top
        self._r_mid = r_mid
        self._r_bottom = r_bottom
        self._is_calibrated = True
        
        result = CalibrationResult(
            r_top=r_top,
            r_mid=r_mid,
            r_bottom=r_bottom,
            is_valid=True,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S")
        )
        
        if self._on_calibration_complete:
            self._on_calibration_complete(result)
        
        return result
    
    def _compute_reference(self, position: CalibrationPosition) -> Optional[float]:
        """计算指定位置的参考值（截尾均值）"""
        sample = self._samples.get(position)
        if sample is None or len(sample.values) < self.MIN_SAMPLES:
            return None
        
        values = np.array(sample.values)
        
        # 截尾均值：去除最高和最低 10%
        lower = np.percentile(values, 10)
        upper = np.percentile(values, 90)
        trimmed = values[(values >= lower) & (values <= upper)]
        
        if len(trimmed) < 3:
            return float(np.median(values))
        
        return float(np.mean(trimmed))
    
    def map(self, gaze_y_raw: float) -> float:
        """
        将原始注视高度映射到标准化值 s ∈ [0, 1]
        
        使用分段线性映射：
        - s=0 对应 r_top
        - s=0.5 对应 r_mid
        - s=1 对应 r_bottom
        
        Args:
            gaze_y_raw: 原始注视高度
            
        Returns:
            标准化注视高度 s ∈ [0, 1]
        """
        if not self._is_calibrated:
            # 未标定时使用默认线性映射
            return np.clip(gaze_y_raw, 0.0, 1.0)
        
        # 分段线性映射
        if gaze_y_raw <= self._r_mid:
            # 上半段：[r_top, r_mid] -> [0, 0.5]
            if self._r_mid - self._r_top < 0.001:
                s = 0.25
            else:
                s = 0.5 * (gaze_y_raw - self._r_top) / (self._r_mid - self._r_top)
        else:
            # 下半段：[r_mid, r_bottom] -> [0.5, 1]
            if self._r_bottom - self._r_mid < 0.001:
                s = 0.75
            else:
                s = 0.5 + 0.5 * (gaze_y_raw - self._r_mid) / (self._r_bottom - self._r_mid)
        
        return float(np.clip(s, 0.0, 1.0))
    
    def load_calibration(self, r_top: float, r_mid: float, r_bottom: float) -> None:
        """加载已保存的标定参数"""
        self._r_top = r_top
        self._r_mid = r_mid
        self._r_bottom = r_bottom
        self._is_calibrated = True
    
    def set_callbacks(
        self,
        on_position_complete: Optional[Callable] = None,
        on_calibration_complete: Optional[Callable] = None
    ) -> None:
        """设置回调函数"""
        self._on_position_complete = on_position_complete
        self._on_calibration_complete = on_calibration_complete
    
    @property
    def is_calibrating(self) -> bool:
        """是否正在标定"""
        return self._is_calibrating
    
    @property
    def is_calibrated(self) -> bool:
        """是否已完成标定"""
        return self._is_calibrated
    
    @property
    def current_position(self) -> Optional[CalibrationPosition]:
        """当前采样位置"""
        return self._current_position
    
    @property
    def calibration_params(self) -> tuple:
        """获取标定参数 (r_top, r_mid, r_bottom)"""
        return self._r_top, self._r_mid, self._r_bottom
