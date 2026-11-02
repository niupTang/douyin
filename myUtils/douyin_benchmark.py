import json
import os
import re
from pathlib import Path
from urllib.parse import quote, urlparse

from playwright.async_api import async_playwright

from backend_app.common.browser_engine import BrowserEngine, BrowserSpec, BrowserStrategyRegistry
from conf import BASE_DIR
from utils.base_social_media import set_init_script
from backend_app.common.browser_engine.shared import on_browser_worker
from myUtils.douyin_session import resolve_storage_state, session_key
from backend_app.common.browser_engine.presentation import prepare_floating_launch


def launch_options():
    options = {"headless": True}
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("ALL_PROXY")
    if proxy:
        options["proxy"] = {"server": proxy}
    return options


def collection_browser_spec(storage_state=None):
    options = launch_options()
    options.pop("headless", None)
    headless, options = prepare_floating_launch(options)
    options["args"] = [arg for arg in options.get("args", [])
                       if not arg.startswith("--window-size=")]
    options["args"].append("--window-size=1280,900")
    context_options = {
        "viewport": {"width": 1440, "height": 1200},
        "locale": "zh-CN",
        "accept_downloads": False,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
    }
    if storage_state:
        context_options["storage_state"] = str(storage_state)
    return BrowserSpec(
        headless=headless, launch_options=options, context_options=context_options,
        shared_key=session_key(storage_state),
    )


def douyin_profile_dir():
    path = Path(BASE_DIR) / "cookiesFile" / "douyin_browser_profile"
    path.mkdir(parents=True, exist_ok=True)
    return path


class DouyinInteractiveLoginStrategy:
    platform = "douyin"
    operation = "interactive_login"

    def browser_spec(self, request):
        options = launch_options()
        options.pop("headless", None)
        return BrowserSpec(
            headless=False,
            launch_options=options,
            context_options={"viewport": {"width": 1440, "height": 1000}, "locale": "zh-CN"},
            persistent_profile=str(douyin_profile_dir()),
        )

    async def execute(self, context, page, request):
        await page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(request["timeout_ms"])


async def open_douyin_login_browser(timeout_ms=600000, cookie_file=None):
    """打开可见的持久化浏览器，用户完成扫码/验证后关闭窗口即可。"""
    from myUtils.douyin_session import open_preview
    return await open_preview("https://www.douyin.com/", cookie_file)


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


def build_profile_counts(profile_stats, raw_text):
    """将抖音主页 data-e2e 统计项映射到语义明确的数据库字段。"""
    stats = profile_stats or {}
    following = stats.get("following") or parse_count(raw_text, ["关注"])
    followers = stats.get("fans") or parse_count(raw_text, ["粉丝"])
    received_likes = stats.get("receivedLikes") or parse_count(raw_text, ["获赞", "喜欢"])
    return {
        "following_count": following,
        "followers_count": followers,
        # likes_count 是旧字段，继续写入获赞值以免旧导出/API 读取到错误的粉丝数。
        "likes_count": received_likes,
        "received_likes_count": received_likes,
    }


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


async def dismiss_douyin_login_popup(page):
    """关闭未登录访问公开页面时出现的登录遮罩。"""
    panel = page.locator("#login-panel-new, [id^='login-full-panel-']")
    if not await panel.count() or not await panel.first.is_visible():
        return False

    close_button = page.locator(
        "#douyin_login_comp_flat_panel_title + div, "
        "#login-panel-new [aria-label='关闭']"
    )
    if await close_button.count() and await close_button.first.is_visible():
        await close_button.first.click(force=True)
    else:
        await page.keyboard.press("Escape")

    try:
        await panel.first.wait_for(state="hidden", timeout=3000)
    except Exception:
        # 页面版本变化时，移除仍占据视口的遮罩，避免阻止滚动与采集。
        await page.evaluate(
            """() => {
                document.querySelectorAll('#login-panel-new, [id^="login-full-panel-"]')
                    .forEach(node => node.remove());
            }"""
        )
    return True


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


@on_browser_worker
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
    storage_state = resolve_storage_state(cookie_file)
    if cookie_file:
        cookie_path = Path(BASE_DIR / "cookiesFile" / cookie_file)
        if cookie_path.exists():
            storage_state = cookie_path

    results = []
    seen = set()
    engine = BrowserEngine(playwright_factory=async_playwright, init_context=set_init_script)
    async with engine.session(collection_browser_spec(storage_state)) as (context, page):

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

    return results[:limit]


@on_browser_worker
async def search_douyin_content(keywords, cookie_file=None, target_count=50, scroll_rounds=12):
    """采集抖音综合内容搜索结果，保留页面原始顺序。"""
    keyword_list = [item.strip() for item in (keywords or []) if item and item.strip()]
    if not keyword_list:
        raise ValueError("请至少输入一个内容关键词")
    target_count = max(1, min(int(target_count or 50), 100))
    storage_state = resolve_storage_state(cookie_file)
    spec = collection_browser_spec(storage_state)
    # Content search previously used Chromium's default user agent.
    spec.context_options.pop("user_agent", None)
    engine = BrowserEngine(playwright_factory=async_playwright, init_context=set_init_script)
    async with engine.session(spec) as (context, page):
        results = []
        seen = set()
        for keyword in keyword_list:
            await page.goto(f"https://www.douyin.com/search/{quote(keyword)}?type=video", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(5000)
            page_hint = f"{await page.title()} {await page.locator('body').inner_text(timeout=10000)}"
            if any(token in page_hint for token in ("验证码", "安全验证", "人机验证")):
                raise RuntimeError("抖音触发了验证码，请先完成登录/验证后再搜索")
            for _ in range(scroll_rounds + 1):
                items = await page.evaluate("""() => {
                  const clean = v => (v || '').replace(/\\s+/g, ' ').trim();
                  const count = v => { const t = clean(v); const m = t.match(/^([\\d.,]+)\\s*([万wW])?$/); if (!m) return {raw:'', value:null}; return {raw:t, value: Math.round(parseFloat(m[1].replace(/,/g,'')) * (m[2] ? 10000 : 1))}; };
                  const out = []; const local = new Set();
                  for (const a of Array.from(document.querySelectorAll('a[href]'))) {
                    let href = ''; try { const u = new URL(a.href); u.search=''; u.hash=''; href=u.toString(); } catch (_) {}
                    if (!/douyin\\.com\\/(video|note)\\//.test(href) || local.has(href)) continue;
                    local.add(href); const card = a.closest('li, div') || a; const img = card.querySelector('img');
                    const lines = (card.innerText || a.innerText || '').split(/\\n|\\r/).map(clean).filter(Boolean);
                    const metric = lines.map(count).find(x => x.raw) || {raw:'', value:null};
                    const title = lines.find(x => x.length > 1 && x.length <= 260 && !count(x).raw && !/^(赞|评论|分享|收藏|打开|播放|更多)$/.test(x)) || '';
                    const authorLink = Array.from(card.querySelectorAll('a[href]')).find(x => /douyin\\.com\\/user\\//.test(x.href));
                    out.push({video_url: href, title, cover_url: img?.src || '', like_count: metric.raw, like_count_value: metric.value, author_name: clean(authorLink?.innerText || ''), author_url: authorLink?.href || '', video_type: href.includes('/note/') ? 'note' : 'video'});
                  } return out;
                }""")
                for item in items:
                    if item.get("video_url") in seen:
                        continue
                    if not item.get("title"):
                        continue
                    seen.add(item["video_url"]); item["source_rank"] = len(results) + 1; item["source_keyword"] = keyword; results.append(item)
                    if len(results) >= target_count: break
                if len(results) >= target_count: break
                await page.mouse.wheel(0, 2400); await page.wait_for_timeout(1600)
            if len(results) >= target_count: break
    return results[:target_count]


@on_browser_worker
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
    storage_state = resolve_storage_state(cookie_file)
    if cookie_file:
        cookie_path = Path(BASE_DIR / "cookiesFile" / cookie_file)
        if cookie_path.exists():
            storage_state = cookie_path

    engine = BrowserEngine(playwright_factory=async_playwright, init_context=set_init_script)
    async with engine.session(collection_browser_spec(storage_state)) as (context, page):
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)
        await dismiss_douyin_login_popup(page)

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
                const avatarNode = document.querySelector('[data-e2e="live-avatar"] img');
                const avatar = avatarNode?.src || imgs.find(src => /aweme-avatar|avatar/.test(src)) || "";
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
            await dismiss_douyin_login_popup(page)
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

    profile_counts = build_profile_counts(profile.get("profileStats"), raw_text)
    return {
        "homepage_url": url,
        "nickname": nickname,
        "avatar": profile.get("avatar") or "",
        "bio": bio,
        **profile_counts,
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
