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
4/ Install msys2 from http://www.msys2.org/ (32 bit version)
   Update packages as instructed, then install gexiv2 (32 bit version):
   pacman -S mingw-w64-i686-gexiv2
5/ Download opencv_python-3.1.0-cp34-cp34m-win32.whl from
   http://www.lfd.uci.edu/~gohlke/pythonlibs/#opencv
6/ Install WinPython (3.4.x, 32 bit, Qt5) from https://winpython.github.io/ to
   Photini/src/windows/WinPython
7/ Install All-In-One PyGI/PyGObject for Windows from
   http://sourceforge.net/projects/pygobjectwin32/files/
   Add the Photini/src/windows/WinPython Python as a "portable Python" installation
   Select "Base packages" and "Gexiv2" packages, then "Enchant-extra-dicts" non-GNOME library
8/ Run WinPython Command Prompt.exe to open a shell, then navigate to the src/windows
   directory. Run 'python clean_winpython.py' to remove unwanted stuff and copy other
   stuff.
9/ In the same shell run
   'pip install -U -I setuptools_scm pgi photini[flickr,picasa,spelling]' to install
   Photini. Test that it works as expected, then uninstall Photini:
   'pip uninstall photini'.
10/ Run Inno Setup to compile an installer
