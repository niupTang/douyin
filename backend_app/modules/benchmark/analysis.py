import json
import re

from backend_app.agent.structured_runner import load_json_object as agent_load_json_object

from .prompts import build_video_analysis_prompt
from .schemas import video_analysis_schema


def split_title_parts(title):
    text = re.sub(r"\s+", " ", title or "").strip()
    if not text:
        return []
    parts = re.split(r"[，。！？!?；;\n\r]+", text)
    return [part.strip() for part in parts if part.strip()]


def is_count_like_text(value):
    text = re.sub(r"\s+", " ", value or "").strip()
    return bool(re.fullmatch(r"[\d.,]+\s*[万wW]?", text))


def pick_analysis_source_text(video):
    raw_data = {}
    try:
        raw_data = json.loads(video.get("raw_data") or "{}")
    except Exception:
        raw_data = {}
    candidates = [
        video.get("title"),
        raw_data.get("title"),
        raw_data.get("raw_text"),
        raw_data.get("text"),
    ]
    for value in candidates:
        text = re.sub(r"\s+", " ", value or "").strip()
        if text and not is_count_like_text(text) and not text.startswith("热门"):
            return text
    return "该作品暂未同步到标题/文案"


def is_douyin_analysis_stale(analysis, video):
    if not analysis:
        return False
    parsed = parse_douyin_video_analysis(analysis)
    hook = parsed.get("hook") or ""
    summary = parsed.get("summary") or ""
    if is_count_like_text(hook):
        return True
    if re.search(r"围绕「[\d.,]+\s*[万wW]?」", summary):
        return True
    source_text = pick_analysis_source_text(video)
    return source_text != "该作品暂未同步到标题/文案" and hook and hook not in source_text


def pick_keywords(text):
    candidates = [
        "AI", "智能体", "Agent", "Coze", "Obsidian", "Hermes", "Claude", "抖音", "视频号",
        "副业", "自媒体", "知识库", "工作流", "私域", "变现", "获客", "剪辑", "口播",
        "爆款", "账号", "流量", "工具", "教程", "开源", "成本", "模型", "算力", "提示词"
    ]
    found = []
    lower_text = (text or "").lower()
    for word in candidates:
        if word.lower() in lower_text and word not in found:
            found.append(word)
    hashtags = re.findall(r"#([^#\s，。！？!?,;；]+)", text or "")
    for tag in hashtags:
        if tag and tag not in found:
            found.append(tag)
    return found[:8]


def generate_douyin_video_analysis_fallback(video):
    source_text = pick_analysis_source_text(video)
    parts = split_title_parts(source_text)
    keywords = pick_keywords(source_text)
    hook = parts[0] if parts else source_text[:40]
    core = parts[1] if len(parts) > 1 else f"围绕「{hook}」展开观点，用具体问题吸引目标用户继续看。"
    pain_points = [
        "观众可能正在寻找更高效的方法或工具",
        "观众需要把抽象概念变成可执行步骤",
    ]
    if any(word in source_text for word in ["成本", "价格", "便宜", "贵"]):
        pain_points.insert(0, "用户关心成本下降后自己能抓住什么机会")
    if any(word in source_text for word in ["学", "教程", "入门", "路径"]):
        pain_points.insert(0, "用户想知道从哪里开始学、按什么路径学")

    viral_points = [
        "选题有明确对象和具体问题，适合做开头钩子",
        "可以拆成短句字幕和重点弹窗，降低理解成本",
    ]
    if keywords:
        viral_points.append(f"关键词可前置：{' / '.join(keywords[:4])}")

    reusable_points = [
        "用“现象 -> 原因 -> 普通人行动”的结构复刻",
        "保留一个具体例子，再给出三条可执行路径",
        "结尾用清单式行动建议，引导收藏或评论",
    ]
    script_suggestions = [
        f"开头：最近我看到一个信号，{hook}",
        "中段：这件事真正影响普通人的地方，不是新闻本身，而是成本和门槛变化",
        "结尾：如果你也想跟上，可以先从一个工具、一个教程、一个项目开始练",
    ]

    analysis = {
        "basis": "metadata",
        "keywords": keywords,
        "structure": [
            {"label": "开头钩子", "content": hook},
            {"label": "核心观点", "content": core},
            {"label": "论证/案例", "content": "用行业变化、工具案例或个人体验证明观点。"},
            {"label": "行动引导", "content": "给出可执行路径，让用户知道下一步做什么。"},
        ],
        "pain_points": pain_points[:4],
        "viral_points": viral_points[:4],
        "reusable_points": reusable_points,
        "script_suggestions": script_suggestions,
    }

    return {
        "analysis_type": "metadata",
        "summary": f"这是一个围绕「{hook}」展开的知识分享选题，适合复刻为观点口播或教程切片。",
        "hook": hook,
        "core_viewpoint": core,
        "pain_points": pain_points[:4],
        "viral_points": viral_points[:4],
        "reusable_points": reusable_points,
        "script_suggestions": script_suggestions,
        "raw_analysis": analysis,
    }


def build_douyin_analysis_prompt(video):
    raw_data = {}
    try:
        raw_data = json.loads(video.get("raw_data") or "{}")
    except Exception:
        raw_data = {}
    return build_video_analysis_prompt(video, pick_analysis_source_text(video), raw_data)


def get_codex_analysis_schema():
    return video_analysis_schema()


def load_json_object(text):
    return agent_load_json_object(text)


def normalize_text_list(value, limit=5):
    if isinstance(value, list):
        items = value
    elif isinstance(value, str) and value.strip():
        items = re.split(r"[\n；;]+", value)
    else:
        items = []
    result = []
    for item in items:
        text = re.sub(r"\s+", " ", str(item)).strip()
        if text and text not in result:
            result.append(text)
    return result[:limit]


def normalize_codex_video_analysis(video, codex_data):
    source_text = pick_analysis_source_text(video)
    hook = re.sub(r"\s+", " ", str(codex_data.get("hook") or "")).strip()
    if not hook or is_count_like_text(hook):
        parts = split_title_parts(source_text)
        hook = parts[0] if parts else source_text[:40]

    raw_analysis = {
        "basis": "codex_cli",
        "keywords": normalize_text_list(codex_data.get("keywords"), 8),
        "structure": codex_data.get("structure") or [],
        "source_text": source_text,
    }
    return {
        "analysis_type": "codex_cli",
        "summary": re.sub(r"\s+", " ", str(codex_data.get("summary") or "")).strip(),
        "hook": hook,
        "core_viewpoint": re.sub(r"\s+", " ", str(codex_data.get("core_viewpoint") or "")).strip(),
        "pain_points": normalize_text_list(codex_data.get("pain_points"), 5),
        "viral_points": normalize_text_list(codex_data.get("viral_points"), 5),
        "reusable_points": normalize_text_list(codex_data.get("reusable_points"), 5),
        "script_suggestions": normalize_text_list(codex_data.get("script_suggestions"), 5),
        "raw_analysis": raw_analysis,
    }


def parse_douyin_video_analysis(row):
    if not row:
        return None
    item = dict(row)
    for key in ("pain_points", "viral_points", "reusable_points", "script_suggestions"):
        try:
            item[key] = json.loads(item.get(key) or "[]")
        except Exception:
            item[key] = []
    try:
        item["raw_analysis"] = json.loads(item.get("raw_analysis") or "{}")
    except Exception:
        item["raw_analysis"] = {}
    return item
