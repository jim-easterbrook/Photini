Creating Windows installers
===========================

Brief notes.  (-:

Preliminaries:
1/ Install Inno Setup from http://www.jrsoftware.org/isinfo.php

64-bit:
1/ Install 64-bit MSYS2 and Photini dependencies to C:\photini64.
2/ Edit C:\photini64\etc\pacman.conf and comment out the [mingw32] section.
3/ Remove unneeded packages:
   pacman -Rdd mingw-w64-x86_64-icu-debug-libs
               mingw-w64-x86_64-tcl
               mingw-w64-x86_64-tk
4/ Run clean_mingw32-64.py to remove unneeded files.
5/ Run create_installer_64bit.iss to create the installer.

32-bit:
1/ Install 32-bit MSYS2 and Photini dependencies to C:\photini32.
2/ Edit C:\photini32\etc\pacman.conf and comment out the [mingw64] section.
3/ Remove unneeded packages:
   pacman -Rdd mingw-w64-i686-icu-debug-libs
               mingw-w64-i686-tcl
               mingw-w64-i686-tk
4/ Run clean_mingw32-64.py to remove unneeded files.
5/ Run create_installer_32bit.iss to create the installer.
