from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import server


class VoteStatsTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.original_db_path = server.DB_PATH
        server.DB_PATH = Path(self.temp_dir.name) / "vote-stats-test.sqlite3"
        server.init_db()

    def tearDown(self):
        server.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def option_ids(self):
        question = server.get_current_question_payload()
        return [option["id"] for option in question["options"]]

    def assert_stats(self, expected_votes, expected_percentages):
        question = server.get_current_question_payload()

        self.assertEqual(question["total_votes"], sum(expected_votes))
        for index, option in enumerate(question["options"]):
            self.assertEqual(option["votes"], expected_votes[index])
            self.assertEqual(option["percentage"], expected_percentages[index])

    def test_no_votes(self):
        self.assert_stats(
            expected_votes=[0, 0, 0, 0],
            expected_percentages=[0, 0, 0, 0],
        )

    def test_only_one_option_has_votes(self):
        first_option_id = self.option_ids()[0]

        server.record_vote(first_option_id)
        server.record_vote(first_option_id)
        server.record_vote(first_option_id)

        self.assert_stats(
            expected_votes=[3, 0, 0, 0],
            expected_percentages=[100.0, 0.0, 0.0, 0.0],
        )

    def test_multiple_options_have_votes(self):
        first_option_id, second_option_id, third_option_id, _ = self.option_ids()

        server.record_vote(first_option_id)
        server.record_vote(first_option_id)
        server.record_vote(second_option_id)
        server.record_vote(third_option_id)

        self.assert_stats(
            expected_votes=[2, 1, 1, 0],
            expected_percentages=[50.0, 25.0, 25.0, 0.0],
        )


if __name__ == "__main__":
    unittest.main()
