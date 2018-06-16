##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2018  Jim Easterbrook  jim@jim-easterbrook.me.uk
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


class MapboxMap(PhotiniMap):
    def get_head(self):
        return '''
    <script type="text/javascript"
      src="https://api.mapbox.com/mapbox.js/v3.1.1/mapbox.js">
    </script>
    <link rel="stylesheet"
      href="https://api.mapbox.com/mapbox.js/v3.1.1/mapbox.css" />
    <script type="text/javascript">
      window.addEventListener('load', initialize);
    </script>
    <script type="text/javascript" src="../openstreetmap/common.js" async>
    </script>
'''
