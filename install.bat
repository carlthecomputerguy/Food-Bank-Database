@echo off
echo ========================================
echo I-70 Street Reach Food Bank Database
echo Client Installation
echo ========================================
echo.

REM Create server configuration file
echo https://database.i70streetreach.com > server_config.txt

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)

echo Python found!
echo.

REM Install required packages
echo Installing required Python packages...
python -m pip install --upgrade pip
python -m pip install requests openpyxl keyring

if %errorlevel% neq 0 (
    echo.
    echo WARNING: Some packages may not have installed correctly.
    echo The application may still work, but some features might be limited.
    echo.
) else (
    echo.
    echo All packages installed successfully!
)

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Server configured to: https://database.i70streetreach.com
echo.
echo Creating desktop shortcut...

REM Get current directory path
set CURRENT_DIR=%~dp0
set CURRENT_DIR=%CURRENT_DIR:~0,-1%

REM Create temporary PowerShell script
echo $ws = New-Object -ComObject WScript.Shell > create_shortcut.ps1
echo $desktop = [Environment]::GetFolderPath('Desktop') >> create_shortcut.ps1
echo $shortcut = $ws.CreateShortcut("$desktop\Food Bank Database.lnk") >> create_shortcut.ps1
echo $shortcut.TargetPath = "%CURRENT_DIR%\Start Application.bat" >> create_shortcut.ps1
echo $shortcut.WorkingDirectory = "%CURRENT_DIR%" >> create_shortcut.ps1
echo $shortcut.Description = "I-70 Street Reach Food Bank Database" >> create_shortcut.ps1
echo $shortcut.IconLocation = "%CURRENT_DIR%\..\assets\i70-Street-Reach-Logo-3.ico" >> create_shortcut.ps1
echo $shortcut.Save() >> create_shortcut.ps1
echo Write-Host "Shortcut created successfully" >> create_shortcut.ps1

REM Execute the PowerShell script
powershell -ExecutionPolicy Bypass -File create_shortcut.ps1

REM Clean up
del create_shortcut.ps1

if exist "%USERPROFILE%\Desktop\Food Bank Database.lnk" (
    echo Desktop shortcut created successfully with custom icon!
) else (
    echo Note: Could not create desktop shortcut automatically.
    echo You can manually create a shortcut to "Start Application.bat"
)

echo.
echo You can now:
echo   1. Double-click "Food Bank Database" icon on your desktop
echo   2. Or run "Start Application.bat" from this folder
echo.
pause
