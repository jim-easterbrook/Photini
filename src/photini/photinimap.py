##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import base64
from datetime import timezone
import io
import logging
import os
import pickle

import cachetools
import PIL.Image, PIL.ImageDraw
import platformdirs

from photini.imagelist import DRAG_MIMETYPE
from photini.pyqt import *
from photini.pyqt import (QtNetwork, QtWebChannel, QtWebEngineCore,
                          QtWebEngineWidgets, qt_version_info)
from photini.widgets import AltitudeDisplay, ComboBox, Label, LatLongDisplay


logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class MapIconFactory(QtCore.QObject):
    icons_changed = QtSignal()

    def __init__(self, *args, **kwds):
        super(MapIconFactory, self).__init__(*args, **kwds)
        self.app = QtWidgets.QApplication.instance()
        self.src_dir = os.path.join(os.path.dirname(__file__), 'data', 'map')
        self._icons = {True: {}, False: {}}
        self.new_colours()

    def new_colours(self):
        # get source elements
        image = PIL.Image.open(os.path.join(self.src_dir, 'pin_image.png'))
        alpha = PIL.Image.open(os.path.join(self.src_dir, 'pin_alpha.png'))
        # composite elements and resize to make pin icons
        marker_height = width_for_text(self.parent(), 'X' * 35) // 8
        for active in (False, True):
            colour = {False: '#a8a8a8', True: '#ff3000'}[active]
            colour = self.app.config_store.get(
                'map', 'pin_colour_{}'.format(active), colour)
            marker = PIL.Image.composite(
                PIL.Image.new('RGB', alpha.size, colour), image, alpha)
            w, h = marker.size
            w = (w * marker_height) // h
            h = marker_height
            self._icons[True][active] = marker.resize((w, h), PIL.Image.LANCZOS)
        # draw GPS track markers
        marker_size = width_for_text(self.parent(), 'X' * 11) // 8
        w = marker_size * 8
        d = w // 10
        alpha = PIL.Image.new("L", (w, w), 0)
        draw = PIL.ImageDraw.Draw(alpha)
        draw.ellipse((d, d, w - d, w - d), fill=64, outline=255, width=w // 10)
        # resize alpha to get anti-aliased drawing
        alpha = alpha.resize((marker_size, marker_size), PIL.Image.LANCZOS)
        # composite with colours
        for active in (False, True):
            colour = {False: '#3388ff', True: '#ff0000'}[active]
            colour = self.app.config_store.get(
                'map', 'gps_colour_{}'.format(active), colour)
            self._icons[False][active] = PIL.Image.new(
                'RGB', alpha.size, colour)
            self._icons[False][active].putalpha(alpha)
            self._icons[False][active] = self._icons[False][active].copy()
        self.icons_changed.emit()

    def get_pin_as_pixmap(self, pin, active):
        data = io.BytesIO()
        self._icons[pin][active].save(data, 'PNG')
        buf = QtCore.QBuffer()
        buf.setData(data.getvalue())
        reader = QtGui.QImageReader(buf)
        return QtGui.QPixmap.fromImage(reader.read())

    def get_pin_as_url(self, pin, active):
        data = io.BytesIO()
        self._icons[pin][active].save(data, 'PNG')
        data = data.getvalue()
        return 'data:image/png;base64,' + base64.b64encode(data).decode('ascii')

    def get_pin_size(self, pin):
        return list(self._icons[pin][False].size)


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
                platformdirs.user_cache_dir('photini'),
                self.__class__.__name__ + '.pkl')
            try:
                with open(self.cache_file, 'rb') as f:
                    self.query_cache = pickle.load(f)
            except Exception as ex:
                if not isinstance(ex, (AttributeError, FileNotFoundError,
                                       ModuleNotFoundError)):
                    logger.exception(ex)
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

    @QtSlot(bool)
    def initialize_finished(self, OK):
        self.parent().initialize_finished(OK)

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


class MapWebPage(QtWebEngineCore.QWebEnginePage):
    def __init__(self, *args, call_handler=None, transient=False, **kwds):
        super(MapWebPage, self).__init__(*args, **kwds)
        self.call_handler = call_handler
        self.transient = transient
        if self.call_handler:
            self.web_channel = QtWebChannel.QWebChannel(parent=self)
            self.setWebChannel(self.web_channel)
            self.web_channel.registerObject('python', self.call_handler)
        self.local_links = False

    def set_local_links(self):
        self.local_links = True

    @catch_all
    def acceptNavigationRequest(self, url, type_, isMainFrame):
        if self.local_links or (
                type_ != self.NavigationType.NavigationTypeLinkClicked):
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
        level = {
            self.JavaScriptConsoleMessageLevel.InfoMessageLevel: logging.INFO,
            self.JavaScriptConsoleMessageLevel.WarningMessageLevel: logging.WARNING,
            self.JavaScriptConsoleMessageLevel.ErrorMessageLevel: logging.ERROR,
            }[level]
        logger.log(level, '%s line %d: %s', source, line, msg)


class MapWebView(QtWebEngineWidgets.QWebEngineView):
    drop_text = QtSignal(int, int, str)

    def __init__(self, call_handler, *args, **kwds):
        super(MapWebView, self).__init__(*args, **kwds)
        self.setPage(MapWebPage(call_handler=call_handler, parent=self))

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
    use_layout_direction = True

    def __init__(self, parent=None):
        super(PhotiniMap, self).__init__(parent)
        self.app = QtWidgets.QApplication.instance()
        self.app.loggerwindow.hide_word(self.api_key)
        self.script_dir = os.path.join(os.path.dirname(__file__), 'data', 'map')
        self.drag_icon = self.app.map_icon_factory.get_pin_as_pixmap(
            True, False)
        w, h = self.app.map_icon_factory.get_pin_size(True)
        self.search_string = None
        self.map_loaded = 0     # not loaded
        self.marker_info = {}
        self.map_status = {}
        self.dropped_images = []
        self.geocoder = self.get_geocoder()
        self.gpx_ids = []
        self.widgets = {}
        # timer to count marker clicks
        self.click_info = {'id': None}
        self.click_timer = QtCore.QTimer(self)
        self.click_timer.setSingleShot(True)
        self.click_timer.setInterval(self.app.doubleClickInterval())
        self.click_timer.timeout.connect(self.click_timer_expired)
        self.setLayout(QtWidgets.QHBoxLayout())
        ## left side
        left_side = QtWidgets.QGridLayout()
        # latitude & longitude
        self.widgets['latlon'] = LatLongDisplay()
        left_side.addWidget(self.widgets['latlon'].label, 0, 0)
        self.widgets['latlon'].new_value.connect(self.new_latlon)
        left_side.addWidget(self.widgets['latlon'], 0, 1)
        # altitude
        self.widgets['alt'] = AltitudeDisplay()
        left_side.addWidget(self.widgets['alt'].label, 1, 0)
        self.widgets['alt'].new_value.connect(self.new_value)
        left_side.addWidget(self.widgets['alt'], 1, 1)
        if hasattr(self.geocoder, 'get_altitude'):
            self.widgets['get_altitude'] = QtWidgets.QPushButton(
                translate('PhotiniMap', 'Get altitude from map'))
            self.widgets['get_altitude'].clicked.connect(self.get_altitude)
            left_side.addWidget(self.widgets['get_altitude'], 2, 1)
        else:
            self.widgets['get_altitude'] = None
        # search
        label = Label(translate('PhotiniMap', 'Search'))
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
            self.widgets['load_gpx'] = QtWidgets.QPushButton(
                translate('PhotiniMap', 'Load GPX file'))
            self.widgets['load_gpx'].setEnabled(False)
            self.widgets['load_gpx'].clicked.connect(self.load_gpx)
            self.widgets['set_from_gpx'] = QtWidgets.QPushButton(
                translate('PhotiniMap', 'Set coords from GPX'))
            self.widgets['set_from_gpx'].setEnabled(False)
            self.widgets['set_from_gpx'].clicked.connect(self.set_from_gpx)
            self.widgets['clear_gpx'] = QtWidgets.QPushButton(
                translate('PhotiniMap', 'Remove GPX data'))
            self.widgets['clear_gpx'].setEnabled(False)
            self.widgets['clear_gpx'].clicked.connect(self.clear_gpx)
            width = max(self.widgets['load_gpx'].sizeHint().width(),
                        self.widgets['set_from_gpx'].sizeHint().width(),
                        self.widgets['clear_gpx'].sizeHint().width())
            if width > self.widgets['latlon'].size().width():
                args = 0, 1, 2
            else:
                args = 1, 1, 1
            left_side.addWidget(self.widgets['load_gpx'], 8, *args)
            left_side.addWidget(self.widgets['set_from_gpx'], 9, *args)
            left_side.addWidget(self.widgets['clear_gpx'], 10, *args)
        self.layout().addLayout(left_side)
        # map
        # create handler for calls from JavaScript
        self.call_handler = CallHandler(parent=self)
        self.widgets['map'] = MapWebView(self.call_handler)
        self.widgets['map'].setUrl(QtCore.QUrl(''))
        self.widgets['map'].drop_text.connect(self.drop_text)
        self.widgets['map'].setAcceptDrops(False)
        self.layout().addWidget(self.widgets['map'])
        self.layout().setStretch(1, 1)
        # other init
        self.app.image_list.image_list_changed.connect(self.image_list_changed)
        self.app.map_icon_factory.icons_changed.connect(self.set_icon_data)

    @QtSlot()
    @catch_all
    def image_list_changed(self):
        if not self.isVisible():
            return
        # add or remove markers
        self.redraw_markers()

    def get_body(self, text_dir):
        return '''  <body ondragstart="return false">
    <div id="mapDiv" dir="{text_dir}"></div>
  </body>'''.format(text_dir=text_dir)

    def get_options(self):
        return {}

    @QtSlot()
    @catch_all
    def initialise(self):
        lat, lng = self.app.config_store.get('map', 'centre', (51.0, 0.0))
        zoom = float(self.app.config_store.get('map', 'zoom', 11))
        lang = self.app.language['primary']
        text_dir = ('ltr', 'rtl')[
            self.use_layout_direction and
            self.layoutDirection() == Qt.LayoutDirection.RightToLeft]
        page = '''<!DOCTYPE html>
<html lang="{lang}" dir="{text_dir}">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="initial-scale=1.0, user-scalable=no" />
    <style type="text/css">
      html, body {{ height: 100%; margin: 0; padding: 0 }}
      #mapDiv {{ position: relative; width: 100%; height: 100% }}
    </style>
    <script type="text/javascript"
      src="qrc:///qtwebchannel/qwebchannel.js">
    </script>
    <script type="text/javascript">
      var python;
      function initialize() {{
          new QWebChannel(qt.webChannelTransport, doLoadMap);
      }}
      function doLoadMap(channel) {{
          python = channel.objects.python;
          loadMap({lat}, {lng}, {zoom}, {options});
      }}
    </script>
{head}
  </head>
{body}
</html>'''.format(lat=lat, lng=lng, zoom=zoom, lang=lang, text_dir=text_dir,
                  head=self.get_head(), body=self.get_body(text_dir),
                  options=self.get_options())
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.widgets['map'].setHtml(
            page, QtCore.QUrl.fromLocalFile(self.script_dir + '/'))

    @catch_all
    def initialize_finished(self, OK):
        QtWidgets.QApplication.restoreOverrideCursor()
        if not OK:
            self.widgets['map'].page().set_local_links()
            link = '<a href="https://webglreport.com/">webglreport.com</a>'
            msg = translate('PhotiniMap', 'The map could not be loaded.'
                            ' This might be a WebGL problem. You can test'
                            ' this by clicking on {}.').format(link)
            self.widgets['map'].setHtml('''<!DOCTYPE html>
<html>
  <head><meta charset="utf-8" /></head>
  <body><h1>{}</h1><p>{}</p>
  </body>
</html>'''.format(translate('PhotiniMap', 'Map unavailable'), msg))
            return
        self.map_loaded = 2     # finished loading
        self.set_icon_data()
        self.widgets['search'].setEnabled(True)
        if 'load_gpx' in self.widgets:
            self.widgets['load_gpx'].setEnabled(True)
        self.widgets['map'].setAcceptDrops(True)
        self.new_selection(
            self.app.image_list.get_selected_images(), adjust_map=False)

    @QtSlot()
    @catch_all
    def set_icon_data(self):
        if self.map_loaded < 2:
            return
        for pin in (False, True):
            size = self.app.map_icon_factory.get_pin_size(pin)
            for active in (False, True):
                self.JavaScript('setIconData({:d},{:d},{!r},{!r})'.format(
                    pin, active,
                    self.app.map_icon_factory.get_pin_as_url(pin, active),
                    size))
        self.redraw_markers(force=True)

    def refresh(self):
        self.app.image_list.set_drag_to_map(self.drag_icon)
        selection = self.app.image_list.get_selected_images()
        self.update_display(selection, adjust_map=False)
        if self.map_loaded < 1:
            self.map_loaded = 1     # started loading
            self.initialise()
            return
        if self.map_loaded < 2:
            return
        lat, lng = self.app.config_store.get('map', 'centre')
        zoom = float(self.app.config_store.get('map', 'zoom'))
        self.JavaScript('setView({!r},{!r},{:f})'.format(lat, lng, zoom))
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
        value = {'exif:GPSLatitude': lat, 'exif:GPSLongitude': lng}
        images = [self.app.image_list.get_image(path)
                  for path in self.dropped_images]
        self.dropped_images = []
        self.new_value(value, images=images, adjust_map=False)

    @QtSlot(dict)
    @catch_all
    def new_latlon(self, value):
        self.new_value(value, adjust_map=True)

    @QtSlot(dict)
    @catch_all
    def new_value(self, value, images=[], adjust_map=False):
        images = images or self.app.image_list.get_selected_images()
        value['method'] = 'MANUAL'
        for image in images:
            gps = dict(image.metadata.gps_info)
            gps.update(value)
            image.metadata.gps_info = gps
        self.update_display(images, adjust_map=adjust_map)

    def update_display(self, images, adjust_map=True):
        self.redraw_markers()
        values = []
        for image in images:
            values.append(image.metadata.gps_info)
        self.widgets['latlon'].set_value_list(values)
        self.widgets['alt'].set_value_list(values)
        if self.widgets['get_altitude']:
            self.widgets['get_altitude'].setEnabled(
                bool(self.widgets['latlon'].get_value()))
        if adjust_map:
            self.see_selection(images)

    def see_selection(self, selected_images):
        locations = []
        # get locations of selected images
        for image in selected_images:
            gps = image.metadata.gps_info
            if not gps['exif:GPSLatitude']:
                continue
            location = [float(gps['exif:GPSLatitude']),
                        float(gps['exif:GPSLongitude'])]
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
            self.widgets['clear_gpx'].setEnabled(
                bool(self.app.gpx_importer.display_points))
        self.redraw_gps_track(selection)
        self.update_display(selection, adjust_map=adjust_map)

    def redraw_markers(self, force=False):
        if self.map_loaded < 2:
            return
        for info in self.marker_info.values():
            info['images'] = []
        # assign images to existing markers or create new marker_info
        for image in self.app.image_list.get_images():
            gps = image.metadata.gps_info
            if not gps['exif:GPSLatitude']:
                continue
            location = [float(gps['exif:GPSLatitude']),
                        float(gps['exif:GPSLongitude'])]
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
                    }
        # update markers on map
        for marker_id in list(self.marker_info.keys()):
            info = self.marker_info[marker_id]
            selected = any([x.selected for x in info['images']])
            if not info['images']:
                # delete redundant marker
                self.JavaScript('delMarker({:d})'.format(marker_id))
                del self.marker_info[marker_id]
            elif 'selected' not in info:
                # create new marker
                info['selected'] = selected
                location = info['location']
                self.JavaScript('addMarker({:d},{!r},{!r},{:d})'.format(
                    marker_id, location[0], location[1], selected))
            elif force or info['selected'] != selected:
                # update existing marker
                info['selected'] = selected
                self.JavaScript(
                    'enableMarker({:d},{:d})'.format(marker_id, selected))

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
        set_altitude = self.app.config_store.get('map', 'gpx_altitude', True)
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
            gps = dict(image.metadata.gps_info)
            gps['exif:GPSLatitude'] = nearest.latitude
            gps['exif:GPSLongitude'] = nearest.longitude
            if set_altitude and nearest.elevation is not None:
                gps['exif:GPSAltitude'] = round(nearest.elevation, 1)
            else:
                gps['exif:GPSAltitude'] = None
            gps['method'] = 'GPS'
            image.metadata.gps_info = gps
            changed = True
        if changed:
            self.update_display(selected_images)

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
            self.new_value(
                {'exif:GPSAltitude': round(altitude, 1)}, images=images)

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
        self.click_timer.start()
        if self.click_info['id'] != marker_id:
            self.click_info = {
                'id': marker_id,
                'count': 0,
                'marker_list': [marker_id],
                }
        self.click_info['count'] += 1
        if self.click_info['count'] == 2:
            # sort markers by proximity
            marker_list = [(self.marker_distance(marker_id, id), id)
                           for id in self.marker_info]
            marker_list.sort()
            self.click_info['marker_list'] = [x[1] for x in marker_list]
        # select markers' images
        images = []
        for id in self.click_info['marker_list'][:self.click_info['count']]:
            images += self.marker_info[id]['images']
        self.app.image_list.select_images(images)

    @QtSlot()
    @catch_all
    def click_timer_expired(self):
        self.click_info = {'id': None}

    def marker_distance(self, id_a, id_b):
        lat_a, lng_a = self.marker_info[id_a]['location']
        lat_b, lng_b = self.marker_info[id_b]['location']
        return (lat_a - lat_b)**2 + (lng_a - lng_b)**2

    @catch_all
    def marker_drag(self, lat, lng):
        self.widgets['latlon'].set_value((lat, lng))

    @catch_all
    def marker_drag_end(self, lat, lng, marker_id):
        info = self.marker_info[marker_id]
        for image in info['images']:
            gps = dict(image.metadata.gps_info)
            gps['exif:GPSLatitude'] = lat
            gps['exif:GPSLongitude'] = lng
            gps['method'] = 'MANUAL'
            image.metadata.gps_info = gps
        info['location'] = [float(image.metadata.gps_info['exif:GPSLatitude']),
                            float(image.metadata.gps_info['exif:GPSLongitude'])]
        self.widgets['latlon'].set_value_list(
            [info['images'][0].metadata.gps_info])

    def JavaScript(self, command):
        if self.map_loaded >= 2:
            self.widgets['map'].page().runJavaScript(command)
