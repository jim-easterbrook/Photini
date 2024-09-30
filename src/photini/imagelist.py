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

from datetime import datetime
import io
import logging
import os
import time

import PIL.Image as PIL

from photini.ffmpeg import FFmpeg
from photini.metadata import Metadata
from photini.pyqt import *
from photini.pyqt import (image_types, image_types_lower, qt_version_info,
                          set_symbol_font, video_types, video_types_lower)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate
DRAG_MIMETYPE = 'application/x-photini-image'


class Image(QtWidgets.QFrame):
    styles = ('''
QFrame {background: palette(base); color: palette(dark)}
QLabel {background: palette(base); color: palette(text)}''',
              '''
QFrame {background: palette(highlight); color: palette(dark)}
QLabel {background: palette(highlight); color: palette(highlighted-text)}''')

    def __init__(self, path, thumb_size=4, *arg, **kw):
        super(Image, self).__init__(*arg, **kw)
        self.app = QtWidgets.QApplication.instance()
        self.path = path
        self.name, ext = os.path.splitext(os.path.basename(self.path))
        self.selected = False
        # read metadata
        self.metadata = Metadata(self.path, notify=self.show_status)
        self.file_times = (os.path.getatime(self.path),
                           os.path.getmtime(self.path))
        # set file type
        self.file_type = self.metadata.mime_type
        # sub widgets
        layout = QtWidgets.QGridLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(3, 3, 3, 3)
        self.setLayout(layout)
        self.setToolTip('<p>' + self.path + '</p>')
        # label to display image
        self.image = QtWidgets.QLabel()
        self.image.setWordWrap(True)
        self.image.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.image, 0, 0, 1, 2)
        # label to display file name
        self.label = QtWidgets.QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignRight)
        scale_font(self.label, 80)
        layout.addWidget(self.label, 1, 1)
        # label to display status
        self.status = QtWidgets.QLabel()
        self.status.setAlignment(Qt.AlignmentFlag.AlignLeft)
        set_symbol_font(self.status)
        scale_font(self.status, 80)
        layout.addWidget(self.status, 1, 0)
        self.setFrameStyle(
            QtWidgets.QFrame.Shape.Panel | QtWidgets.QFrame.Shadow.Plain)
        self.setLineWidth(max(1, width_for_text(self, 'X' * 10) // 40))
        self.set_selected(False)
        self.show_status(False)
        self._set_thumb_size(thumb_size)

    def reload_metadata(self):
        self.metadata = Metadata(self.path, notify=self.show_status)
        self.show_status(False)
        self.load_thumbnail()
        self.app.image_list.emit_selection()

    def transform(self, pixmap, orientation):
        transform = orientation and orientation.get_transform()
        if not transform:
            return pixmap
        return pixmap.transformed(transform)

    def regenerate_thumbnail(self):
        # DCF spec says thumbnail must be 160 x 120, so other aspect
        # ratios are padded with black
        # try using PIL first, good quality and quick
        qt_im = self.get_qt_image()
        if qt_im:
            data = self.make_thumb_PIL(qt_im)
            if data:
                self.metadata.thumbnail = {'data': data}
                return True
        # next try using FFmpeg, good quality but slower
        data = self.make_thumb_ffmpeg()
        if data:
            self.metadata.thumbnail = {'data': data}
            return True
        # lastly use Qt, quick but not high quality
        if qt_im:
            qt_im = self.make_thumb_Qt(qt_im)
            if qt_im:
                self.metadata.thumbnail = {'image': qt_im}
                return True
        return False

    def make_thumb_ffmpeg(self):
        # get input dimensions
        dims = self.metadata.dimensions
        if not dims:
            return None
        width = dims['width']
        height = dims['height']
        duration = self.metadata.video_duration or 0
        skip = int(min(duration / 2, 10.0))
        # target dimensions
        w, h = 160, 120
        if width < height:
            w, h = h, w
        # use ffmpeg to make scaled, padded, single frame JPEG
        quality = 1
        while True:
            try:
                data = FFmpeg.make_thumbnail(self.path, w, h, skip, quality)
            except Exception as ex:
                logger.error(str(ex))
                return None
            if not data or len(data) < 50000:
                break
            quality += 1
        return data

    def get_qt_image(self):
        qt_im = self.metadata.get_image_pixmap()
        if not qt_im:
            return None
        w = qt_im.width()
        h = qt_im.height()
        if max(w, h) > 1000:
            # use Qt's scaling (not high quality) to pre-shrink large
            # images
            qt_im = qt_im.scaled(
                1000, 1000, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            w = qt_im.width()
            h = qt_im.height()
        # pad image to 4:3 (or 3:4) aspect ratio
        if w >= h:
            new_h = int(0.5 + (float(w * 3) / 4.0))
            new_w = int(0.5 + (float(h * 4) / 3.0))
        else:
            new_h = int(0.5 + (float(w * 4) / 3.0))
            new_w = int(0.5 + (float(h * 3) / 4.0))
        if new_w > w:
            pad = (new_w - w) // 2
            qt_im = qt_im.copy(-pad, 0, new_w, h)
        elif new_h > h:
            pad = (new_h - h) // 2
            qt_im = qt_im.copy(0, -pad, w, new_h)
        return qt_im

    def make_thumb_PIL(self, qt_im):
        w, h = 160, 120
        if qt_im.width() < qt_im.height():
            w, h = h, w
        # convert Qt image to PIL image
        buf = QtCore.QBuffer()
        buf.open(buf.OpenModeFlag.WriteOnly)
        qt_im.save(buf, 'PPM')
        data = io.BytesIO(buf.data().data())
        try:
            pil_im = PIL.open(data)
        except Exception as ex:
            logger.error(ex)
            return None
        # scale PIL image
        pil_im.thumbnail((w, h), PIL.LANCZOS)
        # save image to memory
        data = io.BytesIO()
        pil_im.save(data, 'JPEG')
        return data.getvalue()

    def make_thumb_Qt(self, qt_im):
        w, h = 160, 120
        if qt_im.width() < qt_im.height():
            w, h = h, w
        # scale Qt image - not as good quality as PIL
        return qt_im.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)

    @catch_all
    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu(self)
        self.app.image_list.add_selected_actions(menu)
        execute(menu, event.globalPos())

    @catch_all
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if qt_version_info >= (6, 0):
                self.drag_start_pos = event.position()
            else:
                self.drag_start_pos = event.pos()

    @catch_all
    def mouseReleaseEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.app.image_list.select_image(self, multiple_selection=True)
        elif event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
            self.app.image_list.select_image(self, extend_selection=True)
        else:
            self.app.image_list.select_image(self)

    @catch_all
    def mouseMoveEvent(self, event):
        if not self.app.image_list.drag_icon:
            return
        if qt_version_info >= (6, 0):
            pos = event.position()
        else:
            pos = event.pos()
        if ((pos - self.drag_start_pos).manhattanLength() <
                                    QtWidgets.QApplication.startDragDistance()):
            return
        if not self.get_selected():
            # user has started dragging an unselected image
            self.app.image_list.select_image(self, emit_selection=False)
        paths = []
        for image in self.app.image_list.get_selected_images():
            paths.append(image.path)
        if not paths:
            return
        drag = QtGui.QDrag(self)
        # construct icon
        count = min(len(paths), 8)
        src_icon = self.app.image_list.drag_icon
        src_w = src_icon.width()
        src_h = src_icon.height()
        margin = (count - 1) * 4
        if count == 1:
            icon = src_icon
        else:
            icon = QtGui.QPixmap(src_w + margin, src_h + margin)
            icon.fill(Qt.GlobalColor.transparent)
            try:
                paint = QtGui.QPainter(icon)
                for i in range(count):
                    paint.drawPixmap(
                        QtCore.QPoint(margin - (i * 4), i * 4), src_icon)
            finally:
                del paint
        drag.setPixmap(icon)
        drag.setHotSpot(QtCore.QPoint(src_w // 2, src_h + margin))
        mimeData = QtCore.QMimeData()
        mimeData.setData(DRAG_MIMETYPE, repr(paths).encode('utf-8'))
        drag.setMimeData(mimeData)
        if execute(drag,
                   Qt.DropAction.CopyAction) == Qt.DropAction.IgnoreAction:
            # image wasn't dragged to map
            self.app.image_list.emit_selection()

    @catch_all
    def mouseDoubleClickEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.NoModifier:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(self.path))

    def show_status(self, changed):
        status = ''
        # set 'geotagged' status
        if self.metadata.gps_info['exif:GPSLatitude']:
            status += chr(0x2690)
        # set 'unsaved' status
        if changed:
            status += chr(0x26A1)
        self.status.setText(status)
        self._elide_name()
        if changed:
            self.app.image_list.new_metadata.emit(True)

    def _elide_name(self):
        self.status.adjustSize()
        elided_name = self.label.fontMetrics().elidedText(
            self.name, Qt.TextElideMode.ElideLeft,
            self.image.width() - self.status.width())
        self.label.setText(elided_name)

    def _set_thumb_size(self, thumb_size):
        width = width_for_text(self.label, 'X' * thumb_size * 20) // 6
        self.image.setFixedSize(width, width)
        self._elide_name()

    def set_thumb_size(self, thumb_size):
        self._set_thumb_size(thumb_size)
        self.load_thumbnail()

    def load_thumbnail(self, label=None):
        label = label or self.image
        image = self.metadata.thumbnail and self.metadata.thumbnail['image']
        if not image:
            label.setText(wrap_text(
                label, translate('ImageList', 'No thumbnail in file'), lines=4))
            return
        pixmap = QtGui.QPixmap.fromImage(image)
        pixmap = self.transform(pixmap, self.metadata.orientation)
        rect = label.contentsRect()
        label.setPixmap(
            pixmap.scaled(rect.width(), rect.height(),
                          Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation))

    def set_selected(self, value):
        self.selected = value
        self.setStyleSheet(self.styles[self.selected])

    def get_selected(self):
        return self.selected


class ScrollArea(QtWidgets.QScrollArea):
    dropped_images = QtSignal(list)

    def __init__(self, image_list=None, parent=None):
        super(ScrollArea, self).__init__(parent)
        self.image_list = image_list
        self.setWidgetResizable(True)
        self.setAcceptDrops(True)
        widget = QtWidgets.QWidget()
        self.thumbs = ThumbsLayout(scroll_area=self)
        widget.setLayout(self.thumbs)
        self.setWidget(widget)
        # adopt some layout methods & signals
        self.add_widget = self.thumbs.addWidget
        self.remove_widget = self.thumbs.removeWidget

    @catch_all
    def ensureWidgetVisible(self, widget):
        left, top, right, bottom = self.thumbs.getContentsMargins()
        super(ScrollArea, self).ensureWidgetVisible(
            widget, max(left, right), max(top, bottom))

    @catch_all
    def dropEvent(self, event):
        file_list = []
        for uri in event.mimeData().urls():
            file_list.append(uri.toLocalFile())
        if file_list:
            self.dropped_images.emit(file_list)

    @catch_all
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat('text/uri-list'):
            event.acceptProposedAction()

    @catch_all
    def resizeEvent(self, event):
        super(ScrollArea, self).resizeEvent(event)
        self.thumbs.do_layout()

    def usable_size(self):
        rect = self.contentsRect()
        width = rect.width() - self.verticalScrollBar().sizeHint().width()
        height = rect.height() - self.horizontalScrollBar().sizeHint().height()
        return width, height

    def set_minimum_height(self, min_height):
        bar = self.horizontalScrollBar()
        if bar.isVisible():
            min_height += bar.height()
        margins = self.contentsMargins()
        self.setMinimumHeight(min_height + margins.top() + margins.bottom())

    @QtSlot()
    @catch_all
    def multi_row_changed(self):
        if self.image_list.last_selected:
            self.ensureWidgetVisible(self.image_list.last_selected)


class ThumbsLayout(QtWidgets.QLayout):
    """Multi-row fixed-width or single-row variable-width grid of
    thumbnail widgets, according to height.

    """
    def __init__(self, scroll_area=None, **kw):
        super(ThumbsLayout, self).__init__(**kw)
        self.scroll_area = scroll_area
        self.item_list = []
        self.multi_row = None
        self.do_layout()

    def addItem(self, item):
        self.item_list.append(item)

    def horizontalSpacing(self):
        return 0

    def verticalSpacing(self):
        return 0

    def count(self):
        return len(self.item_list)

    def itemAt(self, idx):
        if idx < 0 or idx >= len(self.item_list):
            return None
        return self.item_list[idx]

    def takeAt(self, idx):
        if idx < 0 or idx >= len(self.item_list):
            return None
        return self.item_list.pop(idx)

    def expandingDirections(self):
        return 0

    def hasHeightForWidth(self):
        return False

    @catch_all
    def setGeometry(self, rect):
        super(ThumbsLayout, self).setGeometry(rect)
        self.do_layout(rect)

    def sizeHint(self):
        return self.size_hint

    def minimumSize(self):
        return self.size_hint

    def do_layout(self, rect=None):
        left, top, right, bottom = self.getContentsMargins()
        width_hint = left + right
        height_hint = top + bottom
        if self.item_list and self.scroll_area:
            item_size = self.item_list[0].sizeHint()
            overlap = self.item_list[0].widget().lineWidth()
            item_h = item_size.height() - overlap
            item_w = item_size.width() - overlap
            width_hint += overlap
            height_hint += overlap
            row_height = item_h + height_hint
            self.scroll_area.set_minimum_height(row_height)
            view_width, view_height = self.scroll_area.usable_size()
            multi_row = view_height > row_height
            if multi_row != self.multi_row:
                self.multi_row = multi_row
                # make selected item visible after redrawing has finished
                QtCore.QTimer.singleShot(0, self.scroll_area.multi_row_changed)
            if multi_row:
                columns = max((view_width - width_hint) // item_w, 1)
                rows = (len(self.item_list) + columns - 1) // columns
            else:
                columns = len(self.item_list)
                rows = 1
            width_hint += columns * item_w
            height_hint += rows * item_h
        self.size_hint = QtCore.QSize(width_hint, height_hint)
        widget = self.parentWidget()
        if widget:
            widget.setMinimumSize(self.size_hint)
        if not (rect and self.item_list):
            return
        if QtWidgets.QApplication.isRightToLeft():
            x = rect.right() - right - item_w
            item_w = -item_w
        else:
            x = rect.left() + left
        y = rect.top() + top
        for n, item in enumerate(self.item_list):
            i, j = n % columns, n // columns
            item.setGeometry(QtCore.QRect(
                QtCore.QPoint(x + (i * item_w), y + (j * item_h)), item_size))


class ImageList(QtWidgets.QWidget):
    image_list_changed = QtSignal()
    new_metadata = QtSignal(bool)
    selection_changed = QtSignal(list)
    sort_order_changed = QtSignal()

    def __init__(self, parent=None):
        super(ImageList, self).__init__(parent)
        self.app = QtWidgets.QApplication.instance()
        self.drag_icon = None
        self.images = []
        self.last_selected = None
        self.selection_anchor = None
        self.thumb_size = self.app.config_store.get('controls', 'thumb_size', 4)
        if self.thumb_size > 20:
            # old config, in pixels
            self.thumb_size = self.thumb_size // 20
        # thumbnail display
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.scroll_area = ScrollArea(image_list=self)
        self.scroll_area.dropped_images.connect(self.open_file_list)
        self.layout().addWidget(self.scroll_area)
        QtGui2.QShortcut(QtGui.QKeySequence.StandardKey.MoveToPreviousChar,
                         self.scroll_area, self.move_to_prev_thumb)
        QtGui2.QShortcut(QtGui.QKeySequence.StandardKey.MoveToNextChar,
                         self.scroll_area, self.move_to_next_thumb)
        QtGui2.QShortcut(QtGui.QKeySequence.StandardKey.MoveToStartOfLine,
                         self.scroll_area, self.move_to_first_thumb)
        QtGui2.QShortcut(QtGui.QKeySequence.StandardKey.MoveToEndOfLine,
                         self.scroll_area, self.move_to_last_thumb)
        QtGui2.QShortcut(QtGui.QKeySequence.StandardKey.SelectPreviousChar,
                         self.scroll_area, self.select_prev_thumb)
        QtGui2.QShortcut(QtGui.QKeySequence.StandardKey.SelectNextChar,
                         self.scroll_area, self.select_next_thumb)
        QtGui2.QShortcut(QtGui.QKeySequence.StandardKey.SelectAll,
                         self.scroll_area, self.select_all)
        # sort key selector
        bottom_bar = QtWidgets.QHBoxLayout()
        self.layout().addLayout(bottom_bar)
        bottom_bar.addWidget(QtWidgets.QLabel(
            translate('ImageList', 'Sort by')))
        self.sort_name = QtWidgets.QRadioButton(
            translate('ImageList', 'file name'))
        self.sort_name.clicked.connect(self._new_sort_order)
        bottom_bar.addWidget(self.sort_name)
        self.sort_date = QtWidgets.QRadioButton(
            translate('ImageList', 'date taken'))
        self.sort_date.clicked.connect(self._new_sort_order)
        bottom_bar.addWidget(self.sort_date)
        if self.app.config_store.get('controls', 'sort_date', False):
            self.sort_date.setChecked(True)
        else:
            self.sort_name.setChecked(True)
        # size selector
        bottom_bar.addStretch(1)
        bottom_bar.addWidget(QtWidgets.QLabel(
            translate('ImageList', 'Thumbnail size')))
        self.size_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setTracking(False)
        self.size_slider.setRange(4, 9)
        self.size_slider.setPageStep(1)
        self.size_slider.setValue(self.thumb_size)
        self.size_slider.setTickPosition(
            QtWidgets.QSlider.TickPosition.TicksBelow)
        self.size_slider.setMinimumWidth(
            width_for_text(self.size_slider, 'x' * 20))
        self.size_slider.valueChanged.connect(self._new_thumb_size)
        bottom_bar.addWidget(self.size_slider)

    def set_drag_to_map(self, icon):
        self.drag_icon = icon

    def get_image(self, path):
        for image in self.images:
            if image.path == path:
                return image
        return None

    def get_images(self):
        return self.images

    @catch_all
    def mousePressEvent(self, event):
        if self.scroll_area.underMouse():
            self._clear_selection()
            self.last_selected = None
            self.selection_anchor = None
            self.emit_selection()

    @QtSlot(bool)
    @catch_all
    def open_files(self, checked=False):
        args = [
            self,
            translate('ImageList', 'Open files'),
            self.app.config_store.get('paths', 'images', ''),
            translate('ImageList',
                      "Images ({0});;Videos ({1});;All files (*)").format(
                          ' '.join(['*.' + x for x in image_types()]),
                          ' '.join(['*.' + x for x in video_types()]))
            ]
        if not self.app.config_store.get('pyqt', 'native_dialog', True):
            args += [None, QtWidgets.QFileDialog.Option.DontUseNativeDialog]
        path_list = QtWidgets.QFileDialog.getOpenFileNames(*args)
        path_list = path_list[0]
        if not path_list:
            return
        self.open_file_list(path_list, select=False)

    @QtSlot(list)
    @catch_all
    def open_file_list(self, path_list, select=True):
        dir_list = []
        opened_images = []
        with Busy():
            opened_images = self._open_file_list(path_list, dir_list)
        if opened_images:
            self.done_opening(opened_images[-1].path)
            if select:
                self.select_images(opened_images)

    def _open_file_list(self, path_list, dir_list, types=None):
        opened_images = []
        for path in path_list:
            if os.path.basename(path).startswith('.'):
                # don't open .directory or .thumbs
                continue
            if os.path.isdir(path):
                types = types or ['.' + x for x in
                                  (image_types_lower() + video_types_lower())]
                path = os.path.realpath(path)
                if path in dir_list:
                    # don't open directories we've already opened
                    continue
                dir_list.append(path)
                files = [os.path.join(path, x) for x in os.listdir(path)]
                files = [x for x in files if os.path.isdir(x) or
                         os.path.splitext(x)[1].lower() in types]
                opened_images += self._open_file_list(
                    files, dir_list, types=types)
            else:
                image = self.open_file(path)
                if image:
                    opened_images.append(image)
        return opened_images

    def open_file(self, path):
        path = os.path.realpath(path)
        base, ext = os.path.splitext(path)
        if ext.lower() == '.xmp':
            if os.path.isfile(base):
                path = base
            else:
                dir_name = os.path.dirname(path)
                for file in os.listdir(dir_name):
                    path = os.path.join(dir_name, file)
                    b, e = os.path.splitext(path)
                    if b == base and e.lower() != '.xmp':
                        break
                else:
                    return None
        if not os.path.isfile(path):
            return None
        # may have already opened this path
        image = self.get_image(path)
        if not image:
            image = Image(path, thumb_size=self.thumb_size)
            self.images.append(image)
            self.show_thumbnail(image)
        return image

    def done_opening(self, path):
        self.app.config_store.set(
            'paths', 'images', os.path.dirname(os.path.abspath(path)))
        self._sort_thumbnails()

    def _date_key(self, image):
        result = (image.metadata.date_taken or image.metadata.date_digitised
                  or image.metadata.date_modified)
        if result:
            result = result['datetime']
        else:
            # use file date as last resort
            result = datetime.fromtimestamp(os.path.getmtime(image.path))
        # convert result to string and append path so photos with same
        # time stamp get sorted consistently
        result = result.strftime('%Y%m%d%H%M%S%f') + image.path
        return result

    @QtSlot()
    @catch_all
    def _new_sort_order(self):
        self._sort_thumbnails()
        self.sort_order_changed.emit()

    def _sort_thumbnails(self):
        sort_date = self.sort_date.isChecked()
        self.app.config_store.set('controls', 'sort_date', sort_date)
        with Busy():
            if sort_date:
                self.images.sort(key=self._date_key)
            else:
                self.images.sort(key=lambda x: x.path)
            for image in self.images:
                self.show_thumbnail(image, False)
        if self.last_selected:
            self.app.processEvents()
            self.scroll_area.ensureWidgetVisible(self.last_selected)
        self.image_list_changed.emit()

    def show_thumbnail(self, image, live=True):
        self.scroll_area.add_widget(image)
        if live:
            self.app.processEvents()
        image.load_thumbnail()
        if live:
            self.app.processEvents()
            self.scroll_area.ensureWidgetVisible(image)
            self.app.processEvents()

    def add_selected_actions(self, menu):
        actions = {}
        actions['reload'] = menu.addAction('', self.reload_selected_metadata)
        actions['save'] = menu.addAction(
            translate('ImageList', 'Save changes'), self.save_selected_metadata)
        actions['diff'] = menu.addAction(
            translate('ImageList', 'View changes'), self.diff_selected_metadata)
        actions['thumbs'] = menu.addAction(
            '', self.regenerate_selected_thumbnails)
        actions['close'] = menu.addAction('', self.close_selected_files)
        self.configure_selected_actions(actions)
        return actions

    def configure_selected_actions(self, actions):
        images = self.get_selected_images()
        changed_images = any([x.metadata.changed() for x in images])
        actions['reload'].setEnabled(bool(images))
        actions['save'].setEnabled(changed_images)
        actions['diff'].setEnabled(changed_images)
        actions['thumbs'].setEnabled(bool(images))
        actions['close'].setEnabled(bool(images))

        if qt_version_info >= (6, 0):
            # pyside6-lupdate doesn't recognise plurals with 'translate'
            actions['reload'].setText(
                ImageList.tr('Reload file(s)', '', len(images)))
            actions['thumbs'].setText(
                ImageList.tr('Regenerate thumbnail(s)', '', len(images)))
            actions['close'].setText(
                ImageList.tr('Close file(s)', '', len(images)))
        else:
            # Qt5 doesn't handle ClassName.tr correctly
            actions['reload'].setText(translate(
                'ImageList', 'Reload file(s)', '', len(images)))
            actions['thumbs'].setText(translate(
                'ImageList', 'Regenerate thumbnail(s)', '', len(images)))
            actions['close'].setText(translate(
                'ImageList', 'Close file(s)', '', len(images)))

    @QtSlot()
    @catch_all
    def reload_selected_metadata(self):
        with Busy():
            for image in self.get_selected_images():
                image.reload_metadata()

    @QtSlot()
    @catch_all
    def save_selected_metadata(self):
        self._save_files(images=self.get_selected_images())

    @QtSlot()
    @catch_all
    def diff_selected_metadata(self):
        dialog = QtWidgets.QDialog(parent=self)
        dialog.setLayout(QtWidgets.QVBoxLayout())
        width = width_for_text(dialog, 'x' * 120)
        dialog.setFixedSize(min(width, self.window().width()),
                            min(width // 2, self.window().height()))
        table = QtWidgets.QTableWidget()
        table.setVerticalScrollMode(table.ScrollMode.ScrollPerPixel)
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels([translate('ImageList', 'new value'),
                                         translate('ImageList', 'undo'),
                                         translate('ImageList', 'old value')])
        table.horizontalHeader().setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        dialog.layout().addWidget(table)
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addWidget(button_box)
        changed = False
        position = None
        for image in self.get_selected_images():
            if not image.metadata.changed():
                continue
            dialog.setWindowTitle(translate(
                'ImageList', 'Metadata differences: {file_name}').format(
                    file_name=image.name))
            labels = []
            row = 0
            undo = {}
            table.clearContents()
            new_md = image.metadata
            old_md = Metadata(image.path)
            for key in ('title', 'headline', 'description', 'alt_text',
                        'alt_text_ext', 'rating', 'keywords', 'nested_tags',
                        'creator', 'creator_title', 'credit_line', 'copyright',
                        'rights', 'instructions', 'contact_info',
                        'date_taken', 'date_digitised', 'date_modified',
                        'orientation', 'camera_model', 'lens_model',
                        'focal_length', 'focal_length_35', 'aperture',
                        'gps_info', 'location_taken', 'location_shown',
                        'image_region', 'thumbnail'):
                values = getattr(new_md, key), getattr(old_md, key)
                if values[0] == values[1]:
                    continue
                values = [str(x or '') for x in values]
                table.setRowCount(row + 1)
                for n, value in enumerate(values):
                    item = QtWidgets.QTableWidgetItem(value)
                    table.setItem(row, n * 2, item)
                undo[key] = QtWidgets.QTableWidgetItem()
                undo[key].setFlags(
                    undo[key].flags() | Qt.ItemFlag.ItemIsUserCheckable)
                undo[key].setCheckState(Qt.CheckState.Unchecked)
                table.setItem(row, 1, undo[key])
                labels.append(key)
                row += 1
            if not row:
                continue
            table.setVerticalHeaderLabels(labels)
            table.resizeColumnsToContents()
            table.resizeRowsToContents()
            if position:
                dialog.move(position)
            result = execute(dialog)
            if result != QtWidgets.QDialog.DialogCode.Accepted:
                return
            position = dialog.pos()
            undo_all = True
            for key, widget in undo.items():
                if widget.checkState() == Qt.CheckState.Checked:
                    setattr(new_md, key, getattr(old_md, key))
                    changed = True
                else:
                    undo_all = False
            if undo_all:
                image.reload_metadata()
        if changed:
            self.emit_selection()

    @QtSlot()
    @catch_all
    def regenerate_selected_thumbnails(self):
        with Busy():
            for image in self.get_selected_images():
                if image.regenerate_thumbnail():
                    image.load_thumbnail()
                    self.app.processEvents()

    @QtSlot()
    @catch_all
    def fix_missing_thumbs(self):
        with Busy():
            for image in self.get_images():
                thumb = image.metadata.thumbnail
                if not thumb or not thumb['image']:
                    if image.regenerate_thumbnail():
                        image.load_thumbnail()
                        self.app.processEvents()
        self.image_list_changed.emit()

    @QtSlot()
    @catch_all
    def close_selected_files(self):
        self.close_files(False)

    @QtSlot()
    @catch_all
    def close_all_files(self):
        self.close_files(True)

    def close_files(self, all_files):
        if not self.unsaved_files_dialog(all_files=all_files):
            return
        if all_files:
            close_list = list(self.images)
        else:
            close_list = self.get_selected_images()
        if not close_list:
            return
        idx = self.images.index(close_list[0])
        for image in close_list:
            self.images.remove(image)
            self.scroll_area.remove_widget(image)
            image.setParent(None)
        if 0 <= idx < len(self.images):
            self.select_image(self.images[idx])
        else:
            self.last_selected = None
            self.selection_anchor = None
            self.emit_selection()
        self.image_list_changed.emit()

    @QtSlot(bool)
    @catch_all
    def save_files(self, checked=False):
        self._save_files(self.images)

    def _save_files(self, images=[]):
        self._flush_editing()
        if_mode = self.app.config_store.get('files', 'image', True)
        sc_mode = self.app.config_store.get('files', 'sidecar', 'auto')
        iptc_mode = self.app.config_store.get('files', 'iptc_iim', 'preserve')
        keep_time = self.app.config_store.get(
            'files', 'preserve_timestamps', 'now')
        if isinstance(keep_time, bool):
            # old config format
            keep_time = ('now', 'keep')[keep_time]
        if not images:
            images = self.images
        with Busy():
            for image in images:
                if keep_time == 'taken' and image.metadata.date_taken:
                    date_taken = image.metadata.date_taken['datetime']
                    try:
                        date_taken = date_taken.timestamp()
                    except Exception:
                        # probably a negative value on Windows
                        epoch = time.gmtime(0)
                        epoch = datetime(
                            epoch.tm_year, epoch.tm_mon, epoch.tm_mday)
                        date_taken = (date_taken - epoch).total_seconds()
                    file_times = image.file_times[0], date_taken
                elif keep_time == 'keep':
                    file_times = image.file_times
                else:
                    file_times = None
                image.metadata.save(
                    if_mode=if_mode, sc_mode=sc_mode,
                    iptc_mode=iptc_mode, file_times=file_times)
        unsaved = any([image.metadata.changed() for image in self.images])
        self.new_metadata.emit(unsaved)

    def unsaved_files_dialog(
            self, all_files=False, with_cancel=True, with_discard=True):
        """Return true if OK to continue with close or quit or whatever"""
        self._flush_editing()
        for image in self.images:
            if image.metadata.changed() and (all_files or image.selected):
                break
        else:
            return True
        dialog = QtWidgets.QMessageBox(parent=self)
        dialog.setWindowTitle(translate('ImageList', 'Photini: unsaved data'))
        dialog.setText('<h3>{}</h3>'.format(
            translate('ImageList', 'Some images have unsaved metadata.')))
        dialog.setInformativeText(
            translate('ImageList', 'Do you want to save your changes?'))
        dialog.setIcon(dialog.Icon.Warning)
        buttons = dialog.StandardButton.Save
        if with_cancel:
            buttons |= dialog.StandardButton.Cancel
        if with_discard:
            buttons |= dialog.StandardButton.Discard
        dialog.setStandardButtons(buttons)
        dialog.setDefaultButton(dialog.StandardButton.Save)
        result = execute(dialog)
        if result == dialog.StandardButton.Save:
            self._save_files()
            return True
        return result == dialog.StandardButton.Discard

    def _flush_editing(self):
        # finish any editing in progress
        current_focus = self.app.focusWidget()
        if current_focus:
            current_focus.clearFocus()

    def get_selected_images(self):
        selection = []
        for image in self.images:
            if image.get_selected():
                selection.append(image)
        return selection

    def emit_selection(self):
        self.selection_changed.emit(self.get_selected_images())

    def select_all(self):
        for image in self.images:
            image.set_selected(True)
        self.selection_anchor = None
        self.last_selected = None
        self.emit_selection()

    def move_to_prev_thumb(self):
        self._inc_selection(-1)

    def move_to_next_thumb(self):
        self._inc_selection(1)

    def move_to_first_thumb(self):
        if self.images:
            self.select_image(self.images[0])

    def move_to_last_thumb(self):
        if self.images:
            self.select_image(self.images[-1])

    def select_prev_thumb(self):
        self._inc_selection(-1, extend_selection=True)

    def select_next_thumb(self):
        self._inc_selection(1, extend_selection=True)

    def _inc_selection(self, inc, extend_selection=False):
        if not self.images:
            return
        if self.last_selected:
            idx = self.images.index(self.last_selected)
            idx = (idx + inc) % len(self.images)
        else:
            idx = 0
        self.select_image(self.images[idx], extend_selection=extend_selection)

    @QtSlot(int)
    @catch_all
    def _new_thumb_size(self, value):
        self.thumb_size = value
        self.app.config_store.set('controls', 'thumb_size', self.thumb_size)
        for image in self.images:
            image.set_thumb_size(self.thumb_size)
        if self.last_selected:
            self.app.processEvents()
            self.scroll_area.ensureWidgetVisible(self.last_selected)

    def select_image(self, image, extend_selection=False,
                     multiple_selection=False, emit_selection=True):
        self.scroll_area.ensureWidgetVisible(image)
        if extend_selection and self.selection_anchor:
            idx1 = self.images.index(self.selection_anchor)
            idx2 = self.images.index(self.last_selected)
            for i in range(min(idx1, idx2), max(idx1, idx2) + 1):
                self.images[i].set_selected(False)
            idx2 = self.images.index(image)
            for i in range(min(idx1, idx2), max(idx1, idx2) + 1):
                self.images[i].set_selected(True)
        elif multiple_selection:
            image.set_selected(not image.get_selected())
            self.selection_anchor = image
        else:
            self._clear_selection()
            image.set_selected(True)
            self.selection_anchor = image
        self.last_selected = image
        if emit_selection:
            self.emit_selection()

    def select_images(self, images):
        self._clear_selection()
        if not images:
            self.last_selected = None
            self.selection_anchor = None
            self.emit_selection()
            return
        for image in images:
            image.set_selected(True)
            self.scroll_area.ensureWidgetVisible(image)
        self.selection_anchor = images[0]
        self.last_selected = images[-1]
        self.emit_selection()

    def _clear_selection(self):
        for image in self.images:
            if image.get_selected():
                image.set_selected(False)
