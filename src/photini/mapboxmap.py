##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2018-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import requests

from photini.configstore import key_store
from photini.photinimap import GeocoderBase, PhotiniMap
from photini.pyqt import Busy, catch_all, QtCore, QtGui, QtSlot, QtWidgets
from photini.widgets import CompactButton

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class MapboxGeocoder(GeocoderBase):
    api_key = key_store.get('mapboxmap', 'api_key')
    cache_size = 0

    def query(self, params):
        query = params['query']
        del params['query']
        params['access_token'] = self.api_key
        params['autocomplete '] = 'false'
        lang, encoding = locale.getlocale()
        if lang:
            params['language'] = lang
        query += '.json'
        url = 'https://api.mapbox.com/geocoding/v5/mapbox.places/' + query
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
        self.block_timer.setInterval(
            self.interval * 600 // max(int(rsp.headers['X-Rate-Limit-Limit']), 1))
        rsp = rsp.json()
        return rsp['features']

    def search(self, search_string, bounds=None):
        params = {
            'query': search_string,
            'limit': '10',
            }
        if bounds:
            north, east, south, west = bounds
            margin = (10.0 + west - east) / 2.0
            if margin > 0.0:
                east += margin
                west -= margin
            margin = (10.0 + south - north) / 2.0
            if margin > 0.0:
                north = min(north + margin,  90.0)
                south = max(south - margin, -90.0)
            params['bbox'] = '{:.4f},{:.4f},{:.4f},{:.4f}'.format(
                west, south, east, north)
        for feature in self.query(params):
            if 'place_name' not in feature:
                continue
            if 'bbox' in feature:
                west, south, east, north = feature['bbox']
                yield north, east, south, west, feature['place_name']
            elif 'center' in feature:
                east, north = feature['center']
                yield north, east, None, None, feature['place_name']

    def search_terms(self):
        widget = CompactButton(
            translate('MapTabMapbox', 'Search powered by Mapbox'))
        widget.clicked.connect(self.load_mapbox_tos)
        return [widget]

    @QtSlot()
    @catch_all
    def load_mapbox_tos(self):
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl('https://www.mapbox.com/tos/'))


class TabWidget(PhotiniMap):
    api_key = key_store.get('mapboxmap', 'api_key')

    @staticmethod
    def tab_name():
        return translate('MapTabMapbox', 'Map (&Mapbox)')

    def get_geocoder(self):
        return MapboxGeocoder(parent=self)

    def get_head(self):
        url = 'https://api.mapbox.com/mapbox-gl-js/v3.4.0'
        return """<script type="text/javascript">
var exports = {{}};
</script>
<script src='{url}/mapbox-gl.js'></script>
<link href='{url}/mapbox-gl.css' rel='stylesheet' />
<script
 src="https://cdnjs.cloudflare.com/ajax/libs/mapbox-gl-style-switcher/1.0.11/index.min.js"
 integrity="sha512-YUXVABhePA/4bucH67dmr0jHhoAftZaohBcK9iHk4XhwPpV1Tp5I2OhKooiettXrc29cdCe0TER4D+YPJg6HOA=="
 crossorigin="anonymous" referrerpolicy="no-referrer"></script>
<link rel="stylesheet"
 href="https://cdnjs.cloudflare.com/ajax/libs/mapbox-gl-style-switcher/1.0.11/styles.min.css"
 integrity="sha512-0Yn+skifSWsXXCwOpPt30lf5Yq3bXo607axVyGBNJZPJPAhMFhTImY/AOMY4oH7Cpd3dwjF9T8YK/n64qPZsDQ=="
 crossorigin="anonymous" referrerpolicy="no-referrer" />
<script type="text/javascript" src="mapboxmap.js"></script>""".format(url=url)

    def get_body(self):
        return '''  <body onload="initialize()" ondragstart="return false">
    <div id="mapDiv"></div>
  </body>
'''

    def get_options(self):
        options = {'accessToken': self.api_key}
        lang, encoding = locale.getlocale()
        if lang:
            language, sep, region = lang.replace('_', '-').partition('-')
            options['language'] = language
            if region:
                options['worldview'] = region
        return options
