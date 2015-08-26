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
    def __init__(self, parent=None):
        QtWidgets.QPlainTextEdit.__init__(self, parent)
        self.setText = self.setPlainText
        self.text = self.toPlainText

    editingFinished = QtCore.pyqtSignal()
    def focusOutEvent(self, event):
        self.editingFinished.emit()
        QtWidgets.QPlainTextEdit.focusOutEvent(self, event)

class LineEditWithAuto(QtWidgets.QWidget):
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # line edit box
        self.edit = QtWidgets.QLineEdit()
        layout.addWidget(self.edit)
        # auto complete button
        self.auto = QtWidgets.QPushButton(self.tr('Auto'))
        layout.addWidget(self.auto)
        # adopt child widget methods and signals
        self.editingFinished = self.edit.editingFinished
        self.setText = self.edit.setText
        self.clear = self.edit.clear
        self.text = self.edit.text
        self.autoComplete = self.auto.clicked

class Descriptive(QtWidgets.QWidget):
    def __init__(self, config_store, image_list, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.config_store = config_store
        self.image_list = image_list
        self.form = QtWidgets.QFormLayout()
        self.setLayout(self.form)
        if QT_VERSION[0] >= 5:
            self.trUtf8 = self.tr
        # construct widgets
        self.widgets = dict()
        # title
        self.widgets['title'] = QtWidgets.QLineEdit()
        self.widgets['title'].editingFinished.connect(self.new_title)
        self.form.addRow(self.tr('Title / Object Name'), self.widgets['title'])
        # description
        self.widgets['description'] = MultiLineEdit()
        self.widgets['description'].editingFinished.connect(self.new_description)
        self.form.addRow(
            self.tr('Description / Caption'), self.widgets['description'])
        # keywords
        self.widgets['keywords'] = QtWidgets.QLineEdit()
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
        self.widgets['creator'].setText(name)
        self._new_value('creator')

    def _new_value(self, key):
        value = self.widgets[key].text()
        if value != multiple_values:
            for image in self.image_list.get_selected_images():
                setattr(image.metadata, key, value)
        self._update_widget(key)

    def _update_widget(self, key):
        images = self.image_list.get_selected_images()
        value = getattr(images[0].metadata, key)
        for image in images[1:]:
            if getattr(image.metadata, key) != value:
                self.widgets[key].setText(multiple_values)
                return
        if not value:
            self.widgets[key].clear()
        elif isinstance(value, list):
            self.widgets[key].setText('; '.join(value))
        else:
            self.widgets[key].setText(value)

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        if not selection:
            for key in self.widgets:
                self.widgets[key].clear()
            self.setEnabled(False)
            return
        for key in self.widgets:
            self._update_widget(key)
        self.setEnabled(True)
