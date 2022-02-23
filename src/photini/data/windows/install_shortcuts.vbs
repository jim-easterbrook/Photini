Set options = WScript.Arguments.Named
Set args = WScript.Arguments.Unnamed
strTargetPath = args(0)
strIconPath = args(1)
strSystemPrefix = args(2)

On Error Resume Next

Set objShell = WScript.CreateObject("Wscript.Shell")

'Attempt to read registry to find out if we have administrator rights
objShell.RegRead("HKEY_USERS\S-1-5-19\Environment\TEMP")
If Err.Number <> 0 Then
  'Use this user's start menu and desktop
  Err.Clear
  strDesktop = objShell.SpecialFolders("Desktop")
  strGroup = objShell.SpecialFolders("StartMenu") & "\Photini"
Else
  'Use all users' start menu and desktop
  strDesktop = objShell.SpecialFolders("AllUsersDesktop")
  strGroup = objShell.SpecialFolders("AllUsersStartMenu") & "\Photini"
End If

strDesktopLink = strDesktop & "\Photini.lnk"
strShortcutLink = strGroup & "\Photini.lnk"
strDocumentationLink = strGroup & "\Photini documentation.url"

Set FSO = WScript.CreateObject("Scripting.FileSystemObject")

If options.Exists("remove") Then
    'Delete shortcut files
    If FSO.FileExists(strDesktopLink) Then
        WScript.Echo "Deleting " & strDesktopLink
        FSO.DeleteFile(strDesktopLink)
        If Err.Number <> 0 then WScript.Quit Err.Number
    End If
    If FSO.FileExists(strShortcutLink) Then
        WScript.Echo "Deleting " & strShortcutLink
        FSO.DeleteFile(strShortcutLink)
        If Err.Number <> 0 then WScript.Quit Err.Number
    End If
    If FSO.FolderExists(strGroup) Then
        WScript.Echo "Deleting " & strGroup
        FSO.DeleteFolder(strGroup)
    End If
    WScript.Quit Err.Number
End If

'Create start menu group
If Not FSO.FolderExists(strGroup) Then
    WScript.Echo "Creating " & strGroup
    FSO.CreateFolder(strGroup)
    If Err.Number <> 0 then WScript.Quit Err.Number
End If

'Create program desktop shortcut
WScript.Echo "Creating " & strDesktopLink
Set objShortcut = objShell.CreateShortcut(strDesktopLink)
objShortcut.TargetPath = strTargetPath
objShortcut.Description = "Photini metadata editor"
objShortcut.IconLocation = strIconPath
objShortcut.Save
If Err.Number <> 0 then WScript.Quit Err.Number

'Create program start menu shortcut
WScript.Echo "Creating " & strShortcutLink
Set objShortcut = objShell.CreateShortcut(strShortcutLink)
objShortcut.TargetPath = strTargetPath
objShortcut.Description = "Photini metadata editor"
objShortcut.IconLocation = strIconPath
objShortcut.Save
If Err.Number <> 0 then WScript.Quit Err.Number

'Create documentation start menu shortcut
WScript.Echo "Creating " & strDocumentationLink
Set objShortcut = objShell.CreateShortcut(strDocumentationLink)
objShortcut.TargetPath = "https://photini.readthedocs.io/"
objShortcut.Save
If Err.Number <> 0 then WScript.Quit Err.Number
