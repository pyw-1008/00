from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import server


class Slice2MessageTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.original_db_path = server.DB_PATH
        server.DB_PATH = Path(self.temp_dir.name) / "slice2-test.sqlite3"
        server.init_db()

    def tearDown(self):
        server.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_message_can_be_saved_and_listed(self):
        message = server.record_message("你好")
        messages = server.list_messages()

        self.assertEqual(message["body"], "你好")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["body"], "你好")

    def test_message_longer_than_50_chars_is_rejected(self):
        too_long = "好" * 51

        with self.assertRaisesRegex(ValueError, "留言最多 50 字"):
            server.record_message(too_long)

        self.assertEqual(server.list_messages(), [])

    def test_list_messages_only_returns_newer_messages(self):
        first = server.record_message("第一条")
        second = server.record_message("第二条")
        third = server.record_message("第三条")

        messages = server.list_messages(since_id=first["id"])

        self.assertEqual([message["id"] for message in messages], [second["id"], third["id"]])
        self.assertEqual([message["body"] for message in messages], ["第二条", "第三条"])


if __name__ == "__main__":
    unittest.main()
