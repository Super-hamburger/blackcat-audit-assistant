import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit

from ui.main_window import ScanInputController


class ScanInputCompatibilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.input_widget = QLineEdit()
        self.input_widget.show()
        self.input_widget.setFocus()
        self.application.processEvents()
        self.submissions = []
        self.controller = ScanInputController(
            self.input_widget,
            lambda: self.submissions.append(self.input_widget.text()),
        )

    def tearDown(self):
        self.input_widget.close()

    def test_tab_submits_input_without_moving_focus(self):
        self.input_widget.setFocus()
        QTest.keyClicks(self.input_widget, "ORDER-100")
        QTest.keyClick(self.input_widget, Qt.Key_Tab)

        self.assertEqual(self.submissions, ["ORDER-100"])
        self.assertTrue(self.input_widget.hasFocus())

    def test_fast_input_without_terminator_submits_after_idle_delay(self):
        QTest.keyClicks(self.input_widget, "ORDER-100")
        QTest.qWait(200)

        self.assertEqual(self.submissions, ["ORDER-100"])

    def test_slow_input_waits_for_enter(self):
        QTest.keyClick(self.input_widget, "O")
        QTest.qWait(1100)
        QTest.keyClicks(self.input_widget, "RDER-100")
        QTest.qWait(200)

        self.assertEqual(self.submissions, [])

        QTest.keyClick(self.input_widget, Qt.Key_Return)
        self.assertEqual(self.submissions, ["ORDER-100"])

    def test_return_submission_cancels_pending_automatic_submission(self):
        QTest.keyClicks(self.input_widget, "ORDER-100")
        QTest.keyClick(self.input_widget, Qt.Key_Return)
        QTest.qWait(200)

        self.assertEqual(self.submissions, ["ORDER-100"])


if __name__ == "__main__":
    unittest.main()
