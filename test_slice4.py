from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest

import server


class Slice4AdminTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.original_db_path = server.DB_PATH
        self.original_admin_password = os.environ.get("ADMIN_PASSWORD")
        server.DB_PATH = Path(self.temp_dir.name) / "slice4-test.sqlite3"
        os.environ["ADMIN_PASSWORD"] = "test-admin-password"
        server.init_db()

    def tearDown(self):
        server.DB_PATH = self.original_db_path
        if self.original_admin_password is None:
            os.environ.pop("ADMIN_PASSWORD", None)
        else:
            os.environ["ADMIN_PASSWORD"] = self.original_admin_password
        self.temp_dir.cleanup()

    def test_admin_password_is_required(self):
        self.assertFalse(server.is_admin_password_valid(""))
        self.assertFalse(server.is_admin_password_valid("wrong-password"))
        self.assertTrue(server.is_admin_password_valid("test-admin-password"))

    def test_save_question_sets_it_active_and_resets_votes(self):
        original = server.get_current_question_payload()
        server.record_vote(original["options"][0]["id"])
        server.record_message("保存题目前的弹幕")

        saved = server.save_admin_question(
            {
                "title": "新的当前题目",
                "options": ["选项 A", "选项 B", "选项 C"],
            }
        )

        self.assertEqual(saved["title"], "新的当前题目")
        self.assertEqual(saved["total_votes"], 0)
        self.assertEqual(server.list_messages(), [])
        self.assertEqual([option["label"] for option in saved["options"]], ["选项 A", "选项 B", "选项 C"])

        questions = server.get_admin_questions_payload()
        active_questions = [question for question in questions if question["status"] == "active"]
        self.assertEqual(len(active_questions), 1)
        self.assertEqual(active_questions[0]["title"], "新的当前题目")

    def test_activate_question_keeps_only_one_active_and_resets_votes(self):
        first = server.save_admin_question(
            {
                "title": "第一题",
                "options": ["A", "B"],
            }
        )
        second = server.save_admin_question(
            {
                "title": "第二题",
                "options": ["C", "D"],
            }
        )

        server.activate_admin_question(first["id"])
        current = server.get_current_question_payload()
        server.record_vote(current["options"][0]["id"])
        server.record_message("切题前的弹幕")
        self.assertEqual(server.get_current_question_payload()["total_votes"], 1)
        self.assertEqual(len(server.list_messages()), 1)

        activated = server.activate_admin_question(second["id"])
        questions = server.get_admin_questions_payload()

        self.assertEqual(activated["id"], second["id"])
        self.assertEqual(activated["total_votes"], 0)
        self.assertEqual(server.list_messages(), [])
        self.assertEqual(len([question for question in questions if question["status"] == "active"]), 1)

    def test_clear_current_votes(self):
        current = server.get_current_question_payload()
        server.record_vote(current["options"][0]["id"])
        server.record_vote(current["options"][1]["id"])
        server.record_message("清票前的弹幕")

        cleared = server.clear_current_votes()

        self.assertEqual(cleared["total_votes"], 0)
        self.assertEqual(server.list_messages(), [])
        self.assertTrue(all(option["votes"] == 0 for option in cleared["options"]))

    def test_question_requires_two_to_six_options(self):
        with self.assertRaisesRegex(ValueError, "选项数量必须是 2-6 个"):
            server.save_admin_question({"title": "无效题目", "options": ["只有一个"]})


if __name__ == "__main__":
    unittest.main()
