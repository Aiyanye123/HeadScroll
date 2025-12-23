"""
眼动控制网页漫画滚动 - 主程序入口

实现线程管理与数据流：
- T1 Capture: 摄像头采集
- T2 Inference: 推理与特征提取
- T3 Control: 滤波、状态机、滚动控制
- Main Thread: UI
"""

import sys
import time
from pathlib import Path

# Ensure local modules (capture/, tracking/, etc.) are importable in dev and PyInstaller.
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from threading import Thread, Event
from queue import Queue, Empty
from typing import Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QTimer, QObject, Signal

# 导入模块
from capture import Camera
from tracking import FaceTracker, FeatureExtractor, FeaturePacket, BlinkState
from calibration import Calibrator
from processing import GazeFilter
from control import IntentFSM, FSMState, ScrollController
from injection import PlatformInjector
from ui import MainWindow
from ui.settings_dialog import SettingsDialog
from ui.styles import apply_theme
from utils import Config, setup_logging, get_logger


class WorkerSignals(QObject):
    """工作线程信号"""
    frame_processed = Signal(object)  # FeaturePacket
    state_updated = Signal(str, bool, float, float)  # state_name, is_scrolling, s_f, confidence
    error_occurred = Signal(str, str)  # component, message


class EyeScrollController:
    """眼动滚动控制器 - 主控制类"""
    
    def __init__(self):
        self.logger = get_logger("main")
        
        # 加载配置
        self.config = Config()
        self.config.load()
        
        # 创建组件
        self._create_components()
        
        # 线程控制
        self._stop_event = Event()
        self._pause_event = Event()
        self._capture_thread: Optional[Thread] = None
        self._inference_thread: Optional[Thread] = None
        self._control_thread: Optional[Thread] = None
        
        # 数据队列
        self._frame_queue: Queue = Queue(maxsize=2)
        self._feature_queue: Queue = Queue(maxsize=2)
        
        # 信号
        self.signals = WorkerSignals()
        
        # 统计
        self._frame_count = 0
        self._fps_start_time = time.perf_counter()
        self._current_fps = 0.0
        self._running = False
    
    def _create_components(self):
        """创建各模块组件"""
        cfg = self.config
        
        # M1: 摄像头
        self.camera = Camera(
            index=cfg.camera.index,
            width=cfg.camera.width,
            height=cfg.camera.height,
            target_fps=cfg.camera.target_fps
        )
        
        # M2: 人脸追踪
        self.face_tracker = FaceTracker()
        
        # M3: 特征提取
        self.feature_extractor = FeatureExtractor()
        
        # M4: 标定器
        self.calibrator = Calibrator()
        if cfg.calibration.timestamp:
            self.calibrator.load_calibration(
                cfg.calibration.r_top,
                cfg.calibration.r_mid,
                cfg.calibration.r_bottom
            )
        
        # M5: 滤波器
        self.gaze_filter = GazeFilter(
            ema_alpha=cfg.filter.ema_alpha,
            confidence_min=cfg.filter.confidence_min,
            lost_face_timeout_ms=cfg.filter.lost_face_timeout_ms
        )
        
        # M6: 状态机
        self.intent_fsm = IntentFSM(
            th_on=cfg.thresholds.th_on,
            th_off=cfg.thresholds.th_off,
            dwell_on_ms=cfg.thresholds.dwell_on_ms,
            dwell_off_ms=cfg.thresholds.dwell_off_ms,
            long_blink_ms=cfg.blink.long_blink_ms,
            blink_cooldown_ms=cfg.blink.cooldown_ms
        )
        
        # M7: 滚动控制器
        self.scroll_controller = ScrollController(
            v_max=cfg.scroll.v_max,
            gamma=cfg.scroll.gamma,
            a_up=cfg.scroll.a_up,
            a_down=cfg.scroll.a_down,
            tick_hz=cfg.scroll.tick_hz
        )
        
        # M8: 输入注入
        self.injector = PlatformInjector(
            use_smooth_scroll=cfg.injection.smooth_scroll,
            target_mode=cfg.injection.target,
            target_process=cfg.injection.process_name
        )
    
    def start(self) -> bool:
        """启动系统"""
        self.logger.info("Starting eye scroll controller...")
        
        # 初始化摄像头
        if not self.camera.start():
            self.signals.error_occurred.emit("camera", "无法打开摄像头")
            self._running = False
            return False
        
        # 初始化输入注入
        if not self.injector.init():
            error_detail = getattr(self.injector, "last_error", None)
            message = "无法初始化输入注入"
            if error_detail:
                message = f"{message}（{error_detail}）"
            self.signals.error_occurred.emit("injector", message)
            self.camera.stop()
            self._running = False
            return False
        
        # 重置状态
        self._stop_event.clear()
        self._pause_event.clear()
        self.gaze_filter.reset()
        self.scroll_controller.reset()
        self.intent_fsm.resume()
        
        # 启动工作线程
        self._capture_thread = Thread(target=self._capture_loop, daemon=True)
        self._inference_thread = Thread(target=self._inference_loop, daemon=True)
        self._control_thread = Thread(target=self._control_loop, daemon=True)
        
        self._capture_thread.start()
        self._inference_thread.start()
        self._control_thread.start()
        
        self.logger.info("Eye scroll controller started")
        self._running = True
        return True
    
    def stop(self):
        """停止系统"""
        self.logger.info("Stopping eye scroll controller...")
        
        self._stop_event.set()
        
        # 等待线程结束
        if self._capture_thread:
            self._capture_thread.join(timeout=1.0)
        if self._inference_thread:
            self._inference_thread.join(timeout=1.0)
        if self._control_thread:
            self._control_thread.join(timeout=1.0)
        
        # 清理资源
        self.camera.stop()
        self.injector.shutdown()
        self.scroll_controller.stop()
        
        self.logger.info("Eye scroll controller stopped")
        self._running = False
    
    def pause(self):
        """暂停"""
        self.intent_fsm.pause()
        self.scroll_controller.stop()
    
    def resume(self):
        """恢复"""
        self.intent_fsm.resume()
    
    def toggle_pause(self):
        """切换暂停状态"""
        self.intent_fsm.toggle_pause()
        if self.intent_fsm.is_paused:
            self.scroll_controller.stop()
    
    def _capture_loop(self):
        """T1: 摄像头采集循环"""
        while not self._stop_event.is_set():
            frame, timestamp = self.camera.get_frame()
            
            if frame is not None:
                # 只保留最新帧
                try:
                    # 清空队列中的旧帧
                    while not self._frame_queue.empty():
                        try:
                            self._frame_queue.get_nowait()
                        except Empty:
                            break
                    self._frame_queue.put_nowait((frame, timestamp))
                except:
                    pass
            
            # 简单的帧率控制
            time.sleep(0.001)
    
    def _inference_loop(self):
        """T2: 推理与特征提取循环"""
        while not self._stop_event.is_set():
            try:
                frame, timestamp = self._frame_queue.get(timeout=0.1)
            except Empty:
                continue
            
            # 人脸追踪
            landmarks = self.face_tracker.process(frame)
            
            # 特征提取
            features = self.feature_extractor.extract(landmarks, timestamp)
            
            # 发送到控制线程
            try:
                while not self._feature_queue.empty():
                    try:
                        self._feature_queue.get_nowait()
                    except Empty:
                        break
                self._feature_queue.put_nowait(features)
            except:
                pass
            
            # 发送信号更新 UI
            self.signals.frame_processed.emit(features)
            
            # 更新 FPS
            self._frame_count += 1
            elapsed = time.perf_counter() - self._fps_start_time
            if elapsed >= 1.0:
                self._current_fps = self._frame_count / elapsed
                self._frame_count = 0
                self._fps_start_time = time.perf_counter()
    
    def _control_loop(self):
        """T3: 控制循环"""
        tick_interval = 1.0 / self.config.scroll.tick_hz
        last_tick = time.perf_counter()
        
        while not self._stop_event.is_set():
            # 获取最新特征
            try:
                features: FeaturePacket = self._feature_queue.get(timeout=0.05)
            except Empty:
                features = None
            
            current_time = time.perf_counter()
            dt = current_time - last_tick
            
            if dt < tick_interval:
                time.sleep(tick_interval - dt)
                current_time = time.perf_counter()
                dt = current_time - last_tick
            
            last_tick = current_time
            
            if features is None:
                continue
            
            # 标定映射
            mode = self.config.calibration.mode
            if mode == "head":
                if not self.calibrator.is_calibrated:
                    s_raw = 0.5
                else:
                    s_raw = self.calibrator.map(features.head_pitch)
            else:
                s_raw = self.calibrator.map(features.gaze_y_raw)
            
            # 滤波
            confidence_for_filter = features.confidence
            if mode == "head":
                # 头部模式不依赖眼部置信度
                confidence_for_filter = 1.0 if features.face_present else 0.0

            s_f = self.gaze_filter.update(
                s_raw,
                confidence_for_filter,
                features.face_present,
                features.timestamp
            )
            
            # 状态机更新
            state, v_target = self.intent_fsm.update(
                s_f,
                features.blink_state,
                features.face_present,
                self.gaze_filter.is_face_lost,
                features.timestamp
            )
            
            # 滚动控制
            self.scroll_controller.set_target(v_target)
            scroll_delta = self.scroll_controller.tick(dt)
            
            # 发送滚轮事件
            if scroll_delta != 0 and state == FSMState.SCROLLING:
                self.injector.scroll(scroll_delta)
            
            # 发送状态更新信号
            state_name = state.name
            is_scrolling = state == FSMState.SCROLLING
            self.signals.state_updated.emit(state_name, is_scrolling, s_f, features.confidence)
    
    @property
    def fps(self) -> float:
        return self._current_fps
    
    @property
    def is_paused(self) -> bool:
        return self.intent_fsm.is_paused
    @property
    def is_running(self) -> bool:
        return self._running



class Application:
    """应用程序类"""
    
    def __init__(self):
        # 设置日志
        setup_logging()
        self.logger = get_logger("app")
        
        # 创建 Qt 应用
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        # 应用主题样式
        apply_theme(self.app)
        
        # 创建控制器和 UI
        self.controller = EyeScrollController()
        self.window = MainWindow(
            always_on_top=True,
            toggle_pause_hotkey=self.controller.config.ui.hotkeys.toggle_pause,
            emergency_stop_hotkey=self.controller.config.ui.hotkeys.emergency_stop,
        )
        self._calibration_started_controller = False
        self._calibration_prev_paused = False
        
        # 连接信号
        self._connect_signals()
        
        # UI 更新定时器
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_ui)
        self.update_timer.start(50)  # 20 FPS UI 更新
    
    def _normalize_head_pitch(self, pitch: float) -> float:
        """将头部俯仰角粗略归一化到 0-1（显示/标定引导用）"""
        cfg = self.controller.config.calibration
        min_pitch = cfg.head_pitch_min
        max_pitch = cfg.head_pitch_max
        center = cfg.head_pitch_center
        if max_pitch - min_pitch < 1e-6:
            return 0.5
        value = (pitch - center - min_pitch) / (max_pitch - min_pitch)
        return max(0.0, min(1.0, value))

    def _connect_signals(self):
        """连接控制器和 UI 信号"""
        # UI -> 控制器
        self.window.start_requested.connect(self._on_start)
        self.window.stop_requested.connect(self._on_stop)
        self.window.pause_requested.connect(self._on_pause)
        self.window.calibrate_requested.connect(self._on_calibrate)
        self.window.settings_requested.connect(self._on_settings)
        self.window.speed_changed.connect(self._on_speed_changed)
        self.window.exit_requested.connect(self._on_exit)
        
        # 控制器 -> UI
        self.controller.signals.frame_processed.connect(self._on_frame_processed)
        self.controller.signals.state_updated.connect(self._on_state_updated)
        self.controller.signals.error_occurred.connect(self._on_error)
    
    def _on_start(self):
        """启动"""
        if self.controller.start():
            self.window.set_running(True)
            self.logger.info("System started")
        else:
            self.window.show_error("启动失败", "无法启动眼动控制系统")
    
    def _on_stop(self):
        """停止"""
        self.controller.stop()
        self.window.set_running(False)
        self.logger.info("System stopped")
    
    def _on_speed_changed(self, value: int):
        """??????????"""
        # ? 1-10 ??? v_max 1.0-6.0
        v_max = 1.0 + (value - 1) * 0.55
        self.controller.scroll_controller.set_params(v_max=v_max)

    def _on_pause(self):
        """暂停/恢复"""
        self.controller.toggle_pause()
        self.window.set_paused(self.controller.is_paused)

    def _on_settings(self):
        """打开设置对话框"""
        dialog = SettingsDialog(self.controller.config, self.window, self.window.panel)
        if dialog.exec():
            # 应用注入设置（无需重启）
            inj_cfg = self.controller.config.injection
            if hasattr(self.controller.injector, "target_mode"):
                self.controller.injector.target_mode = inj_cfg.target
            if hasattr(self.controller.injector, "target_process"):
                self.controller.injector.target_process = inj_cfg.process_name
            if hasattr(self.controller.injector, "use_smooth_scroll"):
                self.controller.injector.use_smooth_scroll = inj_cfg.smooth_scroll
            # 应用快捷键（无需重启）
            hk_cfg = self.controller.config.ui.hotkeys
            self.window.update_hotkeys(hk_cfg.toggle_pause, hk_cfg.emergency_stop)
            self.window.show_info("设置", "设置已保存，建议重新标定")

    def _on_calibrate(self):
        """标定"""
        self.logger.info("Starting calibration...")

        wizard = self.window.calibration_wizard
        if wizard:
            try:
                wizard.calibration_complete.disconnect(self._on_calibration_complete)
            except TypeError:
                pass
            try:
                wizard.calibration_cancelled.disconnect(self._on_calibration_cancelled)
            except TypeError:
                pass
            wizard.calibration_complete.connect(self._on_calibration_complete)
            wizard.calibration_cancelled.connect(self._on_calibration_cancelled)

        self._calibration_prev_paused = self.controller.is_paused
        self._calibration_started_controller = False

        if not self.controller.is_running:
            if not self.controller.start():
                self.window.show_error("标定失败", "无法启动摄像头进行标定")
                return
            self._calibration_started_controller = True

        if not self.controller.is_paused:
            self.controller.pause()

    def _on_calibration_complete(self, r_top: float, r_mid: float, r_bottom: float):
        """标定完成"""
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.controller.calibrator.load_calibration(r_top, r_mid, r_bottom)
        self.controller.config.update_calibration(r_top, r_mid, r_bottom, timestamp)
        if not self.controller.config.save():
            self.logger.warning("Failed to save calibration config")
        self.window.show_info("标定完成", "标定参数已保存")
        self._finish_calibration_flow()

    def _on_calibration_cancelled(self):
        """标定取消"""
        self._finish_calibration_flow()

    def _finish_calibration_flow(self):
        if self._calibration_started_controller:
            self.controller.stop()
        elif not self._calibration_prev_paused:
            self.controller.resume()

    def _on_exit(self):
        """退出"""
        self.controller.stop()
        self.app.quit()
    
    def _on_frame_processed(self, features: FeaturePacket):
        """帧处理完成"""
        self.window.update_face_status(features.face_present, features.confidence)
        self.window.head_pitch_updated.emit(features.head_pitch)
        mode = self.controller.config.calibration.mode
        if mode == "head":
            display_value = self._normalize_head_pitch(features.head_pitch)
            self.window.update_calibration_gaze(display_value, features.head_pitch)
        else:
            self.window.update_calibration_gaze(features.gaze_y_raw)
    
    def _on_state_updated(self, state_name: str, is_scrolling: bool, s_f: float, confidence: float):
        """状态更新"""
        self.window.update_fsm_state(state_name, is_scrolling)
        self.window.update_gaze(s_f)
        self.window.set_paused(state_name == 'PAUSED')
    
    def _on_error(self, component: str, message: str):
        """错误处理"""
        self.logger.error(f"Error in {component}: {message}")
        self.window.show_error(f"{component} 错误", message)
    
    def _update_ui(self):
        """定时 UI 更新"""
        self.window.update_fps(self.controller.fps)
    
    def run(self) -> int:
        """运行应用"""
        self.logger.info("Starting application...")
        self.window.show()
        return self.app.exec()


def main():
    """程序入口"""
    app = Application()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
