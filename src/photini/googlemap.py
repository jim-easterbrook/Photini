# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-17  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import os
import re
import webbrowser

from photini.configstore import key_store
from photini.photinimap import PhotiniMap
from photini.pyqt import QtCore, QtWidgets

class GoogleMap(PhotiniMap):
    def get_page_elements(self):
        url = 'http://maps.googleapis.com/maps/api/js?callback=initialize&v=3'
        if self.app.test_mode:
            url += '.exp'
        url += '&key=' + key_store.get('google', 'api_key')
        lang, encoding = locale.getdefaultlocale()
        if lang:
            match = re.match('[a-zA-Z]+[-_]([A-Z]+)', lang)
            if match:
                name = match.group(1)
                if name:
                    url += '&region=' + name
        return {
            'head': '',
            'body': '''
    <script type="text/javascript"
      src="{}" async defer>
    </script>
'''.format(url),
            }

    def show_terms(self):
        # return widget to display map terms and conditions
        layout = QtWidgets.QVBoxLayout()
        widget = QtWidgets.QLabel(self.tr('Search powered by Google'))
        widget.setStyleSheet('QLabel { font-size: 10px }')
        layout.addWidget(widget)
        widget = QtWidgets.QPushButton(self.tr('Terms of Use'))
        widget.clicked.connect(self.load_tou)
        widget.setStyleSheet('QPushButton { font-size: 10px }')
        layout.addWidget(widget)
        return layout

    @QtCore.pyqtSlot()
    def load_tou(self):
        webbrowser.open_new('http://www.google.com/help/terms_maps.html')
