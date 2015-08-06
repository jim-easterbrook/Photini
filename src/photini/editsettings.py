# -*- coding: utf-8 -*-
#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2012-15  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from __future__ import unicode_literals

try:
    import keyring
except ImportError:
    keyring = None
from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt

class EditSettings(QtGui.QDialog):
    def __init__(self, parent, config_store):
        QtGui.QDialog.__init__(self, parent)
        self.config_store = config_store
        self.setWindowTitle(self.tr('Photini: settings'))
        self.setLayout(QtGui.QVBoxLayout())
        # main dialog area
        scroll_area = QtGui.QScrollArea()
        self.layout().addWidget(scroll_area)
        panel = QtGui.QWidget()
        panel.setLayout(QtGui.QFormLayout())
        # apply & cancel buttons
        self.button_box = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Apply | QtGui.QDialogButtonBox.Cancel)
        self.button_box.clicked.connect(self.button_clicked)
        self.layout().addWidget(self.button_box)
        # copyright holder name
        self.copyright_name = QtGui.QLineEdit()
        self.copyright_name.setText(
            self.config_store.get('user', 'copyright_name', ''))
        self.copyright_name.setMinimumWidth(200)
        panel.layout().addRow(self.tr('Copyright holder'), self.copyright_name)
        # creator name
        self.creator_name = QtGui.QLineEdit()
        self.creator_name.setText(
            self.config_store.get('user', 'creator_name', ''))
        panel.layout().addRow(self.tr('Creator'), self.creator_name)
        # reset flickr
        self.reset_flickr = QtGui.QCheckBox()
        panel.layout().addRow(self.tr('Reset Flickr'), self.reset_flickr)
        if not keyring or keyring.get_password('photini', 'flickr') is None:
            self.reset_flickr.setDisabled(True)
            panel.layout().labelForField(self.reset_flickr).setDisabled(True)
        # reset picasa
        self.reset_picasa = QtGui.QCheckBox()
        panel.layout().addRow(self.tr('Reset Picasa'), self.reset_picasa)
        if not keyring or keyring.get_password('photini', 'picasa') is None:
            self.reset_picasa.setDisabled(True)
            panel.layout().labelForField(self.reset_picasa).setDisabled(True)
        # IPTC data
        force_iptc = eval(self.config_store.get('files', 'force_iptc', 'False'))
        self.write_iptc = QtGui.QCheckBox(self.tr('Write unconditionally'))
        self.write_iptc.setChecked(force_iptc)
        panel.layout().addRow(self.tr('IPTC metadata'), self.write_iptc)
        # sidecar files
        if_mode = eval(self.config_store.get('files', 'image', 'True'))
        sc_mode = self.config_store.get('files', 'sidecar', 'auto')
        if not if_mode:
            sc_mode = 'always'
        self.sc_always = QtGui.QRadioButton(self.tr('Always create'))
        self.sc_always.setChecked(sc_mode == 'always')
        panel.layout().addRow(self.tr('Sidecar files'), self.sc_always)
        self.sc_auto = QtGui.QRadioButton(self.tr('Create if necessary'))
        self.sc_auto.setChecked(sc_mode == 'auto')
        self.sc_auto.setEnabled(if_mode)
        panel.layout().addRow('', self.sc_auto)
        self.sc_delete = QtGui.QRadioButton(self.tr('Delete when possible'))
        self.sc_delete.setChecked(sc_mode == 'delete')
        self.sc_delete.setEnabled(if_mode)
        panel.layout().addRow('', self.sc_delete)
        # image file locking
        self.write_if = QtGui.QCheckBox(self.tr('(when possible)'))
        self.write_if.setChecked(if_mode)
        self.write_if.clicked.connect(self.new_write_if)
        panel.layout().addRow(self.tr('Write to image'), self.write_if)
        # add panel to scroll area after its size is known
        scroll_area.setWidget(panel)

    def new_write_if(self):
        if_mode = self.write_if.isChecked()
        self.sc_auto.setEnabled(if_mode)
        self.sc_delete.setEnabled(if_mode)
        if not if_mode:
            self.sc_always.setChecked(True)

    def button_clicked(self, button):
        if button != self.button_box.button(QtGui.QDialogButtonBox.Apply):
            return self.reject()
        # change config
        self.config_store.set('user', 'copyright_name', self.copyright_name.text())
        self.config_store.set('user', 'creator_name', self.creator_name.text())
        if (self.reset_flickr.isChecked() and
                            keyring.get_password('photini', 'flickr')):
            keyring.delete_password('photini', 'flickr')
        if (self.reset_picasa.isChecked() and
                            keyring.get_password('photini', 'picasa')):
            keyring.delete_password('photini', 'picasa')
        self.config_store.set(
            'files', 'force_iptc', str(self.write_iptc.isChecked()))
        if self.sc_always.isChecked():
            sc_mode = 'always'
        elif self.sc_auto.isChecked():
            sc_mode = 'auto'
        else:
            sc_mode = 'delete'
        self.config_store.set('files', 'sidecar', sc_mode)
        self.config_store.set('files', 'image', str(self.write_if.isChecked()))
        return self.accept()
