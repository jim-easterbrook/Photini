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

import logging

import requests

from photini.configstore import key_store
from photini.photinimap import GeocoderBase, PhotiniMap
from photini.pyqt import Busy, catch_all, QtCore, QtGui, QtSlot, QtWidgets
from photini.widgets import CompactButton

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class MapboxGeocoder(GeocoderBase):
    # see https://docs.mapbox.com/api/search/geocoding-v5/
    api_key = key_store.get('mapboxmap', 'api_key')
    cache_size = 0

    def query(self, params):
        query = params['query']
        del params['query']
        params['access_token'] = self.api_key
        params['autocomplete '] = 'false'
        lang = self.app.locale.bcp47Name()
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
                yield north, east, north, east, feature['place_name']

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
        return """<script
  src='https://api.mapbox.com/mapbox-gl-js/plugins/mapbox-gl-supported/v2.0.0/mapbox-gl-supported.js'>
</script>
<script type="text/javascript">
function chooseMap() {{
    if (mapboxgl.supported())
        loadLibrary('{url_gl}/mapbox-gl.js', '{url_gl}/mapbox-gl.css',
                    'mapboxmap.js');
    else
        loadLibrary('{url_js}/mapbox.js', '{url_js}/mapbox.css',
                    'mapboxmap_legacy.js');
}}
function loadLibrary(jsSource, cssSource, scriptName) {{
    const headElement = document.getElementsByTagName('head')[0];
    const scriptElement = document.createElement('script');
    const styleElement = document.createElement('link');

    styleElement.href = cssSource;
    styleElement.rel = 'stylesheet';
    headElement.appendChild(styleElement);

    scriptElement.type = 'text/javascript';
    scriptElement.onload = function() {{
        loadScript(scriptName);
    }};
    scriptElement.src = jsSource;
    headElement.appendChild(scriptElement);
}}
function loadScript(scriptName) {{
    const headElement = document.getElementsByTagName('head')[0];
    const scriptElement = document.createElement('script');

    scriptElement.type = 'text/javascript';
    scriptElement.onload = initialize;
    scriptElement.src = scriptName;
    headElement.appendChild(scriptElement);
}}
</script>""".format(
    url_gl='https://api.mapbox.com/mapbox-gl-js/v3.6.0',
    url_js='https://api.mapbox.com/mapbox.js/v3.3.1')

    def get_body(self, text_dir):
        return '''  <body onload="chooseMap()" ondragstart="return false">
    <div id="mapDiv" dir="{text_dir}"></div>
  </body>'''.format(text_dir=text_dir)

    def get_options(self):
        options = {'accessToken': self.api_key}
        lang = self.locale().bcp47Name()
        options['language'] = lang
        lang, sep, region = lang.partition('-')
        if region:
            options['worldview'] = region
        return options
