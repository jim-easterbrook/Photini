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

from __future__ import unicode_literals

import six
from datetime import datetime
import os
import subprocess
import sys
from six.moves.urllib.parse import unquote

import appdirs

from .flowlayout import FlowLayout
from .metadata import Metadata, MetadataHandler
from .pyqt import Qt, QtCore, QtGui, QtWidgets
from .utils import Busy

DRAG_MIMETYPE = 'application/x-photini-image'

class Image(QtWidgets.QFrame):
    def __init__(self, path, image_list, thumb_size=80, parent=None):
        QtWidgets.QFrame.__init__(self, parent)
        self.path = path
        self.image_list = image_list
        self.name = os.path.splitext(os.path.basename(self.path))[0]
        self.selected = False
        self.pixmap = None
        self.thumb_size = thumb_size
        self.metadata = Metadata(self.path)
        self.metadata.new_status.connect(self.show_status)
        layout = QtWidgets.QGridLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(3, 3, 3, 3)
        self.setLayout(layout)
        self.setToolTip(self.path)
        # label to display image
        self.image = QtWidgets.QLabel()
        self.image.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        layout.addWidget(self.image, 0, 0, 1, 2)
        # label to display file name
        self.label = QtWidgets.QLabel(self.name)
        self.label.setAlignment(Qt.AlignRight)
        self.label.setStyleSheet("QLabel { font-size: 12px }")
        layout.addWidget(self.label, 1, 1)
        # label to display status
        self.status = QtWidgets.QLabel()
        self.status.setAlignment(Qt.AlignLeft)
        self.status.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed, self.status.sizePolicy().verticalPolicy())
        self.status.setStyleSheet("QLabel { font-size: 12px }")
        self.status.setFont(QtGui.QFont("Dejavu Sans"))
        if not self.status.fontInfo().exactMatch():
            # probably on Windows, try a different font
            self.status.setFont(QtGui.QFont("Segoe UI Symbol"))
        layout.addWidget(self.status, 1, 0)
        self.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Plain)
        self.setObjectName("thumbnail")
        self.set_selected(False)
        self.show_status(False)
        self._set_thumb_size(self.thumb_size)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.pos()
        self.image_list.thumb_mouse_press(self.path, event)

    def mouseMoveEvent(self, event):
        if not self.image_list.drag_icon:
            return
        if ((event.pos() - self.drag_start_pos).manhattanLength() <
                                    QtWidgets.QApplication.startDragDistance()):
            return
        paths = []
        for image in self.image_list.get_selected_images():
            paths.append(image.path)
        if not paths:
            return
        drag = QtWidgets.QDrag(self)
        drag.setPixmap(self.image_list.drag_icon)
        drag.setHotSpot(QtCore.QPoint(
            drag.pixmap().width() // 2, drag.pixmap().height()))
        mimeData = QtCore.QMimeData()
        mimeData.setData(DRAG_MIMETYPE, repr(paths).encode('utf-8'))
        drag.setMimeData(mimeData)
        dropAction = drag.exec_(Qt.CopyAction)

    def mouseDoubleClickEvent(self, event):
        if sys.platform.startswith('linux'):
            subprocess.call(['xdg-open', self.path])
        elif sys.platform.startswith('darwin'):
            subprocess.call(['open', self.path])
        elif sys.platform.startswith('win'):
            subprocess.call(['start', self.path], shell=True)

    @QtCore.pyqtSlot(bool)
    def show_status(self, changed):
        status = ''
        # set 'geotagged' status
        if self.metadata.latlong:
            status += six.unichr(0x2690)
        # set 'unsaved' status
        if changed:
            status += six.unichr(0x26A1)
        self.status.setText(status)
        if changed:
            self.image_list.new_metadata.emit(True)

    def _set_thumb_size(self, thumb_size):
        self.thumb_size = thumb_size
        self.image.setFixedSize(self.thumb_size, self.thumb_size)
        margins = self.layout().contentsMargins()
        self.setFixedWidth(self.thumb_size + margins.left() + margins.right() +
                           (self.frameWidth() * 2))

    def set_thumb_size(self, thumb_size):
        self._set_thumb_size(thumb_size)
        self.load_thumbnail()

    def load_thumbnail(self):
        if not self.pixmap:
            self.pixmap = QtGui.QPixmap(self.path)
            if not self.pixmap.isNull():
                if max(self.pixmap.width(), self.pixmap.height()) > 300:
                    # store a scaled down version of image to save memory
                    self.pixmap = self.pixmap.scaled(
                        300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                orientation = self.metadata.orientation
                if orientation and orientation > 1:
                    # need to rotate and or reflect image
                    transform = QtGui.QTransform()
                    if orientation in (3, 4):
                        transform = transform.rotate(180.0)
                    elif orientation in (5, 6):
                        transform = transform.rotate(90.0)
                    elif orientation in (7, 8):
                        transform = transform.rotate(-90.0)
                    if orientation in (2, 4, 5, 7):
                        transform = transform.scale(-1.0, 1.0)
                    self.pixmap = self.pixmap.transformed(transform)
        if self.pixmap.isNull():
            self.image.setText(self.tr('Can not\nload\nimage'))
        else:
            self.image.setPixmap(self.pixmap.scaled(
                self.thumb_size, self.thumb_size,
                Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def as_jpeg(self):
        im = QtWidgets.QImage(self.path)
        temp_dir = appdirs.user_cache_dir('photini')
        if not os.path.isdir(temp_dir):
            os.makedirs(temp_dir)
        path = os.path.join(temp_dir, os.path.basename(self.path) + '.jpg')
        im.save(path, format='jpeg', quality=95)
        # copy metadata
        try:
            src_md = MetadataHandler(self.path)
        except Exception:
            pass
        else:
            dst_md = MetadataHandler(path)
            dst_md.copy(src_md)
            dst_md.save()
        return path

    def set_selected(self, value):
        self.selected = value
        if self.selected:
            self.setStyleSheet("#thumbnail {border: 2px solid red}")
        else:
            self.setStyleSheet("#thumbnail {border: 2px solid grey}")

    def get_selected(self):
        return self.selected

class ScrollArea(QtWidgets.QScrollArea):
    dropped_images = QtCore.pyqtSignal(list)
    def __init__(self, parent=None):
        QtWidgets.QScrollArea.__init__(self, parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setWidgetResizable(True)
        self.setAcceptDrops(True)

    def dropEvent(self, event):
        file_list = []
        for uri in event.mimeData().urls():
            file_list.append(uri.toLocalFile())
        if file_list:
            self.dropped_images.emit(file_list)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('text/uri-list'):
            event.acceptProposedAction()

class ImageList(QtWidgets.QWidget):
    image_list_changed = QtCore.pyqtSignal()
    new_metadata = QtCore.pyqtSignal(bool)
    selection_changed = QtCore.pyqtSignal(list)
    sort_order_changed = QtCore.pyqtSignal()
    def __init__(self, config_store, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.config_store = config_store
        self.app = QtWidgets.QApplication.instance()
        self.drag_icon = None
        self.path_list = list()
        self.image = dict()
        self.last_selected = None
        self.selection_anchor = None
        self.thumb_size = int(self.config_store.get(
            'controls', 'thumb_size', '80'))
        layout = QtWidgets.QGridLayout()
        layout.setSpacing(0)
        layout.setRowStretch(0, 1)
        layout.setColumnStretch(3, 1)
        self.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        # thumbnail display
        self.scroll_area = ScrollArea()
        self.scroll_area.dropped_images.connect(self.open_file_list)
        layout.addWidget(self.scroll_area, 0, 0, 1, 6)
        self.thumbnails = QtWidgets.QWidget()
        self.thumbnails.setLayout(FlowLayout(hSpacing=0, vSpacing=0))
        self.scroll_area.setWidget(self.thumbnails)
        QtWidgets.QShortcut(QtGui.QKeySequence.MoveToPreviousChar,
                        self.scroll_area, self.move_to_prev_thumb)
        QtWidgets.QShortcut(QtGui.QKeySequence.MoveToNextChar,
                        self.scroll_area, self.move_to_next_thumb)
        QtWidgets.QShortcut(QtGui.QKeySequence.SelectPreviousChar,
                        self.scroll_area, self.select_prev_thumb)
        QtWidgets.QShortcut(QtGui.QKeySequence.SelectNextChar,
                        self.scroll_area, self.select_next_thumb)
        QtWidgets.QShortcut(QtGui.QKeySequence.SelectAll,
                        self.scroll_area, self.select_all)
        # sort key selector
        layout.addWidget(QtWidgets.QLabel(self.tr('sort by: ')), 1, 0)
        self.sort_name = QtWidgets.QRadioButton(self.tr('file name'))
        self.sort_name.clicked.connect(self._new_sort_order)
        layout.addWidget(self.sort_name, 1, 1)
        self.sort_date = QtWidgets.QRadioButton(self.tr('date taken'))
        layout.addWidget(self.sort_date, 1, 2)
        self.sort_date.clicked.connect(self._new_sort_order)
        if eval(self.config_store.get('controls', 'sort_date', 'False')):
            self.sort_date.setChecked(True)
        else:
            self.sort_name.setChecked(True)
        # size selector
        layout.addWidget(QtWidgets.QLabel(self.tr('thumbnail size: ')), 1, 4)
        self.size_slider = QtWidgets.QSlider(Qt.Horizontal)
        self.size_slider.setTracking(False)
        self.size_slider.setRange(4, 9)
        self.size_slider.setPageStep(1)
        self.size_slider.setValue(self.thumb_size / 20)
        self.size_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.size_slider.setMinimumWidth(140)
        self.size_slider.valueChanged.connect(self._new_thumb_size)
        layout.addWidget(self.size_slider, 1, 5)

    def set_drag_to_map(self, icon):
        self.drag_icon = icon

    def get_image(self, path):
        if path not in self.path_list:
            return None
        return self.image[path]

    def get_images(self):
        for path in self.path_list:
            yield self.image[path]

    def get_selected_images(self):
        selection = list()
        for path in self.path_list:
            image = self.image[path]
            if image.get_selected():
                selection.append(image)
        return selection

    def mousePressEvent(self, event):
        if self.scroll_area.underMouse():
            self._clear_selection()
            self.last_selected = None
            self.selection_anchor = None
            self.emit_selection()

    @QtCore.pyqtSlot()
    def open_files(self):
        types = [
            'jpeg', 'jpg', 'exv', 'cr2', 'crw', 'mrw', 'tiff', 'tif', 'dng',
            'nef', 'pef', 'arw', 'rw2', 'sr2', 'srw', 'orf', 'png', 'pgf',
            'raf', 'eps', 'gif', 'psd', 'tga', 'bmp', 'jp2', 'pnm'
            ]
        for fmt in QtGui.QImageReader.supportedImageFormats():
            ext = fmt.data().decode('utf_8').lower()
            if ext not in types:
                types.append(ext)
        types = map(lambda x: '*.' + x, types)
        path_list = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Open files", self.config_store.get('paths', 'images', ''),
            self.tr("Images ({0});;All files (*)").format(' '.join(types)))
        if QtCore.QT_VERSION_STR.split('.')[0] == '5':
            path_list = path_list[0]
        if not path_list:
            return
        # work around for Qt bug 33992
        # https://bugreports.qt-project.org/browse/QTBUG-33992
        if QtCore.QT_VERSION_STR in ('4.8.4', '4.8.5'):
            path_list = list(map(unquote, path_list))
        self.open_file_list(path_list)

    @QtCore.pyqtSlot(list)
    def open_file_list(self, path_list):
        self.config_store.set(
            'paths', 'images', os.path.dirname(path_list[0]))
        with Busy():
            for path in path_list:
                path = os.path.normpath(path)
                if path in self.path_list:
                    continue
                self.path_list.append(path)
                image = Image(path, self, thumb_size=self.thumb_size)
                self.image[path] = image
                self.show_thumbnail(image)
        self._sort_thumbnails()

    def _date_key(self, idx):
        result = self.image[idx].metadata.date_taken
        if result is None:
            result = self.image[idx].metadata.date_digitised
        if result is None:
            result = self.image[idx].metadata.date_modified
        if result is None:
            # use file date as last resort
            return datetime.fromtimestamp(os.path.getmtime(self.image[idx].path))
        return result.datetime()

    def _new_sort_order(self):
        self._sort_thumbnails()
        self.sort_order_changed.emit()

    def _sort_thumbnails(self):
        sort_date = self.sort_date.isChecked()
        self.config_store.set('controls', 'sort_date', str(sort_date))
        with Busy():
            if sort_date:
                self.path_list.sort(key=self._date_key)
            else:
                self.path_list.sort()
            layout = self.thumbnails.layout()
            for path in self.path_list:
                self.show_thumbnail(self.image[path], False)
        if self.last_selected:
            self.app.processEvents()
            self.scroll_area.ensureWidgetVisible(self.image[self.last_selected])
        self.image_list_changed.emit()

    def show_thumbnail(self, image, live=True):
        self.thumbnails.layout().addWidget(image)
        if live:
            self.app.processEvents()
        image.load_thumbnail()
        if live:
            self.app.processEvents()
            self.scroll_area.ensureWidgetVisible(image)
            self.app.processEvents()

    def close_files(self, all_files):
        layout = self.thumbnails.layout()
        for path in list(self.path_list):
            image = self.image[path]
            if all_files or image.get_selected():
                self.path_list.remove(path)
                del self.image[path]
                layout.removeWidget(image)
                image.setParent(None)
        self.last_selected = None
        self.selection_anchor = None
        self.emit_selection()
        self.image_list_changed.emit()

    @QtCore.pyqtSlot()
    def save_files(self):
        if_mode = eval(self.config_store.get('files', 'image', 'True'))
        sc_mode = self.config_store.get('files', 'sidecar', 'auto')
        force_iptc = eval(self.config_store.get('files', 'force_iptc', 'False'))
        unsaved = False
        for path in list(self.path_list):
            image = self.image[path]
            image.metadata.save(if_mode, sc_mode, force_iptc)
            unsaved = unsaved or image.metadata.changed()
        self.new_metadata.emit(unsaved)

    def unsaved_files_dialog(
            self, all_files=False, with_cancel=True, with_discard=True):
        """Return true if OK to continue with close or quit or whatever"""
        for path in self.path_list:
            image = self.image[path]
            if image.metadata.changed() and (all_files or image.selected):
                break
        else:
            return True
        dialog = QtWidgets.QMessageBox()
        dialog.setWindowTitle(self.tr('Photini: unsaved data'))
        dialog.setText(self.tr('<h3>Some images have unsaved metadata.</h3>'))
        dialog.setInformativeText(self.tr('Do you want to save your changes?'))
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        buttons = QtWidgets.QMessageBox.Save
        if with_cancel:
            buttons |= QtWidgets.QMessageBox.Cancel
        if with_discard:
            buttons |= QtWidgets.QMessageBox.Discard
        dialog.setStandardButtons(buttons)
        dialog.setDefaultButton(QtWidgets.QMessageBox.Save)
        result = dialog.exec_()
        if result == QtWidgets.QMessageBox.Save:
            self.save_files()
            return True
        return result == QtWidgets.QMessageBox.Discard

    def get_selected_images(self):
        selection = list()
        for path in self.path_list:
            image = self.image[path]
            if image.get_selected():
                selection.append(image)
        return selection

    def emit_selection(self):
        self.selection_changed.emit(self.get_selected_images())

    def thumb_mouse_press(self, path, event):
        if event.modifiers() == Qt.ControlModifier:
            self.select_image(path, multiple_selection=True)
        elif event.modifiers() == Qt.ShiftModifier:
            self.select_image(path, extend_selection=True)
        else:
            self.select_image(path)

    def select_all(self):
        for path in self.path_list:
            image = self.image[path]
            image.set_selected(True)
        self.selection_anchor = None
        self.last_selected = None
        self.emit_selection()

    def move_to_prev_thumb(self):
        self._inc_selection(-1)

    def move_to_next_thumb(self):
        self._inc_selection(1)

    def select_prev_thumb(self):
        self._inc_selection(-1, extend_selection=True)

    def select_next_thumb(self):
        self._inc_selection(1, extend_selection=True)

    def _inc_selection(self, inc, extend_selection=False):
        if self.last_selected:
            idx = self.path_list.index(self.last_selected)
            idx = (idx + inc) % len(self.path_list)
        else:
            idx = 0
        path = self.path_list[idx]
        self.select_image(path, extend_selection=extend_selection)

    @QtCore.pyqtSlot()
    def _new_thumb_size(self):
        self.thumb_size = self.size_slider.value() * 20
        self.config_store.set('controls', 'thumb_size', str(self.thumb_size))
        for path in self.path_list:
            self.image[path].set_thumb_size(self.thumb_size)
        if self.last_selected:
            self.app.processEvents()
            self.scroll_area.ensureWidgetVisible(self.image[self.last_selected])

    def select_image(
            self, path, extend_selection=False, multiple_selection=False):
        image = self.image[path]
        self.scroll_area.ensureWidgetVisible(image)
        if extend_selection and self.selection_anchor:
            self._clear_selection()
            idx1 = self.path_list.index(self.selection_anchor)
            idx2 = self.path_list.index(path)
            for i in range(min(idx1, idx2), max(idx1, idx2) + 1):
                self.image[self.path_list[i]].set_selected(True)
        elif multiple_selection:
            image.set_selected(not image.get_selected())
            self.selection_anchor = path
        else:
            self._clear_selection()
            image.set_selected(True)
            self.selection_anchor = path
        self.last_selected = path
        self.emit_selection()

    def _clear_selection(self):
        for path in self.path_list:
            image = self.image[path]
            if image.get_selected():
                image.set_selected(False)
