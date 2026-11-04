# Repository Guidelines

## 项目结构与模块组织

本仓库由 Python 后端、Vue/Vite 前端和 Electron 桌面壳组成。

- `sau_backend.py` 仅作为后端启动与应用装配入口；业务逻辑必须按领域拆分到 `backend_app/modules/`，公共配置和数据库能力放在 `backend_app/common/`，智能体能力放在 `backend_app/agent/`。
- `uploader/` 存放各平台上传实现；`koubo_integration/`、`myUtils/` 和 `utils/` 提供集成与公共能力。
- `sau_frontend/src/` 是 Vue 前端源码，按 `views/`、`components/`、`api/`、`stores/` 和 `router/` 组织。
- `electron/` 存放 Electron 主进程、预加载脚本和 sidecar；`project-video/` 是独立的视频生成项目。
- `tests/` 存放 pytest 测试，`examples/` 提供平台调用示例，`scripts/` 放构建及维护脚本，`docs/` 放设计文档。
- `build/`、`dist/`、`release*/`、`node_modules/`、日志及媒体输出均为依赖或生成物，不应作为源码修改。

## 构建、测试与本地开发

先执行 `pip install -r requirements.txt` 和 `npm install` 安装依赖。首次运行可用 `python db/createTable.py` 初始化 SQLite 数据库。

- `python sau_backend.py`：启动后端，默认地址为 `http://localhost:5409`。
- `npm run frontend:dev`：启动 Vite 开发服务器，默认端口为 5173。
- `npm run desktop:dev`：连接开发服务器并启动 Electron。
- `npm run frontend:build`：构建前端。
- `npm run desktop:pack`：生成未打包桌面程序；`npm run desktop:dist`：生成安装包。
- `pytest`：运行全部 Python 测试；可用 `pytest tests/test_koubo_integration.py` 运行单个文件。

## 编码风格与命名

Python 使用 4 空格缩进，模块、函数和变量使用 `snake_case`；JavaScript/Vue 延续相邻文件风格，变量和函数使用 `camelCase`，Vue 视图组件使用 `PascalCase.vue`。平台特有逻辑放入对应的 `uploader/<platform>_uploader/`，可复用逻辑放入公共模块。禁止把路由、数据库访问和业务逻辑继续堆入 `sau_backend.py`；新增功能应按领域建立或扩展 `backend_app/modules/<domain>/`，入口文件只保留初始化、依赖装配和服务启动。仓库暂未配置统一格式化或 lint 命令，提交前应检查变更，并确保 Windows 命令、脚本及日志统一使用 UTF-8。

## 测试规范

测试框架为 pytest。测试文件命名为 `test_*.py`，测试函数命名为 `test_*`。修复缺陷或修改后端、集成、上传逻辑时，应补充聚焦的回归测试。测试不得依赖真实账号、Cookie 或实际发布操作；优先使用 fixture、mock 和临时目录。

## 提交与合并请求

Git 历史主要采用 Conventional Commits，例如 `feat:`、`fix:`、`refactor:`。提交标题应简短、使用祈使语气且一次只描述一类改动。PR 需说明用户可见影响、列出验证命令、关联 issue 或设计文档；前端和 Electron 改动应附截图或录屏，并明确数据库、配置、打包或迁移影响。

## 安全与配置

以 `conf.example.py` 为模板创建本地配置。禁止提交密钥、令牌、Cookie、账号文件、数据库、日志中的敏感信息或生成的安装包。新增运行时目录前先检查 `.gitignore`，共享截图和日志前完成脱敏。
