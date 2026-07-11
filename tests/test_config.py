import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils.config import Config


class ConfigTest(unittest.TestCase):
    def test_gesture_settings_round_trip_through_user_config(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Config(directory)
            config.gesture.min_swipe_distance = 0.22
            self.assertTrue(config.save())

            loaded = Config(directory)
            self.assertTrue(loaded.load())
            self.assertEqual(loaded.gesture.min_swipe_distance, 0.22)

    def test_invalid_gesture_settings_are_not_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Config(directory)
            config.gesture.direction_consistency = 1.5
            self.assertFalse(config.save())
            self.assertFalse((Path(directory) / "config" / "config.json").exists())

    def test_invalid_user_config_falls_back_to_valid_default(self):
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory) / "config"
            config_dir.mkdir()
            (config_dir / "config.json").write_text(
                json.dumps({"gesture": {"min_swipe_distance": -1}}),
                encoding="utf-8",
            )
            (config_dir / "default_config.json").write_text(
                json.dumps({"gesture": {"min_swipe_distance": 0.2}}),
                encoding="utf-8",
            )

            config = Config(directory)
            self.assertTrue(config.load())
            self.assertEqual(config.gesture.min_swipe_distance, 0.2)

    def test_migrates_legacy_head_mode_and_ignores_removed_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory) / "config"
            config_dir.mkdir()
            (config_dir / "config.json").write_text(
                json.dumps({
                    "calibration": {
                        "mode": "head",
                        "method": "linear",
                        "r_top": -0.2,
                        "r_mid": 0.0,
                        "r_bottom": 0.2,
                        "head_pitch_center": 0.1,
                        "timestamp": "2026-01-01T00:00:00",
                    }
                }),
                encoding="utf-8",
            )
            config = Config(directory)
            self.assertTrue(config.load())
            self.assertEqual(config.mode, "head")
            self.assertEqual(config.calibration.r_top, -0.2)


if __name__ == "__main__":
    unittest.main()
