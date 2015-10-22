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

"""Left to right, top to bottom, fill available space Qt layout.

Python implementation, based on C++ example at
http://doc.qt.io/qt-4.8/qt-layouts-flowlayout-example.html

"""

from __future__ import unicode_literals

from .pyqt import Qt, QtCore, QtWidgets

class FlowLayout(QtWidgets.QLayout):
    def __init__(self, *arg, **kw):
        super(FlowLayout, self).__init__(*arg, **kw)
        self.item_list = []

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
        return True

    def heightForWidth(self, width):
        return self._do_layout(QtCore.QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self.item_list:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        size += QtCore.QSize(left + right, top + bottom)
        return size

    def _do_layout(self, rect, test_only):
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(left, top, -right, -bottom)
        x = effective_rect.x()
        y = effective_rect.y()
        row_height = 0
        for item in self.item_list:
            item_size = item.sizeHint()
            if x + item_size.width() > effective_rect.right() and row_height > 0:
                x = effective_rect.x()
                y += row_height
                row_height = 0
            if not test_only:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item_size))
            x += item_size.width()
            row_height = max(row_height, item_size.height())
        return y + row_height - rect.y() + bottom
