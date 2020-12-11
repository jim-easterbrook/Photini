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

from __future__ import unicode_literals

import os
import subprocess
import sys


def main(argv=None):
    root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    src_dir = os.path.join(root, 'src', 'lang')
    dst_dir = os.path.join(root, 'src', 'photini', 'data', 'lang')
    inputs = []
    for name in os.listdir(src_dir):
        src_file = os.path.join(src_dir, name, 'photini.ts')
        if not os.path.exists(src_file):
            continue
        cmd = ['lrelease-qt5', src_file,
               '-qm', os.path.join(dst_dir, 'photini.' + name + '.qm')]
        result = subprocess.call(cmd)
        if result:
            return result
    return 0


if __name__ == "__main__":
    sys.exit(main())
