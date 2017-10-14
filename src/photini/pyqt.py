# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2015-17  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import re
import six

from photini.configstore import BaseConfigStore

# temporarily open config file to get any over-rides
config = BaseConfigStore('editor')
using_pyqt5 = config.get('pyqt', 'using_pyqt5', 'auto') != 'False'
using_qtwebengine = config.get('pyqt', 'using_qtwebengine', 'auto') != 'False'

if using_pyqt5:
    try:
        from PyQt5 import QtCore
    except ImportError:
        using_pyqt5 = False

if using_pyqt5:
    from PyQt5 import QtGui, QtWidgets
    from PyQt5.QtCore import Qt
    from PyQt5.QtNetwork import QNetworkProxy
    if using_qtwebengine:
        try:
            from PyQt5 import QtWebChannel, QtWebEngineWidgets
        except ImportError:
            using_qtwebengine = False
    if using_qtwebengine:
        QtWebKit = None
        QtWebKitWidgets = None
    else:
        from PyQt5 import QtWebKit, QtWebKitWidgets
        QtWebChannel = None
        QtWebEngineWidgets = None
    import sip
    sip.setdestroyonexit(True)
else:
    import sip
    sip.setapi('QString', 2)
    sip.setapi('QVariant', 2)
    from PyQt4 import QtCore, QtGui, QtWebKit
    using_qtwebengine = False
    QtWidgets = QtGui
    QtWebKitWidgets = QtWebKit
    QtWebChannel = None
    QtWebEngineWidgets = None
    from PyQt4.QtCore import Qt
    from PyQt4.QtNetwork import QNetworkProxy

style = config.get('pyqt', 'style')
if style:
    QtWidgets.QApplication.setStyle(style)
config.save()
del config, style

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

def video_types():
    return ['3gp', 'avi', 'mp4', 'mpeg', 'mpg', 'mov', 'mts', 'qt', 'wmv']

def multiple():
    return QtCore.QCoreApplication.translate('Multiple', '<multiple>')

def multiple_values():
    return QtCore.QCoreApplication.translate('Multiple', '<multiple values>')

def set_symbol_font(widget):
    widget.setFont(QtGui.QFont('DejaVu Sans'))
    if widget.fontInfo().family().lower() != 'dejavu sans':
        # probably on Windows, try a different font
        widget.setFont(QtGui.QFont("Segoe UI Symbol"))

class Busy(object):
    @staticmethod
    def start():
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)

    @staticmethod
    def stop():
        QtWidgets.QApplication.restoreOverrideCursor()

    def __enter__(self):
        Busy.start()
        return self

    def __exit__(self, type, value, traceback):
        Busy.stop()


class SpellingHighlighter(QtGui.QSyntaxHighlighter):
    words = re.compile(r"\w+([-'’]\w+)*", flags=re.IGNORECASE | re.UNICODE)

    def __init__(self, *arg, **kw):
        super(SpellingHighlighter, self).__init__(*arg, **kw)
        self.spell_check = QtWidgets.QApplication.instance().spell_check
        self.spell_check.new_dict.connect(self.rehighlight)

    def findWords(self, text):
        for word in self.words.finditer(text):
            yield word.group(), word.start(), word.end()

    def highlightBlock(self, text):
        if not (text and self.spell_check.enabled and self.spell_check.dict):
            return
        formatter = QtGui.QTextCharFormat()
        formatter.setUnderlineColor(Qt.red)
        formatter.setUnderlineStyle(QtGui.QTextCharFormat.SpellCheckUnderline)
        for word, start, end in self.findWords(text):
            if not self.spell_check.dict.check(word):
                self.setFormat(start, end - start, formatter)

    def suggestions(self, word):
        if not (self.spell_check.enabled and self.spell_check.dict):
            return []
        if self.spell_check.dict.check(word):
            return []
        return self.spell_check.dict.suggest(word)


class MultiLineEdit(QtWidgets.QPlainTextEdit):
    editingFinished = QtCore.pyqtSignal()

    def __init__(self, spell_check=False, *arg, **kw):
        super(MultiLineEdit, self).__init__(*arg, **kw)
        self.multiple_values = multiple_values()
        self.setTabChangesFocus(True)
        self._is_multiple = False
        if spell_check:
            self.spell_check = SpellingHighlighter(self.document())
        else:
            self.spell_check = None

    def focusOutEvent(self, event):
        if not self._is_multiple:
            self.editingFinished.emit()
        super(MultiLineEdit, self).focusOutEvent(event)

    def keyPressEvent(self, event):
        if self._is_multiple:
            self._is_multiple = False
            if qt_version_info >= (5, 3):
                self.setPlaceholderText('')
        super(MultiLineEdit, self).keyPressEvent(event)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        suggestion_group = QtWidgets.QActionGroup(menu)
        if self._is_multiple:
            if self.choices:
                sep = menu.insertSeparator(menu.actions()[0])
                fm = menu.fontMetrics()
                for suggestion in self.choices:
                    label = six.text_type(suggestion).replace('\n', ' ')
                    label = fm.elidedText(label, Qt.ElideMiddle, self.width())
                    action = QtWidgets.QAction(label, suggestion_group)
                    action.setData(six.text_type(suggestion))
                    menu.insertAction(sep, action)
        elif self.spell_check:
            cursor = self.cursorForPosition(event.pos())
            block_pos = cursor.block().position()
            for word, start, end in self.spell_check.findWords(cursor.block().text()):
                if start > cursor.positionInBlock():
                    break
                if end <= cursor.positionInBlock():
                    continue
                cursor.setPosition(block_pos + start)
                cursor.setPosition(block_pos + end, QtGui.QTextCursor.KeepAnchor)
                break
            word = cursor.selectedText()
            if word:
                suggestions = self.spell_check.suggestions(word)
                if suggestions:
                    sep = menu.insertSeparator(menu.actions()[0])
                    for suggestion in suggestions:
                        action = QtWidgets.QAction(suggestion, suggestion_group)
                        menu.insertAction(sep, action)
        action = menu.exec_(event.globalPos())
        if action and action.actionGroup() == suggestion_group:
            if self._is_multiple:
                self.set_value(action.data())
            else:
                cursor.setPosition(block_pos + start)
                cursor.setPosition(block_pos + end, QtGui.QTextCursor.KeepAnchor)
                cursor.insertText(action.iconText())

    def set_value(self, value):
        self._is_multiple = False
        if not value:
            self.clear()
            if qt_version_info >= (5, 3):
                self.setPlaceholderText('')
        else:
            self.setPlainText(six.text_type(value))

    def get_value(self):
        value = self.toPlainText()
        if qt_version_info < (5, 3) and value == self.multiple_values:
            return ''
        return value

    def set_multiple(self, choices=[]):
        self._is_multiple = True
        self.choices = list(choices)
        if qt_version_info >= (5, 3):
            self.setPlaceholderText(self.multiple_values)
            self.clear()
        else:
            self.setPlainText(self.multiple_values)

    def is_multiple(self):
        return self._is_multiple and not bool(self.get_value())


class SingleLineEdit(MultiLineEdit):
    def __init__(self, *arg, **kw):
        super(SingleLineEdit, self).__init__(*arg, **kw)
        self.setFixedHeight(
            self.fontMetrics().lineSpacing() + 8 + (self.frameWidth() * 2))
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Return:
            event.ignore()
            return
        super(SingleLineEdit, self).keyPressEvent(event)

    def insertFromMimeData(self, source):
        self.insertPlainText(source.text().replace('\n', ' '))


class Slider(QtWidgets.QSlider):
    editing_finished = QtCore.pyqtSignal()

    def focusOutEvent(self, event):
        self.editing_finished.emit()
        super(Slider, self).focusOutEvent(event)


class SquareButton(QtWidgets.QPushButton):
    def sizeHint(self):
        size = super(SquareButton, self).sizeHint()
        size.setHeight(size.height() - 4)
        size.setWidth(size.height())
        return size


class StartStopButton(QtWidgets.QPushButton):
    click_start = QtCore.pyqtSignal()
    click_stop = QtCore.pyqtSignal()

    def __init__(self, start_text, stop_text, *arg, **kw):
        super(StartStopButton, self).__init__(*arg, **kw)
        self.start_text = start_text
        self.stop_text = stop_text
        self.setCheckable(True)
        self.toggled.connect(self.toggle_text)
        self.clicked.connect(self.do_clicked)
        # get a size big enough for either text
        self.setText(self.stop_text)
        stop_size = super(StartStopButton, self).sizeHint()
        self.setText(self.start_text)
        start_size = super(StartStopButton, self).sizeHint()
        self.minimum_size = stop_size.expandedTo(start_size)

    def sizeHint(self):
        return self.minimum_size

    @QtCore.pyqtSlot(bool)
    def toggle_text(self, checked):
        if checked:
            self.setText(self.stop_text)
        else:
            self.setText(self.start_text)

    @QtCore.pyqtSlot(bool)
    def do_clicked(self, checked):
        if checked:
            self.click_start.emit()
        else:
            self.click_stop.emit()
