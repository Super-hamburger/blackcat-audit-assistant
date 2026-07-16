import unittest
import wave
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLineEdit

from ui.main_window import MainWindow, ScanInputController


class FakeSoundEngine:
    def __init__(self):
        self.paths = []

    def play(self, path):
        self.paths.append(path)


class ScanFeedbackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_scan_error_sound_is_valid_mono_wav(self):
        path = Path("assets/sounds/scan_error.wav")

        with wave.open(str(path), "rb") as audio:
            self.assertEqual(audio.getnchannels(), 1)
            self.assertEqual(audio.getsampwidth(), 2)
            self.assertGreater(audio.getframerate(), 0)
            self.assertGreater(audio.getnframes(), 0)

    def test_scan_error_sound_bypasses_general_sound_setting(self):
        window = MainWindow.__new__(MainWindow)
        window.sound_engine = FakeSoundEngine()
        window.sound_path = lambda name: f"sounds/{name}"

        MainWindow.play_scan_error_sound(window)

        self.assertEqual(window.sound_engine.paths, ["sounds/scan_error.wav"])

    def test_scan_input_prefers_lowercase_latin_input(self):
        input_widget = QLineEdit()
        ScanInputController(input_widget, lambda: None)
        hints = input_widget.inputMethodHints()

        self.assertTrue(hints & Qt.ImhLatinOnly)
        self.assertTrue(hints & Qt.ImhPreferLowercase)


if __name__ == "__main__":
    unittest.main()

