##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-21  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from collections import deque
from contextlib import contextmanager
from datetime import datetime
import logging
import os
import six
import re
import shutil
import sys

try:
    import gphoto2 as gp
except ImportError:
    gp = None

from photini.metadata import Metadata
from photini.pyqt import (
    Busy, catch_all, image_types_lower, Qt, QtCore, QtGui,
    QtSignal, QtSlot, QtWidgets, qt_version_info, StartStopButton,
    video_types_lower)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class FolderSource(object):
    image_types = ['.' + x for x in image_types_lower() + video_types_lower()]

    def __init__(self, root):
        self.root = root

    def get_file_data(self):
        if not os.path.isdir(self.root):
            return None
        file_list = []
        for root, dirs, files in os.walk(self.root):
            # ignore special directories such as .thumbs
            dirs[:] = [x for x in dirs if x[0] != '.']
            for name in files:
                base, ext = os.path.splitext(name)
                if ext.lower() in self.image_types:
                    file_list.append(os.path.join(root, name))
        file_data = {}
        for path in file_list:
            metadata = Metadata(path)
            timestamp = metadata.date_taken
            if not timestamp:
                timestamp = metadata.date_digitised
            if not timestamp:
                timestamp = metadata.date_modified
            if not timestamp:
                # use file date as last resort
                timestamp = datetime.fromtimestamp(os.path.getmtime(path))
            else:
                timestamp = timestamp['datetime']
            sc_path = metadata.find_sidecar()
            name = os.path.basename(path)
            camera = metadata.camera_model
            if camera:
                camera = camera['model']
            file_data[name] = {
                'camera'    : camera,
                'path'      : path,
                'sc_path'   : sc_path,
                'name'      : name,
                'timestamp' : timestamp,
                }
        return file_data

    def copy_files(self, info_list, move):
        for info in info_list:
            dest_path = info['dest_path']
            dest_dir = os.path.dirname(dest_path)
            if not os.path.isdir(dest_dir):
                os.makedirs(dest_dir)
            sc_file = info['sc_path']
            if move:
                shutil.move(info['path'], dest_path)
                if sc_file:
                    shutil.move(sc_file, dest_path + '.xmp')
            else:
                shutil.copy2(info['path'], dest_path)
                if sc_file:
                    shutil.copy2(sc_file, dest_path + '.xmp')
            yield info


class CameraSource(object):
    image_types = ['.' + x for x in image_types_lower() + video_types_lower()]

    def __init__(self, model, port_name):
        self.model = model
        self.port_name = port_name

    @contextmanager
    def session(self):
        # initialise camera
        camera = gp.Camera()
        # search ports for camera port name
        port_info_list = gp.PortInfoList()
        port_info_list.load()
        idx = port_info_list.lookup_path(self.port_name)
        camera.set_port_info(port_info_list[idx])
        camera.init()
        # check camera is the right model
        if camera.get_abilities().model != self.model:
            raise RuntimeError('Camera model mismatch')
        try:
            yield camera
        finally:
            camera.exit()

    def _list_files(self, camera, path='/'):
        result = []
        # get files
        for name, value in camera.folder_list_files(path):
            base, ext = os.path.splitext(name)
            if ext.lower() in self.image_types:
                result.append(os.path.join(path, name))
        # get folders
        folders = []
        for name, value in camera.folder_list_folders(path):
            folders.append(name)
        # recurse over subfolders
        for name in folders:
            result.extend(self._list_files(camera, os.path.join(path, name)))
        return result

    def get_file_data(self):
        with self.session() as camera:
            try:
                file_list = self._list_files(camera)
            except gp.GPhoto2Error:
                # camera is no longer visible
                return None
            file_data = {}
            for path in file_list:
                folder, name = os.path.split(path)
                try:
                    info = camera.file_get_info(str(folder), str(name))
                except gp.GPhoto2Error:
                    return None
                timestamp = datetime.utcfromtimestamp(info.file.mtime)
                file_data[name] = {
                    'camera'    : self.model,
                    'folder'    : folder,
                    'name'      : name,
                    'timestamp' : timestamp,
                    }
        return file_data

    def copy_files(self, info_list, move):
        with self.session() as camera:
            for info in info_list:
                dest_dir = os.path.dirname(info['dest_path'])
                if not os.path.isdir(dest_dir):
                    os.makedirs(dest_dir)
                camera_file = camera.file_get(
                    info['folder'], info['name'], gp.GP_FILE_TYPE_NORMAL)
                camera_file.save(info['dest_path'])
                if move:
                    camera.file_delete(info['folder'], info['name'])
                yield info


class FileCopier(QtCore.QObject):
    def __init__(self, source, copy_list, move, copier_result, *args, **kwds):
        super(FileCopier, self).__init__(*args, **kwds)
        self.source = source
        self.copy_list = copy_list
        self.move = move
        self.copier_result = copier_result
        self.running = True

    @QtSlot()
    @catch_all
    def start(self):
        status = 'ok'
        try:
            for info in self.source.copy_files(self.copy_list, self.move):
                self.copier_result.append((info, status))
                # wait for image display to show previous image(s)
                while self.running and len(self.copier_result) > 1:
                    QtCore.QThread.yieldCurrentThread()
                if not self.running:
                    break
        except Exception as ex:
            status = str(ex)
            logger.error(status)
        self.copier_result.append(({}, status))


def get_camera_list():
    if not gp:
        return []
    camera_list = []
    for name, addr in gp.check_result(gp.gp_camera_autodetect()):
        camera_list.append((name, addr))
    camera_list.sort(key=lambda x: x[0])
    return camera_list


class NameMangler(QtCore.QObject):
    number_parser = re.compile(r'(\d+)')
    new_example = QtSignal(str)

    def __init__(self, parent=None):
        super(NameMangler, self).__init__(parent)
        self.example = None
        self.format_string = None

    @QtSlot(str)
    @catch_all
    def new_format(self, format_string):
        self.format_string = format_string
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
        numbers = self.number_parser.findall(name)
        if numbers:
            subst['number'] = numbers[-1]
        else:
            subst['number'] = ''
        subst['root'], subst['ext'] = os.path.splitext(name)
        subst['camera'] = file_data['camera'] or 'unknown_camera'
        subst['camera'] = subst['camera'].replace(' ', '_')
        # process {...} parts first
        try:
            result = self.format_string.format(**subst)
        except (KeyError, ValueError):
            result = self.format_string
        # then do timestamp
        return file_data['timestamp'].strftime(result)


class PathFormatValidator(QtGui.QValidator):
    def validate(self, inp, pos):
        if os.path.abspath(inp) == inp:
            return QtGui.QValidator.Acceptable, inp, pos
        return QtGui.QValidator.Intermediate, inp, pos

    def fixup(self, inp):
        return os.path.abspath(inp)


class TabWidget(QtWidgets.QWidget):
    @staticmethod
    def tab_name():
        return translate('ImporterTab', '&Import photos')

    def __init__(self, image_list, parent=None):
        super(TabWidget, self).__init__(parent)
        self.app = QtWidgets.QApplication.instance()
        self.app.aboutToQuit.connect(self.stop_copy)
        if gp and self.app.options.test:
            self.gp_log = gp.check_result(gp.use_python_logging())
        self.config_store = self.app.config_store
        self.image_list = image_list
        self.setLayout(QtWidgets.QGridLayout())
        form = QtWidgets.QFormLayout()
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        self.nm = NameMangler()
        self.file_data = {}
        self.file_list = []
        self.source = None
        self.file_copier = None
        self.updating = QtCore.QMutex()
        # source selector
        box = QtWidgets.QHBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        self.source_selector = QtWidgets.QComboBox()
        self.source_selector.currentIndexChanged.connect(self.new_source)
        box.addWidget(self.source_selector)
        refresh_button = QtWidgets.QPushButton(
            translate('ImporterTab', 'refresh'))
        refresh_button.clicked.connect(self.refresh)
        box.addWidget(refresh_button)
        box.setStretch(0, 1)
        form.addRow(translate('ImporterTab', 'Source'), box)
        # path format
        self.path_format = QtWidgets.QLineEdit()
        self.path_format.setValidator(PathFormatValidator())
        self.path_format.textChanged.connect(self.nm.new_format)
        self.path_format.editingFinished.connect(self.path_format_finished)
        form.addRow(translate('ImporterTab', 'Target format'), self.path_format)
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
        buttons.addWidget(self.selected_count)
        select_all = QtWidgets.QPushButton(
            translate('ImporterTab', 'Select\nall'))
        select_all.clicked.connect(self.select_all)
        buttons.addWidget(select_all)
        select_new = QtWidgets.QPushButton(
            translate('ImporterTab', 'Select\nnew'))
        select_new.clicked.connect(self.select_new)
        buttons.addWidget(select_new)
        # copy buttons
        self.move_button = StartStopButton(
            translate('ImporterTab', 'Move\nphotos'),
            translate('ImporterTab', 'Stop\nmove'))
        self.move_button.click_start.connect(self.move_selected)
        self.move_button.click_stop.connect(self.stop_copy)
        buttons.addWidget(self.move_button)
        self.copy_button = StartStopButton(
            translate('ImporterTab', 'Copy\nphotos'),
            translate('ImporterTab', 'Stop\ncopy'))
        self.copy_button.click_start.connect(self.copy_selected)
        self.copy_button.click_stop.connect(self.stop_copy)
        buttons.addWidget(self.copy_button)
        self.layout().addLayout(buttons, 0, 1, 2, 1)
        self.selection_changed()
        # final initialisation
        self.image_list.sort_order_changed.connect(self.sort_file_list)
        if qt_version_info >= (5, 0):
            path = QtCore.QStandardPaths.writableLocation(
                QtCore.QStandardPaths.PicturesLocation)
        else:
            path = QtGui.QDesktopServices.storageLocation(
                QtGui.QDesktopServices.PicturesLocation)
        self.path_format.setText(
            os.path.join(path, '%Y', '%Y_%m_%d', '{name}'))
        self.refresh()
        self.list_files()

    @QtSlot(int)
    @catch_all
    def new_source(self, idx):
        self.source = None
        item_data = self.source_selector.itemData(idx)
        if not item_data:
            return
        if callable(item_data):
            # a special 'source' that's actually a method to call
            (item_data)()
            return
        # select new source
        self.source, self.config_section = item_data
        path_format = self.path_format.text()
        path_format = self.config_store.get(
            self.config_section, 'path_format', path_format)
        path_format = path_format.replace('(', '{').replace(')', '}')
        self.path_format.setText(path_format)
        self.file_list_widget.clear()
        # allow 100ms for display to update before getting file list
        QtCore.QTimer.singleShot(100, self.list_files)

    def add_folder(self):
        folders = eval(self.config_store.get('importer', 'folders', '[]'))
        if folders:
            directory = folders[0]
        else:
            directory = ''
        root = QtWidgets.QFileDialog.getExistingDirectory(
            self, translate('ImporterTab', "Select root folder"), directory)
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

    @QtSlot()
    @catch_all
    def path_format_finished(self):
        if self.source:
            self.config_store.set(
                self.config_section, 'path_format', self.nm.format_string)
        self.show_file_list()

    @QtSlot()
    @catch_all
    def refresh(self):
        was_blocked = self.source_selector.blockSignals(True)
        # save current selection
        idx = self.source_selector.currentIndex()
        if idx >= 0:
            old_item_text = self.source_selector.itemText(idx)
        else:
            old_item_text = None
        # rebuild list
        self.source_selector.clear()
        self.source_selector.addItem(
            translate('ImporterTab', '<select source>'), self._new_file_list)
        for model, port_name in get_camera_list():
            self.source_selector.addItem(
                translate('ImporterTab', 'camera: {0}').format(model),
                (CameraSource(model, port_name), 'importer ' + model))
        for root in eval(self.config_store.get('importer', 'folders', '[]')):
            if os.path.isdir(root):
                self.source_selector.addItem(
                    translate('ImporterTab', 'folder: {0}').format(root),
                    (FolderSource(root), 'importer folder ' + root))
        self.source_selector.addItem(
            translate('ImporterTab', '<add a folder>'), self.add_folder)
        # restore saved selection
        new_idx = -1
        for idx in range(self.source_selector.count()):
            item_text = self.source_selector.itemText(idx)
            if item_text == old_item_text:
                new_idx = idx
                self.source_selector.setCurrentIndex(idx)
                break
        self.source_selector.blockSignals(was_blocked)
        if new_idx < 0:
            self.source_selector.setCurrentIndex(0)

    def do_not_close(self):
        if not self.file_copier:
            return False
        dialog = QtWidgets.QMessageBox(parent=self)
        dialog.setWindowTitle(translate(
            'ImporterTab', 'Photini: import in progress'))
        dialog.setText(translate(
            'ImporterTab', '<h3>Importing photos has not finished.</h3>'))
        dialog.setInformativeText(translate(
            'ImporterTab', 'Closing now will terminate the import.'))
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        dialog.setStandardButtons(
            QtWidgets.QMessageBox.Close | QtWidgets.QMessageBox.Cancel)
        dialog.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        result = dialog.exec_()
        if result == QtWidgets.QMessageBox.Close:
            self.stop_copy()
        return result == QtWidgets.QMessageBox.Cancel

    @QtSlot(list)
    def new_selection(self, selection):
        pass

    @QtSlot()
    @catch_all
    def list_files(self):
        file_data = {}
        if self.source:
            with Busy():
                file_data = self.source.get_file_data()
                if file_data is None:
                    self._fail()
                    return
        self._new_file_list(file_data)

    def _fail(self):
        self.source_selector.setCurrentIndex(0)
        self.refresh()

    def _new_file_list(self, file_data={}):
        self.file_list = list(file_data.keys())
        self.file_data = file_data
        self.sort_file_list()

    @QtSlot()
    @catch_all
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
            item.setData(Qt.UserRole, name)
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

    @QtSlot()
    @catch_all
    def selection_changed(self):
        count = len(self.file_list_widget.selectedItems())
        self.selected_count.setText(
            translate('ImporterTab', '%n file(s)\nselected', '', count))
        if not self.file_copier:
            self.move_button.setEnabled(count > 0)
            self.copy_button.setEnabled(count > 0)

    @QtSlot()
    @catch_all
    def select_all(self):
        self.select_files(datetime.min)

    @QtSlot()
    @catch_all
    def select_new(self):
        since = datetime.min
        if self.source:
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
            name = item.data(Qt.UserRole)
            timestamp = self.file_data[name]['timestamp']
            if timestamp > since:
                if not first_active:
                    first_active = item
                item.setSelected(True)
        if not first_active:
            first_active = item
        self.file_list_widget.scrollToItem(
            first_active, QtWidgets.QAbstractItemView.PositionAtTop)

    @QtSlot()
    @catch_all
    def move_selected(self):
        self.copy_selected(move=True)

    @QtSlot()
    @catch_all
    def copy_selected(self, move=False):
        copy_list = []
        for item in self.file_list_widget.selectedItems():
            name = item.data(Qt.UserRole)
            info = self.file_data[name]
            if (move and 'path' in info and
                    self.image_list.get_image(info['path'])):
                # don't rename an open file
                logger.warning(
                    'Please close image %s before moving it', info['name'])
            else:
                copy_list.append(info)
        if not copy_list:
            return
        if move:
            self.move_button.set_checked(True)
            self.copy_button.setEnabled(False)
        else:
            self.copy_button.set_checked(True)
            self.move_button.setEnabled(False)
        last_file_copied = None, datetime.min
        copier_result = deque()
        # start file copier in a separate thread
        self.file_copier = FileCopier(
            self.source, copy_list, move, copier_result)
        copier_thread = QtCore.QThread(self)
        self.file_copier.moveToThread(copier_thread)
        copier_thread.started.connect(self.file_copier.start)
        copier_thread.start()
        # show files as they're copied
        while self.file_copier.running:
            if copier_result:
                info, status = copier_result.popleft()
                if not info:
                    # copier thread has finished
                    break
                if status != 'ok':
                    self._fail()
                    break
                if last_file_copied[1] < info['timestamp']:
                    last_file_copied = info['dest_path'], info['timestamp']
                for n in range(self.file_list_widget.count()):
                    item = self.file_list_widget.item(n)
                    if item.data(Qt.UserRole) == info['name']:
                        item.setFlags(Qt.NoItemFlags)
                        self.file_list_widget.scrollToItem(
                            item, QtWidgets.QAbstractItemView.PositionAtTop)
                        self.selection_changed()
                        break
                self.image_list.open_file(info['dest_path'])
            else:
                # wait for copier result
                self.app.processEvents()
        self.move_button.set_checked(False)
        self.copy_button.set_checked(False)
        self.file_copier = None
        copier_thread.quit()
        copier_thread.wait()
        if last_file_copied[0]:
            self.config_store.set(self.config_section, 'last_transfer',
                                  last_file_copied[1].isoformat(' '))
            self.image_list.done_opening(last_file_copied[0])
        self.list_files()

    @QtSlot()
    @catch_all
    def stop_copy(self):
        if self.file_copier:
            self.file_copier.running = False
