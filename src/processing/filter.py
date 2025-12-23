"""
M5: 滤波去抖模块
EMA 滤波、置信度门控、去抖处理
"""

from typing import Optional
import time


class GazeFilter:
    """注视滤波器 - EMA 滤波与去抖"""
    
    def __init__(
        self,
        ema_alpha: float = 0.85,
        confidence_min: float = 0.6,
        lost_face_timeout_ms: float = 500
    ):
        """
        初始化滤波器
        
        Args:
            ema_alpha: EMA 滤波系数，越大越平滑 (0.7-0.92)
            confidence_min: 最小置信度阈值
            lost_face_timeout_ms: 丢脸容忍时间（毫秒）
        """
        self.ema_alpha = ema_alpha
        self.confidence_min = confidence_min
        self.lost_face_timeout_ms = lost_face_timeout_ms
        
        # 状态
        self._s_filtered = 0.5  # 滤波后的注视高度
        self._last_valid_time: Optional[float] = None
        self._invalid_duration_ms = 0.0
        self._is_face_lost = False
    
    def update(
        self,
        s_raw: float,
        confidence: float,
        face_present: bool,
        timestamp: float
    ) -> float:
        """
        更新滤波器
        
        Args:
            s_raw: 原始标准化注视高度 [0,1]
            confidence: 置信度 [0,1]
            face_present: 是否检测到人脸
            timestamp: 时间戳
            
        Returns:
            滤波后的注视高度 s_f
        """
        current_time = timestamp
        
        # 处理无效帧
        if not face_present or confidence < self.confidence_min:
            return self._handle_invalid_frame(current_time)
        
        # 有效帧处理
        self._last_valid_time = current_time
        self._invalid_duration_ms = 0.0
        self._is_face_lost = False
        
        # EMA 滤波
        self._s_filtered = self.ema_alpha * self._s_filtered + (1 - self.ema_alpha) * s_raw
        
        return self._s_filtered
    
    def _handle_invalid_frame(self, current_time: float) -> float:
        """处理无效帧"""
        if self._last_valid_time is not None:
            # 计算无效持续时间
            self._invalid_duration_ms = (current_time - self._last_valid_time) * 1000
            
            # 检查是否超过容忍时间
            if self._invalid_duration_ms > self.lost_face_timeout_ms:
                self._is_face_lost = True
        
        # 保持上一个有效值
        return self._s_filtered
    
    def reset(self) -> None:
        """重置滤波器状态"""
        self._s_filtered = 0.5
        self._last_valid_time = None
        self._invalid_duration_ms = 0.0
        self._is_face_lost = False
    
    @property
    def s_filtered(self) -> float:
        """获取当前滤波后的注视高度"""
        return self._s_filtered
    
    @property
    def is_face_lost(self) -> bool:
        """人脸是否丢失（超过容忍时间）"""
        return self._is_face_lost
    
    @property
    def invalid_duration_ms(self) -> float:
        """无效帧持续时间（毫秒）"""
        return self._invalid_duration_ms
    
    def set_params(
        self,
        ema_alpha: Optional[float] = None,
        confidence_min: Optional[float] = None,
        lost_face_timeout_ms: Optional[float] = None
    ) -> None:
        """动态更新滤波参数"""
        if ema_alpha is not None:
            self.ema_alpha = ema_alpha
        if confidence_min is not None:
            self.confidence_min = confidence_min
        if lost_face_timeout_ms is not None:
            self.lost_face_timeout_ms = lost_face_timeout_ms
