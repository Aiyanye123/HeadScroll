import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from control.page_turn_fsm import PageAction, PageTurnFSM


class PageTurnFSMTest(unittest.TestCase):
    def setUp(self):
        self.fsm = PageTurnFSM(
            arm_duration_ms=150,
            min_swipe_distance=0.18,
            max_vertical_drift=0.10,
            max_swipe_duration_ms=700,
            cooldown_ms=600,
            fist_hold_ms=700,
            arm_stability_radius=0.04,
            min_swipe_duration_ms=120,
            min_swipe_speed=0.35,
            direction_consistency=0.75,
        )

    def test_open_palm_swipe_left_turns_to_next_page_once(self):
        self.assertEqual(self.fsm.update("Open_Palm", 0.75, 0.5, 0.00), PageAction.NONE)
        self.assertEqual(self.fsm.update("Open_Palm", 0.74, 0.5, 0.16), PageAction.NONE)
        self.assertEqual(self.fsm.update("Open_Palm", 0.50, 0.5, 0.36), PageAction.NEXT)
        self.assertEqual(self.fsm.update("Open_Palm", 0.30, 0.5, 0.45), PageAction.NONE)

    def test_open_palm_swipe_right_turns_to_previous_page(self):
        self.fsm.update("Open_Palm", 0.25, 0.5, 0.00)
        self.fsm.update("Open_Palm", 0.26, 0.5, 0.16)
        self.assertEqual(self.fsm.update("Open_Palm", 0.50, 0.5, 0.36), PageAction.PREVIOUS)

    def test_vertical_motion_does_not_turn_page(self):
        self.fsm.update("Open_Palm", 0.75, 0.30, 0.00)
        self.fsm.update("Open_Palm", 0.74, 0.30, 0.16)
        self.assertEqual(self.fsm.update("Open_Palm", 0.50, 0.50, 0.36), PageAction.NONE)

    def test_hand_must_reset_after_cooldown(self):
        self.fsm.update("Open_Palm", 0.75, 0.5, 0.00)
        self.fsm.update("Open_Palm", 0.74, 0.5, 0.16)
        self.assertEqual(self.fsm.update("Open_Palm", 0.50, 0.5, 0.36), PageAction.NEXT)
        self.assertEqual(self.fsm.update("Open_Palm", 0.75, 0.5, 1.10), PageAction.NONE)
        self.fsm.update("None", None, None, 1.20)
        self.fsm.update("Open_Palm", 0.75, 0.5, 1.30)
        self.fsm.update("Open_Palm", 0.74, 0.5, 1.46)
        self.assertEqual(self.fsm.update("Open_Palm", 0.50, 0.5, 1.66), PageAction.NEXT)

    def test_holding_fist_toggles_pause_once_and_can_resume_after_release(self):
        self.fsm.update("Closed_Fist", 0.5, 0.5, 0.00)
        self.fsm.update("Closed_Fist", 0.5, 0.5, 0.71)
        self.assertTrue(self.fsm.is_paused)
        self.fsm.update("Closed_Fist", 0.5, 0.5, 1.50)
        self.assertTrue(self.fsm.is_paused)
        self.fsm.update("None", None, None, 1.60)
        self.fsm.update("Closed_Fist", 0.5, 0.5, 1.70)
        self.fsm.update("Closed_Fist", 0.5, 0.5, 2.41)
        self.assertFalse(self.fsm.is_paused)

    def test_unstable_open_palm_restarts_arming(self):
        self.fsm.update("Open_Palm", 0.75, 0.5, 0.00)
        self.fsm.update("Open_Palm", 0.68, 0.5, 0.16)
        self.assertEqual(self.fsm.update("Open_Palm", 0.50, 0.5, 0.30), PageAction.NONE)

    def test_direction_reversal_is_rejected(self):
        self.fsm.update("Open_Palm", 0.75, 0.5, 0.00)
        self.fsm.update("Open_Palm", 0.75, 0.5, 0.16)
        self.fsm.update("Open_Palm", 0.59, 0.5, 0.26)
        self.fsm.update("Open_Palm", 0.73, 0.5, 0.36)
        self.assertEqual(self.fsm.update("Open_Palm", 0.50, 0.5, 0.46), PageAction.NONE)

    def test_switching_hands_cancels_tracking(self):
        self.fsm.update("Open_Palm", 0.75, 0.5, 0.00, "Right")
        self.fsm.update("Open_Palm", 0.75, 0.5, 0.16, "Right")
        self.assertEqual(
            self.fsm.update("Open_Palm", 0.50, 0.5, 0.36, "Left"),
            PageAction.NONE,
        )

    def test_implausibly_fast_jump_is_rejected(self):
        self.fsm.update("Open_Palm", 0.75, 0.5, 0.00)
        self.fsm.update("Open_Palm", 0.75, 0.5, 0.16)
        self.assertEqual(self.fsm.update("Open_Palm", 0.50, 0.5, 0.20), PageAction.NONE)


if __name__ == "__main__":
    unittest.main()
