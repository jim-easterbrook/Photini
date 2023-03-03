##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2023  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import re

from photini.pyqt import *
from photini.types import ImageRegionItem, LangAltDict
from photini.widgets import (
    ComboBox, Label, LangAltWidget, MultiLineEdit, SingleLineEdit, Slider)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class ImageDisplayWidget(QtWidgets.QGraphicsView):
    def __init__(self, *arg, **kw):
        super(ImageDisplayWidget, self).__init__(*arg, **kw)
        self.setScene(QtWidgets.QGraphicsScene())
        self.boundary = None

    def set_image(self, image):
        scene = self.scene()
        scene.clear()
        self.boundary = None
        if image:
            self.image_dims = image.metadata.get_sensor_size()
            reader = QtGui.QImageReader(image.path)
            pixmap = QtGui.QPixmap.fromImageReader(reader)
            if pixmap.isNull():
                w, h = 0, 0
            else:
                w, h = pixmap.width(), pixmap.height()
            # try image previews
            for data in image.metadata.get_previews():
                buf = QtCore.QBuffer()
                buf.setData(bytes(data))
                reader = QtGui.QImageReader(buf)
                reader.setAutoTransform(False)
                preview = QtGui.QPixmap.fromImageReader(reader)
                if preview.isNull():
                    continue
                preview = image.transform(preview, image.metadata.orientation)
                if preview.width() > w:
                    pixmap = preview
                break
            if pixmap.isNull():
                logger.error('%s: %s', os.path.basename(image.path),
                             reader.errorString())
                scene.addText(
                    translate('RegionsTab', 'Unreadable image format'))
            else:
                rect = self.contentsRect()
                w, h = pixmap.width(), pixmap.height()
                if w * rect.height() < h * rect.width():
                    pixmap = pixmap.scaledToWidth(
                        rect.width()
                        - self.verticalScrollBar().sizeHint().width(),
                        Qt.TransformationMode.SmoothTransformation)
                else:
                    pixmap = pixmap.scaledToHeight(
                        rect.height()
                        - self.horizontalScrollBar().sizeHint().height(),
                        Qt.TransformationMode.SmoothTransformation)
                item = QtWidgets.QGraphicsPixmapItem(pixmap)
                scene.addItem(item)
                scene.setSceneRect(item.boundingRect())

    @QtSlot(dict)
    @catch_all
    def draw_boundary(self, boundary):
        scene = self.scene()
        if self.boundary:
            scene.removeItem(self.boundary)
            self.boundary = None
        if not boundary:
            return
        rect = scene.sceneRect()
        x_scale = rect.width()
        y_scale = rect.height()
        if boundary['Iptc4xmpExt:rbUnit'] == 'pixel':
            x_scale /= self.image_dims['x']
            y_scale /= self.image_dims['y']
        pen = QtGui.QPen()
        pen.setColor(Qt.green)
        brush = QtGui.QColor(128, 230, 128, 150)
        if boundary['Iptc4xmpExt:rbShape'] == 'rectangle':
            x = float(boundary['Iptc4xmpExt:rbX']) * x_scale
            y = float(boundary['Iptc4xmpExt:rbY']) * y_scale
            w = float(boundary['Iptc4xmpExt:rbW']) * x_scale
            h = float(boundary['Iptc4xmpExt:rbH']) * y_scale
            self.boundary = scene.addRect(x, y, w, h, pen=pen, brush=brush)
        elif boundary['Iptc4xmpExt:rbShape'] == 'circle':
            r = float(boundary['Iptc4xmpExt:rbRx']) * x_scale
            x = (float(boundary['Iptc4xmpExt:rbX']) * x_scale) - r
            y = (float(boundary['Iptc4xmpExt:rbY']) * y_scale) - r
            w = r * 2
            h = r * 2
            self.boundary = scene.addEllipse(x, y, w, h, pen=pen, brush=brush)
        else:
            vertices = [(float(v['Iptc4xmpExt:rbX']) * x_scale,
                         float(v['Iptc4xmpExt:rbY']) * y_scale)
                        for v in boundary['Iptc4xmpExt:rbVertices']]
            if len(vertices) == 1:
                # single point, draw bow tie shape
                dx = rect.width() / 20.0
                x, y = vertices[0]
                vertices = [
                    (x-dx, y-dx), (x-dx, y+dx), (x+dx, y-dx), (x+dx, y+dx)]
            polygon = QtGui.QPolygonF()
            for v in vertices:
                polygon.append(QtCore.QPointF(*v))
            self.boundary = scene.addPolygon(polygon, pen=pen, brush=brush)


class EntityConceptWidget(SingleLineEdit):
    def __init__(self, key, vocab, *arg, **kw):
        super(EntityConceptWidget, self).__init__(key, *arg, **kw)
        self.setReadOnly(True)
        self._updating = False
        self.menu = QtWidgets.QMenu(parent=self)
        self.menu.setToolTipsVisible(True)
        self.actions = []
        for item in vocab:
            label = LangAltDict(item['name']).best_match()
            tip = LangAltDict(item['definition']).best_match()
            action = self.menu.addAction(label)
            action.setCheckable(True)
            action.setToolTip('<p>{}</p>'.format(tip))
            action.setData(item['uri'])
            action.toggled.connect(self._action_toggled)
            self.actions.append(action)

    def mousePressEvent(self, event):
        self.menu.popup(self.mapToGlobal(event.pos()))

    @QtSlot(bool)
    @catch_all
    def _action_toggled(self, checked):
        if self._updating:
            return
        selection = []
        for action in self.actions:
            if action.isChecked():
                selection.append(action.text())
        self.setPlainText(', '.join(selection))

    def set_value(self, value):
        value = value or []
        # extract uris and names
        uris = set()
        labels = {}
        for item in value:
            label = None
            if 'Iptc4xmpExt:Name' in item:
                label = LangAltDict(item['Iptc4xmpExt:Name']).best_match()
            if 'xmp:Identifier' in item:
                for uri in item['xmp:Identifier']:
                    uris.add(uri)
                    labels[uri] = label
        # update existing actions
        self._updating = True
        for action in self.actions:
            uri = action.data()
            if uri in uris:
                action.setChecked(True)
                if labels[uri]:
                    action.setText(labels[uri])
                uris.remove(uri)
            else:
                action.setChecked(False)
        # add new actions
        for uri in uris:
            action = self.menu.addAction(labels[uri] or uri)
            action.setCheckable(True)
            action.setToolTip('<p>{}</p>'.format(uri))
            action.setChecked(True)
            action.setData(uri)
            action.toggled.connect(self._action_toggled)
            self.actions.append(action)
        self._updating = False
        # update display
        self._action_toggled(True)


class RegionForm(QtWidgets.QScrollArea):
    name_changed = QtSignal(object, str)

    def __init__(self, *arg, **kw):
        super(RegionForm, self).__init__(*arg, **kw)
        self.setFrameStyle(QtWidgets.QFrame.Shape.NoFrame)
        self.setWidget(QtWidgets.QWidget())
        self.setWidgetResizable(True)
        layout = FormLayout(wrapped=True)
        self.widget().setLayout(layout)
        self.region = {}
        self.widgets = {}
        # name
        key = 'Iptc4xmpExt:Name'
        self.widgets[key] = LangAltWidget(key, multi_line=False)
        layout.addRow(translate('RegionsTab', 'Name'), self.widgets[key])
        self.widgets[key].edit.textChanged.connect(self.new_name)
        # identifier
        key = 'Iptc4xmpExt:rId'
        self.widgets[key] = SingleLineEdit(key)
        layout.addRow(translate('RegionsTab', 'Identifier'), self.widgets[key])
        # roles
        key = 'Iptc4xmpExt:rRole'
        self.widgets[key] = EntityConceptWidget(key, ImageRegionItem.roles)
        layout.addRow(translate('RegionsTab', 'Role'), self.widgets[key])
        # content types
        key = 'Iptc4xmpExt:rCtype'
        self.widgets[key] = EntityConceptWidget(key, ImageRegionItem.ctypes)
        layout.addRow(
            translate('RegionsTab', 'Content type'), self.widgets[key])

    def set_value(self, region):
        self.region = region
        # extend form if needed
        layout = self.widget().layout()
        for key, value in region.items():
            if key in list(self.widgets) + ['Iptc4xmpExt:RegionBoundary']:
                continue
            label = key.split(':')[-1]
            label = re.sub(r'([a-z])([A-Z])', r'\1 \2', label)
            label = label.capitalize()
            if isinstance(value, dict):
                self.widgets[key] = LangAltWidget(key, multi_line=False)
            else:
                self.widgets[key] = SingleLineEdit(key)
            layout.addRow(label, self.widgets[key])
        # set values
        for key in self.widgets:
            value = region
            for part in key.split('/'):
                if part not in value:
                    value = None
                    break
                value = value[part]
            self.widgets[key].set_value(value)

    @QtSlot()
    @catch_all
    def new_name(self):
        self.name_changed.emit(
            self, self.widgets['Iptc4xmpExt:Name'].edit.toPlainText())


class RegionTabs(QtWidgets.QTabWidget):
    new_boundary = QtSignal(dict)

    def __init__(self, *arg, **kw):
        super(RegionTabs, self).__init__(*arg, **kw)
        self.setFixedWidth(width_for_text(self, 'x' * 40))
        self.currentChanged.connect(self.tab_changed)

    def set_image(self, image):
        self.clear()
        if image:
            self.regions = image.metadata.image_region
        else:
            self.regions = []
        if not self.regions:
            self.addTab(RegionForm(), '')
            return
        for region in self.regions:
            region_form = RegionForm()
            region_form.name_changed.connect(self.tab_name_changed)
            self.addTab(region_form, '')
            region_form.set_value(region)

    @QtSlot(int)
    @catch_all
    def tab_changed(self, idx):
        if idx < 0 or idx >= len(self.regions):
            self.new_boundary.emit({})
            return
        region_form = self.widget(idx)
        region_form.set_value(self.regions[idx])
        self.new_boundary.emit(self.regions[idx]['Iptc4xmpExt:RegionBoundary'])

    @QtSlot(object, str)
    @catch_all
    def tab_name_changed(self, widget, name):
        self.setTabText(self.indexOf(widget), name)


class TabWidget(QtWidgets.QWidget):
    @staticmethod
    def tab_name():
        return translate('RegionsTab', 'Image &Regions')

    def __init__(self, *arg, **kw):
        super(TabWidget, self).__init__(*arg, **kw)
        self.app = QtWidgets.QApplication.instance()
        self.setLayout(QtWidgets.QHBoxLayout())
        # data display area
        self.region_tabs = RegionTabs()
        self.layout().addWidget(self.region_tabs)
        # image display area
        self.image_display = ImageDisplayWidget()
        self.layout().addWidget(self.image_display, stretch=1)
        # connections
        self.region_tabs.new_boundary.connect(self.image_display.draw_boundary)

    def refresh(self):
        self.new_selection(self.app.image_list.get_selected_images())

    def do_not_close(self):
        return False

    def new_selection(self, selection):
        if len(selection) != 1:
            self.image_display.set_image(None)
            self.region_tabs.set_image(None)
            self.setEnabled(False)
            return
        self.image_display.set_image(selection[0])
        self.region_tabs.set_image(selection[0])
        self.setEnabled(True)
