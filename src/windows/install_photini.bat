@echo off

rem check for admin permissions

net session >nul 2>&1

if NOT %errorLevel% == 0 (
    echo Please run install_photini as administrator.
    pause
    exit /b
)

rem running as admin
call "%~dp0env_for_icons.bat"

@echo on
pip install -U pgi
pip install -U opencv-python
pip install -U PyQt5
pip install -U photini[facebook,flickr,picasa,spelling]

@echo off
pause
