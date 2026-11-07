"""Dual-mode voice page turning and head scrolling application."""

import sys
import time
from contextlib import contextmanager
from math import isfinite
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, RLock, Thread, current_thread
from typing import Optional

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from calibration import Calibrator
from capture import Camera
from control.intent_fsm import FSMState, IntentFSM
from control.scroll_controller import ScrollController
from injection import PlatformInjector
from processing import GazeFilter
from tracking.face_tracker import FaceTracker, HEAD_POSE_MATRIX_ALGORITHM
from tracking.feature_extractor import FeatureExtractor, FeaturePacket
from tracking.speech_recognizer import CommandParser, SpeechRecognizer, VoiceCommand
from ui import MainWindow
from ui.settings_dialog import SettingsDialog
from ui.head_center_dialog import HeadCenterCalibrationDialog
from ui.styles import apply_theme
from utils import Config, get_logger, setup_logging


class WorkerSignals(QObject):
    frame_processed = Signal(object)
    transcript_recognized = Signal(str)
    state_updated = Signal(str, bool)
    action_triggered = Signal(str)
    error_occurred = Signal(str, str)


class InteractionController:
    def __init__(self) -> None:
        self.logger = get_logger("controller")
        self._lifecycle_lock = RLock()
        self._control_lock = RLock()
        self.config = Config()
        self.config.load()
        self.camera = Camera(
            index=self.config.camera.index,
            width=self.config.camera.width,
            height=self.config.camera.height,
            target_fps=self.config.camera.target_fps,
        )
        self.injector = PlatformInjector(
            use_smooth_scroll=self.config.injection.smooth_scroll,
            target_mode=self.config.injection.target,
            target_process=self.config.injection.process_name,
        )
        self.tracker: Optional[object] = None
        self.feature_extractor: Optional[FeatureExtractor] = None
        self.calibrator = Calibrator()
        self.speech_recognizer: Optional[SpeechRecognizer] = None
        self._voice_paused = False
        self._last_voice_action_at = 0.0
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
        self._head_calibration_active = False
        self._last_feature_timestamp = 0.0

    def _configure_mode_components(self) -> None:
        thresholds = self.config.thresholds
        self.head_fsm = IntentFSM(
            th_on=thresholds.th_on,
            th_off=thresholds.th_off,
            dwell_on_ms=thresholds.dwell_on_ms,
            dwell_off_ms=thresholds.dwell_off_ms,
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
        self._calibration_key = None

    def start(self, *, paused: bool = False) -> bool:
        with self._lifecycle_lock:
            return self._start(paused=paused)

    def _start(self, *, paused: bool = False) -> bool:
        if self._running:
            return True
        if any(thread and thread.is_alive() for thread in self._worker_threads()):
            self.signals.error_occurred.emit("启动", "上次运行的线程仍在退出，请稍后重试")
            return False
        try:
            if self.mode == "voice":
                voice = self.config.voice
                parser = CommandParser(
                    voice.previous_phrases,
                    voice.next_phrases,
                    voice.pause_phrases,
                    voice.resume_phrases,
                    voice.wake_words,
                    voice.require_wake_word,
                )
                self.speech_recognizer = SpeechRecognizer(
                    self._voice_model_path(), parser, voice.device,
                    voice.sample_rate, voice.latency_mode
                )
            elif self.tracker is None:
                self.tracker = FaceTracker(refine_landmarks=False)
                self.feature_extractor = FeatureExtractor()
            if not self.injector.init():
                raise RuntimeError(self.injector.last_error or "无法初始化输入注入")
            if self.mode == "head" and not self.camera.start():
                raise RuntimeError("无法打开摄像头")
        except Exception as exc:
            self.camera.stop()
            self.injector.shutdown()
            self.signals.error_occurred.emit("启动", str(exc))
            return False

        with self._control_lock:
            self._stop_event.clear()
            self._voice_paused = paused
            self._last_voice_action_at = 0.0
            self.head_fsm.reset(paused=paused)
            self._reset_head_motion()
            self._sync_head_calibration()
            self._drain_queues()
        self._frame_count = 0
        self._fps_started_at = time.perf_counter()
        self._fps = 0.0
        if self.mode == "voice":
            self._capture_thread = None
            self._inference_thread = Thread(target=self._voice_loop, daemon=True)
            self._control_thread = None
        else:
            self._capture_thread = Thread(target=self._capture_loop, daemon=True)
            self._inference_thread = Thread(target=self._inference_loop, daemon=True)
            self._control_thread = Thread(target=self._head_control_loop, daemon=True)
        self._running = True
        if self._capture_thread:
            self._capture_thread.start()
        self._inference_thread.start()
        if self._control_thread:
            self._control_thread.start()
        self.logger.info("Controller started in %s mode", self.mode)
        return True

    def stop(self) -> None:
        with self._lifecycle_lock:
            self._stop()

    def _worker_threads(self):
        return self._capture_thread, self._inference_thread, self._control_thread

    def _stop(self) -> None:
        self._stop_event.set()
        with self._control_lock:
            self._running = False
            self.head_fsm.reset()
            self._reset_head_motion()
            self._voice_paused = False
            self._fps = 0.0
            self.injector.shutdown()
            self._drain_queues()
        for thread in self._worker_threads():
            if thread and thread is not current_thread():
                thread.join(timeout=1.5)
        if not self._capture_thread or not self._capture_thread.is_alive():
            self.camera.stop()
        if not self._inference_thread or not self._inference_thread.is_alive():
            self.speech_recognizer = None
        self.logger.info("Controller stopped")

    def shutdown(self) -> None:
        self.stop()
        self._close_tracker()

    @contextmanager
    def head_calibration_session(self):
        """Temporarily collect head frames without enabling input output."""
        previous_mode = self.mode
        was_running = self.is_running
        was_paused = self.is_paused
        self.stop()
        self.config.config.mode = "head"
        started = False
        self._head_calibration_active = True
        try:
            started = self.start(paused=True)
            yield started
        finally:
            # An explicit stop or worker failure during calibration stays stopped.
            restore_running = was_running and (not started or self.is_running)
            self.stop()
            self.config.config.mode = previous_mode
            self._head_calibration_active = False
            if restore_running:
                self.start(paused=was_paused)
            elif was_paused:
                self.pause()

    def _close_tracker(self) -> None:
        if self._inference_thread and self._inference_thread.is_alive():
            self.logger.warning("Tracker left open while inference worker exits")
            return
        if self.tracker is not None:
            self.tracker.close()
            self.tracker = None
        self.feature_extractor = None

    def reload_settings(self, was_paused: Optional[bool] = None) -> bool:
        with self._lifecycle_lock:
            was_running = self._running
            if was_paused is None:
                was_paused = self.is_paused
            self._stop()
            if any(thread and thread.is_alive() for thread in self._worker_threads()):
                self.signals.error_occurred.emit("设置", "识别线程仍在退出，请稍后重试")
                return False
            self._close_tracker()
            self._configure_mode_components()
            self.injector.use_smooth_scroll = self.config.injection.smooth_scroll
            self.injector.target_mode = self.config.injection.target
            self.injector.target_process = self.config.injection.process_name
            if was_running and not self._start(paused=was_paused):
                return False
            if was_paused and not was_running:
                self.pause()
            return True

    def toggle_pause(self) -> None:
        with self._control_lock:
            if not self._running or self._head_calibration_active:
                return
            if self.mode == "voice":
                self._voice_paused = not self._voice_paused
                state = "PAUSED" if self._voice_paused else "LISTENING"
                paused = self._voice_paused
            else:
                self.head_fsm.toggle_pause()
                self._reset_head_motion()
                state, paused = self.head_fsm.state.name, self.head_fsm.is_paused
        self.signals.state_updated.emit(state, paused)

    def pause(self) -> None:
        with self._control_lock:
            if self.mode == "voice":
                self._voice_paused = True
            else:
                self.head_fsm.pause()
                self._reset_head_motion()
        if self._running:
            self.signals.state_updated.emit("PAUSED", True)

    def resume(self) -> None:
        with self._control_lock:
            if not self._running or self._head_calibration_active:
                return
            if self.mode == "voice":
                self._voice_paused = False
            else:
                self._reset_head_motion()
                self.head_fsm.resume()
            state = "LISTENING" if self.mode == "voice" else self.head_fsm.state.name
        self.signals.state_updated.emit(state, False)

    def set_sensitivity(self, value: int) -> None:
        if self.mode == "head":
            with self._control_lock:
                self.scroll_controller.v_max = 1.0 + (value - 1) * 0.55

    def _voice_model_path(self) -> str:
        if self.config.voice.model_path:
            return self.config.voice.model_path
        root = Path(getattr(sys, "_MEIPASS", _ROOT.parent))
        return str(root / "assets" / "models" / "vosk-model-small-cn-0.22")

    def _voice_loop(self) -> None:
        try:
            self.signals.state_updated.emit(
                "PAUSED" if self._voice_paused else "LISTENING", self._voice_paused
            )
            self.speech_recognizer.run(self._stop_event, self._on_voice_command)
        except Exception as exc:
            self._worker_failed("语音识别", exc)

    def _on_voice_command(self, command: VoiceCommand) -> None:
        with self._control_lock:
            if self._stop_event.is_set() or not self._running:
                return
            self._apply_voice_command(command)

    def _apply_voice_command(self, command: VoiceCommand) -> None:
        self.signals.transcript_recognized.emit(command.transcript)
        if command.action == "PAUSE":
            self._voice_paused = True
        elif command.action == "RESUME":
            self._voice_paused = False
        elif not self._voice_paused:
            now = time.monotonic()
            if now - self._last_voice_action_at >= self.config.voice.cooldown_ms / 1000:
                key = (
                    self.config.voice.next_key
                    if command.action == "NEXT"
                    else self.config.voice.previous_key
                )
                if not self.injector.press_key(key):
                    raise RuntimeError(self.injector.last_error or "翻页按键发送失败")
                self._last_voice_action_at = now
                self.signals.action_triggered.emit(command.action)
        self.signals.state_updated.emit(
            "PAUSED" if self._voice_paused else "LISTENING", self._voice_paused
        )

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
                if not self._stop_event.is_set():
                    self._put_latest(self._frames, (frame, timestamp))
        except Exception as exc:
            self._worker_failed("摄像头", exc)
        finally:
            self.camera.stop()

    def _inference_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                try:
                    frame, timestamp = self._frames.get(timeout=0.1)
                except Empty:
                    continue
                self._process_head_frame(frame, timestamp)
                self._update_fps()
        except Exception as exc:
            self._worker_failed("视觉识别", exc)

    def _process_head_frame(self, frame, timestamp: float) -> None:
        landmarks = self.tracker.process(frame)
        features = self.feature_extractor.extract(landmarks, timestamp)
        if self._stop_event.is_set():
            return
        self._put_latest(self._features, features)
        self.signals.frame_processed.emit(features)

    def _head_control_loop(self) -> None:
        interval = 1.0 / self.config.scroll.tick_hz
        next_tick = time.perf_counter() + interval
        try:
            while not self._stop_event.is_set():
                try:
                    features = self._features.get(
                        timeout=max(0.0, next_tick - time.perf_counter())
                    )
                except Empty:
                    features = None
                with self._control_lock:
                    if self._stop_event.is_set():
                        break
                    now = time.perf_counter()
                    self._sync_head_calibration()
                    self._expire_head_features(now)
                    if features is not None:
                        self._process_head_features(features, now)
                    if now >= next_tick:
                        self._head_output_tick(interval, now)
                        # Drop missed ticks instead of integrating a delayed burst.
                        next_tick = time.perf_counter() + interval
        except Exception as exc:
            self._worker_failed("头部滚动", exc)

    def _reset_head_motion(self) -> None:
        self.gaze_filter.reset()
        self.scroll_controller.reset()
        self.head_fsm.reset(paused=self.head_fsm.is_paused)
        self._last_feature_timestamp = time.perf_counter()

    def _sync_head_calibration(self) -> None:
        calibration = self.config.calibration
        algorithm = self.tracker.head_pose_algorithm if self.tracker is not None else None
        reference = (calibration.r_top, calibration.r_mid, calibration.r_bottom)
        key = (algorithm, calibration.reference_algorithm, calibration.timestamp, reference)
        if key == self._calibration_key:
            return
        self.calibrator.clear()
        if algorithm and calibration.timestamp and calibration.reference_algorithm == algorithm:
            try:
                error = Calibrator.head_reference_error(*reference)
                if error:
                    raise ValueError(error)
                self.calibrator.load_calibration(*reference)
            except ValueError as exc:
                self.logger.warning("Ignoring invalid saved calibration: %s", exc)
        self._calibration_key = key
        self._reset_head_motion()

    def save_head_calibration(self, top: float, middle: float, bottom: float) -> bool:
        with self._control_lock:
            error = Calibrator.head_reference_error(top, middle, bottom)
            if error:
                raise ValueError(error)
            if self.tracker is None:
                raise ValueError("请先启动头部识别")
            calibration = self.config.calibration
            calibration.r_top, calibration.r_mid, calibration.r_bottom = top, middle, bottom
            calibration.timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
            calibration.reference_algorithm = self.tracker.head_pose_algorithm
            calibration.pose_source = (
                "matrix" if calibration.reference_algorithm == HEAD_POSE_MATRIX_ALGORITHM
                else "landmarks"
            )
            self._sync_head_calibration()
            return self.config.save()

    def has_valid_head_pose(self, features: FeaturePacket) -> bool:
        return (
            features.face_present
            and features.head_pose_valid
            and isfinite(features.head_pitch)
            and self.tracker is not None
            and features.head_pose_algorithm == self.tracker.head_pose_algorithm
        )

    def _expire_head_features(self, now: float) -> None:
        if now - self._last_feature_timestamp > self.config.filter.lost_face_timeout_ms / 1000:
            self._reset_head_motion()
            self.signals.state_updated.emit("FACE_LOST", self.head_fsm.is_paused)

    def _process_head_features(self, features: FeaturePacket, now: float) -> None:
        max_age = self.config.filter.lost_face_timeout_ms / 1000
        if (
            not isfinite(features.timestamp)
            or features.timestamp <= self._last_feature_timestamp
            or not 0.0 <= now - features.timestamp <= max_age
        ):
            return
        self._last_feature_timestamp = features.timestamp
        if not self.calibrator.is_calibrated or not self.has_valid_head_pose(features):
            self._reset_head_motion()
            status = "NEEDS_CALIBRATION" if not self.calibrator.is_calibrated else "INVALID_POSE"
            self.signals.state_updated.emit(status, self.head_fsm.is_paused)
            return
        filtered = self.gaze_filter.update(
            self.calibrator.map(features.head_pitch), 1.0, True, features.timestamp
        )
        state, target = self.head_fsm.update(filtered, True, False, features.timestamp)
        self.scroll_controller.set_target(target)
        self.signals.state_updated.emit(state.name, self.head_fsm.is_paused)

    def _head_output_tick(self, dt: float, now: float) -> None:
        self._expire_head_features(now)
        if (
            self._stop_event.is_set() or self._head_calibration_active
            or self.head_fsm.state != FSMState.SCROLLING
        ):
            self.scroll_controller.stop()
            return
        wheel_units = self.scroll_controller.tick(
            dt, smooth_scroll=self.injector.use_smooth_scroll
        )
        if wheel_units and not self.injector.scroll(wheel_units):
            raise RuntimeError(self.injector.last_error or "滚动注入失败")

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
        self._stop_event.set()
        with self._control_lock:
            self._running = False
            self.head_fsm.reset()
            self._reset_head_motion()
            self.injector.shutdown()
        self.signals.error_occurred.emit(component, str(exc))

    def _update_fps(self) -> None:
        if not self._running:
            return
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
        return self._voice_paused if self.mode == "voice" else self.head_fsm.is_paused


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
        self.controller.signals.transcript_recognized.connect(self.window.update_transcript)
        self.controller.signals.state_updated.connect(self._on_state_updated)
        self.controller.signals.action_triggered.connect(self._on_action)
        self.controller.signals.error_occurred.connect(self._on_error)

    def _on_start(self) -> None:
        running = self.controller.start()
        self.window.set_running(running)
        self.window.set_paused(self.controller.is_paused if running else False)
        if running:
            status = "LISTENING" if self.controller.mode == "voice" else (
                self.controller.head_fsm.state.name if self.controller.calibrator.is_calibrated
                else "NEEDS_CALIBRATION"
            )
            self.window.update_control_state(status)

    def _on_stop(self) -> None:
        self.controller.stop()
        self.window.set_running(False)
        if self.window.calibration_wizard.isVisible():
            self.window.calibration_wizard.reject()

    def _on_pause(self) -> None:
        self.controller.toggle_pause()

    def _on_settings(self) -> None:
        was_paused = self.controller.is_paused
        self.controller.pause()
        self.window.set_paused(self.controller.is_running)
        dialog = SettingsDialog(
            self.controller.config, self.window.panel,
            calibrate_head_range=self._calibrate_head_range,
        )
        if dialog.exec():
            if dialog.head_reference is not None:
                if not self.controller.save_head_calibration(*dialog.head_reference):
                    self.window.show_error("头部范围", "无法保存头部范围")
            hotkeys = self.controller.config.ui.hotkeys
            self.window.update_hotkeys(hotkeys.toggle_pause, hotkeys.emergency_stop)
            if self.controller.reload_settings(was_paused):
                self.window.set_mode(self.controller.mode)
                self.window.set_running(self.controller.is_running)
                self.window.set_paused(self.controller.is_paused if self.controller.is_running else False)
            else:
                self.window.set_running(False)
                self.window.show_error("设置", "设置已保存，但重新启动识别失败")
        elif not was_paused:
            self.controller.resume()
            self.window.set_paused(False)

    def _calibrate_head_range(self, parent):
        reference = None
        try:
            with self.controller.head_calibration_session() as started:
                if started:
                    self.window.set_running(True)
                    self.window.set_paused(True)
                    dialog = HeadCenterCalibrationDialog(
                        self.window, self.controller.config.filter.lost_face_timeout_ms / 1000,
                        parent,
                    )
                    if dialog.exec():
                        reference = dialog.reference
        finally:
            self.window.set_mode(self.controller.mode)
            self.window.set_running(self.controller.is_running)
            paused = self.controller.is_running and self.controller.is_paused
            self.window.set_paused(paused)
            if self.controller.is_running:
                if paused:
                    state = "PAUSED"
                elif self.controller.mode == "voice":
                    state = "LISTENING"
                else:
                    state = self.controller.head_fsm.state.name
                self.window.update_control_state(state)
        return reference

    def _on_calibrate(self) -> None:
        if self.controller.mode != "head":
            return
        self._calibration_started_controller = not self.controller.is_running
        self._calibration_was_paused = self.controller.is_paused
        if self._calibration_started_controller and not self.controller.start():
            self.window.show_error("标定失败", "无法启动摄像头")
            return
        self.controller.pause()
        self.window.set_running(self.controller.is_running)
        self.window.set_paused(True)
        self.window.calibration_ready = True

    def _on_calibration_complete(self, top: float, middle: float, bottom: float) -> None:
        try:
            saved = self.controller.save_head_calibration(top, middle, bottom)
        except ValueError as exc:
            self.window.show_error("标定失败", str(exc))
            return
        if not saved:
            self.window.show_error("标定失败", "无法保存标定参数")
        self._finish_calibration()

    def _finish_calibration(self) -> None:
        if self._calibration_started_controller:
            self.controller.stop()
            self.window.set_running(False)
        elif not self._calibration_was_paused:
            self.controller.resume()
        self.window.set_paused(self.controller.is_paused if self.controller.is_running else False)

    def _on_frame_processed(self, frame: object) -> None:
        if not self.controller.is_running or self.controller.mode != "head":
            return
        max_age = self.controller.config.filter.lost_face_timeout_ms / 1000
        valid = (
            self.controller.has_valid_head_pose(frame)
            and isfinite(frame.timestamp)
            and 0 <= time.perf_counter() - frame.timestamp <= max_age
        )
        self.window.head_pitch_updated.emit(
            frame.head_pitch if valid else float("nan"), frame.timestamp
        )
        self.window.update_detection(valid, "头部", float(valid))
        if not valid:
            self.window.update_position(None)
            self.window.update_calibration_value(None, None)
            return
        self.window.update_position(self.controller.head_preview_position(frame.head_pitch))
        self.window.update_calibration_value(
            self.controller.head_preview_position(frame.head_pitch), frame.head_pitch, frame.timestamp
        )

    def _on_state_updated(self, state: str, paused: bool) -> None:
        if not self.controller.is_running:
            return
        self.window.update_control_state(state)
        self.window.set_paused(paused)

    def _on_action(self, action: str) -> None:
        self.window.update_last_action("下一页" if action == "NEXT" else "上一页")

    def _on_error(self, component: str, message: str) -> None:
        self.controller.stop()
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
