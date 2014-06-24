# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-13  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import webbrowser
import sys

from PyQt4 import QtGui, QtCore

from .photinimap import PhotiniMap

if sys.version < '3':
    text_type = unicode
    binary_type = str
else:
    text_type = str
    binary_type = bytes

class BingMap(PhotiniMap):
    def __init__(self, *arg, **kw):
        self.copyright_widget = QtGui.QLabel()
        self.copyright_widget.setWordWrap(True)
        PhotiniMap.__init__(self, *arg, **kw)

    def load_api(self):
        return """
    <script charset="UTF-8" type="text/javascript"
      src="http://ecn.dev.virtualearth.net/mapcontrol/mapcontrol.ashx?v=7.0">
    </script>
    <script type="text/javascript">
      var api_key = "%s";
    </script>
""" % 'ArJEzSPM47yeCE31K9ZgelN2jPG20egbQNC8DGM__Z4r9Y8U-hvj4vyHJSRoAcCQ'

    def show_terms(self):
        # return a widget to display map terms and conditions
        result = QtGui.QFrame()
        layout = QtGui.QVBoxLayout()
        result.setLayout(layout)
        layout.addWidget(self.copyright_widget)
        load_tou = QtGui.QPushButton('Terms of Use')
        load_tou.clicked.connect(self.load_tou)
        layout.addWidget(load_tou)
        return result

    @QtCore.pyqtSlot(text_type)
    def new_copyright(self, text):
        self.copyright_widget.setText(text)

    def load_tou(self):
        webbrowser.open_new(
            'http://www.microsoft.com/maps/assets/docs/terms.aspx')
