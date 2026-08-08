import json


def build_video_analysis_prompt(video, source_text, raw_data=None):
    payload = {
        "video_id": video.get("id"),
        "video_url": video.get("video_url"),
        "title": video.get("title"),
        "cover_url": video.get("cover_url"),
        "like_count": video.get("like_count"),
        "comment_count": video.get("comment_count"),
        "share_count": video.get("share_count"),
        "collect_count": video.get("collect_count"),
        "source_text": source_text,
        "raw_data": raw_data or {},
    }
    return f"""
你是一个中文自媒体对标账号分析师。请基于下面这条抖音作品的同步数据，分析它为什么值得对标，以及普通内容创作者如何复刻。

要求：
1. 只根据输入数据分析，不要编造不存在的评论、完播率、转化率或视频画面细节。
2. 如果信息不足，请明确写成“基于标题/文案判断”。
3. 输出必须是一个 JSON 对象，不要输出 Markdown，不要解释，不要包裹代码块。
4. 所有数组字段都输出 3 到 5 条，语言要适合直接展示在后台页面。
5. hook 不要返回纯数字、点赞数或播放量；必须是作品的开头钩子/标题钩子。

JSON 字段：
- summary: 一句话总结这个作品的内容类型和对标价值
- hook: 开头钩子
- core_viewpoint: 核心观点
- pain_points: 人群痛点数组
- viral_points: 爆点分析数组
- reusable_points: 可复刻点数组
- script_suggestions: 脚本复刻建议数组
- keywords: 关键词数组
- structure: 内容结构数组，每项包含 label 和 content

作品数据：
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()
