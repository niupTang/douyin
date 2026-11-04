"""
GitHub Trending 采集脚本
每天跑一次，产出 raw JSON 数据，供后续分析使用

用法：
  python scripts/github_trending_scraper.py
  python scripts/github_trending_scraper.py --since weekly  # 周榜
  python scripts/github_trending_scraper.py --output E:/Obsidian/GitHub开源项目库/日榜/raw/

输出：
  - raw_YYYY-MM-DD.json：原始项目列表
  - 终端打印格式化的项目摘要
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.parse import quote

BEIJING_TZ = timezone(timedelta(hours=8))

def fetch_trending(since="daily", language=""):
    """从 GitHub Trending 页面抓取项目列表"""
    url = f"https://github.com/trending/{language}?since={since}"
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
    })
    resp = urlopen(req, timeout=30)
    html = resp.read().decode("utf-8", errors="ignore")
    return html


def parse_trending(html):
    """从 HTML 中解析出项目列表"""
    projects = []

    # 匹配每个项目 article
    # GitHub Trending 页面结构：<article class="Box-row"> ... </article>
    articles = re.findall(
        r'<article class="Box-row[^"]*"[^>]*>(.*?)</article>',
        html,
        re.DOTALL,
    )

    for article in articles:
        proj = {}

        # 项目名 owner/repo
        name_match = re.search(
            r'href="/trending[^"]*"[^>]*>\s*<span[^>]*>.*?</span>\s*(.*?)</a>',
            article,
            re.DOTALL,
        )
        if not name_match:
            name_match = re.search(
                r'href="/([^/"]+/[^/"]+?)"[^>]*class="[^"]*text-bold[^"]*"',
                article,
                re.DOTALL,
            )
        if not name_match:
            name_match = re.search(r'href="/([^/"]+/[^/"]+?)"[^>]*>', article)
        if name_match:
            proj["name"] = name_match.group(1).strip()

        # 描述
        desc_match = re.search(
            r'<p class="col-9[^"]*"[^>]*>\s*(.*?)\s*</p>', article, re.DOTALL
        )
        if desc_match:
            proj["description"] = re.sub(r"<[^>]+>", "", desc_match.group(1)).strip()

        # 编程语言
        lang_match = re.search(
            r'<span[^>]*itemprop="programmingLanguage"[^>]*>(.*?)</span>',
            article,
            re.DOTALL,
        )
        if lang_match:
            proj["language"] = lang_match.group(1).strip()

        # 今日 stars
        stars_match = re.search(
            r'class="d-inline-block float-sm-right"[^>]*>([\d,]+)\s*stars\s*today',
            article,
        )
        if stars_match:
            proj["stars_today"] = int(stars_match.group(1).replace(",", ""))

        # 总 stars（可选，有些页面有有些没有）
        total_stars_match = re.search(
            r'class="[^"]*css-truncate[^"]*"[^>]*>\s*([\d,]+)\s*</a>',
            article,
        )
        if total_stars_match:
            try:
                proj["total_stars"] = int(total_stars_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # 项目链接
        proj["url"] = f"https://github.com/{proj.get('name', '')}"
        proj["repo"] = proj.get("name", "")

        if proj.get("name"):
            projects.append(proj)

    return projects


def fetch_repo_details(repo_name):
    """用 GitHub API 补充项目详情"""
    # 注意：未认证的 API 每小时只有 60 次请求
    # 建议设置 GITHUB_TOKEN 环境变量来提高限额
    token = os.environ.get("GITHUB_TOKEN", "")
    url = f"https://api.github.com/repos/{repo_name}"

    req = Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "github-trending-scraper")
    if token:
        req.add_header("Authorization", f"token {token}")

    try:
        resp = urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("utf-8"))
        return {
            "total_stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "language": data.get("language", ""),
            "topics": data.get("topics", []),
            "license": data.get("license", {}).get("spdx_id", "") if data.get("license") else "",
            "pushed_at": data.get("pushed_at", ""),
            "description": data.get("description", ""),
        }
    except Exception as e:
        return {"error": str(e)}


def is_ai_related(project):
    """判断项目是否与 AI 相关"""
    ai_keywords = [
        "ai", "llm", "rag", "agent", "gpt", "claude", "codex", "copilot",
        "openai", "anthropic", "deepseek", "qwen", "kimi", "llama",
        "machine learning", "deep learning", "neural", "transformer",
        "embedding", "vector", "tensor", "pytorch", "tensorflow",
        "chatbot", "prompt", "fine-tun", "inference", "generat",
        "recommend", "predict", "nlp", "vision", "speech",
        "mcp", "acl", "coding agent", "autonomous",
    ]
    text = json.dumps(project).lower()
    for kw in ai_keywords:
        if kw.lower() in text:
            return True
    return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="GitHub Trending 采集脚本")
    parser.add_argument("--since", default="daily", choices=["daily", "weekly", "monthly"])
    parser.add_argument("--language", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--ai-only", action="store_true", help="只输出 AI 相关项目")
    args = parser.parse_args()

    now = datetime.now(BEIJING_TZ)
    date_str = now.strftime("%Y-%m-%d")

    print(f"🔄 正在采集 GitHub Trending ({args.since})...")
    html = fetch_trending(args.since, args.language)
    projects = parse_trending(html)

    print(f"✅ 采集到 {len(projects)} 个项目")

    # 尝试用 API 补充详情（每天可选）
    # 为节省 API 配额，只补充总 stars 为 0 或没有总 stars 的项目
    for i, proj in enumerate(projects):
        if "total_stars" not in proj or proj.get("total_stars", 0) == 0:
            time.sleep(0.1)  # 避免 API 限流
            details = fetch_repo_details(proj.get("name", ""))
            if "error" not in details:
                proj.update(details)

    # 标记 AI 相关性
    for proj in projects:
        proj["ai_related"] = is_ai_related(proj)

    # 输出
    if args.ai_only:
        ai_projects = [p for p in projects if p.get("ai_related")]
        print(f"\n🧠 AI 相关项目: {len(ai_projects)}")
        for p in ai_projects:
            print(f"  {p.get('name')} ⭐{p.get('stars_today', '?')}/day")
        projects = ai_projects

    # 保存 raw 数据
    if args.output:
        os.makedirs(args.output, exist_ok=True)
        raw_path = os.path.join(args.output, f"raw_{date_str}.json")
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(projects, f, ensure_ascii=False, indent=2)
        print(f"\n📁 已保存 raw 数据: {raw_path}")

    # 打印摘要
    print(f"\n{'='*60}")
    print(f"📊 GitHub Trending {date_str} ({args.since}) — 摘要")
    print(f"{'='*60}")
    for i, p in enumerate(projects[:20], 1):
        ai_tag = "🧠 " if p.get("ai_related") else "   "
        stars = p.get("stars_today", "?")
        lang = p.get("language", "?")
        desc = (p.get("description") or "")[:80]
        print(f"{ai_tag}{i:2d}. {p.get('name'):35s} ⭐{str(stars):>6s}  {lang:12s}  {desc}")
    print(f"{'='*60}")

    return projects


if __name__ == "__main__":
    main()
