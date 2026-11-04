import asyncio
from pathlib import Path

from playwright.async_api import async_playwright


async def main() -> None:
    base = Path(__file__).resolve().parent
    html_path = base / "talking-head-cover-vertical.html"
    png_path = base / "douyin-cover-1080x1920.png"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        )
        page = await browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=1)
        await page.goto(html_path.as_uri())
        await page.locator(".cover").screenshot(path=str(png_path))
        await browser.close()

    print(png_path)


if __name__ == "__main__":
    asyncio.run(main())
