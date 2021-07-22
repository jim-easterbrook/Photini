##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2019-21  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import logging
import os

import gpxpy
# See https://pypi.org/project/gpxpy/

from photini.pyqt import QtCore, QtWidgets


logger = logging.getLogger(__name__)


class GpxImporter(QtCore.QObject):
    def import_file(self):
        # get file path
        config_store = QtWidgets.QApplication.instance().config_store
        args = [
            self.parent(),
            self.tr('Import GPX file'),
            config_store.get('paths', 'gpx', ''),
            self.tr("GPX files (*.gpx *.GPX *.Gpx);;All files (*)")
            ]
        if not config_store.get('pyqt', 'native_dialog', True):
            args += [None, QtWidgets.QFileDialog.DontUseNativeDialog]
        path = QtWidgets.QFileDialog.getOpenFileName(*args)
        path = path[0]
        if not path:
            return []
        config_store.set('paths', 'gpx', os.path.dirname(os.path.abspath(path)))
        # make a list of all points in the file
        points = []
        for p in self.read_file(path):
            time_stamp = p.time
            if time_stamp.tzinfo is not None:
                # convert timestamp to UTC
                utc_offset = time_stamp.utcoffset()
                time_stamp = (time_stamp - utc_offset).replace(tzinfo=None)
            # add point to list
            points.append((time_stamp, p.latitude, p.longitude))
        if not points:
            logger.warning('No points found in file "%s"', path)
            return []
        return points

    def read_file(self, path):
        with open(path) as gpx_file:
            gpx = gpxpy.parse(gpx_file)
            for track in gpx.tracks:
                for segment in track.segments:
                    for point in segment.points:
                        yield point
            for route in gpx.routes:
                for point in route.points:
                    yield point
            for point in gpx.waypoints:
                yield point
