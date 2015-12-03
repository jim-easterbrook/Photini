# -*- coding: utf-8 -*-
#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2012-13  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from __future__ import unicode_literals

import logging
import logging.handlers
import os
import sys

from .pyqt import QtCore, QtWidgets

class OutputInterceptor(object):
    def __init__(self, name, stream):
        self.logger = logging.getLogger(name)
        self.stream = stream
        self.flush = self.stream.flush
        self.fileno = self.stream.fileno

    def write(self, msg):
        self.stream.write(msg)
        msg = msg.strip()
        if 'WARNING' in msg:
            self.logger.warning(msg)
        elif msg:
            self.logger.info(msg)

class LoggerWindow(QtWidgets.QWidget):
    class StreamProxy(QtCore.QObject):
        # only the GUI thread is allowed to write messages in the
        # LoggerWindow, so this class acts as a proxy, passing messages
        # over Qt signal/slot for thread safety
        write_text = QtCore.pyqtSignal(str)
        def write(self, msg):
            msg = msg.strip()
            if msg:
                self.write_text.emit(msg)

        flush_text = QtCore.pyqtSignal()
        def flush(self):
            self.flush_text.emit()

    def __init__(self, verbose, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.setWindowTitle(self.tr("Photini error logging"))
        self.setLayout(QtWidgets.QGridLayout())
        self.layout().setRowStretch(0, 1)
        self.layout().setColumnStretch(0, 1)
        # main dialog area
        self.text = QtWidgets.QTextEdit()
        self.text.setReadOnly(True)
        self.text.setMinimumWidth(500)
        self.layout().addWidget(self.text, 0, 0, 1, 2)
        # dismiss button
        dismiss_button = QtWidgets.QPushButton(self.tr('Dismiss'))
        dismiss_button.clicked.connect(self.hide)
        self.layout().addWidget(dismiss_button, 1, 1)
        # Python logger
        logger = logging.getLogger('')
        for handler in logger.handlers:
            logger.removeHandler(handler)
        logger.setLevel(max(logging.ERROR - (verbose * 10), 1))
        stream_proxy = self.StreamProxy(self)
        stream_proxy.write_text.connect(self.write)
        stream_proxy.flush_text.connect(self.flush)
        handler = logging.StreamHandler(stream_proxy)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s: %(levelname)s: %(name)s: %(message)s',
            datefmt='%H:%M:%S'))
        logger.addHandler(handler)
        # intercept stdout and stderr, if they exist
        if sys.stderr:
            sys.stderr = OutputInterceptor('stderr', sys.stderr)
        if sys.stdout:
            sys.stdout = OutputInterceptor('stdout', sys.stdout)

    def shutdown(self):
        logger = logging.getLogger('')
        for handler in logger.handlers:
            logger.removeHandler(handler)

    @QtCore.pyqtSlot(str)
    def write(self, msg):
        self.text.append(msg)

    @QtCore.pyqtSlot()
    def flush(self):
        if self.isHidden():
            self.show()
        self.raise_()
