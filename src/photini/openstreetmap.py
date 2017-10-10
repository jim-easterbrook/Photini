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
from photini.pyqt import Busy, Qt, QtCore, QtWidgets, qt_version_info

class OpenStreetMap(PhotiniMap):
    def __init__(self, *arg, **kw):
        super(OpenStreetMap, self).__init__(*arg, **kw)
        self.block_timer = QtCore.QTimer(self)
        self.block_timer.setInterval(5000)
        self.block_timer.setSingleShot(True)
        self.block_timer.timeout.connect(self.enable_search)
        self.api_key = key_store.get('opencagedata', 'api_key')

    def get_page_elements(self):
        return {
            'head': '''
    <link rel="stylesheet"
      href="https://unpkg.com/leaflet@1.0.3/dist/leaflet.css" />
    <script type="text/javascript">
      var L_NO_TOUCH = true;
    </script>
    <script type="text/javascript"
      src="https://unpkg.com/leaflet@1.0.3/dist/leaflet.js">
    </script>
''',
            'body': '''
    <script type="text/javascript">
      initialize();
    </script>
''',
            }

    def show_terms(self):
        # return widget to display map terms and conditions
        layout = QtWidgets.QGridLayout()
        widget = QtWidgets.QPushButton(self.tr('Search powered by OpenCage'))
        widget.clicked.connect(self.load_tou_opencage)
        widget.setStyleSheet('QPushButton { font-size: 10px }')
        layout.addWidget(widget, 0, 0)
        widget = QtWidgets.QPushButton(self.tr('Map powered by Leaflet'))
        widget.clicked.connect(self.load_tou_leaflet)
        widget.setStyleSheet('QPushButton { font-size: 10px }')
        layout.addWidget(widget, 0, 1)
        widget = QtWidgets.QPushButton(
            self.tr('Map data ©OpenStreetMap\ncontributors, licensed under ODbL'))
        widget.clicked.connect(self.load_tou_osm)
        widget.setStyleSheet('QPushButton { font-size: 10px }')
        layout.addWidget(widget, 1, 0)
        widget = QtWidgets.QPushButton(
            self.tr('Map tiles by CARTO\nlicensed under CC BY 3.0'))
        widget.clicked.connect(self.load_tou_tiles)
        widget.setStyleSheet('QPushButton { font-size: 10px }')
        layout.addWidget(widget, 1, 1)
        return layout

    @QtCore.pyqtSlot()
    def load_tou_opencage(self):
        webbrowser.open_new('https://geocoder.opencagedata.com/')

    @QtCore.pyqtSlot()
    def load_tou_leaflet(self):
        webbrowser.open_new('http://leafletjs.com/')

    @QtCore.pyqtSlot()
    def load_tou_osm(self):
        webbrowser.open_new('http://www.openstreetmap.org/copyright')

    @QtCore.pyqtSlot()
    def load_tou_tiles(self):
        webbrowser.open_new('https://carto.com/attribution')

    @QtCore.pyqtSlot()
    def enable_search(self):
        self.edit_box.lineEdit().setEnabled(self.map_loaded)
        if self.search_string:
            item = self.edit_box.model().item(1)
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        self.display_coords()

    def disable_search(self):
        self.edit_box.lineEdit().setEnabled(False)
        if self.search_string:
            item = self.edit_box.model().item(1)
            item.setFlags(~(Qt.ItemIsSelectable | Qt.ItemIsEnabled))
        self.auto_location.setEnabled(False)
        self.block_timer.start()

    def do_search(self, query, params={}):
        self.disable_search()
        params['key'] = self.api_key
        params['q'] = query
        params['abbrv'] = '1'
        params['no_annotations'] = '1'
        lang, encoding = locale.getdefaultlocale()
        if lang:
            params['language'] = lang
        with Busy():
            try:
                rsp = requests.get(
                    'https://api.opencagedata.com/geocode/v1/json',
                    params=params)
            except Exception as ex:
                self.logger.error(str(ex))
                return None
        if rsp.status_code >= 400:
            self.logger.error('Search error %d', rsp.status_code)
            return None
        rsp = rsp.json()
        status = rsp['status']
        if status['code'] != 200:
            self.logger.error(
                'Search error %d: %s', status['code'], status['message'])
            return None
        rate = rsp['rate']
        self.block_timer.setInterval(
            5000 * rate['limit'] // max(rate['remaining'], 1))
        return rsp

    @QtCore.pyqtSlot()
    def get_address(self):
        lat, lon = self.coords.get_value().split(',')
        rsp = self.do_search(lat.strip() + ' ' + lon.strip())
        if not rsp:
            return
        if rsp['total_results'] < 1:
            self.logger.error('Address not found')
            return
        address = rsp['results'][0]['components']
        location = []
        for iptc_key, osm_keys in (
                ('world_region',   ('continent',)),
                ('country_code',   ('country_code', 'ISO_3166-1_alpha-2')),
                ('country_name',   ('country',)),
                ('province_state', ('region', 'county',
                                    'state_district', 'state')),
                ('city',           ('hamlet', 'locality', 'neighbourhood',
                                    'village', 'suburb',
                                    'town', 'city_district', 'city')),
                ('sublocation',    ('building', 'house_number',
                                    'footway', 'pedestrian', 'road'))):
            element = []
            for key in osm_keys:
                if key not in address:
                    continue
                if iptc_key == 'country_code':
                    element = [address[key]]
                elif address[key] not in element:
                    element.append(address[key])
                del(address[key])
            location.append(', '.join(element))
        # put remaining keys in sublocation
        for key in address:
            if key in ('postcode', 'road_reference', 'road_reference_intl',
                       'state_code', '_type'):
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
        scale = 2 ** (self.map_status['zoom'] - 9)
        if scale >= 1:
            w = (east - west) * scale
            h = (north - south) * scale
            lat, lon = self.map_status['centre']
            north = min(lat + h,  90.0)
            south = max(lat - h, -90.0)
            east = lon + w
            west = lon - w
        bounds = (west, south, east, north)
        rsp = self.do_search(
            search_string, {'bounds': ','.join(map(str, bounds))})
        if not rsp:
            return
        if not rsp['results']:
            # repeat search without bounds
            rsp = self.do_search(search_string)
            if not rsp:
                return
        for result in rsp['results']:
            self.search_result(
                result['bounds']['northeast']['lat'],
                result['bounds']['northeast']['lng'],
                result['bounds']['southwest']['lat'],
                result['bounds']['southwest']['lng'],
                result['formatted'])

    @QtCore.pyqtSlot(int)
    def marker_drag_start(self, marker_id):
        blocked = self.image_list.blockSignals(True)
        self.image_list.select_images(self.marker_images[marker_id])
        self.image_list.blockSignals(blocked)
        self.coords.setEnabled(True)
        for other_id, images in self.marker_images.items():
            if other_id != marker_id:
                self.JavaScript('enableMarker({:d},{:d})'.format(
                    other_id, False))
        self.display_coords()
