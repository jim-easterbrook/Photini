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

from datetime import (
    timedelta, datetime as pyDateTime, date as pyDate, time as pyTime)

from PyQt5 import QtGui, QtCore, QtWidgets

from .metadata import LensSpec
from .utils import multiple

class DateTimeEdit(QtWidgets.QHBoxLayout):
    new_value = QtCore.pyqtSignal(str, object)

    def __init__(self, key, is_date, parent=None):
        super(DateTimeEdit, self).__init__(parent)
        self.key = key
        self.is_date = is_date
        self.is_none = True
        self.setContentsMargins(0, 0, 0, 0)
        # main widget
        self.datetime = QtWidgets.QDateTimeEdit()
        if self.is_date:
            self.datetime.setDisplayFormat('yyyy-MM-dd')
            self.datetime.setCalendarPopup(True)
            self.datetime.setDate(pyDate.today())
        else:
            self.datetime.setDisplayFormat('hh:mm:ss.zzz')
        self.datetime.editingFinished.connect(self.editing_finished)
        self.addWidget(self.datetime)
        # clear button
        clear_button = QtWidgets.QPushButton(self.tr('clear'))
        clear_button.clicked.connect(self._clear)
        self.addWidget(clear_button)

    def _clear(self):
        self.new_value.emit(self.key, None)

    def get_value(self):
        if self.is_none:
            return None
        if self.is_date:
            return self.datetime.date().toPyDate()
        return self.datetime.time().toPyTime()

    def set_value(self, value):
        if value is None:
            self.is_none = True
            # QDateTimeEdit clear method only clears first number
            self.datetime.findChild(QtWidgets.QLineEdit).setText('')
        else:
            self.is_none = False
            if self.is_date:
                self.datetime.setDate(value)
            else:
                self.datetime.setTime(value)

    def set_multiple(self):
        self.is_none = True
        # first time setText is called sometimes doesn't show
        self.datetime.findChild(QtWidgets.QLineEdit).setText(multiple)
        self.datetime.findChild(QtWidgets.QLineEdit).setText(multiple)

    def editing_finished(self):
        self.is_none = False
        self.new_value.emit(self.key, self.get_value())

class DateAndTimeWidget(QtWidgets.QWidget):
    def __init__(self, key, parent=None):
        super(DateAndTimeWidget, self).__init__(parent)
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        # date
        self.date = DateTimeEdit(key, True)
        self.layout().addLayout(self.date)
        self.layout().addStretch(1)
        # time
        self.time = DateTimeEdit(key, False)
        self.layout().addLayout(self.time)

class OffsetWidget(QtWidgets.QWidget):
    apply_offset = QtCore.pyqtSignal(timedelta)

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addStretch(1)
        # offset value
        self.offset = QtWidgets.QTimeEdit()
        self.offset.setDisplayFormat('hh:mm:ss')
        self.layout().addWidget(self.offset)
        # add offset button
        add_button = QtWidgets.QPushButton(' + ')
        add_button.clicked.connect(self.add)
        self.layout().addWidget(add_button)
        # subtract offset button
        sub_button = QtWidgets.QPushButton(' - ')
        sub_button.clicked.connect(self.sub)
        self.layout().addWidget(sub_button)

    def add(self):
        value = self.offset.time()
        offset = timedelta(
            hours=value.hour(), minutes=value.minute(), seconds=value.second())
        self.apply_offset.emit(offset)

    def sub(self):
        value = self.offset.time()
        offset = timedelta(
            hours=value.hour(), minutes=value.minute(), seconds=value.second())
        self.apply_offset.emit(-offset)

class DoubleValidator(QtGui.QDoubleValidator):
    def validate(self, input_, pos):
        # accept empty string as valid, to allow metadata to be cleared
        if input_ == '':
            return QtGui.QValidator.Acceptable, input_, pos
        return super(DoubleValidator, self).validate(input_, pos)

class LensData(object):
    def __init__(self, config_store):
        self.config_store = config_store
        self.lenses = eval(self.config_store.get('technical', 'lenses', '[]'))
        self.lenses.sort()

    def image_save(self, model, image):
        image.metadata.lens_model = model
        section = 'lens ' + model
        for item in ('lens_make', 'lens_serial', 'lens_spec'):
            value = self.config_store.get(section, item) or None
            setattr(image.metadata, item, value)

    def image_load(self, model, image):
        section = 'lens '  + model
        for item in ('lens_make', 'lens_serial', 'lens_spec'):
            value = getattr(image.metadata, item)
            if value is not None:
                self.config_store.set(section, item, str(value))
        self.lenses.append(model)
        self.lenses.sort()
        self.config_store.set('technical', 'lenses', repr(self.lenses))

    def dialog_load(self, dialog):
        model = dialog.lens_model.text()
        if not model:
            return None
        min_fl = dialog.lens_spec['min_fl'].text()
        if not min_fl:
            return None
        max_fl = dialog.lens_spec['max_fl'].text() or min_fl
        min_fl_fn = dialog.lens_spec['min_fl_fn'].text() or '0'
        max_fl_fn = dialog.lens_spec['max_fl_fn'].text() or min_fl_fn
        lens_spec = LensSpec(min_fl, max_fl, min_fl_fn, max_fl_fn)
        section = 'lens '  + model
        self.config_store.set(section, 'lens_make', dialog.lens_make.text())
        self.config_store.set(section, 'lens_serial', dialog.lens_serial.text())
        self.config_store.set(section, 'lens_spec', str(lens_spec))
        self.lenses.append(model)
        self.lenses.sort()
        self.config_store.set('technical', 'lenses', repr(self.lenses))
        return model

    def get_spec(self, model):
        section = 'lens ' + model
        spec = self.config_store.get(section, 'lens_spec')
        if not spec:
            return None
        return LensSpec.from_string(spec)

class NewLensDialog(QtWidgets.QDialog):
    def __init__(self, parent):
        super(NewLensDialog, self).__init__(parent)
        self.setWindowTitle(self.tr('Photini: define lens'))
        self.setLayout(QtWidgets.QVBoxLayout())
        # main dialog area
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.layout().addWidget(scroll_area)
        panel = QtWidgets.QWidget()
        panel.setLayout(QtWidgets.QFormLayout())
        # ok & cancel buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout().addWidget(button_box)
        # model
        self.lens_model = QtWidgets.QLineEdit()
        panel.layout().addRow(self.tr('Model name'), self.lens_model)
        # maker
        self.lens_make = QtWidgets.QLineEdit()
        panel.layout().addRow(self.tr("Maker's name"), self.lens_make)
        # serial number
        self.lens_serial = QtWidgets.QLineEdit()
        panel.layout().addRow(self.tr('Serial number'), self.lens_serial)
        ## spec has four items
        self.lens_spec = {}
        # min focal length
        self.lens_spec['min_fl'] = QtWidgets.QLineEdit()
        self.lens_spec['min_fl'].setValidator(QtWidgets.QDoubleValidator(bottom=0.0))
        panel.layout().addRow(self.tr('Minimum focal length (mm)'),
                              self.lens_spec['min_fl'])
        # min focal length aperture
        self.lens_spec['min_fl_fn'] = QtWidgets.QLineEdit()
        self.lens_spec['min_fl_fn'].setValidator(DoubleValidator(bottom=0.0))
        panel.layout().addRow(self.tr('Aperture at min. focal length f/'),
                              self.lens_spec['min_fl_fn'])
        # max focal length
        self.lens_spec['max_fl'] = QtWidgets.QLineEdit()
        self.lens_spec['max_fl'].setValidator(QtWidgets.QDoubleValidator(bottom=0.0))
        panel.layout().addRow(self.tr('Maximum focal length (mm)'),
                              self.lens_spec['max_fl'])
        # max focal length aperture
        self.lens_spec['max_fl_fn'] = QtWidgets.QLineEdit()
        self.lens_spec['max_fl_fn'].setValidator(DoubleValidator(bottom=0.0))
        panel.layout().addRow(self.tr('Aperture at max. focal length f/'),
                              self.lens_spec['max_fl_fn'])
        # add panel to scroll area after its size is known
        scroll_area.setWidget(panel)

class Technical(QtWidgets.QWidget):
    def __init__(self, config_store, image_list, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.config_store = config_store
        self.image_list = image_list
        self.setLayout(QtWidgets.QGridLayout())
        self.date_widget = {}
        self.link_widget = {}
        self.link_master = {
            'taken'     : None,
            'digitised' : 'taken',
            'modified'  : 'digitised'
            }
        # store lens data in another object
        self.lens_data = LensData(self.config_store)
        # date and time
        date_group = QtWidgets.QGroupBox(self.tr('Date and time'))
        date_group.setLayout(QtWidgets.QFormLayout())
        # taken
        self.date_widget['taken'] = DateAndTimeWidget('taken')
        self.date_widget['taken'].date.new_value.connect(self.new_date)
        self.date_widget['taken'].time.new_value.connect(self.new_time)
        date_group.layout().addRow(self.tr('Taken'), self.date_widget['taken'])
        # link taken & digitised
        self.link_widget['digitised'] = QtWidgets.QCheckBox(
            self.tr("Link 'taken' and 'digitised'"))
        self.link_widget['digitised'].clicked.connect(self.new_link)
        date_group.layout().addRow('', self.link_widget['digitised'])
        # digitised
        self.date_widget['digitised'] = DateAndTimeWidget('digitised')
        self.date_widget['digitised'].date.new_value.connect(self.new_date)
        self.date_widget['digitised'].time.new_value.connect(self.new_time)
        date_group.layout().addRow(
            self.tr('Digitised'), self.date_widget['digitised'])
        # link digitised & modified
        self.link_widget['modified'] = QtWidgets.QCheckBox(
            self.tr("Link 'digitised' and 'modified'"))
        self.link_widget['modified'].clicked.connect(self.new_link)
        date_group.layout().addRow('', self.link_widget['modified'])
        # modified
        self.date_widget['modified'] = DateAndTimeWidget('modified')
        self.date_widget['modified'].date.new_value.connect(self.new_date)
        self.date_widget['modified'].time.new_value.connect(self.new_time)
        date_group.layout().addRow(
            self.tr('Modified'), self.date_widget['modified'])
        # offset
        self.offset_widget = OffsetWidget()
        self.offset_widget.apply_offset.connect(self.apply_offset)
        date_group.layout().addRow(self.tr('Adjust times'), self.offset_widget)
        self.layout().addWidget(date_group, 0, 0)
        # other
        other_group = QtWidgets.QGroupBox(self.tr('Other'))
        other_group.setLayout(QtWidgets.QFormLayout())
        # orientation
        self.orientation = QtWidgets.QComboBox()
        self.orientation.addItem(self.tr('normal'), 1)
        self.orientation.addItem(self.tr('rotate -90'), 6)
        self.orientation.addItem(self.tr('rotate +90'), 8)
        self.orientation.addItem(self.tr('rotate 180'), 3)
        self.orientation.addItem(self.tr('reflect left-right'), 2)
        self.orientation.addItem(self.tr('reflect top-bottom'), 4)
        self.orientation.addItem(self.tr('reflect tr-bl'), 5)
        self.orientation.addItem(self.tr('reflect tl-br'), 7)
        self.orientation.addItem('', 0)
        self.orientation.addItem(multiple, -1)
        self.orientation.currentIndexChanged.connect(self.new_orientation)
        other_group.layout().addRow(self.tr('Orientation'), self.orientation)
        # lens model
        self.lens_model = QtWidgets.QComboBox()
        for model in self.lens_data.lenses:
            self.lens_model.addItem(model)
        self.lens_model.addItem('', 0)
        self.lens_model.addItem(self.tr('<add lens>'), -2)
        self.lens_model.addItem(multiple, -1)
        self.lens_model.currentIndexChanged.connect(self.new_lens_model)
        other_group.layout().addRow(self.tr('Lens model'), self.lens_model)
        # link lens to aperture & focal length
        self.link_lens = QtWidgets.QCheckBox(
            self.tr("Link lens model to\nfocal length && aperture"))
        self.link_lens.setChecked(True)
        other_group.layout().addRow('', self.link_lens)
        # focal length
        self.focal_length = QtWidgets.QLineEdit()
        self.focal_length.setValidator(DoubleValidator(bottom=0.1))
        self.focal_length.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.focal_length.editingFinished.connect(self.new_focal_length)
        other_group.layout().addRow(
            self.tr('Focal length (mm)'), self.focal_length)
        # aperture
        self.aperture = QtWidgets.QLineEdit()
        self.aperture.setValidator(DoubleValidator(bottom=0.1))
        self.aperture.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.aperture.editingFinished.connect(self.new_aperture)
        other_group.layout().addRow(self.tr('Aperture f/'), self.aperture)
        self.layout().addWidget(other_group, 0, 1)
        self.layout().setColumnStretch(0, 1)
        self.layout().setColumnStretch(1, 1)
        # disable until an image is selected
        self.setEnabled(False)

    def refresh(self):
        pass

    def do_not_close(self):
        return False

    @QtCore.pyqtSlot(str, object)
    def new_date(self, key, value):
        self._new_date_value(key, value)
        for slave in self.link_widget:
            if self.link_master[slave] == key:
                if self.link_widget[slave].isChecked():
                    self.new_date(slave, value)
                break

    @QtCore.pyqtSlot(str, object)
    def new_time(self, key, value):
        self._new_time_value(key, value)
        for slave in self.link_widget:
            if self.link_master[slave] == key:
                if self.link_widget[slave].isChecked():
                    self.new_time(slave, value)
                break

    def apply_offset(self, offset):
        for image in self.image_list.get_selected_images():
            for key in self.date_widget:
                value = getattr(image.metadata, 'date_' + key)
                if value is None:
                    continue
                value = value.datetime() + offset
                setattr(
                    image.metadata, 'date_' + key, (value.date(), value.time()))
        for key in self.date_widget:
            self._update_datetime(key)

    def new_link(self):
        for key in self.link_widget:
            master = self.link_master[key]
            if self.link_widget[key].isChecked():
                self._new_date_value(
                    key, self.date_widget[master].date.get_value())
                self._new_time_value(
                    key, self.date_widget[master].time.get_value())
                self.date_widget[key].setEnabled(False)
            else:
                self.date_widget[key].setEnabled(True)

    @QtCore.pyqtSlot(int)
    def new_orientation(self, index):
        value = self.orientation.itemData(index)
        if value == -1:
            self._update_orientation()
            return
        if value == 0:
            value = None
        for image in self.image_list.get_selected_images():
            image.metadata.orientation = value
            image.pixmap = None
            image.load_thumbnail()

    @QtCore.pyqtSlot(int)
    def new_lens_model(self, index):
        value = self.lens_model.itemData(index)
        if value == -1:
            self._update_lens_model()
            return
        if value == -2:
            self._add_lens_model()
            self._update_lens_model()
            return
        model = self.lens_model.itemText(index)
        for image in self.image_list.get_selected_images():
            self.lens_data.image_save(model, image)
        spec = self.lens_data.get_spec(model)
        if spec and self.link_lens.isChecked():
            for image in self.image_list.get_selected_images():
                aperture = image.metadata.aperture
                focal_length = image.metadata.focal_length
                focal_length = min(max(focal_length, spec.min_fl), spec.max_fl)
                if focal_length <= spec.min_fl:
                    aperture = max(aperture, spec.min_fl_fn)
                elif focal_length >= spec.max_fl:
                    aperture = max(aperture, spec.max_fl_fn)
                else:
                    aperture = max(aperture, spec.min_fl_fn, spec.max_fl_fn)
                image.metadata.aperture = aperture
                image.metadata.focal_length = focal_length
            self._update_aperture()
            self._update_focal_length()

    def _add_lens_model(self):
        dialog = NewLensDialog(self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        model = self.lens_data.dialog_load(dialog)
        if not model:
            return
        blocked = self.lens_model.blockSignals(True)
        self.lens_model.insertItem(0, model)
        self.lens_model.blockSignals(blocked)

    def new_aperture(self):
        value = self.aperture.text()
        if value != multiple:
            for image in self.image_list.get_selected_images():
                image.metadata.aperture = value

    def new_focal_length(self):
        value = self.focal_length.text()
        if value != multiple:
            for image in self.image_list.get_selected_images():
                image.metadata.focal_length = value

    def _new_date_value(self, key, value):
        if value is None:
            # clear date and time
            for image in self.image_list.get_selected_images():
                setattr(image.metadata, 'date_' + key, None)
        else:
            # update dates, leaving times unchanged
            for image in self.image_list.get_selected_images():
                current = getattr(image.metadata, 'date_' + key)
                if current is not None:
                    current = current.time
                setattr(image.metadata, 'date_' + key, (value, current))
        self._update_datetime(key)

    def _new_time_value(self, key, value):
        # update time, leaving dates unchanged
        for image in self.image_list.get_selected_images():
            current = getattr(image.metadata, 'date_' + key)
            if current is not None:
                current = current.date
            setattr(image.metadata, 'date_' + key, (current, value))
        self._update_datetime(key)

    def _update_datetime(self, key):
        images = self.image_list.get_selected_images()
        value = getattr(images[0].metadata, 'date_' + key)
        if value is None:
            date = None
            time = None
        else:
            date = value.date
            time = value.time
        for image in images[1:]:
            new_value = getattr(image.metadata, 'date_' + key)
            if new_value is not None:
                new_value = new_value.date
            if new_value != date:
                self.date_widget[key].date.set_multiple()
                break
        else:
            self.date_widget[key].date.set_value(date)
        for image in images[1:]:
            new_value = getattr(image.metadata, 'date_' + key)
            if new_value is not None:
                new_value = new_value.time
            if new_value != time:
                self.date_widget[key].time.set_multiple()
                break
        else:
            self.date_widget[key].time.set_value(time)

    def _update_orientation(self):
        images = self.image_list.get_selected_images()
        value = images[0].metadata.orientation
        for image in images[1:]:
            if image.metadata.orientation != value:
                # multiple values
                self.orientation.setCurrentIndex(self.orientation.findData(-1))
                return
        if value is None:
            value = 0
        self.orientation.setCurrentIndex(self.orientation.findData(int(value)))

    def _update_lens_model(self):
        images = self.image_list.get_selected_images()
        value = images[0].metadata.lens_model
        for image in images[1:]:
            if image.metadata.lens_model != value:
                # multiple values
                self.lens_model.setCurrentIndex(self.lens_model.findData(-1))
                return
        if value is None:
            value = ''
        index = self.lens_model.findText(value)
        if index >= 0:
            self.lens_model.setCurrentIndex(index)
            return
        # lens not seen before, so add to list
        self.lens_data.image_load(value, images[0])
        blocked = self.lens_model.blockSignals(True)
        self.lens_model.insertItem(0, value)
        self.lens_model.setCurrentIndex(0)
        self.lens_model.blockSignals(blocked)

    def _update_aperture(self):
        images = self.image_list.get_selected_images()
        value = images[0].metadata.aperture
        for image in images[1:]:
            if image.metadata.aperture != value:
                self.aperture.setText(multiple)
                return
        if value is None:
            self.aperture.clear()
        else:
            self.aperture.setText('{:g}'.format(float(value)))

    def _update_focal_length(self):
        images = self.image_list.get_selected_images()
        value = images[0].metadata.focal_length
        for image in images[1:]:
            if image.metadata.focal_length != value:
                self.focal_length.setText(multiple)
                return
        if value is None:
            self.focal_length.clear()
        else:
            self.focal_length.setText('{:g}'.format(float(value)))

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        if not selection:
            for key in self.date_widget:
                self.date_widget[key].date.set_value(None)
                self.date_widget[key].time.set_value(None)
            self.orientation.setCurrentIndex(self.orientation.findData(0))
            self.lens_model.setCurrentIndex(self.lens_model.findData(0))
            self.aperture.clear()
            self.focal_length.clear()
            self.setEnabled(False)
            return
        for key in self.date_widget:
            self._update_datetime(key)
        for key in self.link_widget:
            master = self.link_master[key]
            if (self.date_widget[key].date.get_value() ==
                                self.date_widget[master].date.get_value() and
                    self.date_widget[key].time.get_value() ==
                                self.date_widget[master].time.get_value()):
                self.date_widget[key].setEnabled(False)
                self.link_widget[key].setChecked(True)
            else:
                self.link_widget[key].setChecked(False)
                self.date_widget[key].setEnabled(True)
        self._update_orientation()
        self._update_lens_model()
        self._update_aperture()
        self._update_focal_length()
        self.setEnabled(True)
