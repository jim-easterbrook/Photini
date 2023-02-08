##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-23  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from datetime import timezone
import logging
import os
import pickle

import appdirs
import cachetools
import pkg_resources

from photini.imagelist import DRAG_MIMETYPE
from photini.pyqt import *
from photini.pyqt import (
    QtNetwork, QWebChannel, QWebEnginePage, QWebEngineView, qt_version_info)
from photini.technical import DoubleSpinBox
from photini.widgets import ComboBox, LatLongDisplay


logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class GeocoderBase(QtCore.QObject):
    interval = 5000
    cache_size = 200
    cache_ttl = 30 * 24 * 3600

    def __init__(self, *args, **kwds):
        super(GeocoderBase, self).__init__(*args, **kwds)
        self.app = QtWidgets.QApplication.instance()
        self.block_timer = QtCore.QTimer(self)
        self.block_timer.setInterval(self.interval)
        self.block_timer.setSingleShot(True)
        if self.cache_size:
            self.cache_file = os.path.join(
                appdirs.user_cache_dir('photini'),
                self.__class__.__name__ + '.pkl')
            try:
                with open(self.cache_file, 'rb') as f:
                    self.query_cache = pickle.load(f)
            except (AttributeError, FileNotFoundError):
                self.query_cache = cachetools.TTLCache(
                    self.cache_size, self.cache_ttl)
            logger.debug('cache %s has %d entries',
                         self.cache_file, self.query_cache.currsize)
            self.app.aboutToQuit.connect(self.save_cache)
        else:
            self.query_cache = None

    @QtSlot()
    @catch_all
    def save_cache(self):
        if self.query_cache:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.query_cache, f)

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


class MapWebPage(QWebEnginePage):
    def __init__(self, *args, call_handler=None, transient=False, **kwds):
        super(MapWebPage, self).__init__(*args, **kwds)
        self.call_handler = call_handler
        self.transient = transient
        if self.call_handler:
            self.web_channel = QWebChannel(parent=self)
            self.setWebChannel(self.web_channel)
            self.web_channel.registerObject('python', self.call_handler)
        self.profile().setCachePath(
            os.path.join(appdirs.user_cache_dir('photini'), 'WebEngine'))

    @catch_all
    def acceptNavigationRequest(self, url, type_, isMainFrame):
        if type_ != self.NavigationType.NavigationTypeLinkClicked:
            return super(MapWebPage, self).acceptNavigationRequest(
                url, type_, isMainFrame)
        if url.isLocalFile():
            url.setScheme('http')
        QtGui.QDesktopServices.openUrl(url)
        if self.transient:
            # delete temporary child created by createWindow
            self.deleteLater()
        return False

    @catch_all
    def createWindow(self, type_):
        return MapWebPage(transient=True, parent=self)

    @catch_all
    def javaScriptConsoleMessage(self, level, msg, line, source):
        logger.log(
            logging.INFO + (level * 10), '%s line %d: %s', source, line, msg)


class MapWebView(QWebEngineView):
    drop_text = QtSignal(int, int, str)

    def __init__(self, call_handler, *args, **kwds):
        super(MapWebView, self).__init__(*args, **kwds)
        self.setPage(MapWebPage(call_handler=call_handler, parent=self))
        settings = self.settings()
        settings.setAttribute(
            settings.WebAttribute.Accelerated2dCanvasEnabled, False)
        settings.setAttribute(
            settings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(
            settings.WebAttribute.LocalContentCanAccessFileUrls, True)

    @catch_all
    def dragEnterEvent(self, event):
        if not event.mimeData().hasFormat(DRAG_MIMETYPE):
            return super(MapWebView, self).dragEnterEvent(event)
        event.acceptProposedAction()

    @catch_all
    def dragMoveEvent(self, event):
        if not event.mimeData().hasFormat(DRAG_MIMETYPE):
            return super(MapWebView, self).dragMoveEvent(event)
        event.acceptProposedAction()

    @catch_all
    def dropEvent(self, event):
        if not event.mimeData().hasFormat(DRAG_MIMETYPE):
            return super(MapWebView, self).dropEvent(event)
        text = event.mimeData().data(DRAG_MIMETYPE).data().decode('utf-8')
        if text:
            if qt_version_info < (6, 0):
                pos = event.pos()
            else:
                pos = event.position().toPoint()
            self.drop_text.emit(pos.x(), pos.y(), text)
            event.acceptProposedAction()


class PhotiniMap(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(PhotiniMap, self).__init__(parent)
        self.app = QtWidgets.QApplication.instance()
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
        self.widgets['latlon'] = LatLongDisplay()
        left_side.addWidget(self.widgets['latlon'].label, 0, 0)
        self.widgets['latlon'].changed.connect(self.new_coords)
        left_side.addWidget(self.widgets['latlon'], 0, 1)
        # altitude
        label = QtWidgets.QLabel(translate('PhotiniMap', 'Altitude'))
        label.setAlignment(Qt.AlignmentFlag.AlignRight)
        left_side.addWidget(label, 1, 0)
        self.widgets['altitude'] = DoubleSpinBox()
        self.widgets['altitude'].setSuffix(' m')
        self.widgets['altitude'].new_value.connect(self.new_altitude)
        left_side.addWidget(self.widgets['altitude'], 1, 1)
        if hasattr(self.geocoder, 'get_altitude'):
            self.widgets['get_altitude'] = QtWidgets.QPushButton(
                translate('PhotiniMap', 'Get altitude from map'))
            self.widgets['get_altitude'].clicked.connect(self.get_altitude)
            left_side.addWidget(self.widgets['get_altitude'], 2, 1)
        else:
            self.widgets['get_altitude'] = None
        # search
        label = QtWidgets.QLabel(translate('PhotiniMap', 'Search'))
        label.setAlignment(Qt.AlignmentFlag.AlignRight)
        left_side.addWidget(label, 3, 0)
        self.widgets['search'] = ComboBox()
        self.widgets['search'].setEditable(True)
        self.widgets['search'].setInsertPolicy(ComboBox.InsertPolicy.NoInsert)
        self.widgets['search'].lineEdit().setPlaceholderText(
            translate('PhotiniMap', '<new search>'))
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
                translate('PhotiniMap', 'Load GPX file'))
            button.clicked.connect(self.load_gpx)
            left_side.addWidget(button, 8, 1)
            self.widgets['set_from_gpx'] = QtWidgets.QPushButton(
                translate('PhotiniMap', 'Set coords from GPX'))
            self.widgets['set_from_gpx'].setEnabled(False)
            self.widgets['set_from_gpx'].clicked.connect(self.set_from_gpx)
            left_side.addWidget(self.widgets['set_from_gpx'], 9, 1)
            self.widgets['clear_gpx'] = QtWidgets.QPushButton(
                translate('PhotiniMap', 'Remove GPX data'))
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
        self.app.image_list.image_list_changed.connect(self.image_list_changed)

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
        initialize = initialize.format(lat=lat, lng=lng, zoom=zoom)
        page = page.format(initialize=initialize, head=self.get_head())
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.widgets['map'].setHtml(
            page, QtCore.QUrl.fromLocalFile(self.script_dir))

    @catch_all
    def initialize_finished(self):
        QtWidgets.QApplication.restoreOverrideCursor()
        self.map_loaded = 2     # finished loading
        self.widgets['search'].setEnabled(True)
        self.widgets['map'].setAcceptDrops(True)
        self.new_selection(
            self.app.image_list.get_selected_images(), adjust_map=False)

    def refresh(self):
        self.app.image_list.set_drag_to_map(self.drag_icon, self.drag_hotspot)
        selection = self.app.image_list.get_selected_images()
        self.widgets['latlon'].update_display(selection)
        self.update_altitude(selection)
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
            image = self.app.image_list.get_image(path)
            gps = dict(image.metadata.gps_info or {})
            gps['lat'] = lat
            gps['lon'] = lng
            gps['method'] = 'MANUAL'
            image.metadata.gps_info = gps
        self.dropped_images = []
        self.new_coords()

    @QtSlot()
    @catch_all
    def new_coords(self):
        selected_images = self.app.image_list.get_selected_images()
        self.redraw_markers()
        self.widgets['latlon'].update_display(selected_images)
        self.update_altitude(selected_images)
        self.see_selection(selected_images)

    @QtSlot(object)
    @catch_all
    def new_altitude(self, value, images=[]):
        images = images or self.app.image_list.get_selected_images()
        for image in images:
            gps = dict(image.metadata.gps_info or {})
            gps['alt'] = value
            gps['method'] = 'MANUAL'
            image.metadata.gps_info = gps
        self.update_altitude(images)

    def update_altitude(self, selected_images):
        if not selected_images:
            self.widgets['altitude'].set_value(None)
            self.widgets['altitude'].setEnabled(False)
            if self.widgets['get_altitude']:
                self.widgets['get_altitude'].setEnabled(False)
            return
        values = []
        for image in selected_images:
            gps = image.metadata.gps_info
            if not (gps and gps['alt']):
                continue
            if gps['alt'] not in values:
                values.append(gps['alt'])
        if not values:
            self.widgets['altitude'].set_value(None)
        elif len(values) > 1:
            self.widgets['altitude'].set_multiple(choices=values)
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
            gps = image.metadata.gps_info
            if not (gps and gps['lat']):
                continue
            location = [float(gps['lat']), float(gps['lon'])]
            if location not in locations:
                locations.append(location)
        if not locations:
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
        for image in self.app.image_list.get_images():
            gps = image.metadata.gps_info
            if not (gps and gps['lat']):
                continue
            location = [float(gps['lat']), float(gps['lon'])]
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
            selected_images = self.app.image_list.get_selected_images()
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
        self.widgets['set_from_gpx'].setEnabled(
            bool(self.app.image_list.get_selected_images())
            and bool(self.app.gpx_importer.display_points))
        self.widgets['clear_gpx'].setEnabled(
            bool(self.app.gpx_importer.display_points))

    @QtSlot()
    @catch_all
    def set_from_gpx(self):
        selected_images = self.app.image_list.get_selected_images()
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
            gps = dict(image.metadata.gps_info or {})
            gps['lat'] = nearest.latitude
            gps['lon'] = nearest.longitude
            gps['alt'] = nearest.elevation
            gps['method'] = 'GPS'
            image.metadata.gps_info = gps
            changed = True
        if changed:
            self.redraw_markers()
            self.widgets['latlon'].update_display(selected_images)
            self.update_altitude(selected_images)
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
        images = self.app.image_list.get_selected_images()
        altitude = self.geocoder.get_altitude(
            self.widgets['latlon'].get_value())
        if altitude is not None:
            self.new_altitude(round(altitude, 1), images)

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
                translate('PhotiniMap', '<widen search>'), 'widen')
            self.widgets['search'].addItem(
                translate('PhotiniMap', '<repeat search>'), 'repeat')

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
        self.app.image_list.select_images(self.marker_info[marker_id]['images'])

    @catch_all
    def marker_drag(self, lat, lng):
        self.widgets['latlon'].set_value('{:.6f}, {:.6f}'.format(lat, lng))

    @catch_all
    def marker_drag_end(self, lat, lng, marker_id):
        info = self.marker_info[marker_id]
        for image in info['images']:
            gps = dict(image.metadata.gps_info or {})
            gps['lat'] = lat
            gps['lon'] = lng
            gps['method'] = 'MANUAL'
            image.metadata.gps_info = gps
        info['location'] = [float(image.metadata.gps_info['lat']),
                            float(image.metadata.gps_info['lon'])]
        self.widgets['latlon'].update_display()

    def JavaScript(self, command):
        if self.map_loaded >= 2:
            self.widgets['map'].page().runJavaScript(command)
