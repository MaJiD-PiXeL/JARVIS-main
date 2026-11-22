import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("JARVIS_CONFIG_DIR", str(Path(__file__).resolve().parents[1] / ".test-config"))

from core import config
from core.ai.local_tasks import LocalTaskPlanner, verified_step
from core.assistant import Assistant
from core.tasks import EXAMPLES, local_plan, make_step
from core.command_router import CommandRouter
from core.commands_loader import load_commands


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.router = CommandRouter(load_commands(), 85)

    def test_every_displayed_example_has_an_offline_plan(self):
        for example in EXAMPLES:
            with self.subTest(example=example):
                self.assertTrue(local_plan(example, self.router))

    def test_quoted_separator_and_note_text_survive_a_multistep_request(self):
        with tempfile.TemporaryDirectory() as folder, patch("core.tasks.known_folder", return_value=Path(folder)):
            text = 'در اسناد یادداشت «Plan A» با متن «خرید و بعد تماس؛ ساعت ۱۰» بساز و بعد روی دسکتاپ پوشه «Week 1» بساز'
            steps = local_plan(text, self.router)
            self.assertEqual([step.name for step in steps], ["write_note", "create_folder"])
            for step in steps:
                step.action()
            path = Path(folder, "Plan A.txt")
            self.assertEqual(path.read_text(encoding="utf-8"), "خرید و بعد تماس؛ ساعت ۱۰\n")
            self.assertTrue(Path(folder, "Week 1").is_dir())
            with self.assertRaises(FileExistsError):
                steps[0].action()
            self.assertEqual(path.read_text(encoding="utf-8"), "خرید و بعد تماس؛ ساعت ۱۰\n")

    def test_unsupported_step_does_not_run_the_recognized_prefix(self):
        self.assertEqual(local_plan("ماشین حساب رو باز کن و بعد فایل قدیمی را حذف کن", self.router), [])
        with self.assertRaises(ValueError):
            local_plan("ماشین حساب رو باز کن و بعد سطل زباله را خالی کن", self.router)

    def test_model_arguments_cannot_escape_supported_operations(self):
        for args in (("open_app", "powershell"), ("create_folder", "..\\other", "desktop"),
                     ("write_note", "NUL.txt", "desktop", "test"), ("set_volume", "101")):
            with self.subTest(args=args), self.assertRaises(ValueError):
                make_step(*args)

    def test_execution_stops_at_first_error(self):
        first = Mock(__name__="first", side_effect=OSError("test error"))
        later = Mock(__name__="later")
        with patch.object(config, "GEMINI_API_KEY", ""), patch("core.assistant.speak") as output:
            assistant = Assistant(None, {("کار اول",): first, ("کار دوم",): later})
            assistant.process_text("کار اول و بعد کار دوم", activated=True)
        first.assert_called_once()
        later.assert_not_called()
        self.assertTrue(any("مرحلهٔ بعدی اجرا نشد" in call.args[0] for call in output.call_args_list))

    def test_questions_and_negations_do_not_reach_the_model(self):
        with patch.object(config, "GEMINI_API_KEY", ""), patch("core.assistant.speak"):
            assistant = Assistant(None, load_commands())
            assistant.planner.plan = Mock()
            assistant.process_text("چطور ماشین حساب رو باز کنم؟", activated=True)
            assistant.process_text("ماشین حساب رو باز نکن", activated=True)
        assistant.planner.plan.assert_not_called()

    def test_model_plan_requires_matching_actions_and_arguments(self):
        self.assertIsNone(verified_step("روی دسکتاپ یک پوشه بساز", {
            "kind": "open_folder", "value": "desktop",
        }))
        self.assertIsNone(verified_step("یه پوشهٔ تست در اسناد ایجاد کن", {
            "kind": "create_folder", "value": "تست", "folder": "desktop",
        }))
        with patch("core.ai.local_tasks.request_json") as request:
            steps = LocalTaskPlanner("test").plan("نوت پد رو باز کن و یکی از فایل‌ها را حذف کن")
        self.assertEqual(steps, [])
        request.assert_not_called()

    def test_unquoted_persian_filename_and_app_variants(self):
        steps = local_plan("روی دسکتاپ یک پوشه به اسم برنامه هفتگی درست کن بعد نوت پد رو بیار بالا", self.router)
        self.assertEqual([step.name for step in steps], ["create_folder", "open_app"])

    def test_colloquial_commands_from_voice_or_text(self):
        cases = [
            ("میشه نوت پد و ماشین حساب رو برام باز کنی؟", ["open_app", "open_app"]),
            ("باز کن نوتپد و بعد ساعت الان چنده", ["open_app", "say_time"]),
            ("صدا رو بذار روی سی و پنج درصد", ["set_volume"]),
            ("در مورد تقویم شمسی سرچ کن", ["web_search"]),
        ]
        for text, names in cases:
            with self.subTest(text=text):
                self.assertEqual([step.name for step in local_plan(text, self.router)], names)
        with patch("core.actions.volume.set_volume") as set_volume:
            local_plan("صدا رو بذار روی سی و پنج درصد", self.router)[0].action()
        set_volume.assert_called_once_with(.35)

    def test_fuzzy_match_does_not_guess_between_similar_commands(self):
        router = CommandRouter({("صدا را کم کن",): Mock(), ("صدا را قطع کن",): Mock()}, 75)
        self.assertEqual(router.detect("صدا را قم کن"), [])
