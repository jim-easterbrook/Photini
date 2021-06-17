##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2021  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from collections import defaultdict
from datetime import datetime
import logging

from photini.exiv2 import ImageMetadata
from photini.pyqt import (
    catch_all, ComboBox, multiple_values, MultiLineEdit, Qt, QtCore, QtGui,
    QtSlot, QtWidgets, SingleLineEdit, Slider, width_for_text)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class TabWidget(QtWidgets.QWidget):
    @staticmethod
    def tab_name():
        return translate('OwnerTab', '&Ownership metadata')

    def __init__(self, image_list, *arg, **kw):
        super(TabWidget, self).__init__(*arg, **kw)
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.image_list = image_list
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        # construct widgets
        self.enableable = []
        ## data fields
        form = QtWidgets.QWidget()
        self.enableable.append(form)
        layout, self.widgets = self.data_form()
        form.setLayout(layout)
        for key in self.widgets:
            self.widgets[key].editingFinished.connect(
                getattr(self, 'new_' + key))
        self.layout().addWidget(form)
        ## buttons
        buttons = QtWidgets.QVBoxLayout()
        buttons.addStretch(1)
        edit_template = QtWidgets.QPushButton(
            translate('OwnerTab', 'Edit\ntemplate'))
        edit_template.clicked.connect(self.edit_template)
        buttons.addWidget(edit_template)
        apply_template = QtWidgets.QPushButton(
            translate('OwnerTab', 'Apply\ntemplate'))
        apply_template.clicked.connect(self.apply_template)
        self.enableable.append(apply_template)
        buttons.addWidget(apply_template)
        self.layout().addLayout(buttons)
        # disable data entry until an image is selected
        self.set_enabled(False)

    def data_form(self):
        widgets = {}
        form = QtWidgets.QFormLayout()
        # creator
        widgets['creator'] = SingleLineEdit(
            length_check=ImageMetadata.max_bytes('creator'), multi_string=True)
        widgets['creator'].setToolTip(translate(
            'OwnerTab', "Photographer's name."))
        form.addRow(translate(
            'OwnerTab', 'Creator / Artist'), widgets['creator'])
        # copyright
        widgets['copyright'] = SingleLineEdit(
            length_check=ImageMetadata.max_bytes('copyright'))
        widgets['copyright'].setToolTip(translate(
            'OwnerTab',
            'Full copyright message, can even include contact details.'))
        form.addRow(translate('OwnerTab', 'Copyright'), widgets['copyright'])
        # usage terms
        widgets['usageterms'] = SingleLineEdit(
            length_check=ImageMetadata.max_bytes('usageterms'))
        widgets['usageterms'].setToolTip(translate(
            'OwnerTab', 'Brief description of licence or other conditions.'))
        form.addRow(translate(
            'OwnerTab', 'Rights Usage Terms'), widgets['usageterms'])
        return form, widgets

    def set_enabled(self, enabled):
        for widget in self.enableable:
            widget.setEnabled(enabled)

    def refresh(self):
        self.new_selection(self.image_list.get_selected_images())

    def do_not_close(self):
        return False

    @QtSlot()
    @catch_all
    def image_list_changed(self):
        pass

    @QtSlot()
    @catch_all
    def new_copyright(self):
        self._new_value('copyright')

    @QtSlot()
    @catch_all
    def new_usageterms(self):
        self._new_value('usageterms')

    @QtSlot()
    @catch_all
    def new_creator(self):
        self._new_value('creator')

    def _new_value(self, key):
        images = self.image_list.get_selected_images()
        if not self.widgets[key].is_multiple():
            value = self.widgets[key].get_value()
            for image in images:
                setattr(image.metadata, key, value)
        self._update_widget(key, images)

    def _update_widget(self, key, images):
        if not images:
            return
        values = []
        for image in images:
            value = getattr(image.metadata, key)
            if value not in values:
                values.append(value)
        if len(values) > 1:
            self.widgets[key].set_multiple(choices=filter(None, values))
        else:
            self.widgets[key].set_value(values[0])

    @QtSlot()
    @catch_all
    def edit_template(self):
        dialog = QtWidgets.QDialog(parent=self)
        dialog.setFixedSize(min(800, self.window().width()),
                            min(400, self.window().height()))
        dialog.setWindowTitle(self.tr('Photini: ownership template'))
        dialog.setLayout(QtWidgets.QVBoxLayout())
        # main dialog area
        form, widgets = self.data_form()
        widgets['copyright'].setToolTip(
            widgets['copyright'].toolTip() + ' ' +
            translate('OwnerTab',
                      'Use %Y to insert the year the photograph was taken.'))
        for key in widgets:
            if key == 'copyright':
                name = self.config_store.get('user', 'copyright_name', '')
                text = self.config_store.get('user', 'copyright_text', '')
                value = text.format(year='%Y', name=name)
            elif key == 'creator':
                value = self.config_store.get('user', 'creator_name', '')
            else:
                value = ''
            widgets[key].set_value(
                self.config_store.get('ownership', key, value))
        dialog.layout().addLayout(form)
        # apply & cancel buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addWidget(button_box)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        for key in widgets:
            self.config_store.set('ownership', key, widgets[key].get_value())

    @QtSlot()
    @catch_all
    def apply_template(self):
        value = {}
        for key in self.widgets:
            text = self.config_store.get('ownership', key)
            if text:
                value[key] = text
        images = self.image_list.get_selected_images()
        for image in images:
            date_taken = image.metadata.date_taken
            if date_taken is None:
                date_taken = datetime.now()
            else:
                date_taken = date_taken['datetime']
            for key in value:
                setattr(image.metadata, key, date_taken.strftime(value[key]))
        for key in value:
            self._update_widget(key, images)

    @QtSlot(list)
    @catch_all
    def new_selection(self, selection):
        if not selection:
            for key in self.widgets:
                self.widgets[key].set_value(None)
            self.set_enabled(False)
            return
        for key in self.widgets:
            self._update_widget(key, selection)
        self.set_enabled(True)
