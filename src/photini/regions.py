##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2023-26  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from photini.pyqt import *
from photini.types import ImageRegionItem, MD_LangAlt, RegionBoundary
from photini.vocab import IPTCRoleCV, IPTCTypeCV, MWGTypeCV
from photini.widgets import (
    CompoundWidgetMixin, ContextMenuMixin, LangAltWidget, MultiStringEdit,
    SingleLineEdit, WidgetMixin)

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
        self.setVisible(False)

    @catch_all
    def mouseMoveEvent(self, event):
        super(ResizeHandle, self).mouseMoveEvent(event)
        self.parentItem().handle_drag(self, self.pos())

    @catch_all
    def mouseReleaseEvent(self, event):
        super(ResizeHandle, self).mouseReleaseEvent(event)
        self.parentItem().emit_value()


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


class Signaller(QtCore.QObject, WidgetMixin):
    selected = QtSignal()

    def is_multiple(self):
        return False


class RegionMixin(object):
    def initialise(self, key, owner):
        self.setFlag(self.GraphicsItemFlag.ItemIsMovable)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.display = owner.image_display
        self.active = False
        self.handles = []
        self.setCursor(Qt.CursorShape.ArrowCursor)
        # QObject subclass to send signals for the region
        self.signaller = Signaller()
        self.emit_value = self.signaller.emit_value
        self.new_value = self.signaller.new_value
        self.selected = self.signaller.selected
        self.signaller._key = key
        self.signaller.get_value = self.get_value
        # a dimension to set the size of elements such as line thickness
        self.draw_unit = width_for_text(owner, 'x') * 0.14

    def set_active(self, active):
        if active == self.active:
            return
        self.active = active
        self.set_style()
        for handle in self.handles:
            handle.setVisible(active)

    def set_role(self, value):
        pass

    def set_style(self):
        pen = QtGui.QPen()
        pen.setCosmetic(True)
        pen.setWidthF(self.draw_unit * 1.5)
        if self.active:
            # fg is a thin white line, bg is a wide translucent dark line
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            pen.setColor(Qt.GlobalColor.white)
            for part in self.fg_parts:
                part.setPen(pen)
            pen.setColor(QtGui.QColor(0, 0, 0, 120))
            pen.setWidthF(self.draw_unit * 5.5)
        else:
            # fg is yellow dashes, bg is blue dashes in the gaps
            dashes = [self.draw_unit * 2.2, self.draw_unit * 3.8]
            pen.setDashPattern(dashes)
            pen.setColor(Qt.GlobalColor.yellow)
            for part in self.fg_parts:
                part.setPen(pen)
            pen.setDashPattern([
                0, self.draw_unit * 3.8, self.draw_unit * 2.2, 0])
            pen.setColor(Qt.GlobalColor.blue)
        for part in self.bg_parts:
            part.setPen(pen)

    def set_scale(self):
        transform = self.display.transform()
        scale = 1.0 / max(abs(transform.m11()), abs(transform.m21()))
        for handle in self.handles:
            handle.setScale(scale)


class RectangleRegion(QtWidgets.QGraphicsRectItem, RegionMixin):
    def __init__(self, key, boundary, owner, *arg, **kw):
        super(RectangleRegion, self).__init__(*arg, **kw)
        self.constraint = None
        self.initialise(key, owner)
        self.setFlag(self.GraphicsItemFlag.ItemSendsGeometryChanges)
        for idx in range(4):
            self.handles.append(ResizeHandle(self.draw_unit, parent=self))
        self.bg_parts = [self]
        self.fg_parts = [QtWidgets.QGraphicsRectItem(parent=self)]
        rect = self.display.to_scene.mapRect(QtCore.QRectF(
            boundary['Iptc4xmpExt:rbX'], boundary['Iptc4xmpExt:rbY'],
            boundary['Iptc4xmpExt:rbW'], boundary['Iptc4xmpExt:rbH']))
        self.setRect(rect)
        self.fg_parts[0].setRect(rect)
        self.handles[0].setPos(rect.topLeft())
        self.handles[1].setPos(rect.topRight())
        self.handles[2].setPos(rect.bottomLeft())
        self.handles[3].setPos(rect.bottomRight())
        self.set_style()
        self.set_scale()

    def set_role(self, value):
        if value.has_role('squareCropping'):
            self.constraint = 'square'
        elif value.has_role('landscapeCropping'):
            self.constraint = ('landscape', 'portrait')[
                self.display.transform().isRotating()]
        elif value.has_role('portraitCropping'):
            self.constraint = ('portrait', 'landscape')[
                self.display.transform().isRotating()]
        else:
            self.constraint = None

    @catch_all
    def itemChange(self, change, value):
        scene = self.scene()
        if scene and change == self.GraphicsItemChange.ItemSceneHasChanged:
            if self.constraint:
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
        self.selected.emit()

    @catch_all
    def mouseReleaseEvent(self, event):
        super(RectangleRegion, self).mouseReleaseEvent(event)
        self.emit_value()

    @classmethod
    def nearest_aspect(cls, width, height):
        w = abs(width)
        h = abs(height)
        for idx, boundary in enumerate(cls.ar_thresholds):
            if w <= h * boundary:
                result = cls.aspect_ratios[idx]
                break
        else:
            result = cls.aspect_ratios[-1]
        if (width * height) < 0:
            result = -result
        return result

    def constrain(self, pos, anchor, bounds=None):
        x = anchor.x()
        y = anchor.y()
        w = pos.x() - x
        h = pos.y() - y
        if self.constraint == 'square':
            aspect_ratio = 1.0
        elif self.constraint == 'landscape':
            aspect_ratio = self.nearest_aspect(w, h)
        elif self.constraint == 'portrait':
            aspect_ratio = 1.0 / self.nearest_aspect(h, w)
        if abs(w) < abs(h * aspect_ratio):
            w = h * aspect_ratio
        else:
            h = w / aspect_ratio
        pos = QtCore.QPointF(x + w, y + h)
        if bounds and not bounds.contains(pos):
            w = min(max(pos.x(), bounds.left()), bounds.right()) - x
            h = min(max(pos.y(), bounds.top()), bounds.bottom()) - y
            if abs(w) < abs(h * aspect_ratio):
                h = w / aspect_ratio
            else:
                w = h * aspect_ratio
            pos = QtCore.QPointF(x + w, y + h)
        return pos

    def handle_drag(self, handle, pos):
        idx = self.handles.index(handle)
        anchor = self.handles[3-idx].pos()
        scene = self.scene()
        bounds = scene.sceneRect()
        bounds.translate(-self.pos())
        if self.constraint:
            # force rectangle to correct aspect ratio
            pos = self.constrain(pos, anchor, bounds=bounds)
        elif not bounds.contains(pos):
            # constrain handle to scene bounds
            pos = QtCore.QPointF(
                min(max(pos.x(), bounds.left()), bounds.right()),
                min(max(pos.y(), bounds.top()), bounds.bottom()))
        self.handles[idx].setPos(pos)
        rect = QtCore.QRectF(anchor, pos)
        if idx in (0, 3):
            self.handles[1].setPos(rect.topRight())
            self.handles[2].setPos(rect.bottomLeft())
        else:
            self.handles[0].setPos(rect.topRight())
            self.handles[3].setPos(rect.bottomLeft())
        rect = rect.normalized()
        self.setRect(rect)
        self.fg_parts[0].setRect(rect)

    def get_value(self):
        rect = self.rect()
        rect.translate(self.scenePos())
        rect = self.display.from_scene.mapRect(rect)
        boundary = {
            'Iptc4xmpExt:rbUnit': 'relative',
            'Iptc4xmpExt:rbShape': 'rectangle',
            'Iptc4xmpExt:rbX': rect.x(),
            'Iptc4xmpExt:rbY': rect.y(),
            'Iptc4xmpExt:rbW': rect.width(),
            'Iptc4xmpExt:rbH': rect.height(),
            }
        return RegionBoundary(boundary)

    aspect_ratios = (4.0 / 3.0, 3.0 / 2.0, 16.0 / 9.0)

RectangleRegion.ar_thresholds = [
    math.sqrt(RectangleRegion.aspect_ratios[x-1] *
              RectangleRegion.aspect_ratios[x])
    for x in range(1, len(RectangleRegion.aspect_ratios))]


class CircleRegion(QtWidgets.QGraphicsEllipseItem, RegionMixin):
    def __init__(self, key, boundary, owner, *arg, **kw):
        super(CircleRegion, self).__init__(*arg, **kw)
        self.initialise(key, owner)
        for idx in range(4):
            self.handles.append(ResizeHandle(self.draw_unit, parent=self))
        self.bg_parts = [self]
        self.fg_parts = [QtWidgets.QGraphicsEllipseItem(parent=self)]
        centre = QtCore.QPointF(
            boundary['Iptc4xmpExt:rbX'], boundary['Iptc4xmpExt:rbY'])
        edge = centre + QtCore.QPointF(boundary['Iptc4xmpExt:rbRx'], 0.0)
        centre = self.display.to_scene.map(centre)
        edge = self.display.to_scene.map(edge)
        x = centre.x()
        y = centre.y()
        r = edge.x() - x
        rect = QtCore.QRectF(x - r, y - r, r * 2, r * 2)
        self.setRect(rect)
        self.fg_parts[0].setRect(rect)
        self.handles[0].setPos(x - r, y)
        self.handles[1].setPos(x, y - r)
        self.handles[2].setPos(x, y + r)
        self.handles[3].setPos(x + r, y)
        self.set_style()
        self.set_scale()

    @catch_all
    def mousePressEvent(self, event):
        super(CircleRegion, self).mousePressEvent(event)
        self.selected.emit()

    @catch_all
    def mouseReleaseEvent(self, event):
        super(CircleRegion, self).mouseReleaseEvent(event)
        self.emit_value()

    def handle_drag(self, handle, pos):
        idx = self.handles.index(handle)
        anchor = self.handles[3-idx].pos()
        x = anchor.x()
        y = anchor.y()
        if idx in (0, 3):
            r = (pos.x() - x) / 2.0
            x += r
            self.handles[idx].setY(y)
            self.handles[1].setPos(x, y - r)
            self.handles[2].setPos(x, y + r)
        else:
            r = (pos.y() - y) / 2.0
            y += r
            self.handles[idx].setX(x)
            self.handles[0].setPos(x - r, y)
            self.handles[3].setPos(x + r, y)
        rect = QtCore.QRectF(x - r, y - r, r * 2, r * 2).normalized()
        self.setRect(rect)
        self.fg_parts[0].setRect(rect)

    def get_value(self):
        rect = self.rect()
        rect.translate(self.scenePos())
        rect = self.display.from_scene.mapRect(rect)
        centre = rect.center()
        boundary = {
            'Iptc4xmpExt:rbUnit': 'relative',
            'Iptc4xmpExt:rbShape': 'circle',
            'Iptc4xmpExt:rbX': centre.x(),
            'Iptc4xmpExt:rbY': centre.y(),
            'Iptc4xmpExt:rbRx': rect.width() / 2.0,
            }
        return RegionBoundary(boundary)


class PointRegion(QtWidgets.QGraphicsItemGroup, RegionMixin):
    def __init__(self, key, boundary, owner, *arg, **kw):
        super(PointRegion, self).__init__(*arg, **kw)
        self.initialise(key, owner)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFlag(self.GraphicsItemFlag.ItemSendsGeometryChanges)
        # single point, draw cross hairs with a centre circle
        r = self.draw_unit * 6
        dx1 = r / 1.35
        dx2 = self.draw_unit * 20
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
        pos = boundary['Iptc4xmpExt:rbVertices'][0]
        self.setPos(self.display.to_scene.map(
            QtCore.QPointF(pos['Iptc4xmpExt:rbX'], pos['Iptc4xmpExt:rbY'])))
        self.set_style()
        self.set_scale()

    def set_scale(self):
        transform = self.display.transform()
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
        self.selected.emit()

    @catch_all
    def mouseReleaseEvent(self, event):
        super(PointRegion, self).mouseReleaseEvent(event)
        self.emit_value()

    def get_value(self):
        pos = self.display.from_scene.map(self.scenePos())
        boundary = {
            'Iptc4xmpExt:rbUnit': 'relative',
            'Iptc4xmpExt:rbShape': 'polygon',
            'Iptc4xmpExt:rbVertices': [
                {'Iptc4xmpExt:rbX': pos.x(), 'Iptc4xmpExt:rbY': pos.y()}],
            }
        return RegionBoundary(boundary)


class PolygonRegion(QtWidgets.QGraphicsPolygonItem, RegionMixin):
    def __init__(self, key, boundary, owner, *arg, **kw):
        super(PolygonRegion, self).__init__(*arg, **kw)
        self.initialise(key, owner)
        polygon = self.display.to_scene.map(QtGui.QPolygonF(
            [QtCore.QPointF(v['Iptc4xmpExt:rbX'], v['Iptc4xmpExt:rbY'])
             for v in boundary['Iptc4xmpExt:rbVertices']]))
        for idx in range(polygon.count()):
            handle = PolygonHandle(self.draw_unit, parent=self)
            handle.setPos(polygon.at(idx))
            self.handles.append(handle)
        self.setPolygon(polygon)
        self.bg_parts = [self]
        self.fg_parts = [QtWidgets.QGraphicsPolygonItem(parent=self)]
        self.fg_parts[0].setPolygon(polygon)
        self.set_style()
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
        handle.setVisible(self.active)
        transform = self.display.transform()
        scale = 1.0 / max(abs(transform.m11()), abs(transform.m21()))
        handle.setScale(scale)
        self.handles.insert(insert, handle)
        self.emit_value()

    @catch_all
    def mousePressEvent(self, event):
        super(PolygonRegion, self).mousePressEvent(event)
        self.selected.emit()

    @catch_all
    def mouseReleaseEvent(self, event):
        super(PolygonRegion, self).mouseReleaseEvent(event)
        self.emit_value()

    def handle_drag(self, handle, pos):
        idx = self.handles.index(handle)
        polygon = self.polygon()
        polygon[idx] = pos
        self.setPolygon(polygon)
        self.fg_parts[0].setPolygon(polygon)

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
        self.emit_value()

    def get_value(self):
        polygon = self.polygon()
        polygon.translate(self.scenePos())
        polygon = self.display.from_scene.map(polygon)
        boundary = {
            'Iptc4xmpExt:rbUnit': 'relative',
            'Iptc4xmpExt:rbShape': 'polygon',
            'Iptc4xmpExt:rbVertices': [
                {'Iptc4xmpExt:rbX': p.x(), 'Iptc4xmpExt:rbY': p.y()}
                for p in (polygon.at(n) for n in range(polygon.count()))],
            }
        return RegionBoundary(boundary)


class ImageGraphic(QtWidgets.QGraphicsPixmapItem):
    @catch_all
    def contextMenuEvent(self, event):
        view = self.scene().views()[0]
        pos = view.from_scene.map(event.pos())
        w = 0.25
        menu = QtWidgets.QMenu()
        x = max(min(pos.x() - (w / 2.0), 1.0 - w), 0.0)
        y = max(min(pos.y() - (w / 2.0), 1.0 - w), 0.0)
        action = menu.addAction(translate('RegionsTab', 'New rectangle'))
        action.setData({'Iptc4xmpExt:rbShape': 'rectangle',
                        'Iptc4xmpExt:rbX': x, 'Iptc4xmpExt:rbY': y,
                        'Iptc4xmpExt:rbW': w, 'Iptc4xmpExt:rbH': w})
        x = max(min(pos.x(), 1.0), 0.0)
        y = max(min(pos.y(), 1.0), 0.0)
        action = menu.addAction(translate('RegionsTab', 'New circle'))
        action.setData({'Iptc4xmpExt:rbShape': 'circle',
                        'Iptc4xmpExt:rbX': x, 'Iptc4xmpExt:rbY': y,
                        'Iptc4xmpExt:rbRx': w / 2.0})
        action = menu.addAction(translate('RegionsTab', 'New point'))
        action.setData({'Iptc4xmpExt:rbShape': 'polygon',
                        'Iptc4xmpExt:rbVertices': [{
                            'Iptc4xmpExt:rbX': x, 'Iptc4xmpExt:rbY': y}]})
        action = menu.addAction(translate('RegionsTab', 'New polygon'))
        action.setData({'Iptc4xmpExt:rbShape': 'polygon',
                        'Iptc4xmpExt:rbVertices': [
                            {'Iptc4xmpExt:rbX': x - (w / 2.0),
                             'Iptc4xmpExt:rbY': y - (w / 2.0)},
                            {'Iptc4xmpExt:rbX': x + (w / 2.0),
                             'Iptc4xmpExt:rbY': y},
                            {'Iptc4xmpExt:rbX': x,
                             'Iptc4xmpExt:rbY': y + (w / 2.0)}]})
        action = execute(menu, event.screenPos())
        if action:
            data = action.data()
            data['Iptc4xmpExt:rbUnit'] = 'relative'
            region = {'Iptc4xmpExt:RegionBoundary': data}
            view.tab_widget.add_region(region)


class ImageDisplayWidget(QtWidgets.QGraphicsView):
    def __init__(self, tab_widget, *arg, **kw):
        super(ImageDisplayWidget, self).__init__(*arg, **kw)
        self.tab_widget = tab_widget
        self.setRenderHint(
            QtGui.QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(
            QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setScene(QtWidgets.QGraphicsScene())
        self.setDragMode(self.DragMode.ScrollHandDrag)
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
        for boundary in self.boundaries():
            boundary.set_scale()

    def set_image(self, image):
        self.image = image
        scene = self.scene()
        scene.clear()
        self.resetTransform()
        if image:
            with Busy():
                pixmap = image.metadata.get_image_pixmap()
            if not pixmap:
                item = scene.addText(
                    translate('RegionsTab', 'Unreadable image format'))
            else:
                rect = self.contentsRect()
                md = image.metadata
                orientation = md.orientation
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
                item = ImageGraphic(pixmap)
                scene.addItem(item)
            scene.setSceneRect(item.boundingRect())
        # transforms between scene and normalised/relative coordinates
        rect = scene.sceneRect()
        self.to_scene = QtGui.QTransform().scale(rect.width(), rect.height())
        self.from_scene = self.to_scene.inverted()[0]

    def boundaries(self):
        return [x for x in self.items() if isinstance(
            x, (RectangleRegion, CircleRegion, PointRegion, PolygonRegion))]

    def stack_boundaries(self):
        items = self.boundaries()
        # put active item at the front by default
        for item in items:
            item.setZValue((0, len(items) * 2)[item.active])
        # ensure big regions don't hide small regions
        mode = Qt.ItemSelectionMode.ContainsItemBoundingRect
        for item_m in items:
            for item_n in items:
                if item_n == item_m:
                    continue
                if item_n.collidesWithItem(item_m, mode):
                    item_n.setZValue(max(item_n.zValue(), item_m.zValue() + 1))

    def ensure_visible(self, boundary):
        if not boundary:
            return
        # zoom out if needed to make boundary visible
        rect = boundary.boundingRect()
        visible = self.mapToScene(self.viewport().geometry()).boundingRect()
        scale = min(visible.width() / rect.width(),
                    visible.height() / rect.height())
        if scale < 1.02:
            self.adjust_zoom(scale - 1.02)
        self.ensureVisible(boundary)


class EntityConceptWidget(SingleLineEdit):
    def __init__(self, key, vocab, *arg, **kw):
        super(EntityConceptWidget, self).__init__(key, *arg, **kw)
        self.setReadOnly(True)
        self._updating = False
        self.menu = QtWidgets.QMenu(parent=self)
        self.menu.setToolTipsVisible(True)
        self.actions = []
        self.add_separator = False
        self.add_menu_items(vocab)

    def mousePressEvent(self, event):
        self.menu.popup(self.mapToGlobal(event.pos()))

    def add_menu_items(self, items, add_separator=True, exclusive=False):
        if self.add_separator:
            self.menu.addSeparator()
        self.add_separator = add_separator
        if exclusive:
            group = QtGui2.QActionGroup(self)
            group.setExclusionPolicy(group.ExclusionPolicy.ExclusiveOptional)
        for item in items:
            label = MD_LangAlt(item['data']['Iptc4xmpExt:Name']).best_match()
            tip = MD_LangAlt(item['definition']).best_match()
            if item['note']:
                tip += ' ({})'.format(MD_LangAlt(item['note']).best_match())
            action = self.menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(True)
            if exclusive:
                group.addAction(action)
            if tip:
                action.setToolTip('<p>{}</p>'.format(tip))
            action.setData(item['data'])
            action.toggled.connect(self.update_display)
            action.triggered.connect(self.action_triggered)
            self.actions.append(action)

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
            for action in self.actions:
                if item == action.data():
                    action.setChecked(True)
                    break
            else:
                # add new action
                self.add_menu_items([{
                    'data': item,
                    'definition': None,
                    'note': None}], add_separator=False)
        self._updating = False
        self.update_display()

    def get_value(self):
        result = []
        for action in self.actions:
            if action.isChecked():
                result.append(action.data())
        return result


class BoundaryWidget(QtWidgets.QWidget, WidgetMixin):
    # displays boundary unit radio buttons and "owns" boundary graphic item
    def __init__(self, key, region_form, *arg, **kw):
        super(BoundaryWidget, self).__init__(*arg, **kw)
        self._key = key
        self.region_form = region_form
        self.image_display = region_form.image_display
        self.graphic = None
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
        self.buttons['pixel'].clicked.connect(self.emit_value)
        self.layout().addWidget(self.buttons['pixel'])
        self.buttons['relative'] = QtWidgets.QRadioButton(
            translate('RegionsTab', 'relative'))
        self.buttons['relative'].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'Relative part of the size of an image along the'
            ' x- or the y-axis.')))
        self.buttons['relative'].clicked.connect(self.emit_value)
        self.layout().addWidget(self.buttons['relative'])
        self.setFixedHeight(self.sizeHint().height())

    def get_value(self):
        if not self.graphic:
            return None
        value = self.graphic.get_value()
        if self.buttons['pixel'].isChecked():
            value = value.to_pixel(self.image_dims)
        else:
            value = value.to_relative(self.image_dims)
        return value

    def is_multiple(self):
        return False

    def set_value(self, value):
        scene = self.image_display.scene()
        active = False
        if self.graphic:
            active = self.graphic.active
            scene.removeItem(self.graphic)
            self.graphic = None
        value = value or {}
        for key in self.buttons:
            self.buttons[key].setChecked(key == value.get('Iptc4xmpExt:rbUnit'))
        if not value:
            return
        rect = scene.sceneRect()
        self.image_dims = {'stDim:w': rect.width(), 'stDim:h': rect.height()}
        value = value.to_relative(self.image_dims)
        if value['Iptc4xmpExt:rbShape'] == 'rectangle':
            self.graphic = RectangleRegion(self._key, value, self)
        elif value['Iptc4xmpExt:rbShape'] == 'circle':
            self.graphic = CircleRegion(self._key, value, self)
        elif len(value['Iptc4xmpExt:rbVertices']) == 1:
            self.graphic = PointRegion(self._key, value, self)
        else:
            self.graphic = PolygonRegion(self._key, value, self)
        if active:
            self.graphic.set_active(active)
        self.graphic.new_value.connect(self.new_boundary)
        self.graphic.selected.connect(self.region_form.region_clicked)
        scene.addItem(self.graphic)

    @QtSlot(dict)
    @catch_all
    def new_boundary(self, value):
        boundary = value[self._key]
        if self.buttons['pixel'].isChecked():
            value[self._key] = boundary.to_pixel(self.image_dims)
        else:
            value[self._key] = boundary.to_relative(self.image_dims)
        self.new_value.emit(value)

    def set_active(self, active):
        if self.graphic:
            self.graphic.set_active(active)

    @QtSlot(dict)
    @catch_all
    def set_role(self, value):
        if self.graphic:
            self.graphic.set_role(ImageRegionItem(value))


class RegionForm(QtWidgets.QScrollArea, ContextMenuMixin, CompoundWidgetMixin):
    select_region = QtSignal(int)
    clipboard_key = 'RegionForm'

    def __init__(self, idx, image_display, *arg, **kw):
        super(RegionForm, self).__init__(*arg, **kw)
        self._key = idx
        self.app = QtWidgets.QApplication.instance()
        self.image_display = image_display
        self.setFrameStyle(QtWidgets.QFrame.Shape.NoFrame)
        self.setWidget(QtWidgets.QWidget())
        self.setWidgetResizable(True)
        layout = QtWidgets.QFormLayout()
        layout.setRowWrapPolicy(layout.RowWrapPolicy.WrapLongRows)
        self.widget().setLayout(layout)
        self.widgets = {}
        self.extra_keys = []
        # name
        key = 'Iptc4xmpExt:Name'
        self.widgets[key] = LangAltWidget(
            key, multi_line=False, min_width=15,
            label=translate('RegionsTab', 'Region name'))
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'Free-text name of the region. Should be unique among'
            ' all Region Names of an image.')))
        layout.addRow(self.widgets[key])
        # identifier
        key = 'Iptc4xmpExt:rId'
        self.widgets[key] = SingleLineEdit(key, min_width=15)
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'Identifier of the region. Must be unique among all'
            ' Region Identifiers of an image. Does not have to be unique beyond'
            ' the metadata of this image.')))
        layout.addRow(translate('RegionsTab', 'Identifier'), self.widgets[key])
        # units & boundary graphic
        key = 'Iptc4xmpExt:RegionBoundary'
        self.widgets[key] = BoundaryWidget(key, self)
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'Unit used for measuring dimensions of the boundary'
            ' of a region.')))
        layout.addRow(
            translate('RegionsTab', 'Boundary unit'), self.widgets[key])
        self.set_active = self.widgets[key].set_active
        # roles
        key = 'Iptc4xmpExt:rRole'
        self.widgets[key] = EntityConceptWidget(key, IPTCRoleCV.vocab.values())
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'Role of this region among all regions of this image'
            ' or of other images. The value SHOULD be taken from a Controlled'
            ' Vocabulary.')))
        self.widgets[key].new_value.connect(
            self.widgets['Iptc4xmpExt:RegionBoundary'].set_role)
        layout.addRow(translate('RegionsTab', 'Role'), self.widgets[key])
        # content types
        key = 'Iptc4xmpExt:rCtype'
        self.widgets[key] = EntityConceptWidget(key, IPTCTypeCV.vocab.values())
        self.widgets[key].add_menu_items(
            MWGTypeCV.vocab.values(), exclusive=True)
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'The semantic type of what is shown inside the'
            ' region. The value SHOULD be taken from a Controlled'
            ' Vocabulary.')))
        layout.addRow(
            translate('RegionsTab', 'Content type'), self.widgets[key])
        # person im image
        key = 'Iptc4xmpExt:PersonInImage'
        self.widgets[key] = MultiStringEdit(key, min_width=15)
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'Enter the names of people shown in this region.'
            ' Separate multiple entries with ";" characters.')))
        layout.addRow(
            translate('RegionsTab', 'Person shown'), self.widgets[key])
        # description
        key = 'dc:description'
        self.widgets[key] = LangAltWidget(
            key, min_width=15, label=translate('RegionsTab', 'Description'))
        self.widgets[key].setToolTip('<p>{}</p>'.format(translate(
            'RegionsTab', 'Enter a "caption" describing the who, what, and why'
            ' of what is happening in this region.')))
        layout.addRow(self.widgets[key])
        for widget in self.sub_widgets():
            widget.new_value.connect(self.sw_new_value)
        # disable widgets until value is set
        self.set_value_dict({})

    @catch_all
    def contextMenuEvent(self, event):
        self.compound_context_menu(event, title=translate(
            'RegionsTab', 'All "region {}" data').format(self._key + 1))

    def sub_widgets(self):
        return self.widgets.values()

    def is_multiple(self):
        return False

    @QtSlot()
    @catch_all
    def region_clicked(self):
        self.select_region.emit(self._key)

    def get_boundary(self):
        return self.widgets['Iptc4xmpExt:RegionBoundary'].graphic

    def set_value(self, region):
        region = region or {}
        # shrink or extend form if needed
        layout = self.widget().layout()
        for key in self.extra_keys:
            if key not in region or not region[key]:
                layout.removeRow(self.widgets[key])
                self.extra_keys.remove(key)
                del self.widgets[key]
        for key, value in region.items():
            if not value or key in self.widgets:
                continue
            self.extra_keys.append(key)
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
            self.widgets[key].setToolTip('<p>{}<br/>{}</p>'.format(
                key, translate(
                    'RegionsTab', 'The Image Region Structure includes'
                    ' optionally any metadata property which is related to the'
                    ' region.')))
            self.widgets[key].new_value.connect(self.update_value)
            if label:
                layout.addRow(label, self.widgets[key])
            else:
                layout.addRow(self.widgets[key])
        # set values and enable or disable widgets
        for widget in self.sub_widgets():
            widget.setEnabled(bool(region))
            widget.set_value_dict(region)
        # set region constraints
        self.widgets['Iptc4xmpExt:RegionBoundary'].set_role(region)


class QTabBar(QtWidgets.QTabBar):
    @catch_all
    def tabSizeHint(self, index):
        size = super(QTabBar, self).tabSizeHint(index)
        size.setWidth(size.height() * 140 // 100)
        return size


class RegionTabs(QtWidgets.QTabWidget, WidgetMixin):
    _key = 'iptcExt:ImageRegion'

    def __init__(self, *arg, **kw):
        super(RegionTabs, self).__init__(*arg, **kw)
        self.app = QtWidgets.QApplication.instance()
        self.setTabBar(QTabBar())
        self.setFixedWidth(width_for_text(self, 'x' * 42))
        self.currentChanged.connect(self.tab_changed)
        # image display area
        self.image_display = ImageDisplayWidget(self)

    def emit_value(self):
        pass

    def get_value(self):
        result = {}
        for idx in range(self.count()):
            result[idx] = self.widget(idx).get_value()
        return result

    def is_multiple(self):
        return False

    def set_value(self, value):
        value = value or {}
        md = self.image.metadata
        md.image_region = md.image_region.set_regions(value.values())
        self.update_display()

    def add_region(self, region):
        self.update_value({self.count() - 1: region})

    def update_display(self, current=None):
        if current is None:
            current = self.currentIndex()
        if self.image:
            regions = self.image.metadata.image_region
        else:
            regions = []
        data_len = len(regions)
        # always have one extra tab to paste into
        count = data_len + 1
        # add tabs if needed
        idx = self.count()
        while idx < count:
            region_form = RegionForm(idx, self.image_display)
            region_form.new_value.connect(self.update_value)
            region_form.select_region.connect(self.setCurrentIndex)
            idx += 1
            self.addTab(region_form, str(idx))
        self.widget(data_len).set_value(None)
        # remove surplus tabs
        idx = self.count()
        while idx > count:
            idx -= 1
            self.widget(idx).set_value(None)
            self.removeTab(idx)
        # set data
        for idx, region in enumerate(regions):
            self.widget(idx).set_value(region)
        # make current region selected and visible
        current = max(0, min(current, data_len - 1))
        self.setCurrentIndex(current)
        self.tab_changed(current)

    def set_image(self, image):
        current = self.currentIndex()
        blocked = self.blockSignals(True)
        self.clear()
        self.blockSignals(blocked)
        self.image_display.scene().clear()
        self.image_display.set_image(image)
        self.image = image
        if image:
            md = image.metadata
            image_dims = md.dimensions
            image_dims = {'w': image_dims['width'], 'h': image_dims['height']}
            region_dims = md.image_region.get_dimensions()
            if region_dims and region_dims != image_dims:
                dialog = QtWidgets.QMessageBox(parent=self)
                dialog.setWindowTitle(
                    translate('RegionsTab', 'Photini: image size'))
                dialog.setText('<h3>{}</h3>'.format(
                    translate('RegionsTab', 'Image has been resized.')))
                dialog.setInformativeText(translate(
                    'RegionsTab', 'Image dimensions {w_im}x{h_im} do not match'
                    ' region definition {w_reg}x{h_reg}. The image regions may'
                    ' be incorrect.').format(
                        w_im=image_dims['w'], h_im=image_dims['h'],
                        w_reg=region_dims['w'], h_reg=region_dims['h']))
                dialog.setStandardButtons(dialog.StandardButton.Ok)
                dialog.setIcon(dialog.Icon.Warning)
                execute(dialog)
            # set region image dimensions without flagging as changed
            changed = md.changed()
            md.image_region = md.image_region.set_dimensions(image_dims)
            md.set_changed(changed)
        self.update_display(current=current)

    @QtSlot(int)
    @catch_all
    def tab_changed(self, idx):
        for n in range(self.count()):
            self.widget(n).set_active(n == idx)
        self.image_display.stack_boundaries()
        self.image_display.ensure_visible(self.widget(idx).get_boundary())

    @QtSlot(dict)
    @catch_all
    def update_value(self, value):
        (idx, value), = value.items()
        simple_update = len(value) == 1
        md = self.image.metadata
        regions = list(md.image_region)
        while len(regions) <= idx:
            regions.append({})
            simple_update = False
        regions[idx].update(value)
        md.image_region = md.image_region.set_regions(regions)
        if 'Iptc4xmpExt:PersonInImage' in value:
            people = list(md.people)
            for name in value['Iptc4xmpExt:PersonInImage']:
                if name not in people:
                    people.append(name)
            md.people = people
        if not simple_update:
            self.update_display(current=idx)


class TabWidget(QtWidgets.QWidget, ContextMenuMixin, CompoundWidgetMixin):
    clipboard_key = 'RegionsTab'

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
        self.widgets = {'region_tabs': RegionTabs()}
        self.layout().addWidget(self.widgets['region_tabs'])
        # image display area
        self.layout().addWidget(
            self.widgets['region_tabs'].image_display, stretch=1)

    @catch_all
    def contextMenuEvent(self, event):
        self.compound_context_menu(event)

    def sub_widgets(self):
        return [self.widgets['region_tabs']]

    @QtSlot()
    @catch_all
    def emit_value(self):
        pass

    def refresh(self):
        self.new_selection(self.app.image_list.get_selected_images())

    def do_not_close(self):
        return False

    def new_selection(self, selection):
        if len(selection) != 1:
            self.widgets['region_tabs'].set_image(None)
            self.setEnabled(False)
            return
        self.widgets['region_tabs'].set_image(selection[0])
        self.setEnabled(True)
