import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ui.compact_status import CompactStatusWindow
from ui.floating_panel import FloatingPanel


class CompactStatusWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_status_values_are_updated(self):
        window = CompactStatusWindow()

        window.set_mode("head")
        window.update_detection(True, "头部", 0.37)
        window.update_control_state("PAUSED")
        window.update_last_action("下一页")
        window.update_fps(30.24)
        window.update_position(0.25)

        self.assertEqual(window.mode_status.text(), "头部滚动")
        self.assertEqual(window.detection_status.text(), "头部 37%")
        self.assertEqual(window.control_status.text(), "PAUSED")
        self.assertEqual(window.action_status.text(), "下一页")
        self.assertEqual(window.fps_label.text(), "30.2")
        self.assertEqual(window.position_bar.value(), 25)

    def test_pin_button_controls_always_on_top_flag(self):
        window = CompactStatusWindow(always_on_top=False)
        self.assertFalse(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)

        window.pin_btn.click()

        self.assertTrue(window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)

    def test_closing_full_panel_requests_compact_window(self):
        panel = FloatingPanel()
        requested = []
        panel.compact_requested.connect(lambda: requested.append(True))
        panel.show()

        panel.close()

        self.assertEqual(requested, [True])
        self.assertFalse(panel.isVisible())

    def test_minimizing_full_panel_requests_compact_window(self):
        panel = FloatingPanel()
        requested = []
        panel.compact_requested.connect(lambda: requested.append(True))
        panel.show()

        self.assertTrue(
            panel.windowFlags() & Qt.WindowType.WindowMinimizeButtonHint
        )
        panel.showMinimized()
        self.app.processEvents()
        self.app.processEvents()

        self.assertEqual(requested, [True])
        self.assertFalse(panel.isVisible())


if __name__ == "__main__":
    unittest.main()
