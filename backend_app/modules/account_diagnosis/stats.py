import re
import statistics


def parse_count(value):
    """把 '1.2万' / '86,000' / 86000 / '3.5w' 统一转成 int。"""
    text = re.sub(r"\s+", "", str(value or "")).replace(",", "")
    if not text:
        return 0
    match = re.search(r"([\d.]+)", text)
    if not match:
        return 0
    number = float(match.group(1))
    if "万" in text or "w" in text.lower():
        number *= 10000
    return int(number)


def _num(value):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _median(values):
    values = [v for v in values if v is not None]
    return round(statistics.median(values), 4) if values else None


def _mean(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 4) if values else None


def _video_like(video):
    value = video.get("like_count_value")
    if value:
        return parse_count(value)
    return parse_count(video.get("like_count"))


def _like_rate(like, play):
    if not play:
        return None
    return round(like / play, 4)


def _classify_benchmark(deviation_x, like_rate):
    if deviation_x is None:
        return "数据不足"
    if deviation_x >= 5:
        return "爆款"
    if deviation_x >= 2:
        return "表现突出（半爆）"
    if deviation_x >= 0.5:
        return "粉丝基数正常发挥"
    return "低于自身基线"


# ---------------------------------------------------------------- 自有账号

def build_own_facts(own_videos, publish_records, account=None):
    plays = [_num(v.get("play_count")) for v in own_videos]
    plays = [p for p in plays if p is not None]
    two_sec = [_num(v.get("two_sec_bounce_rate")) for v in own_videos]
    two_sec = [t for t in two_sec if t is not None]
    completion = [_num(v.get("completion_rate")) for v in own_videos]
    completion = [c for c in completion if c is not None]

    ranked = sorted(
        own_videos,
        key=lambda v: (_num(v.get("play_count")) or 0),
        reverse=True,
    )
    play_median = _median(plays)
    low_threshold = (play_median or 0) * 0.5
    low_play = [v for v in own_videos if (_num(v.get("play_count")) or 0) < low_threshold]

    def _brief(v):
        return {
            "id": v.get("id"),
            "title": v.get("title"),
            "play_count": _num(v.get("play_count")) or 0,
            "two_sec_bounce_rate": _num(v.get("two_sec_bounce_rate")),
            "completion_rate": _num(v.get("completion_rate")),
            "like_count": _num(v.get("like_count")) or 0,
            "published_at": v.get("published_at"),
        }

    publish_views = [_num(r.get("views")) for r in publish_records]
    publish_views = [p for p in publish_views if p is not None]
    publish_success = sum(1 for r in publish_records if r.get("status") == "success")
    publish_failed = len(publish_records) - publish_success

    # 四层诊断信号（只给确定性事实，结论交给 LLM 解释）
    signals = {
        "has_play": bool(plays),
        "has_two_sec": bool(two_sec),
        "has_completion": bool(completion),
        "two_sec_bounce_median": _median(two_sec),
        "completion_median": _median(completion),
        "play_median": play_median,
        "play_mean": _mean(plays),
        "play_max": max(plays) if plays else None,
        "play_min": min(plays) if plays else None,
        "low_play_count": len(low_play),
    }

    return {
        "account": {
            "id": (account or {}).get("id"),
            "userName": (account or {}).get("userName"),
            "follower_count": parse_count((account or {}).get("follower_count")),
        },
        "own_videos": {
            "count": len(own_videos),
            "signals": signals,
            "top_by_play": [_brief(v) for v in ranked[:5]],
            "low_by_play": [_brief(v) for v in low_play[:10]],
        },
        "publish_records": {
            "count": len(publish_records),
            "success_count": publish_success,
            "failed_count": publish_failed,
            "views_total": int(sum(publish_views)) if publish_views else 0,
            "views_median": _median(publish_views),
        },
    }


# ---------------------------------------------------------------- 对标账号

def build_benchmark_facts(account, videos):
    followers = parse_count((account or {}).get("followers_count"))
    likes = [_video_like(v) for v in videos]
    likes = [n for n in likes if n > 0]
    like_median = _median(likes)
    like_mean = _mean(likes)
    like_max = max(likes) if likes else 0

    rows = []
    for v in videos:
        like = _video_like(v)
        rate = round(like / followers, 4) if followers else None
        deviation = round(like / like_median, 2) if like_median else None
        rows.append({
            "id": v.get("id"),
            "title": v.get("title"),
            "video_url": v.get("video_url"),
            "like": like,
            "comment": parse_count(v.get("comment_count")),
            "share": parse_count(v.get("share_count")),
            "collect": parse_count(v.get("collect_count")),
            "like_rate": rate,
            "deviation_x": deviation,
            "classification": _classify_benchmark(deviation, rate),
        })

    rows.sort(key=lambda r: (r["deviation_x"] is not None, r["deviation_x"] or 0), reverse=True)

    return {
        "account": {
            "id": (account or {}).get("id"),
            "nickname": (account or {}).get("nickname"),
            "followers": followers,
            "video_count": len(videos),
            "last_sync_at": (account or {}).get("last_sync_at"),
        },
        "engagement": {
            "like_median": like_median,
            "like_mean": like_mean,
            "like_max": like_max,
            "sample_size": len(likes),
        },
        "videos": rows,
    }
