##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2019-23  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
translate = QtCore.QCoreApplication.translate


class GpxImporter(QtCore.QObject):
    def __init__(self, *args, **kwds):
        super(GpxImporter, self).__init__(*args, **kwds)
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.clear_data()

    def clear_data(self):
        self.display_points = []
        self.gpx = {}

    def import_file(self):
        # get file path
        args = [
            self.parent(),
            translate('GpxImporter', 'Import GPX file'),
            self.config_store.get('paths', 'gpx', ''),
            translate('GpxImporter',
                      "GPX files (*.gpx *.GPX *.Gpx);;All files (*)")
            ]
        if not self.config_store.get('pyqt', 'native_dialog', True):
            args += [None, QtWidgets.QFileDialog.Option.DontUseNativeDialog]
        path = QtWidgets.QFileDialog.getOpenFileName(*args)
        path = path[0]
        if not path:
            return []
        path = os.path.abspath(path)
        self.config_store.set('paths', 'gpx', os.path.dirname(path))
        # open and read GPX file
        with open(path) as gpx_file:
            gpx = gpxpy.parse(gpx_file)
        if not gpx.get_points_no():
            logger.error('No points in file "%s"', os.path.basename(path))
            return []
        if not gpx.has_times():
            logger.error('No time stamps in file "%s"', os.path.basename(path))
            return []
        self.gpx[path] = gpx
        # make a list of points to display, which may be a subset of a
        # large file
        reduced_gpx = self.gpx[path].clone()
        reduced_gpx.reduce_points(max_points_no=500, min_distance=25.0)
        result = []
        for p in reduced_gpx.walk(only_points=True):
            time_stamp = p.time
            if time_stamp.tzinfo is not None:
                # convert timestamp to UTC
                utc_offset = time_stamp.utcoffset()
                time_stamp = (time_stamp - utc_offset).replace(tzinfo=None)
            # add point to list
            point = time_stamp, p.latitude, p.longitude
            if point not in self.display_points:
                self.display_points.append(point)
            result.append(point)
        self.display_points.sort(key=lambda x: x[0])
        return result

    def get_locations_at(self, utc_time):
        # return track point(s) nearest given time stamp
        result = []
        for gpx in self.gpx.values():
            for location in gpx.get_location_at(utc_time):
                if abs(location.time - utc_time).total_seconds() < 60:
                    result.append(location)
        return result

    def nearest(self, utc_time):
        # return points near utc_time
        # find bounding points by binary search
        lo, hi = 0, len(self.display_points) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if utc_time < self.display_points[mid][0]:
                hi = mid
            else:
                lo = mid
        # expand range to 4 points, if possible
        if lo > 0:
            lo -= 1
        if hi < len(self.display_points) - 1:
            hi += 1
        # remove points too far away in time
        threshold = timedelta(seconds=60)
        while lo <= hi and utc_time - self.display_points[lo][0] > threshold:
            lo += 1
        while lo <= hi and self.display_points[hi][0] - utc_time > threshold:
            hi -= 1
        return self.display_points[lo:hi+1]
