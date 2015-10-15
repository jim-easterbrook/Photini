Creating a Windows installer
============================

Brief notes.  (-:

1/ Install Windows SDK from http://www.microsoft.com/en-us/download/details.aspx?id=8279
   Unselect everything except the VisualC redistributable and the native code development tools (to get the signing tool)
2/ Install GitHub Desktop from https://desktop.github.com/
3/ Install Inno Setup from http://www.jrsoftware.org/isinfo.php
   With the "Tools -> Configure Sign Tools..." menu add a tool as follows:
   name: normal
   command: "C:\Program Files\Microsoft SDKs\Windows\v7.1\Bin\signtool.exe" sign /v /f "C:\Users\Jim\My Documents\Certificates\photini_SPC.pfx" $f
4/ Install WinPython (3.4.x, 32 bit) from https://winpython.github.io/ to Photini/src/windows/WinPython
5/ Run WinPython Control Panel.exe to remove all packages except:
   pip, pkginfo, pyqt4, pywin32, setuptools, wheel, winpython
6/ Install All-In-One PyGI/PyGObject for Windows from http://sourceforge.net/projects/pygobjectwin32/files/
   Add the Photini/src/windows/WinPython Python as a "portable Python" installation
   Select "Base packages" and "Gexiv2" packages, then "Enchant-extra-dicts" non-GNOME library
7/ Run WinPython Command Prompt.exe to open a shell, then navigate to the Photini root directory
   a/ Run "pip install -U appdirs six flickrapi keyring"
   b/ Run "python setup.py build"
   c/ Run "python setup.py install"
   d/ Run "python -m photini.editor" and make sure Photini works as it should
8/ Run WinPython Control Panel.exe to remove packages installed in step 7
9/ Run Inno Setup to compile an installer
