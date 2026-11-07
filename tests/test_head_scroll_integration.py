"""Hardware-free contracts for the integrated voice and head control paths."""

import ctypes
from copy import deepcopy
import math
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from calibration import Calibrator
from control.intent_fsm import FSMState
from control.scroll_controller import ScrollController
from injection.windows import INPUT, KEYEVENTF_KEYUP, POINT, SEND_TIMEOUT_MS, WindowsInjector
from main import InteractionController
from tracking.face_tracker import (
    FaceLandmarks, HEAD_POSE_LEGACY_ALGORITHM, HEAD_POSE_MATRIX_ALGORITHM,
)
from tracking.feature_extractor import BlinkState, FeatureExtractor, FeaturePacket
from tracking.speech_recognizer import VoiceCommand
from utils.config import Config


class HeadPoseContracts(unittest.TestCase):
    def test_scaled_transform_yields_pitch_without_eye_measurements(self):
        pitch = 0.24
        rotation = np.array([
            [1, 0, 0],
            [0, math.cos(pitch), -math.sin(pitch)],
            [0, math.sin(pitch), math.cos(pitch)],
        ])
        transform = np.eye(4)
        transform[:3, :3] = rotation @ np.diag([2.0, 3.0, 4.0])
        landmarks = FaceLandmarks(
            np.empty((0, 3)), 640, 480, transform, HEAD_POSE_MATRIX_ALGORITHM
        )
        feature = FeatureExtractor().extract(landmarks, 1.0)
        self.assertTrue(feature.head_pose_valid)
        self.assertAlmostEqual(feature.head_pitch, pitch)

    def test_missing_or_invalid_matrix_never_becomes_neutral_pose(self):
        for transform in (None, np.eye(3), np.zeros((4, 4)), np.full((4, 4), np.nan)):
            with self.subTest(transform=transform):
                landmarks = FaceLandmarks(
                    np.zeros((468, 3)), 640, 480, transform, HEAD_POSE_MATRIX_ALGORITHM
                )
                feature = FeatureExtractor().extract(landmarks, 1.0)
                self.assertFalse(feature.head_pose_valid)
                self.assertTrue(math.isnan(feature.head_pitch))

    def test_head_reference_rejects_nonfinite_and_wrong_action_order(self):
        calibrator = Calibrator()
        for anchors in ((-0.2, 0.0, float("inf")), (float("nan"), 0.0, 0.2)):
            with self.assertRaises(ValueError):
                calibrator.load_calibration(*anchors)
        self.assertTrue(Calibrator.head_reference_error(0.2, 0.0, -0.2))
        self.assertEqual(Calibrator.head_reference_error(-0.2, 0.0, 0.2), "")


class ControllerContracts(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.config = Config(self.directory.name)
        self.config.config.mode = "head"
        with patch("main.Config", return_value=self.config):
            self.controller = InteractionController()
        self.controller.tracker = SimpleNamespace(head_pose_algorithm=HEAD_POSE_MATRIX_ALGORITHM)
        self.controller.injector = Mock(use_smooth_scroll=True)
        self.controller._running = True
        self.controller.head_fsm.reset(paused=False)
        self.controller.gaze_filter.ema_alpha = 0.0
        self.controller.calibrator.load_calibration(-0.2, 0.0, 0.2)
        self.controller._last_feature_timestamp = 100.0

    @staticmethod
    def feature(timestamp, *, valid=True):
        return FeaturePacket(
            timestamp, 0.5, float(valid), BlinkState.OPEN, 0.0,
            0.2 if valid else float("nan"), True, valid, HEAD_POSE_MATRIX_ALGORITHM,
        )

    def test_duplicate_and_stale_frames_do_not_advance_dwell(self):
        controller = self.controller
        controller._process_head_features(self.feature(100.01), 100.02)
        controller._process_head_features(self.feature(100.01), 100.2)
        controller._process_head_features(self.feature(99.0), 100.3)
        self.assertEqual(controller.head_fsm.state, FSMState.ARMED)
        controller._process_head_features(self.feature(100.3), 100.31)
        self.assertEqual(controller.head_fsm.state, FSMState.SCROLLING)

    def test_invalid_pose_pause_resume_and_expiry_clear_motion(self):
        controller = self.controller
        controller._process_head_features(self.feature(100.01), 100.02)
        controller._process_head_features(self.feature(100.2), 100.21)
        self.assertGreater(controller.scroll_controller.v_target, 0)
        controller._process_head_features(self.feature(100.22, valid=False), 100.23)
        self.assertEqual(controller.head_fsm.state, FSMState.IDLE)
        self.assertEqual(controller.scroll_controller.v_target, 0)
        controller.scroll_controller.set_target(1)
        controller.pause()
        controller.resume()
        self.assertEqual(controller.head_fsm.state, FSMState.IDLE)
        self.assertEqual(controller.scroll_controller.tick(0.1, True), 0)
        controller._last_feature_timestamp = 100.0
        controller.scroll_controller.set_target(1)
        controller._head_output_tick(1 / 90, 100.6)
        controller.injector.scroll.assert_not_called()
        self.assertEqual(controller.scroll_controller.v_target, 0)

    def test_calibration_is_bound_to_the_pose_algorithm_and_persisted(self):
        controller = self.controller
        self.assertTrue(controller.save_head_calibration(-0.2, 0.0, 0.2))
        loaded = Config(self.directory.name)
        self.assertTrue(loaded.load())
        self.assertEqual(loaded.calibration.reference_algorithm, HEAD_POSE_MATRIX_ALGORITHM)
        self.assertTrue(controller.calibrator.is_calibrated)
        controller.tracker.head_pose_algorithm = HEAD_POSE_LEGACY_ALGORITHM
        controller._sync_head_calibration()
        self.assertFalse(controller.calibrator.is_calibrated)
        self.assertEqual(controller.scroll_controller.v_target, 0)

    def test_rejected_settings_leave_the_running_mode_and_voice_config_intact(self):
        candidate = deepcopy(self.config.config)
        candidate.mode = "voice"
        candidate.voice.next_key = candidate.voice.previous_key
        self.assertFalse(self.config.apply_settings(candidate))
        self.assertEqual(self.config.mode, "head")
        self.assertEqual(self.config.voice.next_key, "Right")

    def test_output_ticks_are_independent_of_frame_arrivals(self):
        controller = self.controller
        clock = {"now": 0.0}
        arrivals = iter([0.002, 0.004, 0.012, 0.024])

        def next_frame(timeout):
            try:
                clock["now"] = next(arrivals)
            except StopIteration:
                controller._stop_event.set()
            return self.feature(clock["now"])

        controller._features = Mock()
        controller._features.get.side_effect = next_frame
        with patch("main.time.perf_counter", side_effect=lambda: clock["now"]), \
             patch.object(controller, "_sync_head_calibration"), \
             patch.object(controller, "_expire_head_features"), \
             patch.object(controller, "_process_head_features") as process, \
             patch.object(controller, "_head_output_tick") as output:
            controller._head_control_loop()
        self.assertEqual(process.call_count, 4)
        self.assertEqual(output.call_count, 2)
        self.assertEqual([call.args[0] for call in output.call_args_list], [1 / 90, 1 / 90])

    def test_voice_still_uses_page_keys_and_honors_pause_and_stop(self):
        controller = self.controller
        self.config.config.mode = "voice"
        with patch("main.time.monotonic", return_value=10.0):
            controller._on_voice_command(VoiceCommand("NEXT", "右"))
            controller._on_voice_command(VoiceCommand("PAUSE", "暂停"))
            controller._on_voice_command(VoiceCommand("NEXT", "右"))
            controller._on_voice_command(VoiceCommand("RESUME", "继续"))
        with patch("main.time.monotonic", return_value=11.0):
            controller._on_voice_command(VoiceCommand("PREVIOUS", "左"))
        self.assertEqual(
            [call.args[0] for call in controller.injector.press_key.call_args_list],
            ["Right", "Left"],
        )
        controller.stop()
        controller._on_voice_command(VoiceCommand("NEXT", "右"))
        self.assertEqual(controller.injector.press_key.call_count, 2)
        controller.injector.scroll.assert_not_called()

    def test_restart_waits_for_previous_workers(self):
        controller = self.controller
        controller._running = False
        controller._capture_thread = Mock()
        controller._capture_thread.is_alive.return_value = True
        self.assertFalse(controller.start())
        controller.injector.init.assert_not_called()


class WheelInjectionContracts(unittest.TestCase):
    def injector(self, target="cursor"):
        injector = WindowsInjector(target_mode=target, target_process="reader.exe")
        injector._initialized = True
        injector._user32 = Mock()
        injector._send_input = Mock(return_value=1)
        return injector

    def test_subnotch_and_whole_notch_outputs_share_windows_units(self):
        smooth = ScrollController(v_max=1, a_up=100)
        whole = ScrollController(v_max=1, a_up=100)
        smooth.set_target(1)
        whole.set_target(1)
        self.assertEqual(smooth.tick(0.1, True), 12)
        self.assertEqual(whole.tick(0.1), 0)
        self.assertEqual(whole.tick(0.9), 120)
        injector = self.injector()
        with patch.object(injector, "_send_wheel_by_mode", return_value=True) as send:
            self.assertTrue(injector.scroll(12))
        send.assert_called_once_with(-12)

    def test_missing_process_and_timed_out_window_do_not_fall_back(self):
        injector = self.injector("process")
        with patch.object(injector, "_find_window_by_process_name", return_value=None):
            self.assertFalse(injector.scroll(120))
        self.assertIn("reader.exe", injector.last_error)
        injector._send_input.assert_not_called()
        injector._user32.SendMessageTimeoutW.return_value = 0
        self.assertFalse(injector._send_wheel_to_window(1, -12, POINT(0, 0)))
        args = injector._user32.SendMessageTimeoutW.call_args.args
        self.assertEqual(args[5], SEND_TIMEOUT_MS)
        injector._send_input.assert_not_called()

    def test_voice_key_injection_keeps_keyboard_down_up_pair(self):
        injector = self.injector()
        injector._send_input.return_value = 2
        self.assertTrue(injector.press_key("Right"))
        count, inputs, input_size = injector._send_input.call_args.args
        self.assertEqual(count, 2)
        self.assertEqual(input_size, ctypes.sizeof(INPUT))
        self.assertEqual([inputs[index].ki.wVk for index in range(2)], [0x27, 0x27])
        self.assertEqual(inputs[1].ki.dwFlags, KEYEVENTF_KEYUP)


if __name__ == "__main__":
    unittest.main()
