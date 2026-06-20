@echo off
echo =====================================================================
echo           Abstract Finder - Setup and Launcher Script
echo =====================================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python version 3.8 or higher and check Add Python to PATH.
    echo.
    pause
    exit /b 1
)

:: Create virtual environment if it doesn't exist
if not exist venv (
    echo [INFO] Virtual environment 'venv' not found. Creating it now...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [SUCCESS] Virtual environment created.
    echo.
)

:: Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)
echo [SUCCESS] Virtual environment activated.
echo.

:: Install / Update dependencies
echo [INFO] Installing/updating project requirements...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo [SUCCESS] Requirements verified and up-to-date.
echo.

:: Apply database migrations
echo [INFO] Applying database migrations...
python manage.py migrate
if %errorlevel% neq 0 (
    echo [ERROR] Failed to run database migrations.
    pause
    exit /b 1
)
echo [SUCCESS] Migrations applied.
echo.

:: Run Django server
echo [INFO] Starting Django development server...
echo.
echo =====================================================================
echo   Abstract Finder is starting!
echo   Open your browser and navigate to: http://127.0.0.1:8000/
echo   To stop the server, press Ctrl+C or close this window.
echo =====================================================================
echo.
python manage.py runserver

pause
