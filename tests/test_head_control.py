import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from control.intent_fsm import FSMState, IntentFSM
from control.scroll_controller import ScrollController
from processing.filter import GazeFilter
from tracking.feature_extractor import BlinkState


class HeadControlTest(unittest.TestCase):
    def _armed_fsm(self, position: float):
        fsm = IntentFSM(th_on=0.45, th_off=0.35, dwell_on_ms=120)
        fsm.resume()
        fsm.update(position, BlinkState.OPEN, True, False, 1.00)
        return fsm, fsm.update(position, BlinkState.OPEN, True, False, 1.13)

    def test_head_up_scrolls_up(self):
        _, (state, target) = self._armed_fsm(0.0)
        self.assertEqual(state, FSMState.SCROLLING)
        self.assertLess(target, 0)

    def test_head_down_scrolls_down(self):
        _, (state, target) = self._armed_fsm(1.0)
        self.assertEqual(state, FSMState.SCROLLING)
        self.assertGreater(target, 0)

    def test_face_loss_stops_active_scroll(self):
        fsm, _ = self._armed_fsm(1.0)
        state, target = fsm.update(1.0, BlinkState.OPEN, False, True, 1.20)
        self.assertEqual(state, FSMState.IDLE)
        self.assertEqual(target, 0.0)

    def test_filter_marks_face_lost_after_timeout(self):
        filter_ = GazeFilter(confidence_min=0.4, lost_face_timeout_ms=500)
        filter_.update(0.8, 1.0, True, 1.0)
        filter_.update(0.8, 0.0, False, 1.51)
        self.assertTrue(filter_.is_face_lost)

    def test_scroll_controller_stops_without_residual_delta(self):
        controller = ScrollController(v_max=5.0, tick_hz=60)
        controller.set_target(1.0)
        controller.tick(0.5)
        controller.stop()
        self.assertEqual(controller.tick(1 / 60), 0)


if __name__ == "__main__":
    unittest.main()
