@echo off
setlocal
cd /d "%~dp0\.."

if not exist "node_modules" (
  npm install
)

if not exist "sau_frontend\node_modules" (
  npm run frontend:install
)

start "Sunbird OS Frontend" cmd /c "npm run frontend:dev"
timeout /t 3 /nobreak >nul
npm run desktop:dev
