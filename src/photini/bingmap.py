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
import webbrowser

import six

from photini.configstore import key_store
from photini.photinimap import PhotiniMap
from photini.pyqt import QtCore, QtGui, QtWebEngineWidgets, QtWebKit, QtWidgets

class BingMap(PhotiniMap):
    def __init__(self, *arg, **kw):
        super(BingMap, self).__init__(*arg, **kw)
        if not QtWebEngineWidgets:
            self.map.settings().setAttribute(
                QtWebKit.QWebSettings.LocalContentCanAccessRemoteUrls, True)
            self.map.settings().setAttribute(
                QtWebKit.QWebSettings.LocalContentCanAccessFileUrls, True)

    def get_page_elements(self):
        url = 'http://www.bing.com/api/maps/mapcontrol?callback=initialize'
        lang, encoding = locale.getdefaultlocale()
        if lang:
            url += '&mkt={0},ngt'.format(lang.replace('_', '-'))
        else:
            url += '&mkt=ngt'
        if self.app.test_mode:
            url += '&branch=experimental'
        return {
            'head': '''
    <script type="text/javascript">
      var api_key = "{}";
    </script>
    <script type="text/javascript"
      src="{}" async defer>
    </script>
'''.format(key_store.get('bing', 'api_key'), url),
            'body': '',
            }

    def show_terms(self):
        # return widget to display map terms and conditions
        layout = QtWidgets.QVBoxLayout()
        widget = QtWidgets.QPushButton(self.tr('Terms of Use'))
        widget.clicked.connect(self.load_tou)
        widget.setStyleSheet('QPushButton { font-size: 10px }')
        layout.addWidget(widget)
        return layout

    @QtCore.pyqtSlot()
    def load_tou(self):
        webbrowser.open_new(
            'http://www.microsoft.com/maps/assets/docs/terms.aspx')
