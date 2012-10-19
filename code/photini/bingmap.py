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

from datetime import datetime
import webbrowser

from PyQt4 import QtGui

from photinimap import PhotiniMap

class BingMap(PhotiniMap):
    show_map = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html>
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
    <style type="text/css">
      html { height: 100%% }
      body { height: 100%%; margin: 0; padding: 0 }
      #mapDiv { height: 100%% }
    </style>
    <script charset="UTF-8" type="text/javascript"
      src="http://ecn.dev.virtualearth.net/mapcontrol/mapcontrol.ashx?v=7.0">
    </script>
    <script type="text/javascript">
      var api_key = "%s";
    </script>
    <script type="text/javascript" src="bingmap.js">
    </script>
  </head>
  <body onload="initialize(%f, %f, %d)">
    <div id="mapDiv" style="position:absolute; width:100%%; height:100%%"></div>
  </body>
</html>
"""
    api_key = 'Am_vgc9Dp3K4_oNG79lDkRjaiT0I5vudkGGjLeGM4_REVchob2LFoNoze7lyAL6T'
    def show_terms(self):
        # return a widget to display map terms and conditions
        result = QtGui.QFrame()
        layout = QtGui.QVBoxLayout()
        result.setLayout(layout)
        layout.addWidget(
            QtGui.QLabel(u'©%d Microsoft Corporation' % datetime.now().year))
        layout.addWidget(QtGui.QLabel(u'©%d Nokia' % datetime.now().year))
        load_tou = QtGui.QPushButton('Terms of Use')
        load_tou.clicked.connect(self.load_tou)
        layout.addWidget(load_tou)
        return result

    def load_tou(self):
        webbrowser.open_new(
            'http://www.microsoft.com/maps/assets/docs/terms.aspx')
