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

from argparse import ArgumentParser
import os
import subprocess
import sys


def main(argv=None):
    if argv:
        sys.argv = argv
    parser = ArgumentParser(
        description='Extract program strings for translation')
    parser.add_argument('-l', '--language',
                        help='language code, e.g. nl or cs_CZ')
    args = parser.parse_args()
    root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    src_dir = os.path.join(root, 'src', 'photini')
    dst_dir = os.path.join(root, 'src', 'lang')
    inputs = []
    for name in os.listdir(src_dir):
        base, ext = os.path.splitext(name)
        if ext == '.py':
            inputs.append(os.path.join(src_dir, name))
    inputs.sort()
    if args.language:
        outputs = [os.path.join(dst_dir, 'photini.' + args.language + '.ts')]
    else:
        outputs = []
        for name in os.listdir(dst_dir):
            if name.startswith('photini.'):
                outputs.append(os.path.join(dst_dir, name))
        outputs.sort()
    cmd = ['pylupdate5', '-verbose', '-noobsolete']
    cmd += inputs
    cmd.append('-ts')
    cmd += outputs
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
