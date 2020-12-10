#define MSYS "{app}\msys2";
#define Bin "{app}\msys2\mingw32\bin";
#define SrcDir "C:\photini_temp_32"
#define SrcIcon "..\photini\data\icons\photini_win.ico"
#define Version "2020.12.0"

[Setup]
VersionInfoVersion={#Version}
VersionInfoProductTextVersion=Latest release
AppId={{55D6EC72-D14D-4A19-AE26-EECC1A6EF1EA}
AppName=Photini
AppVerName=Photini
AppPublisher=Jim Easterbrook
AppPublisherURL=https://github.com/jim-easterbrook/Photini
AppCopyright=Copyright (C) 2012-20 Jim Easterbrook
DefaultDirName={autopf}\Photini
DefaultGroupName=Photini
AllowNoIcons=yes
OutputBaseFilename=photini-win32-{#Version}
OutputDir=..\..\dist
Compression=lzma
SolidCompression=yes
LicenseFile=..\..\LICENSE.txt
InfoBeforeFile=info.txt
SetupIconFile={#SrcIcon}
UninstallDisplayIcon={app}\icon.ico
ExtraDiskSpaceRequired=1568000000

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; \
  Flags: unchecked

[Files]
Source: "{#SrcDir}\*"; DestDir: "{#MSYS}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
Source: {#SrcIcon}; DestDir: "{app}\icon.ico"; Flags: ignoreversion
Source: "install_photini_32.cmd"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Photini"; Filename: "{#Bin}\photini.exe"; \
  Comment: "Photo metadata editor"; IconFileName: {app}\icon.ico
Name: "{group}\Photini documentation"; Filename: "https://photini.readthedocs.io/"
Name: "{group}\MinGW"; Filename: "{app}\msys2\mingw32.exe"; \
  Comment: "MSYS2 command shell"; IconFileName: {app}\msys2\mingw32.ico
Name: "{commondesktop}\Photini"; Filename: "{#Bin}\photini.exe"; \
  Comment: "Photo metadata editor"; IconFileName: {app}\icon.ico; Tasks: desktopicon

[Types]
Name: "custom"; Description: "Custom installation"; Flags: iscustom

[Components]
Name: "upload"; Description: "Upload to photo sharing services"; Types: custom; \
  ExtraDiskSpaceRequired: 1450539
Name: "upload\flickr"; Description: "Flickr uploader"; Types: custom; \
  ExtraDiskSpaceRequired: 428238; Flags: dontinheritcheck
Name: "upload\google"; Description: "Google Photos uploader"; Types: custom; \
  ExtraDiskSpaceRequired: 0; Flags: dontinheritcheck
Name: "spell"; Description: "Spelling checker"; Types: custom; \
  ExtraDiskSpaceRequired: 286778209; Flags: checkablealone
Name: "spell\en"; Description: "English dictionaries"; Types: custom; \
  ExtraDiskSpaceRequired: 4275851; Flags: dontinheritcheck
Name: "spell\fr"; Description: "French dictionaries"; Types: custom; \
  ExtraDiskSpaceRequired: 17766440; Flags: dontinheritcheck
Name: "spell\de"; Description: "German dictionaries"; Types: custom; \
  ExtraDiskSpaceRequired: 6051212; Flags: dontinheritcheck
Name: "spell\ru"; Description: "Russian dictionary"; Types: custom; \
  ExtraDiskSpaceRequired: 5906396; Flags: dontinheritcheck
Name: "spell\es"; Description: "Spanish dictionary"; Types: custom; \
  ExtraDiskSpaceRequired: 1468643; Flags: dontinheritcheck
Name: "ffmpeg"; Description: "Video file reading"; Types: custom; \
  ExtraDiskSpaceRequired: 154102022

[Code]
function GetInstallOptions(Param: String): String;
begin
  Result := WizardSelectedComponents(False);
end;

[Run]
Filename: "{app}\install_photini_32.cmd"; Parameters: {code:GetInstallOptions}; \
  StatusMsg: "Installing Photini..."
Filename: "{#Bin}\photini.exe"; \
  Description: "{cm:LaunchProgram,Photini}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{#MSYS}"
