@setlocal enabledelayedexpansion && c:\python27\python.exe -x "%~f0" %* & exit /b !ERRORLEVEL!

from photini import editor
editor.main()
