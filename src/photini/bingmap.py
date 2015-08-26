# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-15  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from .configstore import key_store
from .photinimap import PhotiniMap
from .pyqt import QtCore, QtGui, QtWidgets
from .utils import data_dir

class BingMap(PhotiniMap):
    def __init__(self, *arg, **kw):
        self.copyright_widget = QtWidgets.QLabel()
        self.copyright_widget.setWordWrap(True)
        PhotiniMap.__init__(self, *arg, **kw)

    def load_api(self):
        src = 'http://ecn.dev.virtualearth.net/mapcontrol/mapcontrol.ashx?v=7.0'
        api_key = key_store.get('bing', 'api_key')
        lang, encoding = locale.getdefaultlocale()
        if lang:
            src += '&mkt={0},ngt'.format(lang.replace('_', '-'))
        else:
            src += '&mkt=ngt'
        return """
    <script charset="UTF-8" type="text/javascript"
      src="{0}">
    </script>
    <script type="text/javascript">
      var api_key = "{1}";
    </script>
""".format(src, api_key)

    def get_drag_icon(self):
        return QtGui.QPixmap(os.path.join(data_dir, 'bing_grey_marker.png'))

    def show_terms(self):
        # return a widget to display map terms and conditions
        result = QtWidgets.QFrame()
        layout = QtWidgets.QVBoxLayout()
        result.setLayout(layout)
        layout.addWidget(self.copyright_widget)
        load_tou = QtWidgets.QPushButton(self.tr('Terms of Use'))
        load_tou.clicked.connect(self.load_tou)
        layout.addWidget(load_tou)
        return result

    @QtCore.pyqtSlot(six.text_type)
    def new_copyright(self, text):
        self.copyright_widget.setText(text)

    def load_tou(self):
        webbrowser.open_new(
            'http://www.microsoft.com/maps/assets/docs/terms.aspx')
