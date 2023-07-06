#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2023  Jim Easterbrook  jim@jim-easterbrook.me.uk
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at
#  your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import subprocess

from setuptools import build_meta as _orig
from setuptools.build_meta import *


def build_lang():
    src_dir = os.path.join('src', 'lang')
    dst_dir = os.path.join('src', 'photini', 'data', 'lang')
    if os.path.exists(dst_dir) and not os.path.exists(src_dir):
        # probably building wheel from sdist, no need to compile
        return
    print('running build_lang')
    os.makedirs(dst_dir, exist_ok=True)
    for lang in os.listdir(src_dir):
        src_file = os.path.join(src_dir, lang, 'photini.ts')
        if not os.path.exists(src_file):
            continue
        dst_file = os.path.join(dst_dir, 'photini.' + lang + '.qm')
        if (os.path.exists(dst_file) and
                os.stat(dst_file).st_mtime >= os.stat(src_file).st_mtime):
            continue
        print('compiling {} -> {}'.format(src_file, dst_file))
        try:
            subprocess.check_call([
                'lrelease-qt5', '-silent', src_file, '-qm', dst_file])
        except FileNotFoundError as ex:
            print('FAIL:', str(ex))
            return


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    build_lang()
    return _orig.build_wheel(wheel_directory, config_settings=config_settings,
                             metadata_directory=metadata_directory)


def build_sdist(sdist_directory, config_settings=None):
    build_lang()
    return _orig.build_sdist(sdist_directory, config_settings=config_settings)
