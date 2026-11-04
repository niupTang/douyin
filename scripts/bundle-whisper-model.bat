@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0\.."

if not defined HF_HOME set "HF_HOME=E:\DevCache\huggingface"
set "SOURCE=%HF_HOME%\hub\models--Systran--faster-whisper-base"
if defined HUGGINGFACE_HUB_CACHE set "SOURCE=%HUGGINGFACE_HUB_CACHE%\models--Systran--faster-whisper-base"
set "TARGET=%CD%\build-resources\huggingface\hub\models--Systran--faster-whisper-base"

call :validate "%TARGET%"
if not errorlevel 1 (
  echo Using staged faster-whisper-base in %TARGET%.
  exit /b 0
)

call :validate "%SOURCE%"
if errorlevel 1 (
  echo Missing or incomplete model in "%SOURCE%".
  echo Set HF_HOME or HUGGINGFACE_HUB_CACHE to an E drive model cache before packaging.
  exit /b 1
)

if not exist "%TARGET%" mkdir "%TARGET%"
robocopy "%SOURCE%" "%TARGET%" /E /NFL /NDL /NJH /NJS /NP
if errorlevel 8 exit /b %errorlevel%
call :validate "%TARGET%"
if errorlevel 1 exit /b 1
echo faster-whisper-base bundled into %TARGET%.
exit /b 0

:validate
if not exist "%~1\refs\main" exit /b 1
set "MODEL_REV="
set /p MODEL_REV=<"%~1\refs\main"
if not defined MODEL_REV exit /b 1
for %%F in (config.json model.bin tokenizer.json vocabulary.txt) do (
  if not exist "%~1\snapshots\%MODEL_REV%\%%F" exit /b 1
  for %%G in ("%~1\snapshots\%MODEL_REV%\%%F") do if %%~zG LEQ 0 exit /b 1
)
exit /b 0
