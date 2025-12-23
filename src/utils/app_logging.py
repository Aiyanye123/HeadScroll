"""
M10: 日志模块
结构化日志系统
"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# 日志格式
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    console: bool = True
) -> None:
    """
    配置日志系统
    
    Args:
        level: 日志级别
        log_file: 日志文件路径，None 则不写文件
        console: 是否输出到控制台
    """
    # 获取根 logger
    root_logger = logging.getLogger("eye_scroll")
    root_logger.setLevel(level)
    
    # 清除已有处理器
    root_logger.handlers.clear()
    
    formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)
    
    # 控制台处理器
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # 文件处理器
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的 logger
    
    Args:
        name: logger 名称
        
    Returns:
        Logger 实例
    """
    return logging.getLogger(f"eye_scroll.{name}")


class EventLogger:
    """事件日志记录器"""
    
    def __init__(self, name: str = "events"):
        """
        初始化事件记录器
        
        Args:
            name: logger 名称
        """
        self._logger = get_logger(name)
        self._session_start = datetime.now()
    
    def log_scroll_start(self, s_f: float, v_target: float) -> None:
        """记录滚动开始事件"""
        self._logger.info(f"SCROLL_START | s_f={s_f:.3f} | v_target={v_target:.2f}")
    
    def log_scroll_stop(self, s_f: float, duration_sec: float) -> None:
        """记录滚动停止事件"""
        self._logger.info(f"SCROLL_STOP | s_f={s_f:.3f} | duration={duration_sec:.2f}s")
    
    def log_pause(self, reason: str) -> None:
        """记录暂停事件"""
        self._logger.info(f"PAUSE | reason={reason}")
    
    def log_resume(self) -> None:
        """记录恢复事件"""
        self._logger.info("RESUME")
    
    def log_face_lost(self, duration_ms: float) -> None:
        """记录人脸丢失事件"""
        self._logger.warning(f"FACE_LOST | duration={duration_ms:.0f}ms")
    
    def log_face_found(self) -> None:
        """记录人脸找回事件"""
        self._logger.info("FACE_FOUND")
    
    def log_calibration(self, r_top: float, r_mid: float, r_bottom: float) -> None:
        """记录标定完成事件"""
        self._logger.info(
            f"CALIBRATION | r_top={r_top:.3f} | r_mid={r_mid:.3f} | r_bottom={r_bottom:.3f}"
        )
    
    def log_error(self, component: str, message: str) -> None:
        """记录错误事件"""
        self._logger.error(f"ERROR | component={component} | message={message}")
    
    def log_stats(self, fps: float, avg_confidence: float, scroll_count: int) -> None:
        """记录统计信息"""
        self._logger.debug(
            f"STATS | fps={fps:.1f} | confidence={avg_confidence:.2f} | scrolls={scroll_count}"
        )
