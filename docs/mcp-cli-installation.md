# Sunbird MCP CLI 安装与使用

Sunbird MCP CLI 是桌面程序本地服务的命令行客户端。Windows 用户需要 Python 3.9 或更新版本，并先启动、激活包含 CLI 令牌同步功能的 Sunbird 桌面程序。

## 安装

发行包目录中的 wheel 文件可以复制给其他用户。用户在 PowerShell 中运行：

```powershell
py -m pip install --user .\sunbird_mcp_cli-0.1.1-py3-none-any.whl
```

如果提示找不到 `sunbird-mcp`，关闭并重新打开终端，或把 Python 用户脚本目录加入 `PATH`。查看目录：

```powershell
py -m site --user-base
```

命令位于返回目录下的 `Scripts` 文件夹。

## 使用

先启动 Sunbird 桌面程序并完成许可证激活，然后在 PowerShell 运行：

```powershell
sunbird-mcp list
sunbird-mcp invoke collect_douyin_account --args '{"homepage_url":"https://www.douyin.com/user/...","max_videos":20}'
```

CLI 默认连接 `http://127.0.0.1:5409`。桌面程序激活或续期许可证时，会把短期访问令牌同步到 `%APPDATA%\Sunbird MCP\config.json`。该令牌由本机桌面程序管理，通常不需要手工配置；令牌过期时重新启动桌面程序后再试。

也可以显式指定后端和令牌：

```powershell
$env:SAU_TOKEN = "<访问令牌>"
sunbird-mcp --url http://127.0.0.1:5409 list
```

## 生成发行包

在仓库根目录执行：

```powershell
.\scripts\build_mcp_cli.ps1
```

生成的 wheel 位于 `release-cli`。把 wheel 和本说明发给用户即可；CLI 令牌同步也需要更新后的桌面程序版本。发布到 PyPI 需要项目维护者的发布账号，本仓库脚本只负责生成安装包。
