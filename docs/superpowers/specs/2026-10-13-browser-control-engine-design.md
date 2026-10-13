# Python Playwright 浏览器控制引擎设计

日期：2026-10-13  
状态：待用户审阅

## 1. 目标与范围

把当前分散在登录、采集、导出和上传代码中的 Playwright 通用行为抽取为 Python 浏览器控制引擎。平台操作采用策略模式：新增平台或操作时，实现并注册对应策略，不修改引擎的启动、会话、下载和清理逻辑。

首期保持现有 API、任务结果、Cookie 文件格式和发布行为不变。首期只处理 Python Playwright；Electron `WebContentsView` 的人工登录窗口及其会话同步接口继续作为独立适配器。智能体以后通过单独的受限工具层调用引擎，不直接获得 Playwright `Page` 或任意 JavaScript 执行权。

本设计覆盖现有的抖音登录、对标采集、自有作品导出和发布，以及其他平台上传代码的后续迁移。首期不要求一次性迁移所有平台，也不改变平台网页选择器。

## 2. 当前实现

- `myUtils/login.py` 为各平台分别启动 Chromium、创建 Context、注入初始化脚本、扫码、保存 `storage_state`。
- `myUtils/douyin_benchmark.py` 使用独立的启动参数和持久化 Profile；采集任务又单独创建临时 Context。
- `backend_app/modules/own_content_review/exporter.py` 自己创建带下载目录的浏览器、加载账号状态、导出文件并刷新状态。
- `uploader/<platform>_uploader/main.py` 分别管理浏览器生命周期、账号状态和发布页面动作；部分平台使用 Chromium，TikTok 使用 Firefox。
- `utils/base_social_media.py` 只提供初始化脚本注入，没有统一的会话或策略接口。
- Electron 主进程另有 `WebContentsView` 和 `persist:douyin` 会话，用于用户手动登录；它不属于 Python Playwright 控制链。

重复的是资源管理和会话装配；页面 URL、定位器、登录判断、上传步骤和采集解析属于平台行为，应留在策略中。

## 3. 方案比较

### A. 通用函数集合

把 `launch()`、`new_context()`、`storage_state()` 包装成几个函数。改动小，但调用方仍需自行组合资源和异常清理；新增平台仍容易复制旧流程。

### B. 浏览器会话引擎 + 平台操作策略（采用）

引擎持有 Playwright、Browser、Context、Page 的生命周期，策略仅声明所需会话配置并执行平台步骤。注册表按 `(platform, operation)` 选择策略。可逐个迁移已有流程，且新操作无需修改引擎。

### C. 通用网页指令解释器

把点击、输入和等待都改成配置化指令。不同平台的登录验证、上传进度和异常恢复很难用同一套静态指令准确描述，还会增加调试成本，因此不作为首期核心。

## 4. 模块边界

```text
backend_app/common/browser_engine/
  models.py            BrowserSpec、账号状态和操作结果定义
  session.py           异步上下文管理器、Browser/Context/Page 生命周期
  storage.py           storage_state 读取、校验、原子更新
  downloads.py         下载目录、文件保存和路径校验
  registry.py          (platform, operation) -> strategy 注册与查找
  engine.py            根据策略配置建立会话并运行操作

backend_app/agent/browser_tools.py
  以后为智能体提供经授权的有限操作，不属于首期迁移

现有平台模块、uploader/<platform>_uploader/
  平台 URL、定位器、扫码条件、解析规则、上传步骤和异常恢复策略
```

`backend_app/common/browser_engine/` 不依赖 Flask、数据库或具体平台。业务模块负责账号身份校验、任务状态和数据持久化；引擎只处理浏览器资源及文件边界。平台特有的上传策略放在对应 `uploader/<platform>_uploader/`；登录、采集等策略先留在现有领域模块，迁移时抽成相邻的 `browser_strategy.py`。注册表把它们统一暴露，不把所有平台行为塞进一个类。

## 5. 策略契约

一个策略代表某个平台的一种操作，例如 `(douyin, login)`、`(douyin, collect_benchmark)`、`(douyin, export_own_content)`、`(douyin, publish_video)`、`(tencent, publish_video)`。新平台只注册它实际支持的操作；不需要实现一组空方法。

策略必须提供：

1. `platform` 和 `operation`，用于唯一注册。
2. `browser_spec(request)`，声明浏览器类型、可见性、代理、视口、语言、账号状态、下载需求和可选的浏览器可执行文件。
3. `execute(session, request)`，在已有会话中执行平台步骤并返回结构化结果。

请求包含业务传入的账号引用、文件、标题及操作参数；策略自身不得从全局状态猜测账号。`session` 提供受管理的 `page`、`context`、下载保存和状态更新能力；平台代码可继续使用 Playwright Locator，不逐个包装所有定位器方法。引擎在 `finally` 中关闭 Context、Browser 和 Playwright，失败时保留原始异常类型供业务层映射。

引擎入口的概念形式为 `await engine.run(platform, operation, request)`。现有同步 Flask 入口通过原有后台任务或事件循环桥接，避免在运行中的事件循环里嵌套 `asyncio.run()`。现有路由、SSE 事件和上传调用签名保留兼容包装，迁移完成后再清理包装。

## 6. 账号、下载与安全边界

- 每次业务操作创建独立 Context；持久化 Profile 仅用于明确需要用户交互的登录场景，不与其他账号共享。
- `storage_state` 路径由账号仓储解析，必须位于配置的账号状态目录内。写入先到同目录临时文件，再原子替换；失败时不覆盖已验证状态。
- 引擎不记录 Cookie、请求头、密码、二维码内容或完整 `storage_state`。日志只记录任务 ID、平台、操作、账号 ID、阶段和脱敏错误。
- 下载根目录显式配置并验证。在当前 Windows 工作环境中，所有浏览器下载、临时文件和浏览器安装/缓存路径必须位于 E 盘；不回退到 `%LOCALAPPDATA%` 或其他 C 盘目录。新运行时目录加入 `.gitignore`。
- 浏览器可执行文件路径、代理和超时由配置注入；策略可以声明需要的浏览器类型，不自行寻找或下载浏览器。
- 未来智能体工具层仅允许已注册的读操作和用户授权的写操作；不能把任意 URL、任意脚本执行或自动发布作为通用工具直接开放。

## 7. 迁移顺序

1. 建立引擎、策略注册表和假 Playwright 测试夹具，不触碰真实账号。
2. 迁移抖音对标采集与自有作品导出，验证临时 Context、账号状态、下载路径和资源关闭。
3. 迁移抖音扫码登录，保留二维码 SSE、真实账号身份验证和原子状态提交。
4. 迁移抖音发布，再逐个平台迁移其他上传策略。每次只迁移一个平台，保持原 API 和页面行为。
5. 所有调用方完成迁移后，移除重复的启动与清理代码；再考虑 Electron 会话适配和智能体工具接口。

## 8. 错误处理与验收

引擎区分浏览器不可用、账号状态无效、页面超时、下载失败和策略执行失败；业务层把它们映射到现有用户提示。任务取消或异常时必须关闭资源，下载中的临时文件不得留下可误认的最终结果。策略返回数据前由业务层确认目标账号，避免串号。

聚焦回归测试使用 mock Browser、Context、Page 和临时目录，不访问真实平台，也不实际发布。验收包括：

- 注册新平台操作无需修改引擎；重复键和不支持的操作给出明确错误。
- 相同账号状态只进入指定任务的 Context；不同账号不会共享会话。
- 成功、超时、异常和取消均能关闭资源；失败不覆盖旧状态。
- 下载和缓存路径在本工作环境留在 E 盘。
- 已迁移的登录、采集、导出和上传保持原有外部接口与结果。

## 9. 非目标

首期不统一 Electron 的 `WebContentsView` 与 Playwright 进程，不构建任意网页的通用 RPA 编辑器，不让智能体直接控制任意页面，不重写平台选择器，也不一次性迁移所有平台。
