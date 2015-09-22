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

image_types = [
    'jpeg', 'jpg', 'exv', 'cr2', 'crw', 'mrw', 'tiff', 'tif', 'dng',
    'nef', 'pef', 'arw', 'rw2', 'sr2', 'srw', 'orf', 'png', 'pgf',
    'raf', 'eps', 'gif', 'psd', 'tga', 'bmp', 'jp2', 'pnm'
    ]
for _fmt in QtGui.QImageReader.supportedImageFormats():
    _ext = _fmt.data().decode('utf_8').lower()
    if _ext not in image_types:
        image_types.append(_ext)
for _ext in ('ico', 'xcf'):
    if _ext in image_types:
        image_types.remove(_ext)

class Busy(object):
    def __enter__(self):
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        return self

    def __exit__(self, type, value, traceback):
        QtWidgets.QApplication.restoreOverrideCursor()


class FileObjWithCallback(object):
    def __init__(self, fileobj, callback):
        self._f = fileobj
        self._callback = callback
        # requests library uses 'len' attribute instead of seeking to
        # end of file and back
        self.len = os.fstat(self._f.fileno()).st_size

    # substitute read method
    def read(self, size):
        if self._callback:
            self._callback(self._f.tell() * 100 // self.len)
        return self._f.read(size)

    # delegate all other attributes to file object
    def __getattr__(self, name):
        return getattr(self._f, name)
