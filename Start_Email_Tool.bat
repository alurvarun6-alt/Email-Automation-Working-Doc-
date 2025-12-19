@echo off
echo ============================================
echo    Email Automation Tool - Starting...
echo ============================================
echo.

cd /d "%~dp0email_app"

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed!
    echo.
    echo Please install Python:
    echo 1. Go to https://www.python.org/downloads/
    echo 2. Download and run the installer
    echo 3. IMPORTANT: Check "Add Python to PATH" during installation
    echo 4. Restart your computer
    echo 5. Run this script again
    echo.
    pause
    exit /b 1
)

:: Install dependencies if needed
if not exist ".deps_installed" (
    echo Installing dependencies (first time only)...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
    echo. > .deps_installed
    echo Dependencies installed successfully!
    echo.
)

echo Starting the Email Tool...
echo.
echo ============================================
echo    The tool will open in your browser.
echo    Keep this window open while using it.
echo    Close this window when you're done.
echo ============================================
echo.

:: Open browser after a short delay
start "" "http://localhost:5000"

:: Start the Flask app
python app.py
