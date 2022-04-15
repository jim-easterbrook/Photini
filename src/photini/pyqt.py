##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2015-22  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from collections import namedtuple
from contextlib import contextmanager
from functools import wraps
import importlib
import logging
import os
import re
import sys

from photini.configstore import BaseConfigStore

logger = logging.getLogger(__name__)

# temporarily open config file to get any over-rides
config = BaseConfigStore('editor')
config.delete('pyqt', 'using_pyqt5')
using_pyside = config.get('pyqt', 'using_pyside2')
config.delete('pyqt', 'using_pyside2')
using_qtwebengine = config.get('pyqt', 'using_qtwebengine', 'auto')
qt_lib = config.get('pyqt', 'qt_lib', 'auto')
if qt_lib == 'auto' and isinstance(using_pyside, bool):
    # copy old config
    qt_lib = ('PyQt5', 'PySide2')[using_pyside]
    config.set('pyqt', 'qt_lib', qt_lib)
qt_scale_factor = config.get('pyqt', 'scale_factor', 1)
if qt_scale_factor != 1:
    os.environ['QT_SCALE_FACTOR'] = str(qt_scale_factor)

# choose Qt package
if qt_lib == 'auto':
    _libs = ('PyQt5', 'PySide2', 'PySide6')
    for package in _libs:
        try:
            importlib.import_module('.QtCore', package)
        except ImportError:
            continue
        qt_lib = package
        break
    else:
        raise RuntimeError('Please install ' + ' or '.join(_libs))
using_pyside = qt_lib != 'PyQt5'

# import normal Qt stuff
if qt_lib == 'PySide6':
    using_qtwebengine = True
    from PySide6 import QtCore, QtGui, QtNetwork, QtWidgets
    from PySide6.QtCore import Qt
    from PySide6.QtCore import Signal as QtSignal
    from PySide6.QtCore import Slot as QtSlot
    from PySide6 import __version__ as PySide_version
    QtGui2 = QtGui
elif qt_lib == 'PySide2':
    from PySide2 import QtCore, QtGui, QtNetwork, QtWidgets
    from PySide2.QtCore import Qt
    from PySide2.QtCore import Signal as QtSignal
    from PySide2.QtCore import Slot as QtSlot
    from PySide2 import __version__ as PySide_version
    QtGui2 = QtWidgets
elif qt_lib == 'PyQt5':
    from PyQt5 import QtCore, QtGui, QtNetwork, QtWidgets
    from PyQt5.QtCore import Qt
    from PyQt5.QtCore import pyqtSignal as QtSignal
    from PyQt5.QtCore import pyqtSlot as QtSlot
    QtGui2 = QtWidgets
else:
    raise RuntimeError('Unrecognised Qt library ' + qt_lib)

style = config.get('pyqt', 'style')
if style:
    QtWidgets.QApplication.setStyle(style)
config.save()
del config, style

if qt_lib == 'PyQt5':
    qt_version_info = namedtuple(
        'qt_version_info', ('major', 'minor', 'micro'))._make(
            map(int, QtCore.QT_VERSION_STR.split('.')))
    qt_version = 'PyQt {}, Qt {}'.format(
        QtCore.PYQT_VERSION_STR, QtCore.QT_VERSION_STR)
else:
    qt_version_info = QtCore.__version_info__
    qt_version = '{} {}, Qt {}'.format(
        qt_lib, PySide_version, QtCore.__version__)
if qt_version_info < (5, 8):
    raise ImportError(
        'Qt version {}.{}.{} is less than 5.8'.format(*qt_version_info))

# set network proxy
QtNetwork.QNetworkProxyFactory.setUseSystemConfiguration(True)

# workaround for Qt bug affecting QtWebEngine
# https://bugreports.qt.io/browse/QTBUG-67537
if sys.platform.startswith('linux') and qt_version_info < (5, 11, 0):
    import ctypes
    import ctypes.util
    ctypes.CDLL(ctypes.util.find_library('GL'), ctypes.RTLD_GLOBAL)

# choose WebEngine or WebKit
if not isinstance(using_qtwebengine, bool):
    using_qtwebengine = True
    try:
        importlib.import_module('.QtWebEngineWidgets', qt_lib)
    except ImportError:
        using_qtwebengine = False

# import WebEngine or WebKit stuff
if using_qtwebengine:
    if qt_lib == 'PySide6':
        from PySide6 import QtWebChannel
        from PySide6 import QtWebEngineWidgets as QtWebWidgets
        from PySide6 import QtWebEngineCore as QtWebCore
    elif qt_lib == 'PySide2':
        from PySide2 import QtWebChannel
        from PySide2 import QtWebEngineWidgets as QtWebWidgets
        QtWebCore = QtWebWidgets
    else:
        from PyQt5 import QtWebChannel
        from PyQt5 import QtWebEngineWidgets as QtWebWidgets
        QtWebCore = QtWebWidgets
else:
    QtWebChannel = None
    if qt_lib == 'PySide2':
        from PySide2 import QtWebKitWidgets as QtWebWidgets
        from PySide2 import QtWebKit as QtWebCore
    else:
        from PyQt5 import QtWebKitWidgets as QtWebWidgets
        from PyQt5 import QtWebKit as QtWebCore

qt_version += ', using {}'.format(
    ('QtWebKit', 'QtWebEngine')[using_qtwebengine])

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
    return translate('Common', '<multiple>')

def multiple_values():
    return translate('Common', '<multiple values>')

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

def execute(widget, *arg, **kwds):
    if qt_lib == 'PySide2':
        return widget.exec_(*arg, **kwds)
    return widget.exec(*arg, **kwds)


@contextmanager
def Busy():
    QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
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
            self.setRowWrapPolicy(self.WrapAllRows)
        self.setFieldGrowthPolicy(self.AllNonFixedFieldsGrow)


class CompactButton(QtWidgets.QPushButton):
    def __init__(self, *args, **kwds):
        super(CompactButton, self).__init__(*args, **kwds)
        if QtWidgets.QApplication.style().objectName() in ('breeze',):
            self.setStyleSheet('padding: 2px;')
        scale_font(self, 80)


class TextHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, spelling, length, multi_string, parent):
        super(TextHighlighter, self).__init__(parent)
        self.config_store = QtWidgets.QApplication.instance().config_store
        if spelling:
            self.spell_check = QtWidgets.QApplication.instance().spell_check
            self.spell_check.new_dict.connect(self.rehighlight)
            self.spell_formatter = QtGui.QTextCharFormat()
            self.spell_formatter.setUnderlineColor(Qt.red)
            self.spell_formatter.setUnderlineStyle(
                QtGui.QTextCharFormat.SpellCheckUnderline)
            self.find_words = self.spell_check.find_words
            self.suggest = self.spell_check.suggest
        else:
            self.spell_check = None
        if length:
            self.length_check = length
            self.length_formatter = QtGui.QTextCharFormat()
            self.length_formatter.setUnderlineColor(Qt.blue)
            self.length_formatter.setUnderlineStyle(
                QtGui.QTextCharFormat.SingleUnderline)
            if multi_string:
                self.pattern = re.compile(r'\s*(.+?)(;|$)')
            else:
                self.pattern = re.compile(r'\s*(.+)')
        else:
            self.length_check = None

    @catch_all
    def highlightBlock(self, text):
        if not text:
            return
        if self.length_check:
            length_warning = self.config_store.get(
                'files', 'length_warning', True)
            if length_warning:
                consumed = max(self.previousBlockState(), 0)
                max_len = max(self.length_check - consumed, 0)
                for match in self.pattern.finditer(text):
                    start = match.start(1)
                    end = match.end(1)
                    truncated = text[start:end].encode('utf-8')
                    consumed += len(truncated)
                    truncated = truncated[:max_len]
                    start += len(truncated.decode('utf-8', errors='ignore'))
                    if start < end:
                        self.setFormat(start, end - start,
                                       self.length_formatter)
                self.setCurrentBlockState(max(consumed, 0))
        if self.spell_check:
            for word, start, end in self.find_words(text):
                if not self.spell_check.check(word):
                    self.setFormat(start, end - start, self.spell_formatter)


class ComboBox(QtWidgets.QComboBox):
    def __init__(self, *args, **kwds):
        super(ComboBox, self).__init__(*args, **kwds)
        self.setFocusPolicy(Qt.StrongFocus)

    @catch_all
    def wheelEvent(self, event):
        if self.hasFocus():
            return super(ComboBox, self).wheelEvent(event)
        event.ignore()
        return True

    def set_dropdown_width(self):
        width = 0
        for idx in range(self.count()):
            width = max(width, width_for_text(self, self.itemText(idx) + 'xx'))
        margin = self.view().verticalScrollBar().sizeHint().width()
        self.view().setMinimumWidth(width + margin)


class DropDownSelector(ComboBox):
    new_value = QtSignal(str, object)

    def __init__(self, key, values=[], default=None,
                 with_multiple=True, extendable=False, ordered=False):
        super(DropDownSelector, self).__init__()
        self._key = key
        self._with_multiple = with_multiple
        self._extendable = extendable
        self._ordered = ordered
        self._old_idx = 0
        self.setSizeAdjustPolicy(self.AdjustToMinimumContentsLengthWithIcon)
        self.set_values(values, default=default)
        self.currentIndexChanged.connect(self._index_changed)

    def add_item(self, text, data, adjust_width=True):
        idx = self.findData(data)
        if idx >= 0:
            self.setItemText(idx, text)
            return idx
        idx = self._last_idx()
        if self._ordered:
            for n in range(idx):
                if self.itemText(n).lower() > text.lower():
                    idx = n
                    break
        blocked = self.blockSignals(True)
        self.insertItem(idx, text, data)
        self.blockSignals(blocked)
        if adjust_width:
            self.set_dropdown_width()
        return idx

    def remove_item(self, data, adjust_width=True):
        idx = self.findData(data)
        if idx < 0:
            return
        blocked = self.blockSignals(True)
        self.removeItem(idx)
        self.blockSignals(blocked)

    def set_values(self, values, default=None):
        blocked = self.blockSignals(True)
        self.clear()
        if self._extendable:
            self.addItem(self.tr('<new>'))
        if self._with_multiple:
            self.addItem(multiple_values())
            self.setItemData(self.count() - 1, '', Qt.UserRole - 1)
        for text, data in values:
            self.add_item(text, data, adjust_width=False)
        self.set_dropdown_width()
        self.blockSignals(blocked)
        if default is not None:
            self.set_value(default)

    def get_value(self):
        return self.itemData(self.currentIndex())

    def set_value(self, value):
        self._old_idx = self.findData(value)
        if self._old_idx < 0:
            self._old_idx = self.add_item(self.data_to_text(value), value)
        blocked = self.blockSignals(True)
        self.setCurrentIndex(self._old_idx)
        self.blockSignals(blocked)

    def data_to_text(self, data):
        return str(data)

    def is_multiple(self):
        return self._with_multiple and self.currentIndex() == self.count() - 1

    def set_multiple(self, choices=[]):
        if self._with_multiple:
            blocked = self.blockSignals(True)
            self._old_idx = self.count() - 1
            self.setCurrentIndex(self._old_idx)
            self.blockSignals(blocked)

    def findData(self, data):
        # Qt's findData only works with simple types
        for n in range(self._last_idx()):
            if self.itemData(n) == data:
                return n
        return -1

    @QtSlot(int)
    @catch_all
    def _index_changed(self, idx):
        if idx < self._last_idx():
            # normal item selection
            self._old_idx = idx
            self.new_value.emit(self._key, self.itemData(idx))
            return
        # user must have clicked '<new>'
        text, data = self.define_new_value()
        if text:
            self._old_idx = self.add_item(text, data)
            blocked = self.blockSignals(True)
            self.setCurrentIndex(self._old_idx)
            self.blockSignals(blocked)
            self.new_value.emit(self._key, data)
            return
        blocked = self.blockSignals(True)
        self.setCurrentIndex(self._old_idx)
        self.blockSignals(blocked)

    def _last_idx(self):
        idx = self.count()
        if self._extendable:
            idx -= 1
        if self._with_multiple:
            idx -= 1
        return idx


class MultiLineEdit(QtWidgets.QPlainTextEdit):
    new_value = QtSignal(str, object)

    def __init__(self, key, *arg, spell_check=False, length_check=None,
                 multi_string=False, **kw):
        super(MultiLineEdit, self).__init__(*arg, **kw)
        self._key = key
        self.multiple_values = multiple_values()
        self.setTabChangesFocus(True)
        self._is_multiple = False
        self.spell_check = spell_check
        self.highlighter = TextHighlighter(
            spell_check, length_check, multi_string, self.document())

    def focusOutEvent(self, event):
        if not self._is_multiple:
            self.new_value.emit(self._key, self.get_value())
        super(MultiLineEdit, self).focusOutEvent(event)

    def keyPressEvent(self, event):
        if self._is_multiple:
            self._is_multiple = False
            self.setPlaceholderText('')
        super(MultiLineEdit, self).keyPressEvent(event)

    @catch_all
    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        suggestion_group = QtGui2.QActionGroup(menu)
        if self._is_multiple:
            if self.choices:
                sep = menu.insertSeparator(menu.actions()[0])
                fm = menu.fontMetrics()
                for suggestion in self.choices:
                    label = str(suggestion).replace('\n', ' ')
                    label = fm.elidedText(label, Qt.ElideMiddle, self.width())
                    action = QtGui2.QAction(label, suggestion_group)
                    action.setData(str(suggestion))
                    menu.insertAction(sep, action)
        elif self.spell_check:
            cursor = self.cursorForPosition(event.pos())
            block_pos = cursor.block().position()
            for word, start, end in self.highlighter.find_words(
                                                        cursor.block().text()):
                if start > cursor.positionInBlock():
                    break
                if end <= cursor.positionInBlock():
                    continue
                cursor.setPosition(block_pos + start)
                cursor.setPosition(block_pos + end, QtGui.QTextCursor.KeepAnchor)
                break
            suggestions = self.highlighter.suggest(cursor.selectedText())
            if suggestions:
                sep = menu.insertSeparator(menu.actions()[0])
                for suggestion in suggestions:
                    action = QtGui2.QAction(suggestion, suggestion_group)
                    menu.insertAction(sep, action)
        action = menu.exec_(event.globalPos())
        if action and action.actionGroup() == suggestion_group:
            if self._is_multiple:
                self.new_value.emit(self._key, action.data())
            else:
                cursor.setPosition(block_pos + start)
                cursor.setPosition(block_pos + end, QtGui.QTextCursor.KeepAnchor)
                cursor.insertText(action.iconText())

    def set_height(self, rows):
        margins = self.contentsMargins()
        self.setFixedHeight((self.fontMetrics().lineSpacing() * rows)
                            + (self.document().documentMargin() * 2)
                            + (self.frameWidth() * 2)
                            + (margins.top() + margins.bottom()))

    def set_value(self, value):
        self._is_multiple = False
        if not value:
            self.clear()
            self.setPlaceholderText('')
        else:
            self.setPlainText(str(value))

    def get_value(self):
        return self.toPlainText()

    def set_multiple(self, choices=[]):
        self._is_multiple = True
        self.choices = list(choices)
        self.setPlaceholderText(self.multiple_values)
        self.clear()

    def is_multiple(self):
        return self._is_multiple and not bool(self.get_value())


class SingleLineEdit(MultiLineEdit):
    def __init__(self, *arg, **kw):
        super(SingleLineEdit, self).__init__(*arg, **kw)
        self.setFixedHeight(QtWidgets.QLineEdit().sizeHint().height())
        self.setLineWrapMode(self.NoWrap)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return:
            event.ignore()
            return
        super(SingleLineEdit, self).keyPressEvent(event)

    def insertFromMimeData(self, source):
        self.insertPlainText(source.text().replace('\n', ' '))


class LangAltWidget(QtWidgets.QWidget):
    new_value = QtSignal(str, object)

    def __init__(self, key, multi_line=True, **kw):
        super(LangAltWidget, self).__init__()
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self.value = {}
        # text edit
        if multi_line:
            self.edit = MultiLineEdit(key, **kw)
        else:
            self.edit = SingleLineEdit(key, **kw)
        self.edit.new_value.connect(self._new_value)
        layout.addWidget(self.edit)
        # language drop down
        self.lang = DropDownSelector(
            'lang', with_multiple=False, extendable=True, ordered=True)
        self.lang.setFixedWidth(width_for_text(self.lang, 'x' * 16))
        self.lang.new_value.connect(self._change_lang)
        layout.addWidget(self.lang)
        layout.setAlignment(self.lang, Qt.AlignTop)
        # adopt some child methods ...
        self.is_multiple = self.edit.is_multiple
        # ... and vice versa
        self.lang.define_new_value = self._define_new_lang

    @QtSlot(str, object)
    @catch_all
    def _change_lang(self, key, lang):
        if lang in self.value:
            self.edit.set_value(self.value[lang])
        else:
            self.edit.set_value('')
        self.lang.clearFocus()
        self.edit.setFocus()

    @QtSlot(str, object)
    @catch_all
    def _new_value(self, key, value):
        if self.is_multiple():
            self.value = self.choices[value]
        else:
            self.value[self.lang.get_value()] = value
        self.new_value.emit(key, self.get_value())

    def _define_new_lang(self):
        lang, OK = QtWidgets.QInputDialog.getText(
            self, translate('LangAltWidget', 'New language'),
            translate('LangAltWidget', 'RFC3066 language tag:'))
        if not (OK and lang):
            return None, None
        return self.labeled_lang(lang)

    def labeled_lang(self, lang):
        label = translate('LangAltWidget', 'Lang:')
        if lang != 'x-default':
            label += ' ' + lang
        return label, lang

    def set_value(self, value):
        self.lang.setEnabled(True)
        if isinstance(value, str):
            self.value = {'x-default': value}
        elif value:
            self.value = dict(value)
        else:
            self.value = {'x-default': ''}
        lang = self.lang.get_value()
        if lang not in self.value:
            lang = 'x-default'
        selection = []
        for key in self.value:
            selection.append(self.labeled_lang(key))
        self.lang.set_values(selection, default=lang)
        self._change_lang('', lang)

    def get_value(self):
        result = {}
        for k in self.value:
            if self.value[k]:
                result[k] = self.value[k]
        return result

    def set_multiple(self, choices=[]):
        self.choices = {}
        for choice in choices:
            self.choices[str(choice)] = dict(choice)
        self.edit.set_multiple(choices=self.choices.keys())
        self.lang.setEnabled(False)


class Slider(QtWidgets.QSlider):
    editing_finished = QtSignal()

    def __init__(self, *arg, **kw):
        super(Slider, self).__init__(*arg, **kw)
        self._is_multiple = False
        self.sliderPressed.connect(self.slider_pressed)

    def focusOutEvent(self, event):
        self.editing_finished.emit()
        super(Slider, self).focusOutEvent(event)

    @QtSlot()
    @catch_all
    def slider_pressed(self):
        self._is_multiple = False

    def get_value(self):
        return self.value()

    def set_value(self, value):
        self._is_multiple = False
        if value is not None:
            self.setValue(value)

    def set_multiple(self, choices=[]):
        self._is_multiple = True
        value = self.value()
        for choice in choices:
            if choice is not None:
                value = max(value, choice)
        self.setValue(value)

    def is_multiple(self):
        return self._is_multiple


class StartStopButton(QtWidgets.QPushButton):
    click_start = QtSignal()
    click_stop = QtSignal()

    def __init__(self, start_text, stop_text, *arg, **kw):
        super(StartStopButton, self).__init__(*arg, **kw)
        self.start_text = start_text
        self.stop_text = stop_text
        self.checked = False
        self.clicked.connect(self.do_clicked)
        # get a size big enough for either text
        self.setText(self.stop_text)
        stop_size = super(StartStopButton, self).sizeHint()
        self.setText(self.start_text)
        start_size = super(StartStopButton, self).sizeHint()
        self.minimum_size = stop_size.expandedTo(start_size)

    def sizeHint(self):
        return self.minimum_size

    def is_checked(self):
        return self.checked

    def set_checked(self, value):
        self.checked = value
        if self.checked:
            self.setText(self.stop_text)
        else:
            self.setText(self.start_text)

    @QtSlot()
    def do_clicked(self):
        if self.checked:
            self.click_stop.emit()
        else:
            self.click_start.emit()
