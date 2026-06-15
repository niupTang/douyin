import json
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from conf import BASE_DIR
from utils.base_social_media import set_init_script


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


def parse_count(text, labels):
    for label in labels:
        patterns = [
            rf"([\d.,]+)\s*万?\s*{label}",
            rf"{label}\s*([\d.,]+)\s*万?",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
    return ""


def compact_lines(text, limit=80):
    lines = []
    for line in re.split(r"[\r\n]+", text or ""):
        clean = re.sub(r"\s+", " ", line).strip()
        if clean and clean not in lines:
            lines.append(clean)
        if len(lines) >= limit:
            break
    return lines


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


async def scrape_douyin_benchmark(
    homepage_url,
    cookie_file=None,
    max_videos=20,
    existing_video_urls=None,
    max_scan_videos=120,
    scroll_rounds=10,
):
    url = normalize_douyin_url(homepage_url)
    existing_video_urls = set(existing_video_urls or [])
    storage_state = None
    if cookie_file:
        cookie_path = Path(BASE_DIR / "cookiesFile" / cookie_file)
        if cookie_path.exists():
            storage_state = cookie_path

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
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
            context_kwargs["storage_state"] = storage_state
        context = await browser.new_context(**context_kwargs)
        context = await set_init_script(context)
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)

        title = await page.title()
        body_text = await page.locator("body").inner_text(timeout=15000)
        extract_script = """(maxVideos) => {
                const text = document.body ? document.body.innerText : "";
                const title = document.title || "";
                const h1 = document.querySelector("h1")?.innerText || "";
                const imgs = Array.from(document.images).map(img => img.src).filter(Boolean);
                const avatar = imgs.find(src => /avatar|aweme|douyin|pstatp|byteimg/.test(src)) || imgs[0] || "";
                const anchors = Array.from(document.querySelectorAll("a[href]"));
                const videos = [];
                const seen = new Set();
                const normalizeHref = (href) => {
                    try {
                        const url = new URL(href);
                        url.search = "";
                        url.hash = "";
                        return url.toString();
                    } catch (_) {
                        return (href || "").split("?")[0].split("#")[0];
                    }
                };
                const isCountText = (value) => {
                    const text = (value || "").trim();
                    return /^[\\d.,]+\\s*[万wW]?$/.test(text);
                };
                const isRecommendHref = (href) => {
                    try {
                        const url = new URL(href);
                        const source = url.searchParams.get("source") || "";
                        return /Baiduspider/i.test(source);
                    } catch (_) {
                        return /source=Baiduspider/i.test(href || "");
                    }
                };
                const isNoiseText = (value) => {
                    const text = cleanText(value);
                    if (!text) return true;
                    if (isCountText(text)) return true;
                    if (/^(赞|点赞|评论|分享|收藏|置顶|作品|喜欢|合集|打开|播放|更多)$/.test(text)) return true;
                    if (/^打开/.test(text) || /^播放/.test(text) || /^更多/.test(text)) return true;
                    return false;
                };
                const cleanText = (value) => (value || "").replace(/\\s+/g, " ").trim();
                const pickTitle = (card, a, img) => {
                    const attrs = [
                        img?.getAttribute("alt"),
                        img?.getAttribute("aria-label"),
                        img?.getAttribute("title"),
                        a.getAttribute("aria-label"),
                        a.getAttribute("title"),
                    ].map(cleanText).filter(Boolean);
                    for (const value of attrs) {
                        if (!isCountText(value) && !/^打开/.test(value) && value.length > 1) {
                            return value;
                        }
                    }

                    const candidates = Array.from(card.querySelectorAll("[title], [aria-label], span, p, div"))
                        .flatMap((node) => [
                            node.getAttribute("title"),
                            node.getAttribute("aria-label"),
                            node.innerText,
                            node.textContent,
                        ])
                        .map(cleanText)
                        .filter(Boolean);
                    for (const value of candidates) {
                        if (isNoiseText(value)) continue;
                        if (value.length > 260) continue;
                        if (value.length > 1) return value;
                    }

                    const lines = (card.innerText || a.innerText || "")
                        .split(/\\n|\\r/)
                        .map(cleanText)
                        .filter(Boolean);
                    for (const line of lines) {
                        if (!isNoiseText(line) && line.length > 1 && line.length <= 260) return line;
                    }
                    return "";
                };
                for (const a of anchors) {
                    const rawHref = a.href || "";
                    if (isRecommendHref(rawHref)) continue;
                    const href = normalizeHref(rawHref);
                    if (!/douyin\\.com\\/(video|note)\\//.test(href)) continue;
                    if (seen.has(href)) continue;
                    seen.add(href);
                    const card = a.closest("li, div") || a;
                    const img = card.querySelector("img");
                    const itemText = (card.innerText || a.innerText || "").trim();
                    const lines = itemText.split("\\n").map(s => s.trim()).filter(Boolean);
                    const likeCount = lines.find(isCountText) || "";
                    const pickedTitle = pickTitle(card, a, img);
                    if (!pickedTitle || /^热门/.test(pickedTitle)) continue;
                    videos.push({
                        video_url: href,
                        title: pickedTitle,
                        cover_url: img ? img.src : "",
                        like_count: likeCount,
                        raw_text: itemText
                    });
                    if (videos.length >= maxVideos) break;
                }
                return { text, title, h1, avatar, videos };
            }"""
        collected_videos = {}
        profile = await page.evaluate(extract_script, max_scan_videos)
        last_count = 0
        stagnant_rounds = 0
        for _ in range(scroll_rounds + 1):
            profile = await page.evaluate(extract_script, max_scan_videos)
            for video in profile.get("videos") or []:
                video_url = video.get("video_url")
                if video_url and video_url not in collected_videos:
                    collected_videos[video_url] = video

            new_count = sum(1 for video_url in collected_videos if video_url not in existing_video_urls)
            if new_count >= max_videos:
                break

            if len(collected_videos) == last_count:
                stagnant_rounds += 1
            else:
                stagnant_rounds = 0
            if stagnant_rounds >= 3:
                break
            last_count = len(collected_videos)

            await page.mouse.wheel(0, 2600)
            await page.wait_for_timeout(1800)

        await context.close()
        await browser.close()

    raw_text = profile.get("text") or body_text or ""
    nickname = profile.get("h1") or (title.split("-")[0].strip() if title else "")
    lines = compact_lines(raw_text)
    bio = ""
    for line in lines:
        if line and line != nickname and not any(token in line for token in ["关注", "粉丝", "获赞", "作品"]):
            bio = line
            break

    selected_videos = []
    selected_new_count = 0
    for video in collected_videos.values():
        if video.get("video_url") not in existing_video_urls:
            selected_new_count += 1
        selected_videos.append(video)
        if selected_new_count >= max_videos:
            break

    return {
        "homepage_url": url,
        "nickname": nickname,
        "avatar": profile.get("avatar") or "",
        "bio": bio,
        "following_count": parse_count(raw_text, ["关注"]),
        "followers_count": parse_count(raw_text, ["粉丝"]),
        "likes_count": parse_count(raw_text, ["获赞", "喜欢"]),
        "video_count": parse_count(raw_text, ["作品"]),
        "videos": [
            {
                **video,
                "title": clean_video_title(video.get("title")) or "",
            }
            for video in selected_videos
        ],
        "raw_data": {
            "title": title,
            "lines": lines,
            "text_sample": raw_text[:5000],
            "scanned_video_count": len(collected_videos),
            "target_new_video_count": max_videos,
        },
    }
