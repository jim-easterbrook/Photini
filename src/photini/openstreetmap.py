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

import os
import webbrowser

import requests
import six

from photini import __version__
from photini.photinimap import PhotiniMap
from photini.pyqt import QtCore, QtWidgets, qt_version_info

class OpenStreetMap(PhotiniMap):
    def get_page_elements(self):
        return {
            'head': '''
    <link rel="stylesheet"
      href="https://unpkg.com/leaflet@1.0.3/dist/leaflet.css" />
    <script type="text/javascript">
      var L_NO_TOUCH = true;
    </script>
    <script type="text/javascript"
      src="https://unpkg.com/leaflet@1.0.3/dist/leaflet.js">
    </script>
''',
            'body': '''
    <script type="text/javascript">
      initialize();
    </script>
''',
            }

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
            self.trUtf8('Map data ©OpenStreetMap contributors\nlicensed under ODbL'))
        load_tou.clicked.connect(self.load_tou_osm)
        yield load_tou
        load_tou = QtWidgets.QPushButton(
            self.tr('Map tiles by CARTO\nlicensed under CC BY 3.0'))
        load_tou.clicked.connect(self.load_tou_tiles)
        yield load_tou

    @QtCore.pyqtSlot()
    def load_tou_nominatim(self):
        webbrowser.open_new(
            'https://operations.osmfoundation.org/policies/nominatim/')

    @QtCore.pyqtSlot()
    def load_tou_leaflet(self):
        webbrowser.open_new('http://leafletjs.com/')

    @QtCore.pyqtSlot()
    def load_tou_osm(self):
        webbrowser.open_new('http://www.openstreetmap.org/copyright')

    @QtCore.pyqtSlot()
    def load_tou_tiles(self):
        webbrowser.open_new('https://carto.com/attribution')

    @QtCore.pyqtSlot()
    def search(self, search_string=None):
        if not search_string:
            search_string = self.edit_box.lineEdit().text()
            self.edit_box.clearEditText()
        if not search_string:
            return
        self.search_string = search_string
        self.clear_search()
        params = {
            'q': search_string,
            'format': 'json',
            'polygon': '0',
            'addressdetails': '0',
            }
        if 'bounds' in self.map_status:
            bounds = self.map_status['bounds']
            params['viewbox'] = '{:.8f},{:.8f},{:.8f},{:.8f}'.format(
                bounds[3], bounds[0], bounds[1], bounds[2])
        headers = {'user-agent': 'Photini/' + __version__}
        rsp = requests.get(
            'http://nominatim.openstreetmap.org/search',
            params=params, headers=headers)
        for result in rsp.json():
            self.search_result(
                result['boundingbox'][0], result['boundingbox'][3],
                result['boundingbox'][1], result['boundingbox'][2],
                result['display_name'])

    @QtCore.pyqtSlot(six.text_type)
    def marker_drag_start(self, marker_id):
        blocked = self.image_list.blockSignals(True)
        self.image_list.select_images(self.marker_images[marker_id])
        self.image_list.blockSignals(blocked)
        self.coords.setEnabled(True)
        for other_id, images in self.marker_images.items():
            if other_id != marker_id:
                self.JavaScript('enableMarker("{}", {:d})'.format(
                    other_id, False))
        self.display_coords()
