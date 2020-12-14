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

from photini.pyqt import QtCore


def main(argv=None):
    root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    lang_dir = os.path.join(root, 'src', 'photini', 'data', 'lang')
    translator = QtCore.QTranslator()
    cmd = []
    for name in os.listdir(lang_dir):
        lang = name.split('.')[1]
        if lang == 'en':
            continue
        if not translator.load('photini.' + lang, lang_dir):
            print('load failed:', lang)
            continue
        text = translator.translate('MenuBar', 'Photini photo metadata editor')
        if text:
            cmd += ['--set-key=GenericName[{}]'.format(lang),
                    '--set-value={}'.format(text.strip())]
        text = translator.translate('MenuBar',
                                    'An easy to use digital photograph metadata'
                                    ' (Exif, IPTC, XMP) editing application.')
        if text:
            cmd += ['--set-key=Comment[{}]'.format(lang),
                    '--set-value={}'.format(text.strip())]
    if not cmd:
        return 0
    desktop_file = os.path.join(
        root, 'src', 'photini', 'data', 'linux', 'photini.desktop')
    cmd = ['desktop-file-edit'] + cmd + [desktop_file]
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
