TOOL_DEFINITIONS = [
    {
        "name": "collect_douyin_account",
        "description": "采集抖音对标账号资料和前 N 条作品。",
        "input_schema": {
            "type": "object",
            "required": ["homepage_url"],
            "properties": {
                "homepage_url": {"type": "string"},
                "max_videos": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
            },
        },
    },
    {
        "name": "list_benchmark_videos",
        "description": "分页查询对标作品池。",
        "input_schema": {
            "type": "object",
            "required": ["account_id"],
            "properties": {
                "account_id": {"type": "integer"},
                "page": {"type": "integer", "minimum": 1, "default": 1},
                "page_size": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
        },
    },
    {
        "name": "analyze_benchmark_video",
        "description": "对单条对标作品做简单爆款拆解。",
        "input_schema": {
            "type": "object",
            "required": ["video_id"],
            "properties": {
                "video_id": {"type": "integer"},
                "force": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "run_idea_radar",
        "description": "根据筛选条件生成观点雷达。",
        "input_schema": {
            "type": "object",
            "required": ["video_id"],
            "properties": {
                "video_id": {"type": "integer"},
                "target_direction": {"type": "string", "default": "AI 生产系统研究员"},
                "force": {"type": "boolean", "default": False},
                "force_transcription": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "generate_my_script",
        "description": "根据身份定位和观点雷达生成完整口播文案。",
        "input_schema": {
            "type": "object",
            "required": ["identity_profile", "radar_result"],
            "properties": {
                "identity_profile": {"type": "object"},
                "radar_result": {"type": "object"},
                "benchmark_analysis": {"type": "object"},
            },
        },
    },
    {
        "name": "review_published_content",
        "description": "对已发布作品数据做 AI 复盘。",
        "input_schema": {
            "type": "object",
            "properties": {
                "work_id": {"type": "integer"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
            },
        },
    },
    {
        "name": "publish_video",
        "description": "调用发布链路发布作品。",
        "input_schema": {
            "type": "object",
            "required": ["platform_type", "file_list", "account_list", "title"],
            "properties": {
                "platform_type": {"type": "integer"},
                "file_list": {"type": "array", "items": {"type": "string"}},
                "account_list": {"type": "array", "items": {"type": "string"}},
                "title": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "thumbnail_path": {"type": "string"},
            },
        },
    },
]


def describe_tools():
    return [dict(tool) for tool in TOOL_DEFINITIONS]


def create_tool_handlers(services):
    return {
        "collect_douyin_account": lambda args: services["collect_douyin_account"](
            args["homepage_url"], max_videos=args.get("max_videos", 20)
        ),
        "list_benchmark_videos": lambda args: services["list_benchmark_videos"](
            args["account_id"], page=args.get("page", 1), page_size=args.get("page_size", 20)
        ),
        "analyze_benchmark_video": lambda args: services["analyze_benchmark_video"](
            args["video_id"], force=bool(args.get("force"))
        ),
        "run_idea_radar": lambda args: services["run_idea_radar"](
            args["video_id"],
            target_direction=args.get("target_direction") or "AI 生产系统研究员",
            force=bool(args.get("force")),
            force_transcription=bool(args.get("force_transcription")),
        ),
        "generate_my_script": lambda args: services["generate_my_script"](
            args["identity_profile"],
            args["radar_result"],
            args.get("benchmark_analysis") or {},
        ),
        "review_published_content": lambda args: services["review_published_content"](
            work_id=args.get("work_id"),
            limit=args.get("limit", 50),
        ),
        "publish_video": lambda args: services["publish_video"](
            platform_type=args["platform_type"],
            file_list=args["file_list"],
            account_list=args["account_list"],
            title=args["title"],
            tags=args.get("tags") or [],
            thumbnail_path=args.get("thumbnail_path"),
        ),
    }
