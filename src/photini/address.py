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
    AltitudeDisplay, CompactButton, CompoundWidgetMixin, ContextMenuMixin,
    GPSInfoWidgets, Label, LatLongDisplay, LangAltWidget, ListWidgetMixin,
    SingleLineEdit, TopLevelWidgetMixin)

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


class LocationInfo(QtWidgets.QScrollArea, ContextMenuMixin, CompoundWidgetMixin):
    clipboard_key = 'LocationInfo'

    def __init__(self, key, menu_title, *args, **kw):
        super(LocationInfo, self).__init__(*args, **kw)
        self._key = key
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
        for widget in self.sub_widgets():
            widget.new_value.connect(self.sw_new_value)

    @catch_all
    def contextMenuEvent(self, event):
        self.compound_context_menu(event, title=self.menu_title)

    def sub_widgets(self):
        return self.widgets.values()


class LocationList(QtCore.QObject, ListWidgetMixin):
    def __init__(self, tab_widget, is_camera, *arg, **kw):
        super(LocationList, self).__init__(*arg, **kw)
        self.tab_widget = tab_widget
        self.is_camera = is_camera
        self._key = ('location_shown', 'location_taken')[is_camera]

    def adjust_widget(self, value_list=None):
        if not self.is_camera:
            if value_list is None:
                count = self.tab_widget.count()
                while count > 1:
                    if self.tab_widget.widget(count - 1).has_value():
                        break
                    count -= 1
            else:
                count = 0
                for value in value_list:
                    idx = len(value)
                    while idx > count:
                        idx -= 1
                        if any(bool(x) for x in value[idx].values()):
                            count = max(count, 1 + idx)
                            break
                count += 1
            self.tab_widget.set_tab_count(count)

    def setEnabled(self, enabled):
        for widget in self.sub_widgets():
            widget.setEnabled(enabled)

    def sub_widgets(self):
        if self.is_camera:
            yield self.tab_widget.widget(0)
        else:
            for idx in range(1, self.tab_widget.count()):
                yield self.tab_widget.widget(idx)


class AddressTabs(QtWidgets.QTabWidget, ContextMenuMixin, CompoundWidgetMixin):
    clipboard_key = 'AddressTab'

    def __init__(self, *args, **kw):
        super(AddressTabs, self).__init__(*args, **kw)
        self.app = QtWidgets.QApplication.instance()
        self.setElideMode(Qt.TextElideMode.ElideLeft)
        # "virtual" widgets to handle camera and subject location lists
        self.camera_locations = LocationList(self, True)
        self.subject_locations = LocationList(self, False)
        # "camera" location is always present
        text = translate('AddressTab', 'camera')
        tip = translate('AddressTab', 'Enter the details about a'
                        ' location where this image was created.')
        menu_title = translate(
            'AddressTab', 'All "{tab}" address data').format(tab=text)
        widget = LocationInfo(0, menu_title)
        widget.new_value.connect(self.camera_locations.sw_new_value)
        self.addTab(widget, text)
        self.setTabToolTip(0, '<p>' + tip + '</p>')
        self.set_tab_count(0)

    def paste_address(self, address):
        self.currentWidget().paste_value(address)

    def emit_value(self):
        for widget in self.sub_widgets():
            widget.emit_value()

    def set_tab_count(self, data_len):
        # minimum is camera location plus one empty subject location
        data_len += 1
        data_len = max(data_len, 2)
        if self.currentIndex() >= data_len:
            self.setCurrentIndex(data_len - 1)
        idx = self.count()
        while idx < data_len:
            text = translate('AddressTab', 'subject {idx}').format(idx=idx)
            tip = translate('AddressTab', 'Enter the details about a'
                            ' location which is shown in this image.')
            menu_title = translate(
                'AddressTab', 'All "{tab}" address data').format(tab=text)
            widget = LocationInfo(idx - 1, menu_title)
            widget.new_value.connect(self.subject_locations.sw_new_value)
            self.addTab(widget, text)
            self.setTabToolTip(idx, '<p>' + tip + '</p>')
            idx += 1
        while idx > data_len:
            idx -= 1
            self.removeTab(idx)

    def sub_widgets(self):
        return (self.camera_locations, self.subject_locations)


class TabWidget(QtWidgets.QWidget, TopLevelWidgetMixin):
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
        self.coords_widget = GPSInfoWidgets()
        self.coords_widget.latlon.setReadOnly(True)
        left_side.addWidget(self.coords_widget.latlon_label, 0, 0)
        left_side.addWidget(self.coords_widget.latlon, 0, 1)
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
        for widget in self.locations_widget.sub_widgets():
            widget.new_value.connect(self.save_data)
        self.layout().addWidget(self.locations_widget, stretch=1)
        # delegate context menu to locations widget
        self.locations_widget.tab_short_name = self.tab_short_name

    @catch_all
    def contextMenuEvent(self, event):
        self.locations_widget.compound_context_menu(event)

    def refresh(self):
        self.new_selection(self.app.image_list.get_selected_images())

    def do_not_close(self):
        return False

    def sub_widgets(self):
        return (self.coords_widget,
                self.locations_widget.camera_locations,
                self.locations_widget.subject_locations)

    def new_selection(self, selection):
        self.load_data(selection)
        self.auto_location.setEnabled(self.coords_widget.latlon.has_value())

    @QtSlot()
    @catch_all
    def get_address(self):
        location = self.geocoder.get_address(
            self.coords_widget.latlon.get_value())
        if location:
            self.locations_widget.paste_address(location)
