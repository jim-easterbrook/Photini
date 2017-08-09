import os
import shutil
import site
import subprocess
import sys

import gi

site_packages = os.path.dirname(os.path.dirname(gi.__file__))

# remove unneeded packages
for line in subprocess.check_output(['pip', 'list', '--format=legacy'],
                                    universal_newlines=True).splitlines():
    package = str(line).split()[0]
    if package in ('appdirs', 'certifi', 'cffi', 'chardet', 'flickrapi', 'idna',
                   'keyring', 'numpy', 'oauthlib', 'opencv-python', 'pgi',
                   'photini', 'Pillow', 'pip', 'pkginfo', 'pycparser', 'pydbus',
                   'pyenchant', 'pygobject','PyQt5', 'pywin32',
                   'pywin32-ctypes', 'requests', 'requests-oauthlib',
                   'requests-toolbelt', 'setuptools', 'six', 'urllib3',
                   'wheel', 'winpython'):
        continue
    subprocess.check_call(['pip', 'uninstall', '-y', package])

# install OpenCV
subprocess.check_call([
    'pip', 'install',
    'C:/Users/Jim/Downloads/opencv_python-3.1.0-cp34-cp34m-win32.whl'])

# remove surplus big files
for name in ('opencv_ffmpeg310.dll', 'PyQt5/qml'):
    path = os.path.join(site_packages, name)
    if not os.path.exists(path):
        continue
    print('delete', path)
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.unlink(path)

# copy newer exiv2 dlls
gnome = os.path.join(site_packages, 'gnome')
for name in ('libgexiv2-2', 'libexiv2',
             'libgcc_s_dw2-1', 'libstdc++-6',
             'libexpat-1', 'libiconv-2', 'zlib1'):
    dll = name + '.dll'
    print('copying', dll)
    shutil.copy2(os.path.join('C:/msys32/mingw32/bin', dll), gnome)
