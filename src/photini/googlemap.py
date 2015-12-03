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
import re
import webbrowser

from .configstore import key_store
from .photinimap import PhotiniMap
from .pyqt import QtWidgets

class GoogleMap(PhotiniMap):
    def load_api(self):
        url = 'http://maps.googleapis.com/maps/api/js?v=3'
        url += '&key=' + key_store.get('google', 'api_key')
        lang, encoding = locale.getdefaultlocale()
        if lang:
            match = re.match('[a-zA-Z]+[-_]([A-Z]+)', lang)
            if match:
                name = match.group(1)
                if name:
                    url += '&region=' + name
        return """
    <script type="text/javascript"
      src="{}">
    </script>
""".format(url)

    def show_terms(self):
        # return widgets to display map terms and conditions
        yield QtWidgets.QLabel(self.tr('Search powered by Google'))
        load_tou = QtWidgets.QPushButton(self.tr('Terms of Use'))
        load_tou.clicked.connect(self.load_tou)
        yield load_tou

    def load_tou(self):
        webbrowser.open_new('http://www.google.com/help/terms_maps.html')
