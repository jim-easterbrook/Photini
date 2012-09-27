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

class ChromePage(QtWebKit.QWebPage):
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
      src="http://maps.googleapis.com/maps/api/js?key=%s&sensor=false&region=GB">
    </script>
    <script type="text/javascript" src="googlemap.js">
    </script>
  </head>
  <body onload="initialize(%f, %f, %d)">
    <div id="map_canvas" style="width:100%%; height:100%%"></div>
  </body>
</html>
"""

class GoogleMap(QtGui.QWidget):
    api_key = 'AIzaSyBPUg_kKGYxyzV0jV7Gg9m4rxme97tE13Y'
    def __init__(self, config_store, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.config_store = config_store
        self.location = dict()
        self.search_string = None
        self.selection = list()
        self.map_loaded = False
        self.layout = QtGui.QGridLayout()
        self.layout.setMargin(0)
        self.layout.setRowStretch(6, 1)
        self.layout.setColumnStretch(1, 1)
        self.setLayout(self.layout)
        # map
        self.map = QtWebKit.QWebView()
        self.map.setPage(ChromePage())
        self.map.page().loadFinished.connect(self.load_finished)
        self.map.page().mainFrame().addToJavaScriptWindowObject("python", self)
        self.layout.addWidget(self.map, 0, 1, 8, 1)
        # search
        self.layout.addWidget(QtGui.QLabel('Search:'), 0, 0)
        self.edit_box = QtGui.QComboBox()
        self.edit_box.setMinimumWidth(200)
        self.edit_box.setEditable(True)
        self.edit_box.lineEdit().returnPressed.connect(self.search)
        self.edit_box.activated.connect(self.goto_search_result)
        self.clear_search()
        self.edit_box.setEnabled(False)
        self.layout.addWidget(self.edit_box, 1, 0)
        # latitude
        self.layout.addWidget(QtGui.QLabel('Latitude:'), 2, 0)
        self.latitude = QtGui.QLineEdit()
        self.layout.addWidget(self.latitude, 3, 0)
        # longitude
        self.layout.addWidget(QtGui.QLabel('Longitude:'), 4, 0)
        self.longitude = QtGui.QLineEdit()
        self.layout.addWidget(self.longitude, 5, 0)
        # load map button
        self.load_map = QtGui.QPushButton('Load map\n\nConnect to Google')
        self.load_map.clicked.connect(self.initialise)
        self.layout.addWidget(self.load_map, 7, 0)

    def initialise(self):
        last_position = 51.0, 0.0
        latitude, longitude = eval(
            self.config_store.get('map', 'last_position', str(last_position)))
        self.map.setHtml(show_map % (self.api_key, latitude, longitude, 11),
                         QtCore.QUrl('file://%s/' % os.path.dirname(__file__)))

    @QtCore.pyqtSlot(bool)
    def load_finished(self, success):
        if success:
            self.map_loaded = True
            self.layout.removeWidget(self.load_map)
            self.load_map.setParent(None)
            self.edit_box.setEnabled(True)

    lat_keys = ('Xmp.exif.GPSLatitude', 'Exif.GPSInfo.GPSLatitude')
    long_keys = ('Xmp.exif.GPSLongitude', 'Exif.GPSInfo.GPSLongitude')

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        self.selection = selection
        self.JavaScript('removeMarkers()')
        if not self.selection:
            self.latitude.clear()
            self.longitude.clear()
            return
        # get info from first image
        image = self.selection[0]
        latitude = image.get_metadata(self.lat_keys)
        longitude = image.get_metadata(self.long_keys)
        self.add_marker(latitude, longitude, image.name)
        # check remaining images
        for image in self.selection[1:]:
            new_latitude = image.get_metadata(self.lat_keys)
            new_longitude = image.get_metadata(self.long_keys)
            self.add_marker(new_latitude, new_longitude, image.name)
            if new_latitude != latitude:
                latitude = "<multiple values>"
            if new_longitude != longitude:
                longitude = "<multiple values>"
        if isinstance(latitude, float):
            self.latitude.setText('%.8f' % (latitude))
        elif latitude:
            self.latitude.setText(str(latitude))
        if isinstance(longitude, float):
            self.longitude.setText('%.8f' % (longitude))
        elif longitude:
            self.longitude.setText(str(longitude))

    def add_marker(self, latitude, longitude, name):
        if not self.map_loaded:
            return
        if latitude is None or longitude is None:
            return
        self.JavaScript('addMarker(%f, %f, "%s")' % (latitude, longitude, name))
        self.config_store.set('map', 'last_position', str((latitude, longitude)))

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
            self.JavaScript('goTo(%f, %f, 11)' % location)
            self.config_store.set('map', 'last_position', str(location))

    @QtCore.pyqtSlot(float, float, str)
    def done(self, lat, lng, name):
        print 'done', lat, lng, name

    def JavaScript(self, command):
        if self.map_loaded:
            self.map.page().mainFrame().evaluateJavaScript(command)
