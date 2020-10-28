Set args = WScript.Arguments
strTargetPath = args(0)
strIconLocation = args(1)
strPrefix = args(2)

Set objShell = WScript.CreateObject("Wscript.Shell")

If args.Named.Exists("user") Then
  'Use this user's start menu and desktop
  strDesktop = objShell.SpecialFolders("Desktop")
  strGroup = objShell.SpecialFolders("StartMenu") & "\Photini"
Else
  'Use all users' start menu and desktop
  strDesktop = objShell.SpecialFolders("AllUsersDesktop")
  strGroup = objShell.SpecialFolders("AllUsersStartMenu") & "\Photini"
  'Re-run this script as administrator
  If NOT args.Named.Exists("elevated") Then
    Set appShell = CreateObject("Shell.Application")
    appShell.ShellExecute "cscript.exe", """" & WScript.ScriptFullName & """" & _
      " """ & strTargetPath & """ """ & strIconLocation & """ """ & strPrefix & _
      """ /elevated", , "runas", 0
    WScript.Quit
  End If
End If

On Error Resume Next

'Create start menu group
Set FSO = WScript.CreateObject("Scripting.FileSystemObject")
If NOT FSO.FolderExists(strGroup) Then
    FSO.CreateFolder(strGroup)
    If Err.Number <> 0 then WScript.Quit Err.Number
End If

'Create program desktop shortcut
Set objShortcut = objShell.CreateShortcut(strDesktop & "\Photini.lnk")
objShortcut.TargetPath = strTargetPath
objShortcut.Arguments = "-m photini.editor"
objShortcut.Description = "Photini metadata editor"
objShortcut.IconLocation = strIconLocation
objShortcut.Save
If Err.Number <> 0 then WScript.Quit Err.Number

'Create program start menu shortcut
Set objShortcut = objShell.CreateShortcut(strGroup & "\Photini.lnk")
objShortcut.TargetPath = strTargetPath
objShortcut.Arguments = "-m photini.editor"
objShortcut.Description = "Photini metadata editor"
objShortcut.IconLocation = strIconLocation
objShortcut.Save
If Err.Number <> 0 then WScript.Quit Err.Number

'Create documentation start menu shortcut
Set objShortcut = objShell.CreateShortcut(strGroup & "\Photini documentation.url")
objShortcut.TargetPath = "https://photini.readthedocs.io/"
objShortcut.Save
If Err.Number <> 0 then WScript.Quit Err.Number

'Create command shell start menu shortcut
Set objShortcut = objShell.CreateShortcut(strGroup & "\MinGW.lnk")
objShortcut.TargetPath = strPrefix & ".exe"
objShortcut.Description = "MSYS2 MinGW command shell"
objShortcut.IconLocation = strPrefix & ".ico"
objShortcut.Save
If Err.Number <> 0 then WScript.Quit Err.Number
