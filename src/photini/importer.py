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

from __future__ import unicode_literals

from datetime import datetime
import logging
import os
import re
import sys

import gphoto2 as gp
from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt

from .configstore import ConfigStore
from .utils import Busy

class CameraHandler(QtCore.QObject):
    new_camera_list = QtCore.pyqtSignal(list)
    new_camera = QtCore.pyqtSignal(str)
    def __init__(self, parent=None):
        QtCore.QObject.__init__(self, parent)
        self.context = gp.Context()
        self.camera = None
        self.cam_model = ''
        self.cam_port_name = None

    @QtCore.pyqtSlot()
    def get_camera_list(self):
        with gp.CameraList() as cameras:
            cam_count = self.context.camera_autodetect(cameras.list)
            camera_list = []
            for n in range(cam_count):
                name = cameras.get_name(n)
                addr = cameras.get_value(n)
                camera_list.append((name, addr))
        camera_list.sort(key=lambda x: x[0])
        self.new_camera_list.emit(camera_list)

    @QtCore.pyqtSlot(str, str)
    def select_camera(self, model, port_name):
        # free any existing camera
        if self.camera:
            self.camera.exit()
            self.camera.cleanup()
            self.camera = None
        # initialise camera
        self.camera = gp.Camera(self.context.context)
        # search abilities for camera model
        with gp.CameraAbilitiesList() as abilities_list:
            abilities_list.load(self.context.context)
            idx = abilities_list.lookup_model(str(model))
            abilities = gp.CameraAbilities()
            abilities_list.get_abilities(idx, abilities)
            self.camera.set_abilities(abilities)
        # search ports for camera port name
        with gp.PortInfoList() as port_info_list:
            port_info_list.load()
            idx = port_info_list.lookup_path(str(port_name))
            # port_info is a pointer to an entry in port_info_list, so
            # don't free port_info_list until after port_info has been
            # used
            port_info = port_info_list.get_info(idx)
            self.camera.set_port_info(port_info)
        self.cam_model = model
        self.cam_port_name = port_name
        try:
            self.camera.init()
        except gp.GPhoto2Error:
            self.camera.cleanup()
            self.camera = None
            self.cam_model = ''
            self.cam_port_name = None
            self.get_camera_list()
        self.new_camera.emit(self.cam_model)

    def list_files(self, path='/'):
        if not self.camera:
            return []
        result = []
        with gp.CameraList() as gp_list:
            # get files
            self.camera.folder_list_files(str(path), gp_list.list)
            for n in range(gp_list.count()):
                result.append(os.path.join(path, gp_list.get_name(n)))
            # read folders
            folders = []
            gp_list.reset()
            self.camera.folder_list_folders(str(path), gp_list.list)
            for n in range(gp_list.count()):
                folders.append(gp_list.get_name(n))
        # recurse over subfolders
        for name in folders:
            result.extend(self.list_files(os.path.join(path, name)))
        return result

    def get_file_info(self, path):
        folder, name = os.path.split(path)
        info = gp.CameraFileInfo()
        self.camera.file_get_info(str(folder), str(name), info)
        return info

    def copy_file(self, folder, name, dest):
        with gp.CameraFile() as camera_file:
            self.camera.file_get(
                str(folder), str(name), gp.GP_FILE_TYPE_NORMAL, camera_file.file)
            camera_file.save(dest)

class CameraSelector(QtGui.QWidget):
    select_camera = QtCore.pyqtSignal(str, str)
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.setLayout(QtGui.QHBoxLayout())
        self.layout().setMargin(0)
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
        port_name = self.cam_list.itemData(idx)
        if sys.version_info[0] < 3:
            port_name = port_name.toString()
        if port_name:
            model = self.cam_list.itemText(idx)
            if model != self.current_cam:
                self.select_camera.emit(model, port_name)
                return
        self._show_current()

    def _show_current(self):
        self.cam_list.setCurrentIndex(
            max(0, self.cam_list.findText(self.current_cam)))

class NameMangler(QtCore.QObject):
    number_parser = re.compile('\D*(\d+)')
    new_example = QtCore.pyqtSignal(str)
    def __init__(self, parent=None):
        QtCore.QObject.__init__(self, parent)
        self.example = None
        self.format_string = None

    @QtCore.pyqtSlot(str)
    def new_format(self, format_string):
        format_string = str(format_string)
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
        self.refresh_example()

    def set_example(self, name, timestamp):
        self.example = name, timestamp
        self.refresh_example()

    def refresh_example(self):
        if self.format_string and self.example:
            self.new_example.emit(self.transform(*self.example))

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

class Importer(QtGui.QWidget):
    def __init__(self, config_store, image_list, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.config_store = config_store
        self.image_list = image_list
        self.setLayout(QtGui.QGridLayout())
        form = QtGui.QFormLayout()
        form.setFieldGrowthPolicy(QtGui.QFormLayout.AllNonFixedFieldsGrow)
        self.app = QtGui.QApplication.instance()
        self.ch = CameraHandler()
        self.nm = NameMangler()
        self.camera = ''
        self.file_data = {}
        self.file_list = []
        self.config_section = 'importer'
        # camera selector
        self.camera_selector = CameraSelector()
        self.camera_selector.scan_for_cameras.connect(self.ch.get_camera_list)
        self.camera_selector.select_camera.connect(self.ch.select_camera)
        self.ch.new_camera_list.connect(self.camera_selector.new_camera_list)
        self.ch.new_camera.connect(self.new_camera)
        form.addRow('Camera', self.camera_selector)
        # path format
        self.path_format = QtGui.QLineEdit()
        self.path_format.textChanged.connect(self.nm.new_format)
        self.path_format.editingFinished.connect(self.path_format_finished)
        form.addRow('Target format', self.path_format)
        # path example
        self.path_example = QtGui.QLabel()
        self.nm.new_example.connect(self.path_example.setText)
        form.addRow('=>', self.path_example)
        self.layout().addLayout(form, 0, 0)
        # file list
        self.file_list_widget = QtGui.QListWidget()
        self.file_list_widget.setSelectionMode(
            QtGui.QAbstractItemView.ExtendedSelection)
        self.layout().addWidget(self.file_list_widget, 1, 0)
        # selection buttons
        buttons = QtGui.QVBoxLayout()
        buttons.addStretch(1)
        select_all = QtGui.QPushButton('Select\nall')
        select_all.clicked.connect(self.select_all)
        buttons.addWidget(select_all)
        select_new = QtGui.QPushButton('Select\nnew')
        select_new.clicked.connect(self.select_new)
        buttons.addWidget(select_new)
        copy_selected = QtGui.QPushButton('Copy\nphotos')
        copy_selected.clicked.connect(self.copy_selected)
        buttons.addWidget(copy_selected)
        self.layout().addLayout(buttons, 0, 1, 2, 1)
        # final initialisation
        self.image_list.sort_order_changed.connect(self.sort_file_list)
        self.path_format.setText(os.path.join(
            os.path.expanduser('~/Pictures'), '%Y/%Y_%m_%d/(name)'))
        self.new_camera('')

    @QtCore.pyqtSlot()
    def path_format_finished(self):
        if self.camera:
            self.config_store.set(
                self.config_section, 'path_format', self.nm.format_string)
        self.show_file_list()

    def refresh(self):
        self.ch.get_camera_list()

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        pass

    @QtCore.pyqtSlot(str)
    def new_camera(self, camera_model):
        self.camera = unicode(camera_model)
        if self.camera:
            self.config_section = 'importer %s' % self.camera
            path_format = unicode(self.path_format.text())
            path_format = self.config_store.get(
                self.config_section, 'path_format', path_format)
            self.path_format.setText(path_format)
        self.camera_selector.camera_changed(camera_model)
##        self.statusBar().showMessage('Getting file list...')
        self.file_list_widget.clear()
        # allow 100ms for display to update before getting file list
        QtCore.QTimer.singleShot(100, self.list_files)

    def list_files(self):
        self.file_data = {}
        with Busy():
            file_list = []
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
##        self.statusBar().clearMessage()
        self.file_list = self.file_data.keys()
        self.sort_file_list()

    def sort_file_list(self):
        if eval(self.config_store.get('controls', 'sort_date', 'False')):
            self.file_list.sort(key=lambda x: self.file_data[x]['timestamp'])
        else:
            self.file_list.sort()
        self.show_file_list()
        if self.file_list:
            name = self.file_list[-1]
            timestamp = self.file_data[name]['timestamp']
        else:
            name = 'IMG_9999.JPG'
            timestamp = datetime.now()
        self.nm.set_example(name, timestamp)

    def show_file_list(self):
        self.file_list_widget.clear()
        first_active = None
        item = None
        for name in self.file_list:
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
            self.file_list_widget.addItem(item)
        if not first_active:
            first_active = item
        self.file_list_widget.scrollToItem(
            first_active, QtGui.QAbstractItemView.PositionAtTop)

    @QtCore.pyqtSlot()
    def select_all(self):
        self.select_files(datetime.min)

    @QtCore.pyqtSlot()
    def select_new(self):
        since = datetime.min
        if self.camera:
            since = datetime.strptime(
                self.config_store.get(
                    self.config_section, 'last_transfer', since.isoformat(b' ')),
                '%Y-%m-%d %H:%M:%S')
        self.select_files(since)

    def select_files(self, since):
        count = self.file_list_widget.count()
        if not count:
            return
        self.file_list_widget.clearSelection()
        first_active = None
        for row in range(count):
            item = self.file_list_widget.item(row)
            if not (item.flags() & Qt.ItemIsSelectable):
                continue
            name = str(item.text()).split()[0]
            timestamp = self.file_data[name]['timestamp']
            if timestamp > since:
                if not first_active:
                    first_active = item
                self.file_list_widget.setItemSelected(item, True)
        if not first_active:
            first_active = item
        self.file_list_widget.scrollToItem(
            first_active, QtGui.QAbstractItemView.PositionAtTop)

    @QtCore.pyqtSlot()
    def copy_selected(self):
        indexes = self.file_list_widget.selectedIndexes()
        if not indexes:
            return
        last_transfer = datetime.min
        count = 0
        with Busy():
            for idx in indexes:
                count += 1
                item = self.file_list_widget.itemFromIndex(idx)
                name = str(item.text()).split()[0]
                timestamp = self.file_data[name]['timestamp']
                dest_path = self.file_data[name]['dest_path']
                src_folder = self.file_data[name]['src_folder']
##                self.statusBar().showMessage(
##                    'Copying %d/%d %s' % (count, len(indexes), dest_path))
                self.app.processEvents()
                dest_dir = os.path.dirname(dest_path)
                if not os.path.isdir(dest_dir):
                    os.makedirs(dest_dir)
                self.ch.copy_file(src_folder, name, dest_path)
                self.image_list.open_file_list([dest_path])
                last_transfer = max(last_transfer, timestamp)
##        self.statusBar().clearMessage()
        self.show_file_list()
        self.config_store.set(
            self.config_section, 'last_transfer', last_transfer.isoformat(b' '))
