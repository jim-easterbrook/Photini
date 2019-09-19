##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-19  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

    def do_geocode(self, query='', params={}):
        url = 'http://dev.virtualearth.net/REST/v1/Locations'
        if query:
            url += '/' + query
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
            logger.error('Server overload')
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

    def search(self, search_string, map_status, bounds=None):
        params = {
            'key'   : map_status['session_id'],
            'q'     : search_string,
            'maxRes': 20,
            }
        if bounds:
            north, east, south, west = bounds
            params['umv'] = '{!r},{!r},{!r},{!r}'.format(
                south, west, north, east)
        for resource_set in self.do_geocode(params=params):
            for resource in resource_set['resources']:
                south, west, north, east = resource['bbox']
                yield north, east, south, west, resource['name']

    def search_terms(self):
        widget = QtWidgets.QLabel(translate('BingMap', 'Search powered by Bing'))
        widget.setAlignment(Qt.AlignRight)
        scale_font(widget, 80)
        return [widget]


class TabWidget(PhotiniMap):
    api_key = key_store.get('bingmap', 'api_key')

    @staticmethod
    def tab_name():
        return translate('BingMap', 'Map (&Bing)')

    def get_geocoder(self):
        return BingGeocoder(parent=self)

    def get_head(self):
        url = 'http://www.bing.com/api/maps/mapcontrol?callback=initialize'
        url += '&key=' + self.api_key
        lang, encoding = locale.getdefaultlocale()
        if lang:
            url += '&mkt={0},ngt'.format(lang.replace('_', '-'))
        else:
            url += '&mkt=ngt'
        if self.app.test_mode:
            url += '&branch=experimental'
        return '''
    <script type="text/javascript"
      src="{}" async>
    </script>
'''.format(url)
