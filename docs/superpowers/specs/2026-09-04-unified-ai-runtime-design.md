# Sunbird OS 统一 AI 服务层与内置 Agent Runtime 设计

日期：2026-09-04

状态：待用户审阅

## 1. 背景

当前项目存在两条 AI 调用链：

1. 普通结构化分析由 Vue 调用 Flask，Flask 读取 `settings.json` 中的 Hermes 和模型配置，再调用 Hermes Gateway。
2. PI Agent 由 Vue 通过 Electron IPC 调用 `pi-agent-sidecar.mjs`，Electron 从 `pi-agent-settings.json` 解密 DeepSeek 密钥，再由 Node sidecar 执行模型和工具循环。

此外，Codex CLI 结构化分析仍从 `settings.json` 读取可执行文件、模型和超时配置。当前设计导致配置、密钥、错误处理、任务状态和日志分散在 Python、Electron 和 Node sidecar 三处。

## 2. 已确认目标

- 所有持久化业务数据、AI 配置和 Agent 运行状态统一由 SQLite 管理。
- API Key 等秘密信息只以密文形式进入 SQLite，不允许明文写入数据库、JSON、日志或 API 响应。
- 预留 Windows、macOS 和 Linux 跨平台系统安全存储适配。
- 普通结构化 Agent 和工具型 Agent 共用一个 Python AI 服务层。
- 不强制不同 Agent 使用同一个模型；它们可以选择不同 Provider、模型参数和备用模型。
- Agent Runtime 内置在 Python 后端，Vue 不直接调用模型、Electron IPC 或 Node sidecar。
- Electron 只负责桌面生命周期和操作系统级桌面能力。
- 运行日志继续按既有决定写入 `<运行数据目录>/logs/backend.json`，不写入 SQLite；SQLite 保存结构化任务事件和业务结果。

## 3. 非目标

- 本期不拆分微服务，不引入 Redis、Celery、Kafka 或云端任务队列。
- 本期不把后台运行日志迁入 SQLite。
- 本期不实现跨设备同步 API Key。数据库复制到新设备后，用户必须重新输入秘密信息。
- 本期不重构所有既有业务仓储，只要求新增 AI 配置和 Agent 运行模块使用统一数据库连接与迁移机制。

## 4. 方案比较

### 方案 A：Electron/Node Agent Runtime

所有 Agent 继续运行在 Electron sidecar，Python 只提供数据 API。它可以最大限度复用现有 PI Agent 依赖，但后端能力仍被 Electron 生命周期绑定，工具需要通过 HTTP 绕回 Flask，配置、日志和测试边界继续分裂。

### 方案 B：Python 内置统一 Agent Runtime（采用）

Flask 后端内置统一 Runtime，结构化分析与工具循环只是两种执行策略。模型、密钥、任务、事件和工具调用都由 Python 负责。Electron 不再读取或传递模型密钥。

该方案最符合当前模块化单体结构，能够直接调用领域 service/repository，并满足统一配置、统一错误处理和前端不直连 Agent Runtime 的要求。

### 方案 C：独立 Agent 服务

把 Runtime 拆成独立本地进程或云服务。该方案适合多用户或大规模并发，但对当前单机桌面项目增加了部署、鉴权、进程管理和可观测性成本，因此本期不采用。

## 5. 目标架构

```text
Vue 前端
   │ 仅管理配置、提交任务、查看进度与结果
   ▼
Flask Agent API
   ▼
Python Agent Runtime
   ├─ StructuredExecutionStrategy
   ├─ ToolLoopExecutionStrategy
   ├─ ModelRouter
   ├─ ToolRegistry
   ├─ SecretStore
   └─ RunRepository
   │
   ├─ HermesProviderAdapter
   ├─ OpenAICompatibleProviderAdapter
   └─ CodexCliProviderAdapter
```

所有 Agent 请求只有一个入口：

```text
Vue → Flask Agent API → Python Agent Runtime → Model Adapter
```

Electron 不再提供以下 AI IPC：

- `window.sunbirdDesktop.piPrompt`
- `getPiSettings`
- `savePiSettings`
- `sunbird:pi-prompt`
- `sunbird:get-pi-settings`
- `sunbird:save-pi-settings`

## 6. 模块边界

智能体基础能力放在 `backend_app/agent/`：

```text
backend_app/agent/
├─ runtime.py
├─ model_router.py
├─ tool_registry.py
├─ secret_store.py
├─ errors.py
├─ strategies/
│  ├─ structured.py
│  └─ tool_loop.py
└─ providers/
   ├─ hermes.py
   ├─ openai_compatible.py
   └─ codex_cli.py
```

配置和任务属于业务模块，放在：

```text
backend_app/modules/ai_settings/
backend_app/modules/agent_runs/
```

每个业务模块按 `routes.py`、`service.py`、`repository.py` 拆分。`sau_backend.py` 只注册 Blueprint、初始化数据库、装配 Runtime 和启动服务，不新增 AI 业务实现。

## 7. 数据模型

### 7.1 `app_settings`

保存非敏感通用配置，替代 `settings.json`。

| 字段 | 说明 |
|---|---|
| `key` | 主键 |
| `value_json` | JSON 编码后的值 |
| `value_type` | 值类型与校验提示 |
| `updated_at` | 更新时间 |

Codex CLI 路径、默认模型和默认超时可以迁入该表或对应 Provider/Profile 表，不再依赖 JSON 文件。

### 7.2 `ai_providers`

| 字段 | 说明 |
|---|---|
| `id` | UUID 主键 |
| `name` | 显示名称 |
| `provider_type` | `hermes`、`openai_compatible` 或 `codex_cli` |
| `base_url` | HTTP Provider 地址；CLI Provider 可为空 |
| `timeout_seconds` | 请求超时 |
| `enabled` | 是否启用 |
| `capabilities_json` | 工具调用、JSON Schema、推理等能力 |
| `created_at` / `updated_at` | 时间戳 |

### 7.3 `ai_credentials`

| 字段 | 说明 |
|---|---|
| `id` | UUID 主键 |
| `provider_id` | Provider 外键 |
| `credential_type` | 默认 `api_key` |
| `ciphertext` | AES-GCM 密文 |
| `nonce` | 随机 nonce |
| `algorithm` | 默认 `AES-256-GCM` |
| `key_reference` | 系统安全存储中的主密钥引用 |
| `encryption_version` | 加密版本 |
| `created_at` / `updated_at` | 时间戳 |

数据库不得保存明文、可逆掩码或完整密钥摘要。

### 7.4 `ai_model_profiles`

保存具体模型与推理参数：`provider_id`、`name`、`model_name`、`reasoning_effort`、`service_tier`、`temperature`、`max_tokens`、`extra_options_json` 和 `enabled`。

### 7.5 `agent_profiles`

保存每个 Agent 的运行方式：`agent_key`、`name`、`execution_mode`、`primary_model_profile_id`、`fallback_model_profile_id`、`timeout_seconds`、`max_steps` 和 `enabled`。

`execution_mode` 只允许：

- `structured`：要求结构化 JSON 或 JSON Schema 输出。
- `tool_loop`：允许多轮模型调用和工具执行。

### 7.6 `agent_runs`

保存任务输入、输出、状态、错误、实际模型和时间。状态机固定为：

```text
queued → running → succeeded
                 → failed
                 → cancelled
                 → interrupted
```

### 7.7 `agent_run_events`

保存任务进度、模型调用、工具调用、工具结果和安全错误事件。事件只保存脱敏后的结构化数据。

### 7.8 会话扩展

若工具型 Agent 需要多轮持久会话，再增加 `agent_sessions` 和 `agent_messages`。首期单次 Prompt 可以只使用 `agent_runs`，避免提前引入无用复杂度。

## 8. 密钥保护

采用信封加密：

1. 首次运行生成随机 256 位数据加密密钥。
2. 数据加密密钥由操作系统安全存储保护。
3. API Key 使用 AES-256-GCM 和独立随机 nonce 加密。
4. SQLite 仅保存密文、nonce、算法版本和安全存储引用。
5. 调用模型时由 Python `SecretStore` 临时解密，秘密不进入日志、异常或 API 响应。

跨平台主密钥适配：

- Windows：DPAPI 或 Windows Credential Manager。
- macOS：Keychain。
- Linux：Secret Service。

可以由 Python `keyring` 提供统一适配层，AES-GCM 由 `cryptography` 实现。如果系统安全存储不可用，保存密钥和启动需要密钥的 Agent 必须失败关闭，不允许降级为明文。

数据库是配置的唯一事实来源；系统安全存储只保存数据加密密钥，不保存业务配置。复制数据库到另一设备后，密钥不可解密，用户需要重新录入。

## 9. Agent Runtime

### 9.1 `StructuredExecutionStrategy`

迁移现有 `call_hermes_structured` 和 `run_codex_cli_structured` 的能力：

- 根据 Agent Profile 选择模型。
- 构造结构化输出约束。
- 对非法 JSON 最多执行一次格式修复重试。
- 记录实际 Provider、模型、耗时和脱敏错误。

### 9.2 `ToolLoopExecutionStrategy`

替代 `pi-agent-sidecar.mjs`：

- 读取 Agent Profile 和模型能力。
- 向支持工具调用的 Provider 发送工具定义。
- 限制最大步骤和总超时。
- 每次工具调用前后写入任务事件。
- 有副作用的工具失败后不自动重复执行。
- 达到最大步骤、取消或超时时安全终止。

### 9.3 `ModelRouter`

选择 Agent 的主模型；在明确允许回退且错误属于连接、限流或模型不可用时使用备用模型。鉴权失败、输入校验失败和工具业务错误不得触发模型回退。

### 9.4 `ToolRegistry`

工具直接调用 Python 领域服务，不再通过 HTTP 绕回本机 Flask：

- `search_douyin_content` → benchmark service
- `list_benchmark_videos` → benchmark service/repository
- `save_benchmark_analysis` → benchmark service
- `get_account_diagnosis_facts` → account_diagnosis service

工具定义负责参数 Schema、权限标签、是否有副作用和超时配置；业务逻辑仍由对应领域 service 负责。

## 10. API

配置 API：

```text
GET    /api/ai/providers
POST   /api/ai/providers
PUT    /api/ai/providers/{id}
PUT    /api/ai/providers/{id}/credential
DELETE /api/ai/providers/{id}/credential
POST   /api/ai/providers/{id}/test

GET    /api/ai/model-profiles
POST   /api/ai/model-profiles
PUT    /api/ai/model-profiles/{id}
DELETE /api/ai/model-profiles/{id}

GET    /api/ai/agent-profiles
PUT    /api/ai/agent-profiles/{agent_key}
```

密钥没有读取接口。Provider API 只返回 `credentialConfigured: true|false`。

Agent API：

```text
POST /api/agents/{agent_key}/runs
GET  /api/agent-runs/{run_id}
GET  /api/agent-runs/{run_id}/events
POST /api/agent-runs/{run_id}/cancel
```

创建任务返回 HTTP 202、`runId` 和 `queued` 状态。第一版由前端轮询状态，不引入 WebSocket；需要实时增量文本时再增加 SSE。

## 11. 后台执行与可靠性

桌面单机版使用进程内有界线程池，默认最多同时执行两个 Agent 任务。超出的任务保持 `queued`。应用启动时将遗留的 `queued` 或 `running` 任务标记为 `interrupted`，由用户决定是否重试。

SQLite 统一启用：

- `PRAGMA journal_mode=WAL`
- `PRAGMA foreign_keys=ON`
- `PRAGMA busy_timeout=5000`

所有新增表由统一迁移管理器创建，不在请求路由中临时建表。

## 12. 安全规则

- Vue、Electron和 API 响应不得获得明文 API Key。
- 日志必须递归脱敏 `apiKey`、`authorization`、`token`、`secret`、`credential` 等字段。
- Provider 地址只接受 HTTP(S)。非本机地址默认要求 HTTPS；仅 `localhost` 和 `127.0.0.1` 可使用 HTTP。
- 修改或删除密钥只记录审计事件，不记录密钥、密文和 nonce。
- Provider 测试必须通过统一 `ModelRouter` 和 `SecretStore`。
- 主密钥和密文包含版本号，为密钥轮换预留迁移能力。

## 13. 迁移方案

### 阶段 1：数据库与安全基础

- 增加迁移管理器和新表。
- 实现 `SecretStore`、Provider Repository 和 Model Profile Repository。
- 保持旧调用链可运行。

### 阶段 2：配置迁移

- 将 `settings.json` 中的 Hermes、Agent 模型、任务绑定和 Codex CLI 设置导入 SQLite。
- 将 Hermes 明文 API Key 加密后写入 `ai_credentials`。
- 导入成功并验证后停止读取并删除旧 `settings.json`。
- 迁移必须幂等，重复启动不得产生重复 Provider 或 Model Profile。

### 阶段 3：结构化 Agent 迁移

- 让现有爆款拆解、选题雷达、账号诊断等结构化调用经过统一 Runtime。
- 保留旧 HTTP 路径作为数据库-backed 兼容接口，前端稳定后再切换新 API。

### 阶段 4：PI Agent 迁移

- Electron 一次性使用现有 `safeStorage` 解密 PI API Key。
- 通过本机实例令牌保护的迁移接口把秘密仅在内存中发送给后端。
- 后端使用新 `SecretStore` 加密入库。
- 将四个现有 PI 工具迁入 Python Tool Registry。
- 前端改为创建 `tool_loop` Agent Run。

### 阶段 5：移除旧链路

- 移除 Electron PI IPC。
- 删除 `pi-agent-sidecar.mjs` 和 PI Agent 独立配置 UI。
- 验证数据库配置后停止读取并删除 `pi-agent-settings.json`。
- 更新 README、架构图、时序图和数据流图。

## 14. 错误处理

统一错误类型包括：配置缺失、密钥不可用、Provider 鉴权失败、Provider 不可达、请求超时、模型能力不兼容、结构化输出无效、工具参数无效、工具业务失败、任务取消和任务中断。

外部错误写入完整但脱敏的后端日志；API 仅返回稳定错误码和用户可理解的信息。鉴权错误不得自动回退到另一个 Provider，以免隐藏错误配置。

## 15. 测试策略

### 单元测试

- AES-GCM 加解密、错误主密钥、nonce 唯一性和密钥轮换。
- Repository 的唯一约束、外键和状态转换。
- Model Router 主模型选择与允许的回退条件。
- Structured Strategy 的 JSON 修复上限。
- Tool Strategy 的步骤上限、取消、超时和副作用工具不重试。
- 日志与 API 脱敏。

### 集成测试

- 使用临时 SQLite 和伪系统安全存储。
- 使用 Mock Provider，不调用真实账号或真实模型。
- 验证配置、密钥、模型、Agent Profile 和 Run API。
- 验证 `settings.json` 与 PI 配置迁移幂等。

### 桌面验收

- Windows 打包版首次迁移、重启和卸载重装场景。
- 后端异常退出后任务标记为 `interrupted`。
- Electron 不再读取或传递 AI Key。
- macOS/Linux 先验证 SecretStore 接口和不可用时失败关闭；正式打包时再做平台实机验收。

## 16. 验收标准

- 删除 `settings.json` 后应用仍可读取所有持久配置。
- 删除 `pi-agent-settings.json` 后 Tool Agent 仍可运行。
- SQLite、JSON、日志和 API 响应中不存在 API Key 明文。
- Vue 不再调用 `piPrompt` 或任何模型供应商。
- Electron 不再保存、解密或传递日常 AI 模型密钥；只保留一次性迁移桥接，迁移完成后删除。
- Structured Agent 与 Tool Agent 均通过同一 Python Runtime。
- 不同 Agent 可以绑定不同模型与备用模型。
- 工具型 Agent 直接调用 Python 领域服务，不经过本机 HTTP 回环。
- 后端重启后能够查看历史任务，未完成任务状态为 `interrupted`。
- 所有相关测试使用 Mock Provider，不依赖真实密钥和实际发布操作。

## 17. 实施顺序结论

实施必须按“数据库与密钥基础 → 统一配置 → 结构化 Agent → Tool Agent → 删除旧链路”的顺序推进。每个阶段独立测试，旧链路只在迁移阶段保留，最终版本不允许两套配置和两套 Runtime 长期共存。
