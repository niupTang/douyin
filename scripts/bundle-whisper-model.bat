@echo off
setlocal
cd /d "%~dp0\.."

set SOURCE=%USERPROFILE%\.cache\huggingface\hub\models--Systran--faster-whisper-base
set TARGET=build-resources\huggingface\hub\models--Systran--faster-whisper-base

if not exist "%SOURCE%" (
  echo Missing "%SOURCE%".
  echo Run a transcription once or download Systran/faster-whisper-base before packaging.
  exit /b 1
)

if exist "%TARGET%" rmdir /s /q "%TARGET%"
mkdir "%TARGET%"

robocopy "%SOURCE%" "%TARGET%" /MIR /NFL /NDL /NJH /NJS /NP
if errorlevel 8 exit /b %errorlevel%

echo faster-whisper-base bundled into %TARGET%.
