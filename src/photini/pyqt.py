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

QT_VERSION = list(map(int, QtCore.QT_VERSION_STR.split('.')))
