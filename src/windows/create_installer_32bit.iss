#define MSYS "{app}\msys2";
#define PythonW "{app}\msys2\mingw32\bin\python3w.exe";
#define Shell "{app}\msys2\usr\bin\env.exe";
#define SrcDir "C:\photini32"
#define Version "2019.5.0"

[Setup]
VersionInfoVersion={#Version}
VersionInfoProductTextVersion=Latest release
AppId={{55D6EC72-D14D-4A19-AE26-EECC1A6EF1EA}
AppName=Photini
AppVerName=Photini
AppPublisher=Jim Easterbrook
AppPublisherURL=https://github.com/jim-easterbrook/Photini
AppCopyright=Copyright (C) 2012-19 Jim Easterbrook
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
ExtraDiskSpaceRequired=8800000

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; \
  Flags: unchecked

[Files]
Source: "{#SrcDir}\*"; DestDir: "{#MSYS}"; \
  Excludes: "\dev,\home\*,\proc,\tmp\*,\var\log\*,cache,cmake,include,pkgconfig,__pycache__,*.a,*.h,*.prl"; \
  Flags: ignoreversion recursesubdirs createallsubdirs
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Photini"; Filename: "{#PythonW}"; \
  Parameters: "-m photini.editor"; Comment: "Photo metadata editor"; \
  IconFileName: {app}\icon.ico
Name: "{group}\Photini documentation"; Filename: "https://photini.readthedocs.io/"
Name: "{commondesktop}\Photini"; Filename: "{#PythonW}"; \
  Parameters: "-m photini.editor"; Comment: "Photo metadata editor"; \
  IconFileName: {app}\icon.ico; Tasks: desktopicon

[Types]
Name: "custom"; Description: "Custom installation"; Flags: iscustom

[Components]
Name: "flickr"; Description: "Flickr uploader"; Types: custom; \
  ExtraDiskSpaceRequired: 2254271
Name: "spell"; Description: "Spelling checker"; Types: custom; \
  ExtraDiskSpaceRequired: 233381050; Flags: checkablealone
Name: "spell/en"; Description: "English dictionaries"; Types: custom; \
  ExtraDiskSpaceRequired: 5408565; Flags: dontinheritcheck
Name: "spell/fr"; Description: "French dictionaries"; Types: custom; \
  ExtraDiskSpaceRequired: 22155650; Flags: dontinheritcheck
Name: "spell/de"; Description: "German dictionaries"; Types: custom; \
  ExtraDiskSpaceRequired: 7275135; Flags: dontinheritcheck
Name: "spell/ru"; Description: "Russian dictionary"; Types: custom; \
  ExtraDiskSpaceRequired: 7332670; Flags: dontinheritcheck
Name: "spell/es"; Description: "Spanish dictionary"; Types: custom; \
  ExtraDiskSpaceRequired: 1921721; Flags: dontinheritcheck

[Run]
Filename: "{#Shell}"; \
  Parameters: "MSYSTEM=MINGW32 /bin/bash -l -c ""qtbinpatcher --nobackup --qt-dir=/mingw32/bin || sleep 300"""; \
  StatusMsg: "Configuring Qt5..."
Filename: "{#Shell}"; \
  Parameters: "MSYSTEM=MINGW32 /bin/bash -l -c ""python3 -m pip install -U --no-cache-dir --disable-pip-version-check photini || sleep 300"""; \
  StatusMsg: "Installing Photini..."
Filename: "{#Shell}"; \
  Parameters: "MSYSTEM=MINGW32 /bin/bash -l -c ""python3 -m pip install -U --no-cache-dir --disable-pip-version-check flickrapi keyring || sleep 300"""; \
  StatusMsg: "Installing Flickr uploader..."; \
  Components: flickr
Filename: "{#Shell}"; \
  Parameters: "MSYSTEM=MINGW32 /bin/bash -l -c ""pacman -S --noconfirm mingw-w64-i686-gspell || sleep 300"""; \
  StatusMsg: "Installing Spelling checker..."; \
  Components: spell
Filename: "{#Shell}"; \
  Parameters: "MSYSTEM=MINGW32 /bin/bash -l -c ""pacman -S --noconfirm mingw-w64-i686-aspell-en || sleep 300"""; \
  StatusMsg: "Installing English dictionaries..."; \
  Components: spell/en
Filename: "{#Shell}"; \
  Parameters: "MSYSTEM=MINGW32 /bin/bash -l -c ""pacman -S --noconfirm mingw-w64-i686-aspell-fr || sleep 300"""; \
  StatusMsg: "Installing French dictionaries..."; \
  Components: spell/fr
Filename: "{#Shell}"; \
  Parameters: "MSYSTEM=MINGW32 /bin/bash -l -c ""pacman -S --noconfirm mingw-w64-i686-aspell-de || sleep 300"""; \
  StatusMsg: "Installing German dictionaries..."; \
  Components: spell/de
Filename: "{#Shell}"; \
  Parameters: "MSYSTEM=MINGW32 /bin/bash -l -c ""pacman -S --noconfirm mingw-w64-i686-aspell-ru || sleep 300"""; \
  StatusMsg: "Installing Russian dictionaries..."; \
  Components: spell/ru
Filename: "{#Shell}"; \
  Parameters: "MSYSTEM=MINGW32 /bin/bash -l -c ""pacman -S --noconfirm mingw-w64-i686-aspell-es || sleep 300"""; \
  StatusMsg: "Installing Spanish dictionaries..."; \
  Components: spell/es
Filename: "{#PythonW}"; Parameters: "-m photini.editor"; \
  Description: "{cm:LaunchProgram,Photini}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{#MSYS}"
