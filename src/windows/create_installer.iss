#define PyDir "{app}\python-3.4.3"
#define SrcDir "WinPython\python-3.4.3"

[Setup]
VersionInfoVersion=15.10
VersionInfoProductTextVersion=Latest release
AppId={{55D6EC72-D14D-4A19-AE26-EECC1A6EF1EA}
AppName=Photini
AppVerName=Photini
AppPublisher=Jim Easterbrook
AppPublisherURL=https://github.com/jim-easterbrook/Photini
AppCopyright=Copyright (C) 2012-15 Jim Easterbrook
DefaultDirName={pf}\Photini
DefaultGroupName=Photini
AllowNoIcons=yes
OutputBaseFilename=photini-win32-setup
OutputDir=installers
Compression=lzma
SolidCompression=yes
LicenseFile=..\..\LICENSE.txt
InfoBeforeFile=info.txt
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\icon.ico
ExtraDiskSpaceRequired=8500000
SignTool=normal

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; \
  Flags: unchecked

[Files]
Source: "{#SrcDir}\*"; DestDir: "{#PyDir}"; \
  Excludes: "*.pyc,\DLLs\t*86t.dll,\Lib\site-packages,\Lib\test,\Doc,\include,\Logs,\man,\share,\tcl,\Tools"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SrcDir}\Lib\site-packages\*"; DestDir: "{#PyDir}\Lib\site-packages"; \
  Excludes: "*.pyc,\gnome,\PyQt4"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SrcDir}\Lib\site-packages\PyQt4\*"; DestDir: "{#PyDir}\Lib\site-packages\PyQt4"; \
  Excludes: "*.exe,\doc,\examples,\qsci,\sip,\uic"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SrcDir}\Lib\site-packages\gnome\*"; DestDir: "{#PyDir}\Lib\site-packages\gnome"; \
  Excludes: "*.exe,\share"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "WinPython\WinPython Command Prompt.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Photini"; Filename: "{#PyDir}\pythonw.exe"; \
  Parameters: "-m photini.editor"; Comment: "Photo metadata editor"; IconFileName: {app}\icon.ico
Name: "{group}\Photini documentation"; Filename: "http://photini.readthedocs.org/"
Name: "{group}\upgrade Photini"; Filename: "{#PyDir}\python.exe"; \
  Parameters: "-m pip install -U -I setuptools_scm pyenchant photini[flickr,picasa]"
Name: "{commondesktop}\Photini"; Filename: "{#PyDir}\pythonw.exe"; \
  Parameters: "-m photini.editor"; Comment: "Photo metadata editor"; \
  IconFileName: {app}\icon.ico; Tasks: desktopicon

[Run]
Filename: "{#PyDir}\python.exe"; \
  Parameters: "-m pip install -U -I setuptools_scm pyenchant photini[flickr,picasa]"; \
  StatusMsg: "Installing PyPI packages..."; Flags: hidewizard
Filename: "{#PyDir}\pythonw.exe"; Parameters: "-m photini.editor"; \
  Description: "{cm:LaunchProgram,Photini}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{#PyDir}"
