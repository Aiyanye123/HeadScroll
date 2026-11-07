"""Temporary calibration lifecycle without UI or real devices."""

import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from main import InteractionController
from tracking.face_tracker import HEAD_POSE_MATRIX_ALGORITHM
from utils.config import Config


class HeadCalibrationSessionTests(unittest.TestCase):
    def make_controller(self, mode, running, paused):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        config = Config(directory.name)
        config.config.mode = mode
        with patch("main.Config", return_value=config):
            controller = InteractionController()
        controller.camera = Mock()
        controller.camera.start.return_value = True
        controller.injector = Mock(use_smooth_scroll=True)
        controller.injector.init.return_value = True
        tracker = Mock(head_pose_algorithm=HEAD_POSE_MATRIX_ALGORITHM)
        starts = []

        def make_thread(**kwargs):
            thread = Mock()
            thread.is_alive.return_value = False
            thread.start.side_effect = lambda: starts.append((controller.mode, controller.is_paused))
            return thread

        for target, options in (
            ("main.Thread", {"side_effect": make_thread}),
            ("main.FaceTracker", {"return_value": tracker}),
            ("main.SpeechRecognizer", {}),
        ):
            replacement = patch(target, **options)
            replacement.start()
            self.addCleanup(replacement.stop)
        self.addCleanup(controller.shutdown)
        if running:
            self.assertTrue(controller.start(paused=paused))
        elif paused:
            controller.pause()
        starts.clear()
        return controller, config, starts

    def test_collection_is_paused_before_threads_start_and_restores_prior_state(self):
        for mode in ("voice", "head"):
            for running, paused in ((False, False), (True, False), (True, True)):
                with self.subTest(mode=mode, running=running, paused=paused):
                    controller, config, starts = self.make_controller(mode, running, paused)
                    previous_pause = controller.is_paused
                    config.voice.cooldown_ms = 777
                    with controller.head_calibration_session() as started:
                        self.assertTrue(started)
                        self.assertEqual(controller.mode, "head")
                        self.assertTrue(controller.is_running)
                        self.assertTrue(controller.is_paused)
                        self.assertEqual(starts, [("head", True)] * 3)
                        controller.toggle_pause()
                        controller.resume()
                        self.assertTrue(controller.is_paused)
                        controller._head_output_tick(1 / 90, time.perf_counter())
                        controller.injector.scroll.assert_not_called()
                        controller.injector.press_key.assert_not_called()
                    self.assertEqual(controller.mode, mode)
                    self.assertEqual(controller.is_running, running)
                    self.assertEqual(controller.is_paused, previous_pause)
                    self.assertEqual(config.voice.cooldown_ms, 777)
                    self.assertFalse((config.config_dir / "config.json").exists())

    def test_cancel_or_exception_restores_paused_voice_without_saving(self):
        controller, config, _ = self.make_controller("voice", True, True)
        with self.assertRaisesRegex(RuntimeError, "cancel"):
            with controller.head_calibration_session() as started:
                self.assertTrue(started)
                raise RuntimeError("cancel")
        self.assertEqual(controller.mode, "voice")
        self.assertTrue(controller.is_running)
        self.assertTrue(controller.is_paused)
        self.assertFalse((config.config_dir / "config.json").exists())

    def test_camera_start_failure_restores_original_voice(self):
        controller, _, _ = self.make_controller("voice", True, True)
        controller.camera.start.return_value = False
        with controller.head_calibration_session() as started:
            self.assertFalse(started)
        self.assertEqual(controller.mode, "voice")
        self.assertTrue(controller.is_running)
        self.assertTrue(controller.is_paused)
        controller.injector.press_key.assert_not_called()

    def test_emergency_stop_during_collection_does_not_restart_original_mode(self):
        controller, _, _ = self.make_controller("voice", True, True)
        with controller.head_calibration_session() as started:
            self.assertTrue(started)
            controller.stop()
        self.assertEqual(controller.mode, "voice")
        self.assertFalse(controller.is_running)
        controller.injector.press_key.assert_not_called()


if __name__ == "__main__":
    unittest.main()
