@echo off
:: Seer daemon installer for Windows
:: Requires Python 3.10+ (https://python.org) and Ollama (https://ollama.com)

echo.
echo  Seer - Local AI Image Descriptions
echo  ====================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found.
    echo  Download from: https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo  [1/3] Installing Python dependencies...
pip install fastapi uvicorn --quiet
if errorlevel 1 (
    echo  [ERROR] pip install failed.
    pause
    exit /b 1
)

:: Check Ollama
ollama --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [2/3] Ollama not found.
    echo  Download from: https://ollama.com/download
    echo  Install Ollama, then run this script again.
    pause
    exit /b 1
)

echo  [2/3] Pulling vision model (moondream ~1.7 GB)...
echo  This will take a few minutes on first run.
ollama pull moondream
if errorlevel 1 (
    echo  [ERROR] Failed to pull model. Is Ollama running?
    echo  Start Ollama from the system tray, then try again.
    pause
    exit /b 1
)

:: Create startup script in same folder
echo  [3/3] Creating seer-start.bat...
set SCRIPT_DIR=%~dp0
(
    echo @echo off
    echo echo Starting Seer daemon...
    echo python "%SCRIPT_DIR%server.py" ollama --model moondream
) > "%SCRIPT_DIR%seer-start.bat"

echo.
echo  Done! To start Seer:
echo    Double-click: %SCRIPT_DIR%seer-start.bat
echo.
echo  To start automatically with Windows:
echo    Press Win+R, type: shell:startup
echo    Copy seer-start.bat into that folder.
echo.
pause
