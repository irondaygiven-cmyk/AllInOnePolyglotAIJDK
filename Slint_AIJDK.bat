@echo off
cd /d "%~dp0"

if not exist ".venv" (
    echo Virtual environment not found. Please run AIDK_in.bat first.
    pause
    exit /b 1
)

powershell.exe -ExecutionPolicy Bypass -Command "& '.\.venv\Scripts\Activate.ps1'; python SlintAIJDK.py"
