#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2024  Jim Easterbrook  jim@jim-easterbrook.me.uk
#
#  This file is part of Photini.
#
#  Photini is free software: you can redistribute it and/or modify it
#  under the terms of the GNU General Public License as published by the
#  Free Software Foundation, either version 3 of the License, or (at
#  your option) any later version.
#
#  Photini is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Photini.  If not, see <http://www.gnu.org/licenses/>.

import sys

import win32com.client

def post_install(exec_path, icon_path, remove):
    shell = win32com.client.Dispatch("WScript.Shell")
    # test for administrator rights
    try:
        shell.RegRead("HKEY_USERS\S-1-5-19\Environment\TEMP")
        # running as administrator
        desktop = shell.SpecialFolders("AllUsersDesktop")
        group = shell.SpecialFolders("AllUsersStartMenu") + "\\Photini"
    except Exception:
        # running as user
        desktop = shell.SpecialFolders("Desktop")
        group = shell.SpecialFolders("StartMenu") + "\\Photini"
    desktop_link = desktop + "\\Photini.lnk"
    shortcut_link = group + "\\Photini.lnk"
    documentation_link = group + "\\Photini documentation.url"
    FSO = win32com.client.Dispatch("Scripting.FileSystemObject")
    if remove:
        for path in (desktop_link, shortcut_link, documentation_link):
            if FSO.FileExists(path):
                print('Deleting', path)
                FSO.DeleteFile(path)
        if FSO.FolderExists(group):
            print('Deleting', group)
            FSO.DeleteFolder(group)
        return 0
    if not FSO.FolderExists(group):
        print('Creating', group)
        FSO.CreateFolder(group)
    for path in (desktop_link, shortcut_link):
        print('Creating', path)
        shortcut = shell.CreateShortcut(path)
        shortcut.TargetPath = exec_path
        shortcut.Description = "Photini metadata editor"
        shortcut.IconLocation = icon_path
        shortcut.Save()
    print('Creating', documentation_link)
    shortcut = shell.CreateShortcut(documentation_link)
    shortcut.TargetPath = "https://photini.readthedocs.io/"
    shortcut.Save()
    return 0
