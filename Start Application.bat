@echo off
title I-70 Street Reach Food Bank Database
echo Starting Food Bank Database Client...
python food_bank_client.py
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Failed to start application
    echo Make sure you have run install.bat first
    pause
)
