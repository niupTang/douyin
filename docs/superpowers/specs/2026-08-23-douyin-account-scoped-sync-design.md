# 抖音账号维度作品数据同步设计

## 背景

当前“作品复盘”的自动导出使用固定的 `cookiesFile/douyin_creator_profile`，同步结果统一写入名为“太阳鸟”的自有账号。该模式无法保证创作者中心登录态与账号中心所选账号一致，也无法在多账号场景中隔离作品、同步状态和分析结果。

本次改造要求用户先从账号中心选择一个抖音账号，后端临时使用该账号已有的 Playwright `storage_state` 完成创作者中心数据导出。自动同步和手动文件导入都必须归属到所选账号。

## 目标

- 作品复盘页必须先选择账号中心中的抖音账号。
- 自动同步只使用所选账号的 Cookie JSON，不使用固定 Creator Profile 或备用登录态。
- 手动 CSV/XLSX 导入与自动同步使用相同的账号归属规则。
- 作品列表、同步状态和单条作品分析按账号隔离。
- Cookie 失效时立即停止并提示用户去账号管理重新登录。
- 同步浏览器使用一次性 Context，任务结束后必须关闭。

## 非目标

- 不在作品复盘页重新实现扫码登录。
- 不从 Electron 会话、普通抖音网页或固定 Profile 猜测登录账号。
- 不修改抖音发布流程和发布账号 Cookie 的生成方式。
- 不自动合并不同账号下已有的历史作品。
- 不调用真实抖音 API 作为测试依赖。

## 账号模型

账号中心的 `user_info` 是账号身份来源：

- `id`：前后端传递的账号标识。
- `type`：必须为 `3`，代表抖音。
- `userName`：界面展示和自有账号命名来源。
- `filePath`：`cookiesFile` 下的 Playwright `storage_state` JSON 文件名。
- `status`：必须为正常状态 `1`。

自有作品账号继续使用 `douyin_own_accounts`，通过已有的 `user_info_id` 与账号中心绑定。`user_info_id` 应保持唯一账号归属；同步或导入时按该字段查找账号，不再按固定名称“太阳鸟”归档。

## 前端设计

### 账号选择

“作品复盘”页顶部增加“数据账号”选择器，只展示 `type=3` 的账号中心账号。选择器保存 `userInfoId`，并显示账号名称和状态。

未选择账号时，以下操作不可用：

- 立即同步
- 手动导入预览
- 确认导入
- 作品列表与作品分析

选择账号后立即加载该账号的作品和最近同步状态。切换账号时清空上一账号的预览结果、导入结果、作品抽屉和轮询任务，再加载新账号数据。

### 页面数据隔离

- 作品列表请求必须携带当前 `userInfoId`。
- 同步状态请求必须携带当前 `userInfoId`。
- 手动预览和确认导入必须携带当前 `userInfoId`。
- 单条作品分析继续按作品 ID 调用；后端必须确保作品已有明确账号归属。

页面不提供混合账号的“全部作品”视图。

## API 设计

### 查询可同步账号

复用账号诊断已有的抖音账号列表能力，或在作品复盘领域提供等价只读接口。返回字段至少包含：

```json
{
  "id": 36,
  "userName": "太阳鸟",
  "status": 1
}
```

不得向前端返回 Cookie 内容。

### 自动同步

`POST /own/douyin/export/run`

请求体：

```json
{
  "userInfoId": 36
}
```

后端根据 `userInfoId` 查询 `user_info`，自行解析 Cookie 文件路径。前端不得提交 `filePath` 或任意文件路径。

成功接收返回 `202`，响应包含账号和任务标识：

```json
{
  "code": 202,
  "msg": "已开始同步",
  "data": {
    "runId": 101,
    "userInfoId": 36,
    "status": "running"
  }
}
```

同一账号已有运行中任务时返回冲突结果，不重复启动。不同账号的任务相互独立。

### 同步状态

`GET /own/douyin/export/status?userInfoId=36`

只返回该账号最近一次同步任务。未提供 `userInfoId` 返回 `400`，不回退到全局最近任务。

### 作品列表

`GET /own/douyin/videos?userInfoId=36&limit=200`

只查询绑定到该 `user_info_id` 的自有账号作品。未提供账号返回 `400`。

### 手动导入

以下接口的 multipart 表单均增加必填字段 `userInfoId`：

- `POST /own/douyin/import/preview`
- `POST /own/douyin/import`

预览阶段也校验账号存在、平台类型和状态，避免用户预览完成后才发现无法归档。确认导入时按 `userInfoId` 查找或创建自有账号并写入作品。

## 后端组件边界

### 账号解析服务

新增领域内账号解析函数，输入 `user_info_id`，输出经过验证的账号对象和绝对 Cookie 路径。它负责：

- 账号存在性校验。
- `type == 3` 校验。
- `status == 1` 校验。
- `filePath` 必须为普通文件名，解析后必须位于 `BASE_DIR/cookiesFile` 内。
- Cookie 文件存在且为合法 Playwright storage state JSON。

路由和导出器不直接拼接用户输入路径。

### 导出器

导出器接收已验证的 Cookie JSON 路径和下载目录：

1. 启动 Chromium。
2. 使用 `browser.new_context(storage_state=cookie_path)` 创建一次性 Context。
3. 注入现有 stealth 初始化脚本。
4. 打开创作者中心内容管理页。
5. 检查是否被重定向到登录界面。
6. 点击导出并保存文件到 `E:/social-auto-upload/data/douyin_exports`。
7. 导出成功后，将当前 Context 的 storage state 原子写回原账号 JSON，更新平台刷新后的 Cookie。
8. 无论成功或失败都关闭 Context 和 Browser。

导出器不再读取或创建 `douyin_creator_profile`，也不使用普通 `douyin_browser_profile` 作为备用。

### 导入服务

导入服务输入标准化作品行和已验证账号：

- 按 `douyin_own_accounts.user_info_id` 查找自有账号。
- 不存在时使用 `user_info.userName` 创建并绑定。
- 同一个 `user_info_id` 只对应一个自有账号。
- 作品唯一性仍采用视频 URL；无 URL 时采用标题与发布时间哈希。
- 唯一性范围保留在自有账号内部，因此不同账号的相同作品链接或标题不会互相覆盖。

## 数据库变更

`douyin_own_export_runs` 增加：

- `user_info_id INTEGER NOT NULL`
- `account_name TEXT`

并建立 `(user_info_id, id)` 查询索引，用于获取指定账号最近任务。

`douyin_own_accounts.user_info_id` 已存在，补充唯一索引前先检查历史重复绑定。若存在重复绑定，不自动删除数据；迁移应明确报错并要求人工处理，避免错误合并作品。

旧的无账号同步记录可以保留，但不会出现在账号维度状态查询中。旧的未绑定“太阳鸟”作品保持原状，后续如需迁移应设计单独的数据迁移工具。

## 并发与任务状态

- 创建任务记录后再启动后台线程，接口立即返回确定的 `runId`。
- 同一 `user_info_id` 同时最多一个 `running` 任务。
- 不同账号允许并行，但每个任务使用独立 Browser/Context 和独立下载文件名。
- 状态为 `running`、`success` 或 `failed`。
- 失败记录保存阶段明确的错误信息，不修改既有作品数据。
- 文件下载和解析成功后才执行数据库事务写入。

## 错误处理

- 缺少 `userInfoId`：`400`。
- 账号不存在：`400`。
- 非抖音账号：`400`。
- 账号状态异常：`409`，提示去账号管理重新登录。
- Cookie 路径越界、文件缺失或 JSON 无效：`409`。
- 创作者中心显示登录页：任务标记 `failed`，提示重新登录账号。
- 未找到导出入口或下载超时：任务标记 `failed`，保留具体阶段信息。
- 文件字段不兼容：任务标记 `failed`，不写入部分数据。

任何错误都不得尝试固定 Creator Profile 或其他账号 Cookie。

## 测试设计

### 后端单元测试

- 账号存在、类型、状态和 Cookie 路径校验。
- 拒绝绝对路径、目录穿越和 `cookiesFile` 外路径。
- 按 `user_info_id` 查找或创建自有账号。
- 两个账号导入相同 URL、标题和发布时间时分别保存。
- 作品列表按账号隔离。
- 同步状态按账号隔离。
- 同账号运行中任务去重，不同账号可创建任务。
- Cookie 失效、下载失败、解析失败时状态正确且不产生部分入库。

### 导出器测试

使用 mock Playwright Browser、Context、Page 和 Download，验证：

- `new_context` 接收所选账号 storage state。
- 不调用持久化 Profile。
- 成功后写回刷新后的 storage state。
- 成功和异常路径都关闭 Context/Browser。

### 前端测试与验收

- 未选账号时操作禁用。
- 选择账号后加载该账号作品与状态。
- 切换账号清空旧状态并发起新请求。
- 手动预览和导入都携带 `userInfoId`。
- Cookie 失效提示明确指向账号管理重新登录。
- 不出现“登录数据账号”或固定 Profile 入口。

## 验收标准

- 用户可以从账号中心选择任一正常抖音账号并同步其创作者中心数据。
- 自动同步和手动导入的数据只出现在当前账号作品库。
- 切换账号后看不到上一账号的作品和同步状态。
- 删除或失效 Cookie 不会回退到其他登录态。
- 全部后端聚焦测试、Python 编译和前端生产构建通过。
