import unittest

from myUtils.douyin_benchmark import parse_count


class DouyinBenchmarkCountTests(unittest.TestCase):
    def test_profile_counts_match_benchmark_headers(self):
        text = "关注 123\n粉丝 4.5万\n获赞 67.8万\n作品 91"

        self.assertEqual(parse_count(text, ["关注"]), "关注 123")
        self.assertEqual(parse_count(text, ["粉丝"]), "粉丝 4.5万")
        self.assertEqual(parse_count(text, ["获赞", "喜欢"]), "获赞 67.8万")
        self.assertEqual(parse_count(text, ["作品"]), "作品 91")


if __name__ == "__main__":
    unittest.main()
