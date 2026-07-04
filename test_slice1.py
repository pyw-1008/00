from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import server


class Slice1VotingTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.original_db_path = server.DB_PATH
        server.DB_PATH = Path(self.temp_dir.name) / "slice1-test.sqlite3"
        server.init_db()

    def tearDown(self):
        server.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_default_question_exists(self):
        question = server.get_current_question_payload()

        self.assertEqual(question["title"], server.DEFAULT_QUESTION_TITLE)
        self.assertGreaterEqual(len(question["options"]), 2)
        self.assertLessEqual(len(question["options"]), 6)
        self.assertEqual(question["total_votes"], 0)

    def test_vote_can_be_recorded_and_repeated(self):
        question = server.get_current_question_payload()
        first_option = question["options"][0]

        server.record_vote(first_option["id"])
        server.record_vote(first_option["id"])
        updated = server.get_current_question_payload()

        updated_first = updated["options"][0]
        self.assertEqual(updated["total_votes"], 2)
        self.assertEqual(updated_first["votes"], 2)
        self.assertEqual(updated_first["percentage"], 100)

    def test_percentage_updates_across_options(self):
        question = server.get_current_question_payload()
        first_option = question["options"][0]
        second_option = question["options"][1]

        server.record_vote(first_option["id"])
        server.record_vote(first_option["id"])
        server.record_vote(second_option["id"])
        updated = server.get_current_question_payload()

        self.assertEqual(updated["total_votes"], 3)
        self.assertEqual(updated["options"][0]["votes"], 2)
        self.assertEqual(updated["options"][0]["percentage"], 66.7)
        self.assertEqual(updated["options"][1]["votes"], 1)
        self.assertEqual(updated["options"][1]["percentage"], 33.3)


if __name__ == "__main__":
    unittest.main()
