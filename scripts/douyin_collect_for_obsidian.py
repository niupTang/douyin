#!/usr/bin/env python3
"""抖音用户主页采集脚本 - 供 Codex 自动化调用

采集指定抖音用户的视频列表，输出 JSON 到 stdout。
支持去重：传入已处理的视频 URL 列表文件。

用法:
    python douyin_collect_for_obsidian.py <douyin_homepage_url> [--existing FILE] [--max N] [--cookie NAME]
"""

import asyncio
import json
import os
import sys
import re
from pathlib import Path
from urllib.parse import urlparse

# 添加 social-auto-upload 项目路径
PROJECT_DIR = Path(r"E:\social-auto-upload").resolve()
sys.path.insert(0, str(PROJECT_DIR))

from conf import BASE_DIR
from utils.base_social_media import set_init_script

PLAYWRIGHT_BROWSERS_PATH = str(Path(os.environ["LOCALAPPDATA"]) / "ms-playwright")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = PLAYWRIGHT_BROWSERS_PATH


# ── 以下代码复用于 douyin_benchmark.py ──────────────────

def normalize_douyin_url(url):
    value = (url or "").strip()
    if not value:
        raise ValueError("抖音主页链接不能为空")
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    host = urlparse(value).netloc.lower()
    if "douyin.com" not in host:
        raise ValueError("请输入 douyin.com 的主页链接")
    return value.split("?")[0]


def clean_video_title(value):
    text = re.sub(r"\s+", " ", value or "").strip()
    if not text:
        return ""
    text = re.sub(r"^(视频|图文|作品|置顶)[:：\s-]*", "", text).strip()
    if text.startswith("热门"):
        return ""
    if not text:
        return ""
    if re.fullmatch(r"[\d.,]+", text):
        return ""
    if re.fullmatch(r"[\d.,]+\s*[万wW]?", text):
        return ""
    if text in {"赞", "点赞", "评论", "分享", "收藏"}:
        return ""
    return text


# ── 主采集逻辑 ──────────────────

async def scrape_homepage(homepage_url, cookie_name=None, max_videos=30, existing_urls=None):
    from playwright.async_api import async_playwright

    url = normalize_douyin_url(homepage_url)
    existing_urls = set(existing_urls or [])
    storage_state = None

    if cookie_name:
        cookie_path = Path(BASE_DIR / "cookies" / cookie_name)
        if cookie_path.exists():
            storage_state = cookie_path

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context_kwargs = {
            "viewport": {"width": 1440, "height": 1200},
            "locale": "zh-CN",
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        }
        if storage_state:
            context_kwargs["storage_state"] = str(storage_state)
        context = await browser.new_context(**context_kwargs)
        context = await set_init_script(context)
        page = await context.new_page()

        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)

        title = await page.title()
        body_text = await page.locator("body").inner_text(timeout=15000)

        # ── JS 提取脚本（同 douyin_benchmark） ──
        extract_script = """(maxVideos) => {
            const anchors = Array.from(document.querySelectorAll("a[href]"));
            const seen = new Set();
            const videos = [];
            const normalizeHref = (href) => {
                try {
                    const u = new URL(href);
                    u.search = ""; u.hash = "";
                    return u.toString();
                } catch (_) {
                    return (href || "").split("?")[0].split("#")[0];
                }
            };
            const isCountText = (v) => /^[\\d.,]+\\s*[万wW]?$/.test((v||"").trim());
            const isNoiseText = (v) => {
                const t = (v||"").trim();
                if (!t) return true;
                if (/^(赞|点赞|评论|分享|收藏|热门|视频|图文|作品|置顶)$/.test(t)) return true;
                if (t.length > 260) return true;
                return false;
            };
            const pickTitle = (card, a, img) => {
                const candidates = [a.title, a.getAttribute("aria-label"), a.innerText, a.textContent,
                    card.title, card.getAttribute("aria-label"), card.innerText, card.textContent,
                    img && img.alt, img && img.title].filter(Boolean);
                for (const v of candidates) {
                    const c = (v||"").trim();
                    if (!isNoiseText(c) && c.length > 1) return c;
                }
                const lines = (card.innerText||a.innerText||"").split(/\\n|\\r/).map(s=>s.trim()).filter(Boolean);
                for (const l of lines) {
                    if (!isNoiseText(l) && l.length > 1 && l.length <= 260) return l;
                }
                return "";
            };
            for (const a of anchors) {
                const href = normalizeHref(a.href||"");
                if (!/douyin\\.com\\/(video|note)\\//.test(href)) continue;
                if (seen.has(href)) continue;
                seen.add(href);
                const card = a.closest("li, div") || a;
                const img = card.querySelector("img");
                const pickedTitle = pickTitle(card, a, img);
                if (!pickedTitle || /^热门/.test(pickedTitle)) continue;
                videos.push({
                    video_url: href,
                    title: pickedTitle,
                    cover_url: img ? img.src : "",
                    raw_text: (card.innerText||a.innerText||"").trim()
                });
                if (videos.length >= maxVideos) break;
            }
            const imgs = Array.from(document.images).map(i=>i.src).filter(Boolean);
            const avatar = imgs.find(s=>/avatar|aweme|douyin|pstatp|byteimg/.test(s))||imgs[0]||"";
            const ogTitle = (document.querySelector('meta[property="og:title"]')||{}).content||"";
            const ogDesc = (document.querySelector('meta[property="og:description"]')||{}).content||"";
            const metaDesc = (document.querySelector('meta[name="description"]')||{}).content||"";
            return {
                title: document.title,
                h1: (document.querySelector("h1")||{}).innerText||"",
                avatar: avatar,
                videos: videos,
                text: document.body ? document.body.innerText : "",
                og_title: ogTitle,
                og_description: ogDesc,
                meta_description: metaDesc
            };
        }"""

        collected_videos = {}
        new_count = 0
        for _ in range(12):  # 最多滚动 12 次
            profile = await page.evaluate(extract_script, 120)
            for v in profile.get("videos") or []:
                vu = v.get("video_url")
                if vu and vu not in collected_videos:
                    collected_videos[vu] = v
                # 一旦收集到足够的新视频就提前退出
                new_count = sum(1 for u in collected_videos if u not in existing_urls)
                if new_count >= max_videos:
                    break
            if new_count >= max_videos:
                break
            await page.mouse.wheel(0, 2600)
            await page.wait_for_timeout(1800)

        await context.close()
        await browser.close()

    # 提取用户信息
    nickname = profile.get("h1") or (title.split("-")[0].strip() if title else "")
    raw_text = profile.get("text", "")

    # 精选新视频
    selected = []
    for v in collected_videos.values():
        entry = {
            "video_url": v.get("video_url", ""),
            "title": clean_video_title(v.get("title", "")),
            "cover_url": v.get("cover_url", ""),
        }
        if entry["title"]:
            selected.append(entry)
            if len(selected) >= max_videos * 2:
                break

    return {
        "homepage_url": url,
        "nickname": nickname,
        "avatar": profile.get("avatar", ""),
        "og_title": profile.get("og_title", ""),
        "og_description": profile.get("og_description", ""),
        "meta_description": profile.get("meta_description", ""),
        "total_found": len(collected_videos),
        "videos": selected,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="采集抖音用户主页视频")
    parser.add_argument("url", help="抖音主页 URL")
    parser.add_argument("--existing", help="已处理视频 URL 的 JSON 文件路径（去重用）")
    parser.add_argument("--max", type=int, default=30, help="最多采集新视频数")
    parser.add_argument("--cookie", default="douyin_sunbird.json", help="Cookie 文件名")
    parser.add_argument("--output-existing", help="更新后的已处理 URL 文件保存路径（若指定 --existing 则自动更新）")
    args = parser.parse_args()

    # 加载已有 URL
    existing_urls = set()
    if args.existing and os.path.exists(args.existing):
        with open(args.existing, "r", encoding="utf-8-sig") as f:
            existing_urls = set(json.load(f))

    # 采集
    result = asyncio.run(scrape_homepage(
        args.url,
        cookie_name=args.cookie,
        max_videos=args.max,
        existing_urls=existing_urls,
    ))

    # 区分新/旧视频
    new_videos = [v for v in result["videos"] if v["video_url"] not in existing_urls]
    result["new_videos"] = new_videos
    result["new_count"] = len(new_videos)
    result["existing_count"] = len(existing_urls)
    result["all_urls"] = sorted(set(v["video_url"] for v in result["videos"]) | existing_urls)

    # 输出 JSON
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 更新已有 URL 文件
    if args.output_existing and result["all_urls"]:
        os.makedirs(os.path.dirname(args.output_existing) or ".", exist_ok=True)
        with open(args.output_existing, "w", encoding="utf-8") as f:
            json.dump(result["all_urls"], f, ensure_ascii=False, indent=2)
    elif args.existing and result["all_urls"]:
        with open(args.existing, "w", encoding="utf-8") as f:
            json.dump(result["all_urls"], f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
