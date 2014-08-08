##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-14  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import logging
import os
import webbrowser

from PyQt4 import QtGui, QtCore, QtWebKit
from PyQt4.QtCore import Qt

from .utils import data_dir
from . import __version__

class WebPage(QtWebKit.QWebPage):
    def __init__(self, parent=None):
        QtWebKit.QWebPage.__init__(self, parent)
        self.logger = logging.getLogger(self.__class__.__name__)

    def javaScriptConsoleMessage(self, msg, line, source):
        if unicode(msg).startswith(
                        "Consider using 'dppx' units instead of 'dpi'"):
            return
        self.logger.error('%s line %d: %s', source, line, msg)

    def userAgentForUrl(self, url):
        # Nominatim requires the user agent to identify the application
        if url.host() == 'nominatim.openstreetmap.org':
            return 'Photini/%s' % __version__
        return QtWebKit.QWebPage.userAgentForUrl(self, url)

class WebView(QtWebKit.QWebView):
    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    drop_text = QtCore.pyqtSignal(int, int, str)
    def dropEvent(self, event):
        if not event.mimeData().hasText():
            return
        text = event.mimeData().text()
        if not str(text).strip():
            return
        event.acceptProposedAction()
        self.drop_text.emit(event.pos().x(), event.pos().y(), text)

class PhotiniMap(QtGui.QWidget):
    def __init__(self, config_store, image_list, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.config_store = config_store
        self.image_list = image_list
        self.location = dict()
        self.search_string = None
        self.map_loaded = False
        layout = QtGui.QGridLayout()
        layout.setMargin(0)
        layout.setRowStretch(6, 1)
        layout.setColumnStretch(1, 1)
        self.setLayout(layout)
        # map
        self.map = WebView()
        self.map.setPage(WebPage())
        self.map.setAcceptDrops(False)
        self.map.page().setLinkDelegationPolicy(QtWebKit.QWebPage.DelegateAllLinks)
        self.map.page().linkClicked.connect(self.link_clicked)
        self.map.page().loadFinished.connect(self.load_finished)
        self.map.page().mainFrame().addToJavaScriptWindowObject("python", self)
        self.map.drop_text.connect(self.drop_text)
        self.layout().addWidget(self.map, 0, 1, 8, 1)
        # search
        self.layout().addWidget(QtGui.QLabel('Search:'), 0, 0)
        self.edit_box = QtGui.QComboBox()
        self.edit_box.setMinimumWidth(200)
        self.edit_box.setEditable(True)
        self.edit_box.setInsertPolicy(QtGui.QComboBox.NoInsert)
        self.edit_box.lineEdit().setPlaceholderText('<new search>')
        self.edit_box.lineEdit().returnPressed.connect(self.search)
        self.edit_box.activated.connect(self.goto_search_result)
        self.clear_search()
        self.edit_box.setEnabled(False)
        self.layout().addWidget(self.edit_box, 1, 0)
        # latitude & longitude
        self.layout().addWidget(QtGui.QLabel('Latitude, longitude:'), 2, 0)
        self.coords = QtGui.QLineEdit()
        self.coords.editingFinished.connect(self.new_coords)
        self.coords.setEnabled(False)
        self.layout().addWidget(self.coords, 3, 0)
        # load map button
        self.load_map = QtGui.QPushButton('\nLoad map\n')
        self.load_map.clicked.connect(self.initialise)
        self.layout().addWidget(self.load_map, 7, 0)
        # other init
        self.image_list.image_list_changed.connect(self.image_list_changed)

    def link_clicked(self, url):
        webbrowser.open_new(url.toString())

    @QtCore.pyqtSlot()
    def image_list_changed(self):
        self.new_images()
        self.see_all()

    def initialise(self):
        page_start = """
<!DOCTYPE html>
<html>
  <head>
    <meta name="viewport" http-equiv="Content-Type"
      content="initial-scale=1.0, user-scalable=no" />
    <style type="text/css">
      html { height: 100% }
      body { height: 100%; margin: 0; padding: 0 }
      #mapDiv { height: 100% }
    </style>
"""
        page_end = """
    <script type="text/javascript" src="%s.js">
    </script>
  </head>
  <body onload="initialize(%f, %f, %d)">
    <div id="mapDiv" style="width:100%%; height:100%%"></div>
  </body>
</html>
"""
        lat, lng = eval(
            self.config_store.get('map', 'centre', '(51.0, 0.0)'))
        zoom = eval(self.config_store.get('map', 'zoom', '11'))
        self.map.setHtml(
            page_start + self.load_api() +
            page_end % (self.__class__.__name__.lower(), lat, lng, zoom),
            QtCore.QUrl.fromLocalFile(data_dir))

    @QtCore.pyqtSlot(bool)
    def load_finished(self, success):
        if success:
            self.map_loaded = True
            self.layout().removeWidget(self.load_map)
            self.load_map.setParent(None)
            show_terms = self.show_terms()
            show_terms.setStyleSheet('QPushButton, QLabel { font-size: 10px }')
            self.layout().addWidget(show_terms, 7, 0)
            self.edit_box.setEnabled(True)
            self.map.setAcceptDrops(True)
            self.new_images()

    def refresh(self):
        if not self.map_loaded:
            return
        lat, lng = eval(self.config_store.get('map', 'centre'))
        zoom = eval(self.config_store.get('map', 'zoom'))
        self.JavaScript('setView(%s, %s, %d)' % (repr(lat), repr(lng), zoom))
        self.new_images()

    @QtCore.pyqtSlot(float, float, int)
    def new_bounds(self, centre_lat, centre_lng, zoom):
        self.map_centre = centre_lat, centre_lng
        self.config_store.set('map', 'centre', str(self.map_centre))
        self.config_store.set('map', 'zoom', str(zoom))

    @QtCore.pyqtSlot(int, int, str)
    def drop_text(self, x, y, text):
        lat, lng = self.JavaScript(
            'latLngFromPixel(%d, %d)' % (x, y)).toPyObject()
        for path in eval(str(text)):
            image = self.image_list.get_image(path)
            self._add_marker(image, lat, lng)
            self._set_metadata(image, lat, lng)
        self.display_coords()
        self.see_selection()

    def new_coords(self):
        text = str(self.coords.text()).strip()
        if not text:
            for image in self.image_list.get_selected_images():
                image.metadata.del_item('latlong')
            self.JavaScript('delMarker("%s")' % (image.path))
            return
        lat, lng = map(float, text.split(','))
        for image in self.image_list.get_selected_images():
            self._set_metadata(image, lat, lng)
            self._add_marker(image, lat, lng)
        self.display_coords()
        self.see_selection()

    def see_all(self):
        marker_list = list()
        for image in self.image_list.get_images():
            marker_list.append(image.path)
        if marker_list:
            self.JavaScript('seeMarkers(%s)' % str(marker_list))

    def see_selection(self):
        marker_list = list()
        for image in self.image_list.get_selected_images():
            marker_list.append(image.path)
        if marker_list:
            self.JavaScript('seeMarkers(%s)' % str(marker_list))

    def display_coords(self):
        coords = None
        for image in self.image_list.get_selected_images():
            latlong = image.metadata.get_item('latlong')
            if latlong.empty():
                new_coords = None
            else:
                new_coords = latlong.value
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
            latlong = image.metadata.get_item('latlong')
            if not latlong.empty():
                self.JavaScript(
                    'enableMarker("%s", %d)' % (image.path, image.selected))
        self.display_coords()
        self.see_selection()

    def new_images(self):
        self.JavaScript('removeMarkers()')
        for image in self.image_list.get_images():
            latlong = image.metadata.get_item('latlong')
            if not latlong.empty():
                self._add_marker(image, *latlong.value)

    def _add_marker(self, image, lat, lng):
        if not self.map_loaded:
            return
        if lat is None or lng is None:
            return
        self.JavaScript('addMarker("%s", %s, %s, "%s", %d)' % (
            image.path, repr(lat), repr(lng), image.name, image.selected))

    def search(self, search_string=None):
        if not search_string:
            search_string = self.edit_box.lineEdit().text()
            self.edit_box.clearEditText()
        if not search_string:
            return
        self.search_string = search_string
        self.clear_search()
        self.location = dict()
        self.JavaScript('search("%s")' % (search_string))

    def clear_search(self):
        self.edit_box.clear()
        self.edit_box.addItem('')
        if self.search_string:
            self.edit_box.addItem('<repeat search>')

    @QtCore.pyqtSlot(float, float, unicode)
    def search_result(self, lat, lng, name):
        self.edit_box.addItem(name)
        self.location[unicode(name)] = lat, lng
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
        name = unicode(self.edit_box.itemText(idx))
        if name in self.location:
            lat, lng = self.location[name]
            self.JavaScript('goTo(%s, %s)' % (repr(lat), repr(lng)))

    @QtCore.pyqtSlot(str)
    def marker_click(self, path):
        self.image_list.select_image(str(path))

    @QtCore.pyqtSlot(float, float, str)
    def marker_drag_end(self, lat, lng, path):
        image = self.image_list.get_image(str(path))
        self._set_metadata(image, lat, lng)
        self.display_coords()
        self.see_selection()

    def _set_metadata(self, image, lat, lng):
        image.metadata.set_item('latlong', (lat, lng))

    def JavaScript(self, command):
        if self.map_loaded:
            return self.map.page().mainFrame().evaluateJavaScript(command)
        return None
