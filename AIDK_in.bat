@echo off
cd /d "%~dp0"

echo AllInOnePolyglotAIJDK - Installer
echo ===================================
echo.

REM Require Python 3.11 (win_amd64 wheels are built for cp311)
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    echo Please install Python 3.11 from https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)

echo.
echo Activating venv and installing dependencies...
echo.
REM Wheels included in this folder (Windows x64 / pure-Python):
REM   setuptools-82.0.1-py3-none-any.whl          (universal)
REM   huggingface_hub-0.36.2-py3-none-any.whl     (universal)
REM   llama_cpp_python-0.1.66+cu121-cp311-...whl  (Windows x64, CUDA 12.1)
REM   torchvision-0.21.0-cp311-cp311-win_amd64.whl (Windows x64)
REM NOTE: onnx-*.manylinux*.whl is Linux-only and is intentionally skipped.

powershell.exe -ExecutionPolicy Bypass -NoExit -Command "$ErrorActionPreference = 'Stop'; try { & '.\.venv\Scripts\Activate.ps1'; pip install --upgrade pip wheel; pip install setuptools-82.0.1-py3-none-any.whl; pip install PySide6 requests; pip install huggingface_hub-0.36.2-py3-none-any.whl; pip install llama_cpp_python-0.1.66+cu121-cp311-cp311-win_amd64.whl; pip install torchvision-0.21.0-cp311-cp311-win_amd64.whl; pip install slint; Write-Host ''; Write-Host 'Installation complete. Run AIJDK.bat to start.' -ForegroundColor Green } catch { Write-Host ''; Write-Host \"ERROR: $_\" -ForegroundColor Red; Write-Host 'Installation failed. See above for details.' -ForegroundColor Red }"
