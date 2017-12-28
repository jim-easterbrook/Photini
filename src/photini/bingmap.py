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

import requests
import six

from photini.configstore import key_store
from photini.photinimap import PhotiniMap
from photini.pyqt import (
    Busy, QtCore, QtGui, QtWebEngineWidgets, QtWebKit, QtWidgets)

class BingMap(PhotiniMap):
    def __init__(self, *arg, **kw):
        super(BingMap, self).__init__(*arg, **kw)
        if not QtWebEngineWidgets:
            self.map.settings().setAttribute(
                QtWebKit.QWebSettings.LocalContentCanAccessRemoteUrls, True)
            self.map.settings().setAttribute(
                QtWebKit.QWebSettings.LocalContentCanAccessFileUrls, True)
        self.api_key = key_store.get('bing', 'api_key')

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
    def load_tou(self):
        webbrowser.open_new(
            'http://www.microsoft.com/maps/assets/docs/terms.aspx')

    def do_search(self, query='', params={}):
        self.disable_search()
        params['key'] = self.api_key
        url = 'http://dev.virtualearth.net/REST/v1/Locations'
        if query:
            url += '/' + query
        with Busy():
            try:
                rsp = requests.get(url, params=params, timeout=5)
            except Exception as ex:
                self.logger.error(str(ex))
                return None
        if rsp.status_code >= 400:
            self.logger.error('Search error %d', rsp.status_code)
            return None
        if rsp.headers['X-MS-BM-WS-INFO'] == '1':
            self.logger.error('Server overload')
        else:
            # re-enable search immediately rather than after timeout
            self.enable_search()
        rsp = rsp.json()
        if rsp['statusCode'] != 200:
            self.logger.error('Search error %d: %s',
                              rsp['statusCode'], rsp['statusDescription'])
            return None
        resource_sets = rsp['resourceSets']
        if not resource_sets:
            self.logger.error('No results found')
            return None
        return resource_sets

    @QtCore.pyqtSlot()
    def get_address(self):
        query = self.coords.get_value().replace(' ', '')
        params = {
            'inclnb': '1',
            'incl'  : 'ciso2',
            }
        resource_sets = self.do_search(query=query, params=params)
        if not resource_sets:
            return
        address = resource_sets[0]['resources'][0]['address']
        location = []
        for iptc_key, bing_keys in (
                ('world_region',   ('no_key',)),
                ('country_code',   ('countryRegionIso2',)),
                ('country_name',   ('countryRegion',)),
                ('province_state', ('adminDistrict', 'adminDistrict2')),
                ('city',           ('locality', 'neighborhood')),
                ('sublocation',    ('landmark', 'addressLine'))):
            element = []
            for key in bing_keys:
                if key not in address:
                    continue
                if address[key] not in element:
                    element.append(address[key])
                del(address[key])
            location.append(', '.join(element))
        # put any remaining keys in sublocation
        for key in address:
            if key in ('formattedAddress', 'postalCode'):
                continue
            location[-1] = '{}: {}, {}'.format(key, address[key], location[-1])
        self.set_location_taken(*location)

    @QtCore.pyqtSlot()
    def search(self, search_string=None):
        if not search_string:
            search_string = self.edit_box.lineEdit().text()
            self.edit_box.clearEditText()
        if not search_string:
            return
        self.search_string = search_string
        self.clear_search()
        north, east, south, west = self.map_status['bounds']
        params = {
            'q'     : search_string,
            'maxRes': 20,
            'umv'   : '{!r},{!r},{!r},{!r}'.format(south, west, north, east),
            }
        resource_sets = self.do_search(params=params)
        if not resource_sets:
            return
        for resource_set in resource_sets:
            for resource in resource_set['resources']:
                south, west, north, east = resource['bbox']
                self.search_result(north, east, south, west, resource['name'])
