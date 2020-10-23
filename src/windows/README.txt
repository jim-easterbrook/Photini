Creating Windows installers
===========================

Brief notes.  (-:

Preliminaries:
1/ Install Inno Setup from http://www.jrsoftware.org/isinfo.php

64-bit:
1/ Install 64-bit MSYS2 as normal to C:/msys64.
Using C:/msys64/mingw64.exe shell:
2/ Install pacman-contrib, $MINGW_PACKAGE_PREFIX-python and any other software you like.
3/ Run 'python src/windows/copy_base_system.py' to copy essential files only to C:/photini_temp_64.
4/ Run create_installer_64bit.iss to create the installer.
5/ Delete C:/photini_temp_64.

32-bit:
1/ Install 32-bit MSYS2 as normal to C:/msys32.
Using C:/msys32/mingw32.exe shell:
2/ Edit /etc/pacman.conf and change SigLevel to Never, then run pacman -Syu and so on.
3/ Install pacman-contrib, $MINGW_PACKAGE_PREFIX-python and any other software you like.
4/ Run 'python src/windows/copy_base_system.py' to copy essential files only to C:/photini_temp_32.
5/ Run create_installer_32bit.iss to create the installer.
6/ Delete C:/photini_temp_32.
