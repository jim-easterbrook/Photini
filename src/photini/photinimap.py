##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-21  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from collections import OrderedDict
import locale
import logging
import os

import pkg_resources
import requests

from photini.imagelist import DRAG_MIMETYPE
from photini.metadata import LatLon
from photini.pyqt import (
    catch_all, ComboBox, Qt, QtCore, QtGui, QtSignal, QtSlot, QtWebChannel,
    QtWebEngineWidgets, QtWebKit, QtWebKitWidgets, QtWidgets, qt_version_info,
    SingleLineEdit)
from photini.technical import DoubleSpinBox

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class GeocoderBase(QtCore.QObject):
    interval = 5000

    def __init__(self, *args, **kwds):
        super(GeocoderBase, self).__init__(*args, **kwds)
        self.app = QtWidgets.QApplication.instance()
        self.block_timer = QtCore.QTimer(self)
        self.block_timer.setInterval(self.interval)
        self.block_timer.setSingleShot(True)
        self.query_cache = OrderedDict()

    def rate_limit(self):
        while self.block_timer.isActive():
            self.app.processEvents()
        self.block_timer.start()

    def cached_query(self, params, *args):
        cache_key = ','.join(sorted([':'.join(x) for x in params.items()]))
        if cache_key in self.query_cache:
            return self.query_cache[cache_key]
        results = self.query(params, *args)
        self.query_cache[cache_key] = results
        while len(self.query_cache) > 20:
            self.query_cache.popitem(last=False)
        return results


class CallHandler(QtCore.QObject):
    # Simple object (with no attributes) for JavaScript to send signals
    # to and hence invoke the methods JavaScript wants to call.
    @QtSlot(int, str)
    def log(self, level, message):
        logger.log(level, message)

    @QtSlot()
    def initialize_finished(self):
        self.parent().initialize_finished()

    @QtSlot('QVariant')
    def new_status(self, status):
        self.parent().new_status(status)

    @QtSlot(int)
    def marker_click(self, marker_id):
        self.parent().marker_click(marker_id)

    @QtSlot(float, float)
    def marker_drag(self, lat, lng):
        self.parent().marker_drag(lat, lng)

    @QtSlot(float, float, int)
    def marker_drag_end(self, lat, lng, marker_id):
        self.parent().marker_drag_end(lat, lng, marker_id)

    @QtSlot(float, float)
    def marker_drop(self, lat, lng):
        self.parent().marker_drop(lat, lng)


if QtWebEngineWidgets:
    class QWebPage(QtWebEngineWidgets.QWebEnginePage):
        def set_call_handler(self, call_handler):
            self.web_channel = QtWebChannel.QWebChannel(parent=self)
            self.setWebChannel(self.web_channel)
            self.web_channel.registerObject('python', call_handler)

        def acceptNavigationRequest(self, url, type_, isMainFrame):
            if type_ == self.NavigationTypeLinkClicked:
                if url.isLocalFile():
                    url.setScheme('http')
                QtGui.QDesktopServices.openUrl(url)
                # delete temporary child created by createWindow
                if isinstance(self.parent(), QWebPage):
                    self.deleteLater()
                return False
            return super(QWebPage, self).acceptNavigationRequest(
                url, type_, isMainFrame)

        def createWindow(self, type_):
            return QWebPage(parent=self)

        def do_java_script(self, command):
            self.runJavaScript(command)


else:
    class QWebPage(QtWebKitWidgets.QWebPage):
        def __init__(self, call_handler, *args, **kwds):
            super(QWebPage, self).__init__(*args, **kwds)
            self.call_handler = call_handler
            self.setLinkDelegationPolicy(self.DelegateAllLinks)
            self.linkClicked.connect(self.link_clicked)
            self.mainFrame().javaScriptWindowObjectCleared.connect(
                self.java_script_window_object_cleared)

        @QtSlot()
        @catch_all
        def java_script_window_object_cleared(self):
            self.mainFrame().addToJavaScriptWindowObject(
                'python', self.call_handler)

        @QtSlot(QtCore.QUrl)
        @catch_all
        def link_clicked(self, url):
            if url.isLocalFile():
                url.setScheme('http')
            QtGui.QDesktopServices.openUrl(url)

        def do_java_script(self, command):
            self.mainFrame().evaluateJavaScript(command)


class MapWebPage(QWebPage):
    if qt_version_info >= (5, 6):
        def javaScriptConsoleMessage(self, level, msg, line, source):
            logger.log(logging.INFO + (level * 10),
                       '%s line %d: %s', source, line, msg)
    else:
        def javaScriptConsoleMessage(self, msg, line, source):
            logger.error('%s line %d: %s', source, line, msg)


if QtWebEngineWidgets:
    class QWebView(QtWebEngineWidgets.QWebEngineView):
        def __init__(self, call_handler, *args, **kwds):
            super(QWebView, self).__init__(*args, **kwds)
            self.setPage(MapWebPage(parent=self))
            self.page().set_call_handler(call_handler)
            self.settings().setAttribute(
                QtWebEngineWidgets.QWebEngineSettings.Accelerated2dCanvasEnabled, False)
            self.settings().setAttribute(
                QtWebEngineWidgets.QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
            self.settings().setAttribute(
                QtWebEngineWidgets.QWebEngineSettings.LocalContentCanAccessFileUrls, True)


else:
    class QWebView(QtWebKitWidgets.QWebView):
        def __init__(self, call_handler, *args, **kwds):
            super(QWebView, self).__init__(*args, **kwds)
            self.setPage(MapWebPage(call_handler, parent=self))
            self.settings().setAttribute(
                QtWebKit.QWebSettings.LocalContentCanAccessRemoteUrls, True)
            self.settings().setAttribute(
                QtWebKit.QWebSettings.LocalContentCanAccessFileUrls, True)


class MapWebView(QWebView):
    drop_text = QtSignal(int, int, str)

    @catch_all
    def dragEnterEvent(self, event):
        if not event.mimeData().hasFormat(DRAG_MIMETYPE):
            return super(MapWebView, self).dragEnterEvent(event)
        event.acceptProposedAction()

    @catch_all
    def dragMoveEvent(self, event):
        if not event.mimeData().hasFormat(DRAG_MIMETYPE):
            return super(MapWebView, self).dragMoveEvent(event)

    @catch_all
    def dropEvent(self, event):
        if not event.mimeData().hasFormat(DRAG_MIMETYPE):
            return super(MapWebView, self).dropEvent(event)
        text = event.mimeData().data(DRAG_MIMETYPE).data().decode('utf-8')
        if text:
            self.drop_text.emit(event.pos().x(), event.pos().y(), text)


class LatLongDisplay(SingleLineEdit):
    changed = QtSignal()

    def __init__(self, image_list, *args, **kwds):
        super(LatLongDisplay, self).__init__(*args, **kwds)
        self.image_list = image_list
        self.label = QtWidgets.QLabel(translate('MapTabsAll', 'Lat, long'))
        self.label.setAlignment(Qt.AlignRight)
        self.setFixedWidth(170)
        self.setEnabled(False)
        self.editingFinished.connect(self.editing_finished)

    @QtSlot()
    @catch_all
    def editing_finished(self):
        text = self.get_value().strip()
        if text:
            try:
                new_value = list(map(float, text.split(',')))
            except Exception:
                # user typed in an invalid value
                self.refresh()
                return
        else:
            new_value = None
        for image in self.image_list.get_selected_images():
            image.metadata.latlong = new_value
        self.refresh()
        self.changed.emit()

    def refresh(self):
        images = self.image_list.get_selected_images()
        if not images:
            self.set_value(None)
            self.setEnabled(False)
            return
        values = []
        for image in images:
            value = image.metadata.latlong
            if value not in values:
                values.append(value)
        if len(values) > 1:
            self.set_multiple(choices=filter(None, values))
        else:
            self.set_value(values[0])
        self.setEnabled(True)


class PhotiniMap(QtWidgets.QWidget):
    def __init__(self, image_list, parent=None):
        super(PhotiniMap, self).__init__(parent)
        self.app = QtWidgets.QApplication.instance()
        self.image_list = image_list
        name = self.__module__.split('.')[-1]
        self.script_dir = pkg_resources.resource_filename(
            'photini', 'data/' + name + '/')
        self.drag_icon = QtGui.QPixmap(
            os.path.join(self.script_dir, '../map_pin_grey.png'))
        self.drag_hotspot = 11, 35
        self.search_string = None
        self.map_loaded = False
        self.marker_info = {}
        self.map_status = {}
        self.dropped_images = []
        self.geocoder = self.get_geocoder()
        self.setLayout(QtWidgets.QHBoxLayout())
        ## left side
        left_side = QtWidgets.QGridLayout()
        # latitude & longitude
        self.coords = LatLongDisplay(self.image_list)
        left_side.addWidget(self.coords.label, 0, 0)
        self.coords.changed.connect(self.new_coords)
        left_side.addWidget(self.coords, 0, 1)
        # altitude
        label = QtWidgets.QLabel(translate('MapTabsAll', 'Altitude'))
        label.setAlignment(Qt.AlignRight)
        left_side.addWidget(label, 1, 0)
        self.altitude = DoubleSpinBox()
        self.altitude.setSuffix(' m')
        self.altitude.new_value.connect(self.new_altitude)
        left_side.addWidget(self.altitude, 1, 1)
        if hasattr(self.geocoder, 'get_altitude'):
            self.altitude_button = QtWidgets.QPushButton(
                translate('MapTabsAll', 'Get altitude from map'))
            self.altitude_button.clicked.connect(self.get_altitude)
            left_side.addWidget(self.altitude_button, 2, 1)
        else:
            self.altitude_button = None
        # search
        label = QtWidgets.QLabel(translate('MapTabsAll', 'Search'))
        label.setAlignment(Qt.AlignRight)
        left_side.addWidget(label, 3, 0)
        self.edit_box = ComboBox()
        self.edit_box.setEditable(True)
        self.edit_box.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.edit_box.lineEdit().setPlaceholderText(
            translate('MapTabsAll', '<new search>'))
        self.edit_box.lineEdit().returnPressed.connect(self.search)
        self.edit_box.activated.connect(self.goto_search_result)
        self.clear_search()
        self.edit_box.setEnabled(False)
        left_side.addWidget(self.edit_box, 3, 1)
        # search terms and conditions
        for n, widget in enumerate(self.geocoder.search_terms()):
            left_side.addWidget(widget, n+4, 0, 1, 2)
        left_side.setColumnStretch(1, 1)
        left_side.setRowStretch(7, 1)
        self.layout().addLayout(left_side)
        # map
        # create handler for calls from JavaScript
        self.call_handler = CallHandler(parent=self)
        self.map = MapWebView(self.call_handler)
        self.map.drop_text.connect(self.drop_text)
        self.map.setAcceptDrops(False)
        self.layout().addWidget(self.map)
        self.layout().setStretch(1, 1)
        # other init
        self.image_list.image_list_changed.connect(self.image_list_changed)

    @QtSlot()
    @catch_all
    def image_list_changed(self):
        self.redraw_markers()
        self.coords.refresh()
        self.update_altitude()
        self.see_selection()

    @QtSlot()
    @catch_all
    def initialise(self):
        page = '''<!DOCTYPE html>
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
  </body>
</html>'''
        lat, lng = eval(self.app.config_store.get('map', 'centre', '(51.0, 0.0)'))
        zoom = int(eval(self.app.config_store.get('map', 'zoom', '11')))
        if QtWebEngineWidgets:
            initialize = '''    <script type="text/javascript"
      src="qrc:///qtwebchannel/qwebchannel.js">
    </script>
    <script type="text/javascript">
      var python;
      function initialize()
      {{
          new QWebChannel(qt.webChannelTransport, doLoadMap);
      }}
      function doLoadMap(channel)
      {{
          python = channel.objects.python;
          loadMap({lat}, {lng}, {zoom});
      }}
    </script>'''
        else:
            initialize = '''    <script type="text/javascript">
      function initialize()
      {{
          loadMap({lat}, {lng}, {zoom});
      }}
    </script>'''
        initialize = initialize.format(lat=lat, lng=lng, zoom=zoom)
        page = page.format(initialize=initialize, head=self.get_head())
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        self.map.setHtml(page, QtCore.QUrl.fromLocalFile(self.script_dir))

    @catch_all
    def initialize_finished(self):
        QtWidgets.QApplication.restoreOverrideCursor()
        self.map_loaded = True
        self.edit_box.setEnabled(True)
        self.map.setAcceptDrops(True)
        self.redraw_markers()

    def refresh(self):
        self.image_list.set_drag_to_map(self.drag_icon, self.drag_hotspot)
        if not self.map_loaded:
            self.initialise()
            return
        lat, lng = eval(self.app.config_store.get('map', 'centre'))
        zoom = int(eval(self.app.config_store.get('map', 'zoom')))
        self.JavaScript('setView({!r},{!r},{:d})'.format(lat, lng, zoom))

    def do_not_close(self):
        return False

    @catch_all
    def new_status(self, status):
        self.map_status.update(status)
        for key in ('centre', 'zoom'):
            if key in status:
                self.app.config_store.set(
                    'map', key, repr(self.map_status[key]))

    @QtSlot(int, int, str)
    @catch_all
    def drop_text(self, x, y, text):
        self.dropped_images = eval(text)
        self.JavaScript('markerDrop({:d},{:d})'.format(x, y))

    @catch_all
    def marker_drop(self, lat, lng):
        for path in self.dropped_images:
            image = self.image_list.get_image(path)
            image.metadata.latlong = lat, lng
        self.dropped_images = []
        self.redraw_markers()
        self.coords.refresh()
        self.see_selection()

    @QtSlot()
    @catch_all
    def new_coords(self):
        self.redraw_markers()
        self.update_altitude()
        self.see_selection()

    @QtSlot(object)
    @catch_all
    def new_altitude(self, value):
        for image in self.image_list.get_selected_images():
            image.metadata.altitude = value
        self.update_altitude()

    def update_altitude(self):
        images = self.image_list.get_selected_images()
        if not images:
            self.altitude.set_value(None)
            self.altitude.setEnabled(False)
            if self.altitude_button:
                self.altitude_button.setEnabled(False)
            return
        values = []
        for image in images:
            value = image.metadata.altitude
            if value not in values:
                values.append(value)
        if len(values) > 1:
            self.altitude.set_multiple(choices=filter(None, values))
        else:
            self.altitude.set_value(values[0])
        self.altitude.setEnabled(True)
        if self.altitude_button:
            self.altitude_button.setEnabled(bool(self.coords.get_value()))

    def see_selection(self):
        locations = []
        for image in self.image_list.get_selected_images():
            latlong = image.metadata.latlong
            if not latlong:
                continue
            location = [latlong['lat'], latlong['lon']]
            if location not in locations:
                locations.append(location)
        if not locations:
            return
        self.JavaScript('fitPoints({})'.format(repr(locations)))

    @QtSlot(list)
    @catch_all
    def new_selection(self, selection):
        self.redraw_markers()
        self.coords.refresh()
        self.update_altitude()
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
                if info['latlong'] == latlong:
                    info['images'].append(image)
                    break
            else:
                for i in range(len(self.marker_info) + 2):
                    marker_id = i
                    if marker_id not in self.marker_info:
                        break
                self.marker_info[marker_id] = {
                    'images'  : [image],
                    'latlong' : LatLon(latlong),
                    'selected': image.selected,
                    }
                self.JavaScript('addMarker({:d},{!r},{!r},{:d})'.format(
                    marker_id, latlong['lat'], latlong['lon'], image.selected))
        for marker_id in list(self.marker_info.keys()):
            info = self.marker_info[marker_id]
            if not info['images']:
                self.JavaScript('delMarker({:d})'.format(marker_id))
                del self.marker_info[marker_id]
            elif info['selected'] != any([x.selected for x in info['images']]):
                info['selected'] = not info['selected']
                self.JavaScript(
                    'enableMarker({:d},{:d})'.format(marker_id, info['selected']))

    def plot_track(self, tracks):
        latlngs = []
        for t in tracks:
            latlngs.append([[x[1], x[2]] for x in t])
        self.JavaScript('plotTrack({!r})'.format(latlngs))

    @QtSlot()
    @catch_all
    def get_altitude(self):
        altitude = self.geocoder.get_altitude(self.coords.get_value())
        if altitude is not None:
            self.new_altitude(round(altitude, 1))

    @QtSlot()
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
        for result in self.geocoder.search(search_string, bounds=bounds):
            north, east, south, west, name = result
            self.edit_box.addItem(name, (north, east, south, west))
        self.edit_box.set_dropdown_width()
        self.edit_box.showPopup()

    def clear_search(self):
        self.edit_box.clear()
        self.edit_box.addItem('')
        if self.search_string:
            self.edit_box.addItem(
                translate('MapTabsAll', '<widen search>'), 'widen')
            self.edit_box.addItem(
                translate('MapTabsAll', '<repeat search>', 'repeat'))

    @QtSlot(int)
    @catch_all
    def goto_search_result(self, idx):
        self.edit_box.setCurrentIndex(0)
        self.edit_box.clearFocus()
        if idx == 0:
            return
        data = self.edit_box.itemData(idx)
        if data is None:
            return
        if data == 'widen':
            # widen search
            self.search(search_string=self.search_string, bounded=False)
        elif data == 'repeat':
            # repeat search
            self.search(search_string=self.search_string)
        elif data[-1] is None:
            self.JavaScript('setView({},{},{})'.format(
                data[0], data[1], self.map_status['zoom']))
        else:
            self.JavaScript('adjustBounds({},{},{},{})'.format(*data))

    @catch_all
    def marker_click(self, marker_id):
        self.image_list.select_images(self.marker_info[marker_id]['images'])

    @catch_all
    def marker_drag(self, lat, lng):
        self.coords.set_value('{:.6f}, {:.6f}'.format(lat, lng))

    @catch_all
    def marker_drag_end(self, lat, lng, marker_id):
        info = self.marker_info[marker_id]
        for image in info['images']:
            image.metadata.latlong = lat, lng
        info['latlong'] = LatLon((lat, lng))
        self.coords.refresh()

    def JavaScript(self, command):
        if self.map_loaded:
            self.map.page().do_java_script(command)
