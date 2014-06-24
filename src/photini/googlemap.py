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

import locale
import re
import webbrowser

from PyQt4 import QtGui

from .photinimap import PhotiniMap

class GoogleMap(PhotiniMap):
    def __init__(self, config_store, image_list, parent=None):
        # setting the application name & version stops Google maps
        # using the multitouch interface
        app = QtGui.QApplication.instance()
        app.setApplicationName('chrome')
        app.setApplicationVersion('1.0')
        PhotiniMap.__init__(self, config_store, image_list, parent)

    def load_api(self):
        region = ''
        lang, encoding = locale.getdefaultlocale()
        if lang:
            match = re.match('[a-zA-Z]+[-_]([A-Z]+)', lang)
            if match:
                name = match.group(1)
                if name:
                    region = '&region=%s' % name
        return """
    <script type="text/javascript"
      src="http://maps.googleapis.com/maps/api/js?key=%s&sensor=false%s">
    </script>
""" % ('AIzaSyBPUg_kKGYxyzV0jV7Gg9m4rxme97tE13Y', region)

    def show_terms(self):
        # return a widget to display map terms and conditions
        result = QtGui.QFrame()
        layout = QtGui.QVBoxLayout()
        result.setLayout(layout)
        layout.addWidget(QtGui.QLabel('Search powered by Google'))
        load_tou = QtGui.QPushButton('Terms of Use')
        load_tou.clicked.connect(self.load_tou)
        layout.addWidget(load_tou)
        return result

    def load_tou(self):
        webbrowser.open_new('http://www.google.com/help/terms_maps.html')
