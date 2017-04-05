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
    multiple_values, Qt, QtCore, QtGui, QtWebChannel, QtWebEngineWidgets,
    QtWebKitWidgets, QtWidgets)

translate = QtCore.QCoreApplication.translate

if QtWebEngineWidgets:
    WebPageBase = QtWebEngineWidgets.QWebEnginePage
    WebViewBase = QtWebEngineWidgets.QWebEngineView
else:
    WebPageBase = QtWebKitWidgets.QWebPage
    WebViewBase = QtWebKitWidgets.QWebView

class WebPage(WebPageBase):
    def __init__(self, parent=None):
        super(WebPage, self).__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)

    def javaScriptConsoleMessage(self, msg, line, source):
        if msg.startswith("Consider using 'dppx' units instead of 'dpi'"):
            return
        self.logger.error('%s line %d: %s', source, line, msg)


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


class PhotiniMap(QtWidgets.QWidget):
    def __init__(self, image_list, parent=None):
        super(PhotiniMap, self).__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.app = QtWidgets.QApplication.instance()
        self.config_store = self.app.config_store
        self.image_list = image_list
        self.multiple_values = multiple_values()
        self.script_dir = pkg_resources.resource_filename(
            'photini', 'data/' + self.__class__.__name__.lower() + '/')
        self.drag_icon = QtGui.QPixmap(
            os.path.join(self.script_dir, 'grey_marker.png'))
        self.search_string = None
        self.map_loaded = False
        self.marker_images = {}
        self.map_status = {}
        layout = QtWidgets.QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setRowStretch(6, 1)
        layout.setColumnStretch(1, 1)
        self.setLayout(layout)
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
        self.layout().addWidget(self.map, 0, 1, 8, 1)
        # search
        self.layout().addWidget(
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
        self.layout().addWidget(self.edit_box, 1, 0)
        # latitude & longitude
        self.layout().addWidget(
            QtWidgets.QLabel(translate('PhotiniMap', 'Latitude, longitude:')), 2, 0)
        self.coords = QtWidgets.QLineEdit()
        self.coords.editingFinished.connect(self.new_coords)
        self.coords.setEnabled(False)
        self.layout().addWidget(self.coords, 3, 0)
        # load map button
        self.load_map = QtWidgets.QPushButton(translate('PhotiniMap', '\nLoad map\n'))
        self.load_map.clicked.connect(self.initialise)
        self.layout().addWidget(self.load_map, 7, 0)
        # other init
        self.image_list.image_list_changed.connect(self.image_list_changed)

    @QtCore.pyqtSlot(int, six.text_type)
    def log(self, level, message):
        self.logger.log(level, message)

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
      var initData = {data};
    </script>
{body}
  </body>
</html>
'''
        lat, lng = eval(self.config_store.get('map', 'centre', '(51.0, 0.0)'))
        zoom = eval(self.config_store.get('map', 'zoom', '11'))
        data = {'lat': lat, 'lng': lng, 'zoom': zoom}
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
        page = page.format(
            data=str(data), initialize=initialize, **self.get_page_elements())
        QtWidgets.QApplication.setOverrideCursor(Qt.WaitCursor)
        self.map.setHtml(page, QtCore.QUrl.fromLocalFile(self.script_dir))

    @QtCore.pyqtSlot()
    def initialize_finished(self):
        QtWidgets.QApplication.restoreOverrideCursor()
        self.map_loaded = True
        self.layout().removeWidget(self.load_map)
        self.load_map.setParent(None)
        show_terms = QtWidgets.QVBoxLayout()
        for widget in self.show_terms():
            widget.setStyleSheet('QPushButton, QLabel { font-size: 10px }')
            show_terms.addWidget(widget)
        self.layout().addLayout(show_terms, 7, 0)
        self.edit_box.setEnabled(True)
        self.map.setAcceptDrops(True)
        self.image_list_changed()
        self.image_list.set_drag_to_map(self.drag_icon)

    def refresh(self):
        if not self.map_loaded:
            return
        lat, lng = eval(self.config_store.get('map', 'centre'))
        zoom = eval(self.config_store.get('map', 'zoom'))
        self.JavaScript(
            'setView({0}, {1}, {2:d})'.format(repr(lat), repr(lng), zoom))
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
        self.JavaScript('markerDrop({:d},{:d},{:s})'.format(x, y, text))

    @QtCore.pyqtSlot(float, float, QtCore.QVariant)
    def marker_drop(self, lat, lng, path_list):
        for path in path_list:
            image = self.image_list.get_image(path)
            self._remove_image(image)
            self._set_metadata(image, lat, lng)
            self._add_image(image)
        self.display_coords()
        self.see_selection()

    @QtCore.pyqtSlot()
    def new_coords(self):
        text = self.coords.text().strip()
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

    def display_coords(self):
        images = self.image_list.get_selected_images()
        if not images:
            self.coords.clear()
            return
        latlong = images[0].metadata.latlong
        for image in images[1:]:
            if image.metadata.latlong != latlong:
                self.coords.setText(self.multiple_values)
                return
        if latlong:
            self.coords.setText(str(latlong))
        else:
            self.coords.clear()

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        self.coords.setEnabled(bool(selection))
        for marker_id, images in self.marker_images.items():
            self.JavaScript('enableMarker("{}", {:d})'.format(
                marker_id, any([image.selected for image in images])))
        self.display_coords()
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
                        'enableMarker("{}", {:d})'.format(marker_id, True))
                break
        else:
            for i in range(len(self.marker_images) + 2):
                marker_id = str(i)
                if marker_id not in self.marker_images:
                    break
            self.marker_images[marker_id] = [image]
            self.JavaScript('addMarker("{}", {!r}, {!r}, {:d})'.format(
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
            self.JavaScript('enableMarker("{}", {:d})'.format(
                marker_id,
                any([image.selected for image in self.marker_images[marker_id]])))
        else:
            self.JavaScript('delMarker("{}")'.format(marker_id))
            del self.marker_images[marker_id]

    @QtCore.pyqtSlot()
    def search(self, search_string=None):
        if not search_string:
            search_string = self.edit_box.lineEdit().text()
            self.edit_box.clearEditText()
        if not search_string:
            return
        self.search_string = search_string
        self.clear_search()
        self.JavaScript('search("{0}")'.format(search_string))

    def clear_search(self):
        self.edit_box.clear()
        self.edit_box.addItem('')
        if self.search_string:
            self.edit_box.addItem(translate('PhotiniMap', '<repeat search>'))

    @QtCore.pyqtSlot(float, float, float, float, six.text_type)
    def search_result(self, lat0, lng0, lat1, lng1, name):
        self.edit_box.addItem(name, (lat0, lng0, lat1, lng1))
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

    @QtCore.pyqtSlot(six.text_type)
    def marker_click(self, marker_id):
        self.image_list.select_images(self.marker_images[marker_id])

    @QtCore.pyqtSlot(float, float, six.text_type)
    def marker_drag(self, lat, lng, marker_id):
        for image in self.marker_images[marker_id]:
            self._set_metadata(image, lat, lng)
        self.display_coords()

    def _set_metadata(self, image, lat, lng):
        image.metadata.latlong = lat, lng

    def JavaScript(self, command):
        if self.map_loaded:
            command = command.replace('\\', '\\\\')
            if QtWebEngineWidgets:
                self.map.page().runJavaScript(command)
            else:
                self.map.page().mainFrame().evaluateJavaScript(command)
