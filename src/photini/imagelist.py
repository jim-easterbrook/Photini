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
import os
import subprocess
import sys

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt

from .flowlayout import FlowLayout
from .metadata import Metadata

class Image(QtGui.QFrame):
    def __init__(self, path, image_list, thumb_size=80, parent=None):
        QtGui.QFrame.__init__(self, parent)
        self.path = path
        self.image_list = image_list
        self.name = os.path.splitext(os.path.basename(self.path))[0]
        self.selected = False
        self.pixmap = None
        self.thumb_size = thumb_size
        self.metadata = Metadata(self.path)
        self.metadata.new_status.connect(self.show_status)
        layout = QtGui.QGridLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(3, 3, 3, 3)
        self.setLayout(layout)
        # label to display image
        self.image = QtGui.QLabel()
        self.image.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        layout.addWidget(self.image, 0, 0, 1, 2)
        # label to display file name
        self.label = QtGui.QLabel(self.name)
        self.label.setAlignment(Qt.AlignRight)
        self.label.setStyleSheet("QLabel { font-size: 12px }")
        layout.addWidget(self.label, 1, 1)
        # label to display status
        self.status = QtGui.QLabel()
        self.status.setAlignment(Qt.AlignLeft)
        self.status.setSizePolicy(
            QtGui.QSizePolicy.Fixed, self.status.sizePolicy().verticalPolicy())
        self.status.setStyleSheet("QLabel { font-size: 12px }")
        self.status.setFont(QtGui.QFont("Dejavu Sans"))
        layout.addWidget(self.status, 1, 0)
        self.setFrameStyle(QtGui.QFrame.Panel | QtGui.QFrame.Plain)
        self.setObjectName("thumbnail")
        self.set_selected(False)
        self.show_status(False)
        self._set_thumb_size(self.thumb_size)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.pos()
        self.image_list.thumb_mouse_press(self.path, event)

    def mouseMoveEvent(self, event):
        if ((event.pos() - self.drag_start_pos).manhattanLength() <
                                    QtGui.QApplication.startDragDistance()):
            return
        drag = QtGui.QDrag(self)
        mimeData = QtCore.QMimeData()
        paths = list()
        for image in self.image_list.get_selected_images():
            paths.append(image.path)
        mimeData.setText(str(paths))
        drag.setMimeData(mimeData)
        dropAction = drag.exec_(Qt.LinkAction)

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
        if not self.metadata.get_item('latlong').empty():
            status += unichr(0x2690)
        # set 'unsaved' status
        if changed:
            status += unichr(0x26A1)
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
        result = False
        if not self.pixmap:
            result = True
            self.pixmap = QtGui.QPixmap(self.path)
            if max(self.pixmap.width(), self.pixmap.height()) > 400:
                # store a scaled down version of image to save memory
                self.pixmap = self.pixmap.scaled(
                    400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            orientation = self.metadata.get_item('orientation')
            if not orientation.empty() and orientation.value != 1:
                # need to rotate and or reflect image
                transform = QtGui.QTransform()
                if orientation.value in (3, 4):
                    transform = transform.rotate(180.0)
                elif orientation.value in (5, 6):
                    transform = transform.rotate(90.0)
                elif orientation.value in (7, 8):
                    transform = transform.rotate(-90.0)
                if orientation.value in (2, 4, 5, 7):
                    transform = transform.scale(-1.0, 1.0)
                self.pixmap = self.pixmap.transformed(transform)
        self.image.setPixmap(self.pixmap.scaled(
            self.thumb_size, self.thumb_size,
            Qt.KeepAspectRatio, Qt.SmoothTransformation))
        return result

    def set_selected(self, value):
        self.selected = value
        if self.selected:
            self.setStyleSheet("#thumbnail {border: 2px solid red}")
        else:
            self.setStyleSheet("#thumbnail {border: 2px solid grey}")

    def get_selected(self):
        return self.selected

class ScrollArea(QtGui.QScrollArea):
    def __init__(self, parent=None, drop_callback=None):
        QtGui.QScrollArea.__init__(self, parent)
        self.drop_callback = drop_callback
        self.setAcceptDrops(True)

    def dropEvent(self, event):
        if not self.drop_callback:
            return
        file_list = []
        for uri in event.mimeData().urls():
            file_list.append(str(uri.toLocalFile()))
        if not file_list:
            return
        self.drop_callback(file_list)
        event.acceptProposedAction()

    def dragEnterEvent(self, event):
        if self.drop_callback and event.mimeData().hasFormat('text/uri-list'):
            event.acceptProposedAction()

class ImageList(QtGui.QWidget):
    def __init__(self, config_store, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.config_store = config_store
        self.app = QtGui.QApplication.instance()
        self.path_list = list()
        self.image = dict()
        self.last_selected = None
        self.selection_anchor = None
        self.thumb_size = int(self.config_store.get(
            'controls', 'thumb_size', '80'))
        layout = QtGui.QGridLayout()
        layout.setSpacing(0)
        layout.setRowStretch(0, 1)
        layout.setColumnStretch(3, 1)
        self.setLayout(layout)
        layout.setMargin(0)
        # thumbnail display
        self.scroll_area = ScrollArea(drop_callback=self.open_file_list)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll_area.setWidgetResizable(True)
        layout.addWidget(self.scroll_area, 0, 0, 1, 6)
        self.thumbnails = QtGui.QWidget()
        self.thumbnails.setLayout(FlowLayout(hSpacing=0, vSpacing=0))
        self.scroll_area.setWidget(self.thumbnails)
        QtGui.QShortcut(QtGui.QKeySequence.MoveToPreviousChar,
                        self.scroll_area, self.move_to_prev_thumb)
        QtGui.QShortcut(QtGui.QKeySequence.MoveToNextChar,
                        self.scroll_area, self.move_to_next_thumb)
        QtGui.QShortcut(QtGui.QKeySequence.SelectPreviousChar,
                        self.scroll_area, self.select_prev_thumb)
        QtGui.QShortcut(QtGui.QKeySequence.SelectNextChar,
                        self.scroll_area, self.select_next_thumb)
        QtGui.QShortcut(QtGui.QKeySequence.SelectAll,
                        self.scroll_area, self.select_all)
        # sort key selector
        layout.addWidget(QtGui.QLabel('sort by: '), 1, 0)
        self.sort_name = QtGui.QRadioButton('file name')
        self.sort_name.clicked.connect(self._new_sort_order)
        layout.addWidget(self.sort_name, 1, 1)
        self.sort_date = QtGui.QRadioButton('date taken')
        layout.addWidget(self.sort_date, 1, 2)
        self.sort_date.clicked.connect(self._new_sort_order)
        if eval(self.config_store.get('controls', 'sort_date', 'False')):
            self.sort_date.setChecked(True)
        else:
            self.sort_name.setChecked(True)
        # size selector
        layout.addWidget(QtGui.QLabel('thumbnail size: '), 1, 4)
        self.size_slider = QtGui.QSlider(Qt.Horizontal)
        self.size_slider.setTracking(False)
        self.size_slider.setRange(4, 9)
        self.size_slider.setPageStep(1)
        self.size_slider.setValue(self.thumb_size / 20)
        self.size_slider.setTickPosition(QtGui.QSlider.TicksBelow)
        self.size_slider.setMinimumWidth(140)
        self.size_slider.valueChanged.connect(self._new_thumb_size)
        layout.addWidget(self.size_slider, 1, 5)

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
        types = []
        if sys.version_info[0] >= 3:
            for ext in QtGui.QImageReader.supportedImageFormats():
                types.append('*.%s' % str(ext, encoding='utf_8'))
        else:
            for ext in QtGui.QImageReader.supportedImageFormats():
                types.append('*.%s' % str(ext))
        path_list = QtGui.QFileDialog.getOpenFileNames(
            self, "Open files", self.config_store.get('paths', 'images', ''),
            "Images (%s);;All files (*)" % ' '.join(types))
        if sys.version_info[0] < 3:
            path_list = map(lambda x: x.toLocal8Bit(), path_list)
        # work around for Qt bug 33992
        # https://bugreports.qt-project.org/browse/QTBUG-33992
        path_list = map(lambda x: str(
            QtCore.QUrl.fromPercentEncoding(x)), path_list)
        if not path_list:
            return
        self.open_file_list(path_list)

    image_list_changed = QtCore.pyqtSignal()
    def open_file_list(self, path_list):
        self.config_store.set(
            'paths', 'images', os.path.dirname(path_list[0]))
        for path in path_list:
            if path in self.path_list:
                continue
            self.path_list.append(path)
            image = Image(path, self, thumb_size=self.thumb_size)
            self.image[path] = image
        self._show_thumbnails()

    def _date_key(self, idx):
        result = self.image[idx].metadata.get_item('date_taken')
        if result.empty():
            result = self.image[idx].metadata.get_item('date_digitised')
        if result.empty():
            result = self.image[idx].metadata.get_item('date_modified')
        if result.empty():
            # use file date as last resort
            result = datetime.fromtimestamp(
                os.path.getmtime(self.image[idx].path))
        else:
            result = result.value
        return result

    sort_order_changed = QtCore.pyqtSignal()
    def _new_sort_order(self):
        self._show_thumbnails()
        self.sort_order_changed.emit()

    def _show_thumbnails(self):
        sort_date = self.sort_date.isChecked()
        self.config_store.set('controls', 'sort_date', str(sort_date))
        if sort_date:
            self.path_list.sort(key=self._date_key)
        else:
            self.path_list.sort()
        layout = self.thumbnails.layout()
        for path in self.path_list:
            image = self.image[path]
            layout.addWidget(image)
            if image.load_thumbnail():
                self.app.processEvents()
                self.scroll_area.ensureWidgetVisible(image)
                self.app.processEvents()
        if self.last_selected:
            self.app.processEvents()
            self.scroll_area.ensureWidgetVisible(self.image[self.last_selected])
        self.image_list_changed.emit()

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

    new_metadata = QtCore.pyqtSignal(bool)
    @QtCore.pyqtSlot()
    def save_files(self):
        if_mode = eval(self.config_store.get('files', 'image', 'True'))
        sc_mode = self.config_store.get('files', 'sidecar', 'auto')
        unsaved = False
        for path in list(self.path_list):
            image = self.image[path]
            image.metadata.save(if_mode, sc_mode)
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
        dialog = QtGui.QMessageBox()
        dialog.setWindowTitle('Photini: unsaved data')
        dialog.setText('<h3>Some images have unsaved metadata.</h3>')
        dialog.setInformativeText('Do you want to save your changes?')
        dialog.setIcon(QtGui.QMessageBox.Warning)
        buttons = QtGui.QMessageBox.Save
        if with_cancel:
            buttons |= QtGui.QMessageBox.Cancel
        if with_discard:
            buttons |= QtGui.QMessageBox.Discard
        dialog.setStandardButtons(buttons)
        dialog.setDefaultButton(QtGui.QMessageBox.Save)
        result = dialog.exec_()
        if result == QtGui.QMessageBox.Save:
            self.save_files()
            return True
        return result == QtGui.QMessageBox.Discard

    def get_selected_images(self):
        selection = list()
        for path in self.path_list:
            image = self.image[path]
            if image.get_selected():
                selection.append(image)
        return selection

    selection_changed = QtCore.pyqtSignal(list)
    def emit_selection(self):
        self.selection_changed.emit(self.get_selected_images())

    def thumb_mouse_press(self, path, event):
        path = str(path)
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
