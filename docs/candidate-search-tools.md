# AI 找对标工具调用

CDP 元素检查技能在 E:\codex-skills\cdp-page-inspection\SKILL.md。
本工具是项目中的业务方法，不依赖 Codex skill 安装才能运行。

工具实现位于 backend_app/modules/tool_execution/search_tools.py，执行经过统一工具网关。
页面、Agent 和 MCP HTTP 接口共享同一个 CandidateDiscovery 实例及数据库任务，不会各自新建后台任务管理器。

## 发起搜索

POST http://localhost:5409/mcp/invoke

使用当前有效的 Authorization: Bearer 访问令牌，不要把真实令牌写进文档或日志。

```json
{
  "name": "search_benchmark_candidates",
  "arguments": {
    "keywords": ["Codex 实战", "AI 自动化"],
    "limit": 5,
    "max_videos": 10
  }
}
```

keywords 也支持逗号或换行分隔的字符串。搜索要求 benchmarkCollect 授权。
成功响应的 data 包含 task_id、status、status_tool 和 requires_manual_import。
任务异步执行，工具返回并不代表搜索已完成；不应高频轮询消耗模型额度。

## 查询真实进度与候选

```json
{
  "name": "get_benchmark_search",
  "arguments": {
    "task_id": "上一步返回的任务ID",
    "video_limit": 5
  }
}
```

返回任务状态、错误、候选账号和作品预览。每个候选包含完整已采集数量与 videos_truncated 标记。
review_page 提供带 discovery_task_id 的前端路由；在应用前端打开可查看该任务。
不存在的任务返回 SEARCH_TASK_NOT_FOUND 和 HTTP 404。

## 内部 Python 调用

已有应用上下文中的 AgentRuntime 直接使用同一网关，无需通过 HTTP 回调自身：

```python
result = tool_execution_gateway.execute(
    "search_benchmark_candidates",
    {"keywords": ["Codex 实战"], "limit": 5, "max_videos": 10},
)
```

不要为单次调用另建 CandidateDiscovery；复用应用装配后的实例。

## 行为边界

这两个工具只搜索并读取作品预览，不做 AI 自动评分，不观看完整视频，也不自动入库。
入库仍由用户在候选页面点击确认，未向模型暴露候选入库工具。
现有 /mcp/invoke 是项目 HTTP 工具适配层，尚不是标准 MCP 协议服务端。
