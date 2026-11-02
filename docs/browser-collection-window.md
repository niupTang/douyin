# 采集浮窗

对标账号同步、自动找对标、内容搜索、创作者数据导出，以及视频下载的 Playwright 备用路径，默认在可见 Chromium 小窗口中运行。窗口展示实际采集页面，可拖动、最小化和调整大小；Windows 上置顶并初始放在屏幕右下角。任务成功或失败后关闭其浏览器，用户关闭采集页面会停止当前浏览器任务。

窗口初始大小为 900 × 700；页面保留原来的桌面视口并缩放展示，避免因窄屏布局改变采集定位器。批量发现账号后的逐个同步分别创建、关闭窗口；多个并行任务拥有独立的浏览器。关闭一个窗口停止该次任务，批量操作后续账号仍按原流程处理。

yt-dlp 的直接文件下载继续使用业务页的下载进度。它没有浏览器页面；只有切换到 Playwright 解析作品页时才出现浏览器浮窗。

## 运行

默认 `SAU_BROWSER_PRESENTATION=floating`。服务器、CI 或不需要可见窗口时设为 `headless`；没有 DISPLAY/WAYLAND_DISPLAY 的 Linux 环境自动使用无头模式。

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:SAU_BROWSER_PRESENTATION = 'floating'
python sau_backend.py
```

需使用完整的 Playwright Chromium，不能仅安装 headless shell。浏览器包沿用应用的 `PLAYWRIGHT_BROWSERS_PATH`。浮窗任务的临时 profile 和浏览器临时下载存放在 `SAU_BASE_DIR/.sau-cache/browser/`，未配置数据目录时使用项目目录；Windows 拒绝 C 盘路径。用户导出的成果继续写入已选择的下载目录。

## 实现边界

浮窗是现有 Python Playwright 控制的原生 Chromium 窗口。共用引擎提供 `session(spec)` 管理资源，`presentation="floating"` 启用展示。没有迁移到 Electron WebContentsView，也不复制另一份页面或登录会话。平台定位器、滚动和入库逻辑沿用现有实现。

Windows 置顶仅作用于当前任务的 Chromium 进程窗口。置顶失败会降级为普通可见窗口；页面初始化、采集或下载错误继续向原任务入口返回。

## 验证

回归测试覆盖浮窗/无头切换、保持桌面视口、临时目录、采集入口、下载与导出配置，以及成功、失败、关闭页面和取消时的资源清理。使用本地合成页面验证窗口尺寸、页面缩放和截图，不使用真实账号或真实发布。
