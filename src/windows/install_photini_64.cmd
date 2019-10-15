@ECHO OFF
SETLOCAL

SET bash=msys2\usr\bin\env.exe MSYSTEM=MINGW64 /bin/bash -l -c
SET group=mingw-w64-x86_64

%bash% "qtbinpatcher --nobackup --qt-dir=/mingw64/bin || sleep 300"

%bash% "python3 -m pip install -U --no-cache-dir --disable-pip-version-check photini || sleep 300"

FOR %%G IN (%*) DO (
  IF %%G==upload (
    %bash% "python3 -m pip install -U --no-cache-dir --disable-pip-version-check requests-oauthlib keyring || sleep 300"
  )
  IF %%G==upload\flickr (
    %bash% "python3 -m pip install -U --no-cache-dir --disable-pip-version-check flickrapi || sleep 300"
  )
  IF %%G==spell (
    %bash% "pacman -S --noconfirm %group%-gspell || sleep 300"
  )
  IF %%G==spell\en (
    %bash% "pacman -S --noconfirm %group%-aspell-en || sleep 300"
  )
  IF %%G==spell\fr (
    %bash% "pacman -S --noconfirm %group%-aspell-fr || sleep 300"
  )
  IF %%G==spell\de (
    %bash% "pacman -S --noconfirm %group%-aspell-de || sleep 300"
  )
  IF %%G==spell\ru (
    %bash% "pacman -S --noconfirm %group%-aspell-ru || sleep 300"
  )
  IF %%G==spell\es (
    %bash% "pacman -S --noconfirm %group%-aspell-es || sleep 300"
  )
  IF %%G==ffmpeg (
    %bash% "pacman -S --noconfirm %group%-ffmpeg || sleep 300"
  )
)

%bash% "pacman -Scc --noconfirm"
