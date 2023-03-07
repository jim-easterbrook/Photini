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
import math
import os
from pprint import pprint
import re

from photini.pyqt import *
from photini.types import ImageRegionItem, LangAltDict
from photini.widgets import LangAltWidget, MultiStringEdit, SingleLineEdit

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class ResizeHandle(QtWidgets.QGraphicsRectItem):
    def __init__(self, *arg, **kw):
        super(ResizeHandle, self).__init__(*arg, **kw)
        self.setFlag(self.GraphicsItemFlag.ItemIsMovable)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        pen = QtGui.QPen()
        pen.setColor(Qt.white)
        self.setPen(pen)
        widget = QtWidgets.QWidget()
        r = width_for_text(widget, 'x') * 0.8
        self.setRect(-r, -r, r * 2, r * 2)
        border = QtWidgets.QGraphicsRectItem(parent=self)
        pen.setColor(Qt.black)
        border.setPen(pen)
        r -= 1
        border.setRect(-r, -r, r * 2, r * 2)

    @catch_all
    def mouseMoveEvent(self, event):
        super(ResizeHandle, self).mouseMoveEvent(event)
        self.parentItem().handle_drag(self, self.pos())

    @catch_all
    def mouseReleaseEvent(self, event):
        super(ResizeHandle, self).mouseReleaseEvent(event)
        self.parentItem().handle_drag_end()


class PolygonHandle(ResizeHandle):
    deletable = True

    @catch_all
    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu()
        delete_action = self.deletable and menu.addAction(
            translate('RegionsTab', 'Delete vertex'))
        new_vertex_action = menu.addAction(
            translate('RegionsTab', 'New vertex'))
        action = execute(menu, event.screenPos())
        if action == delete_action:
            self.parentItem().delete_vertex(self)
        elif action == new_vertex_action:
            self.parentItem().new_vertex(event.scenePos())


class RegionMixin(object):
    def initialise(self, boundary, scale, display_widget):
        self.setFlag(self.GraphicsItemFlag.ItemIsMovable)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.boundary = boundary
        self.scale = scale
        self.display_widget = display_widget
        pen = QtGui.QPen()
        pen.setColor(Qt.green)
        self.setPen(pen)
        self.setBrush(QtGui.QColor(128, 230, 128, 150))

    def to_iptc_x(self, x):
        if self.boundary['Iptc4xmpExt:rbUnit'] == 'pixel':
            return '{:.0f}'.format(x / self.scale['x'])
        return '{:.4f}'.format(x / self.scale['x'])

    def to_iptc_y(self, y):
        if self.boundary['Iptc4xmpExt:rbUnit'] == 'pixel':
            return '{:.0f}'.format(y / self.scale['y'])
        return '{:.4f}'.format(y / self.scale['y'])


class RectangleRegion(QtWidgets.QGraphicsRectItem, RegionMixin):
    def __init__(self, boundary, scale, display_widget,
                 aspect_ratio=0.0, *arg, **kw):
        super(RectangleRegion, self).__init__(*arg, **kw)
        self.initialise(boundary, scale, display_widget)
        self.setFlag(self.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.aspect_ratio = aspect_ratio
        self.handles = []
        for idx in range(4):
            self.handles.append(ResizeHandle(parent=self))
        x = float(boundary['Iptc4xmpExt:rbX']) * scale['x']
        y = float(boundary['Iptc4xmpExt:rbY']) * scale['y']
        w = float(boundary['Iptc4xmpExt:rbW']) * scale['x']
        h = float(boundary['Iptc4xmpExt:rbH']) * scale['y']
        self.setRect(x, y, w, h)
        self.adjust_handles()
        if self.aspect_ratio:
            self.handle_drag(self.handles[3], self.handles[3].pos())

    @catch_all
    def itemChange(self, change, value):
        scene = self.scene()
        if scene and change == self.GraphicsItemChange.ItemPositionChange:
            # limit move, in relative coords
            rect = self.rect()
            bounds = scene.sceneRect()
            bounds.setRect(
                bounds.x() - rect.x(), bounds.y() - rect.y(),
                bounds.width() - rect.width(), bounds.height() - rect.height())
            if not bounds.contains(value):
                return QtCore.QPointF(
                    min(max(value.x(), bounds.x()), bounds.right()),
                    min(max(value.y(), bounds.y()), bounds.bottom()))
        return super(RectangleRegion, self).itemChange(change, value)

    @catch_all
    def mouseReleaseEvent(self, event):
        super(RectangleRegion, self).mouseReleaseEvent(event)
        self.new_boundary()

    def handle_drag(self, handle, pos):
        idx = self.handles.index(handle)
        anchor = self.handles[3-idx].pos()
        rect = QtCore.QRectF(anchor, pos)
        if self.aspect_ratio:
            # enlarge rectangle to correct aspect ratio
            w = rect.width()
            h = rect.height()
            w_new = abs(h * self.aspect_ratio)
            h_new = abs(w / self.aspect_ratio)
            if h_new < abs(h):
                rect.setWidth(w_new * abs(w) / w)
            else:
                rect.setHeight(h_new * abs(h) / h)
            pos = rect.bottomRight()
        # constrain handle to scene bounds
        scene = self.scene()
        if scene:
            bounds = scene.sceneRect()
            bounds.translate(-self.pos())
            if not bounds.contains(pos):
                pos = QtCore.QPointF(
                    min(max(pos.x(), bounds.x()), bounds.right()),
                    min(max(pos.y(), bounds.y()), bounds.bottom()))
                rect = QtCore.QRectF(anchor, pos)
                if self.aspect_ratio:
                    # shrink rectangle to correct aspect ratio
                    w = rect.width()
                    h = rect.height()
                    w_new = abs(h * self.aspect_ratio)
                    h_new = abs(w / self.aspect_ratio)
                    if h_new > abs(h):
                        rect.setWidth(w_new * abs(w) / w)
                    else:
                        rect.setHeight(h_new * abs(h) / h)
        self.setRect(rect.normalized())
        self.adjust_handles()

    def handle_drag_end(self):
        self.new_boundary()

    def new_boundary(self):
        # get position in scene coords
        pos = self.scenePos()
        rect = self.rect()
        x = rect.x() + pos.x()
        y = rect.y() + pos.y()
        w = rect.width()
        h = rect.height()
        # send new IPTC boundary
        boundary = dict(self.boundary)
        boundary['Iptc4xmpExt:rbX'] = self.to_iptc_x(x)
        boundary['Iptc4xmpExt:rbY'] = self.to_iptc_y(y)
        boundary['Iptc4xmpExt:rbW'] = self.to_iptc_x(w)
        boundary['Iptc4xmpExt:rbH'] = self.to_iptc_y(h)
        self.display_widget.new_boundary(boundary)

    def adjust_handles(self):
        rect = self.rect()
        self.handles[0].setPos(rect.topLeft())
        self.handles[1].setPos(rect.topRight())
        self.handles[2].setPos(rect.bottomLeft())
        self.handles[3].setPos(rect.bottomRight())


class CircleRegion(QtWidgets.QGraphicsEllipseItem, RegionMixin):
    def __init__(self, boundary, scale, display_widget, *arg, **kw):
        super(CircleRegion, self).__init__(*arg, **kw)
        self.initialise(boundary, scale, display_widget)
        self.handles = []
        for idx in range(4):
            self.handles.append(ResizeHandle(parent=self))
        x = float(boundary['Iptc4xmpExt:rbX']) * scale['x']
        y = float(boundary['Iptc4xmpExt:rbY']) * scale['y']
        r = float(boundary['Iptc4xmpExt:rbRx']) * scale['x']
        self.set_geometry(x, y, r)

    @catch_all
    def mouseReleaseEvent(self, event):
        super(CircleRegion, self).mouseReleaseEvent(event)
        self.new_boundary()

    def handle_drag(self, handle, pos):
        idx = self.handles.index(handle)
        anchor = self.handles[3-idx].pos()
        if idx in (0, 3):
            x = (pos.x() + anchor.x()) / 2.0
            y = anchor.y()
            d = pos.x() - anchor.x()
        else:
            x = anchor.x()
            y = (pos.y() + anchor.y()) / 2.0
            d = pos.y() - anchor.y()
        r = abs(d) / 2.0
        self.set_geometry(x, y, r)

    def handle_drag_end(self):
        self.new_boundary()

    def new_boundary(self):
        # get position in scene coords
        pos = self.scenePos()
        rect = self.rect()
        r = rect.width() / 2
        x = rect.x() + r + pos.x()
        y = rect.y() + r + pos.y()
        # send new IPTC boundary
        boundary = dict(self.boundary)
        boundary['Iptc4xmpExt:rbX'] = self.to_iptc_x(x)
        boundary['Iptc4xmpExt:rbY'] = self.to_iptc_y(y)
        boundary['Iptc4xmpExt:rbRx'] = self.to_iptc_x(r)
        self.display_widget.new_boundary(boundary)

    def set_geometry(self, x, y, r):
        self.setRect(x-r, y-r, r*2, r*2)
        self.handles[0].setPos(x-r, y)
        self.handles[1].setPos(x, y-r)
        self.handles[2].setPos(x, y+r)
        self.handles[3].setPos(x+r, y)


class PointRegion(QtWidgets.QGraphicsPolygonItem, RegionMixin):
    def __init__(self, boundary, scale, display_widget, *arg, **kw):
        super(PointRegion, self).__init__(*arg, **kw)
        self.initialise(boundary, scale, display_widget)
        self.setFlag(self.GraphicsItemFlag.ItemSendsGeometryChanges)
        # single point, draw bow tie shape
        point = boundary['Iptc4xmpExt:rbVertices'][0]
        x = float(point['Iptc4xmpExt:rbX']) * scale['x']
        y = float(point['Iptc4xmpExt:rbY']) * scale['y']
        self.setPos(x, y)
        dx = width_for_text(display_widget, 'x') * 4.0
        polygon = QtGui.QPolygonF()
        for v in ((-dx, -dx), (-dx, dx), (dx, -dx), (dx, dx)):
            polygon.append(QtCore.QPointF(*v))
        self.setPolygon(polygon)

    @catch_all
    def itemChange(self, change, value):
        scene = self.scene()
        if scene and change == self.GraphicsItemChange.ItemPositionChange:
            bounds = scene.sceneRect()
            if not bounds.contains(value):
                return QtCore.QPointF(
                    min(max(value.x(), bounds.x()), bounds.right()),
                    min(max(value.y(), bounds.y()), bounds.bottom()))
        return super(PointRegion, self).itemChange(change, value)

    @catch_all
    def mouseReleaseEvent(self, event):
        super(PointRegion, self).mouseReleaseEvent(event)
        # send new IPTC boundary
        pos = self.scenePos()
        boundary = dict(self.boundary)
        boundary['Iptc4xmpExt:rbVertices'][0] = {
            'Iptc4xmpExt:rbX': self.to_iptc_x(pos.x()),
            'Iptc4xmpExt:rbY': self.to_iptc_y(pos.y())}
        self.display_widget.new_boundary(boundary)


class PolygonRegion(QtWidgets.QGraphicsPolygonItem, RegionMixin):
    def __init__(self, boundary, scale, display_widget, *arg, **kw):
        super(PolygonRegion, self).__init__(*arg, **kw)
        self.initialise(boundary, scale, display_widget)
        vertices = [(float(v['Iptc4xmpExt:rbX']) * scale['x'],
                     float(v['Iptc4xmpExt:rbY']) * scale['y'])
                    for v in boundary['Iptc4xmpExt:rbVertices']]
        polygon = QtGui.QPolygonF()
        self.handles = []
        for (x, y) in vertices:
            polygon.append(QtCore.QPointF(x, y))
            handle = PolygonHandle(parent=self)
            handle.setPos(x, y)
            self.handles.append(handle)
        self.setPolygon(polygon)

    @catch_all
    def contextMenuEvent(self, event):
        self.new_vertex(event.pos())

    def new_vertex(self, p0):
        polygon = self.polygon()
        # find pair of points to insert between
        angle = 0
        insert = 0
        idx = polygon.count() - 1
        v2 = QtGui.QVector2D(polygon.at(idx) - p0)
        v2.normalize()
        for idx in range(polygon.count()):
            v1 = v2
            v2 = QtGui.QVector2D(polygon.at(idx) - p0)
            v2.normalize()
            a12 = abs(math.acos(QtGui.QVector2D.dotProduct(v2, v1)))
            if a12 > angle:
                angle = a12
                insert = idx
        polygon.insert(insert, p0)
        self.setPolygon(polygon)
        if len(self.handles) == 2:
            for handle in self.handles:
                handle.deletable = True
        handle = PolygonHandle(parent=self)
        handle.setPos(p0)
        self.handles.insert(insert, handle)

    @catch_all
    def mouseReleaseEvent(self, event):
        super(PolygonRegion, self).mouseReleaseEvent(event)
        self.new_boundary()

    def handle_drag(self, handle, pos):
        idx = self.handles.index(handle)
        polygon = self.polygon()
        polygon.replace(idx, pos)
        self.setPolygon(polygon)

    def handle_drag_end(self):
        self.new_boundary()

    def delete_vertex(self, handle):
        idx = self.handles.index(handle)
        self.handles.remove(handle)
        handle.setParentItem(None)
        if len(self.handles) == 2:
            for handle in self.handles:
                handle.deletable = False
        polygon = self.polygon()
        polygon.remove(idx)
        self.setPolygon(polygon)
        self.new_boundary()

    def new_boundary(self):
        # get vertices in scene coords
        pos = self.scenePos()
        dx, dy = pos.x(), pos.y()
        polygon = self.polygon()
        vertices = []
        for idx in range(polygon.count()):
            v = polygon.at(idx)
            vertices.append((v.x() + dx, v.y() + dy))
        # send new IPTC boundary
        boundary = dict(self.boundary)
        boundary['Iptc4xmpExt:rbVertices'] = [
            {'Iptc4xmpExt:rbX': self.to_iptc_x(x),
             'Iptc4xmpExt:rbY': self.to_iptc_y(y)} for (x, y) in vertices]
        self.display_widget.new_boundary(boundary)


class ImageDisplayWidget(QtWidgets.QGraphicsView):
    new_value = QtSignal(str, object)

    def __init__(self, *arg, **kw):
        super(ImageDisplayWidget, self).__init__(*arg, **kw)
        self.setScene(QtWidgets.QGraphicsScene())
        self.boundary = None

    def set_image(self, image):
        scene = self.scene()
        scene.clear()
        self.resetTransform()
        self.boundary = None
        if image:
            self.image_dims = image.metadata.get_image_size()
            transform = image.get_transform(image.metadata.orientation)
            if transform:
                self.setTransform(transform)
            reader = QtGui.QImageReader(image.path)
            reader.setAutoTransform(False)
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
                print('scene', self.sceneRect())
                print('view', self.mapFromScene(self.sceneRect()))

    @QtSlot(dict)
    @catch_all
    def draw_boundary(self, region):
        scene = self.scene()
        if self.boundary:
            scene.removeItem(self.boundary)
            self.boundary = None
        if not region:
            return
        boundary = region['Iptc4xmpExt:RegionBoundary']
        rect = scene.sceneRect()
        scale = {'x': rect.width(),
                 'y': rect.height()}
        if boundary['Iptc4xmpExt:rbUnit'] == 'pixel':
            if not self.image_dims:
                return
            scale['x'] /= self.image_dims['x']
            scale['y'] /= self.image_dims['y']
        if boundary['Iptc4xmpExt:rbShape'] == 'rectangle':
            aspect_ratio = 0.0
            if region.has_role('http://cv.iptc.org/newscodes/imageregionrole/'
                               'squareCropping'):
                aspect_ratio = 1.0
            elif region.has_role('http://cv.iptc.org/newscodes/imageregionrole/'
                                 'landscapeCropping'):
                aspect_ratio = 16.0 / 9.0
            elif region.has_role('http://cv.iptc.org/newscodes/imageregionrole/'
                                 'portraitCropping'):
                aspect_ratio = 9.0 / 16.0
            if aspect_ratio and self.transform().isRotating():
                aspect_ratio = 1.0 / aspect_ratio
            self.boundary = RectangleRegion(
                boundary, scale, self, aspect_ratio=aspect_ratio)
        elif boundary['Iptc4xmpExt:rbShape'] == 'circle':
            self.boundary = CircleRegion(boundary, scale, self)
        elif len(boundary['Iptc4xmpExt:rbVertices']) == 1:
            self.boundary = PointRegion(boundary, scale, self)
        else:
            self.boundary = PolygonRegion(boundary, scale, self)
        scene.addItem(self.boundary)
        self.ensureVisible(self.boundary.boundingRect())

    def new_boundary(self, boundary):
        self.new_value.emit('Iptc4xmpExt:RegionBoundary', boundary)


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
            data = {'xmp:Identifier': [item['uri']],
                    'Iptc4xmpExt:Name': item['name']}
            action.setData(data)
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
        self.new_value.emit(self._key, self.get_value())

    def set_value(self, value):
        value = value or []
        self._updating = True
        for action in self.actions:
            if action.isChecked():
                action.setChecked(False)
        for item in value:
            found = False
            if 'xmp:Identifier' in item:
                for uri in item['xmp:Identifier']:
                    for action in self.actions:
                        if uri in action.data()['xmp:Identifier']:
                            action.setChecked(True)
                            found = True
                            break
            if found:
                continue
            if 'Iptc4xmpExt:Name' in item:
                for name in item['Iptc4xmpExt:Name'].values():
                    for action in self.actions:
                         if name in action.data()['Iptc4xmpExt:Name'].values():
                            action.setChecked(True)
                            found = True
                            break
            if found:
                continue
            # add new action
            data = {'Iptc4xmpExt:Name': {}, 'xmp:Identifier': []}
            data.update(item)
            label = data['Iptc4xmpExt:Name'] or {
                'x-default': '; '.join(data['xmp:Identifier'])}
            label = LangAltDict(label).best_match()
            if not label:
                continue
            action = self.menu.addAction(label)
            action.setCheckable(True)
            action.setToolTip('<p>{}</p>'.format(
                '; '.join(data['xmp:Identifier'])))
            action.setChecked(True)
            action.setData(data)
            action.toggled.connect(self._action_toggled)
            self.actions.append(action)
        self._updating = False
        # update display
        self._action_toggled(True)

    def get_value(self):
        result = []
        for action in self.actions:
            if action.isChecked():
                result.append(action.data())
        return result


class UnitSelector(QtWidgets.QWidget):
    new_value = QtSignal(str, object)

    def __init__(self, key, *arg, **kw):
        super(UnitSelector, self).__init__(*arg, **kw)
        self._key = key
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().addWidget(QtWidgets.QLabel(
            translate('RegionsTab', 'Boundary unit')))
        self.buttons = {}
        self.buttons['pixel'] = QtWidgets.QRadioButton(
            translate('RegionsTab', 'pixel'))
        self.buttons['pixel'].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'A pixel of a digital image setting an absolute'
            ' value.')))
        self.buttons['pixel'].clicked.connect(self.state_changed)
        self.layout().addWidget(self.buttons['pixel'])
        self.buttons['relative'] = QtWidgets.QRadioButton(
            translate('RegionsTab', 'relative'))
        self.buttons['relative'].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'Relative part of the size of an image along the'
            ' x- or the y-axis.')))
        self.buttons['relative'].clicked.connect(self.state_changed)
        self.layout().addWidget(self.buttons['relative'])

    @QtSlot()
    @catch_all
    def state_changed(self):
        self.new_value.emit(self._key, self.get_value())

    def get_value(self):
        for key, widget in self.buttons.items():
            if widget.isChecked():
                return key
        return None

    def set_value(self, value):
        for key in self.buttons:
            self.buttons[key].setChecked(key == value)


class RegionForm(QtWidgets.QScrollArea):
    name_changed = QtSignal(object, str)
    new_value = QtSignal(str, object)

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
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'Free-text name of the region. Should be unique among'
            ' all Region Names of an image.')))
        self.widgets[key].new_value.connect(self.new_value)
        layout.addRow(translate('RegionsTab', 'Name'), self.widgets[key])
        # units
        key = 'Iptc4xmpExt:RegionBoundary/Iptc4xmpExt:rbUnit'
        self.widgets[key] = UnitSelector(key)
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'Unit used for measuring dimensions of the boundary'
            ' of a region.')))
        self.widgets[key].new_value.connect(self.new_value)
        layout.addRow(self.widgets[key])
        # roles
        key = 'Iptc4xmpExt:rRole'
        self.widgets[key] = EntityConceptWidget(key, ImageRegionItem.roles)
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'Role of this region among all regions of this image'
            ' or of other images. The value SHOULD be taken from a Controlled'
            ' Vocabulary.')))
        self.widgets[key].new_value.connect(self.new_value)
        layout.addRow(translate('RegionsTab', 'Role'), self.widgets[key])
        # content types
        key = 'Iptc4xmpExt:rCtype'
        self.widgets[key] = EntityConceptWidget(key, ImageRegionItem.ctypes)
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'The semantic type of what is shown inside the'
            ' region. The value SHOULD be taken from a Controlled'
            ' Vocabulary.')))
        self.widgets[key].new_value.connect(self.new_value)
        layout.addRow(
            translate('RegionsTab', 'Content type'), self.widgets[key])
        # person im image
        key = 'Iptc4xmpExt:PersonInImage'
        self.widgets[key] = MultiStringEdit(key)
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'Enter the names of people shown in this region.'
            ' Separate multiple entries with ";" characters.')))
        self.widgets[key].new_value.connect(self.new_value)
        layout.addRow(
            translate('RegionsTab', 'Person shown'), self.widgets[key])
        # identifier
        key = 'Iptc4xmpExt:rId'
        self.widgets[key] = SingleLineEdit(key)
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'Identifier of the region. Must be unique among all'
            ' Region Identifiers of an image. Does not have to be unique beyond'
            ' the metadata of this image.')))
        self.widgets[key].new_value.connect(self.new_value)
        layout.addRow(translate('RegionsTab', 'Identifier'), self.widgets[key])

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
            elif isinstance(value, list):
                self.widgets[key] = MultiStringEdit(key)
            else:
                self.widgets[key] = SingleLineEdit(key)
            self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
                'RegionsTab', 'The Image Region Structure includes optionally'
                ' any metadata property which is related to the region.')))
            self.widgets[key].new_value.connect(self.new_value)
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


class QTabBar(QtWidgets.QTabBar):
    @catch_all
    def contextMenuEvent(self, event):
        self.parentWidget().context_menu(
            self.tabAt(event.pos()), event.globalPos())

    @catch_all
    def tabSizeHint(self, index):
        size = super(QTabBar, self).tabSizeHint(index)
        size.setWidth(width_for_text(self, 'x' * 6))
        return size


class RegionTabs(QtWidgets.QTabWidget):
    new_region = QtSignal(dict)

    def __init__(self, *arg, **kw):
        super(RegionTabs, self).__init__(*arg, **kw)
        self.setTabBar(QTabBar())
        self.setFixedWidth(width_for_text(self, 'x' * 40))
        self.currentChanged.connect(self.tab_changed)

    def context_menu(self, idx, pos):
        menu = QtWidgets.QMenu()
        delete_action = (
            bool(self.image.metadata.image_region)
            and menu.addAction(translate('RegionsTab', 'Delete region')))
        rect_action = menu.addAction(
            translate('RegionsTab', 'New rectangle'))
        circ_action = menu.addAction(
            translate('RegionsTab', 'New circle'))
        point_action = menu.addAction(
            translate('RegionsTab', 'New point'))
        poly_action = menu.addAction(
            translate('RegionsTab', 'New polygon'))
        action = execute(menu, pos)
        regions = list(self.image.metadata.image_region)
        current = self.currentIndex()
        if action == delete_action:
            regions.pop(idx)
            if current >= len(regions):
                current = len(regions) - 1
            self.image.metadata.image_region = regions
            self.set_image(self.image)
            self.setCurrentIndex(current)
            return
        if action == rect_action:
            boundary = {'Iptc4xmpExt:rbShape': 'rectangle',
                        'Iptc4xmpExt:rbX': '0.4',
                        'Iptc4xmpExt:rbY': '0.4',
                        'Iptc4xmpExt:rbW': '0.2',
                        'Iptc4xmpExt:rbH': '0.2'}
        elif action == circ_action:
            boundary = {'Iptc4xmpExt:rbShape': 'circle',
                        'Iptc4xmpExt:rbX': '0.5',
                        'Iptc4xmpExt:rbY': '0.5',
                        'Iptc4xmpExt:rbRx': '0.15'}
        elif action == point_action:
            boundary = {'Iptc4xmpExt:rbShape': 'polygon',
                        'Iptc4xmpExt:rbVertices': [{
                            'Iptc4xmpExt:rbX': '0.5',
                            'Iptc4xmpExt:rbY': '0.5'}]}
        elif action == poly_action:
            boundary = {'Iptc4xmpExt:rbShape': 'polygon',
                        'Iptc4xmpExt:rbVertices': [
                            {'Iptc4xmpExt:rbX': '0.4',
                             'Iptc4xmpExt:rbY': '0.4'},
                            {'Iptc4xmpExt:rbX': '0.6',
                             'Iptc4xmpExt:rbY': '0.5'},
                            {'Iptc4xmpExt:rbX': '0.5',
                             'Iptc4xmpExt:rbY': '0.6'}]}
        boundary['Iptc4xmpExt:rbUnit'] = 'relative'
        regions.append({'Iptc4xmpExt:RegionBoundary': boundary})
        current = len(regions) - 1
        self.image.metadata.image_region = regions
        self.set_image(self.image)
        self.setCurrentIndex(current)

    def set_image(self, image):
        self.clear()
        self.image = image
        regions = (image and image.metadata.image_region) or []
        if not regions:
            region_form = RegionForm()
            region_form.setEnabled(False)
            self.addTab(region_form, '')
            return
        for idx, region in enumerate(regions):
            region_form = RegionForm()
            region_form.name_changed.connect(self.tab_name_changed)
            region_form.new_value.connect(self.new_value)
            self.addTab(region_form, str(idx + 1))
            region_form.set_value(region)

    @QtSlot(int)
    @catch_all
    def tab_changed(self, idx):
        regions = (self.image and self.image.metadata.image_region) or []
        if idx < 0 or idx >= len(regions):
            self.new_region.emit({})
            return
        region_form = self.widget(idx)
        region_form.set_value(regions[idx])
        self.new_region.emit(regions[idx])

    @QtSlot(object, str)
    @catch_all
    def tab_name_changed(self, widget, name):
        self.setTabText(self.indexOf(widget), name)

    @QtSlot(str, object)
    @catch_all
    def new_value(self, key, value):
        idx = self.currentIndex()
        regions = list(self.image.metadata.image_region)
        region = regions[idx]
        if 'rbUnit' in key:
            region = region.convert_unit(value, self.image)
        else:
            region = dict(region)
            if value:
                region[key] = value
            elif key in region:
                del region[key]
        regions[idx] = region
        self.image.metadata.image_region = regions
        if key == 'Iptc4xmpExt:rRole':
            # aspect ratio constraint may have changed
            self.new_region.emit(self.image.metadata.image_region[idx])


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
        self.region_tabs.new_region.connect(self.image_display.draw_boundary)
        self.image_display.new_value.connect(self.region_tabs.new_value)

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
