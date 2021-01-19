##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2019-21  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from collections import defaultdict
import logging
import os

import requests

from photini.metadata import Location
from photini.photinimap import LatLongDisplay
from photini.pyqt import (
    catch_all, Qt, QtCore, QtGui, QtSignal, QtSlot, QtWidgets, SingleLineEdit)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class LocationInfo(QtWidgets.QWidget):
    new_value = QtSignal(object, dict)

    def __init__(self, *args, **kw):
        super(LocationInfo, self).__init__(*args, **kw)
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        self.members = {}
        for key in ('sublocation', 'city', 'province_state',
                    'country_name', 'country_code', 'world_region'):
            self.members[key] = SingleLineEdit()
            self.members[key].editingFinished.connect(self.editing_finished)
        self.members['country_code'].setMaximumWidth(40)
        for j, text in enumerate((
                translate('AddressTab', 'Street'),
                translate('AddressTab', 'City'),
                translate('AddressTab', 'Province'),
                translate('AddressTab', 'Country'),
                translate('AddressTab', 'Region'),
                )):
            label = QtWidgets.QLabel(text)
            label.setAlignment(Qt.AlignRight)
            layout.addWidget(label, j, 0)
        layout.addWidget(self.members['sublocation'], 0, 1, 1, 2)
        layout.addWidget(self.members['city'], 1, 1, 1, 2)
        layout.addWidget(self.members['province_state'], 2, 1, 1, 2)
        layout.addWidget(self.members['country_name'], 3, 1)
        layout.addWidget(self.members['country_code'], 3, 2)
        layout.addWidget(self.members['world_region'], 4, 1, 1, 2)
        layout.setRowStretch(5, 1)

    def get_value(self):
        new_value = {}
        for key in self.members:
            if self.members[key].is_multiple():
                continue
            new_value[key] = self.members[key].get_value().strip() or None
        return new_value

    @QtSlot()
    @catch_all
    def editing_finished(self):
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

    def __init__(self, image_list, parent=None):
        super(TabWidget, self).__init__(parent)
        self.app = QtWidgets.QApplication.instance()
        self.geocoder = self.app.open_cage
        self.image_list = image_list
        self.setLayout(QtWidgets.QHBoxLayout())
        ## left side
        left_side = QtWidgets.QGridLayout()
        # latitude & longitude
        self.coords = LatLongDisplay(self.image_list)
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
        terms = self.geocoder.search_terms(search=False)
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
        self.location_info.setElideMode(Qt.ElideLeft)
        self.location_info.setMovable(True)
        self.location_info.setEnabled(False)
        self.layout().addWidget(self.location_info, stretch=1)
        # other init
        self.image_list.image_list_changed.connect(self.image_list_changed)

    @QtSlot()
    @catch_all
    def image_list_changed(self):
        self.coords.refresh()
        self.auto_location.setEnabled(bool(self.coords.get_value()))
        self.display_location()

    def refresh(self):
        pass

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
        action = menu.exec_(event.globalPos())

    @QtSlot()
    @catch_all
    def duplicate_location(self):
        idx = self.location_info.currentIndex()
        for image in self.image_list.get_selected_images():
            # duplicate data
            location = Location(self._get_location(image, idx) or {})
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
        for image in self.image_list.get_selected_images():
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
        for image in self.image_list.get_selected_images():
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
    def new_location(self, widget, new_value):
        idx = self.location_info.indexOf(widget)
        for image in self.image_list.get_selected_images():
            temp = dict(self._get_location(image, idx) or {})
            temp.update(new_value)
            self._set_location(image, idx, temp)
        # new_location can be called when changing tab, so don't delete
        # tabs until later
        QtCore.QTimer.singleShot(0, self.display_location)

    def set_tab_text(self, idx):
        if idx == 0:
            text = translate('AddressTab', 'camera')
        else:
            text = translate('AddressTab', 'subject {}').format(idx)
        self.location_info.setTabText(idx, text)

    @QtSlot()
    @catch_all
    def display_location(self):
        images = self.image_list.get_selected_images()
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

    @QtSlot(list)
    @catch_all
    def new_selection(self, selection):
        self.location_info.setEnabled(bool(selection))
        self.coords.refresh()
        self.auto_location.setEnabled(bool(self.coords.get_value()))
        self.display_location()

    @QtSlot()
    @catch_all
    def get_address(self):
        location = self.geocoder.get_address(self.coords.get_value())
        if location:
            self.new_location(self.location_info.currentWidget(), location)
