##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-18  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import locale

from photini.photinimap import PhotiniMap


class BingMap(PhotiniMap):
    def get_head(self):
        url = 'http://www.bing.com/api/maps/mapcontrol?callback=initialize'
        lang, encoding = locale.getdefaultlocale()
        if lang:
            url += '&mkt={0},ngt'.format(lang.replace('_', '-'))
        else:
            url += '&mkt=ngt'
        if self.app.test_mode:
            url += '&branch=experimental'
        return '''
    <script type="text/javascript"
      src="{}" async>
    </script>
'''.format(url)
