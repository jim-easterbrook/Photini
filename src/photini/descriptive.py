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

from datetime import datetime

from .pyqt import Qt, QtCore, QtWidgets, QT_VERSION
from .utils import multiple_values

class MultiLineEdit(QtWidgets.QPlainTextEdit):
    editingFinished = QtCore.pyqtSignal()

    def __init__(self, *arg, **kw):
        super(MultiLineEdit, self).__init__(*arg, **kw)
        self._is_multiple = False

    def focusOutEvent(self, event):
        self.editingFinished.emit()
        super(MultiLineEdit, self).focusOutEvent(event)

    def set_value(self, value):
        self._is_multiple = False
        if not value:
            self.clear()
            if QT_VERSION >= [5, 3]:
                self.setPlaceholderText('')
        elif isinstance(value, list):
            self.setPlainText('; '.join(value))
        else:
            self.setPlainText(value)

    def get_value(self):
        return self.toPlainText()

    def set_multiple(self):
        self._is_multiple = True
        if QT_VERSION >= [5, 3]:
            self.setPlaceholderText(multiple_values)
            self.clear()
        else:
            self.setPlainText(multiple_values)

    def is_multiple(self):
        return self._is_multiple and not bool(self.get_value())


class LineEdit(QtWidgets.QLineEdit):
    def __init__(self, *arg, **kw):
        super(LineEdit, self).__init__(*arg, **kw)
        self._is_multiple = False

    def set_value(self, value):
        self._is_multiple = False
        if not value:
            self.clear()
            self.setPlaceholderText('')
        elif isinstance(value, list):
            self.setText('; '.join(value))
        else:
            self.setText(value)

    def get_value(self):
        return self.text()

    def set_multiple(self):
        self._is_multiple = True
        self.setPlaceholderText(multiple_values)
        self.clear()

    def is_multiple(self):
        return self._is_multiple and not bool(self.get_value())


class LineEditWithAuto(QtWidgets.QWidget):
    def __init__(self, *arg, **kw):
        super(LineEditWithAuto, self).__init__(*arg, **kw)
        self._is_multiple = False
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # line edit box
        self.edit = LineEdit()
        layout.addWidget(self.edit)
        # auto complete button
        self.auto = QtWidgets.QPushButton(self.tr('Auto'))
        layout.addWidget(self.auto)
        # adopt child widget methods and signals
        self.set_value = self.edit.set_value
        self.get_value = self.edit.get_value
        self.set_multiple = self.edit.set_multiple
        self.is_multiple = self.edit.is_multiple
        self.editingFinished = self.edit.editingFinished
        self.autoComplete = self.auto.clicked


class Descriptive(QtWidgets.QWidget):
    def __init__(self, config_store, image_list, *arg, **kw):
        super(Descriptive, self).__init__(*arg, **kw)
        self.config_store = config_store
        self.image_list = image_list
        self.form = QtWidgets.QFormLayout()
        self.setLayout(self.form)
        if QT_VERSION[0] >= 5:
            self.trUtf8 = self.tr
        # construct widgets
        self.widgets = {}
        # title
        self.widgets['title'] = LineEdit()
        self.widgets['title'].editingFinished.connect(self.new_title)
        self.form.addRow(self.tr('Title / Object Name'), self.widgets['title'])
        # description
        self.widgets['description'] = MultiLineEdit()
        self.widgets['description'].editingFinished.connect(self.new_description)
        self.form.addRow(
            self.tr('Description / Caption'), self.widgets['description'])
        # keywords
        self.widgets['keywords'] = LineEdit()
        self.widgets['keywords'].editingFinished.connect(self.new_keywords)
        self.form.addRow(self.tr('Keywords'), self.widgets['keywords'])
        # copyright
        self.widgets['copyright'] = LineEditWithAuto()
        self.widgets['copyright'].editingFinished.connect(self.new_copyright)
        self.widgets['copyright'].autoComplete.connect(self.auto_copyright)
        self.form.addRow(self.tr('Copyright'), self.widgets['copyright'])
        # creator
        self.widgets['creator'] = LineEditWithAuto()
        self.widgets['creator'].editingFinished.connect(self.new_creator)
        self.widgets['creator'].autoComplete.connect(self.auto_creator)
        self.form.addRow(self.tr('Creator / Artist'), self.widgets['creator'])
        # disable until an image is selected
        self.setEnabled(False)

    def refresh(self):
        pass

    def do_not_close(self):
        return False

    def new_title(self):
        self._new_value('title')

    def new_description(self):
        self._new_value('description')

    def new_keywords(self):
        self._new_value('keywords')

    def new_copyright(self):
        self._new_value('copyright')

    def new_creator(self):
        self._new_value('creator')

    def auto_copyright(self):
        name = self.config_store.get('user', 'copyright_name')
        if not name:
            name, OK = QtWidgets.QInputDialog.getText(
                self, self.tr('Photini: input name'),
                self.tr("Please type in the copyright holder's name"),
                text=self.config_store.get('user', 'creator_name', ''))
            if OK and name:
                self.config_store.set('user', 'copyright_name', name)
            else:
                name = ''
        for image in self.image_list.get_selected_images():
            date = image.metadata.date_taken
            if date is not None:
                date = date.date
            if date is None:
                date = datetime.now()
            value = self.trUtf8(
                'Copyright ©{0:d} {1}. All rights reserved.').format(
                    date.year, name)
            image.metadata.copyright = value
        self._update_widget('copyright')

    def auto_creator(self):
        name = self.config_store.get('user', 'creator_name')
        if not name:
            name, OK = QtWidgets.QInputDialog.getText(
                self, self.tr('Photini: input name'),
                self.tr("Please type in the creator's name"),
                text=self.config_store.get('user', 'copyright_name', ''))
            if OK and name:
                self.config_store.set('user', 'creator_name', name)
            else:
                name = ''
        for image in self.image_list.get_selected_images():
            image.metadata.creator = name
        self._update_widget('creator')

    def _new_value(self, key):
        if not self.widgets[key].is_multiple():
            value = self.widgets[key].get_value()
            for image in self.image_list.get_selected_images():
                setattr(image.metadata, key, value)
        self._update_widget(key)

    def _update_widget(self, key):
        images = self.image_list.get_selected_images()
        value = getattr(images[0].metadata, key)
        for image in images[1:]:
            if getattr(image.metadata, key) != value:
                self.widgets[key].set_multiple()
                return
        self.widgets[key].set_value(value)

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        if not selection:
            for key in self.widgets:
                self.widgets[key].set_value(None)
            self.setEnabled(False)
            return
        for key in self.widgets:
            self._update_widget(key)
        self.setEnabled(True)
