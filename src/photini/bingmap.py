##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-21  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import requests

from photini.configstore import key_store
from photini.photinimap import GeocoderBase, PhotiniMap
from photini.pyqt import Busy, catch_all, Qt, QtCore, QtWidgets, scale_font

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class BingGeocoder(GeocoderBase):
    interval = 50

    def query(self, params, url):
        params['key'] = self.api_key
        with Busy():
            self.rate_limit()
            try:
                rsp = requests.get(url, params=params, timeout=5)
            except Exception as ex:
                logger.error(str(ex))
                return []
        if rsp.status_code >= 400:
            logger.error('Search error %d', rsp.status_code)
            return []
        if rsp.headers['X-MS-BM-WS-INFO'] == '1':
            logger.error(translate(
                'MapTabBing', 'Server overload, please try again'))
            self.block_timer.start(5000)
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

    def get_altitude(self, coords):
        params = {
            'points' : coords.replace(' ', ''),
            'heights': 'sealevel',
            }
        resource_sets = self.cached_query(
            params, 'http://dev.virtualearth.net/REST/v1/Elevation/List')
        if resource_sets:
            return resource_sets[0]['resources'][0]['elevations'][0]
        return None

    def search(self, search_string, bounds=None):
        params = {
            'query' : search_string,
            'maxRes': '20',
            }
        lang, encoding = locale.getdefaultlocale()
        if lang:
            params['culture'] = lang.replace('_', '-')
        if bounds:
            north, east, south, west = bounds
            params['userMapView'] = '{:.4f},{:.4f},{:.4f},{:.4f}'.format(
                south, west, north, east)
        for resource_set in self.cached_query(
                params, 'http://dev.virtualearth.net/REST/v1/Locations'):
            for resource in resource_set['resources']:
                south, west, north, east = resource['bbox']
                yield north, east, south, west, resource['name']

    def search_terms(self):
        widget = QtWidgets.QLabel(translate(
            'MapTabBing', 'Search and altitude lookup\nprovided by Bing'))
        widget.setAlignment(Qt.AlignRight)
        scale_font(widget, 80)
        return [widget]


class TabWidget(PhotiniMap):
    api_key = key_store.get('bingmap', 'api_key')

    @staticmethod
    def tab_name():
        return translate('MapTabBing', 'Map (&Bing)')

    def get_geocoder(self):
        return BingGeocoder(parent=self)

    def get_head(self):
        url = 'http://www.bing.com/api/maps/mapcontrol?callback=initialize'
        url += '&key=' + self.api_key
        lang, encoding = locale.getdefaultlocale()
        if lang:
            culture = lang.replace('_', '-')
            url += '&setMkt=' + culture
            language, sep, region = culture.partition('-')
            url += '&setLang=' + language
        if self.app.options.test:
            url += '&branch=experimental'
        return '''    <script type="text/javascript"
      src="{}" async>
    </script>'''.format(url)

    @catch_all
    def new_status(self, status):
        super(TabWidget, self).new_status(status)
        if 'session_id' in status:
            # use map session key to make API calls non-billable
            self.geocoder.api_key = status['session_id']
