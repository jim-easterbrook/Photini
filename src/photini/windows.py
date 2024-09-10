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

import win32api
import win32com.client
import win32con


# See https://learn.microsoft.com/en-us/windows/win32/shell/app-registration
# for registry entries

def post_install(exec_path, icon_path, remove, generic_name):
    shell = win32com.client.Dispatch("WScript.Shell")
    # test for administrator rights
    all_users = False
    try:
        shell.RegRead("HKEY_USERS\S-1-5-19\Environment\TEMP")
        all_users = True
    except Exception:
        pass
    if all_users:
        group = shell.SpecialFolders("AllUsersStartMenu")
        desktop_link = shell.SpecialFolders("AllUsersDesktop")
        root_key = win32con.HKEY_LOCAL_MACHINE
        root_name = 'HKEY_LOCAL_MACHINE'
    else:
        group = shell.SpecialFolders("StartMenu")
        desktop_link = shell.SpecialFolders("Desktop")
        root_key = win32con.HKEY_CURRENT_USER
        root_name = 'HKEY_CURRENT_USER'
    group += r"\Photini"
    desktop_link += r"\Photini.lnk"
    shortcut_link = group + r"\Photini.lnk"
    documentation_link = group + r"\Photini documentation.url"
    reg_name = 'photini.exe'
    applications_key = r'Software\Classes\Applications'
    app_paths_key = r'Software\Microsoft\Windows\CurrentVersion\App Paths'
    FSO = win32com.client.Dispatch("Scripting.FileSystemObject")
    if remove:
        for path in (desktop_link, shortcut_link, documentation_link):
            if FSO.FileExists(path):
                print('Deleting', path)
                FSO.DeleteFile(path)
        if FSO.FolderExists(group):
            print('Deleting', group)
            FSO.DeleteFolder(group)
        print('Updating registry')
        for path in (applications_key, app_paths_key):
            print('Deleting', r'{}\{}\{}'.format(root_name, path, reg_name))
            try:
                key = win32api.RegOpenKeyEx(
                    root_key, path, 0, win32con.KEY_ALL_ACCESS)
                win32api.RegDeleteTree(key, reg_name)
            except Exception as ex:
                print(str(ex))
        return 0
    if not FSO.FolderExists(group):
        print('Creating', group)
        FSO.CreateFolder(group)
    for path in (desktop_link, shortcut_link):
        print('Writing', path)
        shortcut = shell.CreateShortcut(path)
        shortcut.TargetPath = exec_path
        shortcut.Description = generic_name
        shortcut.IconLocation = icon_path
        shortcut.Save()
    print('Writing', documentation_link)
    shortcut = shell.CreateShortcut(documentation_link)
    shortcut.TargetPath = "https://photini.readthedocs.io/"
    shortcut.Save()
    print('Updating registry')
    print('Writing', r'{}\{}\{}'.format(root_name, app_paths_key, reg_name))
    key = win32api.RegCreateKey(root_key, r'{}\{}'.format(
        app_paths_key, reg_name))
    win32api.RegSetValueEx(key, None, 0, win32con.REG_SZ, exec_path)
    path = exec_path.replace(r'\photini.exe', '')
    path += ';' + path.replace(r'\Scripts', '')
    win32api.RegSetValueEx(key, 'Path', 0, win32con.REG_SZ, path)
    print('Writing', r'{}\{}\{}'.format(root_name, applications_key, reg_name))
    key = win32api.RegCreateKey(root_key, r'{}\{}\shell\open\command'.format(
        applications_key, reg_name))
    win32api.RegSetValue(key, None, win32con.REG_SZ, exec_path + ' "%1"')
    key = win32api.RegCreateKey(root_key, r'{}\{}\SupportedTypes'.format(
        applications_key, reg_name))
    for ext in ('.jpg', '.jpeg', '.jpe', '.jfif', '.gif', '.tif', '.tiff',
                '.png', '.xmp'):
        win32api.RegSetValueEx(key, ext, 0, win32con.REG_SZ, '')
    return 0
