##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-19  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from photini.photinimap import PhotiniMap
from photini.pyqt import QtCore


class TabWidget(PhotiniMap):
    api_key = ''

    @staticmethod
    def tab_name():
        return QtCore.QCoreApplication.translate('MapTabOSM', 'Map (&OSM)')

    def get_geocoder(self):
        return self.app.open_cage

    def get_head(self):
        return '''    <link rel="stylesheet"
      href="https://unpkg.com/leaflet@1/dist/leaflet.css" />
    <script type="text/javascript">
      var L_NO_TOUCH = true;
    </script>
    <script type="text/javascript"
      src="https://unpkg.com/leaflet@1/dist/leaflet.js">
    </script>
    <script type="text/javascript" src="common.js"></script>'''
