@echo off
echo Creating desktop shortcut for Food Bank Database...
echo.

REM Get the current directory
set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

REM Create temporary PowerShell script
echo $ws = New-Object -ComObject WScript.Shell > create_shortcut.ps1
echo $desktop = [Environment]::GetFolderPath('Desktop') >> create_shortcut.ps1
echo $shortcut = $ws.CreateShortcut("$desktop\Food Bank Database.lnk") >> create_shortcut.ps1
echo $shortcut.TargetPath = "%SCRIPT_DIR%\Start Application.bat" >> create_shortcut.ps1
echo $shortcut.WorkingDirectory = "%SCRIPT_DIR%" >> create_shortcut.ps1
echo $shortcut.Description = "I-70 Street Reach Food Bank Database" >> create_shortcut.ps1
echo $shortcut.IconLocation = "%SCRIPT_DIR%\..\assets\i70-Street-Reach-Logo-3.ico" >> create_shortcut.ps1
echo $shortcut.Save() >> create_shortcut.ps1
echo Write-Host "Shortcut created successfully" >> create_shortcut.ps1

REM Execute the PowerShell script
powershell -ExecutionPolicy Bypass -File create_shortcut.ps1

REM Clean up
del create_shortcut.ps1

if exist "%USERPROFILE%\Desktop\Food Bank Database.lnk" (
    echo.
    echo Desktop shortcut created successfully with custom icon!
    echo You can now launch the application from your desktop.
) else (
    echo.
    echo ERROR: Could not create desktop shortcut.
    echo Please try running this batch file as administrator.
)

echo.
pause
