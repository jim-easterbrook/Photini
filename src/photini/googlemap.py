##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import locale
import logging
import re

import requests

from photini.configstore import key_store
from photini.photinimap import GeocoderBase, PhotiniMap
from photini.pyqt import Busy, Qt, QtCore, QtWidgets, scale_font
from photini.widgets import Label

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class GoogleGeocoder(GeocoderBase):
    api_key = key_store.get('googlemap', 'api_key')
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
        rsp = rsp.json()
        if rsp['status'] != 'OK':
            if 'error_message' in rsp:
                logger.error(
                    'Search error: %s: %s', rsp['status'], rsp['error_message'])
            else:
                logger.error('Search error: %s', rsp['status'])
            return []
        results = rsp['results']
        if not results:
            logger.error('No results found')
            return []
        return results

    def get_altitude(self, coords):
        params = {'locations': '{:.5f},{:.5f}'.format(*coords)}
        results = self.cached_query(
            params, 'https://maps.googleapis.com/maps/api/elevation/json')
        if results:
            return results[0]['elevation']
        return None

    def search(self, search_string, bounds=None):
        params = {'address': search_string}
        lang, encoding = locale.getlocale()
        if lang:
            params['language'] = lang
        if bounds:
            north, east, south, west = bounds
            params['bounds'] = '{:.4f},{:.4f}|{:.4f},{:.4f}'.format(
                south, west, north, east)
        for result in self.cached_query(
                params, 'https://maps.googleapis.com/maps/api/geocode/json'):
            bounds = result['geometry']['viewport']
            yield (bounds['northeast']['lat'], bounds['northeast']['lng'],
                   bounds['southwest']['lat'], bounds['southwest']['lng'],
                   result['formatted_address'])

    def search_terms(self):
        widget = Label(translate(
            'MapTabGoogle', 'Search and altitude lookup powered by Google',
            'Do not translate "powered by Google"'), lines=2)
        widget.setAlignment(Qt.AlignmentFlag.AlignRight)
        scale_font(widget, 80)
        return [widget]


class TabWidget(PhotiniMap):
    api_key = key_store.get('googlemap', 'api_key')

    @staticmethod
    def tab_name():
        return translate('MapTabGoogle', 'Map (&Google)')

    def get_geocoder(self):
        return GoogleGeocoder(parent=self)

    def get_head(self):
        user_agent = self.widgets['map'].page().profile().httpUserAgent()
        match = re.search(r'\sChrome/(\d+)\.', user_agent)
        if match:
            chrome_version = int(match.group(1))
        else:
            chrome_version = 0
        url = ('http://maps.googleapis.com/maps/api/js'
               '?callback=initialize'
               '&loading=async')
        # AdvancedMarkerElement requires Chrome v86+
        if chrome_version >= 86:
            url += '&libraries=marker'
            script = 'googlemap.js'
        else:
            script = 'googlemap_legacy.js'
        if self.app.options.test:
            url += '&v=beta'
        url += '&key=' + self.api_key
        lang, encoding = locale.getlocale()
        if lang:
            language, sep, region = lang.replace('_', '-').partition('-')
            url += '&language=' + language
            if region:
                url += '&region=' + region
        return '''    <script type="text/javascript"
      src="{}" async>
    </script>
    <script type="text/javascript" src="{}"></script>'''.format(url, script)
