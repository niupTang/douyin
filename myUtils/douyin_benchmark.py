import json
import re
from pathlib import Path
from urllib.parse import quote, urlparse

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
    user_url = normalize_douyin_user_url(value)
    return user_url or value.split("?")[0].split("#")[0]


def parse_count(text, labels):
    for label in labels:
        patterns = [
            rf"([\d.,]+)[ \t]*万?[ \t]*{label}",
            rf"{label}[ \t]*([\d.,]+)[ \t]*万?",
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


def normalize_douyin_user_url(url):
    value = (url or "").strip()
    if not value:
        return ""
    if value.startswith("//"):
        value = f"https:{value}"
    if value.startswith("/"):
        value = f"https://www.douyin.com{value}"
    if not value.startswith(("http://", "https://")):
        return ""
    try:
        parsed = urlparse(value)
    except Exception:
        return ""
    if "douyin.com" not in parsed.netloc.lower():
        return ""
    match = re.search(r"/user/([^/?#]+)", parsed.path)
    if not match:
        return ""
    user_id = match.group(1).strip()
    if not user_id or user_id.lower() == "self":
        return ""
    return f"https://www.douyin.com/user/{user_id}"


async def discover_douyin_benchmark_accounts(
    keywords,
    cookie_file=None,
    limit=6,
    scroll_rounds=4,
):
    keyword_list = [item.strip() for item in (keywords or []) if item and item.strip()]
    if not keyword_list:
        raise ValueError("请至少输入一个对标关键词")

    limit = max(1, min(int(limit or 6), 20))
    storage_state = None
    if cookie_file:
        cookie_path = Path(BASE_DIR / "cookiesFile" / cookie_file)
        if cookie_path.exists():
            storage_state = cookie_path

    results = []
    seen = set()
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

        extract_script = """(keyword) => {
            const cleanText = (value) => (value || "").replace(/\\s+/g, " ").trim();
            const normalizeHref = (href) => {
                try {
                    const url = new URL(href);
                    url.search = "";
                    url.hash = "";
                    return url.toString();
                } catch (_) {
                    return "";
                }
            };
            const anchors = Array.from(document.querySelectorAll("a[href]"));
            const users = [];
            const seen = new Set();
            for (const a of anchors) {
                const href = normalizeHref(a.href || "");
                if (!/douyin\\.com\\/user\\//.test(href)) continue;
                if (seen.has(href)) continue;
                seen.add(href);
                const card = a.closest("li, div") || a;
                const img = card.querySelector("img");
                const text = cleanText(card.innerText || a.innerText || "");
                const lines = text.split(/\\n|\\r| {2,}/).map(cleanText).filter(Boolean);
                const nickname = cleanText(
                    a.getAttribute("title") ||
                    a.getAttribute("aria-label") ||
                    lines.find(line => line.length > 1 && !/^粉丝|^获赞|^关注|^作品/.test(line)) ||
                    ""
                );
                users.push({
                    homepage_url: href,
                    nickname,
                    avatar: img ? img.src : "",
                    source_keyword: keyword,
                    raw_text: text.slice(0, 800)
                });
            }
            return users;
        }"""

        for keyword in keyword_list:
            search_url = f"https://www.douyin.com/search/{quote(keyword)}?type=user"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(5000)
            stagnant_rounds = 0
            last_count = len(results)
            for _ in range(scroll_rounds + 1):
                for candidate in await page.evaluate(extract_script, keyword):
                    homepage_url = normalize_douyin_user_url(candidate.get("homepage_url"))
                    if not homepage_url or homepage_url in seen:
                        continue
                    seen.add(homepage_url)
                    candidate["homepage_url"] = homepage_url
                    results.append(candidate)
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break
                if len(results) == last_count:
                    stagnant_rounds += 1
                else:
                    stagnant_rounds = 0
                if stagnant_rounds >= 2:
                    break
                last_count = len(results)
                await page.mouse.wheel(0, 2200)
                await page.wait_for_timeout(1500)
            if len(results) >= limit:
                break

        await context.close()
        await browser.close()

    return results[:limit]


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
        extract_script = r"""(maxVideos) => {
                const text = document.body ? document.body.innerText : "";
                const title = document.title || "";
                const h1 = document.querySelector("h1")?.innerText || "";
                const cleanText = (value) => (value || "").replace(/\s+/g, " ").trim();
                const looksLikeCount = (value) => /^[\d.,]+(?:\s*[万wW])?$/.test(cleanText(value));
                const pickCountFromNode = (node) => {
                    if (!node) return "";
                    const ownText = cleanText(node.innerText || node.textContent || "");
                    if (looksLikeCount(ownText)) return ownText;

                    const divs = Array.from(node.querySelectorAll("div")).map(div => cleanText(div.innerText || div.textContent || ""));
                    const secondDiv = divs[1] || "";
                    if (looksLikeCount(secondDiv)) return secondDiv;
                    const firstCount = divs.find(looksLikeCount);
                    if (firstCount) return firstCount;

                    let parent = node.parentElement;
                    for (let depth = 0; parent && depth < 4; depth += 1, parent = parent.parentElement) {
                        const siblingDivs = Array.from(parent.children)
                            .filter(child => child.tagName === "DIV")
                            .map(div => cleanText(div.innerText || div.textContent || ""));
                        const siblingSecondDiv = siblingDivs[1] || "";
                        if (looksLikeCount(siblingSecondDiv)) return siblingSecondDiv;
                        const siblingCount = siblingDivs.find(looksLikeCount);
                        if (siblingCount) return siblingCount;
                    }
                    return "";
                };
                const statText = (e2e) => {
                    const node = document.querySelector(`[data-e2e="${e2e}"]`);
                    return pickCountFromNode(node);
                };
                const profileStats = {
                    following: statText("user-info-follow"),
                    fans: statText("user-info-fans"),
                    receivedLikes: statText("user-info-like"),
                };
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
                    return /^[\d.,]+\s*[万wW]?$/.test(text);
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
                        .split(/\n|\r/)
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
                    if (!/douyin\.com\/(video|note)\//.test(href)) continue;
                    if (seen.has(href)) continue;
                    seen.add(href);
                    const card = a.closest("li, div") || a;
                    const img = card.querySelector("img");
                    const itemText = (card.innerText || a.innerText || "").trim();
                    const lines = itemText.split("\n").map(s => s.trim()).filter(Boolean);
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
                return { text, title, h1, avatar, profileStats, videos };
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
        # Keep these fields aligned with the established benchmark table/export
        # headers: followers_count=关注人, likes_count=粉丝.
        "following_count": (profile.get("profileStats") or {}).get("following") or parse_count(raw_text, ["关注"]),
        "followers_count": (profile.get("profileStats") or {}).get("following") or parse_count(raw_text, ["关注"]),
        "likes_count": (profile.get("profileStats") or {}).get("fans") or parse_count(raw_text, ["粉丝"]),
        "received_likes_count": (profile.get("profileStats") or {}).get("receivedLikes") or parse_count(raw_text, ["获赞", "喜欢"]),
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
