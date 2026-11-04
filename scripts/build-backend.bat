@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0\.."
set "PYINSTALLER_CONFIG_DIR=E:\DevCache\pyinstaller"

set PYTHON=.venv\Scripts\python.exe
if not exist "%PYTHON%" (
  set PYTHON=python
  goto :python_selected
)

"%PYTHON%" -m pip --version >nul 2>nul
if errorlevel 1 set PYTHON=python

:python_selected

"%PYTHON%" -m pip show pyinstaller >nul 2>nul
if errorlevel 1 (
  "%PYTHON%" -m pip install pyinstaller
  if errorlevel 1 exit /b 1
)

"%PYTHON%" scripts\check_license_public_key.py
if errorlevel 1 exit /b 1

"%PYTHON%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onedir ^
  --name sau_backend ^
  --add-data "db/createTable.py;db" ^
  --add-data "myUtils;myUtils" ^
  --add-data "uploader;uploader" ^
  --add-data "utils;utils" ^
  --add-data "koubo_integration;koubo_integration" ^
  --add-data "sau_backend;sau_backend" ^
  --collect-all playwright ^
  --collect-submodules backend_app ^
  --collect-all yt_dlp ^
  --collect-all faster_whisper ^
  --collect-all ctranslate2 ^
  --collect-all tokenizers ^
  --collect-all huggingface_hub ^
  --collect-all keyring ^
  --collect-all sqlcipher3 ^
  sau_backend.py
