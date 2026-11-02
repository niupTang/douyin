# 后端运行日志模块设计

## 目标

为 Sunbird OS 后端提供本地、结构化、可诊断的运行日志。日志用于排查应用启动、接口异常、任务执行、外部命令和模型调用问题，不作为用户行为审计功能，也不提供前端日志页面。

## 存储

每个日志事件只写入本地文件：

- `<运行数据目录>/logs/backend.json`：用于快速查看最近日志。

`backend.json` 是一个合法 JSON 对象，包含 `version`、`updatedAt` 和 `entries`。每个条目包含：`timestamp`、`level`、`module`、`event`、`message`、`durationMs` 与 `context`。

文件写入使用同目录临时文件并原子替换。文件只保存最近 10,000 条日志快照，超过数量时清理最旧条目。

## 模块边界

新增 `backend_app/modules/runtime_logs/`：

- `service.py`：事件标准化、脱敏、文件快照写入和容量清理。
- `__init__.py`：对外暴露最小日志接口。

现有 `sau_backend.py` 中的 `backend_log()` 保持调用兼容，但内部改为调用日志服务。应用启动、退出、接口异常、任务开始/完成/失败、外部命令和模型调用接入统一事件名。

## 安全与容错

日志不记录请求正文或完整查询参数。`Authorization`、`Cookie`、`token`、`refreshToken`、`apiKey`、`password`、`license`、`code` 等敏感键及其值会被递归替换为 `[REDACTED]`。

文件写入失败时，不向业务调用方抛出异常。日志模块自身不记录原始异常上下文中的敏感信息。

## 验证

pytest 覆盖以下行为：

- 敏感字段、嵌套对象与列表均会脱敏。
- `backend.json` 始终可解析，且仅含最近快照。
- 文件写入失败不会中断业务调用。

## 非目标

- 不新增日志管理前端页面、导出功能或远程日志上传。
- 不修改桌面授权、账号 Cookie、业务数据库数据或发布流程。
