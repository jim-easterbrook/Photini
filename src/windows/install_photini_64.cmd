@ECHO OFF
SETLOCAL

SET bash=msys2\usr\bin\env.exe MSYSTEM=MINGW64 /bin/bash -l -c

%bash% "pacman -Syu --noconfirm || sleep 300"

%bash% "pacman -Su --noconfirm || sleep 300"

%bash% "pacman -S --noconfirm $MINGW_PACKAGE_PREFIX-{gexiv2,python-gobject,python-pyqt5,python-pip} || sleep 300"

%bash% "python -m pip install -U --no-cache-dir --disable-pip-version-check photini gpxpy || sleep 300"

FOR %%G IN (%*) DO (
  IF %%G==upload (
    %bash% "python -m pip install -U --no-cache-dir --disable-pip-version-check requests-oauthlib keyring || sleep 300"
  )
  IF %%G==upload\flickr (
    %bash% "python -m pip install -U --no-cache-dir --disable-pip-version-check flickrapi || sleep 300"
  )
  IF %%G==spell (
    %bash% "pacman -S --noconfirm $MINGW_PACKAGE_PREFIX-gspell || sleep 300"
  )
  IF %%G==spell\en (
    %bash% "pacman -S --noconfirm $MINGW_PACKAGE_PREFIX-aspell-en || sleep 300"
  )
  IF %%G==spell\fr (
    %bash% "pacman -S --noconfirm $MINGW_PACKAGE_PREFIX-aspell-fr || sleep 300"
  )
  IF %%G==spell\de (
    %bash% "pacman -S --noconfirm $MINGW_PACKAGE_PREFIX-aspell-de || sleep 300"
  )
  IF %%G==spell\ru (
    %bash% "pacman -S --noconfirm $MINGW_PACKAGE_PREFIX-aspell-ru || sleep 300"
  )
  IF %%G==spell\es (
    %bash% "pacman -S --noconfirm $MINGW_PACKAGE_PREFIX-aspell-es || sleep 300"
  )
  IF %%G==ffmpeg (
    %bash% "pacman -S --noconfirm $MINGW_PACKAGE_PREFIX-ffmpeg || sleep 300"
  )
)

%bash% "pacman -Scc --noconfirm"
