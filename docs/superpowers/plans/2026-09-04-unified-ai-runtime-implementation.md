# Sunbird OS 统一 AI Runtime 实施计划

日期：2026-09-04

对应设计：`docs/superpowers/specs/2026-09-04-unified-ai-runtime-design.md`

## 阶段 1：数据库与密钥基础

1. 在公共数据库初始化中增加 AI Provider、密钥、模型 Profile、Agent Profile、Run 和 Run Event 表。
2. 增加统一 SQLite 连接辅助，启用 foreign keys、WAL 和 busy timeout。
3. 实现跨平台主密钥后端和 AES-256-GCM `SecretStore`。
4. 增加数据库、加密和密钥不落明文测试。

## 阶段 2：数据库配置服务与兼容迁移

1. 新建 `backend_app/modules/ai_settings/` 的 repository 和 service。
2. 支持 Provider、Credential、Model Profile 和 Agent Profile 的 CRUD。
3. 实现 `settings.json` 到 SQLite 的幂等迁移。
4. 暂时向既有结构化调用提供数据库生成的 legacy settings 视图，避免一次性重写全部业务模块。
5. 将现有设置 API 改为数据库-backed，响应永不返回秘密。

## 阶段 3：Python Agent Runtime

1. 实现 Provider Adapter、Model Router、Structured Strategy 和 Tool Loop Strategy。
2. 实现 Agent Run 状态机、有界线程池、取消和启动恢复。
3. 实现 Tool Registry，并迁移现有四个 PI 工具为 Python 内部调用。
4. 增加 Runtime、回退规则、工具循环和任务恢复测试。

## 阶段 4：前端与 Electron 切换

1. 增加统一 Agent Run API。
2. AgentModels 页面继续使用兼容 API，但数据来源改为 SQLite。
3. BenchmarkManagement 改为创建后端 Tool Agent Run 并轮询状态。
4. 移除日常 PI 配置与 Prompt IPC；保留一次性密钥迁移桥接后再删除 sidecar。

## 阶段 5：验证与清理

1. 运行聚焦 pytest、全量相关测试和 Python 编译检查。
2. 构建 Vue 前端。
3. 检查数据库、API 和日志中不存在 API Key 明文。
4. 更新 README、架构图、时序图和数据流图。
5. Git 锁解除后按阶段创建 Conventional Commits。

## 实施约束

- 不覆盖工作区已有未提交改动。
- 不提交数据库、日志、密钥、构建产物或安装包。
- 测试只使用临时目录、Mock Provider 和内存主密钥后端。
- 任一迁移步骤失败时保留旧数据，不能留下半迁移状态。
