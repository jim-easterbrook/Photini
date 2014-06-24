##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-13  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

"""Left to right, top to bottom, fill available space Qt layout.

Python implementation of C++ example at
http://doc.qt.digia.com/4.7-snapshot/layouts-flowlayout.html

"""

from __future__ import unicode_literals

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt

class FlowLayout(QtGui.QLayout):
    def __init__(self, parent=None, hSpacing=-1, vSpacing=-1):
        QtGui.QLayout.__init__(self, parent)
        self.h_space = hSpacing
        self.v_space = vSpacing
        self.item_list = list()

    def addItem(self, item):
        self.item_list.append(item)

    def horizontalSpacing(self):
        if self.h_space >= 0:
            return self.h_space
        return self._smart_spacing(QtGui.QStyle.PM_LayoutHorizontalSpacing)

    def verticalSpacing(self):
        if self.v_space >= 0:
            return self.v_space
        return self._smart_spacing(QtGui.QStyle.PM_LayoutVerticalSpacing)

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
        return True

    def heightForWidth(self, width):
        return self._do_layout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        QtGui.QLayout.setGeometry(self, rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self.item_list:
            size = size.expandedTo(item.minimumSize())
        size += QtCore.QSize(2 * self.margin(), 2 * self.margin())
        return size

    def _do_layout(self, rect, testOnly):
        left, top, right, bottom = self.getContentsMargins()
        effectiveRect = rect.adjusted(left, top, -right, -bottom)
        x = effectiveRect.x()
        y = effectiveRect.y()
        lineHeight = 0
        for item in self.item_list:
            wid = item.widget()
            spaceX = self.horizontalSpacing()
            if spaceX == -1:
                spaceX = wid.style().layoutSpacing(
                    QSizePolicy.PushButton, QSizePolicy.PushButton,
                    Qt.Horizontal)
            spaceY = self.verticalSpacing()
            if spaceY == -1:
                spaceY = wid.style().layoutSpacing(
                    QSizePolicy.PushButton, QSizePolicy.PushButton,
                    Qt.Vertical)
            if (x + item.sizeHint().width() > effectiveRect.right() and
                    lineHeight > 0):
                x = effectiveRect.x()
                y += lineHeight + spaceY
                lineHeight = 0
            if not testOnly:
                item.setGeometry(
                    QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))
            x += item.sizeHint().width() + spaceX
            lineHeight = max(lineHeight, item.sizeHint().height())
        return y + lineHeight - rect.y() + bottom

    def _smart_spacing(self, pm):
        parent = self.parent()
        if not parent:
            return -1
        if parent.isWidgetType():
            return parent.style().pixelMetric(pm, widget=parent)
        return parent.spacing()
