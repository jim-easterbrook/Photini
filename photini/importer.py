#!/usr/bin/env python

##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-14  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import logging
import os
import re
import sys

import gphoto2 as gp
from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt

from .configstore import ConfigStore

class CameraHandler(QtCore.QObject):
    new_camera_list = QtCore.pyqtSignal(list)
    new_camera = QtCore.pyqtSignal(str)
    def __init__(self):
        QtCore.QObject.__init__(self)
        self.context = gp.gp_context_new()
        self.camera = None
        self.cam_model = ''
        self.cam_port_name = None

    @QtCore.pyqtSlot()
    def get_camera_list(self):
        cameras = gp.check_result(gp.gp_list_new())
        cam_count = gp.check_result(
            gp.gp_camera_autodetect(cameras, self.context))
        camera_list = []
        for n in range(cam_count):
            name = gp.check_result(gp.gp_list_get_name(cameras, n))
            addr = gp.check_result(gp.gp_list_get_value(cameras, n))
            camera_list.append((name, addr))
        gp.check_result(gp.gp_list_unref(cameras))
        camera_list.sort(key=lambda x: x[0])
        self.new_camera_list.emit(camera_list)

    @QtCore.pyqtSlot(str, str)
    def select_camera(self, model, port_name):
        # free any existing camera
        if self.camera:
            gp.check_result(gp.gp_camera_exit(self.camera, self.context))
            gp.check_result(gp.gp_camera_unref(self.camera))
        # search abilities for camera model
        abilities_list = gp.check_result(gp.gp_abilities_list_new())
        gp.check_result(gp.gp_abilities_list_load(abilities_list, self.context))
        idx = gp.check_result(
            gp.gp_abilities_list_lookup_model(abilities_list, str(model)))
        abilities = gp.CameraAbilities()
        gp.check_result(
            gp.gp_abilities_list_get_abilities(abilities_list, idx, abilities))
        gp.check_result(gp.gp_abilities_list_free(abilities_list))
        # search ports for camera port name
        port_info_list = gp.check_result(gp.gp_port_info_list_new())
        gp.check_result(gp.gp_port_info_list_load(port_info_list))
        idx = gp.check_result(
            gp.gp_port_info_list_lookup_path(port_info_list, str(port_name)))
        port_info = gp.check_result(
            gp.gp_port_info_list_get_info(port_info_list, idx))
        # initialise camera
        self.camera = gp.check_result(gp.gp_camera_new())
        gp.check_result(gp.gp_camera_set_abilities(self.camera, abilities))
        gp.check_result(gp.gp_camera_set_port_info(self.camera, port_info))
        self.cam_model = model
        self.cam_port_name = port_name
        # port_info is a pointer to an entry in port_info_list, so
        # don't free it until after port_info has been used
        gp.check_result(gp.gp_port_info_list_free(port_info_list))
        try:
            gp.check_result(gp.gp_camera_init(self.camera, self.context))
        except gp.GPhoto2Error:
            self.camera = None
            self.cam_model = ''
            self.cam_port_name = None
            self.get_camera_list()
        self.new_camera.emit(self.cam_model)

    def list_files(self, path='/'):
        result = []
        gp_list = gp.check_result(gp.gp_list_new())
        # get files
        gp.check_result(gp.gp_camera_folder_list_files(
            self.camera, path, gp_list, self.context))
        for n in range(gp.gp_list_count(gp_list)):
            result.append(os.path.join(
                path, gp.check_result(gp.gp_list_get_name(gp_list, n))))
        # read folders
        folders = []
        gp.check_result(gp.gp_list_reset(gp_list))
        gp.check_result(gp.gp_camera_folder_list_folders(
            self.camera, path, gp_list, self.context))
        for n in range(gp.gp_list_count(gp_list)):
            folders.append(gp.check_result(gp.gp_list_get_name(gp_list, n)))
        gp.gp_list_unref(gp_list)
        # recurse over subfolders
        for name in folders:
            result.extend(self.list_files(os.path.join(path, name)))
        return result

    def get_file_info(self, path):
        folder, name = os.path.split(path)
        info = gp.CameraFileInfo()
        gp.check_result(gp.gp_camera_file_get_info(
            self.camera, folder, name, info, self.context))
        return info

    def copy_file(self, folder, name, dest):
        camera_file = gp.check_result(gp.gp_file_new())
        gp.check_result(gp.gp_camera_file_get(
            self.camera, folder, name, gp.GP_FILE_TYPE_NORMAL,
            camera_file, self.context))
        gp.check_result(gp.gp_file_save(camera_file, dest))
        gp.check_result(gp.gp_file_unref(camera_file))

class CameraSelector(QtGui.QWidget):
    select_camera = QtCore.pyqtSignal(str, str)
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.setLayout(QtGui.QHBoxLayout())
        # camera selector
        self.cam_list = QtGui.QComboBox()
        self.cam_list.activated.connect(self._activated)
        self.layout().addWidget(self.cam_list)
        self.current_cam = ''
        # rescan button
        scan_button = QtGui.QPushButton('rescan')
        self.scan_for_cameras = scan_button.clicked
        self.layout().addWidget(scan_button)
        # make drop down list as wide as possible
        self.layout().setStretch(0, 1)

    @QtCore.pyqtSlot(str)
    def camera_changed(self, model):
        self.current_cam = model
        self._show_current()

    @QtCore.pyqtSlot(list)
    def new_camera_list(self, cameras):
        first_time = self.cam_list.count() == 0
        self.cam_list.setUpdatesEnabled(False)
        self.cam_list.clear()
        self.cam_list.addItem('<select camera>', None)
        for model, port_name in cameras:
            self.cam_list.addItem(model, port_name)
        if first_time and len(cameras) == 1:
            self.select_camera.emit(*cameras[0])
        else:
            self._show_current()
        self.cam_list.setUpdatesEnabled(True)

    @QtCore.pyqtSlot(int)
    def _activated(self, idx):
        if self.cam_list.itemData(idx).isValid():
            model = self.cam_list.itemText(idx)
            port_name = self.cam_list.itemData(idx).toString()
            if model != self.current_cam:
                self.select_camera.emit(model, port_name)
                return
        self._show_current()

    def _show_current(self):
        self.cam_list.setCurrentIndex(
            max(0, self.cam_list.findText(self.current_cam)))

class ConfigPane(QtGui.QWidget):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.setLayout(QtGui.QFormLayout())
        self.layout().setFieldGrowthPolicy(
            QtGui.QFormLayout.AllNonFixedFieldsGrow)
        self.add_row = self.layout().addRow

class NameMangler(object):
    def __init__(self, format_string):
        self.format_string = format_string
        # extract bracket delimited words from string
        self.parts = []
        while format_string:
            parts = format_string.split('(', 1)
            if len(parts) > 1:
                parts[1:] = parts[1].split(')', 1)
            if len(parts) < 3:
                self.parts.append((format_string, ''))
                break
            self.parts.append((parts[0], parts[1]))
            format_string = parts[2]
        self.number_parser = re.compile('\D*(\d+)')

    def transform(self, name, timestamp):
        subst = {'name': name}
        match = self.number_parser.match(name)
        if match:
            subst['number'] = match.group(1)
        else:
            subst['number'] = ''
        subst['root'], subst['ext'] = os.path.splitext(name)
        result = ''
        # process (...) parts first
        for left, right in self.parts:
            result += left
            if right in subst:
                result += subst[right]
            else:
                result += right
        # then do timestamp
        return timestamp.strftime(result)

class MainWindow(QtGui.QMainWindow):
    def __init__(self):
        self.app = QtGui.QApplication.instance()
        self.config = ConfigStore('importer')
        self.ch = CameraHandler()
        self.nm = NameMangler('')
        self.camera = ''
        self.file_data = {}
        QtGui.QMainWindow.__init__(self)
        self.setWindowTitle("Photini image importer")
        self.setMinimumWidth(600)
        self.statusBar()
        # quit shortcut
        quit_action = QtGui.QAction('Quit', self)
        quit_action.setShortcuts(['Ctrl+Q', 'Ctrl+W'])
        quit_action.triggered.connect(self.app.closeAllWindows)
        self.addAction(quit_action)
        # main widget
        central_widget = QtGui.QWidget()
        central_widget.setLayout(QtGui.QFormLayout())
        central_widget.layout().setFieldGrowthPolicy(
            QtGui.QFormLayout.AllNonFixedFieldsGrow)
        self.setCentralWidget(central_widget)
        # camera selector
        self.camera_selector = CameraSelector()
        self.camera_selector.scan_for_cameras.connect(self.ch.get_camera_list)
        self.camera_selector.select_camera.connect(self.ch.select_camera)
        self.ch.new_camera_list.connect(self.camera_selector.new_camera_list)
        self.ch.new_camera.connect(self.new_camera)
        central_widget.layout().addRow('Camera:', self.camera_selector)
        # path format
        self.path_format = QtGui.QLineEdit()
        self.path_format.textChanged.connect(self.path_format_changed)
        self.path_format.editingFinished.connect(self.path_format_finished)
        central_widget.layout().addRow('Target format:', self.path_format)
        # path example
        self.path_example = QtGui.QLabel()
        central_widget.layout().addRow('=>', self.path_example)
        # file list
        self.file_list = QtGui.QListWidget()
        self.file_list.setSelectionMode(
            QtGui.QAbstractItemView.ExtendedSelection)
        central_widget.layout().addRow(self.file_list)
        # selection buttons
        buttons = QtGui.QWidget()
        buttons.setLayout(QtGui.QHBoxLayout())
        select_all = QtGui.QPushButton('select all')
        select_all.clicked.connect(self.select_all)
        buttons.layout().addWidget(select_all)
        select_new = QtGui.QPushButton('select new')
        select_new.clicked.connect(self.select_new)
        buttons.layout().addWidget(select_new)
        copy_selected = QtGui.QPushButton('copy photos')
        copy_selected.clicked.connect(self.copy_selected)
        buttons.layout().addWidget(copy_selected)
        central_widget.layout().addRow(buttons)
        # final initialisation
        self.path_format.setText(os.path.join(
                os.path.expanduser('~/Pictures'), '%Y/%Y_%m_%d/(name)'))
        self.ch.get_camera_list()

    @QtCore.pyqtSlot(str)
    def path_format_changed(self, value):
        self.nm = NameMangler(str(value))
        self.refresh_example()

    def refresh_example(self):
        if self.file_data:
            names = self.file_data.keys()
            names.sort
            name = names[-1]
            timestamp = self.file_data[name]['timestamp']
        else:
            name = 'IMG_9999.JPG'
            timestamp = datetime.now()
        self.path_example.setText(self.nm.transform(name, timestamp))

    @QtCore.pyqtSlot()
    def path_format_finished(self):
        if self.camera:
            self.config.set(self.camera, 'path_format', self.nm.format_string)
        self.show_file_list()

    @QtCore.pyqtSlot(str)
    def new_camera(self, camera_model):
        self.camera = str(camera_model)
        if self.camera:
            path_format = self.config.get(
                self.camera, 'path_format', os.path.join(
                    os.path.expanduser('~/Pictures'), '%Y/%Y_%m_%d/(name)'))
            self.path_format.setText(path_format)
        self.camera_selector.camera_changed(camera_model)
        self.statusBar().showMessage('Getting file list...')
        self.app.setOverrideCursor(Qt.WaitCursor)
        self.file_list.clear()
        # allow 100ms for display to update before getting file list
        QtCore.QTimer.singleShot(100, self.list_files)

    def list_files(self):
        file_list = []
        self.file_data = {}
        try:
            file_list = self.ch.list_files()
        except Exception:
            pass
        for path in file_list:
            folder, name = os.path.split(path)
            info = self.ch.get_file_info(path)
            timestamp = datetime.fromtimestamp(info.file.mtime)
            self.file_data[name] = {
                'src_folder' : folder,
                'timestamp'  : timestamp,
                }
        self.app.restoreOverrideCursor()
        self.statusBar().clearMessage()
        self.show_file_list()
        self.refresh_example()

    def show_file_list(self):
        self.file_list.clear()
        first_active = None
        names = self.file_data.keys()
        names.sort()
        for name in names:
            timestamp = self.file_data[name]['timestamp']
            dest_path = self.nm.transform(name, timestamp)
            self.file_data[name]['dest_path'] = dest_path
            item = QtGui.QListWidgetItem('%s -> %s' % (name, dest_path))
            if os.path.exists(dest_path):
                item.setFlags(Qt.NoItemFlags)
            else:
                if not first_active:
                    first_active = item
                item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.file_list.addItem(item)
        if not first_active:
            first_active = item
        self.file_list.scrollToItem(
            first_active, QtGui.QAbstractItemView.PositionAtTop)

    @QtCore.pyqtSlot()
    def select_all(self):
        self.select_files(datetime.min)

    @QtCore.pyqtSlot()
    def select_new(self):
        since = datetime.min
        if self.camera:
            since = datetime.strptime(
                self.config.get(
                    self.camera, 'last_transfer', since.isoformat(' ')),
                '%Y-%m-%d %H:%M:%S')
        self.select_files(since)

    def select_files(self, since):
        count = self.file_list.count()
        if not count:
            return
        self.file_list.clearSelection()
        first_active = None
        for row in range(count):
            item = self.file_list.item(row)
            if not (item.flags() & Qt.ItemIsSelectable):
                continue
            name = str(item.text()).split()[0]
            timestamp = self.file_data[name]['timestamp']
            if timestamp > since:
                if not first_active:
                    first_active = item
                self.file_list.setItemSelected(item, True)
        if not first_active:
            first_active = item
        self.file_list.scrollToItem(
            first_active, QtGui.QAbstractItemView.PositionAtTop)

    @QtCore.pyqtSlot()
    def copy_selected(self):
        indexes = self.file_list.selectedIndexes()
        if not indexes:
            return
        self.app.setOverrideCursor(Qt.WaitCursor)
        last_transfer = datetime.min
        count = 0
        for idx in indexes:
            count += 1
            item = self.file_list.itemFromIndex(idx)
            name = str(item.text()).split()[0]
            timestamp = self.file_data[name]['timestamp']
            dest_path = self.file_data[name]['dest_path']
            src_folder = self.file_data[name]['src_folder']
            self.statusBar().showMessage(
                'Copying %d/%d %s' % (count, len(indexes), dest_path))
            self.app.processEvents()
            dest_dir = os.path.dirname(dest_path)
            if not os.path.isdir(dest_dir):
                os.makedirs(dest_dir)
            self.ch.copy_file(src_folder, name, dest_path)
            last_transfer = max(last_transfer, timestamp)
        self.app.restoreOverrideCursor()
        self.statusBar().clearMessage()
        self.show_file_list()
        self.config.set(
            self.camera, 'last_transfer', last_transfer.isoformat(' '))

def main():
    logging.basicConfig(
        format='%(levelname)s: %(name)s: %(message)s', level=logging.WARNING)
    gp.check_result(gp.use_python_logging())
    app = QtGui.QApplication(sys.argv)
    main = MainWindow()
    main.show()
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())
