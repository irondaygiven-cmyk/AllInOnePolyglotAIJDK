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
REM Bundled wheels (this folder):
REM   setuptools-82.0.1-py3-none-any.whl                                    (universal)
REM   huggingface_hub-0.36.2-py3-none-any.whl                               (universal)
REM   llama_cpp_python-0.1.66+cu121-cp311-cp311-win_amd64.whl               (Windows x64, CUDA 12.1)
REM   torchvision-0.21.0-cp311-cp311-win_amd64.whl                          (Windows x64)
REM External wheels (H:\Models-D1\wheels\):
REM   pip-26.0.1-py3-none-any.whl                                            (universal)
REM   idna-3.11-py3-none-any.whl                                             (universal)
REM   numpy-1.26.4-cp311-cp311-win_amd64.whl                                (Windows x64)
REM   ml_dtypes-0.5.4-cp311-cp311-win_amd64.whl                            (Windows x64)
REM   pillow-10.4.0-cp311-cp311-win_amd64.whl                               (Windows x64)
REM   kiwisolver-1.5.0-cp311-cp311-win_amd64.whl                            (Windows x64)
REM   fonttools-4.62.1-cp311-cp311-win_amd64.whl                            (Windows x64)
REM   cython-3.2.4-cp311-cp311-win_amd64.whl                                (Windows x64)
REM   tokenizers-0.19.1-cp311-none-win_amd64.whl                            (Windows x64)
REM   transformers-4.44.0-py3-none-any.whl                                   (universal)
REM   diffusers-0.30.0-py3-none-any.whl                                      (universal)
REM   xformers-0.0.35-py39-none-win_amd64.whl                               (Windows x64)
REM   mediapipe-0.10.33-py3-none-win_amd64.whl                              (Windows x64)
REM   pywin32-311-cp311-cp311-win_amd64.whl                                  (Windows x64)
REM   flask-3.1.3-py3-none-any.whl                                           (universal)
REM   flask_cors-6.0.2-py3-none-any.whl                                      (universal)
REM   fastapi-0.115.0-py3-none-any.whl                                       (universal)
REM   onnx-1.21.0-cp311-cp311-win_amd64.whl                                 (Windows x64)
REM   onnxruntime-1.24.4-cp311-cp311-win_amd64.whl                          (Windows x64)

powershell.exe -ExecutionPolicy Bypass -NoExit -Command "$ErrorActionPreference = 'Stop'; try { & '.\.venv\Scripts\Activate.ps1'; pip install 'H:\Models-D1\wheels\pip-26.0.1-py3-none-any.whl'; pip install --upgrade wheel; pip install setuptools-82.0.1-py3-none-any.whl; pip install 'H:\Models-D1\wheels\idna-3.11-py3-none-any.whl'; pip install 'H:\Models-D1\wheels\numpy-1.26.4-cp311-cp311-win_amd64.whl'; pip install 'H:\Models-D1\wheels\ml_dtypes-0.5.4-cp311-cp311-win_amd64.whl'; pip install 'H:\Models-D1\wheels\pillow-10.4.0-cp311-cp311-win_amd64.whl'; pip install 'H:\Models-D1\wheels\kiwisolver-1.5.0-cp311-cp311-win_amd64.whl'; pip install 'H:\Models-D1\wheels\fonttools-4.62.1-cp311-cp311-win_amd64.whl'; pip install 'H:\Models-D1\wheels\cython-3.2.4-cp311-cp311-win_amd64.whl'; pip install PySide6 requests; pip install huggingface_hub-0.36.2-py3-none-any.whl; pip install 'H:\Models-D1\wheels\tokenizers-0.19.1-cp311-none-win_amd64.whl'; pip install 'H:\Models-D1\wheels\transformers-4.44.0-py3-none-any.whl'; pip install 'H:\Models-D1\wheels\diffusers-0.30.0-py3-none-any.whl'; pip install 'H:\Models-D1\wheels\xformers-0.0.35-py39-none-win_amd64.whl'; pip install 'H:\Models-D1\wheels\mediapipe-0.10.33-py3-none-win_amd64.whl'; pip install 'H:\Models-D1\wheels\pywin32-311-cp311-cp311-win_amd64.whl'; pip install 'H:\Models-D1\wheels\flask-3.1.3-py3-none-any.whl'; pip install 'H:\Models-D1\wheels\flask_cors-6.0.2-py3-none-any.whl'; pip install 'H:\Models-D1\wheels\fastapi-0.115.0-py3-none-any.whl'; pip install llama_cpp_python-0.1.66+cu121-cp311-cp311-win_amd64.whl; pip install torchvision-0.21.0-cp311-cp311-win_amd64.whl; pip install 'H:\Models-D1\wheels\onnx-1.21.0-cp311-cp311-win_amd64.whl'; pip install 'H:\Models-D1\wheels\onnxruntime-1.24.4-cp311-cp311-win_amd64.whl'; pip install slint; Write-Host ''; Write-Host 'Installation complete. Run AIJDK.bat to start.' -ForegroundColor Green } catch { Write-Host ''; Write-Host \"ERROR: $_\" -ForegroundColor Red; Write-Host 'Installation failed. See above for details.' -ForegroundColor Red }"
