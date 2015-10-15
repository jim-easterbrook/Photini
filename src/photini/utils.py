# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-15  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from .pyqt import Qt, QtGui, QtWidgets

data_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data', '')

multiple = QtWidgets.QApplication.translate('utils', '<multiple>')
multiple_values = QtWidgets.QApplication.translate('utils', '<multiple values>')

_image_types = None

def image_types():
    global _image_types
    if _image_types:
        return _image_types
    _image_types = [
        'jpeg', 'jpg', 'exv', 'cr2', 'crw', 'mrw', 'tiff', 'tif', 'dng',
        'nef', 'pef', 'arw', 'rw2', 'sr2', 'srw', 'orf', 'png', 'pgf',
        'raf', 'eps', 'gif', 'psd', 'tga', 'bmp', 'jp2', 'pnm'
        ]
    for fmt in QtGui.QImageReader.supportedImageFormats():
        ext = fmt.data().decode('utf_8').lower()
        if ext not in _image_types:
            _image_types.append(ext)
    for ext in ('ico', 'xcf'):
        if ext in _image_types:
            _image_types.remove(ext)
    return _image_types


class Busy(object):
    def __enter__(self):
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        return self

    def __exit__(self, type, value, traceback):
        QtWidgets.QApplication.restoreOverrideCursor()
