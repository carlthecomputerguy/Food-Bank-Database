@echo off
REM I-70 Street Reach Food Bank - Network Server Launcher
REM This script starts the Flask server for network database access

setlocal enabledelayedexpansion

echo.
echo =========================================
echo Food Bank Database - Network Server
echo =========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python and try again
    pause
    exit /b 1
)

REM Install Flask and required packages if not present
echo Checking for required Python packages...
python -m pip install flask requests >nul 2>&1

if errorlevel 1 (
    echo Installing required packages (Flask, requests)...
    python -m pip install flask requests
    if errorlevel 1 (
        echo Error: Failed to install required packages
        pause
        exit /b 1
    )
)

echo Required packages installed successfully.
echo.
echo =========================================
echo Starting Network Database Server
echo =========================================
echo.
echo Server will start on: http://0.0.0.0:5000
echo.
echo Clients can connect using:
echo http://^<YOUR_COMPUTER_IP^>:5000
echo.
echo To find your computer IP, run: ipconfig
echo Look for "IPv4 Address" (e.g., 192.168.x.x)
echo.
echo Default credentials:
echo Username: admin
echo Password: foodbank2024
echo.
echo =========================================
echo.

python "%~dp0food_bank_server.py"

if errorlevel 1 (
    echo.
    echo Error: Server failed to start
    pause
    exit /b 1
)

pause
