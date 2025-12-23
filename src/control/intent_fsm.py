"""
M6: 意图状态机
判定用户滚动意图，管理状态转换
"""

from enum import Enum, auto
from typing import Optional
import time

from tracking.feature_extractor import BlinkState


class FSMState(Enum):
    """状态机状态"""
    PAUSED = auto()     # 暂停态 - 任何情况下不滚动
    IDLE = auto()       # 空闲态 - 检测到脸但未触发
    ARMED = auto()      # 预备态 - 进入触发区，计时中
    SCROLLING = auto()  # 滚动态 - 自动滚动中


class IntentFSM:
    """意图状态机"""
    
    def __init__(
        self,
        th_on: float = 0.78,
        th_off: float = 0.70,
        dwell_on_ms: float = 400,
        dwell_off_ms: float = 100,
        long_blink_ms: float = 600,
        blink_cooldown_ms: float = 1500
    ):
        """
        初始化状态机
        
        Args:
            th_on: 进入触发阈值
            th_off: 退出触发阈值
            dwell_on_ms: 进入停留时间（毫秒）
            dwell_off_ms: 退出停留时间（毫秒）
            long_blink_ms: 长眨眼阈值（毫秒）
            blink_cooldown_ms: 眨眼冷却时间（毫秒）
        """
        self.th_on = th_on
        self.th_off = th_off
        self.dwell_on_ms = dwell_on_ms
        self.dwell_off_ms = dwell_off_ms
        self.long_blink_ms = long_blink_ms
        self.blink_cooldown_ms = blink_cooldown_ms
        
        # 状态
        self._state = FSMState.PAUSED
        self._armed_start_time: Optional[float] = None
        self._off_start_time: Optional[float] = None
        
        # 眨眼检测
        self._blink_start_time: Optional[float] = None
        self._last_blink_toggle_time = 0.0
    
    def update(
        self,
        s_f: float,
        blink_state: BlinkState,
        face_present: bool,
        face_lost: bool,
        timestamp: float
    ) -> tuple:
        """
        更新状态机
        
        Args:
            s_f: 滤波后的注视高度
            blink_state: 眨眼状态
            face_present: 是否检测到人脸
            face_lost: 人脸是否丢失（超时）
            timestamp: 时间戳
            
        Returns:
            (state, v_target) 元组
        """
        # 检测长眨眼暂停切换
        if self._check_long_blink(blink_state, timestamp):
            self._toggle_pause()
        
        # 暂停状态不处理
        if self._state == FSMState.PAUSED:
            return self._state, 0.0
        
        # 人脸丢失处理
        if face_lost or not face_present:
            self._transition_to(FSMState.IDLE)
            return self._state, 0.0
        
        # 状态转换逻辑
        current_time_ms = timestamp * 1000
        s_mag = self._centered_magnitude(s_f)
        
        if self._state == FSMState.IDLE:
            if s_mag > self.th_on:
                self._transition_to(FSMState.ARMED)
                self._armed_start_time = current_time_ms
        
        elif self._state == FSMState.ARMED:
            if s_mag < self.th_off:
                # 退出触发区
                self._transition_to(FSMState.IDLE)
            elif self._armed_start_time is not None:
                # 检查停留时间
                dwell_time = current_time_ms - self._armed_start_time
                if dwell_time >= self.dwell_on_ms:
                    self._transition_to(FSMState.SCROLLING)
        
        elif self._state == FSMState.SCROLLING:
            if s_mag < self.th_off:
                # 开始退出计时
                if self._off_start_time is None:
                    self._off_start_time = current_time_ms
                elif current_time_ms - self._off_start_time >= self.dwell_off_ms:
                    self._transition_to(FSMState.IDLE)
            else:
                self._off_start_time = None
        
        # 计算目标速度
        v_target = self._calculate_v_target(s_f)
        
        return self._state, v_target
    
    def _calculate_v_target(self, s_f: float) -> float:
        """?????????? -1 ? 1?"""
        if self._state != FSMState.SCROLLING:
            return 0.0

        # ??????????????????
        s_mag = self._centered_magnitude(s_f)
        if s_mag <= self.th_on:
            return 0.0

        v = (s_mag - self.th_on) / (1.0 - self.th_on)
        v = min(max(v, 0.0), 1.0)
        direction = -1.0 if s_f < 0.5 else 1.0
        return v * direction

    def _centered_magnitude(self, s_f: float) -> float:
        """??? 0.5 ????????? [0,1]"""
        return min(max(abs(s_f - 0.5) * 2.0, 0.0), 1.0)

    def _check_long_blink(self, blink_state: BlinkState, timestamp: float) -> bool:
        """检测长眨眼"""
        current_time_ms = timestamp * 1000
        
        # 检查冷却时间
        if current_time_ms - self._last_blink_toggle_time < self.blink_cooldown_ms:
            return False
        
        if blink_state == BlinkState.CLOSED:
            if self._blink_start_time is None:
                self._blink_start_time = current_time_ms
            elif current_time_ms - self._blink_start_time >= self.long_blink_ms:
                self._last_blink_toggle_time = current_time_ms
                self._blink_start_time = None
                return True
        else:
            self._blink_start_time = None
        
        return False
    
    def _toggle_pause(self) -> None:
        """切换暂停状态"""
        if self._state == FSMState.PAUSED:
            self._state = FSMState.IDLE
        else:
            self._state = FSMState.PAUSED
        self._reset_timers()
    
    def _transition_to(self, new_state: FSMState) -> None:
        """状态转换"""
        if self._state != new_state:
            self._state = new_state
            if new_state != FSMState.ARMED:
                self._armed_start_time = None
            if new_state != FSMState.SCROLLING:
                self._off_start_time = None
    
    def _reset_timers(self) -> None:
        """重置所有计时器"""
        self._armed_start_time = None
        self._off_start_time = None
        self._blink_start_time = None
    
    def pause(self) -> None:
        """手动暂停"""
        if self._state != FSMState.PAUSED:
            self._state = FSMState.PAUSED
            self._reset_timers()
    
    def resume(self) -> None:
        """手动恢复"""
        if self._state == FSMState.PAUSED:
            self._state = FSMState.IDLE
            self._last_blink_toggle_time = time.perf_counter() * 1000
    
    def toggle_pause(self) -> None:
        """切换暂停/恢复"""
        self._toggle_pause()
    
    @property
    def state(self) -> FSMState:
        """当前状态"""
        return self._state
    
    @property
    def is_scrolling(self) -> bool:
        """是否正在滚动"""
        return self._state == FSMState.SCROLLING
    
    @property
    def is_paused(self) -> bool:
        """是否暂停"""
        return self._state == FSMState.PAUSED
    
    def set_thresholds(
        self,
        th_on: Optional[float] = None,
        th_off: Optional[float] = None,
        dwell_on_ms: Optional[float] = None,
        dwell_off_ms: Optional[float] = None
    ) -> None:
        """动态更新阈值参数"""
        if th_on is not None:
            self.th_on = th_on
        if th_off is not None:
            self.th_off = th_off
        if dwell_on_ms is not None:
            self.dwell_on_ms = dwell_on_ms
        if dwell_off_ms is not None:
            self.dwell_off_ms = dwell_off_ms
