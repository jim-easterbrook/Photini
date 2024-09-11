#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2012-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
#
#  This program is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see
#  <http://www.gnu.org/licenses/>.

import logging
import logging.handlers
import os
import re
import sys

from photini._version import version as photini_version
from photini.ffmpeg import ffmpeg_version
from photini.exiv2 import exiv2_version
from photini.pyqt import (
    catch_all, QtCore, QtSignal, QtSlot, QtWebEngineCore, QtWidgets,
    qt_version, width_for_text)
from photini.spelling import spelling_version

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


def full_version_info():
    version = 'Photini ' + photini_version
    version += '\n  Python ' + sys.version
    version += '\n  ' + exiv2_version
    version += '\n  ' + qt_version
    user_agent = QtWebEngineCore.QWebEngineProfile.defaultProfile(
        ).httpUserAgent()
    match = re.search(r'\sChrome/(.*)\s', user_agent)
    if match:
        version += ', chrome ' + match.group(1)
    version += '\n  system locale ' + QtCore.QLocale.system().bcp47Name()
    version += ', locales: ' + ' '.join(
        QtCore.QLocale.system().uiLanguages())
    if spelling_version:
        version += '\n  ' + spelling_version
    if ffmpeg_version:
        version += '\n  ' + ffmpeg_version
    version += '\n  styles: {}'.format(
        ', '.join(QtWidgets.QStyleFactory.keys()))
    version += '\n  using style: {}'.format(
        QtWidgets.QApplication.style().objectName())
    return version


class StreamProxy(QtCore.QObject):
    # only the GUI thread is allowed to write messages in the
    # LoggerWindow, so this class acts as a proxy, passing messages
    # over Qt signal/slot for thread safety
    flush_text = QtSignal()
    write_text = QtSignal(str)

    def write(self, msg):
        msg = msg.strip()
        if msg:
            self.write_text.emit(msg)

    def flush(self):
        self.flush_text.emit()


class LoggerFilter(object):
    def __init__(self, threshold):
        self.threshold = threshold

    def filter(self, record):
        # raise threshold for non-Photini messages
        threshold = self.threshold
        if not record.name.startswith('photini'):
            threshold += 10
        if record.levelno < threshold:
            return 0
        return 1


class LoggerWindow(QtWidgets.QWidget):
    def __init__(self, verbose, *arg, **kw):
        super(LoggerWindow, self).__init__(*arg, **kw)
        QtWidgets.QApplication.instance().aboutToQuit.connect(self.shutdown)
        self.setWindowTitle(translate('LoggerWindow', "Photini error logging"))
        self.setLayout(QtWidgets.QVBoxLayout())
        self.hidden_words = []
        # main dialog area
        self.text = QtWidgets.QTextEdit()
        self.text.setReadOnly(True)
        self.text.setMinimumWidth(width_for_text(self.text, 'x' * 70))
        self.layout().addWidget(self.text)
        # buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save |
            QtWidgets.QDialogButtonBox.StandardButton.Close)
        button_box.button(
            button_box.StandardButton.Save).clicked.connect(self.save)
        button_box.button(
            button_box.StandardButton.Close).clicked.connect(self.hide)
        self.layout().addWidget(button_box)
        # Python logger
        self.logger = logging.getLogger('')
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)
        threshold = logging.ERROR - (verbose * 10)
        self.logger.setLevel(max(threshold, 1))
        self.stream_proxy = StreamProxy(self)
        self.stream_proxy.write_text.connect(self.write)
        self.stream_proxy.flush_text.connect(self.flush)
        handler = logging.StreamHandler(self.stream_proxy)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s: %(levelname)s: %(name)s: %(message)s',
            datefmt='%H:%M:%S'))
        handler.addFilter(LoggerFilter(threshold))
        self.logger.addHandler(handler)

    def hide_word(self, word):
        if word not in self.hidden_words:
            self.hidden_words.append(word)

    @QtSlot()
    @catch_all
    def shutdown(self):
        self.stream_proxy.write_text.disconnect()
        self.stream_proxy.flush_text.disconnect()
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)

    @QtSlot()
    @catch_all
    def save(self):
        file_name = QtWidgets.QFileDialog.getSaveFileName(
            self, translate('LoggerWindow', 'Save log file'),
            os.path.expanduser('~/photini_log.txt'))
        file_name = file_name[0]
        if file_name:
            with open(file_name, 'w') as of:
                of.write('==== version info ====\n')
                of.write(full_version_info())
                of.write('\n==== messages ====\n')
                of.write(self.text.toPlainText())
                of.write('\n==== end ====\n')

    @QtSlot(str)
    @catch_all
    def write(self, msg):
        for word in self.hidden_words:
            msg = msg.replace(word, 'XXXX')
        self.text.append(msg)

    @QtSlot()
    @catch_all
    def flush(self):
        if self.isHidden():
            self.show()
        self.raise_()
