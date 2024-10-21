##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2015-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
from contextlib import contextmanager
from functools import wraps
import importlib.util
import logging
import os
import sys

from photini.configstore import BaseConfigStore

logger = logging.getLogger(__name__)

# allow a "standard" list of objects to be imported with *
__all__ = (
    'Busy', 'catch_all', 'DisableWidget', 'execute', 'flag_to_int',
    'FormLayout', 'multiple', 'multiple_values', 'Qt', 'QtCore', 'QtGui',
    'QtGui2', 'QtSignal', 'QtSlot', 'QtWidgets', 'scale_font', 'UnBusy',
    'width_for_text', 'wrap_text'
    )

# temporarily open config file to get any over-rides
config = BaseConfigStore('editor')
config.delete('pyqt', 'using_pyqt5')
using_pyside = config.get('pyqt', 'using_pyside2')
config.delete('pyqt', 'using_pyside2')
config.delete('pyqt', 'using_qtwebengine')
qt_lib = config.get('pyqt', 'qt_lib', 'auto')
if qt_lib == 'auto' and isinstance(using_pyside, bool):
    # copy old config
    qt_lib = ('PyQt5', 'PySide2')[using_pyside]
    config.set('pyqt', 'qt_lib', qt_lib)
qt_scale_factor = config.get('pyqt', 'scale_factor', 1)
if qt_scale_factor != 1:
    os.environ['QT_SCALE_FACTOR'] = str(qt_scale_factor)

# choose Qt package
available_packages = []
for _lib in ('PyQt6', 'PyQt5', 'PySide6', 'PySide2'):
    _spec = importlib.util.find_spec(_lib)
    if _spec:
        for _path in _spec.submodule_search_locations:
            for _name in os.listdir(_path):
                if (_name.startswith('QtWebEngineWidgets')
                        and _name != 'QtWebEngineWidgets.pyi'):
                    available_packages.append(_lib)
                    break
        if _lib not in available_packages:
            print(_lib, 'is installed without QtWebEngine')
if not available_packages:
    print('')
    print('No Qt package installed. Installation instructions can be found')
    print('at https://photini.readthedocs.io/')
    sys.exit(1)
if qt_lib not in available_packages:
    qt_lib = available_packages[0]

# import chosen package
if qt_lib == 'PySide6':
    from PySide6 import QtCore, QtGui, QtNetwork, QtWidgets
    from PySide6.QtCore import Qt
    from PySide6.QtCore import Signal as QtSignal
    from PySide6.QtCore import Slot as QtSlot
    from PySide6 import __version__ as PySide_version
    QtGui2 = QtGui
    from PySide6 import QtWebChannel, QtWebEngineCore, QtWebEngineWidgets
elif qt_lib == 'PySide2':
    from PySide2 import QtCore, QtGui, QtNetwork, QtWidgets
    from PySide2.QtCore import Qt
    from PySide2.QtCore import Signal as QtSignal
    from PySide2.QtCore import Slot as QtSlot
    from PySide2 import __version__ as PySide_version
    QtGui2 = QtWidgets
    from PySide2 import QtWebChannel, QtWebEngineWidgets
    QtWebEngineCore = QtWebEngineWidgets
elif qt_lib == 'PyQt6':
    from PyQt6 import QtCore, QtGui, QtNetwork, QtWidgets
    from PyQt6.QtCore import Qt
    from PyQt6.QtCore import pyqtSignal as QtSignal
    from PyQt6.QtCore import pyqtSlot as QtSlot
    QtGui2 = QtGui
    from PyQt6 import QtWebChannel, QtWebEngineCore, QtWebEngineWidgets
else:
    from PyQt5 import QtCore, QtGui, QtNetwork, QtWidgets
    from PyQt5.QtCore import Qt
    from PyQt5.QtCore import pyqtSignal as QtSignal
    from PyQt5.QtCore import pyqtSlot as QtSlot
    QtGui2 = QtWidgets
    from PyQt5 import QtWebChannel, QtWebEngineWidgets
    QtWebEngineCore = QtWebEngineWidgets

using_pyside = 'PySide' in qt_lib

style = config.get('pyqt', 'style')
if style:
    QtWidgets.QApplication.setStyle(style)
config.save()
del config, style

if using_pyside:
    qt_version_info = QtCore.__version_info__
    qt_version = '{} {}, Qt {}'.format(
        qt_lib, PySide_version, QtCore.__version__)
else:
    qt_version_info = namedtuple(
        'qt_version_info', ('major', 'minor', 'micro'))._make(
            map(int, QtCore.QT_VERSION_STR.split('.')))
    qt_version = 'PyQt {}, Qt {}'.format(
        QtCore.PYQT_VERSION_STR, QtCore.QT_VERSION_STR)
    pyqt_version_info = namedtuple(
        'pyqt_version_info', ('major', 'minor', 'micro'))._make(
            map(int, QtCore.PYQT_VERSION_STR.split('.')))
    if pyqt_version_info < (5, 11):
        raise ImportError(
            'PyQt version {}.{}.{} is less than 5.11'.format(*pyqt_version_info))

if qt_version_info < (5, 8):
    raise ImportError(
        'Qt version {}.{}.{} is less than 5.8'.format(*qt_version_info))

# increase image size that can be read
if qt_version_info >= (6, 0):
    if qt_version_info > (6, 3, 1) or using_pyside:
        QtGui.QImageReader.setAllocationLimit(0)
    else:
        os.environ['QT_IMAGEIO_MAXALLOC'] = '256'

# suppress QtWebEngine info logging
if qt_version_info >= (6, 0):
    QtCore.QLoggingCategory(
        'qt.webenginecontext').setFilterRules('*.info=false')

# set network proxy
QtNetwork.QNetworkProxyFactory.setUseSystemConfiguration(True)

# workaround for Qt bug affecting QtWebEngine
# https://bugreports.qt.io/browse/QTBUG-67537
if sys.platform.startswith('linux') and qt_version_info < (5, 11, 0):
    import ctypes
    import ctypes.util
    ctypes.CDLL(ctypes.util.find_library('GL'), ctypes.RTLD_GLOBAL)

translate = QtCore.QCoreApplication.translate

# decorator for methods called by Qt that logs any exception raised
def catch_all(func):
    @wraps(func)
    def wrapper(*args, **kwds):
        try:
            return func(*args, **kwds)
        except Exception as ex:
            logger.exception(ex)
    return wrapper


def image_types_lower():
    result = [
        'jpeg', 'jpg', 'exv', 'cr2', 'crw', 'mrw', 'tiff', 'tif', 'dng',
        'nef', 'pef', 'arw', 'rw2', 'sr2', 'srw', 'orf', 'png', 'pgf',
        'raf', 'eps', 'gif', 'psd', 'tga', 'bmp', 'jp2', 'pnm',
        'cr3', 'heif', 'heic', 'avif'
        ]
    for fmt in QtGui.QImageReader.supportedImageFormats():
        ext = fmt.data().decode('utf-8').lower()
        if ext not in result:
            result.append(ext)
    for ext in ('ico', 'xcf'):
        if ext in result:
            result.remove(ext)
    return result

def image_types():
    lower = image_types_lower()
    return lower + [x.upper() for x in lower] + [x.title() for x in lower]

def video_types_lower():
    return ['3gp', 'avi', 'mp4', 'mpeg', 'mpg', 'mov', 'mts', 'qt', 'wmv']

def video_types():
    lower = video_types_lower()
    return lower + [x.upper() for x in lower] + [x.title() for x in lower]

def multiple():
    return translate('Widgets', '<multiple>')

def multiple_values():
    return translate('Widgets', '<multiple values>')

def set_symbol_font(widget):
    widget.setFont(QtGui.QFont('DejaVu Sans'))
    if widget.fontInfo().family().lower() != 'dejavu sans':
        # probably on Windows, try a different font
        widget.setFont(QtGui.QFont("Segoe UI Symbol"))

def scale_font(widget, scale):
    font = widget.font()
    size = font.pointSizeF()
    if size < 0:
        size = font.pixelSize()
        font.setPixelSize(((size * scale) + 50) // 100)
    else:
        font.setPointSizeF(size * scale / 100.0)
    widget.setFont(font)

def width_for_text(widget, text):
    rect = widget.fontMetrics().boundingRect(text)
    return rect.width()

def wrap_text(widget, text, lines):
    def sub_wrap(fm, text, lines, idx):
        width = fm.boundingRect(0, 0, 1, 1, 0, text).width()
        result = text
        while True:
            idx = text.find(' ', idx + 1)
            if idx < 0:
                break
            new_text = '\n'.join((text[:idx], text[idx+1:]))
            if lines > 2:
                new_text = sub_wrap(fm, new_text, lines-1, idx+1)
            new_width = fm.boundingRect(0, 0, 1, 1, 0, new_text).width()
            if width > new_width:
                width = new_width
                result = new_text
        return result
    return sub_wrap(widget.fontMetrics(), text, lines, 0)

def execute(widget, *arg, **kwds):
    if qt_lib == 'PySide2':
        return widget.exec_(*arg, **kwds)
    return widget.exec(*arg, **kwds)

def flag_to_int(flags):
    if hasattr(flags, 'value'):
        # recent versions of PyQt6 and PySide6 convert QEnum to Python enum
        return flags.value
    return int(flags)


@contextmanager
def Busy():
    QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        yield
    finally:
        QtWidgets.QApplication.restoreOverrideCursor()


@contextmanager
def UnBusy():
    cursors = []
    while True:
        cursor = QtWidgets.QApplication.overrideCursor()
        if not cursor:
            break
        cursors.append(cursor.shape())
        QtWidgets.QApplication.restoreOverrideCursor()
    try:
        yield
    finally:
        while cursors:
            QtWidgets.QApplication.setOverrideCursor(cursors.pop())


@contextmanager
def DisableWidget(widget):
    widget.setEnabled(False)
    QtWidgets.QApplication.processEvents()
    try:
        yield
    finally:
        widget.setEnabled(True)


class FormLayout(QtWidgets.QFormLayout):
    def __init__(self, wrapped=False, **kwds):
        super(FormLayout, self).__init__(**kwds)
        if wrapped:
            self.setRowWrapPolicy(self.RowWrapPolicy.WrapAllRows)
        self.setFieldGrowthPolicy(self.FieldGrowthPolicy.AllNonFixedFieldsGrow)
