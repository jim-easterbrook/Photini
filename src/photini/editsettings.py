# -*- coding: utf-8 -*-
#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2012-20  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import logging

from photini.pyqt import (
    catch_all, Qt, QtSlot, QtWidgets, SingleLineEdit, width_for_text)

logger = logging.getLogger(__name__)


class EditSettings(QtWidgets.QDialog):
    def __init__(self, *arg, **kw):
        super(EditSettings, self).__init__(*arg, **kw)
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.setWindowTitle(self.tr('Photini: settings'))
        self.setLayout(QtWidgets.QVBoxLayout())
        # main dialog area
        scroll_area = QtWidgets.QScrollArea()
        self.layout().addWidget(scroll_area)
        panel = QtWidgets.QWidget()
        panel.setLayout(QtWidgets.QFormLayout())
        panel.layout().setRowWrapPolicy(max(QtWidgets.QFormLayout.WrapLongRows,
                                            panel.layout().rowWrapPolicy()))
        # apply & cancel buttons
        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Apply | QtWidgets.QDialogButtonBox.Cancel)
        self.button_box.clicked.connect(self.button_clicked)
        self.layout().addWidget(self.button_box)
        # copyright holder name
        self.copyright_name = SingleLineEdit(spell_check=True)
        self.copyright_name.set_value(
            self.config_store.get('user', 'copyright_name', ''))
        panel.layout().addRow(self.tr('Copyright holder name'), self.copyright_name)
        # copyright text
        self.copyright_text = SingleLineEdit(spell_check=True)
        self.copyright_text.set_value(
            self.config_store.get('user', 'copyright_text', ''))
        self.copyright_text.setMinimumWidth(
            width_for_text(self.copyright_text, 'x' * 50))
        panel.layout().addRow(self.tr('Copyright text'), self.copyright_text)
        # creator name
        self.creator_name = SingleLineEdit(spell_check=True)
        self.creator_name.set_value(
            self.config_store.get('user', 'creator_name', ''))
        panel.layout().addRow(self.tr('Creator name'), self.creator_name)
        # IPTC data
        force_iptc = eval(self.config_store.get('files', 'force_iptc', 'False'))
        self.write_iptc = QtWidgets.QCheckBox(self.tr('Always write'))
        self.write_iptc.setChecked(force_iptc)
        panel.layout().addRow(self.tr('IPTC metadata'), self.write_iptc)
        # sidecar files
        if_mode = eval(self.config_store.get('files', 'image', 'True'))
        sc_mode = self.config_store.get('files', 'sidecar', 'auto')
        if not if_mode:
            sc_mode = 'always'
        self.sc_always = QtWidgets.QRadioButton(self.tr('Always create'))
        self.sc_always.setChecked(sc_mode == 'always')
        panel.layout().addRow(self.tr('Sidecar files'), self.sc_always)
        self.sc_auto = QtWidgets.QRadioButton(self.tr('Create if necessary'))
        self.sc_auto.setChecked(sc_mode == 'auto')
        self.sc_auto.setEnabled(if_mode)
        panel.layout().addRow('', self.sc_auto)
        self.sc_delete = QtWidgets.QRadioButton(self.tr('Delete when possible'))
        self.sc_delete.setChecked(sc_mode == 'delete')
        self.sc_delete.setEnabled(if_mode)
        panel.layout().addRow('', self.sc_delete)
        # image file locking
        self.write_if = QtWidgets.QCheckBox(self.tr('(when possible)'))
        self.write_if.setChecked(if_mode)
        self.write_if.clicked.connect(self.new_write_if)
        panel.layout().addRow(self.tr('Write to image file'), self.write_if)
        # preserve file timestamps
        keep_time = eval(
            self.config_store.get('files', 'preserve_timestamps', 'False'))
        self.keep_time = QtWidgets.QCheckBox()
        self.keep_time.setChecked(keep_time)
        panel.layout().addRow(
            self.tr('Preserve file timestamps'), self.keep_time)
        # add panel to scroll area after its size is known
        scroll_area.setWidget(panel)

    @QtSlot()
    @catch_all
    def new_write_if(self):
        if_mode = self.write_if.isChecked()
        self.sc_auto.setEnabled(if_mode)
        self.sc_delete.setEnabled(if_mode)
        if not if_mode:
            self.sc_always.setChecked(True)

    @QtSlot(QtWidgets.QAbstractButton)
    @catch_all
    def button_clicked(self, button):
        if button != self.button_box.button(QtWidgets.QDialogButtonBox.Apply):
            return self.reject()
        # change config
        self.config_store.set(
            'user', 'copyright_name', self.copyright_name.get_value())
        self.config_store.set(
            'user', 'copyright_text', self.copyright_text.get_value())
        self.config_store.set(
            'user', 'creator_name', self.creator_name.get_value())
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
        self.config_store.set(
            'files', 'preserve_timestamps', str(self.keep_time.isChecked()))
        return self.accept()
