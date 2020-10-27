Set args = WScript.Arguments
strTargetPath = args(0)
strIconLocation = args(1)
strPrefix = args(2)

Set objShell = WScript.CreateObject("Wscript.Shell")
strDesktop = objShell.SpecialFolders("StartMenu")
strGroup = strDesktop & "\Photini"

Set FSO = WScript.CreateObject("Scripting.FileSystemObject")
If NOT (FSO.FolderExists(strGroup)) Then
    FSO.CreateFolder(strGroup)
End If

Set objShortcut = objShell.CreateShortcut(strGroup & "\Photini.lnk")
objShortcut.TargetPath = strTargetPath
objShortcut.Arguments = "-m photini.editor"
objShortcut.Description = "Photini metadata editor"
objShortcut.IconLocation = strIconLocation
objShortcut.Save

Set objShortcut = objShell.CreateShortcut(strGroup & "\Photini documentation.url")
objShortcut.TargetPath = "https://photini.readthedocs.io/"
objShortcut.Save

Set objShortcut = objShell.CreateShortcut(strGroup & "\MinGW.lnk")
objShortcut.TargetPath = strPrefix & ".exe"
objShortcut.Description = "MSYS2 MinGW command shell"
objShortcut.IconLocation = strPrefix & ".ico"
objShortcut.Save