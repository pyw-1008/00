from pathlib import Path
from tempfile import TemporaryDirectory
import csv
import io
import unittest

import server


class Slice6PersistenceAndExportTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.original_db_path = server.DB_PATH
        server.DB_PATH = Path(self.temp_dir.name) / "slice6-test.sqlite3"
        server.init_db()

    def tearDown(self):
        server.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_votes_and_messages_are_still_there_after_reinit(self):
        current = server.get_current_question_payload()
        server.record_vote(current["options"][0]["id"])
        server.record_message("重启后还在")

        server.init_db()

        after_reinit = server.get_current_question_payload()
        messages = server.list_messages()
        self.assertEqual(after_reinit["total_votes"], 1)
        self.assertEqual(after_reinit["options"][0]["votes"], 1)
        self.assertEqual([message["body"] for message in messages], ["重启后还在"])

    def test_export_csv_contains_vote_stats_and_messages(self):
        current = server.get_current_question_payload()
        first_option = current["options"][0]
        second_option = current["options"][1]
        server.record_vote(first_option["id"])
        server.record_vote(first_option["id"])
        server.record_vote(second_option["id"])
        server.record_message("你好")

        csv_text = server.build_export_csv().lstrip("\ufeff")
        rows = list(csv.DictReader(io.StringIO(csv_text)))

        vote_rows = {
            row["选项"]: row
            for row in rows
            if row["类型"] == "票数" and row["题目ID"] == str(current["id"])
        }
        self.assertEqual(vote_rows[first_option["label"]]["票数"], "2")
        self.assertEqual(vote_rows[first_option["label"]]["总票数"], "3")
        self.assertEqual(vote_rows[first_option["label"]]["百分比"], "66.7")
        self.assertEqual(vote_rows[second_option["label"]]["票数"], "1")
        self.assertEqual(vote_rows[second_option["label"]]["总票数"], "3")
        self.assertEqual(vote_rows[second_option["label"]]["百分比"], "33.3")

        message_rows = [row for row in rows if row["类型"] == "留言"]
        self.assertEqual(len(message_rows), 1)
        self.assertEqual(message_rows[0]["留言内容"], "你好")
        self.assertTrue(message_rows[0]["留言时间"])


if __name__ == "__main__":
    unittest.main()
