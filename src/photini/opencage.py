# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2019-20  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import requests

from photini.configstore import key_store
from photini.metadata import Location
from photini.photinimap import GeocoderBase
from photini.pyqt import Busy, catch_all, CompactButton, QtCore, QtGui, QtSlot

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class OpenCage(GeocoderBase):
    api_key = key_store.get('opencage', 'api_key')

    def query(self, params):
        params['key'] = self.api_key
        params['abbrv'] = '1'
        params['no_annotations'] = '1'
        lang, encoding = locale.getdefaultlocale()
        if lang:
            params['language'] = lang
        with Busy():
            self.rate_limit()
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

    def search(self, search_string, bounds=None):
        params = {
            'q'     : search_string,
            'limit' : '20',
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
            params['bounds'] = '{:.4f},{:.4f},{:.4f},{:.4f}'.format(
                west, south, east, north)
        for result in self.cached_query(params):
            yield (result['bounds']['northeast']['lat'],
                   result['bounds']['northeast']['lng'],
                   result['bounds']['southwest']['lat'],
                   result['bounds']['southwest']['lng'],
                   result['formatted'])

    # Map OpenCage address components to IPTC address heirarchy. There
    # are many possible components (user generated data) so any
    # unrecognised ones are put in 'sublocation'. See
    # https://github.com/OpenCageData/address-formatting/blob/master/conf/components.yaml
    address_map = {
        'world_region'  :('continent',),
        'country_code'  :('ISO_3166-1_alpha-3', 'ISO_3166-1_alpha-2',
                          'country_code'),
        'country_name'  :('country', 'country_name'),
        'province_state':('county', 'county_code', 'local_administrative_area',
                          'state_district', 'state', 'state_code', 'province',
                          'region', 'island'),
        'city'          :('neighbourhood', 'suburb', 'city_district',
                          'district', 'quarter', 'residential', 'commercial',
                          'industrial', 'houses', 'subdivision',
                          'city', 'town', 'municipality', 'postcode'),
        'sublocation'   :('house_number', 'street_number',
                          'house', 'public_building', 'building', 'water',
                          'road', 'pedestrian', 'path',
                          'street_name', 'street', 'cycleway', 'footway',
                          'place', 'square',
                          'village', 'locality', 'hamlet', 'croft'),
        'ignore'        :('political_union', 'road_reference',
                          'road_reference_intl', 'road_type',
                          '_category', '_type'),
        }

    def get_address(self, coords):
        results = self.cached_query({'q': coords.replace(' ', '')})
        if not results:
            return None
        address = dict(results[0]['components'])
        if 'county_code' in address and 'county' in address:
            del address['county_code']
        if 'state_code' in address and 'state' in address:
            del address['state_code']
        return Location.from_address(address, self.address_map)

    def search_terms(self, search=True):
        if search:
            text = self.tr('Search powered by OpenCage')
        else:
            text = self.tr('Address lookup powered by OpenCage')
        tou_opencage = CompactButton(text)
        tou_opencage.clicked.connect(self.load_tou_opencage)
        tou_osm = CompactButton(
            self.tr('Geodata © OpenStreetMap contributors'))
        tou_osm.clicked.connect(self.load_tou_osm)
        return [tou_opencage, tou_osm]

    @QtSlot()
    @catch_all
    def load_tou_opencage(self):
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl('https://geocoder.opencagedata.com/'))

    @QtSlot()
    @catch_all
    def load_tou_osm(self):
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl('http://www.openstreetmap.org/copyright'))
