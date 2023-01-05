##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2019-23  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from collections import defaultdict
import locale
import logging
import os

import requests

from photini.configstore import key_store
from photini.metadata import ImageMetadata
from photini.photinimap import GeocoderBase
from photini.pyqt import *
from photini.types import MD_Location
from photini.widgets import CompactButton, LatLongDisplay, SingleLineEdit

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class OpenCage(GeocoderBase):
    api_key = key_store.get('opencage', 'api_key')

    def query(self, params):
        params['key'] = self.api_key
        params['abbrv'] = '1'
        params['no_annotations'] = '1'
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

    # Map OpenCage address components to IPTC address heirarchy. There
    # are many possible components (user generated data) so any
    # unrecognised ones are put in 'SubLocation'. See
    # https://github.com/OpenCageData/address-formatting/blob/master/conf/components.yaml
    address_map = {
        'WorldRegion'   :('continent',),
        'CountryCode'   :('ISO_3166-1_alpha-3', 'ISO_3166-1_alpha-2',
                          'country_code'),
        'CountryName'   :('country', 'country_name'),
        'ProvinceState' :('county', 'county_code', 'local_administrative_area',
                          'state_district', 'state', 'state_code', 'province',
                          'region', 'island'),
        'City'          :('neighbourhood', 'city_block', 'quarter', 'suburb',
                          'district', 'borough', 'city_district', 'commercial',
                          'industrial', 'houses', 'subdivision',
                          'village', 'town', 'municipality', 'city',
                          'partial_postcode', 'postcode'),
        'SubLocation'   :('house_number', 'street_number',
                          'house', 'public_building', 'building', 'residential',
                          'water', 'road', 'pedestrian', 'path',
                          'street_name', 'street', 'cycleway', 'footway',
                          'place', 'square',
                          'locality', 'hamlet', 'croft'),
        'ignore'        :('ISO_3166-2', 'political_union', 'road_reference',
                          'road_reference_intl', 'road_type',
                          '_category', '_type'),
        }

    def get_address(self, coords):
        coords = [float(x) for x in coords.split(',')]
        params = {'q': '{:.5f},{:.5f}'.format(*coords)}
        lang, encoding = locale.getdefaultlocale()
        if lang:
            params['language'] = lang
        results = self.cached_query(params)
        if not results:
            return None
        address = dict(results[0]['components'])
        formatted = results[0]['formatted']
        for key in address.keys():
            if isinstance(address[key], list):
                try:
                    address[key] = '; '.join(address[key])
                except Exception:
                    pass
            if not isinstance(address[key], str):
                try:
                    address[key] = str(address[key])
                except Exception:
                    del address[key]
        # remove some known equivalent data
        for key_1, key_2 in (('county_code', 'county'),
                             ('state_code', 'state'),
                             ('partial_postcode', 'postcode')):
            if key_1 in address and key_2 in address:
                del address[key_1]
        # remove duplicate data
        for key_list in self.address_map.values():
            for n, key_1 in enumerate(key_list):
                if key_1 not in address:
                    continue
                for key_2 in key_list[n+1:]:
                    if key_2 not in address:
                        continue
                    if address[key_1] == address[key_2]:
                        del address[key_1]
                        break
        # attempt to format postcode correctly
        for key in 'city', 'state', 'country':
            if 'postcode' in address and key in address:
                for fmt in '{0} {1}', '{0}, {1}', '{1} {0}', '{1}, {0}':
                    guess = fmt.format(address['postcode'], address[key])
                    if guess in formatted:
                        address[key] = guess
                        del address['postcode']
                        break
        return MD_Location.from_address(address, self.address_map)

    def search_terms(self):
        text = translate('AddressTab', 'Address lookup powered by OpenCage')
        tou_opencage = CompactButton(text)
        tou_opencage.clicked.connect(self.load_tou_opencage)
        tou_osm = CompactButton(
            translate('AddressTab', 'Geodata © OpenStreetMap contributors'))
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


class LocationInfo(QtWidgets.QWidget):
    new_value = QtSignal(object, dict)

    def __init__(self, *args, **kw):
        super(LocationInfo, self).__init__(*args, **kw)
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        self.members = {}
        for key in ('SubLocation', 'City', 'ProvinceState',
                    'CountryName', 'CountryCode', 'WorldRegion'):
            self.members[key] = SingleLineEdit(
                key, length_check=ImageMetadata.max_bytes(key))
            self.members[key].new_value.connect(self.editing_finished)
        self.members['CountryCode'].setMaximumWidth(
            width_for_text(self.members['CountryCode'], 'W' * 4))
        self.members['SubLocation'].setToolTip('<p>{}</p>'.format(translate(
            'AddressTab', 'Enter the name of the sublocation.')))
        self.members['City'].setToolTip('<p>{}</p>'.format(translate(
            'AddressTab', 'Enter the name of the city.')))
        self.members['ProvinceState'].setToolTip('<p>{}</p>'.format(translate(
            'AddressTab', 'Enter the name of the province or state.')))
        self.members['CountryName'].setToolTip('<p>{}</p>'.format(translate(
            'AddressTab', 'Enter the name of the country.')))
        self.members['CountryCode'].setToolTip('<p>{}</p>'.format(translate(
            'AddressTab',
            'Enter the 2 or 3 letter ISO 3166 country code of the country.')))
        self.members['WorldRegion'].setToolTip('<p>{}</p>'.format(translate(
            'AddressTab', 'Enter the name of the world region.')))
        for j, text in enumerate((translate('AddressTab', 'Street'),
                                  translate('AddressTab', 'City'),
                                  translate('AddressTab', 'Province'),
                                  translate('AddressTab', 'Country'),
                                  translate('AddressTab', 'Region'))):
            label = QtWidgets.QLabel(text)
            label.setAlignment(Qt.AlignmentFlag.AlignRight)
            layout.addWidget(label, j, 0)
        layout.addWidget(self.members['SubLocation'], 0, 1, 1, 2)
        layout.addWidget(self.members['City'], 1, 1, 1, 2)
        layout.addWidget(self.members['ProvinceState'], 2, 1, 1, 2)
        layout.addWidget(self.members['CountryName'], 3, 1)
        layout.addWidget(self.members['CountryCode'], 3, 2)
        layout.addWidget(self.members['WorldRegion'], 4, 1, 1, 2)
        layout.setRowStretch(5, 1)

    def get_value(self):
        new_value = {}
        for key in self.members:
            if self.members[key].is_multiple():
                continue
            new_value[key] = self.members[key].get_value().strip() or None
        return new_value

    @QtSlot(str, object)
    @catch_all
    def editing_finished(self, key, value):
        self.members[key].set_value(value)
        self.new_value.emit(self, self.get_value())


class QTabBar(QtWidgets.QTabBar):
    context_menu = QtSignal(QtGui.QContextMenuEvent)

    @catch_all
    def contextMenuEvent(self, event):
        self.context_menu.emit(event)


class TabWidget(QtWidgets.QWidget):
    @staticmethod
    def tab_name():
        return translate('AddressTab', '&Address')

    def __init__(self, parent=None):
        super(TabWidget, self).__init__(parent)
        self.app = QtWidgets.QApplication.instance()
        self.geocoder = OpenCage(parent=self)
        self.setLayout(QtWidgets.QHBoxLayout())
        ## left side
        left_side = QtWidgets.QGridLayout()
        # latitude & longitude
        self.coords = LatLongDisplay()
        left_side.addWidget(self.coords.label, 0, 0)
        self.coords.changed.connect(self.new_coords)
        left_side.addWidget(self.coords, 0, 1)
        # convert lat/lng to location info
        self.auto_location = QtWidgets.QPushButton(
            translate('AddressTab', 'Get address from lat, long'))
        self.auto_location.setEnabled(False)
        self.auto_location.clicked.connect(self.get_address)
        left_side.addWidget(self.auto_location, 1, 0, 1, 2)
        # terms and conditions
        terms = self.geocoder.search_terms()
        left_side.addWidget(terms[0], 3, 0, 1, 2)
        left_side.addWidget(terms[1], 4, 0, 1, 2)
        left_side.setColumnStretch(1, 1)
        left_side.setRowStretch(2, 1)
        self.layout().addLayout(left_side)
        ## right side
        # location info
        self.location_widgets = []
        self.location_info = QtWidgets.QTabWidget()
        tab_bar = QTabBar()
        self.location_info.setTabBar(tab_bar)
        tab_bar.context_menu.connect(self.location_tab_context_menu)
        tab_bar.tabMoved.connect(self.location_tab_moved)
        self.location_info.setElideMode(Qt.TextElideMode.ElideLeft)
        self.location_info.setMovable(True)
        self.location_info.setEnabled(False)
        self.layout().addWidget(self.location_info, stretch=1)

    def refresh(self):
        self.new_selection(self.app.image_list.get_selected_images())

    def do_not_close(self):
        return False

    @QtSlot()
    @catch_all
    def new_coords(self):
        self.auto_location.setEnabled(bool(self.coords.get_value()))

    @QtSlot(QtGui.QContextMenuEvent)
    @catch_all
    def location_tab_context_menu(self, event):
        idx = self.location_info.tabBar().tabAt(event.pos())
        self.location_info.setCurrentIndex(idx)
        menu = QtWidgets.QMenu(self)
        menu.addAction(translate(
            'AddressTab', 'Duplicate location'), self.duplicate_location)
        menu.addAction(translate(
            'AddressTab', 'Delete location'), self.delete_location)
        action = execute(menu, event.globalPos())

    @QtSlot()
    @catch_all
    def duplicate_location(self):
        idx = self.location_info.currentIndex()
        for image in self.app.image_list.get_selected_images():
            # duplicate data
            location = MD_Location(self._get_location(image, idx) or {})
            # shuffle data up
            location_list = list(image.metadata.location_shown or [])
            location_list.insert(idx, location)
            image.metadata.location_shown = location_list
        # display data
        self.display_location()

    @QtSlot()
    @catch_all
    def delete_location(self):
        idx = self.location_info.currentIndex()
        for image in self.app.image_list.get_selected_images():
            # shuffle data down
            location_list = list(image.metadata.location_shown or [])
            if idx == 0:
                if location_list:
                    location = location_list.pop(0)
                else:
                    location = None
                image.metadata.location_taken = location
            elif idx <= len(location_list):
                del location_list[max(idx - 1, 0)]
            image.metadata.location_shown = location_list
        # display data
        self.display_location()

    @QtSlot(int, int)
    @catch_all
    def location_tab_moved(self, idx_a, idx_b):
        self.pending_move = idx_a, idx_b
        # do actual swap when idle to avoid seg fault
        QtCore.QTimer.singleShot(0, self._location_tab_moved)

    @QtSlot()
    @catch_all
    def _location_tab_moved(self):
        idx_a, idx_b = self.pending_move
        # swap data
        for image in self.app.image_list.get_selected_images():
            temp_a = self._get_location(image, idx_a)
            temp_b = self._get_location(image, idx_b)
            self._set_location(image, idx_a, temp_b)
            self._set_location(image, idx_b, temp_a)
        # adjust tab names
        for idx in range(min(idx_a, idx_b), max(idx_a, idx_b) + 1):
            self.set_tab_text(idx)
        # display data
        self.display_location()

    def _get_location(self, image, idx):
        if idx == 0:
            return image.metadata.location_taken
        elif not image.metadata.location_shown:
            return None
        elif idx <= len(image.metadata.location_shown):
            return image.metadata.location_shown[idx - 1]
        return None

    def _set_location(self, image, idx, location):
        if idx == 0:
            image.metadata.location_taken = location
        else:
            location_list = list(image.metadata.location_shown or [])
            while len(location_list) < idx:
                location_list.append(None)
            location_list[idx - 1] = location
            image.metadata.location_shown = location_list

    @QtSlot(object, dict)
    @catch_all
    def new_location(self, widget, new_value, images=[]):
        images = images or self.app.image_list.get_selected_images()
        idx = self.location_info.indexOf(widget)
        for image in images:
            temp = dict(self._get_location(image, idx) or {})
            temp.update(new_value)
            self._set_location(image, idx, temp)
        # new_location can be called when changing tab, so don't delete
        # tabs until later
        QtCore.QTimer.singleShot(0, self.display_location)

    def set_tab_text(self, idx):
        if idx == 0:
            text = translate('AddressTab', 'camera')
            tip = translate('AddressTab', 'Enter the details about a location'
                            ' where this image was created.')
        else:
            text = translate('AddressTab', 'subject {idx}').format(idx=idx)
            tip = translate('AddressTab', 'Enter the details about a location'
                            ' which is shown in this image.')
        self.location_info.setTabText(idx, text)
        self.location_info.setTabToolTip(idx, '<p>' + tip + '</p>')

    @QtSlot()
    @catch_all
    def display_location(self):
        images = self.app.image_list.get_selected_images()
        # get required number of tabs
        count = 0
        for image in images:
            if image.metadata.location_shown:
                count = max(count, len(image.metadata.location_shown))
        count += 2
        # add or remove tabs
        if self.location_info.currentIndex() >= count:
            self.location_info.setCurrentIndex(count - 1)
        idx = self.location_info.count()
        while idx < count:
            if not self.location_widgets:
                widget = LocationInfo()
                widget.new_value.connect(self.new_location)
                self.location_widgets.append(widget)
            self.location_info.addTab(self.location_widgets.pop(), '')
            self.set_tab_text(idx)
            idx += 1
        while idx > count:
            idx -= 1
            self.location_widgets.append(self.location_info.widget(idx))
            self.location_info.removeTab(idx)
        # display data
        for idx in range(count):
            widget = self.location_info.widget(idx)
            if images:
                values = defaultdict(list)
                for image in images:
                    location = self._get_location(image, idx) or {}
                    for key in widget.members:
                        value = None
                        if key in location:
                            value = location[key]
                        if value not in values[key]:
                            values[key].append(value)
                for key in widget.members:
                    if len(values[key]) > 1:
                        widget.members[key].set_multiple(
                            choices=filter(None, values[key]))
                    else:
                        widget.members[key].set_value(values[key][0])
            else:
                for key in widget.members:
                    widget.members[key].set_value(None)

    def new_selection(self, selection):
        self.location_info.setEnabled(bool(selection))
        self.coords.update_display(selection)
        self.auto_location.setEnabled(bool(self.coords.get_value()))
        self.display_location()

    @QtSlot()
    @catch_all
    def get_address(self):
        images = self.app.image_list.get_selected_images()
        location = self.geocoder.get_address(self.coords.get_value())
        if location:
            self.new_location(
                self.location_info.currentWidget(), location, images)
