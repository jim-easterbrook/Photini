[Setup]
AppId={{55D6EC72-D14D-4A19-AE26-EECC1A6EF1EA}
AppName=Photini
AppVerName=Photini (latest version)
AppPublisher=Jim Easterbrook
AppPublisherURL=https://github.com/jim-easterbrook/Photini
AppSupportURL=https://github.com/jim-easterbrook/Photini
AppUpdatesURL=https://github.com/jim-easterbrook/Photini
DefaultDirName={pf}\Photini
DefaultGroupName=Photini
AllowNoIcons=yes
OutputBaseFilename=photini-win32-setup
OutputDir=installers
Compression=lzma
SolidCompression=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "WinPython\python-2.7.6\*"; DestDir: "{app}"; Excludes: "*.pyc,appdirs*,gdata*,photini*,\Doc,\include,\Logs,\share,\tcl,\Tools"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Photini"; Filename: "{app}\Scripts\photini.exe"
Name: "{commondesktop}\Photini"; Filename: "{app}\Scripts\photini.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Scripts\pip.exe"; Parameters: "install appdirs"; StatusMsg: "Installing appdirs..."
Filename: "{app}\Scripts\pip.exe"; Parameters: "install gdata"; StatusMsg: "Installing gdata..."
Filename: "{app}\Scripts\pip.exe"; Parameters: "install photini"; StatusMsg: "Installing Photini..."
Filename: "{app}\Scripts\photini.exe"; Description: "{cm:LaunchProgram,Photini}"; Flags: nowait postinstall skipifsilent
