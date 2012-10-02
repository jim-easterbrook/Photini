##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import os

from PyQt4 import QtGui, QtCore, QtWebKit
from PyQt4.QtCore import Qt

from imagelist import GPSvalue

class ChromePage(QtWebKit.QWebPage):
    # Cludge to stop Google maps thinking we're a smart-phone and
    # expecting 'touch' API instead of mouse. See
    # http://qt-project.org/forums/viewthread/1643/
    def userAgentForUrl(self, url):
        return 'Chrome/1.0'

    def javaScriptConsoleMessage(self, msg, line, source):
        print '%s line %d: %s' % (source, line, msg)

show_map = """<!DOCTYPE html>
<html>
  <head>
    <meta name="viewport" content="initial-scale=1.0, user-scalable=no" />
    <style type="text/css">
      html { height: 100%% }
      body { height: 100%%; margin: 0; padding: 0 }
      #map_canvas { height: 100%% }
    </style>
    <script type="text/javascript"
      src="http://maps.googleapis.com/maps/api/js?v=3.1&key=%s&sensor=false&region=GB">
    </script>
    <script type="text/javascript" src="googlemap.js">
    </script>
  </head>
  <body onload="initialize(%f, %f, %d)">
    <div id="map_canvas" style="width:100%%; height:100%%"></div>
  </body>
</html>
"""

class WebView(QtWebKit.QWebView):
    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    drop_text = QtCore.pyqtSignal(int, int, str)
    def dropEvent(self, event):
        event.acceptProposedAction()
        self.drop_text.emit(
            event.pos().x(), event.pos().y(), event.mimeData().text())

class GoogleMap(QtGui.QWidget):
    api_key = 'AIzaSyBPUg_kKGYxyzV0jV7Gg9m4rxme97tE13Y'
    def __init__(self, config_store, image_list, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.config_store = config_store
        self.image_list = image_list
        self.location = dict()
        self.search_string = None
        self.map_loaded = False
        self.layout = QtGui.QGridLayout()
        self.layout.setMargin(0)
        self.layout.setRowStretch(6, 1)
        self.layout.setColumnStretch(1, 1)
        self.setLayout(self.layout)
        # map
        self.map = WebView()
        self.map.setPage(ChromePage())
        self.map.setAcceptDrops(False)
        self.map.page().loadFinished.connect(self.load_finished)
        self.map.page().mainFrame().addToJavaScriptWindowObject("python", self)
        self.map.drop_text.connect(self.drop_text)
        self.layout.addWidget(self.map, 0, 1, 8, 1)
        # search
        self.layout.addWidget(QtGui.QLabel('Search:'), 0, 0)
        self.edit_box = QtGui.QComboBox()
        self.edit_box.setMinimumWidth(200)
        self.edit_box.setEditable(True)
        self.edit_box.setInsertPolicy(QtGui.QComboBox.NoInsert)
        self.edit_box.lineEdit().returnPressed.connect(self.search)
        self.edit_box.activated.connect(self.goto_search_result)
        self.clear_search()
        self.edit_box.setEnabled(False)
        self.layout.addWidget(self.edit_box, 1, 0)
        # latitude & longitude
        self.layout.addWidget(QtGui.QLabel('Latitude, longitude:'), 2, 0)
        self.coords = QtGui.QLineEdit()
        self.coords.editingFinished.connect(self.new_coords)
        self.coords.setEnabled(False)
        self.layout.addWidget(self.coords, 3, 0)
        # load map button
        self.load_map = QtGui.QPushButton('Load map\n\nConnect to Google')
        self.load_map.clicked.connect(self.initialise)
        self.layout.addWidget(self.load_map, 7, 0)
        # other init
        self.image_list.image_list_changed.connect(self.new_images)

    def initialise(self):
        lat, lng = eval(
            self.config_store.get('map', 'centre', '(51.0, 0.0)'))
        root = os.path.dirname(__file__) + os.sep
        zoom = eval(self.config_store.get('map', 'zoom', '11'))
        self.map.setHtml(show_map % (self.api_key, lat, lng, zoom),
                         QtCore.QUrl.fromLocalFile(root))

    @QtCore.pyqtSlot(bool)
    def load_finished(self, success):
        if success:
            self.map_loaded = True
            self.layout.removeWidget(self.load_map)
            self.load_map.setParent(None)
            self.edit_box.setEnabled(True)
            self.map.setAcceptDrops(True)
            self.new_images()

    @QtCore.pyqtSlot(float, float, float, float, int)
    def new_bounds(self, span_lat, span_lng, centre_lat, centre_lng, zoom):
        self.map_span = span_lat, span_lng
        self.map_centre = centre_lat, centre_lng
        self.config_store.set('map', 'centre', str(self.map_centre))
        self.config_store.set('map', 'zoom', str(zoom))

    lat_keys = ('Exif.GPSInfo.GPSLatitude', 'Xmp.exif.GPSLatitude')
    lng_keys = ('Exif.GPSInfo.GPSLongitude', 'Xmp.exif.GPSLongitude')

    @QtCore.pyqtSlot(int, int, str)
    def drop_text(self, x, y, text):
        x = float(x) / float(self.map.width())
        y = float(y) / float(self.map.height())
        lat = self.map_centre[0] + (self.map_span[0] * (0.5 - y))
        lng = self.map_centre[1] + (self.map_span[1] * (x - 0.5))
        for path in eval(str(text)):
            image = self.image_list.get_image(path)
            self._add_marker(image, lat, lng)
            image.set_metadata(self.lat_keys, GPSvalue(lat, True))
            image.set_metadata(self.lng_keys, GPSvalue(lng, False))
        self.display_coords()

    def new_coords(self):
        lat, lng = map(float, self.coords.text().split(','))
        for image in self.image_list.get_selected_images():
            image.set_metadata(self.lat_keys, GPSvalue(lat, True))
            image.set_metadata(self.lng_keys, GPSvalue(lng, False))
            self._add_marker(image, lat, lng)
        self.JavaScript('seeAllMarkers()')

    def display_coords(self):
        coords = None
        for image in self.image_list.get_selected_images():
            lat = image.get_metadata(self.lat_keys)
            lng = image.get_metadata(self.lng_keys)
            if lat and lng:
                new_coords = lat.degrees, lng.degrees
            else:
                new_coords = None
            if coords and new_coords != coords:
                self.coords.setText("<multiple values>")
                return
            coords = new_coords
        if coords:
            self.coords.setText('%.6f, %.6f' % coords)
        else:
            self.coords.clear()

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        if selection:
            self.coords.setEnabled(True)
        else:
            self.coords.setEnabled(False)
        for image in self.image_list.get_images():
            lat = image.get_metadata(self.lat_keys)
            lng = image.get_metadata(self.lng_keys)
            if lat is not None and lng is not None:
                self.JavaScript(
                    'enableMarker("%s", %d)' % (image.path, image.selected))
        self.display_coords()

    @QtCore.pyqtSlot()
    def new_images(self):
        self.JavaScript('removeMarkers()')
        for image in self.image_list.get_images():
            lat = image.get_metadata(self.lat_keys)
            lng = image.get_metadata(self.lng_keys)
            if lat is not None and lng is not None:
                self._add_marker(image, lat.degrees, lng.degrees)
        self.JavaScript('seeAllMarkers()')

    def _add_marker(self, image, lat, lng):
        if not self.map_loaded:
            return
        if lat is None or lng is None:
            return
        self.JavaScript('addMarker("%s", %s, %s, "%s", %d)' % (
            image.path, repr(lat), repr(lng),
            image.name, image.selected))

    def search(self, search_string=None):
        if not search_string:
            search_string = self.edit_box.lineEdit().text()
        if not search_string:
            return
        self.search_string = search_string
        self.clear_search()
        self.location = dict()
        self.JavaScript('search("%s")' % (search_string))

    def clear_search(self):
        self.edit_box.clear()
        self.edit_box.addItem('<new search>')
        if self.search_string:
            self.edit_box.addItem('<repeat search>')

    @QtCore.pyqtSlot(float, float, unicode)
    def search_result(self, lat, lng, name):
        self.edit_box.addItem(name)
        self.location[unicode(name)] = lat, lng
        self.edit_box.showPopup()

    @QtCore.pyqtSlot(int)
    def goto_search_result(self, idx):
        if idx == 0:
            # new search
            self.edit_box.clearEditText()
            return
        if self.search_string and idx == 1:
            # repeat search
            self.search(self.search_string)
            return
        name = unicode(self.edit_box.itemText(idx))
        if name in self.location:
            location = self.location[name]
            self.JavaScript(
                'goTo(%s, %s)' % (repr(location[0]), repr(location[1])))

    @QtCore.pyqtSlot(str)
    def marker_drag_start(self, path):
        self.image_list.select_image(str(path))

    @QtCore.pyqtSlot(float, float, str)
    def marker_drag(self, lat, lng, path):
        image = self.image_list.get_image(str(path))
        image.set_metadata(self.lat_keys, GPSvalue(lat, True))
        image.set_metadata(self.lng_keys, GPSvalue(lng, False))
        self.display_coords()

    @QtCore.pyqtSlot(float, float, str)
    def marker_drag_end(self, lat, lng, path):
        image = self.image_list.get_image(str(path))
        image.set_metadata(self.lat_keys, GPSvalue(lat, True))
        image.set_metadata(self.lng_keys, GPSvalue(lng, False))
        self.display_coords()

    def JavaScript(self, command):
        if self.map_loaded:
            return self.map.page().mainFrame().evaluateJavaScript(command)
        return None
