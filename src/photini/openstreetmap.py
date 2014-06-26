# -*- coding: utf-8 -*-
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

import webbrowser

from PyQt4 import QtGui

from .photinimap import PhotiniMap

class OpenStreetMap(PhotiniMap):
    def load_api(self):
        return """
    <link rel="stylesheet"
      href="http://cdn.leafletjs.com/leaflet-0.7.3/leaflet.css" />
    <script type="text/javascript">
      var L_NO_TOUCH = true;
    </script>
    <script type="text/javascript"
      src="http://cdn.leafletjs.com/leaflet-0.7.3/leaflet.js">
    </script>
"""

    def show_terms(self):
        # return a widget to display map terms and conditions
        result = QtGui.QFrame()
        layout = QtGui.QVBoxLayout()
        result.setLayout(layout)
        load_tou = QtGui.QPushButton('Search powered by Nominatim')
        load_tou.clicked.connect(self.load_tou_nominatim)
        layout.addWidget(load_tou)
        load_tou = QtGui.QPushButton('Map powered by Leaflet')
        load_tou.clicked.connect(self.load_tou_leaflet)
        layout.addWidget(load_tou)
        load_tou = QtGui.QPushButton('Map data\n©OpenStreetMap contributors')
        load_tou.clicked.connect(self.load_tou_osm)
        layout.addWidget(load_tou)
        load_tou = QtGui.QPushButton('Tiles courtesy of MapQuest')
        load_tou.clicked.connect(self.load_tou_tiles)
        layout.addWidget(load_tou)
        return result

    def load_tou_nominatim(self):
        webbrowser.open_new(
            'http://wiki.openstreetmap.org/wiki/Nominatim_usage_policy')

    def load_tou_leaflet(self):
        webbrowser.open_new('http://leafletjs.com/')

    def load_tou_osm(self):
        webbrowser.open_new('http://www.openstreetmap.org/copyright')

    def load_tou_tiles(self):
        webbrowser.open_new('http://www.mapquest.com/')
