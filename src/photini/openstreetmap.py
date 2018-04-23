# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-18  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import logging
import os
import webbrowser

import requests
import six

from photini.photinimap import PhotiniMap
from photini.pyqt import Busy, catch_all, Qt, QtCore, QtWidgets, qt_version_info

logger = logging.getLogger(__name__)

class OpenStreetMap(PhotiniMap):
    def get_page_elements(self):
        return {
            'head': '''
    <link rel="stylesheet"
      href="https://unpkg.com/leaflet@1/dist/leaflet.css" />
    <script type="text/javascript">
      var L_NO_TOUCH = true;
    </script>
    <script type="text/javascript"
      src="https://unpkg.com/leaflet@1/dist/leaflet.js">
    </script>
''',
            'body': '''
    <script type="text/javascript">
      initialize();
    </script>
''',
            }

    def show_terms(self):
        # return widget to display map terms and conditions
        layout = QtWidgets.QGridLayout()
        widget = QtWidgets.QPushButton(self.tr('Search powered by OpenCage'))
        widget.clicked.connect(self.load_tou_opencage)
        widget.setStyleSheet('QPushButton { font-size: 9px }')
        layout.addWidget(widget, 0, 0)
        widget = QtWidgets.QPushButton(
            self.tr('Map powered by Leaflet {}').format(
                self.map_status['version']))
        widget.clicked.connect(self.load_tou_leaflet)
        widget.setStyleSheet('QPushButton { font-size: 9px }')
        layout.addWidget(widget, 0, 1)
        widget = QtWidgets.QPushButton(
            self.tr('Map data ©OpenStreetMap\ncontributors, licensed under ODbL'))
        widget.clicked.connect(self.load_tou_osm)
        widget.setStyleSheet('QPushButton { font-size: 9px }')
        layout.addWidget(widget, 1, 0)
        widget = QtWidgets.QPushButton(
            self.tr('Map tiles by CARTO\nlicensed under CC BY 3.0'))
        widget.clicked.connect(self.load_tou_tiles)
        widget.setStyleSheet('QPushButton { font-size: 9px }')
        layout.addWidget(widget, 1, 1)
        return layout

    @QtCore.pyqtSlot()
    @catch_all
    def load_tou_opencage(self):
        webbrowser.open_new('https://geocoder.opencagedata.com/')

    @QtCore.pyqtSlot()
    @catch_all
    def load_tou_leaflet(self):
        webbrowser.open_new('http://leafletjs.com/')

    @QtCore.pyqtSlot()
    @catch_all
    def load_tou_osm(self):
        webbrowser.open_new('http://www.openstreetmap.org/copyright')

    @QtCore.pyqtSlot()
    @catch_all
    def load_tou_tiles(self):
        webbrowser.open_new('https://carto.com/attribution')

    def do_geocode(self, params):
        self.disable_search()
        params['key'] = self.api_key
        params['abbrv'] = '1'
        params['no_annotations'] = '1'
        lang, encoding = locale.getdefaultlocale()
        if lang:
            params['language'] = lang
        with Busy():
            try:
                rsp = requests.get(
                    'https://api.opencagedata.com/geocode/v1/json',
                    params=params, timeout=5)
            except Exception as ex:
                logger.error(str(ex))
                return []
        if rsp.status_code >= 400:
            logger.error('Search error %d', rsp.status_code)
            return []
        rsp = rsp.json()
        status = rsp['status']
        if status['code'] != 200:
            logger.error(
                'Search error %d: %s', status['code'], status['message'])
            return []
        if rsp['total_results'] < 1:
            logger.error('No results found')
            return []
        rate = rsp['rate']
        self.block_timer.setInterval(
            5000 * rate['limit'] // max(rate['remaining'], 1))
        return rsp['results']

    address_map = {
        'world_region'  :('continent',),
        'country_code'  :('country_code', 'ISO_3166-1_alpha-2'),
        'country_name'  :('country',),
        'province_state':('region', 'county', 'state_district', 'state'),
        'city'          :('hamlet', 'locality', 'neighbourhood', 'village',
                          'suburb', 'town', 'city_district', 'city'),
        'sublocation'   :('building', 'house_number',
                          'footway', 'pedestrian', 'road', 'street', 'place'),
        }

    def reverse_geocode(self, coords):
        results = self.do_geocode({'q': coords})
        if not results:
            return None
        address = results[0]['components']
        for key in ('political_union', 'postcode', 'road_reference',
                    'road_reference_intl', 'state_code', '_type'):
            if key in address:
                del address[key]
        if 'country_code' in address:
            address['country_code'] = address['country_code'].upper()
        return address

    def geocode(self, search_string, north, east, south, west):
        w = east - west
        h = north - south
        if min(w, h) < 10.0:
            lat, lon = self.map_status['centre']
            north = min(lat + 5.0,  90.0)
            south = max(lat - 5.0, -90.0)
            east = lon + 5.0
            west = lon - 5.0
        params = {
            'q'     : search_string,
            'limit' : '20',
            'bounds': '{!r},{!r},{!r},{!r}'.format(west, south, east, north),
            }
        for result in self.do_geocode(params):
            yield (result['bounds']['northeast']['lat'],
                   result['bounds']['northeast']['lng'],
                   result['bounds']['southwest']['lat'],
                   result['bounds']['southwest']['lng'],
                   result['formatted'])
