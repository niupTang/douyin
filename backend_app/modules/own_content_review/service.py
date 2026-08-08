def _metric(video, key):
    try:
        return float(video.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def _pick_top(videos, key):
    if not videos:
        return None
    item = max(videos, key=lambda row: _metric(row, key))
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "value": _metric(item, key),
        "video_url": item.get("video_url"),
        "content_format": item.get("content_format"),
    }


def _format_counts(videos):
    counts = {}
    for item in videos:
        name = item.get("content_format") or "unknown"
        counts[name] = counts.get(name, 0) + 1
    return counts


def review_published_content(videos):
    videos = list(videos or [])
    total = len(videos)
    total_play = sum(_metric(item, "play_count") for item in videos)
    total_like = sum(_metric(item, "like_count") for item in videos)
    avg_play = round(total_play / total, 2) if total else 0
    avg_like_rate = round(total_like / total_play, 4) if total_play else 0
    top_play = _pick_top(videos, "play_count")
    top_like = _pick_top(videos, "like_count")
    top_completion = _pick_top(videos, "completion_rate")

    suggestions = []
    if top_play:
        suggestions.append(f"复用《{top_play['title']}》的选题角度，优先放大同类开头和标题结构。")
    if top_completion and top_completion["value"] > 0:
        suggestions.append(f"把《{top_completion['title']}》的节奏作为口播脚本模板，保留高完播段落密度。")
    if avg_like_rate:
        suggestions.append("后续复盘重点看播放到点赞的转化，低转化作品优先重写观点钩子。")
    if not suggestions:
        suggestions.append("先补齐播放、点赞、完播等数据，再进行稳定复盘。")

    return {
        "summary": {
            "total": total,
            "total_play_count": int(total_play),
            "total_like_count": int(total_like),
            "avg_play_count": avg_play,
            "avg_like_rate": avg_like_rate,
            "content_format_counts": _format_counts(videos),
        },
        "winners": {
            "by_play_count": top_play,
            "by_like_count": top_like,
            "by_completion_rate": top_completion,
        },
        "suggestions": suggestions,
        "videos": videos,
    }
