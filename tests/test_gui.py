"""Exercise the real Qt/worker bridge with no microphone or network."""
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("JARVIS_CONFIG_DIR", str(Path(__file__).resolve().parent.parent / ".test-config"))

from PySide6.QtTest import QTest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton
from core import tts
from core.gui import create_application, JarvisWindow


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_application()

    def wait_for(self, condition, timeout=8):
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            QTest.qWait(20)
            time.sleep(.01)
        self.assertTrue(condition())

    def test_typing_time_displays_real_response_and_closes_worker(self):
        window = JarvisWindow()
        tts.set_muted(True)
        try:
            window.show()
            self.wait_for(lambda: window.ready)
            self.assertFalse(window.service.listening)
            window.entry.setText("ساعت چنده")
            QTest.keyClick(window.entry, Qt.Key.Key_Return)
            def has_time_response():
                return any("الان ساعت" in item.text() for bubble in window.messages for item in bubble.findChildren(QLabel))
            self.wait_for(has_time_response)
            self.wait_for(lambda: window.state == "paused")
            self.assertFalse(window.service.stt.active)
        finally:
            window.close()
            self.wait_for(lambda: not window.service.is_alive())
            QTest.qWait(120)

    def test_missing_voice_model_leaves_typed_commands_available(self):
        with patch("core.stt.SpeachToText", side_effect=FileNotFoundError("مدل پیدا نشد")), patch.object(tts, "_muted", True):
            window = JarvisWindow()
            try:
                self.wait_for(lambda: window.ready and window.state == "paused")
                self.assertFalse(window.mic_button.isEnabled())
                self.assertFalse(window.wake_button.isEnabled())
                self.assertFalse(window.settings_button.isEnabled())
                self.assertTrue(window.entry.isEnabled())
                window.submit_text("ساعت چنده")
                self.wait_for(lambda: any("الان ساعت" in item.text()
                                          for bubble in window.messages for item in bubble.findChildren(QLabel)))
            finally:
                window.close()
                self.wait_for(lambda: not window.service.is_alive())
                QTest.qWait(120)

    def test_command_search_finds_normalized_alias(self):
        window = JarvisWindow(start_service=False)
        window.on_event("ready", {"voice_available": True, "command_groups": (
            ("دفترچه یادداشت را باز کن", "نوت پد را باز کن"), ("ساعت چنده",),
        )})
        window.set_state("paused")
        results = []

        def search():
            dialog = window.findChild(QDialog)
            try:
                field = dialog.findChild(QLineEdit)
                field.setText("نوت‌پد")
                results.extend(button.text() for button in dialog.findChildren(QPushButton, "quick")
                               if button.isVisible())
                field.setText("عبارت ناموجود")
                results.extend(button.text() for button in dialog.findChildren(QPushButton, "quick")
                               if button.isVisible())
            finally:
                dialog.reject()

        try:
            QTimer.singleShot(0, search)
            window.show_commands()
            self.assertEqual(results, ["نوت پد را باز کن"])
        finally:
            window.close()

    def test_uncertain_transcript_can_be_edited_without_sending(self):
        window = JarvisWindow(start_service=False)
        try:
            window.show()
            window.on_event("ready", {"voice_available": True, "command_groups": ()})
            window.set_state("listening")
            with patch.object(window.service, "submit") as submit:
                window.on_event("uncertain", {"text": "ساعت چنده ...", "confidence": .4})
                self.assertTrue(window.edit_heard_button.isVisible())
                window.edit_heard_button.click()
                self.assertEqual(window.entry.text(), "ساعت چنده ...")
                submit.assert_not_called()
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
