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

from photini.pyqt import QtCore, QtWidgets


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
        else:
            args += [None, QtWidgets.QFileDialog.DontUseNativeDialog]
        path = QtWidgets.QFileDialog.getOpenFileName(*args)
        path = path[0]
        if not path:
            return
        parent.app.config_store.set(
            'paths', 'gpx', os.path.dirname(os.path.abspath(path)))
        # get user options
        config_store = QtWidgets.QApplication.instance().config_store
        dialog = QtWidgets.QDialog(parent=parent)
        dialog.setWindowTitle(self.tr('GPX options'))
        dialog.setLayout(QtWidgets.QFormLayout())
        max_interval = QtWidgets.QSpinBox()
        max_interval.setRange(60, 300)
        max_interval.setValue(
            int(config_store.get('gpx_importer', 'interval', '120')))
        max_interval.setSuffix(self.tr(' secs'))
        dialog.layout().addRow(self.tr('Max time between points'), max_interval)
        max_dilution = QtWidgets.QDoubleSpinBox()
        max_dilution.setRange(1.0, 100.0)
        max_dilution.setValue(
            float(config_store.get('gpx_importer', 'dilution', '2.5')))
        max_dilution.setSingleStep(0.1)
        dialog.layout().addRow(
            self.tr('Max dilution of precision'), max_dilution)
        if hasattr(parent.tabs.currentWidget(), 'plot_track'):
            plot_track = QtWidgets.QCheckBox()
            plot_track.setChecked(
                bool(config_store.get('gpx_importer', 'plot', 'True')))
            dialog.layout().addRow(self.tr('Plot track on map'), plot_track)
        else:
            plot_track = False
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        dialog.layout().addWidget(button_box)
        dialog.exec_()
        max_interval = max_interval.value()
        max_dilution = max_dilution.value()
        config_store.set('gpx_importer', 'interval', max_interval)
        config_store.set('gpx_importer', 'dilution', max_dilution)
        if plot_track:
            plot_track = plot_track.isChecked()
            config_store.set('gpx_importer', 'plot', plot_track)
        # make a list of all points in the file
        points = []
        discards = 0
        for p in self.read_file(path):
            if p.horizontal_dilution and p.horizontal_dilution > max_dilution:
                discards += 1
                continue
            time_stamp = p.time
            if time_stamp.tzinfo is not None:
                # convert timestamp to UTC
                utc_offset = time_stamp.utcoffset()
                time_stamp = (time_stamp - utc_offset).replace(tzinfo=None)
            # add point to list
            points.append((time_stamp, p.latitude, p.longitude))
        if discards:
            logger.warning('Discarded %d low accuracy points', discards)
        if not points:
            logger.warning('No points found in file "%s"', path)
            return
        logger.warning('Using %d points', len(points))
        # sort points by timestamp
        points.sort(key=lambda x: x[0])
        # display on map
        if plot_track:
            # divide points into contiguous tracks
            tracks = []
            t = []
            for p in points:
                if t and (p[0] - t[-1][0]).total_seconds() > max_interval:
                    tracks.append(t)
                    t = []
                t.append(p)
            if t:
                tracks.append(t)
            parent.tabs.currentWidget().plot_track(tracks)
        # set image coordinates
        max_interval = max_interval / 2.0
        for image in parent.image_list.get_selected_images():
            if not image.metadata.date_taken:
                continue
            time_stamp = image.metadata.date_taken.to_utc()
            if len(points) < 2:
                lo, hi = 0, 0
            elif time_stamp < points[0][0]:
                lo, hi = 0, 1
            elif time_stamp > points[-1][0]:
                lo, hi = -2, -1
            else:
                # binary search for points with nearest timestamps
                lo, hi = 0, len(points) - 1
                while hi - lo > 1:
                    mid = (lo + hi) // 2
                    if time_stamp >= points[mid][0]:
                        lo = mid
                    elif time_stamp <= points[mid][0]:
                        hi = mid
            # use linear interpolation (or extrapolation) to set lat & long
            dt_lo = (time_stamp - points[lo][0]).total_seconds()
            dt_hi = (time_stamp - points[hi][0]).total_seconds()
            if abs(dt_lo) > max_interval and abs(dt_hi) > max_interval:
                logger.info('No point for time %s', image.metadata.date_taken)
                continue
            if dt_lo == dt_hi:
                beta = 0.5
            else:
                beta = dt_lo / (dt_lo - dt_hi)
            lat = points[lo][1] + (beta * (points[hi][1] - points[lo][1]))
            lng = points[lo][2] + (beta * (points[hi][2] - points[lo][2]))
            image.metadata.latlong = lat, lng
        parent.image_list.emit_selection()

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
