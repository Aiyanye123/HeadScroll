"""
M7: 滚动控制器
速度平滑、滚轮事件生成
"""

from typing import Optional


class ScrollController:
    """滚动控制器"""
    
    def __init__(
        self,
        v_max: float = 5.0,
        gamma: float = 1.5,
        a_up: float = 10.0,
        a_down: float = 20.0,
        tick_hz: float = 60
    ):
        """
        初始化滚动控制器
        
        Args:
            v_max: 最大速度（滚轮刻度/秒）
            gamma: 速度曲线指数（>1 使低速区更细腻）
            a_up: 加速度（刻度/秒²）
            a_down: 减速度（刻度/秒²）
            tick_hz: 控制循环频率
        """
        self.v_max = v_max
        self.gamma = gamma
        self.a_up = a_up
        self.a_down = a_down
        self.tick_hz = tick_hz
        
        # 状态
        self._v_current = 0.0  # 当前速度
        self._v_target = 0.0   # 目标速度
        self._scroll_accumulator = 0.0  # 滚轮累积量
    
    def set_target(self, v_target_ratio: float) -> None:
        """
        设置目标速度
        
        Args:
            v_target_ratio: 目标速度比例 [-1, 1]
        """
        # 应用 gamma 曲线
        v_ratio = max(-1.0, min(1.0, v_target_ratio))
        v_mag = pow(abs(v_ratio), self.gamma)
        self._v_target = v_mag * self.v_max * (1.0 if v_ratio >= 0 else -1.0)
    
    def tick(self, dt: Optional[float] = None) -> int:
        """
        控制循环 tick
        
        Args:
            dt: 时间增量（秒），None 则使用默认
            
        Returns:
            本次应发送的滚轮步进（整数）
        """
        if dt is None:
            dt = 1.0 / self.tick_hz
        
        # 速度渐变
        self._update_velocity(dt)
        
        # 累积滚轮量
        self._scroll_accumulator += self._v_current * dt
        
        # 取整数部分作为滚轮步进
        scroll_delta = int(self._scroll_accumulator)
        self._scroll_accumulator -= scroll_delta
        
        return scroll_delta
    
    def _update_velocity(self, dt: float) -> None:
        """更新速度（带加减速限制）"""
        v_diff = self._v_target - self._v_current
        
        if v_diff > 0:
            # 加速
            max_change = self.a_up * dt
            self._v_current += min(v_diff, max_change)
        elif v_diff < 0:
            # 减速（更快）
            max_change = self.a_down * dt
            self._v_current += max(v_diff, -max_change)
    
    def stop(self) -> None:
        """立即停止"""
        self._v_target = 0.0
        self._v_current = 0.0
        self._scroll_accumulator = 0.0
    
    def reset(self) -> None:
        """重置控制器"""
        self.stop()
    
    @property
    def v_current(self) -> float:
        """当前速度"""
        return self._v_current
    
    @property
    def v_target(self) -> float:
        """目标速度"""
        return self._v_target
    
    @property
    def is_scrolling(self) -> bool:
        """是否正在滚动"""
        return abs(self._v_current) > 0.01
    
    def set_params(
        self,
        v_max: Optional[float] = None,
        gamma: Optional[float] = None,
        a_up: Optional[float] = None,
        a_down: Optional[float] = None
    ) -> None:
        """动态更新参数"""
        if v_max is not None:
            self.v_max = v_max
        if gamma is not None:
            self.gamma = gamma
        if a_up is not None:
            self.a_up = a_up
        if a_down is not None:
            self.a_down = a_down
