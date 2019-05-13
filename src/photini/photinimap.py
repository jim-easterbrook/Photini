##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-19  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from collections import defaultdict, OrderedDict
import locale
import logging
import os
import webbrowser

import pkg_resources
import requests
import six

from photini.configstore import key_store
from photini.imagelist import DRAG_MIMETYPE
from photini.metadata import Location
from photini.pyqt import (
    Busy, catch_all, ComboBox, CompactButton, Qt, QtCore, QtGui, QtWebChannel,
    QtWebEngineWidgets, QtWebKit, QtWebKitWidgets, QtWidgets, qt_version_info,
    scale_font, set_symbol_font, SingleLineEdit, SquareButton)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


if QtWebEngineWidgets:
    class WebEnginePage(QtWebEngineWidgets.QWebEnginePage):
        def acceptNavigationRequest(self, url, type_, isMainFrame):
            webbrowser.open_new(url.toString())
            return False

        def createWindow(self, type_):
            return WebEnginePage(self)


    WebPageBase = WebEnginePage
    WebSettings = QtWebEngineWidgets.QWebEngineSettings
    WebViewBase = QtWebEngineWidgets.QWebEngineView
else:
    WebPageBase = QtWebKitWidgets.QWebPage
    WebSettings = QtWebKit.QWebSettings
    WebViewBase = QtWebKitWidgets.QWebView


class WebPage(WebPageBase):
    if qt_version_info >= (5, 6):
        def javaScriptConsoleMessage(self, level, msg, line, source):
            logger.log(logging.INFO + (level * 10),
                       '%s line %d: %s', source, line, msg)
    else:
        def javaScriptConsoleMessage(self, msg, line, source):
            logger.error('%s line %d: %s', source, line, msg)


class WebView(WebViewBase):
    drop_text = QtCore.pyqtSignal(int, int, six.text_type)

    @catch_all
    def dragEnterEvent(self, event):
        if not event.mimeData().hasFormat(DRAG_MIMETYPE):
            return super(WebView, self).dragEnterEvent(event)
        event.acceptProposedAction()

    @catch_all
    def dragMoveEvent(self, event):
        if not event.mimeData().hasFormat(DRAG_MIMETYPE):
            return super(WebView, self).dragMoveEvent(event)

    @catch_all
    def dropEvent(self, event):
        if not event.mimeData().hasFormat(DRAG_MIMETYPE):
            return super(WebView, self).dropEvent(event)
        text = event.mimeData().data(DRAG_MIMETYPE).data().decode('utf-8')
        if text:
            self.drop_text.emit(event.pos().x(), event.pos().y(), text)


class LocationInfo(QtWidgets.QWidget):
    new_value = QtCore.pyqtSignal(object, dict)

    def __init__(self, *args, **kw):
        super(LocationInfo, self).__init__(*args, **kw)
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setVerticalSpacing(1)
        self.members = {}
        for key in ('sublocation', 'city', 'province_state',
                    'country_name', 'country_code', 'world_region'):
            self.members[key] = SingleLineEdit()
            self.members[key].editingFinished.connect(self.editing_finished)
        self.members['country_code'].setMaximumWidth(40)
        for j, text in enumerate((
                translate('PhotiniMap', 'Street'),
                translate('PhotiniMap', 'City'),
                translate('PhotiniMap', 'Province'),
                translate('PhotiniMap', 'Country'),
                translate('PhotiniMap', 'Region'),
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

    def get_value(self):
        new_value = {}
        for key in self.members:
            if self.members[key].is_multiple():
                continue
            new_value[key] = self.members[key].get_value().strip() or None
        return new_value

    @QtCore.pyqtSlot()
    @catch_all
    def editing_finished(self):
        self.new_value.emit(self, self.get_value())


class CallHandler(QtCore.QObject):
    @QtCore.pyqtSlot(int, six.text_type)
    def log(self, level, message):
        logger.log(level, message)

    @QtCore.pyqtSlot()
    def initialize_finished(self):
        try:
            self.parent().initialize_finished()
        except Exception as ex:
            logger.exception(ex)

    @QtCore.pyqtSlot(QtCore.QVariant)
    def new_status(self, status):
        try:
            self.parent().new_status(status)
        except Exception as ex:
            logger.exception(ex)

    @QtCore.pyqtSlot(int)
    def marker_click(self, marker_id):
        try:
            self.parent().marker_click(marker_id)
        except Exception as ex:
            logger.exception(ex)

    @QtCore.pyqtSlot(float, float, int)
    def marker_drag(self, lat, lng, marker_id):
        try:
            self.parent().marker_drag(lat, lng, marker_id)
        except Exception as ex:
            logger.exception(ex)

    @QtCore.pyqtSlot(float, float)
    def marker_drop(self, lat, lng):
        try:
            self.parent().marker_drop(lat, lng)
        except Exception as ex:
            logger.exception(ex)


class QTabBar(QtWidgets.QTabBar):
    context_menu = QtCore.pyqtSignal(object)

    @catch_all
    def contextMenuEvent(self, event):
        self.context_menu.emit(event)


class PhotiniMap(QtWidgets.QSplitter):
    def __init__(self, image_list, parent=None):
        super(PhotiniMap, self).__init__(parent)
        self.app = QtWidgets.QApplication.instance()
        self.image_list = image_list
        self.geocode_cache = OrderedDict()
        name = self.__class__.__name__.lower()
        self.api_key = key_store.get(name, 'api_key')
        self.search_key = key_store.get('opencage', 'api_key')
        self.script_dir = pkg_resources.resource_filename(
            'photini', 'data/' + name + '/')
        self.drag_icon = QtGui.QPixmap(
            os.path.join(self.script_dir, '../map_pin_grey.png'))
        self.drag_hotspot = 10, 35
        self.search_string = None
        self.map_loaded = False
        self.marker_info = {}
        self.map_status = {}
        self.dropped_images = []
        self.setChildrenCollapsible(False)
        left_side = QtWidgets.QWidget()
        self.addWidget(left_side)
        left_side.setLayout(QtWidgets.QFormLayout())
        left_side.layout().setContentsMargins(0, 0, 0, 0)
        left_side.layout().setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        # map
        self.map = WebView()
        self.map.setPage(WebPage(parent=self.map))
        self.call_handler = CallHandler(parent=self)
        if QtWebEngineWidgets:
            self.web_channel = QtWebChannel.QWebChannel(parent=self)
            self.map.page().setWebChannel(self.web_channel)
            self.web_channel.registerObject('python', self.call_handler)
            self.map.settings().setAttribute(
                WebSettings.Accelerated2dCanvasEnabled, False)
        else:
            self.map.page().setLinkDelegationPolicy(
                QtWebKitWidgets.QWebPage.DelegateAllLinks)
            self.map.page().linkClicked.connect(self.link_clicked)
            self.map.page().mainFrame().javaScriptWindowObjectCleared.connect(
                self.java_script_window_object_cleared)
        self.map.settings().setAttribute(
            WebSettings.LocalContentCanAccessRemoteUrls, True)
        self.map.settings().setAttribute(
            WebSettings.LocalContentCanAccessFileUrls, True)
        self.map.setAcceptDrops(False)
        self.map.drop_text.connect(self.drop_text)
        self.addWidget(self.map)
        # search
        search_layout = QtWidgets.QFormLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setVerticalSpacing(0)
        search_layout.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        self.edit_box = ComboBox()
        self.edit_box.setEditable(True)
        self.edit_box.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.edit_box.lineEdit().setPlaceholderText(
            translate('PhotiniMap', '<new search>'))
        self.edit_box.lineEdit().returnPressed.connect(self.search)
        self.edit_box.activated.connect(self.goto_search_result)
        self.clear_search()
        self.edit_box.setEnabled(False)
        search_layout.addRow(translate('PhotiniMap', 'Search'), self.edit_box)
        # search terms and conditions
        terms = self.search_terms()
        if terms:
            search_layout.addRow(*terms)
        left_side.layout().addRow(search_layout)
        if terms:
            divider = QtWidgets.QFrame()
            divider.setFrameStyle(QtWidgets.QFrame.HLine)
            left_side.layout().addRow(divider)
        left_side.layout().addItem(QtWidgets.QSpacerItem(
            1, 1000, vPolicy=QtWidgets.QSizePolicy.Expanding))
        # latitude & longitude
        layout = QtWidgets.QHBoxLayout()
        self.coords = SingleLineEdit()
        self.coords.editingFinished.connect(self.new_coords)
        self.coords.setEnabled(False)
        layout.addWidget(self.coords)
        # convert lat/lng to location info
        self.auto_location = QtWidgets.QPushButton(
            translate('PhotiniMap', six.unichr(0x21e8) + ' address'))
        self.auto_location.setFixedHeight(self.coords.height())
        self.auto_location.setEnabled(False)
        self.auto_location.clicked.connect(self.get_address)
        layout.addWidget(self.auto_location)
        left_side.layout().addRow(
            translate('PhotiniMap', 'Lat, long'), layout)
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
        left_side.layout().addRow(self.location_info)
        # address lookup (and default search) terms and conditions
        layout = QtWidgets.QHBoxLayout()
        if terms:
            widget = CompactButton(
                self.tr('Address lookup\npowered by OpenCage'))
        else:
            widget = CompactButton(
                self.tr('Search && lookup\npowered by OpenCage'))
        widget.clicked.connect(self.load_tou_opencage)
        layout.addWidget(widget)
        widget = CompactButton(
            self.tr('Geodata © OpenStreetMap\ncontributors'))
        widget.clicked.connect(self.load_tou_osm)
        layout.addWidget(widget)
        left_side.layout().addRow(layout)
        # other init
        self.image_list.image_list_changed.connect(self.image_list_changed)
        self.splitterMoved.connect(self.new_split)
        self.block_timer = QtCore.QTimer(self)
        self.block_timer.setInterval(5000)
        self.block_timer.setSingleShot(True)
        self.block_timer.timeout.connect(self.enable_search)

    def search_terms(self):
        return None

    @QtCore.pyqtSlot()
    @catch_all
    def load_tou_opencage(self):
        webbrowser.open_new('https://geocoder.opencagedata.com/')

    @QtCore.pyqtSlot()
    @catch_all
    def load_tou_osm(self):
        webbrowser.open_new('http://www.openstreetmap.org/copyright')

    @catch_all
    def closeEvent(self, event):
        if QtWebEngineWidgets:
            self.web_channel.deRegisterObject(self.call_handler)
        super(PhotiniMap, self).closeEvent(event)

    @QtCore.pyqtSlot(int, int)
    @catch_all
    def new_split(self, pos, index):
        self.app.config_store.set('map', 'split', str(self.sizes()))

    @QtCore.pyqtSlot()
    @catch_all
    def java_script_window_object_cleared(self):
        self.map.page().mainFrame().addToJavaScriptWindowObject(
            "python", self.call_handler)

    @QtCore.pyqtSlot(QtCore.QUrl)
    @catch_all
    def link_clicked(self, url):
        if url.isLocalFile():
            url.setScheme('http')
        webbrowser.open_new(url.toString())

    @QtCore.pyqtSlot()
    @catch_all
    def image_list_changed(self):
        self.redraw_markers()
        self.display_coords()
        self.display_location()
        self.see_selection()

    @QtCore.pyqtSlot()
    @catch_all
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
    <script type="text/javascript">
      var initData = {{key: "{key}", lat: {lat}, lng: {lng}, zoom: {zoom}}};
    </script>
{initialize}
{head}
    <script type="text/javascript" src="script.js" async></script>
  </head>
  <body ondragstart="return false">
    <div id="mapDiv"></div>
  </body>
</html>
'''
        lat, lng = eval(self.app.config_store.get('map', 'centre', '(51.0, 0.0)'))
        zoom = int(eval(self.app.config_store.get('map', 'zoom', '11')))
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
                           key=self.api_key, head=self.get_head())
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        self.map.setHtml(page, QtCore.QUrl.fromLocalFile(self.script_dir))

    def initialize_finished(self):
        QtWidgets.QApplication.restoreOverrideCursor()
        self.map_loaded = True
        self.edit_box.setEnabled(True)
        self.map.setAcceptDrops(True)
        self.image_list.set_drag_to_map(self.drag_icon, self.drag_hotspot)
        self.redraw_markers()
        self.display_coords()

    def refresh(self):
        self.setSizes(
            eval(self.app.config_store.get('map', 'split', str(self.sizes()))))
        if not self.map_loaded:
            self.initialise()
            return
        lat, lng = eval(self.app.config_store.get('map', 'centre'))
        zoom = int(eval(self.app.config_store.get('map', 'zoom')))
        self.JavaScript('setView({!r},{!r},{:d})'.format(lat, lng, zoom))
        self.redraw_markers()
        self.image_list.set_drag_to_map(self.drag_icon, self.drag_hotspot)

    def do_not_close(self):
        return False

    def new_status(self, status):
        self.map_status.update(status)
        for key in ('centre', 'zoom'):
            if key in status:
                self.app.config_store.set(
                    'map', key, repr(self.map_status[key]))

    @QtCore.pyqtSlot(int, int, six.text_type)
    @catch_all
    def drop_text(self, x, y, text):
        self.dropped_images = eval(text)
        self.JavaScript('markerDrop({:d},{:d})'.format(x, y))

    def marker_drop(self, lat, lng):
        for path in self.dropped_images:
            image = self.image_list.get_image(path)
            image.metadata.latlong = lat, lng
        self.dropped_images = []
        self.redraw_markers()
        self.display_coords()
        self.see_selection()

    @QtCore.pyqtSlot()
    @catch_all
    def new_coords(self):
        text = self.coords.get_value().strip()
        if not text:
            for image in self.image_list.get_selected_images():
                image.metadata.latlong = None
            self.redraw_markers()
            return
        try:
            lat, lng = map(float, text.split(','))
        except Exception:
            self.display_coords()
            return
        for image in self.image_list.get_selected_images():
            image.metadata.latlong = lat, lng
        self.redraw_markers()
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

    @QtCore.pyqtSlot(object)
    @catch_all
    def location_tab_context_menu(self, event):
        idx = self.location_info.tabBar().tabAt(event.pos())
        self.location_info.setCurrentIndex(idx)
        menu = QtWidgets.QMenu(self)
        menu.addAction(self.tr('Duplicate location'), self.duplicate_location)
        menu.addAction(self.tr('Delete location'), self.delete_location)
        action = menu.exec_(event.globalPos())

    @QtCore.pyqtSlot()
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

    @QtCore.pyqtSlot()
    @catch_all
    def delete_location(self):
        idx = self.location_info.currentIndex()
        for image in self.image_list.get_selected_images():
            # shuffle data down
            location_list = list(image.metadata.location_shown or [])
            if idx == 0:
                if location_list:
                    location = location_list[0]
                else:
                    location = None
                image.metadata.location_taken = location
            if idx <= len(location_list):
                del location_list[max(idx - 1, 0)]
            image.metadata.location_shown = location_list
        # display data
        self.display_location()

    @QtCore.pyqtSlot(int, int)
    @catch_all
    def location_tab_moved(self, idx_a, idx_b):
        self.pending_move = idx_a, idx_b
        # do actual swap when idle to avoid seg fault
        QtCore.QTimer.singleShot(0, self._location_tab_moved)

    @QtCore.pyqtSlot()
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

    @QtCore.pyqtSlot(object, dict)
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
            self.auto_location.setEnabled(
                bool(values[0]) and not self.block_timer.isActive())

    def set_tab_text(self, idx):
        if idx == 0:
            text = self.tr('camera')
        else:
            text = self.tr('subject {}').format(idx)
        self.location_info.setTabText(idx, text)

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

    @QtCore.pyqtSlot(list)
    @catch_all
    def new_selection(self, selection):
        self.coords.setEnabled(bool(selection))
        self.location_info.setEnabled(bool(selection))
        self.redraw_markers()
        self.display_coords()
        self.display_location()
        self.see_selection()

    def redraw_markers(self):
        if not self.map_loaded:
            return
        for info in self.marker_info.values():
            info['images'] = []
        for image in self.image_list.get_images():
            latlong = image.metadata.latlong
            if not latlong:
                continue
            for info in self.marker_info.values():
                if info['latlong'] == (latlong.lat, latlong.lon):
                    info['images'].append(image)
                    break
            else:
                for i in range(len(self.marker_info) + 2):
                    marker_id = i
                    if marker_id not in self.marker_info:
                        break
                self.marker_info[marker_id] = {
                    'images'  : [image],
                    'latlong' : (latlong.lat, latlong.lon),
                    'selected': image.selected,
                    }
                self.JavaScript('addMarker({:d},{!r},{!r},{:d})'.format(
                    marker_id, latlong.lat, latlong.lon, image.selected))
        for marker_id in list(self.marker_info.keys()):
            info = self.marker_info[marker_id]
            if not info['images']:
                self.JavaScript('delMarker({:d})'.format(marker_id))
                del self.marker_info[marker_id]
            elif info['selected'] != any([x.selected for x in info['images']]):
                info['selected'] = not info['selected']
                self.JavaScript(
                    'enableMarker({:d},{:d})'.format(marker_id, info['selected']))

    @QtCore.pyqtSlot()
    @catch_all
    def enable_search(self):
        self.block_timer.stop()
        self.edit_box.lineEdit().setEnabled(self.map_loaded)
        if self.search_string:
            item = self.edit_box.model().item(1)
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            item = self.edit_box.model().item(2)
            item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        self.display_coords()

    def disable_search(self):
        self.edit_box.lineEdit().setEnabled(False)
        if self.search_string:
            item = self.edit_box.model().item(1)
            item.setFlags(~(Qt.ItemIsSelectable | Qt.ItemIsEnabled))
            item = self.edit_box.model().item(2)
            item.setFlags(~(Qt.ItemIsSelectable | Qt.ItemIsEnabled))
        self.auto_location.setEnabled(False)
        self.block_timer.start()
        focus = QtWidgets.QApplication.focusWidget()
        if focus:
            focus.clearFocus()

    def do_geocode(self, params):
        cache_key = params['q']
        if 'bounds' in params:
            cache_key += params['bounds']
        if cache_key in self.geocode_cache:
            return self.geocode_cache[cache_key]
        self.disable_search()
        params['key'] = self.search_key
        params['abbrv'] = '1'
        params['no_annotations'] = '1'
        lang, encoding = locale.getdefaultlocale()
        if lang:
            params['language'] = lang
        with Busy():
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
        self.geocode_cache[cache_key] = rsp['results']
        while len(self.geocode_cache) > 20:
            self.geocode_cache.popitem(last=False)
        return rsp['results']

    def geocode(self, search_string, bounds=None):
        params = {
            'q'     : search_string,
            'limit' : '20',
            }
        if bounds:
            north, east, south, west = bounds
            w = east - west
            h = north - south
            if min(w, h) < 10.0:
                lat, lon = self.map_status['centre']
                north = min(lat + 5.0,  90.0)
                south = max(lat - 5.0, -90.0)
                east = lon + 5.0
                west = lon - 5.0
            params['bounds'] = '{!r},{!r},{!r},{!r}'.format(
                west, south, east, north)
        for result in self.do_geocode(params):
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
        'city'          :('village', 'locality', 'hamlet',
                          'neighbourhood', 'city_district', 'suburb',
                          'city', 'town', 'postcode'),
        'sublocation'   :('house_number', 'street_number',
                          'house', 'public_building', 'building', 'water',
                          'road', 'pedestrian', 'path', 'residential',
                          'street_name', 'street', 'cycleway', 'footway',
                          'place'),
        'ignore'        :('political_union', 'road_reference',
                          'road_reference_intl', 'road_type', '_type'),
        }

    @QtCore.pyqtSlot()
    @catch_all
    def get_address(self):
        results = self.do_geocode(
            {'q': self.coords.get_value().replace(' ', '')})
        if not results:
            return
        address = dict(results[0]['components'])
        if 'county_code' in address and 'county' in address:
            del address['county_code']
        if 'state_code' in address and 'state' in address:
            del address['state_code']
        self.new_location(self.location_info.currentWidget(),
                          Location.from_address(address, self.address_map))

    @QtCore.pyqtSlot()
    @catch_all
    def search(self, search_string=None, bounded=True):
        if not search_string:
            search_string = self.edit_box.lineEdit().text()
            self.edit_box.clearEditText()
        if not search_string:
            return
        self.search_string = search_string
        self.clear_search()
        if bounded:
            bounds = self.map_status['bounds']
        else:
            bounds = None
        for result in self.geocode(search_string, bounds=bounds):
            north, east, south, west, name = result
            self.edit_box.addItem(name, (north, east, south, west))
        self.edit_box.set_dropdown_width()
        self.edit_box.showPopup()

    def clear_search(self):
        self.edit_box.clear()
        self.edit_box.addItem('')
        if self.search_string:
            self.edit_box.addItem(translate('PhotiniMap', '<widen search>'))
            self.edit_box.addItem(translate('PhotiniMap', '<repeat search>'))

    @QtCore.pyqtSlot(int)
    @catch_all
    def goto_search_result(self, idx):
        self.edit_box.setCurrentIndex(0)
        self.edit_box.clearFocus()
        if idx == 0:
            return
        if self.search_string and idx == 1:
            # widen search
            self.search(search_string=self.search_string, bounded=False)
            return
        if self.search_string and idx == 2:
            # repeat search
            self.search(search_string=self.search_string)
            return
        view = self.edit_box.itemData(idx)
        if view[-1] is None:
            self.JavaScript('setView({},{},{})'.format(
                view[0], view[1], self.map_status['zoom']))
        else:
            self.JavaScript('adjustBounds({},{},{},{})'.format(*view))

    def marker_click(self, marker_id):
        self.image_list.select_images(self.marker_info[marker_id]['images'])

    def marker_drag(self, lat, lng, marker_id):
        info = self.marker_info[marker_id]
        for image in info['images']:
            image.metadata.latlong = lat, lng
        info['latlong'] = lat, lng
        self.display_coords()

    def JavaScript(self, command):
        if self.map_loaded:
            if QtWebEngineWidgets:
                self.map.page().runJavaScript(command)
            else:
                self.map.page().mainFrame().evaluateJavaScript(command)
