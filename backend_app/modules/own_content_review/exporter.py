import asyncio
import re
from datetime import datetime
from pathlib import Path

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from backend_app.common.browser_engine import BrowserEngine, BrowserSpec, BrowserStrategyRegistry
from backend_app.common.browser_engine.downloads import validate_download_directory
from myUtils.douyin_benchmark import launch_options
from utils.base_social_media import set_init_script


CREATOR_CONTENT_URL = "https://creator.douyin.com/creator-micro/content/manage"


def creator_launch_options():
    # Creator Center's data endpoints are more reliable without the inherited
    # local proxy; regular benchmark collection keeps its existing proxy path.
    options = launch_options()
    options.pop("proxy", None)
    return options


def _looks_like_export_text(value):
    text = re.sub(r"\s+", "", value or "")
    return "导出" in text or "下载数据" in text or "数据下载" in text


async def _click_export(page):
    candidates = page.get_by_role("button").filter(has_text=re.compile("导出|下载数据|数据下载"))
    if await candidates.count():
        await candidates.first.click()
        return

    candidates = page.get_by_text(re.compile("导出|下载数据|数据下载"))
    for index in range(min(await candidates.count(), 10)):
        item = candidates.nth(index)
        if await item.is_visible():
            await item.click()
            return
    raise RuntimeError("未找到创作者中心的导出按钮，请先登录并确认账号有数据导出入口")


class DouyinCreatorExportStrategy:
    platform = "douyin"
    operation = "export_own_content"

    def browser_spec(self, request):
        options = creator_launch_options()
        return BrowserSpec(
            headless=options.pop("headless", True),
            launch_options=options,
            download_dir=request["download_dir"],
            presentation="floating",
            context_options={
                "storage_state": str(request["cookie_path"]),
                "accept_downloads": True,
                "viewport": {"width": 1440, "height": 1000},
                "locale": "zh-CN",
            },
        )

    async def execute(self, context, page, request):
        cookie_path = request["cookie_path"]
        download_dir = request["download_dir"]
        try:
            await page.goto(CREATOR_CONTENT_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(4000)
            body = await page.locator("body").inner_text(timeout=15000)
            if any(token in body for token in ("登录", "扫码登录", "登录后")) and not _looks_like_export_text(body):
                raise RuntimeError("账号登录态已失效，请到账号管理重新登录")
            async with page.expect_download(timeout=30000) as download_info:
                await _click_export(page)
            download = await download_info.value
            suffix = Path(download.suggested_filename or "douyin_export.xlsx").suffix or ".xlsx"
            target = download_dir / f"douyin_creator_export_{datetime.now():%Y%m%d_%H%M%S}{suffix}"
            await download.save_as(target)
            refreshed_state = cookie_path.with_suffix(f"{cookie_path.suffix}.tmp")
            await context.storage_state(path=refreshed_state)
            refreshed_state.replace(cookie_path)
            return target
        except PlaywrightTimeoutError as exc:
            raise RuntimeError("点击导出后未收到文件下载，请检查页面是否需要选择时间范围或二次确认") from exc


async def _download_creator_export(cookie_path, download_dir, playwright_factory, init_context):
    registry = BrowserStrategyRegistry()
    registry.register(DouyinCreatorExportStrategy())
    engine = BrowserEngine(registry, playwright_factory=playwright_factory, init_context=init_context)
    return await engine.run(
        "douyin", "export_own_content",
        {"cookie_path": cookie_path, "download_dir": download_dir},
    )


def export_creator_content(
    cookie_path,
    download_dir=None,
    playwright_factory=async_playwright,
    init_context=set_init_script,
):
    cookie_path = Path(cookie_path).resolve()
    if download_dir is None:
        raise ValueError("请先选择下载目录")
    target_dir = validate_download_directory(download_dir)
    return asyncio.run(_download_creator_export(cookie_path, target_dir, playwright_factory, init_context))
