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

from datetime import timedelta
import logging
import os

import gpxpy
# See https://pypi.org/project/gpxpy/

from photini.pyqt import QtCore, QtWidgets


logger = logging.getLogger(__name__)


class GpxImporter(QtCore.QObject):
    def __init__(self, *args, **kwds):
        super(GpxImporter, self).__init__(*args, **kwds)
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.clear_data()

    def clear_data(self):
        self.points = []

    def import_file(self):
        # get file path
        args = [
            self.parent(),
            self.tr('Import GPX file'),
            self.config_store.get('paths', 'gpx', ''),
            self.tr("GPX files (*.gpx *.GPX *.Gpx);;All files (*)")
            ]
        if not self.config_store.get('pyqt', 'native_dialog', True):
            args += [None, QtWidgets.QFileDialog.DontUseNativeDialog]
        path = QtWidgets.QFileDialog.getOpenFileName(*args)
        path = path[0]
        if not path:
            return []
        self.config_store.set(
            'paths', 'gpx', os.path.dirname(os.path.abspath(path)))
        # make a list of points in the file
        result = []
        for p in self.read_file(path):
            time_stamp = p.time
            if time_stamp.tzinfo is not None:
                # convert timestamp to UTC
                utc_offset = time_stamp.utcoffset()
                time_stamp = (time_stamp - utc_offset).replace(tzinfo=None)
            # add point to list
            result.append((time_stamp, p.latitude, p.longitude))
        if not result:
            logger.warning('No points found in file "%s"', path)
            return []
        result.sort(key=lambda x: x[0])
        # store new points
        for point in result:
            time_stamp, lat, lng = point
            if point not in self.points:
                self.points.append(point)
        self.points.sort(key=lambda x: x[0])
        return result

    def nearest(self, utc_time):
        # return points near utc_time
        threshold = timedelta(minutes=30)
        nearest = threshold
        candidates = []
        # get points within 20 minutes of utc_time
        for point in self.points:
            diff = utc_time - point[0]
            if diff > threshold:
                continue
            diff = abs(diff)
            if diff > threshold:
                break
            candidates.append(point)
            nearest = min(nearest, diff)
        # prune list down to 3 or fewer
        while len(candidates) > 3:
            before = utc_time - candidates[0][0]
            after = candidates[-1][0] - utc_time
            if before > after:
                candidates = candidates[1:]
            else:
                candidates = candidates[:-1]
        return candidates

    def read_file(self, path):
        with open(path) as gpx_file:
            gpx = gpxpy.parse(gpx_file)
            if not gpx.has_times():
                logger.error('no time stamps in %s', os.path.basename(path))
                return
            gpx.reduce_points(max_points_no=1000, min_distance=25.0)
            for point in gpx.walk(only_points=True):
                yield point
