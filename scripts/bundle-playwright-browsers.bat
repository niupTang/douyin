@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0\.."

if not defined PLAYWRIGHT_BROWSERS_PATH set PLAYWRIGHT_BROWSERS_PATH=%CD%\ms-playwright
set SOURCE=%PLAYWRIGHT_BROWSERS_PATH%
if /I "%SOURCE:~0,2%"=="C:" (
  echo Playwright browser files must be stored outside C drive.
  exit /b 1
)
set TARGET=build-resources\ms-playwright

if not exist "%SOURCE%\chromium-1169" (
  echo Missing "%SOURCE%\chromium-1169".
  echo Run with PLAYWRIGHT_BROWSERS_PATH set to an E drive directory: playwright install chromium
  exit /b 1
)

if not exist "%SOURCE%\chromium_headless_shell-1169" (
  echo Missing "%SOURCE%\chromium_headless_shell-1169".
  echo Run with PLAYWRIGHT_BROWSERS_PATH set to an E drive directory: playwright install chromium
  exit /b 1
)

if not exist "%SOURCE%\ffmpeg-1011" (
  echo Missing "%SOURCE%\ffmpeg-1011".
  echo Run with PLAYWRIGHT_BROWSERS_PATH set to an E drive directory: playwright install chromium
  exit /b 1
)

if not exist "%SOURCE%\winldd-1007\PrintDeps.exe" (
  echo Missing "%SOURCE%\winldd-1007\PrintDeps.exe".
  echo Run with PLAYWRIGHT_BROWSERS_PATH set to an E drive directory: playwright install winldd
  exit /b 1
)

if not exist "%TARGET%" mkdir "%TARGET%"

robocopy "%SOURCE%\chromium-1169" "%TARGET%\chromium-1169" /E /NFL /NDL /NJH /NJS /NP
if errorlevel 8 exit /b %errorlevel%

robocopy "%SOURCE%\chromium_headless_shell-1169" "%TARGET%\chromium_headless_shell-1169" /E /NFL /NDL /NJH /NJS /NP
if errorlevel 8 exit /b %errorlevel%

robocopy "%SOURCE%\ffmpeg-1011" "%TARGET%\ffmpeg-1011" /E /NFL /NDL /NJH /NJS /NP
if errorlevel 8 exit /b %errorlevel%

robocopy "%SOURCE%\winldd-1007" "%TARGET%\winldd-1007" /E /NFL /NDL /NJH /NJS /NP
if errorlevel 8 exit /b %errorlevel%

if not exist "%TARGET%\winldd-1007\PrintDeps.exe" (
  echo Failed to bundle "%TARGET%\winldd-1007\PrintDeps.exe".
  exit /b 1
)

echo Playwright Chromium and Windows dependencies bundled into %TARGET%.
