import unittest
from pathlib import Path
from unittest.mock import patch

import sau_backend


class IdeaRadarPipelineTests(unittest.TestCase):
    def test_prompt_uses_full_transcript_and_requires_opportunity_chain(self):
        prompt = sau_backend.build_transcript_radar_prompt(
            {
                "id": 1,
                "account_name": "示例账号",
                "title": "工具标题",
                "video_url": "https://example.com/video/1",
                "like_count": "1000",
            },
            "过去只有程序员能写自动化，现在普通运营也可以先完成一个流程。",
            "普通人的 AI 机会",
        )
        self.assertIn("过去只有程序员能写自动化", prompt)
        self.assertIn("具体交付物", prompt)
        self.assertIn("潜在付费者", prompt)
        self.assertIn("最小验证", prompt)

    def test_clean_transcript_removes_repeated_punctuation(self):
        cleaned = sau_backend.clean_transcript_text("第一句。。。。\n  第二句！！！")
        self.assertEqual("第一句。\n第二句！", cleaned)

    @patch.object(sau_backend, "update_idea_radar_transcript")
    @patch.object(sau_backend, "run_codex_structured")
    @patch.object(sau_backend, "transcribe_idea_radar_media")
    @patch.object(sau_backend, "download_douyin_video")
    @patch.object(sau_backend, "get_idea_radar_transcript")
    @patch.object(sau_backend, "load_idea_radar_video")
    def test_pipeline_transcribes_before_analysis(
        self,
        load_video,
        get_transcript,
        download_video,
        transcribe,
        run_codex,
        update_transcript,
    ):
        load_video.return_value = {
            "id": 7,
            "account_name": "对标账号",
            "title": "标题不是正文",
            "video_url": "https://example.com/video/7",
            "like_count": "2000",
        }
        get_transcript.return_value = None
        download_video.return_value = Path("source.mp4")
        transcribe.return_value = ({
            "text": "这是视频完整正文。这里说明了具体需求和交付方式。",
            "segments": [{"start": 0, "end": 3, "text": "这是视频完整正文"}],
            "engine": "faster-whisper",
            "language": "zh",
            "duration": 3,
        }, "base")
        run_codex.return_value = {
            "viral_theme": "网页自动化机会",
            "audience_anxieties": ["重复操作浪费时间"],
            "contrarian_viewpoint": "机会在具体流程，不在通用工具。",
            "evidence_types": ["视频正文事实"],
            "migration_angles": ["为小商家交付一个后台录入流程，并找一位客户试用"],
            "recommended_titles": ["网页开始自己干活后，小生意出现了"],
            "opening_script": "很多人只看见工具。",
            "formula": "变化 × 需求 × 交付 × 验证",
            "content_breakdown": {},
        }

        sau_backend.run_idea_radar_pipeline(7, "普通人的 AI 机会")

        self.assertTrue(transcribe.called)
        analysis_prompt = run_codex.call_args.args[0]
        self.assertIn("这是视频完整正文", analysis_prompt)
        final_update = update_transcript.call_args_list[-1].kwargs
        self.assertEqual("success", final_update["status"])
        self.assertEqual("transcript", final_update["analysis_basis"])


if __name__ == "__main__":
    unittest.main()
