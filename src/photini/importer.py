##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import re
import shutil
import sys

try:
    import gphoto2 as gp
    gp_version_info = tuple(map(int, gp.__version__.split('.')))
except ImportError:
    gp = None

from photini.metadata import Metadata
from photini.pyqt import *
from photini.pyqt import image_types_lower, qt_version_info, video_types_lower
from photini.widgets import ComboBox, PushButton, StartStopButton

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
        # get files
        if gp_version_info >= (2, 4):
            result = [os.path.join(path, x)
                      for x in camera.folder_list_files(path).keys()
                      if os.path.splitext(x)[1].lower() in self.image_types]
        else:
            result = [os.path.join(path, x)
                      for x, y in camera.folder_list_files(path)
                      if os.path.splitext(x)[1].lower() in self.image_types]
        # get folders
        if gp_version_info >= (2, 4):
            folders = list(camera.folder_list_folders(path).keys())
        else:
            folders = [x for x, y in camera.folder_list_folders(path)]
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
                    'size'      : info.file.size,
                    'timestamp' : timestamp,
                    }
        return file_data

    def copy_files(self, info_list, move):
        with self.session() as camera:
            for info in info_list:
                dest_dir = os.path.dirname(info['dest_path'])
                if not os.path.isdir(dest_dir):
                    os.makedirs(dest_dir)
                buf = bytearray(min(info['size'], 32 * 1024 * 1024))
                try:
                    with open(info['dest_path'], 'wb') as of:
                        offset = 0
                        while offset < info['size']:
                            count = camera.file_read(
                                info['folder'], info['name'],
                                gp.GP_FILE_TYPE_NORMAL, offset, buf)
                            of.write(buf[:count])
                            offset += count
                except Exception:
                    os.unlink(info['dest_path'])
                    raise
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
    for name, addr in gp.Camera.autodetect().items():
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
    @catch_all
    def validate(self, inp, pos):
        if os.path.abspath(inp) == inp:
            return self.State.Acceptable, inp, pos
        return self.State.Intermediate, inp, pos

    @catch_all
    def fixup(self, inp):
        return os.path.abspath(inp)


class SourceSelector(ComboBox):
    def __init__(self, importer_tab, *arg, **kw):
        super(SourceSelector, self).__init__(*arg, **kw)
        self.importer_tab = importer_tab

    def showPopup(self):
        # refresh list of cameras
        self.importer_tab.refresh()
        super(SourceSelector, self).showPopup()


class ImporterTab(QtWidgets.QWidget):
    @staticmethod
    def tab_name():
        return translate('ImporterTab', 'Import photos',
                         'Full name of tab shown as a tooltip')

    @staticmethod
    def tab_short_name():
        return translate('ImporterTab', '&Import',
                         'Shortest possible name used as tab label')

    def __init__(self, parent=None):
        super(ImporterTab, self).__init__(parent)
        self.app = QtWidgets.QApplication.instance()
        self.app.aboutToQuit.connect(self.stop_copy)
        if gp and self.app.options.test:
            self.gp_log = gp.check_result(gp.use_python_logging())
        self.config_store = self.app.config_store
        self.setLayout(QtWidgets.QGridLayout())
        form = FormLayout()
        self.nm = NameMangler()
        self.file_data = {}
        self.file_list = []
        self.source = None
        self.file_copier = None
        self.updating = QtCore.QMutex()
        # source selector
        box = QtWidgets.QHBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        self.source_selector = SourceSelector(self)
        self.source_selector.currentIndexChanged.connect(self.new_source)
        self.source_selector.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.source_selector.customContextMenuRequested.connect(
            self.remove_folder)
        box.addWidget(self.source_selector)
        refresh_button = QtWidgets.QPushButton(
            translate('ImporterTab', 'refresh'))
        refresh_button.clicked.connect(self.list_files)
        box.addWidget(refresh_button)
        box.setStretch(0, 1)
        form.addRow(translate('ImporterTab', 'Source'), box)
        # update config
        self.config_store.delete('importer', 'folders')
        for section in self.config_store.config.sections():
            if not section.startswith('importer'):
                continue
            path_format = self.config_store.get(section, 'path_format')
            if not (path_format and '(' in path_format):
                continue
            path_format = path_format.replace('(', '{').replace(')', '}')
            self.config_store.set(section, 'path_format', path_format)
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
            self.file_list_widget.SelectionMode.ExtendedSelection)
        self.file_list_widget.itemSelectionChanged.connect(self.selection_changed)
        self.layout().addWidget(self.file_list_widget, 1, 0)
        # selection buttons
        buttons = QtWidgets.QVBoxLayout()
        buttons.addStretch(1)
        self.selected_count = QtWidgets.QLabel()
        buttons.addWidget(self.selected_count)
        select_all = PushButton(translate('ImporterTab', 'Select all'), lines=2)
        select_all.clicked.connect(self.select_all)
        buttons.addWidget(select_all)
        select_new = PushButton(translate('ImporterTab', 'Select new'), lines=2)
        select_new.clicked.connect(self.select_new)
        buttons.addWidget(select_new)
        # copy buttons
        self.move_button = StartStopButton(
            translate('ImporterTab', 'Move photos'),
            translate('ImporterTab', 'Stop move'), lines=2)
        self.move_button.click_start.connect(self.move_selected)
        self.move_button.click_stop.connect(self.stop_copy)
        buttons.addWidget(self.move_button)
        self.copy_button = StartStopButton(
            translate('ImporterTab', 'Copy photos'),
            translate('ImporterTab', 'Stop copy'), lines=2)
        self.copy_button.click_start.connect(self.copy_selected)
        self.copy_button.click_stop.connect(self.stop_copy)
        buttons.addWidget(self.copy_button)
        self.layout().addLayout(buttons, 0, 1, 2, 1)
        self.selection_changed()
        # final initialisation
        self.app.image_list.sort_order_changed.connect(self.sort_file_list)
        path = QtCore.QStandardPaths.writableLocation(
            QtCore.QStandardPaths.StandardLocation.PicturesLocation)
        self.path_format.setText(
            os.path.join(path, '%Y', '%Y_%m_%d', '{name}'))

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
        self.path_format.setText(path_format)
        self.file_list_widget.clear()
        # allow 100ms for display to update before getting file list
        QtCore.QTimer.singleShot(100, self.list_files)

    @QtSlot(QtCore.QPoint)
    @catch_all
    def remove_folder(self, pos):
        menu = QtWidgets.QMenu()
        roots = []
        for section in self.config_store.config.sections():
            if not section.startswith('importer folder '):
                continue
            roots.append((section[16:], self.config_store.get(
                section, 'last_transfer', datetime.min.isoformat(' '))))
        roots.sort(key=lambda x: x[1], reverse=True)
        for root, last_transfer in roots:
            name = translate(
                'ImporterTab', 'folder: {folder_name}').format(folder_name=root)
            action = QtGui2.QAction(
                translate('ImporterTab', 'Remove "{source_name}"'
                          ).format(source_name=name),
                parent=self)
            action.setData('importer folder ' + root)
            menu.addAction(action)
        if menu.isEmpty():
            return
        action = execute(menu, self.mapToGlobal(pos))
        if not action:
            return
        self.config_store.remove_section(action.data())
        self.refresh()

    def add_folder(self):
        directory = ''
        for idx in range(self.source_selector.count()):
            item_data = self.source_selector.itemData(idx)
            if callable(item_data):
                continue
            source, section = item_data
            if section.startswith('importer folder '):
                directory = section[16:]
                break
        root = QtWidgets.QFileDialog.getExistingDirectory(
            self, translate('ImporterTab', "Select root folder"), directory)
        if not root:
            self._fail()
            return
        section = 'importer folder ' + root
        self.config_store.set(
            section, 'last_transfer', datetime.min.isoformat(' '))
        self.source_selector.addItem(
            translate('ImporterTab', 'folder: {folder_name}'
                      ).format(folder_name=root),
            (FolderSource(root), section))
        idx = self.source_selector.count() - 1
        self.source_selector.setCurrentIndex(idx)
        self.refresh()

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
                translate('ImporterTab', 'camera: {camera_name}'
                          ).format(camera_name=model),
                (CameraSource(model, port_name), 'importer ' + model))
        roots = []
        for section in self.config_store.config.sections():
            if not section.startswith('importer folder '):
                continue
            roots.append((section[16:], self.config_store.get(
                section, 'last_transfer', datetime.min.isoformat(' '))))
        roots.sort(key=lambda x: x[1], reverse=True)
        for root, last_transfer in roots:
            if os.path.isdir(root):
                self.source_selector.addItem(
                    translate('ImporterTab', 'folder: {folder_name}'
                              ).format(folder_name=root),
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
            self.new_source(0)

    def do_not_close(self):
        if not self.file_copier:
            return False
        dialog = QtWidgets.QMessageBox(parent=self)
        dialog.setWindowTitle(translate(
            'ImporterTab', 'Photini: import in progress'))
        dialog.setText('<h3>{}</h3>'.format(translate(
            'ImporterTab', 'Importing photos has not finished.')))
        dialog.setInformativeText(translate(
            'ImporterTab', 'Closing now will terminate the import.'))
        dialog.setIcon(dialog.Icon.Warning)
        dialog.setStandardButtons(
            dialog.StandardButton.Close | dialog.StandardButton.Cancel)
        dialog.setDefaultButton(dialog.StandardButton.Cancel)
        result = execute(dialog)
        if result == dialog.StandardButton.Close:
            self.stop_copy()
        return result == dialog.StandardButton.Cancel

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
        if self.config_store.get('controls', 'sort_date', False):
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
            item.setData(Qt.ItemDataRole.UserRole, name)
            if os.path.exists(dest_path):
                item.setFlags(Qt.ItemFlag.NoItemFlags)
            else:
                if not first_active:
                    first_active = item
                item.setFlags(
                    Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self.file_list_widget.addItem(item)
        if not first_active:
            first_active = item
        self.file_list_widget.scrollToItem(
            first_active, self.file_list_widget.ScrollHint.PositionAtTop)

    @QtSlot()
    @catch_all
    def selection_changed(self):
        count = len(self.file_list_widget.selectedItems())
        if qt_version_info >= (6, 0):
            # pyside6-lupdate doesn't recognise plurals with 'translate'
            string = ImporterTab.tr('%n file(s) selected', '', count)
        else:
            # Qt5 doesn't handle ClassName.tr correctly
            string = translate('ImporterTab', '%n file(s) selected', '', count)
        self.selected_count.setText(wrap_text(self.selected_count, string, 2))
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
            if not (item.flags() & Qt.ItemFlag.ItemIsSelectable):
                continue
            name = item.data(Qt.ItemDataRole.UserRole)
            timestamp = self.file_data[name]['timestamp']
            if timestamp > since:
                if not first_active:
                    first_active = item
                item.setSelected(True)
        if not first_active:
            first_active = item
        self.file_list_widget.scrollToItem(
            first_active, self.file_list_widget.ScrollHint.PositionAtTop)

    @QtSlot()
    @catch_all
    def move_selected(self):
        self.copy_selected(move=True)

    @QtSlot()
    @catch_all
    def copy_selected(self, move=False):
        with Busy():
            copy_list = []
            for item in self.file_list_widget.selectedItems():
                name = item.data(Qt.ItemDataRole.UserRole)
                info = self.file_data[name]
                if (move and 'path' in info and
                        self.app.image_list.get_image(info['path'])):
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
                        if item.data(Qt.ItemDataRole.UserRole) == info['name']:
                            item.setFlags(Qt.ItemFlag.NoItemFlags)
                            self.file_list_widget.scrollToItem(
                                item,
                                self.file_list_widget.ScrollHint.PositionAtTop)
                            self.selection_changed()
                            break
                    self.app.image_list.open_file(info['dest_path'])
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
            self.app.image_list.done_opening(last_file_copied[0])
        self.list_files()

    @QtSlot()
    @catch_all
    def stop_copy(self):
        if self.file_copier:
            self.file_copier.running = False
            self.move_button.setEnabled(False)
            self.copy_button.setEnabled(False)
            self.app.processEvents()


class TabWidget(ImporterTab):
    pass
