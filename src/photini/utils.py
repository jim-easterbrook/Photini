##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-14  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from PyQt4 import QtGui
from PyQt4.QtCore import Qt

data_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data', '')

class Busy(object):
    def __enter__(self):
        QtGui.QApplication.setOverrideCursor(Qt.WaitCursor)
        return self

    def __exit__(self, type, value, traceback):
        QtGui.QApplication.restoreOverrideCursor()
