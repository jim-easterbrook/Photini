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

from photini.photinimap import PhotiniMap
from photini.pyqt import (
    Busy, catch_all, QtCore, QtGui, QtWebEngineWidgets, QtWebKit, QtWidgets)

logger = logging.getLogger(__name__)


if QtWebEngineWidgets:
    WebSettings = QtWebEngineWidgets.QWebEngineSettings
else:
    WebSettings = QtWebKit.QWebSettings


class BingMap(PhotiniMap):
    def __init__(self, *arg, **kw):
        super(BingMap, self).__init__(*arg, **kw)
        if QtWebEngineWidgets:
            self.map.settings().setAttribute(
                WebSettings.Accelerated2dCanvasEnabled, False)
        self.map.settings().setAttribute(
            WebSettings.LocalContentCanAccessRemoteUrls, True)
        self.map.settings().setAttribute(
            WebSettings.LocalContentCanAccessFileUrls, True)

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
'''.format(self.api_key, url),
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
    @catch_all
    def load_tou(self):
        webbrowser.open_new(
            'http://www.microsoft.com/maps/assets/docs/terms.aspx')

    def do_geocode(self, query='', params={}):
        self.disable_search()
        params['key'] = self.map_status['session_id']
        url = 'http://dev.virtualearth.net/REST/v1/Locations'
        if query:
            url += '/' + query
        with Busy():
            try:
                rsp = requests.get(url, params=params, timeout=5)
            except Exception as ex:
                logger.error(str(ex))
                return []
        if rsp.status_code >= 400:
            logger.error('Search error %d', rsp.status_code)
            return []
        if rsp.headers['X-MS-BM-WS-INFO'] == '1':
            logger.error('Server overload')
        else:
            # re-enable search immediately rather than after timeout
            self.enable_search()
        rsp = rsp.json()
        if rsp['statusCode'] != 200:
            logger.error('Search error %d: %s',
                         rsp['statusCode'], rsp['statusDescription'])
            return []
        resource_sets = rsp['resourceSets']
        if not resource_sets:
            logger.error('No results found')
            return []
        return resource_sets

    address_map = {
        'country_code'  : ('countryRegionIso2',),
        'country_name'  : ('countryRegion',),
        'province_state': ('adminDistrict2', 'adminDistrict'),
        'city'          : ('neighborhood', 'locality'),
        'sublocation'   : ('landmark', 'addressLine'),
        }

    def reverse_geocode(self, coords):
        query = coords
        params = {
            'inclnb': '1',
            'incl'  : 'ciso2',
            }
        resource_sets = self.do_geocode(query=query, params=params)
        if not resource_sets:
            return None
        address = resource_sets[0]['resources'][0]['address']
        for key in ('formattedAddress', 'postalCode'):
            if key in address:
                del address[key]
        return address

    def geocode(self, search_string, north, east, south, west):
        params = {
            'q'     : search_string,
            'maxRes': 20,
            'umv'   : '{!r},{!r},{!r},{!r}'.format(south, west, north, east),
            }
        for resource_set in self.do_geocode(params=params):
            for resource in resource_set['resources']:
                south, west, north, east = resource['bbox']
                yield north, east, south, west, resource['name']
