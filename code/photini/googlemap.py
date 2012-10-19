# -*- coding: utf-8 -*-
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

import webbrowser

from PyQt4 import QtGui

from photinimap import PhotiniMap

class GoogleMap(PhotiniMap):
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
      src="http://maps.googleapis.com/maps/api/js?key=%s&sensor=false">
    </script>
    <script type="text/javascript" src="googlemap.js">
    </script>
  </head>
  <body onload="initialize(%f, %f, %d)">
    <div id="map_canvas" style="width:100%%; height:100%%"></div>
  </body>
</html>
"""
    api_key = 'AIzaSyBPUg_kKGYxyzV0jV7Gg9m4rxme97tE13Y'
    def __init__(self, config_store, image_list, parent=None):
        # setting the application name & version stops Google maps
        # using the multitouch interface
        app = QtGui.QApplication.instance()
        app.setApplicationName('chrome')
        app.setApplicationVersion('1.0')
        PhotiniMap.__init__(self, config_store, image_list, parent)

    def show_terms(self):
        # return a widget to display map terms and conditions
        result = QtGui.QFrame()
        layout = QtGui.QVBoxLayout()
        result.setLayout(layout)
        layout.addWidget(QtGui.QLabel('Search powered by Google'))
        load_tou = QtGui.QPushButton('Terms of Use')
        load_tou.clicked.connect(self.load_tou)
        layout.addWidget(load_tou)
        return result

    def load_tou(self):
        webbrowser.open_new('http://www.google.com/help/terms_maps.html')
