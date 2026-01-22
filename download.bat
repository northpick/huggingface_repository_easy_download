@echo off
chcp 65001 >nul
title HF一键下载神器（便携版）

:: 1. 自动寻找便携 python（支持几乎所有命名）
set "PY="
if exist "%~dp0python\python.exe"      set "PY=%~dp0python\python.exe"
if exist "%~dp0python311\python.exe"   set "PY=%~dp0python311\python.exe"
if exist "%~dp0python312\python.exe"   set "PY=%~dp0python312\python.exe"
for /d %%i in ("%~dp0*python*") do if exist "%%i\python.exe" set "PY=%%i\python.exe"

:: 2. 如果没找到便携版，尝试系统 python
if not defined PY (
    where python >nul 2>&1
    if !errorlevel!==0 set "PY=python"
)

:: 3. 真正运行脚本
if defined PY (
    echo.
    echo 正在启动下载神器...
    "%PY%" "%~dp0download.py"
) else (
    echo.
    echo ××× 没找到 python.exe！请检查便携 python 文件夹是否和 bat 在同一级目录 ×××
    echo 正确示例：
    echo     %~dp0python\python.exe
    echo     或 %~dp0python311\python.exe
    pause
)

pause