##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2018  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import json
import locale
import logging
import os
import pprint
import webbrowser

import requests
import six

from photini.photinimap import PhotiniMap
from photini.pyqt import (Busy, catch_all, Qt, QtCore, QtWebEngineWidgets,
                          QtWebKit, QtWidgets, qt_version_info, scale_font)

logger = logging.getLogger(__name__)


if QtWebEngineWidgets:
    WebSettings = QtWebEngineWidgets.QWebEngineSettings
else:
    WebSettings = QtWebKit.QWebSettings


class MapboxMap(PhotiniMap):
    def __init__(self, *arg, **kw):
        super(MapboxMap, self).__init__(*arg, **kw)
        self.map.settings().setAttribute(
            WebSettings.LocalContentCanAccessRemoteUrls, True)
        self.map.settings().setAttribute(
            WebSettings.LocalContentCanAccessFileUrls, True)

    def get_head(self):
        return '''
    <script type="text/javascript"
      src="https://api.mapbox.com/mapbox.js/v3.1.1/mapbox.js">
    </script>
    <link rel="stylesheet"
      href="https://api.mapbox.com/mapbox.js/v3.1.1/mapbox.css" />
    <script type="text/javascript">
      window.addEventListener('load', initialize);
    </script>
'''

    def show_terms(self):
        # return widget to display map terms and conditions
        layout = QtWidgets.QVBoxLayout()
        widget = QtWidgets.QLabel(self.tr('Search powered by Mapbox'))
        scale_font(widget, 80)
        layout.addWidget(widget)
        widget = QtWidgets.QPushButton(self.tr('Terms of Use'))
        widget.clicked.connect(self.load_tou)
        scale_font(widget, 80)
        layout.addWidget(widget)
        return layout

    @QtCore.pyqtSlot()
    @catch_all
    def load_tou(self):
        webbrowser.open_new('https://www.mapbox.com/tos/')

    def do_geocode(self, query, params={}):
        self.disable_search()
        params['access_token'] = self.api_key
        params['autocomplete '] = 'false'
        lang, encoding = locale.getdefaultlocale()
        if lang:
            params['language'] = lang
        query += '.json'
        url = 'https://api.mapbox.com/geocoding/v5/mapbox.places/' + query
        with Busy():
            try:
                rsp = requests.get(url, params=params, timeout=5)
            except Exception as ex:
                logger.error(str(ex))
                return []
        if rsp.status_code >= 400:
            logger.error('Search error %d', rsp.status_code)
            return []
        self.block_timer.setInterval(
            5000 * 600 // max(int(rsp.headers['X-Rate-Limit-Limit']), 1))
        rsp = rsp.json()
        return rsp['features']

    address_map = {
        'country_code'  : ('country.short_code',),
        'country_name'  : ('country',),
        'province_state': ('district', 'region',),
        'city'          : ('locality', 'place',),
        'sublocation'   : ('poi', 'poi.address', 'address'),
        }

    def reverse_geocode(self, coords):
        lat, lng = coords.split(',')
        address = {}
        for feature in self.do_geocode('{},{}'.format(lng, lat)):
            for place_type in feature['place_type']:
                address[place_type] = feature['text']
                for key, value in feature['properties'].items():
                    if key in ('address', 'short_code'):
                        address[place_type + '.' + key] = value
        for key in ('region.short_code', 'postcode'):
            if key in address:
                del address[key]
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
            'limit': 10,
            'bbox' : '{!r},{!r},{!r},{!r}'.format(west, south, east, north),
            }
        for feature in self.do_geocode(search_string, params=params):
            if 'place_name' not in feature:
                continue
            if 'bbox' in feature:
                west, south, east, north = feature['bbox']
                yield north, east, south, west, feature['place_name']
            elif 'center' in feature:
                east, north = feature['center']
                yield north, east, None, None, feature['place_name']
            else:
                pprint.pprint(feature)
