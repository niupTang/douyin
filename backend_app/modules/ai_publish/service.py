def publish_video(payload, *, validate_accounts, publishers, save_record):
    file_list = payload.get("fileList") or payload.get("file_list") or []
    account_list = payload.get("accountList") or payload.get("account_list") or []
    platform_type = payload.get("type") or payload.get("platform_type")
    title = payload.get("title")
    tags = payload.get("tags") or []
    category = payload.get("category")
    if category == 0:
        category = None
    enable_timer = payload.get("enableTimer") if "enableTimer" in payload else payload.get("enable_timer")
    videos_per_day = payload.get("videosPerDay") or payload.get("videos_per_day")
    daily_times = payload.get("dailyTimes") or payload.get("daily_times")
    start_days = payload.get("startDays") if "startDays" in payload else payload.get("start_days")
    thumbnail_path = payload.get("thumbnailPath") or payload.get("thumbnail_path")

    try:
        validate_accounts(platform_type, account_list)
        publisher = publishers.get(int(platform_type))
        if not publisher:
            raise ValueError(f"Unsupported platform type: {platform_type}")
        if int(platform_type) == 3:
            publisher(title, file_list, tags, account_list, category, enable_timer,
                      videos_per_day, daily_times, start_days, thumbnail_path)
        else:
            publisher(title, file_list, tags, account_list, category, enable_timer,
                      videos_per_day, daily_times, start_days)
        record_id = save_record(platform_type, title, tags, file_list, account_list, "success")
        return {"record_id": record_id, "status": "success"}
    except Exception as exc:
        record_id = save_record(platform_type, title, tags, file_list, account_list, "failed", str(exc))
        raise RuntimeError(str(exc)) from exc
