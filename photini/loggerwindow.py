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

import logging
import logging.handlers
import sys
from PyQt4 import QtGui

class OutputInterceptor(object):
    def __init__(self, name):
        self.logger = logging.getLogger(name)

    def flush(self):
        pass

    def fileno(self):
        return -1

    def write(self, msg):
        msg = msg.strip()
        if 'WARNING' in msg:
            self.logger.warning(msg)
        elif msg:
            self.logger.info(msg)

class LoggerWindow(QtGui.QWidget):
    class Stream(object):
        def __init__(self, parent):
            self.parent = parent

        def write(self, msg):
            msg = msg.strip()
            if msg:
                self.parent.text.append(msg)

        def flush(self):
            if self.parent.isHidden():
                self.parent.show()
            self.parent.raise_()

    def __init__(self, verbose, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.setWindowTitle("Photini error logging")
        self.setLayout(QtGui.QGridLayout())
        self.layout().setRowStretch(0, 1)
        self.layout().setColumnStretch(0, 1)
        # main dialog area
        self.text = QtGui.QTextEdit()
        self.text.setReadOnly(True)
        self.text.setMinimumWidth(500)
        self.layout().addWidget(self.text, 0, 0, 1, 2)
        # dismiss button
        dismiss_button = QtGui.QPushButton('Dismiss')
        dismiss_button.clicked.connect(self.hide)
        self.layout().addWidget(dismiss_button, 1, 1)
        # Python logger
        logger = logging.getLogger('')
        for handler in logger.handlers:
            logger.removeHandler(handler)
        logger.setLevel(max(logging.ERROR - (verbose * 10), 1))
        handler = logging.StreamHandler(self.Stream(self))
        handler.setFormatter(logging.Formatter(
            '%(asctime)s: %(levelname)s: %(name)s: %(message)s',
            datefmt='%H:%M:%S'))
        logger.addHandler(handler)
        # intercept stdout and stderr
        sys.stderr = OutputInterceptor('stderr')
        sys.stdout = OutputInterceptor('stdout')
