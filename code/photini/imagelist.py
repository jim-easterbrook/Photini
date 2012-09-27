##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import os

import pyexiv2
from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt

from flowlayout import FlowLayout

class Image(QtGui.QFrame):
    def __init__(self, path, image_list, thumb_size=80, parent=None):
        QtGui.QFrame.__init__(self, parent)
        self.path = path
        self.image_list = image_list
        self.name = os.path.splitext(os.path.basename(self.path))[0]
        self.selected = False
        self.pixmap = None
        self.thumb_size = thumb_size
        # read metadata
        self.metadata = pyexiv2.ImageMetadata(self.path)
        self.metadata.read()
        self.metadata_changed = False
        layout = QtGui.QGridLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(3, 3, 3, 3)
        self.setLayout(layout)
        # label to display image
        self.image = QtGui.QLabel()
        self.image.setFixedSize(self.thumb_size, self.thumb_size)
        self.image.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        layout.addWidget(self.image, 0, 0, 1, 2)
        # label to display file name
        self.label = QtGui.QLabel(self.name)
        self.label.setAlignment(Qt.AlignRight)
        layout.addWidget(self.label, 1, 1)
        # label to display status
        self.status = QtGui.QLabel()
        self.status.setAlignment(Qt.AlignLeft)
        layout.addWidget(self.status, 1, 0)
        self.setFrameStyle(QtGui.QFrame.Panel | QtGui.QFrame.Plain)
        self.setObjectName("thumbnail")
        self.set_selected(False)
        self.show_status()

    def mousePressEvent(self, event):
        self.image_list.thumb_mouse_press(self.path, event)

    def save_metadata(self):
        if not self.metadata_changed:
            return
        self.metadata.write()
        self.metadata_changed = False
        self.show_status()

    def show_status(self):
        status = u''
        # set 'geotagged' status
        if (('Xmp.exif.GPSLatitude' in self.metadata.xmp_keys) or
            ('Exif.GPSInfo.GPSLatitude' in self.metadata.exif_keys)):
            status += unichr(0x2690)
        # set 'unsaved' status
        if self.metadata_changed:
            status += unichr(0x26A1)
        self.status.setText(status)

    def get_metadata(self, keys):
        # Turn every type of text data into a list of unicode strings.
        # Let caller decide what it means.
##            print '### exif'
##            for key in self.metadata.exif_keys:
##                try:
##                    print key, self.metadata[key].value
##                except:
##                    pass
##            print '### iptc'
##            for key in self.metadata.iptc_keys:
##                print key, self.metadata[key].value
##            print '### xmp'
##            for key in self.metadata.xmp_keys:
##                print key, self.metadata[key].value
        for key in keys:
            if key in self.metadata.xmp_keys:
                item = self.metadata[key]
                if item.type.split()[0] in ('bag', 'seq'):
                    return item.value
                if item.type == 'Lang Alt':
                    return item.value.values()
                if item.type == 'GPSCoordinate':
                    degrees = (float(item.value.degrees) +
                              (float(item.value.minutes) / 60.0) +
                              (float(item.value.seconds) / 3600.0))
                    if item.value.direction in ('S', 'W'):
                        degrees = -degrees
                    return degrees
                print key, item.type, item.value
                return item.value
            if key in self.metadata.iptc_keys:
                return map(lambda x: unicode(x, 'iso8859_1'),
                           self.metadata[key].value)
            if key in self.metadata.exif_keys:
                return [unicode(self.metadata[key].value, 'iso8859_1')]
        return None

    def set_metadata(self, keys, value):
        if value == self.get_metadata(keys):
            return
        for key in keys:
            standard = key.split('.')[0]
            if standard == 'Xmp':
                new_tag = pyexiv2.XmpTag(key)
                if new_tag.type.split()[0] in ('bag', 'seq'):
                    new_tag = pyexiv2.XmpTag(key, value)
                elif new_tag.type == 'Lang Alt':
                    new_tag = pyexiv2.XmpTag(key, {'': value[0]})
                else:
                    raise KeyError("Unknown type %s" % new_tag.type)
                self.metadata[key] = new_tag
            elif standard == 'Iptc':
                self.metadata[key] = pyexiv2.IptcTag(key, value)
            elif standard == 'Exif':
                self.metadata[key] = pyexiv2.ExifTag(key, value[0])
        self.metadata_changed = True
        self.show_status()
        self.image_list.new_metadata.emit(True)

    def set_thumb_size(self, thumb_size):
        self.thumb_size = thumb_size
        self.image.setFixedSize(self.thumb_size, self.thumb_size)

    def load_thumbnail(self):
        if not self.pixmap:
            self.pixmap = QtGui.QPixmap(self.path)
            if max(self.pixmap.width(), self.pixmap.height()) > 400:
                # store a scaled down version of image to save memory
                self.pixmap = self.pixmap.scaled(
                    400, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image.setPixmap(self.pixmap.scaled(
            self.thumb_size, self.thumb_size,
            Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def set_selected(self, value):
        self.selected = value
        if self.selected:
            self.setStyleSheet("#thumbnail {border: 2px solid red}")
        else:
            self.setStyleSheet("#thumbnail {border: 2px solid grey}")

    def get_selected(self):
        return self.selected

class ImageList(QtGui.QWidget):
    def __init__(self, config_store, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.config_store = config_store
        self.path_list = list()
        self.image = dict()
        self.last_selected = None
        self.selection_anchor = None
        self.thumb_size = int(self.config_store.get(
            'controls', 'thumb_size', '80'))
        layout = QtGui.QGridLayout()
        layout.setSpacing(0)
        layout.setRowStretch(0, 1)
        layout.setColumnStretch(0, 1)
        self.setLayout(layout)
        layout.setMargin(0)
        # thumbnail display
        self.scroll_area = QtGui.QScrollArea()
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll_area.setWidgetResizable(True)
        layout.addWidget(self.scroll_area, 0, 0, 1, 3)
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
        # size selector
        layout.addWidget(QtGui.QLabel('thumbnail size: '), 1, 1)
        self.size_slider = QtGui.QSlider(Qt.Horizontal)
        self.size_slider.setTracking(False)
        self.size_slider.setRange(4, 9)
        self.size_slider.setPageStep(1)
        self.size_slider.setValue(self.thumb_size / 20)
        self.size_slider.setTickPosition(QtGui.QSlider.TicksBelow)
        self.size_slider.setMinimumWidth(140)
        self.size_slider.valueChanged.connect(self._new_thumb_size)
        layout.addWidget(self.size_slider, 1, 2)

    def mousePressEvent(self, event):
        if self.scroll_area.underMouse():
            self._clear_selection()
            self.last_selected = None
            self.selection_anchor = None
            self.emit_selection()

    @QtCore.pyqtSlot()
    def open_files(self):
        path_list = map(str, QtGui.QFileDialog.getOpenFileNames(
            self, "Open files", self.config_store.get('paths', 'images', ''),
            "Images (*.png *.jpg)"))
        if not path_list:
            return
        self.config_store.set(
            'paths', 'images', os.path.dirname(path_list[0]))
        layout = self.thumbnails.layout()
        for path in reversed(self.path_list):
            layout.removeWidget(self.image[path])
        for path in path_list:
            if path in self.path_list:
                continue
            self.path_list.append(path)
            image = Image(path, self, thumb_size=self.thumb_size)
            self.image[path] = image
        self.path_list.sort()
        for path in self.path_list:
            image = self.image[path]
            layout.addWidget(image)
            image.load_thumbnail()
            QtGui.qApp.processEvents()
            self.scroll_area.ensureWidgetVisible(image)
            QtGui.qApp.processEvents()
        if self.last_selected:
            self.scroll_area.ensureWidgetVisible(self.image[self.last_selected])

    @QtCore.pyqtSlot()
    def close_files(self):
        self._remove(False)

    @QtCore.pyqtSlot()
    def close_all_files(self):
        self._remove(True)

    def _remove(self, all_files):
        layout = self.thumbnails.layout()
        for path in list(self.path_list):
            image = self.image[path]
            if all_files or image.get_selected():
                self.path_list.remove(path)
                del self.image[path]
                layout.removeWidget(image)
                image.setParent(None)
        self.emit_selection()

    new_metadata = QtCore.pyqtSignal(bool)
    @QtCore.pyqtSlot()
    def save_files(self):
        for path in list(self.path_list):
            image = self.image[path].save_metadata()
        self.new_metadata.emit(False)

    selection_changed = QtCore.pyqtSignal(list)
    def emit_selection(self):
        selection = list()
        for path in self.path_list:
            image = self.image[path]
            if image.get_selected():
                selection.append(image)
        self.selection_changed.emit(selection)

    def thumb_mouse_press(self, path, event):
        path = str(path)
        if event.modifiers() == Qt.ControlModifier:
            self._select_thumb(path, multiple_selection=True)
        elif event.modifiers() == Qt.ShiftModifier:
            self._select_thumb(path, extend_selection=True)
        else:
            self._select_thumb(path)

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
        self._select_thumb(path, extend_selection=extend_selection)

    @QtCore.pyqtSlot()
    def _new_thumb_size(self):
        self.thumb_size = self.size_slider.value() * 20
        self.config_store.set('controls', 'thumb_size', str(self.thumb_size))
        for path in self.path_list:
            image = self.image[path]
            image.set_thumb_size(self.thumb_size)
            image.load_thumbnail()

    def _select_thumb(
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
