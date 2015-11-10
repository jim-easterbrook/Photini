#!/usr/bin/env python
# -*- coding: utf-8 -*-

##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-15  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import six
from six.moves.queue import Empty, Queue
import re
import shutil
import sys
import threading

try:
    import gphoto2 as gp
except ImportError:
    gp = None

from .metadata import Metadata
from .pyqt import Busy, image_types, Qt, QtCore, QtGui, QtWidgets, StartStopButton

class FolderSource(object):
    def __init__(self, root):
        super(FolderSource, self).__init__()
        self.root = root
        self.image_types = ['.' + x for x in image_types()]

    def list_files(self):
        result = []
        for root, dirs, files in os.walk(self.root):
            for name in files:
                base, ext = os.path.splitext(name)
                if ext.lower() in self.image_types:
                    result.append(os.path.join(root, name))
        return result

    def get_file_info(self, path):
        metadata = Metadata(path, None)
        timestamp = metadata.date_taken
        if not timestamp:
            timestamp = metadata.date_digitised
        if not timestamp:
            timestamp = metadata.date_modified
        if not timestamp:
            # use file date as last resort
            timestamp = datetime.fromtimestamp(os.path.getmtime(path))
        else:
            timestamp = timestamp.datetime
        folder, name = os.path.split(path)
        return {
            'camera'    : six.text_type(metadata.camera_model),
            'path'      : path,
            'name'      : name,
            'timestamp' : timestamp,
            }

    def copy_file(self, info, dest):
        shutil.copy2(info['path'], dest)
        return None


class CameraSource(object):
    def __init__(self, camera, context):
        self.camera = camera
        self.context = context
        self.camera_model = self.camera.get_abilities().model

    def list_files(self, path='/'):
        result = []
        # get files
        for name, value in self.camera.folder_list_files(path, self.context):
            result.append(os.path.join(path, name))
        # get folders
        folders = []
        for name, value in self.camera.folder_list_folders(path, self.context):
            folders.append(name)
        # recurse over subfolders
        for name in folders:
            result.extend(self.list_files(os.path.join(path, name)))
        return result

    def get_file_info(self, path):
        folder, name = os.path.split(path)
        info = self.camera.file_get_info(str(folder), str(name), self.context)
        timestamp = datetime.utcfromtimestamp(info.file.mtime)
        return {
            'camera'    : self.camera_model,
            'folder'    : folder,
            'name'      : name,
            'timestamp' : timestamp,
            }

    def copy_file(self, info, dest):
        return self.camera.file_get(
            info['folder'], info['name'], gp.GP_FILE_TYPE_NORMAL, self.context)


class CameraLister(QtCore.QObject):
    def __init__(self, parent=None):
        super(CameraLister, self).__init__(parent)
        if gp:
            self.context = gp.Context()
        self.camera = None

    def get_camera_list(self):
        if not gp:
            return []
        camera_list = []
        for name, addr in self.context.camera_autodetect():
            camera_list.append((name, addr))
        camera_list.sort(key=lambda x: x[0])
        return camera_list

    def select_camera(self, port_name):
        # free any existing camera
        if self.camera:
            self.camera.exit(self.context)
            self.camera = None
        # initialise camera
        self.camera = gp.Camera()
        # search ports for camera port name
        port_info_list = gp.PortInfoList()
        port_info_list.load()
        idx = port_info_list.lookup_path(port_name)
        self.camera.set_port_info(port_info_list[idx])
        self.camera.init(self.context)
        return CameraSource(self.camera, self.context)


class NameMangler(QtCore.QObject):
    number_parser = re.compile('\D*(\d+)')
    new_example = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super(NameMangler, self).__init__(parent)
        self.example = None
        self.format_string = None

    @QtCore.pyqtSlot(str)
    def new_format(self, format_string):
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

    def set_example(self, example):
        self.example = example
        self.refresh_example()

    def refresh_example(self):
        if self.format_string and self.example:
            self.new_example.emit(self.transform(self.example))

    def transform(self, file_data):
        name = file_data['name']
        subst = {'name': name}
        match = self.number_parser.match(name)
        if match:
            subst['number'] = match.group(1)
        else:
            subst['number'] = ''
        subst['root'], subst['ext'] = os.path.splitext(name)
        subst['camera'] = file_data['camera'] or 'unknown_camera'
        subst['camera'] = subst['camera'].replace(' ', '_')
        result = ''
        # process (...) parts first
        for left, right in self.parts:
            result += left
            if right in subst:
                result += subst[right]
            else:
                result += right
        # then do timestamp
        return file_data['timestamp'].strftime(result)


class PathFormatValidator(QtGui.QValidator):
    def validate(self, inp, pos):
        if os.path.abspath(inp) == inp:
            return QtGui.QValidator.Acceptable, inp, pos
        return QtGui.QValidator.Intermediate, inp, pos

    def fixup(self, inp):
        return os.path.abspath(inp)


class ImportWorker(QtCore.QObject):
    def __init__(self, source, out_q):
        super(ImportWorker, self).__init__()
        self.source = source
        self.out_q = out_q
        self.thread = QtCore.QThread()
        self.moveToThread(self.thread)

    @QtCore.pyqtSlot(object)
    def import_file(self, item):
        dest_path = item['dest_path']
        dest_dir = os.path.dirname(dest_path)
        if not os.path.isdir(dest_dir):
            os.makedirs(dest_dir)
        try:
            camera_file = self.source.copy_file(item, dest_path)
        except gp.GPhoto2Error:
            self.out_q.put((None, None))
            return
        self.out_q.put((item, camera_file))


class Importer(QtWidgets.QWidget):
    import_file = QtCore.pyqtSignal(object)

    def __init__(self, config_store, image_list, parent=None):
        super(Importer, self).__init__(parent)
        self.config_store = config_store
        self.image_list = image_list
        self.setLayout(QtWidgets.QGridLayout())
        form = QtWidgets.QFormLayout()
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        self.camera_lister = CameraLister()
        self.nm = NameMangler()
        self.file_data = {}
        self.file_list = []
        self.source = None
        self.config_section = None
        self.import_worker = None
        # source selector
        box = QtWidgets.QHBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        self.source_selector = QtWidgets.QComboBox()
        self.source_selector.currentIndexChanged.connect(self.new_source)
        box.addWidget(self.source_selector)
        refresh_button = QtWidgets.QPushButton(self.tr('refresh'))
        refresh_button.clicked.connect(self.refresh)
        box.addWidget(refresh_button)
        box.setStretch(0, 1)
        form.addRow(self.tr('Source'), box)
        # path format
        self.path_format = QtWidgets.QLineEdit()
        self.path_format.setValidator(PathFormatValidator())
        self.path_format.textChanged.connect(self.nm.new_format)
        self.path_format.editingFinished.connect(self.path_format_finished)
        form.addRow(self.tr('Target format'), self.path_format)
        # path example
        self.path_example = QtWidgets.QLabel()
        self.nm.new_example.connect(self.path_example.setText)
        form.addRow('=>', self.path_example)
        self.layout().addLayout(form, 0, 0)
        # file list
        self.file_list_widget = QtWidgets.QListWidget()
        self.file_list_widget.setSelectionMode(
            QtWidgets.QAbstractItemView.ExtendedSelection)
        self.file_list_widget.itemSelectionChanged.connect(self.selection_changed)
        self.layout().addWidget(self.file_list_widget, 1, 0)
        # selection buttons
        buttons = QtWidgets.QVBoxLayout()
        buttons.addStretch(1)
        self.selected_count = QtWidgets.QLabel()
        self.selection_changed()
        buttons.addWidget(self.selected_count)
        select_all = QtWidgets.QPushButton(self.tr('Select\nall'))
        select_all.clicked.connect(self.select_all)
        buttons.addWidget(select_all)
        select_new = QtWidgets.QPushButton(self.tr('Select\nnew'))
        select_new.clicked.connect(self.select_new)
        buttons.addWidget(select_new)
        self.copy_button = StartStopButton(self.tr('Copy\nphotos'),
                                           self.tr('Stop\nimport'))
        self.copy_button.click_start.connect(self.copy_selected)
        buttons.addWidget(self.copy_button)
        self.layout().addLayout(buttons, 0, 1, 2, 1)
        # final initialisation
        self.image_list.sort_order_changed.connect(self.sort_file_list)
        if sys.platform == 'win32':
            import win32com.shell as ws
            path = ws.shell.SHGetFolderPath(
                0, ws.shellcon.CSIDL_MYPICTURES, None, 0)
        else:
            path = os.path.expanduser('~/Pictures')
        self.path_format.setText(
            os.path.join(path, '%Y', '%Y_%m_%d', '(name)'))
        self.refresh()
        self.list_files()

    @QtCore.pyqtSlot(int)
    def new_source(self, idx):
        self.config_section = None
        item_data = self.source_selector.itemData(idx)
        func, param = item_data
        (func)(param)

    def choose_camera(self, params):
        model, port_name = params
        try:
            self.source = self.camera_lister.select_camera(port_name)
        except gp.GPhoto2Error:
            # camera is no longer available
            self._fail()
            return
        self.config_section = 'importer ' + model
        path_format = self.path_format.text()
        path_format = self.config_store.get(
            self.config_section, 'path_format', path_format)
        self.path_format.setText(path_format)
        self.file_list_widget.clear()
        # allow 100ms for display to update before getting file list
        QtCore.QTimer.singleShot(100, self.list_files)

    def add_folder(self, dummy):
        folders = eval(self.config_store.get('importer', 'folders', '[]'))
        if folders:
            directory = folders[0]
        else:
            directory = ''
        root = QtWidgets.QFileDialog.getExistingDirectory(
            self, self.tr("Select root folder"), directory)
        if not root:
            self._fail()
            return
        if root in folders:
            folders.remove(root)
        folders.insert(0, root)
        if len(folders) > 5:
            del folders[-1]
        self.config_store.set('importer', 'folders', repr(folders))
        self.refresh()
        idx = self.source_selector.count() - (1 + len(folders))
        self.source_selector.setCurrentIndex(idx)
##        self.choose_folder(root)

    def choose_folder(self, root):
        if os.path.isdir(root):
            self.source = FolderSource(root)
        else:
            # folder is no longer available
            self._fail()
            return
        self.config_section = 'importer folder ' + root
        path_format = self.path_format.text()
        path_format = self.config_store.get(
            self.config_section, 'path_format', path_format)
        self.path_format.setText(path_format)
        self.file_list_widget.clear()
        # allow 100ms for display to update before getting file list
        QtCore.QTimer.singleShot(100, self.list_files)

    @QtCore.pyqtSlot()
    def path_format_finished(self):
        if self.config_section:
            self.config_store.set(
                self.config_section, 'path_format', self.nm.format_string)
        self.show_file_list()

    @QtCore.pyqtSlot()
    def refresh(self):
        was_blocked = self.source_selector.blockSignals(True)
        # save current selection
        idx = self.source_selector.currentIndex()
        if idx >= 0:
            item_data = self.source_selector.itemData(idx)
            func, param = item_data
        else:
            func, param = None, None
        # rebuild list
        self.source_selector.clear()
        self.source_selector.addItem(
            self.tr('<select source>'), (self._new_file_list, {}))
        cameras = self.camera_lister.get_camera_list()
        for model, port_name in cameras:
            self.source_selector.addItem(
                self.tr('camera: {0}').format(model),
                (self.choose_camera, (model, port_name)))
        folders = eval(self.config_store.get('importer', 'folders', '[]'))
        for root in folders:
            if os.path.isdir(root):
                self.source_selector.addItem(
                    self.tr('folder: {0}').format(root),
                    (self.choose_folder, root))
        self.source_selector.addItem(
            self.tr('<add a folder>'), (self.add_folder, None))
        # restore saved selection
        new_idx = -1
        for idx in range(self.source_selector.count()):
            item_data = self.source_selector.itemData(idx)
            if item_data == (func, param):
                new_idx = idx
                self.source_selector.setCurrentIndex(idx)
                break
        self.source_selector.blockSignals(was_blocked)
        if new_idx < 0:
            self.source_selector.setCurrentIndex(0)

    def do_not_close(self):
        if not self.import_worker:
            return False
        dialog = QtWidgets.QMessageBox()
        dialog.setWindowTitle(self.tr('Photini: import in progress'))
        dialog.setText(self.tr('<h3>Importing photos has not finished.</h3>'))
        dialog.setInformativeText(
            self.tr('Closing now will terminate the import.'))
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        dialog.setStandardButtons(
            QtWidgets.QMessageBox.Close | QtWidgets.QMessageBox.Cancel)
        dialog.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        result = dialog.exec_()
        return result == QtWidgets.QMessageBox.Cancel

    def shutdown(self):
        if self.import_worker:
            self.import_worker.thread.quit()
            self.import_worker.thread.wait()

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        pass

    def list_files(self):
        file_data = {}
        if self.source:
            with Busy():
                try:
                    file_list = self.source.list_files()
                except gp.GPhoto2Error:
                    # camera is no longer visible
                    self._fail()
                    return
                for path in file_list:
                    try:
                        info = self.source.get_file_info(path)
                    except gp.GPhoto2Error:
                        self._fail()
                        return
                    file_data[info['name']] = info
        self._new_file_list(file_data)

    def _fail(self):
        self.source_selector.setCurrentIndex(0)
        self.refresh()

    def _new_file_list(self, file_data):
        self.file_list = list(file_data.keys())
        self.file_data = file_data
        self.sort_file_list()

    def sort_file_list(self):
        if eval(self.config_store.get('controls', 'sort_date', 'False')):
            self.file_list.sort(key=lambda x: self.file_data[x]['timestamp'])
        else:
            self.file_list.sort()
        self.show_file_list()
        if self.file_list:
            example = self.file_data[self.file_list[-1]]
        else:
            example = {
                'camera'    : None,
                'name'      : 'IMG_9999.JPG',
                'timestamp' : datetime.now(),
                }
        self.nm.set_example(example)

    def show_file_list(self):
        self.file_list_widget.clear()
        first_active = None
        item = None
        for name in self.file_list:
            file_data = self.file_data[name]
            dest_path = self.nm.transform(file_data)
            file_data['dest_path'] = dest_path
            item = QtWidgets.QListWidgetItem(name + ' -> ' + dest_path)
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
            first_active, QtWidgets.QAbstractItemView.PositionAtTop)

    @QtCore.pyqtSlot()
    def selection_changed(self):
        count = len(self.file_list_widget.selectedItems())
        self.selected_count.setText(self.tr('%n file(s)\nselected', '', count))

    @QtCore.pyqtSlot()
    def select_all(self):
        self.select_files(datetime.min)

    @QtCore.pyqtSlot()
    def select_new(self):
        since = datetime.min
        if self.config_section:
            since = self.config_store.get(
                self.config_section, 'last_transfer', since.isoformat(' '))
            if len(since) > 19:
                since = datetime.strptime(since, '%Y-%m-%d %H:%M:%S.%f')
            else:
                since = datetime.strptime(since, '%Y-%m-%d %H:%M:%S')
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
            name = item.text().split()[0]
            timestamp = self.file_data[name]['timestamp']
            if timestamp > since:
                if not first_active:
                    first_active = item
                item.setSelected(True)
        if not first_active:
            first_active = item
        self.file_list_widget.scrollToItem(
            first_active, QtWidgets.QAbstractItemView.PositionAtTop)

    @QtCore.pyqtSlot()
    def copy_selected(self):
        if self.import_worker:
            # user has clicked while upload is still cancelling
            self.copy_button.setChecked(False)
            return
        copy_list = []
        for item in self.file_list_widget.selectedItems():
            name = item.text().split()[0]
            copy_list.append(self.file_data[name])
        if not copy_list:
            self.copy_button.setChecked(False)
            return
        # create separate thread to import images
        item_queue = Queue()
        self.import_worker = ImportWorker(self.source, item_queue)
        self.import_file.connect(self.import_worker.import_file)
        self.import_worker.thread.start()
        last_transfer = datetime.min
        last_path = None
        self.import_file.emit(copy_list.pop(0))
        while self.copy_button.isChecked():
            QtWidgets.QApplication.processEvents()
            if not self.import_worker.thread.isRunning():
                # user has closed program
                return
            if item_queue.empty():
                continue
            item, camera_file = item_queue.get()
            if item is None:
                # import failed
                self._fail()
                break
            timestamp = item['timestamp']
            dest_path = item['dest_path']
            if last_transfer < timestamp:
                last_transfer = timestamp
                last_path = dest_path
            if copy_list:
                # start fetching next file
                self.import_file.emit(copy_list[0])
            if camera_file:
                camera_file.save(dest_path)
            self.image_list.open_file(dest_path)
            if not copy_list:
                break
            copy_list.pop(0)
        if last_path:
            self.config_store.set(self.config_section, 'last_transfer',
                                  last_transfer.isoformat(' '))
            self.image_list.done_opening(last_path)
        self.show_file_list()
        self.import_file.disconnect()
        self.import_worker.thread.quit()
        self.import_worker.thread.wait()
        self.import_worker = None
        self.copy_button.setChecked(False)
