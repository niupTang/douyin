@echo off
rem 太阳鸟自媒体自动化运营系统 - 桌面版启动
rem 双击本文件即可打开桌面窗口（无黑窗口，日志在 desktop\logs\）
cd /d "%~dp0"
start "" "D:\python\pythonw.exe" "%~dp0launcher.py"
exit /b
