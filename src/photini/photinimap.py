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
from datetime import timedelta, timezone
import locale
import logging
import os

import appdirs
import pkg_resources
import requests

from photini.imagelist import DRAG_MIMETYPE
from photini.pyqt import (
    catch_all, ComboBox, Qt, QtCore, QtGui, QtSignal, QtSlot, QtWebChannel,
    QtWebCore, QtWebWidgets, QtWidgets, qt_version_info, SingleLineEdit,
    using_qtwebengine, width_for_text)
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


if using_qtwebengine:
    class QWebPage(QtWebCore.QWebEnginePage):
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
    class QWebPage(QtWebWidgets.QWebPage):
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


if using_qtwebengine:
    class QWebView(QtWebWidgets.QWebEngineView):
        def __init__(self, call_handler, *args, **kwds):
            super(QWebView, self).__init__(*args, **kwds)
            self.setPage(MapWebPage(parent=self))
            self.page().set_call_handler(call_handler)
            self.page().profile().setCachePath(appdirs.user_cache_dir('photini'))
            settings = self.settings()
            settings.setAttribute(settings.Accelerated2dCanvasEnabled, False)
            settings.setAttribute(settings.LocalContentCanAccessRemoteUrls, True)
            settings.setAttribute(settings.LocalContentCanAccessFileUrls, True)


else:
    class QWebView(QtWebWidgets.QWebView):
        def __init__(self, call_handler, *args, **kwds):
            super(QWebView, self).__init__(*args, **kwds)
            self.setPage(MapWebPage(call_handler, parent=self))
            settings = self.settings()
            settings.setAttribute(settings.LocalContentCanAccessRemoteUrls, True)
            settings.setAttribute(settings.LocalContentCanAccessFileUrls, True)


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
        self.setFixedWidth(width_for_text(self, '8' * 23))
        self.setEnabled(False)
        self.editingFinished.connect(self.editing_finished)

    @QtSlot()
    @catch_all
    def editing_finished(self):
        selected_images = self.image_list.get_selected_images()
        new_value = self.get_value().strip() or None
        if new_value:
            try:
                new_value = list(map(float, new_value.split(',')))
            except Exception:
                # user typed in an invalid value
                self.update_display(selected_images)
                return
        for image in selected_images:
            image.metadata.latlong = new_value
        self.update_display(selected_images)
        self.changed.emit()

    def update_display(self, selected_images=None):
        if selected_images is None:
            selected_images = self.image_list.get_selected_images()
        if not selected_images:
            self.set_value(None)
            self.setEnabled(False)
            return
        values = []
        for image in selected_images:
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
        self.map_loaded = 0     # not loaded
        self.marker_info = {}
        self.map_status = {}
        self.dropped_images = []
        self.geocoder = self.get_geocoder()
        self.gpx_ids = []
        self.widgets = {}
        self.setLayout(QtWidgets.QHBoxLayout())
        ## left side
        left_side = QtWidgets.QGridLayout()
        # latitude & longitude
        self.widgets['latlon'] = LatLongDisplay(self.image_list)
        left_side.addWidget(self.widgets['latlon'].label, 0, 0)
        self.widgets['latlon'].changed.connect(self.new_coords)
        left_side.addWidget(self.widgets['latlon'], 0, 1)
        # altitude
        label = QtWidgets.QLabel(translate('MapTabsAll', 'Altitude'))
        label.setAlignment(Qt.AlignRight)
        left_side.addWidget(label, 1, 0)
        self.widgets['altitude'] = DoubleSpinBox()
        self.widgets['altitude'].setSuffix(' m')
        self.widgets['altitude'].new_value.connect(self.new_altitude)
        left_side.addWidget(self.widgets['altitude'], 1, 1)
        if hasattr(self.geocoder, 'get_altitude'):
            self.widgets['get_altitude'] = QtWidgets.QPushButton(
                translate('MapTabsAll', 'Get altitude from map'))
            self.widgets['get_altitude'].clicked.connect(self.get_altitude)
            left_side.addWidget(self.widgets['get_altitude'], 2, 1)
        else:
            self.widgets['get_altitude'] = None
        # search
        label = QtWidgets.QLabel(translate('MapTabsAll', 'Search'))
        label.setAlignment(Qt.AlignRight)
        left_side.addWidget(label, 3, 0)
        self.widgets['search'] = ComboBox()
        self.widgets['search'].setEditable(True)
        self.widgets['search'].setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.widgets['search'].lineEdit().setPlaceholderText(
            translate('MapTabsAll', '<new search>'))
        self.widgets['search'].lineEdit().returnPressed.connect(self.search)
        self.widgets['search'].activated.connect(self.goto_search_result)
        self.clear_search()
        self.widgets['search'].setEnabled(False)
        left_side.addWidget(self.widgets['search'], 3, 1)
        # search terms and conditions
        for n, widget in enumerate(self.geocoder.search_terms()):
            left_side.addWidget(widget, n+4, 0, 1, 2)
        left_side.setColumnStretch(1, 1)
        left_side.setRowStretch(7, 1)
        # GPX importer
        if self.app.gpx_importer:
            button = QtWidgets.QPushButton(
                translate('MapTabsAll', 'Load GPX file'))
            button.clicked.connect(self.load_gpx)
            left_side.addWidget(button, 8, 1)
            self.widgets['set_from_gpx'] = QtWidgets.QPushButton(
                translate('MapTabsAll', 'Set coords from GPX'))
            self.widgets['set_from_gpx'].setEnabled(False)
            self.widgets['set_from_gpx'].clicked.connect(self.set_from_gpx)
            left_side.addWidget(self.widgets['set_from_gpx'], 9, 1)
            self.widgets['clear_gpx'] = QtWidgets.QPushButton(
                translate('MapTabsAll', 'Remove GPX data'))
            self.widgets['clear_gpx'].setEnabled(False)
            self.widgets['clear_gpx'].clicked.connect(self.clear_gpx)
            left_side.addWidget(self.widgets['clear_gpx'], 10, 1)
        self.layout().addLayout(left_side)
        # map
        # create handler for calls from JavaScript
        self.call_handler = CallHandler(parent=self)
        self.widgets['map'] = MapWebView(self.call_handler)
        self.widgets['map'].drop_text.connect(self.drop_text)
        self.widgets['map'].setAcceptDrops(False)
        self.layout().addWidget(self.widgets['map'])
        self.layout().setStretch(1, 1)
        # other init
        self.image_list.image_list_changed.connect(self.image_list_changed)

    @QtSlot()
    @catch_all
    def image_list_changed(self):
        if not self.isVisible():
            return
        # add or remove markers
        self.redraw_markers()

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
        lat, lng = self.app.config_store.get('map', 'centre', (51.0, 0.0))
        zoom = int(self.app.config_store.get('map', 'zoom', 11))
        if using_qtwebengine:
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
        self.widgets['map'].setHtml(
            page, QtCore.QUrl.fromLocalFile(self.script_dir))

    @catch_all
    def initialize_finished(self):
        QtWidgets.QApplication.restoreOverrideCursor()
        self.map_loaded = 2     # finished loading
        self.widgets['search'].setEnabled(True)
        self.widgets['map'].setAcceptDrops(True)
        self.new_selection(
            self.image_list.get_selected_images(), adjust_map=False)

    def refresh(self):
        self.image_list.set_drag_to_map(self.drag_icon, self.drag_hotspot)
        selection = self.image_list.get_selected_images()
        self.widgets['latlon'].update_display(selection)
        if self.map_loaded < 1:
            self.map_loaded = 1     # started loading
            self.initialise()
            return
        if self.map_loaded < 2:
            return
        lat, lng = self.app.config_store.get('map', 'centre')
        zoom = int(self.app.config_store.get('map', 'zoom'))
        self.JavaScript('setView({!r},{!r},{:d})'.format(lat, lng, zoom))
        self.new_selection(selection, adjust_map=False)

    def do_not_close(self):
        return False

    @catch_all
    def new_status(self, status):
        self.map_status.update(status)
        for key in ('centre', 'zoom'):
            if key in status:
                self.app.config_store.set('map', key, self.map_status[key])

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
        selected_images = self.image_list.get_selected_images()
        self.redraw_markers()
        self.widgets['latlon'].update_display(selected_images)
        self.see_selection(selected_images)

    @QtSlot()
    @catch_all
    def new_coords(self):
        selected_images = self.image_list.get_selected_images()
        self.redraw_markers()
        self.see_selection(selected_images)

    @QtSlot(object)
    @catch_all
    def new_altitude(self, value):
        selected_images = self.image_list.get_selected_images()
        for image in selected_images:
            image.metadata.altitude = value
        self.update_altitude(selected_images)

    def update_altitude(self, selected_images):
        if not selected_images:
            self.widgets['altitude'].set_value(None)
            self.widgets['altitude'].setEnabled(False)
            if self.widgets['get_altitude']:
                self.widgets['get_altitude'].setEnabled(False)
            return
        values = []
        for image in selected_images:
            value = image.metadata.altitude
            if value not in values:
                values.append(value)
        if len(values) > 1:
            self.widgets['altitude'].set_multiple(choices=filter(None, values))
        else:
            self.widgets['altitude'].set_value(values[0])
        self.widgets['altitude'].setEnabled(True)
        if self.widgets['get_altitude']:
            self.widgets['get_altitude'].setEnabled(
                bool(self.widgets['latlon'].get_value()))

    def see_selection(self, selected_images):
        locations = []
        # get locations of selected images
        for image in selected_images:
            latlong = image.metadata.latlong
            if not latlong:
                continue
            location = [float(latlong['lat']), float(latlong['lon'])]
            if location not in locations:
                locations.append(location)
        # get locations of GPS track points around time of selected images
        for point in self.get_nearest_gps(selected_images):
            time_stamp, lat, lng = point
            location = [lat, lng]
            if location not in locations:
                locations.append(location)
        # adjust map
        if locations:
            self.JavaScript('fitPoints({!r})'.format(locations))

    def new_selection(self, selection, adjust_map=True):
        if 'set_from_gpx' in self.widgets:
            self.widgets['set_from_gpx'].setEnabled(
                bool(selection) and bool(self.app.gpx_importer.display_points))
        self.redraw_markers()
        self.redraw_gps_track(selection)
        self.widgets['latlon'].update_display(selection)
        self.update_altitude(selection)
        if adjust_map:
            self.see_selection(selection)

    def redraw_markers(self):
        if self.map_loaded < 2:
            return
        for info in self.marker_info.values():
            info['images'] = []
        # assign images to existing markers or create new markers
        for image in self.image_list.get_images():
            latlong = image.metadata.latlong
            if not latlong:
                continue
            location = [float(latlong['lat']), float(latlong['lon'])]
            for info in self.marker_info.values():
                if info['location'] == location:
                    info['images'].append(image)
                    break
            else:
                for i in range(len(self.marker_info) + 2):
                    marker_id = i
                    if marker_id not in self.marker_info:
                        break
                self.marker_info[marker_id] = {
                    'images'  : [image],
                    'location': location,
                    'selected': image.selected,
                    }
                self.JavaScript('addMarker({:d},{!r},{!r},{:d})'.format(
                    marker_id, location[0], location[1], image.selected))
        # delete redundant markers and enable markers with selected images
        for marker_id in list(self.marker_info.keys()):
            info = self.marker_info[marker_id]
            if not info['images']:
                self.JavaScript('delMarker({:d})'.format(marker_id))
                del self.marker_info[marker_id]
            elif info['selected'] != any([x.selected for x in info['images']]):
                info['selected'] = not info['selected']
                self.JavaScript(
                    'enableMarker({:d},{:d})'.format(marker_id, info['selected']))

    def redraw_gps_track(self, selected_images=None):
        if self.map_loaded < 2:
            return
        # update GPX track markers
        if not self.app.gpx_importer:
            return
        if not self.app.gpx_importer.display_points:
            self.JavaScript('clearGPS()')
            self.gpx_ids = []
            return
        # add any new points
        new_points = []
        for time_stamp, lat, lng in self.app.gpx_importer.display_points:
            marker_id = time_stamp.isoformat()
            if marker_id not in self.gpx_ids:
                self.gpx_ids.append(marker_id)
                new_points.append([lat, lng, marker_id])
        if new_points:
            self.JavaScript('plotGPS({!r})'.format(new_points))
        # highlight points near selected picture
        if selected_images is None:
            selected_images = self.image_list.get_selected_images()
        selected_ids = [x[0].isoformat()
                        for x in self.get_nearest_gps(selected_images)]
        self.JavaScript('enableGPS({!r})'.format(selected_ids))

    def get_nearest_gps(self, selected_images):
        if not (selected_images and self.app.gpx_importer):
            return []
        date_taken = selected_images[0].metadata.date_taken
        for image in selected_images[1:]:
            if image.metadata.date_taken != date_taken:
                return []
        if not date_taken:
            return []
        return self.app.gpx_importer.nearest(date_taken.to_utc())

    @QtSlot()
    @catch_all
    def load_gpx(self):
        new_points = self.app.gpx_importer.import_file()
        if not new_points:
            return
        self.redraw_gps_track()
        # adjust map to show points just loaded
        latlngs = []
        for p in new_points:
            time_stamp, lat, lng = p
            latlngs.append([lat, lng])
        self.JavaScript('fitPoints({!r})'.format(latlngs))
        self.widgets['clear_gpx'].setEnabled(
            bool(self.app.gpx_importer.display_points))

    @QtSlot()
    @catch_all
    def set_from_gpx(self):
        selected_images = self.image_list.get_selected_images()
        changed = False
        for image in selected_images:
            if not image.metadata.date_taken:
                continue
            utc_time = image.metadata.date_taken.to_utc()
            utc_time = utc_time.replace(tzinfo=timezone.utc)
            candidates = self.app.gpx_importer.get_locations_at(utc_time)
            if not candidates:
                continue
            nearest = candidates[0]
            for c in candidates[1:]:
                if abs(c.time - utc_time) < abs(nearest.time - utc_time):
                    nearest = c
            image.metadata.latlong = nearest.latitude, nearest.longitude
            changed = True
        if changed:
            self.redraw_markers()
            self.widgets['latlon'].update_display(selected_images)
            self.see_selection(selected_images)

    @QtSlot()
    @catch_all
    def clear_gpx(self):
        self.app.gpx_importer.clear_data()
        self.redraw_gps_track()
        self.widgets['set_from_gpx'].setEnabled(False)
        self.widgets['clear_gpx'].setEnabled(False)

    @QtSlot()
    @catch_all
    def get_altitude(self):
        altitude = self.geocoder.get_altitude(
            self.widgets['latlon'].get_value())
        if altitude is not None:
            self.new_altitude(round(altitude, 1))

    @QtSlot()
    @catch_all
    def search(self, search_string=None, bounded=True):
        if not search_string:
            search_string = self.widgets['search'].lineEdit().text()
            self.widgets['search'].clearEditText()
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
            self.widgets['search'].addItem(name, (north, east, south, west))
        self.widgets['search'].set_dropdown_width()
        self.widgets['search'].showPopup()

    def clear_search(self):
        self.widgets['search'].clear()
        self.widgets['search'].addItem('')
        if self.search_string:
            self.widgets['search'].addItem(
                translate('MapTabsAll', '<widen search>'), 'widen')
            self.widgets['search'].addItem(
                translate('MapTabsAll', '<repeat search>', 'repeat'))

    @QtSlot(int)
    @catch_all
    def goto_search_result(self, idx):
        self.widgets['search'].setCurrentIndex(0)
        self.widgets['search'].clearFocus()
        if idx == 0:
            return
        data = self.widgets['search'].itemData(idx)
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
        self.widgets['latlon'].set_value('{:.6f}, {:.6f}'.format(lat, lng))

    @catch_all
    def marker_drag_end(self, lat, lng, marker_id):
        info = self.marker_info[marker_id]
        for image in info['images']:
            image.metadata.latlong = lat, lng
        info['location'] = [float(image.metadata.latlong['lat']),
                            float(image.metadata.latlong['lon'])]
        self.widgets['latlon'].update_display()

    def JavaScript(self, command):
        if self.map_loaded >= 2:
            self.widgets['map'].page().do_java_script(command)
