"""Candidate search tools shared by the internal Agent and MCP HTTP adapter."""
import re

from backend_app.common.tool_gateway import ToolExecutionError


SEARCH_TOOL_NAMES = ('search_benchmark_candidates', 'get_benchmark_search')


def register_candidate_search_tools(gateway, discovery, latest_cookie_file):
    def search_benchmark_candidates(keywords, limit=5, max_videos=10):
        values = re.split(r'[,，\n\r]+', keywords) if isinstance(keywords, str) else keywords
        keywords = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if not keywords or len(keywords) > 20 or any(len(value) > 100 for value in keywords):
            raise ValueError('请提供 1 到 20 个非空关键词，每个关键词不超过 100 字')
        task = discovery.start(keywords, limit, max_videos, latest_cookie_file())
        return {
            'task_id': task['id'], 'status': task['status'],
            'status_tool': 'get_benchmark_search', 'requires_manual_import': True,
            'message': '搜索候选与作品预览，不会自动加入对标库；请等待任务完成后查看候选。',
        }

    def get_benchmark_search(task_id, video_limit=5):
        task = discovery.get(task_id)
        if task is None:
            raise ToolExecutionError('SEARCH_TASK_NOT_FOUND', '搜索任务不存在', 404)
        return {
            'task_id': task['id'], 'status': task['status'], 'error': task.get('error'),
            'keywords': task['keywords'], 'summary': task['summary'],
            'requires_manual_import': True,
            'review_page': f"/#/benchmark-search?discovery_task_id={task['id']}",
            'candidates': [
                {**candidate, 'video_count_collected': len(candidate.get('videos') or []),
                 'videos': (candidate.get('videos') or [])[:video_limit],
                 'videos_truncated': len(candidate.get('videos') or []) > video_limit}
                for candidate in task['candidates']
            ],
        }

    gateway.register(
        'search_benchmark_candidates',
        '按关键词启动抖音对标候选搜索并读取作者作品预览。只返回异步任务 ID；使用 get_benchmark_search 查询。'
        '不自动入库、不做 AI 评分，也不能把标题预览当成已观看完整视频。',
        {
            'type': 'object', 'required': ['keywords'],
            'properties': {
                'keywords': {'oneOf': [
                    {'type': 'string', 'minLength': 1, 'maxLength': 2000},
                    {'type': 'array', 'minItems': 1, 'maxItems': 20,
                     'items': {'type': 'string', 'minLength': 1, 'maxLength': 100}},
                ]},
                'limit': {'type': 'integer', 'minimum': 1, 'maximum': 20, 'default': 5},
                'max_videos': {'type': 'integer', 'minimum': 1, 'maximum': 30, 'default': 10},
            },
        },
        search_benchmark_candidates, side_effect=True, effect_type='collect', entitlement='benchmarkCollect',
    )
    gateway.register(
        'get_benchmark_search',
        '查询对标候选任务的真实进度、失败原因和账号作品预览。queued/running 表示尚未结束；'
        '未完成时报告任务 ID 和进度，不要高频循环查询。候选 ready 后供用户审核，'
        '最终由用户在抖音搜索页面手动确认入库。点赞数据待核对。',
        {
            'type': 'object', 'required': ['task_id'],
            'properties': {
                'task_id': {'type': 'string', 'minLength': 1, 'maxLength': 128},
                'video_limit': {'type': 'integer', 'minimum': 0, 'maximum': 30, 'default': 5},
            },
        },
        get_benchmark_search,
    )
    return SEARCH_TOOL_NAMES
