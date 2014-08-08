# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-14  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt

class MultiLineEdit(QtGui.QPlainTextEdit):
    def __init__(self, parent=None):
        QtGui.QPlainTextEdit.__init__(self, parent)
        self.setText = self.setPlainText
        self.text = self.toPlainText

    editingFinished = QtCore.pyqtSignal()
    def focusOutEvent(self, event):
        self.editingFinished.emit()
        QtGui.QPlainTextEdit.focusOutEvent(self, event)

class LineEditWithAuto(QtGui.QWidget):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        layout = QtGui.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # line edit box
        self.edit = QtGui.QLineEdit()
        layout.addWidget(self.edit)
        # auto complete button
        self.auto = QtGui.QPushButton('Auto')
        layout.addWidget(self.auto)
        # adopt child widget methods and signals
        self.editingFinished = self.edit.editingFinished
        self.setText = self.edit.setText
        self.clear = self.edit.clear
        self.text = self.edit.text
        self.autoComplete = self.auto.clicked

class Descriptive(QtGui.QWidget):
    def __init__(self, config_store, image_list, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.config_store = config_store
        self.image_list = image_list
        self.form = QtGui.QFormLayout()
        self.setLayout(self.form)
        # construct widgets
        self.widgets = dict()
        # title
        self.widgets['title'] = QtGui.QLineEdit()
        self.widgets['title'].editingFinished.connect(self.new_title)
        self.form.addRow('Title / Object Name', self.widgets['title'])
        # description
        self.widgets['description'] = MultiLineEdit()
        self.widgets['description'].editingFinished.connect(self.new_description)
        self.form.addRow('Description / Caption', self.widgets['description'])
        # keywords
        self.widgets['keywords'] = QtGui.QLineEdit()
        self.widgets['keywords'].editingFinished.connect(self.new_keywords)
        self.form.addRow('Keywords', self.widgets['keywords'])
        # copyright
        self.widgets['copyright'] = LineEditWithAuto()
        self.widgets['copyright'].editingFinished.connect(self.new_copyright)
        self.widgets['copyright'].autoComplete.connect(self.auto_copyright)
        self.form.addRow('Copyright', self.widgets['copyright'])
        # creator
        self.widgets['creator'] = LineEditWithAuto()
        self.widgets['creator'].editingFinished.connect(self.new_creator)
        self.widgets['creator'].autoComplete.connect(self.auto_creator)
        self.form.addRow('Creator / Artist', self.widgets['creator'])
        # disable until an image is selected
        for key in self.widgets:
            self.widgets[key].setEnabled(False)

    def refresh(self):
        pass

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
            name, OK = QtGui.QInputDialog.getText(
                self, 'Photini: input name',
                "Please type in the copyright holder's name",
                text=self.config_store.get('user', 'creator_name', ''))
            if OK and name:
                name = unicode(name)
                self.config_store.set('user', 'copyright_name', name)
            else:
                name = ''
        for image in self.image_list.get_selected_images():
            date = image.metadata.get_item('date_taken')
            if date.empty():
                date = datetime.now()
            else:
                date = date.value
            value = 'Copyright ©%d %s. All rights reserved.' % (
                date.year, name)
            image.metadata.set_item('copyright', value)
        self._update_widget('copyright')

    def auto_creator(self):
        name = self.config_store.get('user', 'creator_name')
        if not name:
            name, OK = QtGui.QInputDialog.getText(
                self, 'Photini: input name',
                "Please type in the creator's name",
                text=self.config_store.get('user', 'copyright_name', ''))
            if OK and name:
                name = unicode(name)
                self.config_store.set('user', 'creator_name', name)
            else:
                name = ''
        self.widgets['creator'].setText(name)
        self._new_value('creator')

    def _new_value(self, key):
        value = unicode(self.widgets[key].text())
        if value != '<multiple values>':
            for image in self.image_list.get_selected_images():
                image.metadata.set_item(key, value)
        self._update_widget(key)

    def _update_widget(self, key):
        value = None
        for image in self.image_list.get_selected_images():
            new_value = image.metadata.get_item(key).as_str()
            if value and new_value != value:
                self.widgets[key].setText('<multiple values>')
                return
            value = new_value
        if value:
            self.widgets[key].setText(value)
        else:
            self.widgets[key].clear()

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        if not selection:
            for key in self.widgets:
                self.widgets[key].clear()
                self.widgets[key].setEnabled(False)
            return
        for key in self.widgets:
            self.widgets[key].setEnabled(True)
            self._update_widget(key)
