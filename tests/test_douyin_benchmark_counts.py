import unittest

from myUtils.douyin_benchmark import build_profile_counts, parse_count


class DouyinBenchmarkCountTests(unittest.TestCase):
    def test_profile_counts_match_benchmark_headers(self):
        text = "关注 123\n粉丝 4.5万\n获赞 67.8万\n作品 91"

        self.assertEqual(parse_count(text, ["关注"]), "关注 123")
        self.assertEqual(parse_count(text, ["粉丝"]), "粉丝 4.5万")
        self.assertEqual(parse_count(text, ["获赞", "喜欢"]), "获赞 67.8万")
        self.assertEqual(parse_count(text, ["作品"]), "作品 91")

    def test_profile_stats_map_to_correct_semantics(self):
        counts = build_profile_counts(
            {"following": "18", "fans": "58.6万", "receivedLikes": "425.3万"},
            "",
        )

        self.assertEqual(counts["following_count"], "18")
        self.assertEqual(counts["followers_count"], "58.6万")
        self.assertEqual(counts["received_likes_count"], "425.3万")
        self.assertEqual(counts["likes_count"], "425.3万")


if __name__ == "__main__":
    unittest.main()
