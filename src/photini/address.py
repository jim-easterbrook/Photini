##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2019-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import logging
import os

import requests

from photini.configstore import key_store
from photini.metadata import ImageMetadata
from photini.photinimap import GeocoderBase
from photini.pyqt import *
from photini.types import MD_Location
from photini.widgets import (AltitudeDisplay, CompactButton, Label,
                             LatLongDisplay, LangAltWidget, SingleLineEdit)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class OpenCage(GeocoderBase):
    api_key = key_store.get('opencage', 'api_key')

    def query(self, params):
        params['key'] = self.api_key
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

    # Map OpenCage address components to IPTC address hierarchy. There
    # are many possible components (user generated data) so any
    # unrecognised ones are put in 'Iptc4xmpExt:Sublocation'. See
    # https://github.com/OpenCageData/address-formatting/blob/master/conf/components.yaml
    address_map = {
        'Iptc4xmpExt:WorldRegion': ('continent',),
        'Iptc4xmpExt:CountryCode': (
            'ISO_3166-1_alpha-3', 'ISO_3166-1_alpha-2', 'country_code'),
        'Iptc4xmpExt:CountryName': ('country', 'country_name'),
        'Iptc4xmpExt:ProvinceState': (
            'county', 'county_code', 'local_administrative_area',
            'state_district', 'state', 'state_code', 'province',
            'region', 'island'),
        'Iptc4xmpExt:City': (
            'neighbourhood', 'city_block', 'quarter', 'suburb', 'district',
            'borough', 'city_district', 'commercial', 'industrial', 'houses',
            'subdivision', 'village', 'town', 'municipality', 'city',
            'postal_city', 'partial_postcode', 'postcode'),
        'Iptc4xmpExt:Sublocation': (
            'house_number', 'street_number', 'house', 'public_building',
            'building', 'residential', 'water', 'road', 'pedestrian', 'path',
            'street_name', 'street', 'cycleway', 'footway', 'place', 'square',
            'locality', 'hamlet', 'croft'),
        'ignore': (
            'ISO_3166-2', 'local_authority', 'political_union',
            'road_reference', 'road_reference_intl', 'road_type'),
        }

    def get_address(self, coords):
        params = {
            'q': '{:.5f},{:.5f}'.format(*coords),
            'language': self.app.language['bcp47'],
            }
        results = self.cached_query(params)
        if not results:
            return None
        address = dict(results[0]['components'])
        formatted = results[0]['formatted']
        for key in list(address.keys()):
            if key.startswith('_'):
                del address[key]
                continue
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
        for key in self.address_map['Iptc4xmpExt:City'][-3::-1]:
            if 'postcode' in address and key in address:
                for fmt in '{0} {1}', '{0}, {1}', '{1} {0}', '{1}, {0}':
                    guess = fmt.format(address['postcode'], address[key])
                    if guess in formatted:
                        address[key] = guess
                        del address['postcode']
                        break
        gps = results[0]['geometry']
        return MD_Location.from_address(gps, address, self.address_map)

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


class LocationInfo(QtWidgets.QScrollArea):
    new_value = QtSignal(object, dict)

    def __init__(self, *args, **kw):
        super(LocationInfo, self).__init__(*args, **kw)
        self.setFrameStyle(QtWidgets.QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        form = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout()
        form.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        self.members = {}
        self.members['LocationName'] = LangAltWidget(
            'Iptc4xmpExt:LocationName', multi_line=False)
        self.members['LocationName'].setToolTip('<p>{}</p>'.format(
            translate('AddressTab', 'Enter a full name of the location.')))
        self.members['LocationName'].new_value.connect(self.editing_finished)
        for (key, tool_tip) in (
                ('Sublocation', translate(
                    'AddressTab', 'Enter the name of the sublocation.')),
                ('City', translate(
                    'AddressTab', 'Enter the name of the city.')),
                ('ProvinceState', translate(
                    'AddressTab', 'Enter the name of the province or state.')),
                ('CountryName', translate(
                    'AddressTab', 'Enter the name of the country.')),
                ('CountryCode', translate(
                    'AddressTab', 'Enter the 2 or 3 letter ISO 3166 country'
                    ' code of the country.')),
                ('WorldRegion', translate(
                    'AddressTab', 'Enter the name of the world region.')),
                ('LocationId', translate(
                    'AddressTab', 'Enter globally unique identifier(s) of the'
                    ' location. Separate them with ";" characters.'))):
            self.members[key] = SingleLineEdit(
                'Iptc4xmpExt:' + key, length_check=ImageMetadata.iptc_max_len(
                    'Iptc.Application2.' + key))
            self.members[key].setToolTip('<p>{}</p>'.format(tool_tip))
            self.members[key].new_value.connect(self.editing_finished)
        self.members['latlon'] = LatLongDisplay()
        self.members['latlon'].new_value.connect(self.editing_finished)
        self.members['alt'] = AltitudeDisplay()
        self.members['alt'].new_value.connect(self.editing_finished)
        self.members['CountryCode'].setMaximumWidth(
            width_for_text(self.members['CountryCode'], 'W' * 4))
        for j, text in enumerate((translate('AddressTab', 'Name'),
                                  translate('AddressTab', 'Street'),
                                  translate('AddressTab', 'City'),
                                  translate('AddressTab', 'Province'),
                                  translate('AddressTab', 'Country'),
                                  translate('AddressTab', 'Region'),
                                  translate('AddressTab', 'Location ID'))):
            label = Label(text)
            layout.addWidget(label, j, 0)
        layout.addWidget(self.members['LocationName'], 0, 1, 1, 5)
        layout.addWidget(self.members['Sublocation'], 1, 1, 1, 5)
        layout.addWidget(self.members['City'], 2, 1, 1, 5)
        layout.addWidget(self.members['ProvinceState'], 3, 1, 1, 5)
        layout.addWidget(self.members['CountryName'], 4, 1, 1, 4)
        layout.addWidget(self.members['CountryCode'], 4, 5)
        layout.addWidget(self.members['WorldRegion'], 5, 1, 1, 5)
        layout.addWidget(self.members['LocationId'], 6, 1, 1, 5)
        layout.addWidget(self.members['latlon'].label, 7, 0)
        layout.addWidget(self.members['latlon'], 7, 1)
        layout.addWidget(self.members['alt'].label, 7, 2)
        self.members['alt'].setFixedWidth(self.members['latlon'].width())
        layout.addWidget(self.members['alt'], 7, 3)
        layout.setColumnStretch(4, 1)
        layout.setRowStretch(8, 1)
        self.setWidget(form)

    def get_value(self):
        new_value = {}
        for key in self.members:
            new_value.update(self.members[key].get_value_dict())
        return new_value

    @QtSlot(dict)
    @catch_all
    def editing_finished(self, value):
        self.new_value.emit(self, value)


class QTabBar(QtWidgets.QTabBar):
    context_menu = QtSignal(QtGui.QContextMenuEvent)

    @catch_all
    def contextMenuEvent(self, event):
        self.context_menu.emit(event)


class TabWidget(QtWidgets.QWidget):
    @staticmethod
    def tab_name():
        return translate('AddressTab', 'Location addresses',
                         'Full name of tab shown as a tooltip')

    @staticmethod
    def tab_short_name():
        return translate('AddressTab', '&Address',
                         'Shortest possible name used as tab label')

    def __init__(self, parent=None):
        super(TabWidget, self).__init__(parent)
        self.app = QtWidgets.QApplication.instance()
        self.geocoder = OpenCage(parent=self)
        self.setLayout(QtWidgets.QHBoxLayout())
        ## left side
        left_side = QtWidgets.QGridLayout()
        # latitude & longitude
        self.coords = LatLongDisplay()
        self.coords.setReadOnly(True)
        left_side.addWidget(self.coords.label, 0, 0)
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
            location = self._get_location(image, idx)
            # shuffle data up
            location_list = list(image.metadata.location_shown)
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
            location_list = list(image.metadata.location_shown)
            if idx == 0:
                if location_list:
                    location = [location_list.pop(0)]
                else:
                    location = []
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
            if image.metadata.location_taken:
                return image.metadata.location_taken[0]
            return {}
        elif idx <= len(image.metadata.location_shown):
            return image.metadata.location_shown[idx - 1]
        return {}

    def _set_location(self, image, idx, location):
        if idx == 0:
            image.metadata.location_taken = [location]
        else:
            location_list = list(image.metadata.location_shown)
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
            temp = dict(self._get_location(image, idx))
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
            values = [self._get_location(image, idx) for image in images]
            for key in widget.members:
                widget.members[key].set_value_list(values)

    def new_selection(self, selection):
        self.location_info.setEnabled(bool(selection))
        values = []
        for image in selection:
            values.append(image.metadata.gps_info)
        self.coords.set_value_list(values)
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
