@ECHO OFF
SETLOCAL

SET bash=msys2\usr\bin\env.exe MSYSTEM=MINGW32 /bin/bash -l -c
SET group=mingw-w64-i686

%bash% "qtbinpatcher --nobackup --qt-dir=/mingw32/bin || sleep 300"

%bash% "python3 -m pip install -U --no-cache-dir --disable-pip-version-check photini || sleep 300"

FOR %%G IN (%*) DO (
  IF %%G==flickr (
    %bash% "python3 -m pip install -U --no-cache-dir --disable-pip-version-check flickrapi keyring || sleep 300"
  )
  IF %%G==spell (
    %bash% "pacman -S --noconfirm %group%-gspell || sleep 300"
  )
  IF %%G==spell/en (
    %bash% "pacman -S --noconfirm %group%-aspell-en || sleep 300"
  )
  IF %%G==spell/fr (
    %bash% "pacman -S --noconfirm %group%-aspell-fr || sleep 300"
  )
  IF %%G==spell/de (
    %bash% "pacman -S --noconfirm %group%-aspell-de || sleep 300"
  )
  IF %%G==spell/ru (
    %bash% "pacman -S --noconfirm %group%-aspell-ru || sleep 300"
  )
  IF %%G==spell/es (
    %bash% "pacman -S --noconfirm %group%-aspell-es || sleep 300"
  )
  IF %%G==opencv (
    %bash% "pacman -S --noconfirm %group%-{python3-numpy,openexr,suitesparse,leptonica,gflags,SDL2,protobuf,intel-tbb,hdf5} || sleep 300"
    %bash% "pacman -Sdd --noconfirm %group%-{opencv,tesseract-ocr,ogre3d,ceres-solver,glog} || sleep 300"
  )
)

%bash% "pacman -Scc --noconfirm"
