##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2023-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import re

from photini.cv import image_region_types, image_region_roles
from photini.pyqt import *
from photini.pyqt import set_symbol_font, using_pyside
from photini.types import ImageRegionItem, MD_LangAlt
from photini.widgets import LangAltWidget, MultiStringEdit, SingleLineEdit

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class ResizeHandle(QtWidgets.QGraphicsRectItem):
    def __init__(self, draw_unit, *arg, **kw):
        super(ResizeHandle, self).__init__(*arg, **kw)
        self.setFlag(self.GraphicsItemFlag.ItemIsMovable)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        pen = QtGui.QPen()
        pen.setColor(Qt.GlobalColor.white)
        self.setPen(pen)
        widget = QtWidgets.QWidget()
        r = draw_unit * 5
        self.setRect(-r, -r, r * 2, r * 2)
        border = QtWidgets.QGraphicsRectItem(parent=self)
        pen.setColor(Qt.GlobalColor.black)
        border.setPen(pen)
        r = draw_unit * 4
        border.setRect(-r, -r, r * 2, r * 2)
        self.setCursor(Qt.CursorShape.CrossCursor)

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
    def initialise(self, region, display_widget, active):
        self.setFlag(self.GraphicsItemFlag.ItemIsMovable)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.region = region
        self.image = display_widget.image
        self.active = active
        rect = display_widget.scene().sceneRect()
        self.to_scene = QtGui.QTransform().scale(rect.width(), rect.height())
        self.from_scene = self.to_scene.inverted()[0]
        self.display_widget = display_widget
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_style(self, draw_unit):
        pen = QtGui.QPen()
        pen.setCosmetic(True)
        pen.setWidthF(draw_unit * 1.5)
        if self.active:
            # fg is a thin white line, bg is a wide translucent dark line
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            pen.setColor(Qt.GlobalColor.white)
            for part in self.fg_parts:
                part.setPen(pen)
            pen.setColor(QtGui.QColor(0, 0, 0, 120))
            pen.setWidthF(draw_unit * 5.5)
        else:
            # fg is yellow dashes, bg is blue dashes in the gaps
            dashes = [draw_unit * 2.2, draw_unit * 3.8]
            pen.setDashPattern(dashes)
            pen.setColor(Qt.GlobalColor.yellow)
            for part in self.fg_parts:
                part.setPen(pen)
            pen.setDashPattern([0, draw_unit * 3.8, draw_unit * 2.2, 0])
            pen.setColor(Qt.GlobalColor.blue)
        for part in self.bg_parts:
            part.setPen(pen)

    def item_clicked(self):
        self.display_widget.item_clicked(self)

    def set_scale(self):
        transform = self.display_widget.transform()
        scale = 1.0 / max(abs(transform.m11()), abs(transform.m21()))
        for handle in self.handles:
            handle.setScale(scale)


class RectangleRegion(QtWidgets.QGraphicsRectItem, RegionMixin):
    def __init__(self, region, display_widget, draw_unit, active,
                 aspect_ratio=0.0, *arg, **kw):
        super(RectangleRegion, self).__init__(*arg, **kw)
        self.initialise(region, display_widget, active)
        self.setFlag(self.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.aspect_ratio = aspect_ratio
        self.handles = []
        if active:
            for idx in range(4):
                self.handles.append(ResizeHandle(draw_unit, parent=self))
        corners = self.to_scene.map(region.to_Qt(self.image))
        rect = QtCore.QRectF(corners.at(0), corners.at(1))
        self.setRect(rect)
        self.bg_parts = [self]
        self.fg_parts = [QtWidgets.QGraphicsRectItem(parent=self)]
        self.adjust_handles()
        self.set_style(draw_unit)
        self.set_scale()

    @catch_all
    def itemChange(self, change, value):
        scene = self.scene()
        if scene and change == self.GraphicsItemChange.ItemSceneHasChanged:
            if self.aspect_ratio:
                self.handle_drag(self.handles[3], self.handles[3].pos())
            return
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
    def mousePressEvent(self, event):
        super(RectangleRegion, self).mousePressEvent(event)
        self.item_clicked()

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
        rect = self.rect()
        rect.translate(self.scenePos())
        rect = self.from_scene.mapRect(rect)
        polygon = QtGui.QPolygonF([rect.topLeft(), rect.bottomRight()])
        boundary = self.region.from_Qt(polygon, self.image)
        self.display_widget.new_boundary(boundary)

    def adjust_handles(self):
        rect = self.rect()
        self.fg_parts[0].setRect(rect)
        if self.active:
            self.handles[0].setPos(rect.topLeft())
            self.handles[1].setPos(rect.topRight())
            self.handles[2].setPos(rect.bottomLeft())
            self.handles[3].setPos(rect.bottomRight())


class CircleRegion(QtWidgets.QGraphicsEllipseItem, RegionMixin):
    def __init__(self, region, display_widget, draw_unit, active, *arg, **kw):
        super(CircleRegion, self).__init__(*arg, **kw)
        self.initialise(region, display_widget, active)
        self.handles = []
        if active:
            for idx in range(4):
                self.handles.append(ResizeHandle(draw_unit, parent=self))
        points = self.to_scene.map(region.to_Qt(self.image))
        centre = points.at(0)
        radius = (points.at(1) - centre).manhattanLength()
        self.bg_parts = [self]
        self.fg_parts = [QtWidgets.QGraphicsEllipseItem(parent=self)]
        self.set_geometry(centre, radius)
        self.set_style(draw_unit)
        self.set_scale()

    @catch_all
    def mousePressEvent(self, event):
        super(CircleRegion, self).mousePressEvent(event)
        self.item_clicked()

    @catch_all
    def mouseReleaseEvent(self, event):
        super(CircleRegion, self).mouseReleaseEvent(event)
        self.new_boundary()

    def handle_drag(self, handle, pos):
        idx = self.handles.index(handle)
        anchor = self.handles[3-idx].pos()
        if idx in (0, 3):
            pos.setY(anchor.y())
        else:
            pos.setX(anchor.x())
        centre = (anchor + pos) / 2.0
        r = (centre - anchor).manhattanLength()
        self.set_geometry(centre, r)

    def handle_drag_end(self):
        self.new_boundary()

    def new_boundary(self):
        rect = self.rect()
        rect.translate(self.scenePos())
        rect = self.from_scene.mapRect(rect)
        centre = rect.center()
        edge = QtCore.QPointF(rect.right(), centre.y())
        polygon = QtGui.QPolygonF([centre, edge])
        boundary = self.region.from_Qt(polygon, self.image)
        self.display_widget.new_boundary(boundary)

    def set_geometry(self, centre, r):
        rx = QtCore.QPointF(r, 0)
        ry = QtCore.QPointF(0, r)
        rect = QtCore.QRectF(centre - (rx + ry), centre + (rx + ry))
        self.setRect(rect)
        self.fg_parts[0].setRect(rect)
        if self.active:
            self.handles[0].setPos(centre - rx)
            self.handles[1].setPos(centre - ry)
            self.handles[2].setPos(centre + ry)
            self.handles[3].setPos(centre + rx)


class PointRegion(QtWidgets.QGraphicsItemGroup, RegionMixin):
    def __init__(self, region, display_widget, draw_unit, active, *arg, **kw):
        super(PointRegion, self).__init__(*arg, **kw)
        self.initialise(region, display_widget, active)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFlag(self.GraphicsItemFlag.ItemSendsGeometryChanges)
        # single point, draw cross hairs with a centre circle
        r = draw_unit * 6
        dx1 = r / 1.35
        dx2 = draw_unit * 20
        self.bg_parts = []
        self.fg_parts = []
        for parts in (self.bg_parts, self.fg_parts):
            for ends in ((-dx2, -dx2, -dx1, -dx1), (dx2, -dx2, dx1, -dx1),
                         (-dx2,  dx2, -dx1,  dx1), (dx2,  dx2, dx1,  dx1)):
                line = QtWidgets.QGraphicsLineItem(QtCore.QLineF(*ends))
                parts.append(line)
                self.addToGroup(line)
            circle = QtWidgets.QGraphicsEllipseItem(-r, -r, r * 2, r * 2)
            parts.append(circle)
            self.addToGroup(circle)
        pos = self.to_scene.map(region.to_Qt(self.image)).at(0)
        self.setPos(pos)
        self.set_style(draw_unit)
        self.set_scale()

    def set_scale(self):
        transform = self.display_widget.transform()
        scale = 1.0 / max(abs(transform.m11()), abs(transform.m21()))
        self.setScale(scale)

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
    def mousePressEvent(self, event):
        super(PointRegion, self).mousePressEvent(event)
        self.item_clicked()

    @catch_all
    def mouseReleaseEvent(self, event):
        super(PointRegion, self).mouseReleaseEvent(event)
        self.new_boundary()

    def new_boundary(self):
        pos = self.from_scene.map(self.scenePos())
        polygon = QtGui.QPolygonF([pos])
        boundary = self.region.from_Qt(polygon, self.image)
        self.display_widget.new_boundary(boundary)


class PolygonRegion(QtWidgets.QGraphicsPolygonItem, RegionMixin):
    def __init__(self, region, display_widget, draw_unit, active, *arg, **kw):
        super(PolygonRegion, self).__init__(*arg, **kw)
        self.initialise(region, display_widget, active)
        self.draw_unit = draw_unit
        polygon = self.to_scene.map(region.to_Qt(self.image))
        self.handles = []
        if self.active:
            for idx in range(polygon.count()):
                handle = PolygonHandle(draw_unit, parent=self)
                handle.setPos(polygon.at(idx))
                self.handles.append(handle)
        self.setPolygon(polygon)
        self.bg_parts = [self]
        self.fg_parts = [QtWidgets.QGraphicsPolygonItem(parent=self)]
        self.fg_parts[0].setPolygon(polygon)
        self.set_style(draw_unit)
        self.set_scale()

    @catch_all
    def contextMenuEvent(self, event):
        if not self.active:
            return super(PolygonRegion, self).contextMenuEvent(event)
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
        self.fg_parts[0].setPolygon(polygon)
        if len(self.handles) == 2:
            for handle in self.handles:
                handle.deletable = True
        handle = PolygonHandle(self.draw_unit, parent=self)
        handle.setPos(p0)
        transform = self.display_widget.transform()
        scale = 1.0 / max(abs(transform.m11()), abs(transform.m21()))
        handle.setScale(scale)
        self.handles.insert(insert, handle)

    @catch_all
    def mousePressEvent(self, event):
        super(PolygonRegion, self).mousePressEvent(event)
        self.item_clicked()

    @catch_all
    def mouseReleaseEvent(self, event):
        super(PolygonRegion, self).mouseReleaseEvent(event)
        self.new_boundary()

    def handle_drag(self, handle, pos):
        idx = self.handles.index(handle)
        polygon = self.polygon()
        polygon[idx] = pos
        self.setPolygon(polygon)
        self.fg_parts[0].setPolygon(polygon)

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
        self.fg_parts[0].setPolygon(polygon)
        self.new_boundary()

    def new_boundary(self):
        polygon = self.polygon()
        polygon.translate(self.scenePos())
        polygon = self.from_scene.map(polygon)
        boundary = self.region.from_Qt(polygon, self.image)
        self.display_widget.new_boundary(boundary)


class ImageDisplayWidget(QtWidgets.QGraphicsView):
    new_idx = QtSignal(int)
    new_value = QtSignal(int, dict)

    def __init__(self, *arg, **kw):
        super(ImageDisplayWidget, self).__init__(*arg, **kw)
        self.setRenderHint(
            QtGui.QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(
            QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setScene(QtWidgets.QGraphicsScene())
        self.setDragMode(self.DragMode.ScrollHandDrag)
        self.boundaries = []
        self.image = None

    @catch_all
    def keyPressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Plus:
                self.adjust_zoom(0.1)
                return
            if event.key() == Qt.Key.Key_Minus:
                self.adjust_zoom(-0.1)
                return
        super(ImageDisplayWidget, self).keyPressEvent(event)

    @catch_all
    def wheelEvent(self, event):
        if not event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            return super(ImageDisplayWidget, self).wheelEvent(event)
        # zoom in or out
        delta = event.angleDelta().y()
        self.adjust_zoom(delta / 1200)

    def adjust_zoom(self, delta):
        scale = 1.0 + delta
        anchor = self.transformationAnchor()
        self.setTransformationAnchor(self.ViewportAnchor.AnchorUnderMouse)
        self.scale(scale, scale)
        self.setTransformationAnchor(anchor)
        for boundary in self.boundaries:
            boundary.set_scale()

    def set_image(self, image):
        self.image = image
        scene = self.scene()
        scene.clear()
        self.resetTransform()
        self.boundaries = []
        if image:
            with Busy():
                pixmap = image.metadata.get_image_pixmap()
            if not pixmap:
                item = scene.addText(
                    translate('RegionsTab', 'Unreadable image format'))
            else:
                rect = self.contentsRect()
                orientation = image.metadata.orientation
                transform = orientation and orientation.get_transform()
                if transform:
                    rect = transform.mapRect(rect)
                else:
                    transform = QtGui.QTransform()
                w_im, h_im = pixmap.width(), pixmap.height()
                w_sc, h_sc = rect.width(), rect.height()
                if w_im * h_sc < h_im * w_sc:
                    w_sc -= self.verticalScrollBar().sizeHint().width()
                    scale = w_sc / w_im
                else:
                    h_sc -= self.horizontalScrollBar().sizeHint().height()
                    scale = h_sc / h_im
                transform = transform.scale(scale, scale)
                self.setTransform(transform)
                item = QtWidgets.QGraphicsPixmapItem(pixmap)
                scene.addItem(item)
            scene.setSceneRect(item.boundingRect())

    @QtSlot(int, list)
    @catch_all
    def draw_boundaries(self, idx, regions):
        self.idx = idx
        scene = self.scene()
        if self.boundaries:
            for boundary in self.boundaries:
                scene.removeItem(boundary)
            self.boundaries = []
        if not regions:
            return
        # a dimension to set the size of elements such as line thickness
        draw_unit = width_for_text(self, 'x') * 0.14
        for n, region in enumerate(regions):
            active = n == idx
            boundary = region['Iptc4xmpExt:RegionBoundary']
            if boundary['Iptc4xmpExt:rbShape'] == 'rectangle':
                aspect_ratio = 0.0
                if region.has_role('imgregrole:squareCropping'):
                    aspect_ratio = 1.0
                elif region.has_role('imgregrole:landscapeCropping'):
                    aspect_ratio = 16.0 / 9.0
                elif region.has_role('imgregrole:portraitCropping'):
                    aspect_ratio = 9.0 / 16.0
                if aspect_ratio and self.transform().isRotating():
                    aspect_ratio = 1.0 / aspect_ratio
                boundary = RectangleRegion(
                    region, self, draw_unit, active, aspect_ratio=aspect_ratio)
            elif boundary['Iptc4xmpExt:rbShape'] == 'circle':
                boundary = CircleRegion(region, self, draw_unit, active)
            elif len(boundary['Iptc4xmpExt:rbVertices']) == 1:
                boundary = PointRegion(region, self, draw_unit, active)
            else:
                boundary = PolygonRegion(region, self, draw_unit, active)
            if active:
                boundary.setZValue(100)
            scene.addItem(boundary)
            self.boundaries.append(boundary)
        for m in range(len(self.boundaries)):
            item_m = self.boundaries[m]
            for n in range(m + 1, len(self.boundaries)):
                item_n = self.boundaries[n]
                if item_m.collidesWithItem(
                        item_n, Qt.ItemSelectionMode.ContainsItemBoundingRect):
                    item_m.setZValue(max(item_m.zValue(), item_n.zValue() + 1))
                elif item_n.collidesWithItem(
                        item_m, Qt.ItemSelectionMode.ContainsItemBoundingRect):
                    item_n.setZValue(max(item_n.zValue(), item_m.zValue() + 1))
        # zoom out if needed to make boundary visible
        boundary = self.boundaries[max(idx, 0)]
        rect = boundary.boundingRect()
        visible = self.mapToScene(self.viewport().geometry()).boundingRect()
        scale = min(visible.width() / rect.width(),
                    visible.height() / rect.height())
        if scale < 1.0:
            self.adjust_zoom(scale - 1.0)
        self.ensureVisible(boundary)

    def item_clicked(self, scene_item):
        for idx, item in enumerate(self.boundaries):
            if item == scene_item:
                if idx != self.idx:
                    self.new_idx.emit(idx)
                break

    def new_boundary(self, boundary):
        self.new_value.emit(self.idx, {'Iptc4xmpExt:RegionBoundary': boundary})


class EntityConceptWidget(SingleLineEdit):
    def __init__(self, key, vocab, *arg, **kw):
        super(EntityConceptWidget, self).__init__(key, *arg, **kw)
        self.setReadOnly(True)
        self._updating = False
        self.menu = QtWidgets.QMenu(parent=self)
        self.menu.setToolTipsVisible(True)
        self.actions = []
        for item in vocab:
            label = MD_LangAlt(item['name']).best_match()
            tip = MD_LangAlt(item['definition']).best_match()
            if item['note']:
                tip += ' ({})'.format(MD_LangAlt(item['note']).best_match())
            action = self.menu.addAction(label)
            action.setCheckable(True)
            action.setToolTip('<p>{}</p>'.format(tip))
            action.setData(item['data'])
            action.toggled.connect(self.update_display)
            action.triggered.connect(self.action_triggered)
            self.actions.append(action)

    def mousePressEvent(self, event):
        self.menu.popup(self.mapToGlobal(event.pos()))

    @QtSlot(bool)
    @catch_all
    def update_display(self, checked=None):
        if self._updating:
            return
        selection = []
        for action in self.actions:
            if action.isChecked():
                selection.append(action.text())
        self.setPlainText(', '.join(selection))

    @QtSlot(bool)
    @catch_all
    def action_triggered(self, checked=None):
        self.emit_value()

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
            label = MD_LangAlt(label).best_match()
            if not label:
                continue
            action = self.menu.addAction(label)
            action.setCheckable(True)
            action.setToolTip('<p>{}</p>'.format(
                '; '.join(data['xmp:Identifier'])))
            action.setChecked(True)
            action.setData(data)
            action.toggled.connect(self.update_display)
            action.triggered.connect(self.action_triggered)
            self.actions.append(action)
        self._updating = False
        self.update_display()

    def get_value(self):
        result = []
        for action in self.actions:
            if action.isChecked():
                result.append(action.data())
        return result


class UnitSelector(QtWidgets.QWidget):
    new_value = QtSignal(dict)

    def __init__(self, key, *arg, **kw):
        super(UnitSelector, self).__init__(*arg, **kw)
        self._key = key
        self.setLayout(QtWidgets.QHBoxLayout())
        margins = self.layout().contentsMargins()
        margins.setTop(0)
        margins.setBottom(0)
        self.layout().setContentsMargins(margins)
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
        self.setFixedHeight(self.sizeHint().height())

    @QtSlot()
    @catch_all
    def state_changed(self):
        self.new_value.emit({self._key: self.get_value()})

    def get_value(self):
        for key, widget in self.buttons.items():
            if widget.isChecked():
                return key
        return None

    def set_value(self, value):
        for key in self.buttons:
            self.buttons[key].setChecked(key == value)


class RegionForm(QtWidgets.QScrollArea):
    new_value = QtSignal(int, dict)

    def __init__(self, idx, *arg, **kw):
        super(RegionForm, self).__init__(*arg, **kw)
        self.idx = idx
        self.setFrameStyle(QtWidgets.QFrame.Shape.NoFrame)
        self.setWidget(QtWidgets.QWidget())
        self.setWidgetResizable(True)
        layout = QtWidgets.QFormLayout()
        layout.setRowWrapPolicy(layout.RowWrapPolicy.WrapLongRows)
        self.widget().setLayout(layout)
        self.region = {}
        self.widgets = {}
        # name
        key = 'Iptc4xmpExt:Name'
        self.widgets[key] = LangAltWidget(
            key, multi_line=False, min_width=15,
            label=translate('RegionsTab', 'Name'))
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'Free-text name of the region. Should be unique among'
            ' all Region Names of an image.')))
        self.widgets[key].new_value.connect(self.emit_value)
        layout.addRow(self.widgets[key])
        # identifier
        key = 'Iptc4xmpExt:rId'
        self.widgets[key] = SingleLineEdit(key, min_width=15)
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'Identifier of the region. Must be unique among all'
            ' Region Identifiers of an image. Does not have to be unique beyond'
            ' the metadata of this image.')))
        self.widgets[key].new_value.connect(self.emit_value)
        layout.addRow(translate('RegionsTab', 'Identifier'), self.widgets[key])
        # units
        key = 'Iptc4xmpExt:RegionBoundary/Iptc4xmpExt:rbUnit'
        self.widgets[key] = UnitSelector(key)
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'Unit used for measuring dimensions of the boundary'
            ' of a region.')))
        self.widgets[key].new_value.connect(self.emit_value)
        layout.addRow(
            translate('RegionsTab', 'Boundary unit'), self.widgets[key])
        # roles
        key = 'Iptc4xmpExt:rRole'
        self.widgets[key] = EntityConceptWidget(key, image_region_roles)
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'Role of this region among all regions of this image'
            ' or of other images. The value SHOULD be taken from a Controlled'
            ' Vocabulary.')))
        self.widgets[key].new_value.connect(self.emit_value)
        layout.addRow(translate('RegionsTab', 'Role'), self.widgets[key])
        # content types
        key = 'Iptc4xmpExt:rCtype'
        self.widgets[key] = EntityConceptWidget(key, image_region_types)
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'The semantic type of what is shown inside the'
            ' region. The value SHOULD be taken from a Controlled'
            ' Vocabulary.')))
        self.widgets[key].new_value.connect(self.emit_value)
        layout.addRow(
            translate('RegionsTab', 'Content type'), self.widgets[key])
        # person im image
        key = 'Iptc4xmpExt:PersonInImage'
        self.widgets[key] = MultiStringEdit(key, min_width=15)
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'Enter the names of people shown in this region.'
            ' Separate multiple entries with ";" characters.')))
        self.widgets[key].new_value.connect(self.emit_value)
        layout.addRow(
            translate('RegionsTab', 'Person shown'), self.widgets[key])
        # description
        key = 'dc:description'
        self.widgets[key] = LangAltWidget(
            key, min_width=15, label=translate('RegionsTab', 'Description'))
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'Enter a "caption" describing the who, what, and why'
            ' of what is happening in this region.')))
        self.widgets[key].new_value.connect(self.emit_value)
        layout.addRow(self.widgets[key])

    @QtSlot(dict)
    @catch_all
    def emit_value(self, value):
        self.new_value.emit(self.idx, value)

    def set_value(self, region):
        self.region = region
        # extend form if needed
        layout = self.widget().layout()
        for key, value in region.items():
            if key in list(self.widgets) + ['Iptc4xmpExt:RegionBoundary']:
                continue
            if not value:
                continue
            label = key.split(':')[-1]
            label = re.sub(r'([a-z])([A-Z])', r'\1 \2', label)
            label = label.capitalize()
            if isinstance(value, dict):
                self.widgets[key] = LangAltWidget(
                    key, multi_line=False, min_width=15, label=label)
                label = None
            elif isinstance(value, list):
                self.widgets[key] = MultiStringEdit(key, min_width=15)
            else:
                self.widgets[key] = SingleLineEdit(key, min_width=15)
            self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
                'RegionsTab', 'The Image Region Structure includes optionally'
                ' any metadata property which is related to the region.')))
            self.widgets[key].new_value.connect(self.emit_value)
            if label:
                layout.addRow(label, self.widgets[key])
            else:
                layout.addRow(self.widgets[key])
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
        size.setWidth(size.height() * 140 // 100)
        return size


class AddTabButton(QtWidgets.QPushButton):
    def __init__(self, *arg, **kw):
        super(AddTabButton, self).__init__(chr(0x002b), *arg, **kw)
        set_symbol_font(self)
        scale_font(self, 130)

    def sizeHint(self):
        size = super(AddTabButton, self).sizeHint()
        size.setWidth(size.height() * 140 // 100)
        return size

    def minimumSizeHint(self):
        return super(AddTabButton, self).sizeHint()

class RegionTabs(QtWidgets.QTabWidget):
    new_regions = QtSignal(int, list)

    def __init__(self, *arg, **kw):
        super(RegionTabs, self).__init__(*arg, **kw)
        self.setTabBar(QTabBar())
        self.setFixedWidth(width_for_text(self, 'x' * 42))
        self.currentChanged.connect(self.tab_changed)
        new_tab = AddTabButton()
        self.setCornerWidget(new_tab)
        menu = QtWidgets.QMenu(new_tab)
        menu.addAction(translate('RegionsTab', 'New rectangle'),
                       self.new_rectangle)
        menu.addAction(translate('RegionsTab', 'New circle'),
                       self.new_circle)
        menu.addAction(translate('RegionsTab', 'New point'),
                       self.new_point)
        menu.addAction(translate('RegionsTab', 'New polygon'),
                       self.new_polygon)
        new_tab.setMenu(menu)

    def context_menu(self, idx, pos):
        md = self.image.metadata
        menu = QtWidgets.QMenu()
        rect_action = menu.addAction(
            translate('RegionsTab', 'New rectangle'), self.new_rectangle)
        circ_action = menu.addAction(
            translate('RegionsTab', 'New circle'), self.new_circle)
        point_action = menu.addAction(
            translate('RegionsTab', 'New point'), self.new_point)
        poly_action = menu.addAction(
            translate('RegionsTab', 'New polygon'), self.new_polygon)
        delete_action = (
            bool(md.image_region)
            and menu.addAction(translate('RegionsTab', 'Delete region')))
        action = execute(menu, pos)
        if action == delete_action:
            current = self.currentIndex()
            md.image_region = md.image_region.new_region(None, current)
            if current >= len(md.image_region):
                current = max(len(md.image_region) - 1, 0)
            self.set_image(self.image)
            self.setCurrentIndex(current)

    @QtSlot()
    @catch_all
    def new_rectangle(self):
        self.add_region({'Iptc4xmpExt:rbShape': 'rectangle',
                         'Iptc4xmpExt:rbX': 0.4,
                         'Iptc4xmpExt:rbY': 0.4,
                         'Iptc4xmpExt:rbW': 0.2,
                         'Iptc4xmpExt:rbH': 0.2})

    @QtSlot()
    @catch_all
    def new_circle(self):
        self.add_region({'Iptc4xmpExt:rbShape': 'circle',
                         'Iptc4xmpExt:rbX': 0.5,
                         'Iptc4xmpExt:rbY': 0.5,
                         'Iptc4xmpExt:rbRx': 0.15})

    @QtSlot()
    @catch_all
    def new_point(self):
        self.add_region({'Iptc4xmpExt:rbShape': 'polygon',
                         'Iptc4xmpExt:rbVertices': [{
                             'Iptc4xmpExt:rbX': 0.5,
                             'Iptc4xmpExt:rbY': 0.5}]})

    @QtSlot()
    @catch_all
    def new_polygon(self):
        self.add_region({'Iptc4xmpExt:rbShape': 'polygon',
                         'Iptc4xmpExt:rbVertices': [
                             {'Iptc4xmpExt:rbX': 0.4,
                              'Iptc4xmpExt:rbY': 0.4},
                             {'Iptc4xmpExt:rbX': 0.6,
                              'Iptc4xmpExt:rbY': 0.5},
                             {'Iptc4xmpExt:rbX': 0.5,
                              'Iptc4xmpExt:rbY': 0.6}]})

    def add_region(self, boundary):
        boundary['Iptc4xmpExt:rbUnit'] = 'relative'
        region = {'Iptc4xmpExt:RegionBoundary': boundary}
        md = self.image.metadata
        md.image_region = md.image_region.new_region(region)
        self.set_image(self.image)
        self.setCurrentIndex(len(md.image_region) - 1)

    def set_image(self, image):
        current = self.currentIndex()
        self.image = image
        regions = (image and image.metadata.image_region) or []
        if not regions:
            region_form = RegionForm(-1)
            region_form.setEnabled(False)
            self.clear()
            self.addTab(region_form, '')
            return
        blocked = self.blockSignals(True)
        self.clear()
        for idx in range(len(regions)):
            region_form = RegionForm(idx)
            region_form.new_value.connect(self.new_value)
            self.addTab(region_form, str(idx + 1))
        current = min(max(current, 0), len(regions) - 1)
        self.setCurrentIndex(current)
        self.blockSignals(blocked)
        self.tab_changed(current)

    @QtSlot(int)
    @catch_all
    def tab_changed(self, idx):
        regions = list((self.image and self.image.metadata.image_region) or [])
        if idx < 0 or idx >= len(regions):
            self.new_regions.emit(-1, regions)
            return
        region_form = self.widget(idx)
        region_form.set_value(regions[idx])
        self.new_regions.emit(idx, regions)

    @QtSlot(int, dict)
    @catch_all
    def new_value(self, idx, value):
        (key, value), = value.items()
        md = self.image.metadata
        region = md.image_region[idx]
        if 'rbUnit' in key:
            region = region.convert_unit(value, self.image)
        else:
            region = dict(region)
            if value:
                region[key] = value
            elif key in region:
                del region[key]
        md.image_region = md.image_region.new_region(region, idx)
        if key == 'Iptc4xmpExt:rRole':
            # aspect ratio constraint may have changed
            self.new_regions.emit(idx, list(md.image_region))


class TabWidget(QtWidgets.QWidget):
    @staticmethod
    def tab_name():
        return translate('RegionsTab', 'Image regions',
                         'Full name of tab shown as a tooltip')

    @staticmethod
    def tab_short_name():
        return translate('RegionsTab', '&Regions',
                         'Shortest possible name used as tab label')

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
        self.region_tabs.new_regions.connect(self.image_display.draw_boundaries)
        self.image_display.new_idx.connect(self.region_tabs.setCurrentIndex)
        self.image_display.new_value.connect(self.region_tabs.new_value)

    def refresh(self):
        self.new_selection(self.app.image_list.get_selected_images())

    def do_not_close(self):
        return False

    def new_selection(self, selection):
        if selection == [self.image_display.image]:
            return
        if len(selection) != 1:
            self.image_display.set_image(None)
            self.region_tabs.set_image(None)
            self.setEnabled(False)
            return
        self.image_display.set_image(selection[0])
        self.region_tabs.set_image(selection[0])
        self.setEnabled(True)
