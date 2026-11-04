import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from uploader.douyin_uploader.main import DouYinVideo, douyin_setup

VIDEO = BASE_DIR / "videos" / "ai-focus-data-no-liang.mp4"
COVER = BASE_DIR / "videos" / "ai-focus-data-no-liang.png"
COOKIE = BASE_DIR / "cookies" / "douyin_uploader" / "account.json"

TITLE = "AI工具越多越要克制，普通人先聚焦一件事"
TAGS = ["AI工具", "个人IP", "知识库", "内容复盘", "AI自媒体"]


async def main() -> None:
    ok = await douyin_setup(COOKIE, handle=False)
    if not ok:
        raise RuntimeError(f"抖音 cookie 无效或不存在：{COOKIE}")
    app = DouYinVideo(
        TITLE,
        VIDEO,
        TAGS,
        0,
        COOKIE,
        thumbnail_path=str(COVER),
    )
    await app.main()


if __name__ == "__main__":
    asyncio.run(main())
