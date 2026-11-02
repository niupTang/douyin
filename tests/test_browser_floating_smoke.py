"""Opt-in real Chromium check, using only a routed local fixture (no accounts)."""

import asyncio
import base64
import json
import os
from pathlib import Path

import pytest

from backend_app.common.browser_engine import BrowserEngine, BrowserSpec


pytestmark = pytest.mark.skipif(
    os.environ.get("SAU_RUN_BROWSER_SMOKE") != "1",
    reason="set SAU_RUN_BROWSER_SMOKE=1 to open the local collection preview",
)


def test_real_floating_browser_scroll_click_download_and_close(tmp_path, monkeypatch):
    monkeypatch.setenv("SAU_BROWSER_PRESENTATION", "floating")
    monkeypatch.setenv("SAU_BASE_DIR", str(tmp_path))
    for key in ("TEMP", "TMP", "TMPDIR"):
        monkeypatch.setenv(key, str(tmp_path))

    async def run():
        spec = BrowserSpec(
            presentation="floating", download_dir=tmp_path,
            context_options={"viewport": {"width": 1440, "height": 1200}, "accept_downloads": True},
        )
        async with BrowserEngine().session(spec) as (context, page):
            rows = "".join(f'<article><strong>本地测试作品 {i:02}</strong><p>验证真实页面滚动和内容提取，不连接平台账号。</p></article>' for i in range(1, 16))
            html = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
            <title>Sunbird OS · 采集浮窗验证</title><style>
            *{box-sizing:border-box}body{margin:0;background:#f3f5f9;color:#202c42;font:22px "Microsoft YaHei",sans-serif}
            header{background:#183358;color:white;padding:36px 52px}h1{font-size:34px;margin:0 0 12px}
            main{padding:24px 52px}article{padding:24px;margin:16px 0;background:white;border:1px solid #dce3ef;border-radius:14px}
            p{color:#687b94}button,a{display:inline-block;background:#1668dc;color:white;border:0;border-radius:10px;padding:18px 26px;font:inherit;text-decoration:none;cursor:pointer}
            </style><header><h1>采集浮窗 · 本地验证</h1><div>真实浏览器页面 / 可拖动 / 自动滚动 / 下载验证</div></header>
            <main><button onclick="this.textContent='点击成功'">开始验证</button>
            <a download="collection-demo.txt" href="data:text/plain;charset=utf-8,local-test-only">下载测试文件</a>''' + rows + "</main></html>"
            await page.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body=html))
            await page.goto("https://collection.test/", wait_until="load")
            assert await page.evaluate("[innerWidth, innerHeight]") == [1440, 1200]
            await page.get_by_role("button", name="开始验证").click(timeout=10000)
            assert await page.get_by_role("button").inner_text() == "点击成功"
            async with page.expect_download() as pending:
                await page.get_by_role("link", name="下载测试文件").click()
            download = await pending.value
            target = tmp_path / download.suggested_filename
            await download.save_as(target)
            assert target.read_text() == "local-test-only"
            cdp = await context.new_cdp_session(page)
            bounds = await cdp.send("Browser.getWindowForTarget")
            assert bounds["bounds"]["width"] == 900
            assert bounds["bounds"]["height"] == 700
            image = await cdp.send("Page.captureScreenshot", {"format": "png", "fromSurface": False})
            artifact_dir = Path(__file__).resolve().parents[1] / ".sau-cache" / "floating-preview"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            (artifact_dir / "collection-window.png").write_bytes(base64.b64decode(image["data"]))
            await page.mouse.wheel(0, 800)
            await page.wait_for_function("scrollY > 0")
            assert await page.locator("article").count() == 15
            (artifact_dir / "result.json").write_text(json.dumps({
                "window": bounds["bounds"], "viewport": await page.evaluate("[innerWidth, innerHeight]"),
                "scrollY": await page.evaluate("scrollY"), "download": "verified", "click": "verified",
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            owned_browser = context.browser
        assert not owned_browser.is_connected()

    asyncio.run(run())
