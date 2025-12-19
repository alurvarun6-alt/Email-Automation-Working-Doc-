@echo off
echo.
echo ============================================
echo    Email Automation Tool
echo ============================================
echo.

cd /d "%~dp0email_app"

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed!
    echo.
    echo Please install Python from: https://www.python.org/downloads/
    echo IMPORTANT: Check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

:: Install dependencies if needed
if not exist ".deps_installed" (
    echo Installing dependencies (first time only, please wait)...
    echo.
    pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
    echo. > .deps_installed
    echo Dependencies installed!
    echo.
)

echo Starting the Email Tool...
echo.
echo ============================================
echo    Opening browser to: http://localhost:5001
echo    Keep this window open while using it.
echo    Close this window when you're done.
echo ============================================
echo.

:: Open browser
start "" "http://localhost:5001"

:: Start the Flask app
python app.py
