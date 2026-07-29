TEMPLATE_DEFINITIONS = {
    "knowledge": {
        "id": "knowledge",
        "name": "知识干货",
        "version": 1,
        "description": "前三秒强钩子、紧凑删停顿、黄白关键词字幕和信息型 B-roll。",
        "parameters": {
            "pace": "fast",
            "caption_density": "high",
            "broll_level": 2,
            "target_duration_seconds": 60,
            "color_grade": "neutral_punch",
            "music_style": "light_tech",
        },
    },
    "business": {
        "id": "business",
        "name": "商业观点",
        "version": 1,
        "description": "黑金视觉、克制节奏、金句卡片、数据图表和电影感调色。",
        "parameters": {
            "pace": "medium",
            "caption_density": "medium",
            "broll_level": 1,
            "target_duration_seconds": 90,
            "color_grade": "warm_cinematic",
            "music_style": "minimal_business",
        },
    },
}


def template_snapshot(template_id, overrides=None):
    source = TEMPLATE_DEFINITIONS[template_id]
    snapshot = {
        "id": source["id"],
        "name": source["name"],
        "version": source["version"],
        "description": source["description"],
        "parameters": dict(source["parameters"]),
    }
    allowed = set(snapshot["parameters"])
    for key, value in (overrides or {}).items():
        if key in allowed:
            snapshot["parameters"][key] = value
    snapshot["parameters"]["broll_level"] = max(
        0, min(3, int(snapshot["parameters"]["broll_level"]))
    )
    snapshot["parameters"]["target_duration_seconds"] = max(
        15, min(600, int(snapshot["parameters"]["target_duration_seconds"]))
    )
    return snapshot
