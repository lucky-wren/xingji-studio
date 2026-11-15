@echo off
chcp 65001 >nul 2>&1
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
title Xingji - GitHub Pages Deploy

echo.
echo   Xingji  /  One-click GitHub Pages Deploy
echo   ------------------------------------------------------------
echo   No git install, no git login, no browser sign-in, no SSH key.
echo   Only a GitHub Token (repo + workflow) is needed.
echo   Paste Token + Enter. Uploads run 12 ways in parallel (set XJ_WORKERS=8 if slow).
echo   Default repo: yourname/xingji-studio  (override: --repo owner/name)
echo   First time? Open TOKEN_GUIDE.html for the 60-second Token setup.
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo   [ERROR] Python 3 was not found in PATH.
  echo.
  echo   Install once from https://www.python.org/downloads/
  echo   IMPORTANT: tick "Add python.exe to PATH" during setup,
  echo   then close and reopen this window and double-click deploy.bat again.
  echo.
  pause
  exit /b 1
)

python --version >nul 2>&1
if errorlevel 1 (
  echo   [ERROR] "python" was found but cannot run.
  echo   This is usually the Microsoft Store shortcut, not real Python.
  echo   Install from https://www.python.org/downloads/ and tick
  echo   "Add python.exe to PATH", then double-click deploy.bat again.
  echo.
  pause
  exit /b 1
)

python "%~dp0deploy.py" %*
set RC=%errorlevel%

echo.
if "%~1"=="" (
  echo   ------------------------------------------------------------
  echo   Done. You can close this window.
  pause
)
exit /b %RC%
