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

from collections import defaultdict
import logging
import os
import webbrowser

import pkg_resources
import six

from photini.imagelist import DRAG_MIMETYPE
from photini.pyqt import (
    Qt, QtCore, QtGui, QtWebChannel, QtWebEngineWidgets,
    QtWebKitWidgets, QtWidgets, set_symbol_font, SingleLineEdit, SquareButton)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate

if QtWebEngineWidgets:
    WebPageBase = QtWebEngineWidgets.QWebEnginePage
    WebViewBase = QtWebEngineWidgets.QWebEngineView
else:
    WebPageBase = QtWebKitWidgets.QWebPage
    WebViewBase = QtWebKitWidgets.QWebView

class WebPage(WebPageBase):
    def javaScriptConsoleMessage(self, msg, line, source):
        if msg.startswith("Consider using 'dppx' units instead of 'dpi'"):
            return
        logger.error('%s line %d: %s', source, line, msg)


class WebView(WebViewBase):
    drop_text = QtCore.pyqtSignal(int, int, six.text_type)

    def dragEnterEvent(self, event):
        if not event.mimeData().hasFormat(DRAG_MIMETYPE):
            return super(WebView, self).dragEnterEvent(event)
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if not event.mimeData().hasFormat(DRAG_MIMETYPE):
            return super(WebView, self).dragMoveEvent(event)

    def dropEvent(self, event):
        if not event.mimeData().hasFormat(DRAG_MIMETYPE):
            return super(WebView, self).dropEvent(event)
        text = event.mimeData().data(DRAG_MIMETYPE).data().decode('utf-8')
        if text:
            self.drop_text.emit(event.pos().x(), event.pos().y(), text)


class LocationWidgets(QtCore.QObject):
    new_value = QtCore.pyqtSignal(str, str)

    def __init__(self, *args, **kw):
        super(LocationWidgets, self).__init__(*args, **kw)
        self.members = {
            'sublocation'   : SingleLineEdit(),
            'city'          : SingleLineEdit(),
            'province_state': SingleLineEdit(),
            'country_name'  : SingleLineEdit(),
            'country_code'  : SingleLineEdit(),
            'world_region'  : SingleLineEdit(),
            }
        self.members['sublocation'].editingFinished.connect(self.new_sublocation)
        self.members['city'].editingFinished.connect(self.new_city)
        self.members['province_state'].editingFinished.connect(self.new_province_state)
        self.members['country_name'].editingFinished.connect(self.new_country_name)
        self.members['country_code'].editingFinished.connect(self.new_country_code)
        self.members['world_region'].editingFinished.connect(self.new_world_region)
        self.members['country_code'].setMaximumWidth(40)

    def __getitem__(self, key):
        return self.members[key]

    @QtCore.pyqtSlot()
    def new_sublocation(self):
        self.send_value('sublocation')

    @QtCore.pyqtSlot()
    def new_city(self):
        self.send_value('city')

    @QtCore.pyqtSlot()
    def new_province_state(self):
        self.send_value('province_state')

    @QtCore.pyqtSlot()
    def new_country_name(self):
        self.send_value('country_name')

    @QtCore.pyqtSlot()
    def new_country_code(self):
        self.send_value('country_code')

    @QtCore.pyqtSlot()
    def new_world_region(self):
        self.send_value('world_region')

    def send_value(self, key):
        self.new_value.emit(key, self.members[key].get_value())


class LocationInfo(QtWidgets.QWidget):
    def __init__(self, *args, **kw):
        super(LocationInfo, self).__init__(*args, **kw)
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        self.members = {
            'taken': LocationWidgets(self),
            'shown': LocationWidgets(self)
            }
        self.swap = SquareButton(six.unichr(0x21c4))
        self.swap.setStyleSheet('QPushButton { font-size: 10px }')
        set_symbol_font(self.swap)
        layout.addWidget(self.swap, 0, 4)
        label = QtWidgets.QLabel(translate('PhotiniMap', 'camera'))
        layout.addWidget(label, 0, 1, 1, 2)
        label = QtWidgets.QLabel(translate('PhotiniMap', 'subject'))
        layout.addWidget(label, 0, 3)
        layout.addWidget(
            QtWidgets.QLabel(translate('PhotiniMap', 'Street:')), 1, 0)
        layout.addWidget(
            QtWidgets.QLabel(translate('PhotiniMap', 'City:')), 2, 0)
        layout.addWidget(
            QtWidgets.QLabel(translate('PhotiniMap', 'Province:')), 3, 0)
        layout.addWidget(
            QtWidgets.QLabel(translate('PhotiniMap', 'Country:')), 4, 0)
        layout.addWidget(
            QtWidgets.QLabel(translate('PhotiniMap', 'Region:')), 5, 0)
        for ts, col in (('taken', 1), ('shown', 3)):
            layout.addWidget(self.members[ts]['sublocation'], 1, col, 1, 2)
            layout.addWidget(self.members[ts]['city'], 2, col, 1, 2)
            layout.addWidget(self.members[ts]['province_state'], 3, col, 1, 2)
            layout.addWidget(self.members[ts]['country_name'], 4, col)
            layout.addWidget(self.members[ts]['country_code'], 4, col + 1)
            layout.addWidget(self.members[ts]['world_region'], 5, col, 1, 2)

    def __getitem__(self, key):
        return self.members[key]


class PhotiniMap(QtWidgets.QSplitter):
    def __init__(self, image_list, parent=None):
        super(PhotiniMap, self).__init__(parent)
        self.app = QtWidgets.QApplication.instance()
        self.config_store = self.app.config_store
        self.image_list = image_list
        self.script_dir = pkg_resources.resource_filename(
            'photini', 'data/' + self.__class__.__name__.lower() + '/')
        self.drag_icon = QtGui.QPixmap(
            os.path.join(self.script_dir, 'grey_marker.png'))
        self.search_string = None
        self.map_loaded = False
        self.marker_images = {}
        self.map_status = {}
        self.dropped_images = []
        self.setChildrenCollapsible(False)
        left_side = QtWidgets.QWidget()
        self.addWidget(left_side)
        self.grid = QtWidgets.QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setRowStretch(6, 1)
        self.grid.setColumnStretch(1, 1)
        left_side.setLayout(self.grid)
        # map
        self.map = WebView()
        self.map.setPage(WebPage(parent=self.map))
        if QtWebEngineWidgets:
            self.web_channel = QtWebChannel.QWebChannel()
            self.map.page().setWebChannel(self.web_channel)
            self.web_channel.registerObject('python', self)
        else:
            self.map.page().setLinkDelegationPolicy(
                QtWebKitWidgets.QWebPage.DelegateAllLinks)
            self.map.page().linkClicked.connect(self.link_clicked)
            self.map.page().mainFrame().javaScriptWindowObjectCleared.connect(
                self.java_script_window_object_cleared)
        self.map.setAcceptDrops(False)
        self.map.drop_text.connect(self.drop_text)
        self.addWidget(self.map)
        # search
        self.grid.addWidget(
            QtWidgets.QLabel(translate('PhotiniMap', 'Search:')), 0, 0)
        self.edit_box = QtWidgets.QComboBox()
        self.edit_box.setMinimumWidth(200)
        self.edit_box.setEditable(True)
        self.edit_box.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.edit_box.lineEdit().setPlaceholderText(
            translate('PhotiniMap', '<new search>'))
        self.edit_box.lineEdit().returnPressed.connect(self.search)
        self.edit_box.activated.connect(self.goto_search_result)
        self.clear_search()
        self.edit_box.setEnabled(False)
        self.grid.addWidget(self.edit_box, 0, 1, 1, 2)
        # latitude & longitude
        self.grid.addWidget(
            QtWidgets.QLabel(translate('PhotiniMap', 'Lat, long:')), 1, 0)
        self.coords = SingleLineEdit()
        self.coords.editingFinished.connect(self.new_coords)
        self.coords.setEnabled(False)
        self.grid.addWidget(self.coords, 1, 1)
        # convert lat/lng to location info
        self.auto_location = QtWidgets.QPushButton(
            translate('PhotiniMap', six.unichr(0x21e8) + ' address'))
        self.auto_location.setEnabled(False)
        self.auto_location.clicked.connect(self.get_address)
        self.grid.addWidget(self.auto_location, 1, 2)
        # location info
        self.location_info = LocationInfo()
        self.location_info['taken'].new_value.connect(self.new_location_taken)
        self.location_info['shown'].new_value.connect(self.new_location_shown)
        self.location_info.swap.clicked.connect(self.swap_locations)
        self.location_info.setEnabled(False)
        self.grid.addWidget(self.location_info, 3, 0, 1, 3)
        # load map button
        self.load_map = QtWidgets.QPushButton(translate('PhotiniMap', '\nLoad map\n'))
        self.load_map.clicked.connect(self.initialise)
        self.grid.addWidget(self.load_map, 7, 0, 1, 3)
        # other init
        self.image_list.image_list_changed.connect(self.image_list_changed)
        self.splitterMoved.connect(self.new_split)

    @QtCore.pyqtSlot(int, six.text_type)
    def log(self, level, message):
        logger.log(level, message)

    @QtCore.pyqtSlot(int, int)
    def new_split(self, pos, index):
        self.app.config_store.set('map', 'split', str(self.sizes()))

    @QtCore.pyqtSlot()
    def java_script_window_object_cleared(self):
        self.map.page().mainFrame().addToJavaScriptWindowObject("python", self)

    @QtCore.pyqtSlot(QtCore.QUrl)
    def link_clicked(self, url):
        if url.isLocalFile():
            url.setScheme('http')
        webbrowser.open_new(url.toString())

    @QtCore.pyqtSlot()
    def image_list_changed(self):
        self.redraw_markers()
        self.display_coords()
        self.display_location()
        self.see_selection()

    @QtCore.pyqtSlot()
    def initialise(self):
        page = '''
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="initial-scale=1.0, user-scalable=no" />
    <style type="text/css">
      html, body {{ height: 100%; margin: 0; padding: 0 }}
      #mapDiv {{ position: relative; width: 100%; height: 100% }}
    </style>
{initialize}
{head}
    <script type="text/javascript" src="script.js"></script>
  </head>
  <body ondragstart="return false">
    <div id="mapDiv"></div>
    <script type="text/javascript">
      var initData = {{lat: {lat}, lng: {lng}, zoom: {zoom}}};
    </script>
{body}
  </body>
</html>
'''
        lat, lng = eval(self.config_store.get('map', 'centre', '(51.0, 0.0)'))
        zoom = eval(self.config_store.get('map', 'zoom', '11'))
        if QtWebEngineWidgets:
            initialize = '''
    <script type="text/javascript"
      src="qrc:///qtwebchannel/qwebchannel.js">
    </script>
    <script type="text/javascript">
      var python;
      function initialize()
      {
          new QWebChannel(qt.webChannelTransport, function (channel) {
              python = channel.objects.python;
              loadMap();
              });
      }
    </script>
'''
        else:
            initialize = '''
    <script type="text/javascript">
      function initialize()
      {
          loadMap();
      }
    </script>
'''
        page = page.format(lat=lat, lng=lng, zoom=zoom, initialize=initialize,
                           **self.get_page_elements())
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        self.map.setHtml(page, QtCore.QUrl.fromLocalFile(self.script_dir))

    @QtCore.pyqtSlot()
    def initialize_finished(self):
        QtWidgets.QApplication.restoreOverrideCursor()
        self.map_loaded = True
        self.grid.removeWidget(self.load_map)
        self.load_map.setParent(None)
        show_terms = self.show_terms()
        self.grid.addLayout(show_terms, 7, 0, 1, 3)
        self.edit_box.setEnabled(True)
        self.map.setAcceptDrops(True)
        self.image_list.set_drag_to_map(self.drag_icon)
        self.redraw_markers()
        self.display_coords()

    def refresh(self):
        self.setSizes(
            eval(self.app.config_store.get('map', 'split', str(self.sizes()))))
        if not self.map_loaded:
            return
        lat, lng = eval(self.config_store.get('map', 'centre'))
        zoom = eval(self.config_store.get('map', 'zoom'))
        self.JavaScript('setView({!r},{!r},{:d})'.format(lat, lng, zoom))
        self.redraw_markers()
        self.image_list.set_drag_to_map(self.drag_icon)

    def do_not_close(self):
        return False

    @QtCore.pyqtSlot(QtCore.QVariant)
    def new_status(self, status):
        self.map_status = status
        self.config_store.set('map', 'centre', str(self.map_status['centre']))
        self.config_store.set('map', 'zoom', str(int(self.map_status['zoom'])))

    @QtCore.pyqtSlot(int, int, six.text_type)
    def drop_text(self, x, y, text):
        self.dropped_images = eval(text)
        self.JavaScript('markerDrop({:d},{:d})'.format(x, y))

    @QtCore.pyqtSlot(float, float)
    def marker_drop(self, lat, lng):
        for path in self.dropped_images:
            image = self.image_list.get_image(path)
            self._remove_image(image)
            self._set_metadata(image, lat, lng)
            self._add_image(image)
        self.dropped_images = []
        self.display_coords()
        self.see_selection()

    @QtCore.pyqtSlot()
    def new_coords(self):
        text = self.coords.get_value().strip()
        if not text:
            for image in self.image_list.get_selected_images():
                self._remove_image(image)
                image.metadata.latlong = None
            return
        try:
            lat, lng = map(float, text.split(','))
        except Exception:
            self.display_coords()
            return
        for image in self.image_list.get_selected_images():
            self._remove_image(image)
            self._set_metadata(image, lat, lng)
            self._add_image(image)
        self.display_coords()
        self.see_selection()

    def see_selection(self):
        locations = []
        for image in self.image_list.get_selected_images():
            latlong = image.metadata.latlong
            if not latlong:
                continue
            location = [latlong.lat, latlong.lon]
            if location not in locations:
                locations.append(location)
        if not locations:
            return
        self.JavaScript('fitPoints({})'.format(repr(locations)))

    @QtCore.pyqtSlot(six.text_type, six.text_type, six.text_type,
                     six.text_type, six.text_type, six.text_type)
    def set_location_taken(self, world_region, country_code, country_name,
                           province_state, city, sublocation):
        for image in self.image_list.get_selected_images():
            image.metadata.location_taken = (
                sublocation, city, province_state,
                country_name, country_code, world_region)
        self.display_location()

    @QtCore.pyqtSlot()
    def swap_locations(self):
        for image in self.image_list.get_selected_images():
            image.metadata.location_taken, image.metadata.location_shown = (
                image.metadata.location_shown, image.metadata.location_taken)
        self.display_location()

    @QtCore.pyqtSlot(six.text_type, six.text_type)
    def new_location_taken(self, key, value):
        self._new_location('location_taken', key, value)

    @QtCore.pyqtSlot(six.text_type, six.text_type)
    def new_location_shown(self, key, value):
        self._new_location('location_shown', key, value)

    def _new_location(self, taken_shown, key, value):
        for image in self.image_list.get_selected_images():
            location = getattr(image.metadata, taken_shown)
            if location:
                new_value = dict(location)
            else:
                new_value = dict.fromkeys((
                    'sublocation', 'city', 'province_state',
                    'country_name', 'country_code', 'world_region'))
            new_value[key] = value
            if not any(new_value.values()):
                new_value = None
            setattr(image.metadata, taken_shown, new_value)
        self.display_location()

    def display_coords(self):
        images = self.image_list.get_selected_images()
        if not images:
            self.coords.set_value(None)
            self.auto_location.setEnabled(False)
            return
        values = []
        for image in images:
            value = image.metadata.latlong
            if value not in values:
                values.append(value)
        if len(values) > 1:
            self.coords.set_multiple(choices=filter(None, values))
            self.auto_location.setEnabled(False)
        else:
            self.coords.set_value(values[0])
            self.auto_location.setEnabled(self.map_loaded and bool(values[0]))

    def display_location(self):
        images = self.image_list.get_selected_images()
        if not images:
            for widget_group in (self.location_info['taken'],
                                 self.location_info['shown']):
                for attr in widget_group.members:
                    widget_group[attr].set_value(None)
            return
        for taken_shown in 'taken', 'shown':
            widget_group = self.location_info[taken_shown]
            for attr in widget_group.members:
                values = []
                for image in images:
                    value = getattr(image.metadata, 'location_' + taken_shown)
                    if value:
                        value = value[attr]
                    if value not in values:
                        values.append(value)
                if len(values) > 1:
                    widget_group[attr].set_multiple(choices=filter(None, values))
                else:
                    widget_group[attr].set_value(values[0])

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        self.coords.setEnabled(bool(selection))
        self.location_info.setEnabled(bool(selection))
        for marker_id, images in self.marker_images.items():
            self.JavaScript('enableMarker({:d},{:d})'.format(
                marker_id, any([image.selected for image in images])))
        self.display_coords()
        self.display_location()
        self.see_selection()

    def redraw_markers(self):
        self.JavaScript('removeMarkers()')
        self.marker_images = {}
        for image in self.image_list.get_images():
            self._add_image(image)

    def _add_image(self, image):
        if not self.map_loaded:
            return
        latlong = image.metadata.latlong
        if not latlong:
            return
        for marker_id in self.marker_images:
            if self.marker_images[marker_id][0].metadata.latlong == latlong:
                self.marker_images[marker_id].append(image)
                if image.selected:
                    self.JavaScript(
                        'enableMarker({:d},{:d})'.format(marker_id, True))
                break
        else:
            for i in range(len(self.marker_images) + 2):
                marker_id = i
                if marker_id not in self.marker_images:
                    break
            self.marker_images[marker_id] = [image]
            self.JavaScript('addMarker({:d},{!r},{!r},{:d})'.format(
                marker_id, latlong.lat, latlong.lon,
                image.selected))

    def _remove_image(self, image):
        for marker_id in self.marker_images:
            if image in self.marker_images[marker_id]:
                break
        else:
            return
        self.marker_images[marker_id].remove(image)
        if self.marker_images[marker_id]:
            self.JavaScript('enableMarker({:d},{:d})'.format(
                marker_id,
                any([image.selected for image in self.marker_images[marker_id]])))
        else:
            self.JavaScript('delMarker({:d})'.format(marker_id))
            del self.marker_images[marker_id]

    @QtCore.pyqtSlot()
    def get_address(self):
        latlng = self.coords.get_value()
        self.JavaScript('reverseGeocode({})'.format(latlng))

    @QtCore.pyqtSlot()
    def search(self, search_string=None):
        if not search_string:
            search_string = self.edit_box.lineEdit().text()
            self.edit_box.clearEditText()
        if not search_string:
            return
        self.search_string = search_string
        self.clear_search()
        self.JavaScript('search("{}")'.format(search_string))

    def clear_search(self):
        self.edit_box.clear()
        self.edit_box.addItem('')
        if self.search_string:
            self.edit_box.addItem(translate('PhotiniMap', '<repeat search>'))

    @QtCore.pyqtSlot(float, float, float, float, six.text_type)
    def search_result(self, north, east, south, west, name):
        self.edit_box.addItem(name, (north, east, south, west))
        self.edit_box.showPopup()

    @QtCore.pyqtSlot(int)
    def goto_search_result(self, idx):
        self.edit_box.setCurrentIndex(0)
        self.edit_box.clearFocus()
        if idx == 0:
            return
        if self.search_string and idx == 1:
            # repeat search
            self.search(self.search_string)
            return
        view = self.edit_box.itemData(idx)
        self.JavaScript('adjustBounds({},{},{},{})'.format(*view))

    @QtCore.pyqtSlot(int)
    def marker_click(self, marker_id):
        self.image_list.select_images(self.marker_images[marker_id])

    @QtCore.pyqtSlot(float, float, int)
    def marker_drag(self, lat, lng, marker_id):
        for image in self.marker_images[marker_id]:
            self._set_metadata(image, lat, lng)
        self.display_coords()

    def _set_metadata(self, image, lat, lng):
        image.metadata.latlong = lat, lng

    def JavaScript(self, command):
        if self.map_loaded:
            if QtWebEngineWidgets:
                self.map.page().runJavaScript(command)
            else:
                self.map.page().mainFrame().evaluateJavaScript(command)
