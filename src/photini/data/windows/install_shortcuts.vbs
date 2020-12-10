Set args = WScript.Arguments.Unnamed
Set options = WScript.Arguments.Named

Set objShell = WScript.CreateObject("Wscript.Shell")

If options.Exists("user") Then
  'Use this user's start menu and desktop
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
strShellLink = strGroup & "\MinGW.lnk"

On Error Resume Next

Set FSO = WScript.CreateObject("Scripting.FileSystemObject")

If options.Exists("remove") Then
    'Delete shortcut files
    If FSO.FileExists(strDesktopLink) Then FSO.DeleteFile(strDesktopLink)
    If Err.Number <> 0 then WScript.Quit Err.Number
    If FSO.FileExists(strShortcutLink) Then FSO.DeleteFile(strShortcutLink)
    If Err.Number <> 0 then WScript.Quit Err.Number
    If FSO.FileExists(strDocumentationLink) Then FSO.DeleteFile(strDocumentationLink)
    If Err.Number <> 0 then WScript.Quit Err.Number
    If FSO.FileExists(strShellLink) Then FSO.DeleteFile(strShellLink)
    If Err.Number <> 0 then WScript.Quit Err.Number
    If FSO.FolderExists(strGroup) Then FSO.DeleteFolder(strGroup)
    WScript.Quit Err.Number
End If

strTargetPath = args(0)
strIconPath = args(1)
strSystemPrefix = args(2)

If Not (options.Exists("user") Or options.Exists("elevated")) Then
    'Re-run this script as administrator
    Set appShell = CreateObject("Shell.Application")
    appShell.ShellExecute "cscript.exe", """" & WScript.ScriptFullName & """" & _
      " """ & strTargetPath & """ """ & strIconPath & """ """ & strSystemPrefix & _
      """ /elevated", , "runas", 0
    WScript.Quit Err.Number
End If

'Create start menu group
If Not FSO.FolderExists(strGroup) Then
    FSO.CreateFolder(strGroup)
    If Err.Number <> 0 then WScript.Quit Err.Number
End If

'Create program desktop shortcut
Set objShortcut = objShell.CreateShortcut(strDesktopLink)
objShortcut.TargetPath = strTargetPath
objShortcut.Description = "Photini metadata editor"
objShortcut.IconLocation = strIconPath
objShortcut.Save
If Err.Number <> 0 then WScript.Quit Err.Number

'Create program start menu shortcut
Set objShortcut = objShell.CreateShortcut(strShortcutLink)
objShortcut.TargetPath = strTargetPath
objShortcut.Description = "Photini metadata editor"
objShortcut.IconLocation = strIconPath
objShortcut.Save
If Err.Number <> 0 then WScript.Quit Err.Number

'Create documentation start menu shortcut
Set objShortcut = objShell.CreateShortcut(strDocumentationLink)
objShortcut.TargetPath = "https://photini.readthedocs.io/"
objShortcut.Save
If Err.Number <> 0 then WScript.Quit Err.Number

'Create command shell start menu shortcut
Set objShortcut = objShell.CreateShortcut(strShellLink)
objShortcut.TargetPath = strSystemPrefix & ".exe"
objShortcut.Description = "MSYS2 MinGW command shell"
objShortcut.IconLocation = strSystemPrefix & ".ico"
objShortcut.Save
If Err.Number <> 0 then WScript.Quit Err.Number
