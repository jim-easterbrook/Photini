#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2024-25  Jim Easterbrook  jim@jim-easterbrook.me.uk
#
#  This file is part of Photini.
#
#  Photini is free software: you can redistribute it and/or modify it
#  under the terms of the GNU General Public License as published by the
#  Free Software Foundation, either version 3 of the License, or (at
#  your option) any later version.
#
#  Photini is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Photini.  If not, see <http://www.gnu.org/licenses/>.

import base64
import logging
import os

import requests

from photini.photinimap import fetch_key, GeocoderBase, PhotiniMap
from photini.pyqt import Busy, catch_all, Qt, QtCore, QtWidgets, scale_font
from photini.widgets import Label

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class AzureGeocoder(GeocoderBase):
    interval = 50

    def query(self, params, url):
        params['subscription-key'] = fetch_key('azuremap')
        with Busy():
            self.rate_limit()
            try:
                rsp = requests.get(url, params=params, timeout=5)
            except Exception as ex:
                logger.error(str(ex))
                return []
        rsp = rsp.json()
        if 'error' in rsp:
            logger.error('Search error: %s', rsp['error']['message'])
            return []
        features = rsp['features']
        if not features:
            logger.error('No results found')
            return []
        return features

    def search(self, search_string, bounds=None):
        # see https://learn.microsoft.com/en-us/rest/api/maps/search/get-geocoding
        params = {
            'api-version': '2023-06-01',
            'query': search_string,
            'top': '20',
            }
        if bounds:
            north, east, south, west = bounds
            params['bbox'] = '{:.4f},{:.4f},{:.4f},{:.4f}'.format(
                west, south, east, north)
        # 'view' must be a two letter country code
        territory = self.app.locale.territory_code()
        if len(territory) == 2:
            params['view'] = territory.upper()
        for feature in self.cached_query(
                params, 'https://atlas.microsoft.com/geocode'):
            properties = feature['properties']
            if properties['confidence'] == 'Low':
                continue
            address = properties['address']
            name = address['formattedAddress']
            if 'countryRegion' in address:
                country = address['countryRegion']['name']
                if country not in name:
                    name = '{}, {}'.format(name, country)
            if 'type' in properties:
                if properties['type'] in (
                        'AdminDivision1', 'AdminDivision2'):
                    continue
                if properties['type'] not in (
                        'Address', 'CountryRegion', 'PointOfInterest',
                        'PopulatedPlace'):
                    name = '{} ({})'.format(name, properties['type'])
            if 'bbox' in feature:
                west, south, east, north = feature['bbox']
            else:
                east, north = feature['geometry']['coordinates'][:2]
                west, south = east, north
            yield north, east, south, west, name

    def search_terms(self):
        widget = Label(
            translate(
                'MapTabAzure', 'Search provided by Microsoft Azure'),
            lines=2)
        widget.setAlignment(Qt.AlignmentFlag.AlignRight)
        scale_font(widget, 80)
        return [widget]


class TabWidget(PhotiniMap):
    @staticmethod
    def tab_name():
        return translate('MapTabAzure', 'Azure Map',
                         'Full name of tab shown as a tooltip')

    @staticmethod
    def tab_short_name():
        return translate('MapTabAzure', 'Map &A',
                         'Shortest possible name used as tab label')

    def get_geocoder(self):
        return AzureGeocoder(parent=self)

    def get_head(self):
        url_base = 'https://atlas.microsoft.com/sdk/javascript/mapcontrol/3/'
        url_js = url_base + 'atlas.min.js'
        url_css = url_base + 'atlas.min.css'
        return '''<link rel="stylesheet" href="{url_css}" type="text/css" />
    <script type="text/javascript" src="{url_js}"></script>
    <script type="text/javascript" src="azuremap.js"></script>'''.format(
        url_css=url_css, url_js=url_js)

    def get_body(self, text_dir):
        return '''  <body onload="initialize()" ondragstart="return false">
    <div id="mapDiv" dir="{text_dir}"></div>
  </body>'''.format(text_dir=text_dir)

    def get_options(self):
        options = {
            'authOptions': {
                'authType': 'subscriptionKey',
                'subscriptionKey': fetch_key('azuremap'),
                },
            'language': self.app.locale.bcp47Name(),
            }
        # 'view' must be a two letter country code
        territory = self.app.locale.territory_code()
        if len(territory) == 2:
            options['view'] = territory
        return options
