from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import server


class Slice3SensitiveWordTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.original_db_path = server.DB_PATH
        self.original_sensitive_words_path = server.SENSITIVE_WORDS_PATH
        temp_path = Path(self.temp_dir.name)
        server.DB_PATH = temp_path / "slice3-test.sqlite3"
        server.SENSITIVE_WORDS_PATH = temp_path / "sensitive_words.txt"
        server.SENSITIVE_WORDS_PATH.write_text("敏感词\n广告\n", encoding="utf-8")
        server.init_db()

    def tearDown(self):
        server.DB_PATH = self.original_db_path
        server.SENSITIVE_WORDS_PATH = self.original_sensitive_words_path
        self.temp_dir.cleanup()

    def test_sensitive_message_is_masked_before_listing(self):
        message = server.record_message("这里有敏感词")
        messages = server.list_messages()

        self.assertTrue(message["masked"])
        self.assertEqual(message["body"], "这里有***")
        self.assertEqual(messages[0]["body"], "这里有***")

    def test_normal_message_is_not_changed(self):
        message = server.record_message("你好")
        messages = server.list_messages()

        self.assertFalse(message["masked"])
        self.assertEqual(message["body"], "你好")
        self.assertEqual(messages[0]["body"], "你好")

    def test_multiple_sensitive_words_are_masked(self):
        message = server.record_message("敏感词和广告都不要原样上墙")

        self.assertTrue(message["masked"])
        self.assertEqual(message["body"], "***和**都不要原样上墙")


if __name__ == "__main__":
    unittest.main()
