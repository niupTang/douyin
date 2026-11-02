import asyncio
import builtins
import hashlib
from backend_app.common import sqlite as sqlite3

from playwright.async_api import async_playwright

from myUtils.auth import check_cookie
from utils.base_social_media import set_init_script
import uuid
from pathlib import Path
from conf import BASE_DIR
from backend_app.modules.accounts import repository as account_repository


def safe_print(*args, **kwargs):
    try:
        builtins.print(*args, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(arg) for arg in args)
        encoding = getattr(__import__("sys").stdout, "encoding", None) or "utf-8"
        builtins.print(text.encode(encoding, errors="replace").decode(encoding, errors="replace"), **kwargs)


print = safe_print


def _find_douyin_identity(value):
    if isinstance(value, dict):
        nickname = value.get("nickname") or value.get("name")
        platform_user_id = (
            value.get("sec_uid")
            or value.get("secUid")
            or value.get("user_id")
            or value.get("userId")
            or value.get("uid")
        )
        if nickname and platform_user_id:
            return str(platform_user_id), str(nickname)
        for child in value.values():
            found = _find_douyin_identity(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_douyin_identity(child)
            if found:
                return found
    return None


async def _douyin_identity(page, context):
    endpoints = (
        "https://creator.douyin.com/web/api/media/user/info/",
        "https://creator.douyin.com/aweme/v1/creator/user/info/",
    )
    for endpoint in endpoints:
        try:
            response = await page.request.get(endpoint, timeout=10_000)
            if response.ok:
                found = _find_douyin_identity(await response.json())
                if found:
                    return found
        except Exception:
            continue

    try:
        bootstrap = await page.evaluate(
            """() => [
                window.__INITIAL_STATE__,
                window.__NEXT_DATA__,
                window._ROUTER_DATA
            ].filter(Boolean)"""
        )
        found = _find_douyin_identity(bootstrap)
        if found:
            return found
    except Exception:
        pass

    # uid_tt 是账号相关的抖音登录标识。只保存摘要，不把 Cookie 值写入数据库。
    # 这是创作者中心未返回公开账号信息时的兼容路径。
    cookies = await context.cookies()
    uid_cookie = next(
        (item.get("value") for item in cookies if item.get("name") == "uid_tt"),
        None,
    )
    if uid_cookie:
        digest = hashlib.sha256(uid_cookie.encode("utf-8")).hexdigest()
        return f"uid_tt:{digest}", "抖音账号"
    raise RuntimeError("无法读取已登录的抖音账号身份，请重新扫码")

# 抖音登录
async def douyin_cookie_gen(id, status_queue, existing_account_id=None):
    url_changed_event = asyncio.Event()
    async def on_url_change():
        # 检查是否是主框架的变化
        if page.url != original_url:
            url_changed_event.set()
    async with async_playwright() as playwright:
        options = {
            'headless': False
        }
        # Make sure to run headed.
        browser = await playwright.chromium.launch(**options)
        # Setup context however you like.
        context = await browser.new_context()  # Pass any options
        context = await set_init_script(context)
        # Pause the page, and start recording manually.
        page = await context.new_page()
        await page.goto("https://creator.douyin.com/")
        original_url = page.url
        img_locator = page.get_by_role("img", name="二维码")
        # 获取 src 属性值
        src = await img_locator.get_attribute("src")
        print("[OK] 图片地址:", src)
        status_queue.put(src)
        # 监听页面的 'framenavigated' 事件，只关注主框架的变化
        page.on('framenavigated',
                lambda frame: asyncio.create_task(on_url_change()) if frame == page.main_frame else None)
        try:
            # 等待 URL 变化或超时
            await asyncio.wait_for(url_changed_event.wait(), timeout=200)  # 最多等待 200 秒
            print("监听页面跳转成功")
        except asyncio.TimeoutError:
            print("监听页面跳转超时")
            await page.close()
            await context.close()
            await browser.close()
            status_queue.put("500")
            return None
        platform_user_id, display_name = await _douyin_identity(page, context)
        uuid_v1 = uuid.uuid4()
        print(f"Cookie file id: {uuid_v1}")
        cookie_dir = Path(BASE_DIR / "cookiesFile")
        pending_dir = cookie_dir / ".pending"
        pending_dir.mkdir(parents=True, exist_ok=True)
        pending_name = f".pending/{uuid_v1}.json"
        pending_path = cookie_dir / pending_name
        final_name = f"{uuid_v1}.json"
        final_path = cookie_dir / final_name
        await context.storage_state(path=pending_path)
        result = await check_cookie(3, pending_name)
        if not result:
            pending_path.unlink(missing_ok=True)
            status_queue.put("500")
            await page.close()
            await context.close()
            await browser.close()
            return None
        await page.close()
        await context.close()
        await browser.close()
        pending_path.replace(final_path)
        try:
            binding = account_repository.bind_douyin_account(
                Path(BASE_DIR / "db" / "database.db"),
                cookie_filename=final_name,
                platform_user_id=platform_user_id,
                display_name=display_name,
                remark_name=id,
                existing_account_id=existing_account_id,
            )
        except Exception:
            final_path.unlink(missing_ok=True)
            raise
        replaced_cookie = binding.get("replaced_cookie")
        if replaced_cookie and replaced_cookie != final_name:
            old_path = (cookie_dir / replaced_cookie).resolve()
            if cookie_dir.resolve() in old_path.parents:
                old_path.unlink(missing_ok=True)
        print("[OK] 用户状态已记录")
        status_queue.put("200")


# 视频号登录
async def get_tencent_cookie(id,status_queue):
    url_changed_event = asyncio.Event()
    async def on_url_change():
        # 检查是否是主框架的变化
        if page.url != original_url:
            url_changed_event.set()

    async with async_playwright() as playwright:
        options = {
            'args': [
                '--lang en-GB'
            ],
            'headless': False,  # Set headless option here
        }
        # Make sure to run headed.
        browser = await playwright.chromium.launch(**options)
        # Setup context however you like.
        context = await browser.new_context()  # Pass any options
        # Pause the page, and start recording manually.
        context = await set_init_script(context)
        page = await context.new_page()
        await page.goto("https://channels.weixin.qq.com")
        original_url = page.url

        # 监听页面的 'framenavigated' 事件，只关注主框架的变化
        page.on('framenavigated',
                lambda frame: asyncio.create_task(on_url_change()) if frame == page.main_frame else None)

        # 等待 iframe 出现（最多等 60 秒）
        iframe_locator = page.frame_locator("iframe").first

        # 获取 iframe 中的第一个 img 元素
        img_locator = iframe_locator.get_by_role("img").first

        # 获取 src 属性值
        src = await img_locator.get_attribute("src")
        print("[OK] 图片地址:", src)
        status_queue.put(src)

        try:
            # 等待 URL 变化或超时
            await asyncio.wait_for(url_changed_event.wait(), timeout=200)  # 最多等待 200 秒
            print("监听页面跳转成功")
        except asyncio.TimeoutError:
            status_queue.put("500")
            print("监听页面跳转超时")
            await page.close()
            await context.close()
            await browser.close()
            return None
        uuid_v1 = uuid.uuid1()
        print(f"UUID v1: {uuid_v1}")
        await context.storage_state(path=Path(BASE_DIR / "cookiesFile" / f"{uuid_v1}.json"))
        result = await check_cookie(2,f"{uuid_v1}.json")
        if not result:
            status_queue.put("500")
            await page.close()
            await context.close()
            await browser.close()
            return None
        await page.close()
        await context.close()
        await browser.close()

        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                                INSERT INTO user_info (type, filePath, userName, status)
                                VALUES (?, ?, ?, ?)
                                ''', (2, f"{uuid_v1}.json", id, 1))
            conn.commit()
            print("[OK] 用户状态已记录")
        status_queue.put("200")

# 快手登录
async def get_ks_cookie(id,status_queue):
    url_changed_event = asyncio.Event()
    async def on_url_change():
        # 检查是否是主框架的变化
        if page.url != original_url:
            url_changed_event.set()
    async with async_playwright() as playwright:
        options = {
            'args': [
                '--lang en-GB'
            ],
            'headless': False,  # Set headless option here
        }
        # Make sure to run headed.
        browser = await playwright.chromium.launch(**options)
        # Setup context however you like.
        context = await browser.new_context()  # Pass any options
        context = await set_init_script(context)
        # Pause the page, and start recording manually.
        page = await context.new_page()
        await page.goto("https://cp.kuaishou.com")

        # 定位并点击“立即登录”按钮（类型为 link）
        await page.get_by_role("link", name="立即登录").click()
        await page.get_by_text("扫码登录").click()
        img_locator = page.get_by_role("img", name="qrcode")
        # 获取 src 属性值
        src = await img_locator.get_attribute("src")
        original_url = page.url
        print("[OK] 图片地址:", src)
        status_queue.put(src)
        # 监听页面的 'framenavigated' 事件，只关注主框架的变化
        page.on('framenavigated',
                lambda frame: asyncio.create_task(on_url_change()) if frame == page.main_frame else None)

        try:
            # 等待 URL 变化或超时
            await asyncio.wait_for(url_changed_event.wait(), timeout=200)  # 最多等待 200 秒
            print("监听页面跳转成功")
        except asyncio.TimeoutError:
            status_queue.put("500")
            print("监听页面跳转超时")
            await page.close()
            await context.close()
            await browser.close()
            return None
        uuid_v1 = uuid.uuid1()
        print(f"UUID v1: {uuid_v1}")
        await context.storage_state(path=Path(BASE_DIR / "cookiesFile" / f"{uuid_v1}.json"))
        result = await check_cookie(4, f"{uuid_v1}.json")
        if not result:
            status_queue.put("500")
            await page.close()
            await context.close()
            await browser.close()
            return None
        await page.close()
        await context.close()
        await browser.close()

        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                                        INSERT INTO user_info (type, filePath, userName, status)
                                        VALUES (?, ?, ?, ?)
                                        ''', (4, f"{uuid_v1}.json", id, 1))
            conn.commit()
            print("[OK] 用户状态已记录")
        status_queue.put("200")

# 小红书登录
async def xiaohongshu_cookie_gen(id,status_queue):
    url_changed_event = asyncio.Event()

    async def on_url_change():
        # 检查是否是主框架的变化
        if page.url != original_url:
            url_changed_event.set()

    async with async_playwright() as playwright:
        options = {
            'args': [
                '--lang en-GB'
            ],
            'headless': False,  # Set headless option here
        }
        # Make sure to run headed.
        browser = await playwright.chromium.launch(**options)
        # Setup context however you like.
        context = await browser.new_context()  # Pass any options
        context = await set_init_script(context)
        # Pause the page, and start recording manually.
        page = await context.new_page()
        await page.goto("https://creator.xiaohongshu.com/")
        await page.locator('img.css-wemwzq').click()

        img_locator = page.get_by_role("img").nth(2)
        # 获取 src 属性值
        src = await img_locator.get_attribute("src")
        original_url = page.url
        print("[OK] 图片地址:", src)
        status_queue.put(src)
        # 监听页面的 'framenavigated' 事件，只关注主框架的变化
        page.on('framenavigated',
                lambda frame: asyncio.create_task(on_url_change()) if frame == page.main_frame else None)

        try:
            # 等待 URL 变化或超时
            await asyncio.wait_for(url_changed_event.wait(), timeout=200)  # 最多等待 200 秒
            print("监听页面跳转成功")
        except asyncio.TimeoutError:
            status_queue.put("500")
            print("监听页面跳转超时")
            await page.close()
            await context.close()
            await browser.close()
            return None
        uuid_v1 = uuid.uuid1()
        print(f"UUID v1: {uuid_v1}")
        await context.storage_state(path=Path(BASE_DIR / "cookiesFile" / f"{uuid_v1}.json"))
        result = await check_cookie(1, f"{uuid_v1}.json")
        if not result:
            status_queue.put("500")
            await page.close()
            await context.close()
            await browser.close()
            return None
        await page.close()
        await context.close()
        await browser.close()

        with sqlite3.connect(Path(BASE_DIR / "db" / "database.db")) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                           INSERT INTO user_info (type, filePath, userName, status)
                           VALUES (?, ?, ?, ?)
                           ''', (1, f"{uuid_v1}.json", id, 1))
            conn.commit()
            print("[OK] 用户状态已记录")
        status_queue.put("200")

# a = asyncio.run(xiaohongshu_cookie_gen(4,None))
# print(a)
