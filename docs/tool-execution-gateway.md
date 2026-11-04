# 统一工具执行网关

Agent 的 ToolRegistry 和现有 /mcp/invoke 使用应用装配时创建的同一个 ToolExecutionGateway。
底层业务适配与工具定义位于 backend_app/modules/tool_execution，旧导入路径保留兼容导出。

执行链：调用方工具范围检查 → JSON / JSON Schema 参数校验 → 工具权限检查 → 业务服务 → 成功或失败日志。
网关不通过 HTTP 回调自身，仍直接复用现有业务服务。成功时保留原始业务结果，不改变任务 ID 等结构。

## 定义工具

使用 gateway.register(name, description, parameters, handler, effect_type=..., entitlement=...)。
handler 接收关键字参数；顶层未知参数默认拒绝。嵌套自由对象是否允许未知字段由对应 JSON Schema 决定。
注册表发布给模型的 schema 是副本。授权回调由应用装配，调用者不能通过工具参数覆盖权限或来源。

Agent 工具视图仅暴露原有工具，不因共享网关而自动获得发布能力。
MCP 的旧 list_benchmark_videos（指定账号分页）映射为内部 list_account_benchmark_videos；
Agent 的同名工具仍表示跨账号关键词查询，避免同名不同参数契约冲突。

## 权限和诊断

采集检查 benchmarkCollect，分析检查 aiAnalysis，脚本生成检查 scriptStudio，发布检查 publishing。
HTTP 登录认证仍保留；MCP 不再把所有工具一律作为 aiAnalysis 检查。
应用内部默认读取工具不额外消耗功能授权；写入与外部动作按工具元数据检查。

每次调用记录 invocation_id、source、run_id、actor_id、tool、duration_ms 和 error_code。
不记录完整输入、输出或异常内容。诊断写入失败不改变已经完成的业务结果，不自动重试操作。
日志可通过现有运行日志功能查看，module 为 tool_gateway。

统一错误包括 TOOL_NOT_FOUND、TOOL_ARGUMENTS_INVALID、TOOL_BUSINESS_INVALID、TOOL_EXECUTION_FAILED、
TOOL_NOT_IMPLEMENTED，以及许可证返回的权限错误码。MCP 返回原有 code/msg/data，加 error_code 和 invocation_id；
Agent 工具错误结果中也带错误码和调用 ID。

## 当前范围

这是统一执行边界，不是新的标准 MCP 协议服务端，也不替代已有工作流。
工具返回的异步任务继续由现有任务系统管理。
本次不新增审批存储、持久化幂等键、跨进程任务恢复或强制中止同步业务的超时机制。
许可证检查不代表新增了逐账号访问控制；账号和文件校验继续由业务服务负责。
