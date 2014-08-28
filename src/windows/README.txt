Creating a Windows installer
============================

Brief notes.  (-:

1/ Install WinPython (2.7.6, 32 bit) from http://winpython.sourceforge.net/
2/ Install Inno Setup from http://www.jrsoftware.org/isinfo.php
3/ Copy WinPython-32bit-2.7.6.x to Photini/src/windows/WinPython
4/ Run WinPython Control Panel.exe to remove unneeded libraries such as scipy
5/ Install Photini's dependencies
6/ Run WinPython Command Prompt.exe to open a shell, then navigate to the Photini root directory and run setup.py to build and install
7/ Check that Photini works
8/ Run Inno Setup to compile an installer