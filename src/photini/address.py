##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2019-26  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from photini.metadata import ImageMetadata
from photini.photinimap import fetch_key, GeocoderBase
from photini.pyqt import *
from photini.types import MD_Location
from photini.widgets import (
    AltitudeDisplay, CompactButton, ContextMenuMixin, Label, LatLongDisplay,
    LangAltWidget, SingleLineEdit, WidgetMixin)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class OpenCage(GeocoderBase):
    api_key = fetch_key('opencage')

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
            'language': self.app.locale.bcp47Name(),
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


class LocationInfo(QtWidgets.QScrollArea, ContextMenuMixin, WidgetMixin):
    clipboard_key = 'LocationInfo'
    multi_page = True

    def __init__(self, idx, menu_title, *args, **kw):
        super(LocationInfo, self).__init__(*args, **kw)
        self._key = idx
        self.menu_title = menu_title
        self.app = QtWidgets.QApplication.instance()
        self.setFrameStyle(QtWidgets.QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        form = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout()
        form.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        self.widgets = {}
        self.widgets['LocationName'] = LangAltWidget(
            'Iptc4xmpExt:LocationName', multi_line=False)
        self.widgets['LocationName'].setToolTip('<p>{}</p>'.format(
            translate('AddressTab', 'Enter a full name of the location.')))
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
            self.widgets[key] = SingleLineEdit(
                'Iptc4xmpExt:' + key, length_check=ImageMetadata.iptc_max_len(
                    'Iptc.Application2.' + key))
            self.widgets[key].setToolTip('<p>{}</p>'.format(tool_tip))
        self.widgets['latlon'] = LatLongDisplay()
        self.widgets['alt'] = AltitudeDisplay()
        self.widgets['CountryCode'].setMaximumWidth(
            width_for_text(self.widgets['CountryCode'], 'W' * 4))
        for j, text in enumerate((translate('AddressTab', 'Name'),
                                  translate('AddressTab', 'Street'),
                                  translate('AddressTab', 'City'),
                                  translate('AddressTab', 'Province'),
                                  translate('AddressTab', 'Country'),
                                  translate('AddressTab', 'Region'),
                                  translate('AddressTab', 'Location ID'))):
            label = Label(text)
            layout.addWidget(label, j, 0)
        layout.addWidget(self.widgets['LocationName'], 0, 1, 1, 5)
        layout.addWidget(self.widgets['Sublocation'], 1, 1, 1, 5)
        layout.addWidget(self.widgets['City'], 2, 1, 1, 5)
        layout.addWidget(self.widgets['ProvinceState'], 3, 1, 1, 5)
        layout.addWidget(self.widgets['CountryName'], 4, 1, 1, 4)
        layout.addWidget(self.widgets['CountryCode'], 4, 5)
        layout.addWidget(self.widgets['WorldRegion'], 5, 1, 1, 5)
        layout.addWidget(self.widgets['LocationId'], 6, 1, 1, 5)
        layout.addWidget(self.widgets['latlon'].label, 7, 0)
        layout.addWidget(self.widgets['latlon'], 7, 1)
        layout.addWidget(self.widgets['alt'].label, 7, 2)
        self.widgets['alt'].setFixedWidth(self.widgets['latlon'].width())
        layout.addWidget(self.widgets['alt'], 7, 3)
        layout.setColumnStretch(4, 1)
        layout.setRowStretch(8, 1)
        self.setWidget(form)
        for widget in self.widgets.values():
            widget.new_value.connect(self.update_value)

    @catch_all
    def contextMenuEvent(self, event):
        self.compound_context_menu(event, title=self.menu_title)

    def get_value(self):
        result = {}
        for widget in self.widgets.values():
            result.update(widget.get_value_dict())
        return result

    def is_multiple(self):
        return any(w.is_multiple() for w in self.widgets.values())

    def set_value(self, value):
        value = value or {}
        for widget in self.widgets.values():
            widget.set_value_dict(value)

    @QtSlot(dict)
    @catch_all
    def update_value(self, value):
        self.new_value.emit({self._key: value})


class AddressTabs(QtWidgets.QTabWidget, WidgetMixin):
    _key = 'iptcExt:Location'

    def __init__(self, *args, **kw):
        super(AddressTabs, self).__init__(*args, **kw)
        self.app = QtWidgets.QApplication.instance()
        self.setElideMode(Qt.TextElideMode.ElideLeft)
        self.setEnabled(False)

    def get_value(self):
        result = {}
        for idx in range(self.count()):
            result.update(self.widget(idx).get_value_dict())
        return result

    def is_multiple(self):
        for idx in range(self.count() - 1):
            if self.widget(idx).is_multiple():
                return True
        return False

    def set_value(self, value):
        value = value or {}
        self.set_tab_count(len(value))
        for idx in range(self.count()):
            self.widget(idx).set_value_dict(value)

    def paste_address(self, address):
        self.currentWidget().paste_value(address)

    def set_tab_count(self, data_len):
        # minimum is camera location plus one empty data location
        data_len += 1
        data_len = max(data_len, 2)
        if self.currentIndex() >= data_len:
            self.setCurrentIndex(data_len - 1)
        idx = self.count()
        while idx < data_len:
            if idx == 0:
                text = translate('AddressTab', 'camera')
                tip = translate('AddressTab', 'Enter the details about a'
                                ' location where this image was created.')
            else:
                text = translate('AddressTab', 'subject {idx}').format(idx=idx)
                tip = translate('AddressTab', 'Enter the details about a'
                                ' location which is shown in this image.')
            menu_title = translate(
                'AddressTab', 'All "{tab}" address data').format(tab=text)
            widget = LocationInfo(idx, menu_title)
            widget.new_value.connect(self.update_value)
            self.addTab(widget, text)
            self.setTabToolTip(idx, '<p>' + tip + '</p>')
            idx += 1
        while idx > data_len:
            idx -= 1
            self.removeTab(idx)

    @QtSlot(dict)
    @catch_all
    def update_value(self, value):
        self.new_value.emit({self._key: value})


class TabWidget(QtWidgets.QWidget, ContextMenuMixin):
    clipboard_key = 'AddressTab'
    multi_page = True

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
        self.coords_widget = LatLongDisplay()
        self.coords_widget.setReadOnly(True)
        left_side.addWidget(self.coords_widget.label, 0, 0)
        left_side.addWidget(self.coords_widget, 0, 1)
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
        self.locations_widget = AddressTabs()
        self.locations_widget.new_value.connect(self.update_value)
        self.layout().addWidget(self.locations_widget, stretch=1)
        # as there is only one data widget, adopt its methods for cut/paste
        self.emit_value = self.locations_widget.emit_value
        self.get_value = self.locations_widget.get_value
        self.is_multiple = self.locations_widget.is_multiple
        self.set_value = self.locations_widget.set_value

    @catch_all
    def contextMenuEvent(self, event):
        self.compound_context_menu(event)

    def refresh(self):
        self.new_selection(self.app.image_list.get_selected_images())

    def do_not_close(self):
        return False

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

    @QtSlot(dict)
    @catch_all
    def update_value(self, value):
        images = self.app.image_list.get_selected_images()
        (idx, value), = value.items()
        if len(value) != 1:
            # pasting a set of addresses, so clear old ones first
            for image in images:
                image.metadata.location_taken = None
                image.metadata.location_shown = None
        for image in images:
            for idx in value:
                location = dict(self._get_location(image, idx))
                location.update(value[idx])
                self._set_location(image, idx, location)
        self.display_location(images)

    def display_location(self, images):
        # get required number of tabs
        data_len = 0
        for image in images:
            if image.metadata.location_shown:
                data_len = max(data_len, len(image.metadata.location_shown))
        data_len += 1
        self.locations_widget.set_tab_count(data_len)
        # display data
        for idx in range(self.locations_widget.count()):
            widget = self.locations_widget.widget(idx)
            values = [self._get_location(image, idx) for image in images]
            for key in widget.widgets:
                widget.widgets[key].set_value_list(values)

    def new_selection(self, selection):
        self.locations_widget.setEnabled(bool(selection))
        values = []
        for image in selection:
            values.append(image.metadata.gps_info)
        self.coords_widget.set_value_list(values)
        self.auto_location.setEnabled(bool(self.coords_widget.get_value()))
        self.display_location(selection)

    @QtSlot()
    @catch_all
    def get_address(self):
        location = self.geocoder.get_address(self.coords_widget.get_value())
        if location:
            self.locations_widget.paste_address(location)
