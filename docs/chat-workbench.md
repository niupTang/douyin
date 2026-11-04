# 聊天工作台

首页 `/#/` 为聊天工作台，原增长总览迁移到 `/#/overview`，已有业务页面继续保留。

- 会话和消息存入当前 SQLite/SQLCipher 数据库的 `chat_conversations`、`chat_messages` 表；浏览器只保存最近会话 ID。
- 对话复用 Agent 模型页面的 `piOperations` 配置和 Agent Runtime；每轮带入最近历史，显示工具执行事件，支持停止 Agent 任务。
- `query_workbench_data` 查询账号、对标账号、素材、发布记录，固定 SQL 和字段，不向模型返回 Cookie 文件路径或原始载荷。
- `sync_benchmark_account` 按账号 ID 经统一工具网关调用现有对标同步；不把发布工具暴露给聊天 Agent。
- 选择本地视频后上传到素材库，并在聊天中显示记录。视频文件仍保存在 `videoFile` 中，不受数据库文件加密保护。
- 发布卡选择平台、账号、素材、标题、话题，用户点击确认后，后台异步执行原发布链路。后端按 ID 解析真实账号/文件，验证同平台、登录状态、视频存在及目录范围，并经过工具网关授权和审计。
- 发布请求 ID 保证同一请求重试不重复发布。后端重启将未完成发布标记为中断并提示核对发布记录，不自动重试。

聊天 API 位于 `/api/chat`，受现有登录鉴权保护。新增表在后端启动时自动创建。模型配置缺失、工具失败、连接中断会显示错误或状态，不生成虚假成功结果。

验证：`npm run frontend:build`，`pytest tests/test_chat_workbench.py`。真实上传发布不作为自动测试执行。
