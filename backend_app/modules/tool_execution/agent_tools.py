from backend_app.agent.tool_registry import ToolRegistry
from backend_app.modules.account_diagnosis import service as account_diagnosis_service
from backend_app.modules.benchmark import repository as benchmark_repository


def build_sunbird_tool_registry(db_path, start_content_search, gateway=None, extra_tool_names=()):
    registry = ToolRegistry(gateway)

    def search_douyin_content(keyword, targetCount=50):
        keyword = str(keyword or "").strip()
        if not keyword:
            raise ValueError("内容关键词不能为空")
        target_count = max(10, min(int(targetCount or 50), 100))
        return start_content_search(keyword, target_count)

    def list_benchmark_videos(keyword=None, limit=50):
        return benchmark_repository.list_all_videos(
            db_path,
            str(keyword or "").strip() or None,
            None,
            max(1, min(int(limit or 50), 200)),
        )

    def save_benchmark_analysis(
        videoId,
        summary,
        hook,
        core_viewpoint,
        pain_points,
        viral_points,
        reusable_points,
        script_suggestions,
    ):
        video_id = int(videoId)
        if not benchmark_repository.get_video(db_path, video_id):
            raise ValueError("作品不存在")
        required_text = {
            "summary": summary,
            "hook": hook,
            "core_viewpoint": core_viewpoint,
        }
        if any(not str(value or "").strip() for value in required_text.values()):
            raise ValueError("Agent 分析缺少必要文本字段")
        required_lists = [pain_points, viral_points, reusable_points, script_suggestions]
        if any(not isinstance(value, list) for value in required_lists):
            raise ValueError("Agent 分析数组字段格式错误")
        analysis = {
            **required_text,
            "pain_points": pain_points,
            "viral_points": viral_points,
            "reusable_points": reusable_points,
            "script_suggestions": script_suggestions,
            "analysis_type": "tool_agent",
        }
        return benchmark_repository.save_analysis(db_path, video_id, analysis)

    def get_account_diagnosis_facts(target_type, target_id):
        target_id = int(target_id)
        if target_type == "own":
            return account_diagnosis_service.build_own_facts_payload(db_path, target_id)
        if target_type == "benchmark":
            return account_diagnosis_service.build_benchmark_facts_payload(db_path, target_id)
        raise ValueError("target_type 只能是 own 或 benchmark")

    registry.register(
        "search_douyin_content",
        "按关键词创建抖音综合内容搜索任务。",
        {
            "type": "object",
            "required": ["keyword"],
            "properties": {
                "keyword": {"type": "string", "minLength": 1},
                "targetCount": {"type": "integer", "minimum": 10, "maximum": 100},
            },
        },
        search_douyin_content,
        side_effect=True, entitlement="benchmarkCollect", effect_type="collect",
    )
    registry.register(
        "list_benchmark_videos",
        "读取已经采集的对标作品，包含真实 video_url。展示作品时用 Markdown [作品标题](video_url)；id 是本地记录编号，不是抖音作品 ID。",
        {
            "type": "object",
            "properties": {
                "keyword": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200},
            },
        },
        list_benchmark_videos,
    )
    registry.register(
        "save_benchmark_analysis",
        "将 Agent 生成的结构化作品拆解保存到对标库。仅在完成可靠分析后调用。",
        {
            "type": "object",
            "required": [
                "videoId", "summary", "hook", "core_viewpoint", "pain_points",
                "viral_points", "reusable_points", "script_suggestions",
            ],
            "properties": {
                "videoId": {"type": "integer", "minimum": 1},
                "summary": {"type": "string"},
                "hook": {"type": "string"},
                "core_viewpoint": {"type": "string"},
                "pain_points": {"type": "array", "items": {"type": "string"}},
                "viral_points": {"type": "array", "items": {"type": "string"}},
                "reusable_points": {"type": "array", "items": {"type": "string"}},
                "script_suggestions": {"type": "array", "items": {"type": "string"}},
            },
        },
        save_benchmark_analysis,
        side_effect=True, entitlement="aiAnalysis",
    )
    registry.register(
        "get_account_diagnosis_facts",
        "读取后端已计算好的账号诊断事实卡。",
        {
            "type": "object",
            "required": ["target_type", "target_id"],
            "properties": {
                "target_type": {"type": "string", "enum": ["own", "benchmark"]},
                "target_id": {"type": "integer", "minimum": 1},
            },
        },
        get_account_diagnosis_facts,
    )
    for name in extra_tool_names:
        registry.expose(name)
    return registry
