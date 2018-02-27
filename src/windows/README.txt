Creating a Windows installer
============================

Brief notes.  (-:

1/ Install GitHub Desktop from https://desktop.github.com/
2/ Install Inno Setup from http://www.jrsoftware.org/isinfo.php
2a/ Install Microsoft Visual C++ 2010 Redistributable Package (x86) from
    https://www.microsoft.com/en-us/download/details.aspx?id=5555
3/ Install msys2 from http://www.msys2.org/ (32 bit version)
   Update packages as instructed, then install gexiv2 (32 bit version):
   pacman -S mingw-w64-i686-gexiv2
4/ Install WinPython (3.6.x, 32 bit, Zero) from https://winpython.github.io/ to
   Photini/src/windows/WinPython
5/ (Until PyGObject for Windows is available for Python 3.6.)
   Install older WinPython (3.4.x, 32 bit, Qt5) from https://winpython.github.io/
   to WinPython-old, then install All-In-One PyGI/PyGObject for Windows from
   http://sourceforge.net/projects/pygobjectwin32/files/
   Add the WinPython-old Python as a "portable Python" installation. Select
   "Base packages", "Gexiv2", and "GSpell" packages. Run
   WinPython Command Prompt.exe to open a shell then use pip to install pyenchant.
   Copy WinPython-old/python-3.4.x/Lib/site-packages/enchant/share/enchant/myspell/*
   to WinPython-old/python-3.4.x/Lib/site-packages/gnome/share/enchant/myspell/.
   Copy WinPython-old/python-3.4.x/Lib/site-packages/gnome to
   Photini/src/windows/WinPython/python-3.6.x/Lib/site-packages
6/ Run WinPython Command Prompt.exe to open a shell, then navigate to the src/windows
   directory. Run 'python clean_winpython.py' to remove unwanted stuff and copy other
   stuff.
7/ In the same shell run 'pip install pywin32' then run
   'python WinPython\python-3.6.3\Scripts\pywin32_postinstall.py -install'
8/ Download opengl32sw-32-mesa from
   http://download.qt.io/development_releases/prebuilt/llvmpipe/windows/
   and copy it to Photini/src/windows/WinPython/python-3.6.x/DLLs
9/ In the WinPython Command shell run
   'pip install -U -I PyQt5 pgi opencv-python photini[facebook,flickr,picasa,spelling]'
   to install Photini. Test that it works as expected. Run 'python clean_winpython.py'
   again to remove large packages.
10/ Run Inno Setup to compile an installer
