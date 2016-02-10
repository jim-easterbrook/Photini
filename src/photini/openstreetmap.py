# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-16  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import webbrowser

from .photinimap import PhotiniMap
from .pyqt import QtWidgets, qt_version_info

class OpenStreetMap(PhotiniMap):
    def load_api(self):
        return """
    <link rel="stylesheet"
      href="http://cdn.leafletjs.com/leaflet/v0.7.7/leaflet.css" />
    <script type="text/javascript">
      var L_NO_TOUCH = true;
    </script>
    <script type="text/javascript"
      src="http://cdn.leafletjs.com/leaflet/v0.7.7/leaflet.js">
    </script>
"""

    def show_terms(self):
        # return widgets to display map terms and conditions
        load_tou = QtWidgets.QPushButton(self.tr('Search powered by Nominatim'))
        load_tou.clicked.connect(self.load_tou_nominatim)
        yield load_tou
        load_tou = QtWidgets.QPushButton(self.tr('Map powered by Leaflet'))
        load_tou.clicked.connect(self.load_tou_leaflet)
        yield load_tou
        if qt_version_info >= (5, 0):
            self.trUtf8 = self.tr
        load_tou = QtWidgets.QPushButton(
            self.trUtf8('Map data\n©OpenStreetMap contributors'))
        load_tou.clicked.connect(self.load_tou_osm)
        yield load_tou
        load_tou = QtWidgets.QPushButton(self.tr('Tiles courtesy of MapQuest'))
        load_tou.clicked.connect(self.load_tou_tiles)
        yield load_tou

    def load_tou_nominatim(self):
        webbrowser.open_new(
            'http://wiki.openstreetmap.org/wiki/Nominatim_usage_policy')

    def load_tou_leaflet(self):
        webbrowser.open_new('http://leafletjs.com/')

    def load_tou_osm(self):
        webbrowser.open_new('http://www.openstreetmap.org/copyright')

    def load_tou_tiles(self):
        webbrowser.open_new('http://www.mapquest.com/')
