"""
M1: 摄像头采集模块
负责摄像头初始化、帧采集和时间戳管理
"""

import time
from typing import Optional, Tuple
import cv2
import numpy as np


class Camera:
    """摄像头采集类"""
    
    def __init__(
        self,
        index: int = 0,
        width: int = 640,
        height: int = 480,
        target_fps: int = 30
    ):
        """
        初始化摄像头参数
        
        Args:
            index: 摄像头设备索引
            width: 采集宽度
            height: 采集高度
            target_fps: 目标帧率
        """
        self.index = index
        self.width = width
        self.height = height
        self.target_fps = target_fps
        
        self._cap: Optional[cv2.VideoCapture] = None
        self._is_running = False
        self._last_frame_time = 0.0
    
    def start(self) -> bool:
        """
        启动摄像头
        
        Returns:
            是否成功启动
        """
        if self._is_running:
            return True
        
        try:
            # Windows 下使用 DSHOW 后端以获得更好的兼容性
            self._cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW)
            
            if not self._cap.isOpened():
                # 尝试不带后端参数
                self._cap = cv2.VideoCapture(self.index)
            
            if not self._cap.isOpened():
                return False
            
            # 设置分辨率和帧率
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self._cap.set(cv2.CAP_PROP_FPS, self.target_fps)
            
            # 减少缓冲以降低延迟
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            self._is_running = True
            self._last_frame_time = time.perf_counter()
            return True
            
        except Exception:
            self._is_running = False
            return False
    
    def get_frame(self) -> Tuple[Optional[np.ndarray], float]:
        """
        获取最新帧
        
        Returns:
            (帧图像, 时间戳) 元组，失败时帧为 None
        """
        if not self._is_running or self._cap is None:
            return None, 0.0
        
        ret, frame = self._cap.read()
        timestamp = time.perf_counter()
        
        if not ret or frame is None:
            return None, timestamp
        
        self._last_frame_time = timestamp
        return frame, timestamp
    
    def stop(self) -> None:
        """停止摄像头"""
        self._is_running = False
        if self._cap is not None:
            self._cap.release()
            self._cap = None
    
    @property
    def is_running(self) -> bool:
        """摄像头是否正在运行"""
        return self._is_running
    
    @property
    def actual_fps(self) -> float:
        """获取实际帧率"""
        if self._cap is not None and self._cap.isOpened():
            return self._cap.get(cv2.CAP_PROP_FPS)
        return 0.0
    
    @property
    def actual_resolution(self) -> Tuple[int, int]:
        """获取实际分辨率"""
        if self._cap is not None and self._cap.isOpened():
            w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            return w, h
        return 0, 0
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
