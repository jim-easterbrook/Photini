#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2012-13  Jim Easterbrook  jim@jim-easterbrook.me.uk
#
#  This program is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see
#  <http://www.gnu.org/licenses/>.

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt

class EditSettings(QtGui.QDialog):
    def __init__(self, parent, config_store):
        QtGui.QDialog.__init__(self, parent)
        self.config_store = config_store
        self.setWindowTitle('Photini: settings')
        self.setLayout(QtGui.QGridLayout())
        self.layout().setRowStretch(0, 1)
        self.layout().setColumnStretch(0, 1)
        # main dialog area
        scroll_area = QtGui.QScrollArea()
        self.layout().addWidget(scroll_area, 0, 0, 1, 2)
        panel = QtGui.QWidget()
        panel.setLayout(QtGui.QFormLayout())
        # done button
        done_button = QtGui.QPushButton('Done')
        done_button.clicked.connect(self.accept)
        self.layout().addWidget(done_button, 1, 1)
        # copyright holder name
        self.copyright_name = QtGui.QLineEdit()
        self.copyright_name.setText(
            self.config_store.get('user', 'copyright_name', ''))
        self.copyright_name.editingFinished.connect(
            self.new_copyright_name)
        panel.layout().addRow('Copyright holder', self.copyright_name)
        # creator name
        self.creator_name = QtGui.QLineEdit()
        self.creator_name.setText(
            self.config_store.get('user', 'creator_name', ''))
        self.creator_name.editingFinished.connect(
            self.new_creator_name)
        panel.layout().addRow('Creator', self.creator_name)
        # reset flickr
        self.reset_flickr = QtGui.QPushButton('OK')
        self.reset_flickr.setEnabled(self.config_store.has_section('flickr'))
        self.reset_flickr.clicked.connect(self.do_reset_flickr)
        panel.layout().addRow('Reset Flickr', self.reset_flickr)
        # reset picasa
        self.reset_picasa = QtGui.QPushButton('OK')
        self.reset_picasa.setEnabled(self.config_store.has_section('picasa'))
        self.reset_picasa.clicked.connect(self.do_reset_picasa)
        panel.layout().addRow('Reset Picasa', self.reset_picasa)
        # add panel to scroll area after its size is known
        scroll_area.setWidget(panel)

    def new_copyright_name(self):
        value = unicode(self.copyright_name.text())
        self.config_store.set('user', 'copyright_name', value)

    def new_creator_name(self):
        value = unicode(self.creator_name.text())
        self.config_store.set('user', 'creator_name', value)

    def do_reset_flickr(self):
        self.config_store.remove_section('flickr')
        self.reset_flickr.setDisabled(True)

    def do_reset_picasa(self):
        self.config_store.remove_section('picasa')
        self.reset_picasa.setDisabled(True)
