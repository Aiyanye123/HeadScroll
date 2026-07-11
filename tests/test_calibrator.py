import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from calibration.calibrator import Calibrator


class CalibratorTest(unittest.TestCase):
    def test_maps_ascending_head_pitch_anchors(self):
        calibrator = Calibrator()
        calibrator.load_calibration(-0.2, 0.0, 0.2)
        self.assertEqual(calibrator.map(-0.2), 0.0)
        self.assertEqual(calibrator.map(0.0), 0.5)
        self.assertEqual(calibrator.map(0.2), 1.0)

    def test_maps_descending_head_pitch_anchors(self):
        calibrator = Calibrator()
        calibrator.load_calibration(0.2, 0.0, -0.2)
        self.assertEqual(calibrator.map(0.2), 0.0)
        self.assertEqual(calibrator.map(0.0), 0.5)
        self.assertEqual(calibrator.map(-0.2), 1.0)

    def test_rejects_middle_anchor_outside_range(self):
        calibrator = Calibrator()
        with self.assertRaises(ValueError):
            calibrator.load_calibration(-0.2, 0.3, 0.2)


if __name__ == "__main__":
    unittest.main()
