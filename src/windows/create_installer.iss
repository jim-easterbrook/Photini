#define PyDir "{app}\python-3.6.3"
#define Scripts "{app}\scripts"
#define SrcDir "WinPython\python-3.6.3"
#define Version "2018.02"

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
ExtraDiskSpaceRequired=306600000

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; \
  Flags: unchecked

[Files]
Source: "{#SrcDir}\*"; DestDir: "{#PyDir}"; \
  Excludes: "*.pyc,\DLLs\t*86t.dll,\Lib\site-packages,\Doc,\include,\Logs,\tcl,\Tools"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SrcDir}\Lib\site-packages\*"; DestDir: "{#PyDir}\Lib\site-packages"; \
  Excludes: "*.pyc,\gnome"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SrcDir}\Lib\site-packages\gnome\share\enchant\*"; DestDir: "{#PyDir}\Lib\site-packages\gnome\share\enchant"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SrcDir}\Lib\site-packages\gnome\*"; DestDir: "{#PyDir}\Lib\site-packages\gnome"; \
  Excludes: "*.exe,\share"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "WinPython\WinPython Command Prompt.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "WinPython\scripts\*"; DestDir: "{#Scripts}"; Flags: ignoreversion
Source: "WinPython\settings\winpython.ini"; DestDir: "{app}\settings"; Flags: ignoreversion

[Icons]
Name: "{group}\Photini"; Filename: "{#Scripts}\Noshell.vbs"; \
  Parameters: "python -m photini.editor"; Comment: "Photo metadata editor"; IconFileName: {app}\icon.ico
Name: "{group}\Photini documentation"; Filename: "http://photini.readthedocs.io/"
Name: "{group}\upgrade Photini"; Filename: "{#PyDir}\python.exe"; \
  Parameters: "-m pip install -U PyQt5 pgi opencv-python photini[facebook,flickr,picasa,spelling]"
Name: "{commondesktop}\Photini"; Filename: "{#Scripts}\Noshell.vbs"; \
  Parameters: "python -m photini.editor"; Comment: "Photo metadata editor"; \
  IconFileName: {app}\icon.ico; Tasks: desktopicon

[Run]
Filename: "{#PyDir}\python.exe"; \
  Parameters: "-m pip install -U PyQt5 pgi opencv-python photini[facebook,flickr,picasa,spelling]"; \
  StatusMsg: "Installing PyPI packages..."; Flags: hidewizard

[UninstallDelete]
Type: filesandordirs; Name: "{#PyDir}"
