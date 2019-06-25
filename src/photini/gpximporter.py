##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2019  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from datetime import datetime, timedelta
import logging
import os

import gpxpy

from photini.pyqt import QtCore, QtWidgets, qt_version_info


logger = logging.getLogger(__name__)


class GpxImporter(QtCore.QObject):
    def do_import(self, parent):
        args = [
            parent,
            self.tr('Import GPX file'),
            parent.app.config_store.get('paths', 'gpx', ''),
            self.tr("GPX files (*.gpx *.GPX *.Gpx);;All files (*)")
            ]
        if eval(parent.app.config_store.get('pyqt', 'native_dialog', 'True')):
            pass
        elif qt_version_info >= (5, 0):
            args += [None, QtWidgets.QFileDialog.DontUseNativeDialog]
        else:
            args += [QtWidgets.QFileDialog.DontUseNativeDialog]
        path = QtWidgets.QFileDialog.getOpenFileName(*args)
        if qt_version_info >= (5, 0):
            path = path[0]
        if not path:
            return
        parent.app.config_store.set('paths', 'gpx', os.path.dirname(path))
        # make a list of all points in the file
        points = []
        for time_stamp, latitude, longitude in self.get_points(path):
            if time_stamp.tzinfo is not None:
                # convert timestamp to UTC
                utc_offset = time_stamp.utcoffset()
                time_stamp = (time_stamp - utc_offset).replace(tzinfo=None)
            # add point to list
            points.append((time_stamp, latitude, longitude))
        if not points:
            logger.warning('No points found in file "%s"', path)
            return
        # sort points by timestamp
        points.sort(key=lambda x: x[0])
        # set image coordinates
        for image in parent.image_list.get_selected_images():
            if not image.metadata.date_taken:
                continue
            time_stamp = image.metadata.date_taken.datetime
            tz_offset = image.metadata.date_taken.tz_offset
            if tz_offset:
                time_stamp -= timedelta(minutes=tz_offset)
            if time_stamp < points[0][0] or time_stamp > points[-1][0]:
                logger.info('No point for time %s', image.metadata.date_taken)
                continue
            # binary search for point with nearest timestamp
            lo, hi = 0, len(points)
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if time_stamp >= points[mid][0]:
                    lo = mid
                elif time_stamp <= points[mid][0]:
                    hi = mid
            mid = points[lo][0] + ((points[hi][0] - points[lo][0]) / 2)
            if time_stamp < mid:
                image.metadata.latlong = points[lo][1:]
            else:
                image.metadata.latlong = points[hi][1:]
        parent.image_list.emit_selection()

    def get_points(self, path):
        with open(path) as gpx_file:
            gpx = gpxpy.parse(gpx_file)
            for track in gpx.tracks:
                for segment in track.segments:
                    for point in segment.points:
                        yield point.time, point.latitude, point.longitude
            for route in gpx.routes:
                for point in route.points:
                    yield point.time, point.latitude, point.longitude
            for point in gpx.waypoints:
                yield point.time, point.latitude, point.longitude
