import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ui.global_hotkeys import parse_hotkey


class GlobalHotkeyTest(unittest.TestCase):
    def test_parses_modifier_chord(self):
        self.assertEqual(parse_hotkey("Ctrl+Shift+Space"), (0x0002 | 0x0004, 0x20))

    def test_parses_escape_without_modifiers(self):
        self.assertEqual(parse_hotkey("Escape"), (0, 0x1B))

    def test_rejects_unsupported_key(self):
        with self.assertRaises(ValueError):
            parse_hotkey("Ctrl+Media Play")


if __name__ == "__main__":
    unittest.main()
