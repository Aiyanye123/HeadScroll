import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tracking.speech_recognizer import CommandParser, PartialCommandGate


class CommandParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = CommandParser(
            ["左", "向左", "上一页"],
            ["右", "向右", "下一页"],
            ["暂停"],
            ["继续"],
            ["翻页"],
            False,
        )

    def test_normalizes_vosk_character_spacing(self):
        self.assertEqual(self.parser.parse("向 左").action, "PREVIOUS")

    def test_requires_exact_command(self):
        self.assertIsNone(self.parser.parse("请向左翻页"))

    def test_optional_wake_word_is_removed(self):
        self.assertEqual(self.parser.parse("翻页 下一页").action, "NEXT")

    def test_required_wake_word_rejects_bare_command(self):
        self.parser.require_wake_word = True
        self.assertIsNone(self.parser.parse("下一页"))
        self.assertEqual(self.parser.parse("翻页下一页").action, "NEXT")


class PartialCommandGateTests(unittest.TestCase):
    def test_balanced_mode_triggers_once_after_two_matching_partials(self):
        parser = CommandParser(["左"], ["右"], ["暂停"], ["继续"], [], False)
        gate = PartialCommandGate(2)
        command = parser.parse("左")
        self.assertIsNone(gate.update(command))
        self.assertEqual(gate.update(command).action, "PREVIOUS")
        self.assertIsNone(gate.update(command))
        gate.reset()
        self.assertIsNone(gate.update(command))

    def test_pause_waits_for_final_result(self):
        parser = CommandParser(["左"], ["右"], ["暂停"], ["继续"], [], False)
        gate = PartialCommandGate(1)
        self.assertIsNone(gate.update(parser.parse("暂停")))


if __name__ == "__main__":
    unittest.main()
