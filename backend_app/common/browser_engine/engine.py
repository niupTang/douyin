from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from pathlib import Path

from playwright.async_api import async_playwright
from playwright.async_api import Error as PlaywrightError

from .downloads import validate_download_directory
from .presentation import configure_floating_page, prepare_floating_launch


@dataclass(frozen=True)
class BrowserSpec:
    browser_type: str = "chromium"
    headless: bool = True
    launch_options: dict = field(default_factory=dict)
    context_options: dict = field(default_factory=dict)
    persistent_profile: str | None = None
    download_dir: str | Path | None = None
    presentation: str | None = None
    shared_key: str | None = None


class BrowserStrategyRegistry:
    def __init__(self):
        self._strategies = {}

    def register(self, strategy):
        key = (strategy.platform, strategy.operation)
        if key in self._strategies:
            raise ValueError(f"浏览器策略已存在：{key[0]}/{key[1]}")
        self._strategies[key] = strategy

    def get(self, platform, operation):
        try:
            return self._strategies[(platform, operation)]
        except KeyError as exc:
            raise ValueError(f"不支持的浏览器操作：{platform}/{operation}") from exc


class BrowserEngine:
    def __init__(self, registry=None, *, playwright_factory=async_playwright, init_context=None):
        self.registry = registry or BrowserStrategyRegistry()
        self.playwright_factory = playwright_factory
        self.init_context = init_context

    async def run(self, platform, operation, request):
        strategy = self.registry.get(platform, operation)
        spec = strategy.browser_spec(request)
        async with self.session(spec) as (context, page):
            return await strategy.execute(context, page, request)

    @asynccontextmanager
    async def session(self, spec):
        """Own the browser lifetime for strategies and existing collection code."""
        if spec.shared_key:
            from .shared import shared_contexts
            async with shared_contexts.session(self, spec) as session:
                yield session
            return
        launch_options = dict(spec.launch_options)
        headless = spec.headless
        if spec.presentation == "floating":
            if spec.browser_type != "chromium":
                raise ValueError("采集浮窗目前仅支持 Chromium")
            headless, launch_options = prepare_floating_launch(launch_options)
        if spec.download_dir is not None:
            launch_options["downloads_path"] = str(validate_download_directory(spec.download_dir))
        elif "downloads_path" in launch_options:
            launch_options["downloads_path"] = str(validate_download_directory(launch_options["downloads_path"]))
        elif spec.context_options.get("accept_downloads"):
            raise ValueError("启用浏览器下载时必须指定已验证的下载目录")
        manager = self.playwright_factory()
        async with manager as playwright:
            browser_type = getattr(playwright, spec.browser_type, None)
            if browser_type is None:
                raise ValueError(f"不支持的浏览器类型：{spec.browser_type}")
            browser = None
            context = None
            page = None
            try:
                if spec.persistent_profile:
                    context = await browser_type.launch_persistent_context(
                        spec.persistent_profile,
                        headless=headless,
                        **launch_options,
                        **spec.context_options,
                    )
                else:
                    browser = await browser_type.launch(headless=headless, **launch_options)
                    context = await browser.new_context(**spec.context_options)
                if self.init_context:
                    context = await self.init_context(context)
                page = context.pages[0] if context.pages else await context.new_page()
                if spec.presentation == "floating" and not headless:
                    await configure_floating_page(context, page, spec.context_options.get("viewport"))
                yield context, page
            except PlaywrightError as exc:
                if spec.presentation == "floating" and not headless and page is not None and page.is_closed():
                    raise RuntimeError("采集浮窗已关闭，本次任务已停止；可重新发起任务。") from exc
                raise
            finally:
                try:
                    if context is not None:
                        await context.close()
                finally:
                    if browser is not None:
                        await browser.close()
