import os
import shutil
import site
import subprocess
import sys

import pip

site_packages = os.path.dirname(os.path.dirname(pip.__file__))

# remove unneeded packages
for line in subprocess.check_output(['pip', 'list', '--format=legacy'],
                                    universal_newlines=True).splitlines():
    package = str(line).split()[0]
    if package in ('cffi', 'chardet', 'pip', 'pkginfo', 'pycparser',
                   'pydbus', 'pywin32', 'setuptools',
                   'wheel', 'winpython'):
        continue
    subprocess.check_call(['pip', 'uninstall', '-y', package])

# remove surplus big files
for name in ('PyQt5/Qt/qml',):
    path = os.path.join(site_packages, name)
    if not os.path.exists(path):
        continue
    print('delete', path)
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.unlink(path)

# copy MSYS2 dlls
gnome = os.path.join(site_packages, 'gnome')
for name in ('libgexiv2-2', 'libexiv2',
             'libgcc_s_dw2-1', 'libstdc++-6',
             'libexpat-1', 'libiconv-2', 'zlib1'):
    dll = name + '.dll'
    print('copying', dll)
    shutil.copy2(os.path.join('C:/msys32/mingw32/bin', dll), gnome)
