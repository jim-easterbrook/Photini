Creating a Windows installer
============================

Brief notes.  (-:

1/ Install Windows SDK from http://www.microsoft.com/en-us/download/details.aspx?id=8279
   Unselect everything except the VisualC redistributable and the native code development
   tools (to get the signing tool)
2/ Install GitHub Desktop from https://desktop.github.com/
3/ Install Inno Setup from http://www.jrsoftware.org/isinfo.php
   With the "Tools -> Configure Sign Tools..." menu add a tool as follows:
   name: normal
   command: "C:\Program Files\Microsoft SDKs\Windows\v7.1\Bin\signtool.exe" sign /v /f "C:\Users\Jim\My Documents\Certificates\photini_SPC.pfx" $f
4/ Install msys2 from http://www.msys2.org/ (32 bit version)
   Update packages as instructed, then install gexiv2 (32 bit version):
   pacman -S mingw-w64-i686-gexiv2
5/ Install WinPython (3.6.x, 32 bit, Zero) from https://winpython.github.io/ to
   Photini/src/windows/WinPython
6/ (Until PyGObject for Windows is available for Python 3.6.)
   Install older WinPython (3.4.x, 32 bit, Qt5) from https://winpython.github.io/ to
   WinPython-old, then install All-In-One PyGI/PyGObject for Windows from
   http://sourceforge.net/projects/pygobjectwin32/files/
   Add the WinPython-old Python as a "portable Python" installation. Select "Base packages"
   and "Gexiv2" packages, then "Enchant-extra-dicts" non-GNOME library. Copy
   WinPython-old/python-3.4.x/Lib/site-packages/gnome to
   Photini/src/windows/WinPython/python-3.6.x/Lib/site-packages
7/ Edit Photini/src/windows/WinPython/settings/winpython.ini and add the following line:
   PATH = %WINPYDIR%\Lib\site-packages\gnome;%PATH%
8/ Run WinPython Command Prompt.exe to open a shell, then navigate to the src/windows
   directory. Run 'python clean_winpython.py' to remove unwanted stuff and copy other
   stuff.
9/ In the same shell run 'pip install pywin32' then run
   'python WinPython\python-3.6.3\Scripts\pywin32_postinstall.py -install'
10/ Download opengl32sw-32-mesa from
    http://download.qt.io/development_releases/prebuilt/llvmpipe/windows/
    and copy it to Photini/src/windows/WinPython/python-3.6.x/DLLs
11/ In the WinPython Command shell run
    'pip install -U -I PyQt5 pgi opencv-python photini[facebook,flickr,picasa,spelling]'
    to install Photini. Test that it works as expected. Run 'python clean_winpython.py'
    again to remove large packages.
12/ Run Inno Setup to compile an installer
