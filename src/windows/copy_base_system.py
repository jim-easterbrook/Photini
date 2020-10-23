##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2020  Jim Easterbrook  jim@jim-easterbrook.me.uk
##
##  This program is free software: you can redistribute it and/or
##  modify it under the terms of the GNU General Public License as
##  published by the Free Software Foundation, either version 3 of the
##  License, or (at your option) any later version.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
##  General Public License for more details.
##
##  You should have received a copy of the GNU General Public License
##  along with this program.  If not, see
##  <http://www.gnu.org/licenses/>.

import os
import shutil
import subprocess
import sys


def get_dependencies(name):
    packages = subprocess.check_output(['pactree', '-u', name])
    for package in packages.splitlines():
        yield package.decode('utf-8')


def get_files(name):
    files = subprocess.check_output(['pacman', '-Qlq', name])
    for name in files.splitlines():
        yield name.decode('utf-8')


def main():
    if sys.maxsize > 2**32:
        root = 'C:/msys64'
        install = 'C:/photini_temp_64'
        packages = ('base', 'pacman')
    else:
        root = 'C:/msys32'
        install = 'C:/photini_temp_32'
        packages = ('filesystem', 'msys2-launcher', 'pacman')
    dependencies = []
    for package in packages:
        for dependency in get_dependencies(package):
            if dependency in dependencies:
                continue
            dependencies.append(dependency)
            for path in get_files(dependency):
                dest = install + path
                if os.path.exists(dest):
                    continue
                src = root + path
                if not os.path.exists(src):
                    continue
                print(dest)
                if os.path.isdir(src):
                    os.makedirs(dest)
                else:
                    shutil.copy2(src, dest, follow_symlinks=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
