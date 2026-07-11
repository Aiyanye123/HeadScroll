"""Dual-mode hand page turning and head scrolling application."""

import sys
import time
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Thread, current_thread
from typing import Optional

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from calibration import Calibrator
from capture import Camera
from control.intent_fsm import FSMState, IntentFSM
from control.page_turn_fsm import PageAction, PageTurnFSM
from control.scroll_controller import ScrollController
from injection import PlatformInjector
from processing import GazeFilter
from tracking.face_tracker import FaceTracker
from tracking.feature_extractor import BlinkState, FeatureExtractor, FeaturePacket
from tracking.hand_gesture import HandGestureFrame, HandGestureTracker
from ui import MainWindow
from ui.settings_dialog import SettingsDialog
from ui.styles import apply_theme
from utils import Config, get_logger, setup_logging


class WorkerSignals(QObject):
    frame_processed = Signal(object)
    state_updated = Signal(str, bool)
    action_triggered = Signal(str)
    error_occurred = Signal(str, str)


class InteractionController:
    def __init__(self) -> None:
        self.logger = get_logger("controller")
        self.config = Config()
        self.config.load()
        self.camera = Camera(
            index=self.config.camera.index,
            width=self.config.camera.width,
            height=self.config.camera.height,
            target_fps=self.config.camera.target_fps,
        )
        self.injector = PlatformInjector()
        self.tracker: Optional[object] = None
        self.feature_extractor: Optional[FeatureExtractor] = None
        self.calibrator = Calibrator()
        self.page_fsm: PageTurnFSM
        self.head_fsm: IntentFSM
        self.gaze_filter: GazeFilter
        self.scroll_controller: ScrollController
        self._configure_mode_components()
        self.signals = WorkerSignals()
        self._frames: Queue = Queue(maxsize=1)
        self._features: Queue = Queue(maxsize=1)
        self._stop_event = Event()
        self._capture_thread: Optional[Thread] = None
        self._inference_thread: Optional[Thread] = None
        self._control_thread: Optional[Thread] = None
        self._frame_count = 0
        self._fps_started_at = time.perf_counter()
        self._fps = 0.0
        self._running = False

    def _configure_mode_components(self) -> None:
        gesture = self.config.gesture
        self.page_fsm = PageTurnFSM(
            arm_duration_ms=gesture.arm_duration_ms,
            min_swipe_distance=gesture.min_swipe_distance,
            max_vertical_drift=gesture.max_vertical_drift,
            max_swipe_duration_ms=gesture.max_swipe_duration_ms,
            cooldown_ms=gesture.cooldown_ms,
            fist_hold_ms=gesture.fist_hold_ms,
            arm_stability_radius=gesture.arm_stability_radius,
            min_swipe_duration_ms=gesture.min_swipe_duration_ms,
            min_swipe_speed=gesture.min_swipe_speed,
            direction_consistency=gesture.direction_consistency,
            activation_gesture=gesture.activation_gesture,
        )
        thresholds = self.config.thresholds
        blink = self.config.blink
        self.head_fsm = IntentFSM(
            th_on=thresholds.th_on,
            th_off=thresholds.th_off,
            dwell_on_ms=thresholds.dwell_on_ms,
            dwell_off_ms=thresholds.dwell_off_ms,
            long_blink_ms=blink.long_blink_ms,
            blink_cooldown_ms=blink.cooldown_ms,
        )
        filter_config = self.config.filter
        self.gaze_filter = GazeFilter(
            ema_alpha=filter_config.ema_alpha,
            confidence_min=filter_config.confidence_min,
            lost_face_timeout_ms=filter_config.lost_face_timeout_ms,
        )
        scroll = self.config.scroll
        self.scroll_controller = ScrollController(
            v_max=scroll.v_max,
            gamma=scroll.gamma,
            a_up=scroll.a_up,
            a_down=scroll.a_down,
            tick_hz=scroll.tick_hz,
        )
        self.calibrator = Calibrator()
        calibration = self.config.calibration
        if calibration.timestamp:
            try:
                self.calibrator.load_calibration(
                    calibration.r_top, calibration.r_mid, calibration.r_bottom
                )
            except ValueError as exc:
                self.logger.warning("Ignoring invalid saved calibration: %s", exc)

    def start(self) -> bool:
        if self._running:
            return True
        try:
            if self.tracker is None:
                if self.mode == "hand":
                    gesture = self.config.gesture
                    self.tracker = HandGestureTracker(
                        model_path=gesture.model_path,
                        min_confidence=gesture.min_confidence,
                        mirror=gesture.mirror,
                    )
                else:
                    self.tracker = FaceTracker()
                    self.feature_extractor = FeatureExtractor()
            if not self.injector.init():
                raise RuntimeError(self.injector.last_error or "无法初始化输入注入")
            if not self.camera.start():
                raise RuntimeError("无法打开摄像头")
        except Exception as exc:
            self.camera.stop()
            self.injector.shutdown()
            self.signals.error_occurred.emit("启动", str(exc))
            return False

        self._drain_queues()
        self._stop_event.clear()
        self.page_fsm.resume()
        self.head_fsm.resume()
        self.gaze_filter.reset()
        self.scroll_controller.reset()
        self._frame_count = 0
        self._fps_started_at = time.perf_counter()
        self._capture_thread = Thread(target=self._capture_loop, daemon=True)
        self._inference_thread = Thread(target=self._inference_loop, daemon=True)
        self._control_thread = (
            Thread(target=self._head_control_loop, daemon=True)
            if self.mode == "head"
            else None
        )
        self._running = True
        self._capture_thread.start()
        self._inference_thread.start()
        if self._control_thread:
            self._control_thread.start()
        self.logger.info("Controller started in %s mode", self.mode)
        return True

    def stop(self) -> None:
        if not self._running:
            return
        self._stop_event.set()
        for thread in (
            self._capture_thread,
            self._inference_thread,
            self._control_thread,
        ):
            if thread and thread is not current_thread():
                thread.join(timeout=1.5)
        self.scroll_controller.stop()
        self.camera.stop()
        self.injector.shutdown()
        self._drain_queues()
        self._running = False
        self.logger.info("Controller stopped")

    def shutdown(self) -> None:
        self.stop()
        self._close_tracker()

    def _close_tracker(self) -> None:
        if self.tracker is not None:
            self.tracker.close()
            self.tracker = None
        self.feature_extractor = None

    def reload_settings(self) -> bool:
        was_running = self._running
        was_paused = self.is_paused
        self.stop()
        self._close_tracker()
        self._configure_mode_components()
        if was_running and not self.start():
            return False
        if was_paused:
            self.pause()
        return True

    def toggle_pause(self) -> None:
        if self.mode == "hand":
            self.page_fsm.toggle_pause()
            state, paused = self.page_fsm.state.name, self.page_fsm.is_paused
        else:
            self.head_fsm.toggle_pause()
            if self.head_fsm.is_paused:
                self.scroll_controller.stop()
            state, paused = self.head_fsm.state.name, self.head_fsm.is_paused
        self.signals.state_updated.emit(state, paused)

    def pause(self) -> None:
        if self.mode == "hand":
            self.page_fsm.pause()
        else:
            self.head_fsm.pause()
            self.scroll_controller.stop()

    def resume(self) -> None:
        if self.mode == "hand":
            self.page_fsm.resume()
        else:
            self.head_fsm.resume()

    def set_sensitivity(self, value: int) -> None:
        if self.mode == "hand":
            self.page_fsm.min_swipe_distance = max(0.08, 0.28 - value * 0.02)
        else:
            self.scroll_controller.v_max = 1.0 + (value - 1) * 0.55

    def _capture_loop(self) -> None:
        failures = 0
        try:
            while not self._stop_event.is_set():
                frame, timestamp = self.camera.get_frame()
                if frame is None:
                    failures += 1
                    if failures >= 100:
                        raise RuntimeError("摄像头连续读取失败")
                    time.sleep(0.01)
                    continue
                failures = 0
                self._put_latest(self._frames, (frame, timestamp))
        except Exception as exc:
            self._worker_failed("摄像头", exc)

    def _inference_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                try:
                    frame, timestamp = self._frames.get(timeout=0.1)
                except Empty:
                    continue
                if self.mode == "hand":
                    self._process_hand_frame(frame, timestamp)
                else:
                    self._process_head_frame(frame, timestamp)
                self._update_fps()
        except Exception as exc:
            self._worker_failed("视觉识别", exc)

    def _process_hand_frame(self, frame, timestamp: float) -> None:
        result = self.tracker.process(frame, timestamp)
        action = self.page_fsm.update(
            result.gesture,
            result.palm_x,
            result.palm_y,
            result.timestamp,
            result.handedness,
        )
        if action != PageAction.NONE:
            key = (
                self.config.gesture.next_key
                if action == PageAction.NEXT
                else self.config.gesture.previous_key
            )
            if not self.injector.press_key(key):
                raise RuntimeError(self.injector.last_error or "翻页按键发送失败")
            self.logger.info("PAGE_%s", action.name)
            self.signals.action_triggered.emit(action.name)
        self.signals.frame_processed.emit(result)
        self.signals.state_updated.emit(
            self.page_fsm.state.name, self.page_fsm.is_paused
        )

    def _process_head_frame(self, frame, timestamp: float) -> None:
        landmarks = self.tracker.process(frame)
        features = self.feature_extractor.extract(landmarks, timestamp)
        self._put_latest(self._features, features)
        self.signals.frame_processed.emit(features)

    def _head_control_loop(self) -> None:
        interval = 1.0 / self.config.scroll.tick_hz
        last_tick = time.perf_counter()
        next_tick = last_tick
        latest: Optional[FeaturePacket] = None
        processed_timestamp = -1.0
        state = self.head_fsm.state
        last_ui_emit = 0.0
        try:
            while not self._stop_event.is_set():
                now = time.perf_counter()
                if now < next_tick:
                    self._stop_event.wait(next_tick - now)
                    continue
                dt = min(max(now - last_tick, 0.0), 0.1)
                last_tick = now
                next_tick = now + interval
                try:
                    while True:
                        latest = self._features.get_nowait()
                except Empty:
                    pass

                if latest and latest.timestamp != processed_timestamp:
                    processed_timestamp = latest.timestamp
                    if self.calibrator.is_calibrated:
                        raw = self.calibrator.map(latest.head_pitch)
                        filtered = self.gaze_filter.update(
                            raw,
                            1.0 if latest.face_present else 0.0,
                            latest.face_present,
                            latest.timestamp,
                        )
                        state, target = self.head_fsm.update(
                            filtered,
                            latest.blink_state,
                            latest.face_present,
                            self.gaze_filter.is_face_lost,
                            latest.timestamp,
                        )
                        self.scroll_controller.set_target(target)
                    else:
                        self.scroll_controller.stop()
                elif latest is None or now - latest.timestamp > (
                    self.config.filter.lost_face_timeout_ms / 1000
                ):
                    self.scroll_controller.stop()
                    state, _ = self.head_fsm.update(
                        0.5,
                        latest.blink_state if latest else BlinkState.OPEN,
                        False,
                        True,
                        now,
                    )

                delta = self.scroll_controller.tick(dt)
                if delta and state == FSMState.SCROLLING:
                    if not self.injector.scroll(delta):
                        raise RuntimeError(self.injector.last_error or "滚动注入失败")
                status = state.name if self.calibrator.is_calibrated else "NEEDS_CALIBRATION"
                if now - last_ui_emit >= 0.05:
                    self.signals.state_updated.emit(status, self.head_fsm.is_paused)
                    last_ui_emit = now
        except Exception as exc:
            self._worker_failed("头部滚动", exc)

    @staticmethod
    def _put_latest(queue: Queue, item: object) -> None:
        try:
            queue.put_nowait(item)
        except Full:
            try:
                queue.get_nowait()
            except Empty:
                pass
            queue.put_nowait(item)

    def _drain_queues(self) -> None:
        for queue in (self._frames, self._features):
            while True:
                try:
                    queue.get_nowait()
                except Empty:
                    break

    def _worker_failed(self, component: str, exc: Exception) -> None:
        self.logger.exception("%s worker failed", component)
        self.stop()
        self.signals.error_occurred.emit(component, str(exc))

    def _update_fps(self) -> None:
        self._frame_count += 1
        elapsed = time.perf_counter() - self._fps_started_at
        if elapsed >= 1.0:
            self._fps = self._frame_count / elapsed
            self._frame_count = 0
            self._fps_started_at = time.perf_counter()

    def head_preview_position(self, pitch: float) -> float:
        calibration = self.config.calibration
        span = calibration.r_bottom - calibration.r_top
        if abs(span) < 1e-6:
            return 0.5
        return max(0.0, min(1.0, (pitch - calibration.r_top) / span))

    @property
    def mode(self) -> str:
        return self.config.mode

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self.page_fsm.is_paused if self.mode == "hand" else self.head_fsm.is_paused


class Application:
    def __init__(self) -> None:
        self.controller = InteractionController()
        setup_logging(log_file=str(self.controller.config.app_dir / "logs" / "headscroll.log"))
        self.logger = get_logger("app")
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("HeadScroll")
        self.app.setOrganizationName("HeadScroll")
        self.app.setQuitOnLastWindowClosed(False)
        apply_theme(self.app)
        self.window = MainWindow(
            always_on_top=self.controller.config.ui.always_on_top,
            toggle_pause_hotkey=self.controller.config.ui.hotkeys.toggle_pause,
            emergency_stop_hotkey=self.controller.config.ui.hotkeys.emergency_stop,
        )
        self.window.set_mode(self.controller.mode)
        self._calibration_started_controller = False
        self._calibration_was_paused = False
        self._connect_signals()
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(lambda: self.window.update_fps(self.controller.fps))
        self.update_timer.start(100)

    def _connect_signals(self) -> None:
        self.window.start_requested.connect(self._on_start)
        self.window.stop_requested.connect(self._on_stop)
        self.window.pause_requested.connect(self._on_pause)
        self.window.calibrate_requested.connect(self._on_calibrate)
        self.window.calibration_complete.connect(self._on_calibration_complete)
        self.window.calibration_cancelled.connect(self._finish_calibration)
        self.window.settings_requested.connect(self._on_settings)
        self.window.sensitivity_changed.connect(self.controller.set_sensitivity)
        self.window.exit_requested.connect(self._on_exit)
        self.controller.signals.frame_processed.connect(self._on_frame_processed)
        self.controller.signals.state_updated.connect(self._on_state_updated)
        self.controller.signals.action_triggered.connect(self._on_action)
        self.controller.signals.error_occurred.connect(self._on_error)

    def _on_start(self) -> None:
        self.window.set_running(self.controller.start())

    def _on_stop(self) -> None:
        self.controller.stop()
        self.window.set_running(False)

    def _on_pause(self) -> None:
        self.controller.toggle_pause()

    def _on_settings(self) -> None:
        dialog = SettingsDialog(self.controller.config, self.window.panel)
        if dialog.exec():
            hotkeys = self.controller.config.ui.hotkeys
            self.window.update_hotkeys(hotkeys.toggle_pause, hotkeys.emergency_stop)
            if self.controller.reload_settings():
                self.window.set_mode(self.controller.mode)
                self.window.set_running(self.controller.is_running)
            else:
                self.window.show_error("设置", "设置已保存，但重新启动识别失败")

    def _on_calibrate(self) -> None:
        if self.controller.mode != "head":
            return
        self._calibration_started_controller = not self.controller.is_running
        self._calibration_was_paused = self.controller.is_paused
        if self._calibration_started_controller and not self.controller.start():
            self.window.show_error("标定失败", "无法启动摄像头")
            return
        self.controller.pause()

    def _on_calibration_complete(self, top: float, middle: float, bottom: float) -> None:
        try:
            self.controller.calibrator.load_calibration(top, middle, bottom)
        except ValueError as exc:
            self.window.show_error("标定失败", str(exc))
            return
        calibration = self.controller.config.calibration
        calibration.r_top = top
        calibration.r_mid = middle
        calibration.r_bottom = bottom
        calibration.timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        calibration.pose_source = "matrix"
        if not self.controller.config.save():
            self.window.show_error("标定失败", "无法保存标定参数")
        self._finish_calibration()

    def _finish_calibration(self) -> None:
        if self._calibration_started_controller:
            self.controller.stop()
            self.window.set_running(False)
        elif not self._calibration_was_paused:
            self.controller.resume()

    def _on_frame_processed(self, frame: object) -> None:
        if isinstance(frame, HandGestureFrame):
            self.window.update_detection(
                frame.hand_present,
                f"{frame.handedness} {frame.gesture}".strip(),
                frame.confidence,
            )
            self.window.update_position(frame.palm_x)
        else:
            self.window.update_detection(frame.face_present, "头部", frame.confidence)
            self.window.update_position(self.controller.head_preview_position(frame.head_pitch))
            self.window.update_calibration_value(
                self.controller.head_preview_position(frame.head_pitch), frame.head_pitch
            )

    def _on_state_updated(self, state: str, paused: bool) -> None:
        self.window.update_control_state(state)
        self.window.set_paused(paused)

    def _on_action(self, action: str) -> None:
        self.window.update_last_action("下一页" if action == "NEXT" else "上一页")

    def _on_error(self, component: str, message: str) -> None:
        self.window.set_running(False)
        self.window.show_error(f"{component}错误", message)

    def _on_exit(self) -> None:
        self.window.shutdown_hotkeys()
        self.controller.shutdown()
        self.app.quit()

    def run(self) -> int:
        self.window.show()
        return self.app.exec()


def main() -> None:
    application = Application()
    sys.exit(application.run())


if __name__ == "__main__":
    main()
