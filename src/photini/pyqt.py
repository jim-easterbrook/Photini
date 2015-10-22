# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2015  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from collections import namedtuple

try:
    from PyQt5 import QtCore, QtGui, QtWebKitWidgets, QtWidgets
    from PyQt5.QtCore import Qt
    from PyQt5.QtNetwork import QNetworkProxy
except ImportError:
    import sip
    sip.setapi('QString', 2)
    sip.setapi('QVariant', 2)
    from PyQt4 import QtCore, QtGui
    QtWidgets = QtGui
    from PyQt4 import QtWebKit as QtWebKitWidgets
    from PyQt4.QtCore import Qt
    from PyQt4.QtNetwork import QNetworkProxy

qt_version_info = namedtuple(
    'qt_version_info', ('major', 'minor', 'micro'))._make(
        map(int, QtCore.QT_VERSION_STR.split('.')))

def image_types():
    result = [
        'jpeg', 'jpg', 'exv', 'cr2', 'crw', 'mrw', 'tiff', 'tif', 'dng',
        'nef', 'pef', 'arw', 'rw2', 'sr2', 'srw', 'orf', 'png', 'pgf',
        'raf', 'eps', 'gif', 'psd', 'tga', 'bmp', 'jp2', 'pnm'
        ]
    for fmt in QtGui.QImageReader.supportedImageFormats():
        ext = fmt.data().decode('utf_8').lower()
        if ext not in result:
            result.append(ext)
    for ext in ('ico', 'xcf'):
        if ext in result:
            result.remove(ext)
    return result

def multiple():
    return QtCore.QCoreApplication.translate('Multiple', '<multiple>')

def multiple_values():
    return QtCore.QCoreApplication.translate('Multiple', '<multiple values>')

class Busy(object):
    def __enter__(self):
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        return self

    def __exit__(self, type, value, traceback):
        QtWidgets.QApplication.restoreOverrideCursor()
