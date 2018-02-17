#define PyDir "{app}\python-3.6.3"
#define Scripts "{app}\scripts"
#define SrcDir "WinPython\python-3.6.3"
#define Version "2018.2.1"

[Setup]
VersionInfoVersion={#Version}
VersionInfoProductTextVersion=Latest release
AppId={{55D6EC72-D14D-4A19-AE26-EECC1A6EF1EA}
AppName=Photini
AppVerName=Photini
AppPublisher=Jim Easterbrook
AppPublisherURL=https://github.com/jim-easterbrook/Photini
AppCopyright=Copyright (C) 2012-18 Jim Easterbrook
DefaultDirName={pf}\Photini
DefaultGroupName=Photini
AllowNoIcons=yes
OutputBaseFilename=photini-win32-{#Version}
OutputDir=installers
Compression=lzma
SolidCompression=yes
LicenseFile=..\..\LICENSE.txt
InfoBeforeFile=info.txt
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\icon.ico
ExtraDiskSpaceRequired=308000000

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; \
  Flags: unchecked

[Files]
; Most of the useful files from WinPython
Source: "{#SrcDir}\*"; DestDir: "{#PyDir}"; \
  Excludes: "*.pyc,\DLLs\t*86t.dll,\Lib\site-packages,\Doc,\include,\Logs,\tcl,\Tools"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SrcDir}\Lib\site-packages\*"; DestDir: "{#PyDir}\Lib\site-packages"; \
  Excludes: "*.pyc,\gnome"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
; Useful stuff from the gnome directory
Source: "{#SrcDir}\Lib\site-packages\gnome\share\enchant\*"; \
  DestDir: "{#PyDir}\Lib\site-packages\gnome\share\enchant"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SrcDir}\Lib\site-packages\gnome\*"; DestDir: "{#PyDir}\Lib\site-packages\gnome"; \
  Excludes: "*.exe,\share"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
; Other odds and ends
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "WinPython\WinPython Command Prompt.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "WinPython\scripts\*"; DestDir: "{#Scripts}"; Flags: ignoreversion
Source: "install_photini.bat"; DestDir: "{#Scripts}"; Flags: ignoreversion
Source: "winpython.ini"; DestDir: "{app}\settings"; Flags: ignoreversion
; Some users' systems may not have MSVC redistributable installed
Source: "C:\WINDOWS\SysWOW64\msvcr100.dll"; DestDir: "{#PyDir}"; Flags: ignoreversion

[Icons]
Name: "{group}\Photini"; Filename: "{#PyDir}\pythonw.exe"; \
  Parameters: "-m photini.editor"; Comment: "Photo metadata editor"; IconFileName: {app}\icon.ico
Name: "{group}\Photini documentation"; Filename: "http://photini.readthedocs.io/"
Name: "{group}\upgrade Photini"; Filename: "{#Scripts}\install_photini.bat"
Name: "{commondesktop}\Photini"; Filename: "{#PyDir}\pythonw.exe"; \
  Parameters: "-m photini.editor"; Comment: "Photo metadata editor"; \
  IconFileName: {app}\icon.ico; Tasks: desktopicon

[Run]
Filename: "{#Scripts}\install_photini.bat"; \
  StatusMsg: "Installing PyPI packages..."; Flags: hidewizard
Filename: "{#PyDir}\pythonw.exe"; Parameters: "-m photini.editor"; \
  Description: "{cm:LaunchProgram,Photini}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{#PyDir}"
