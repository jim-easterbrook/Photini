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
from fractions import Fraction

from PyQt4 import QtGui, QtCore

class DateEdit(QtGui.QDateEdit):
    def focusInEvent(self, event):
        if self.date() == self.minimumDate():
            self.setDate(QtCore.QDate.currentDate())
        return QtGui.QDateEdit.focusInEvent(self, event)

class TimeEdit(QtGui.QTimeEdit):
    def focusInEvent(self, event):
        if self.time() == self.minimumTime():
            self.setSpecialValueText('')
        return QtGui.QTimeEdit.focusInEvent(self, event)

class DateAndTimeWidget(QtGui.QWidget):
    def __init__(self, key, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.key = key
        layout = QtGui.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # date
        self.date = DateEdit()
        self.date.setDisplayFormat('yyyy-MM-dd')
        self.date.setCalendarPopup(True)
        self.date.setSpecialValueText(' ')
        self.date.editingFinished.connect(self._new_date)
        layout.addWidget(self.date)
        # time
        self.time = TimeEdit()
        self.time.setDisplayFormat('hh:mm:ss')
        self.time.setSpecialValueText(' ')
        self.time.editingFinished.connect(self._new_time)
        layout.addWidget(self.time)
        # clear button
        clear_button = QtGui.QPushButton(self.tr('clear'))
        clear_button.clicked.connect(self._clear)
        layout.addWidget(clear_button)

    date_changed = QtCore.pyqtSignal(str, QtCore.QDate)
    def _new_date(self):
        date = self.date.date()
        self.date_changed.emit(self.key, date)

    time_changed = QtCore.pyqtSignal(str, QtCore.QTime)
    def _new_time(self):
        time = self.time.time()
        self.time_changed.emit(self.key, time)

    def _clear(self):
        self.clearDate()
        self.clearTime()
        self.time_changed.emit(self.key, self.time.minimumTime())
        self.date_changed.emit(self.key, self.date.minimumDate())

    def clearDate(self):
        self.date.setSpecialValueText(' ')
        self.date.setDate(self.date.minimumDate())

    def clearTime(self):
        self.time.setSpecialValueText(' ')
        self.time.setTime(self.time.minimumTime())

    def setMultipleDate(self):
        self.date.setSpecialValueText(self.tr('<multiple>'))
        self.date.setDate(self.date.minimumDate())

    def setMultipleTime(self):
        self.time.setSpecialValueText(self.tr('<multi>'))
        self.time.setTime(self.time.minimumTime())

    def setDate(self, value):
        self.date.setDate(value)

    def setTime(self, value):
        self.time.setTime(value)
        self.time.setSpecialValueText('')

class OffsetWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        layout = QtGui.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # hours
        self.hours = QtGui.QSpinBox()
        self.hours.setRange(-12, 12)
        self.hours.setSuffix(self.tr(' hours'))
        layout.addWidget(self.hours)
        # minutes
        self.minutes = QtGui.QSpinBox()
        self.minutes.setRange(-60, 60)
        self.minutes.setSuffix(self.tr(' minutes'))
        layout.addWidget(self.minutes)
        # apply button
        apply_button = QtGui.QPushButton(self.tr('apply'))
        apply_button.clicked.connect(self._apply)
        layout.addWidget(apply_button)

    apply_offset = QtCore.pyqtSignal(timedelta)
    def _apply(self):
        offset = timedelta(hours=self.hours.value(),
                           minutes=self.minutes.value())
        self.apply_offset.emit(offset)

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
        image.metadata.set_item('lens_model', model)
        section = 'lens ' + model
        for item in ('lens_make', 'lens_serial', 'lens_spec'):
            value = self.config_store.get(section, item) or ''
            image.metadata.set_item(item, value)

    def image_load(self, model, image):
        section = 'lens '  + model
        for item in ('lens_make', 'lens_serial', 'lens_spec'):
            self.config_store.set(
                section, item, getattr(image.metadata, item).as_str())
        self.lenses.append(model)
        self.lenses.sort()
        self.config_store.set('technical', 'lenses', repr(self.lenses))

    def dialog_load(self, dialog):
        model = dialog.lens_model.text()
        section = 'lens '  + model
        self.config_store.set(section, 'lens_make', dialog.lens_make.text())
        self.config_store.set(section, 'lens_serial', dialog.lens_serial.text())
        self.config_store.set(section, 'lens_make', dialog.lens_make.text())
        lens_spec = {}
        for key in ('min_fl', 'max_fl', 'min_fl_fn', 'max_fl_fn'):
            lens_spec[key] = Fraction(dialog.lens_spec[key].text())
        self.config_store.set(section, 'lens_spec', repr(lens_spec))
        self.lenses.append(model)
        self.lenses.sort()
        self.config_store.set('technical', 'lenses', repr(self.lenses))
        return model

    def get_spec(self, model, key):
        section = 'lens ' + model
        spec = self.config_store.get(section, 'lens_spec')
        if not spec:
            return None
        return eval(spec)[key]

class NewLensDialog(QtGui.QDialog):
    def __init__(self, parent):
        super(NewLensDialog, self).__init__(parent)
        self.setWindowTitle(self.tr('Photini: define lens'))
        self.setLayout(QtGui.QGridLayout())
        self.layout().setRowStretch(0, 1)
        self.layout().setColumnStretch(0, 1)
        # main dialog area
        scroll_area = QtGui.QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.layout().addWidget(scroll_area, 0, 0, 1, 3)
        panel = QtGui.QWidget()
        panel.setLayout(QtGui.QFormLayout())
        # ok button
        ok_button = QtGui.QPushButton(self.tr('OK'))
        ok_button.clicked.connect(self.accept)
        self.layout().addWidget(ok_button, 1, 2)
        # cancel button
        cancel_button = QtGui.QPushButton(self.tr('Cancel'))
        cancel_button.clicked.connect(self.reject)
        self.layout().addWidget(cancel_button, 1, 1)
        # model
        self.lens_model = QtGui.QLineEdit()
        panel.layout().addRow(self.tr('Model name'), self.lens_model)
        # maker
        self.lens_make = QtGui.QLineEdit()
        panel.layout().addRow(self.tr("Maker's name"), self.lens_make)
        # serial number
        self.lens_serial = QtGui.QLineEdit()
        panel.layout().addRow(self.tr('Serial number'), self.lens_serial)
        ## spec has four items
        self.lens_spec = {}
        # min focal length
        self.lens_spec['min_fl'] = QtGui.QLineEdit()
        self.lens_spec['min_fl'].setValidator(QtGui.QDoubleValidator(bottom=0.0))
        panel.layout().addRow(self.tr('Minimum focal length (mm)'),
                              self.lens_spec['min_fl'])
        # min focal length aperture
        self.lens_spec['min_fl_fn'] = QtGui.QLineEdit()
        self.lens_spec['min_fl_fn'].setValidator(DoubleValidator(bottom=0.0))
        panel.layout().addRow(self.tr('Aperture at min. focal length f/'),
                              self.lens_spec['min_fl_fn'])
        # max focal length
        self.lens_spec['max_fl'] = QtGui.QLineEdit()
        self.lens_spec['max_fl'].setValidator(QtGui.QDoubleValidator(bottom=0.0))
        panel.layout().addRow(self.tr('Maximum focal length (mm)'),
                              self.lens_spec['max_fl'])
        # max focal length aperture
        self.lens_spec['max_fl_fn'] = QtGui.QLineEdit()
        self.lens_spec['max_fl_fn'].setValidator(DoubleValidator(bottom=0.0))
        panel.layout().addRow(self.tr('Aperture at max. focal length f/'),
                              self.lens_spec['max_fl_fn'])
        # add panel to scroll area after its size is known
        scroll_area.setWidget(panel)

class Technical(QtGui.QWidget):
    def __init__(self, config_store, image_list, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.config_store = config_store
        self.image_list = image_list
        self.setLayout(QtGui.QGridLayout())
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
        date_group = QtGui.QGroupBox(self.tr('Date and time'))
        date_group.setLayout(QtGui.QFormLayout())
        # taken
        self.date_widget['taken'] = DateAndTimeWidget('taken')
        self.date_widget['taken'].date_changed.connect(self.new_datetime)
        self.date_widget['taken'].time_changed.connect(self.new_datetime)
        date_group.layout().addRow(self.tr('Taken'), self.date_widget['taken'])
        # link taken & digitised
        self.link_widget['digitised'] = QtGui.QCheckBox(
            self.tr("Link 'taken' and 'digitised'"))
        self.link_widget['digitised'].clicked.connect(self.new_link)
        date_group.layout().addRow('', self.link_widget['digitised'])
        # digitised
        self.date_widget['digitised'] = DateAndTimeWidget('digitised')
        self.date_widget['digitised'].date_changed.connect(self.new_datetime)
        self.date_widget['digitised'].time_changed.connect(self.new_datetime)
        date_group.layout().addRow(
            self.tr('Digitised'), self.date_widget['digitised'])
        # link digitised & modified
        self.link_widget['modified'] = QtGui.QCheckBox(
            self.tr("Link 'digitised' and 'modified'"))
        self.link_widget['modified'].clicked.connect(self.new_link)
        date_group.layout().addRow('', self.link_widget['modified'])
        # modified
        self.date_widget['modified'] = DateAndTimeWidget('modified')
        self.date_widget['modified'].date_changed.connect(self.new_datetime)
        self.date_widget['modified'].time_changed.connect(self.new_datetime)
        date_group.layout().addRow(
            self.tr('Modified'), self.date_widget['modified'])
        # offset
        self.offset_widget = OffsetWidget()
        self.offset_widget.apply_offset.connect(self.apply_offset)
        date_group.layout().addRow(self.tr('Offset'), self.offset_widget)
        self.layout().addWidget(date_group, 0, 0)
        # other
        other_group = QtGui.QGroupBox(self.tr('Other'))
        other_group.setLayout(QtGui.QFormLayout())
        # orientation
        self.orientation = QtGui.QComboBox()
        self.orientation.addItem(self.tr('normal'), 1)
        self.orientation.addItem(self.tr('rotate -90'), 6)
        self.orientation.addItem(self.tr('rotate +90'), 8)
        self.orientation.addItem(self.tr('rotate 180'), 3)
        self.orientation.addItem(self.tr('reflect left-right'), 2)
        self.orientation.addItem(self.tr('reflect top-bottom'), 4)
        self.orientation.addItem(self.tr('reflect tr-bl'), 5)
        self.orientation.addItem(self.tr('reflect tl-br'), 7)
        self.orientation.addItem(self.tr('<multiple>'), -1)
        self.orientation.currentIndexChanged.connect(self.new_orientation)
        other_group.layout().addRow(self.tr('Orientation'), self.orientation)
        # lens model
        self.lens_model = QtGui.QComboBox()
        for model in self.lens_data.lenses:
            self.lens_model.addItem(model)
        self.lens_model.addItem('', 0)
        self.lens_model.addItem(self.tr('<add lens>'), -2)
        self.lens_model.addItem(self.tr('<multiple>'), -1)
        self.lens_model.currentIndexChanged.connect(self.new_lens_model)
        other_group.layout().addRow(self.tr('Lens model'), self.lens_model)
        # link lens to aperture & focal length
        self.link_lens = QtGui.QCheckBox(
            self.tr("Link lens to aperture and focal length"))
        other_group.layout().addRow('', self.link_lens)
        # aperture
        self.aperture = QtGui.QLineEdit()
        self.aperture.setValidator(DoubleValidator(bottom=0.1))
        self.aperture.setSizePolicy(
            QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Fixed)
        self.aperture.editingFinished.connect(self.new_aperture)
        other_group.layout().addRow(self.tr('Aperture f/'), self.aperture)
        # focal length
        self.focal_length = QtGui.QLineEdit()
        self.focal_length.setValidator(DoubleValidator(bottom=0.1))
        self.focal_length.setSizePolicy(
            QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Fixed)
        self.focal_length.editingFinished.connect(self.new_focal_length)
        other_group.layout().addRow(
            self.tr('Focal length (mm)'), self.focal_length)
        self.layout().addWidget(other_group, 0, 1)
        self.layout().setColumnStretch(0, 1)
        self.layout().setColumnStretch(1, 1)
        # disable until an image is selected
        self.setEnabled(False)

    def refresh(self):
        pass

    def do_not_close(self):
        return False

    def new_datetime(self, key, value):
        key = str(key)
        self._new_datetime_value(key, value)
        for slave in self.link_widget:
            if self.link_master[slave] == key:
                if self.link_widget[slave].isChecked():
                    self.new_datetime(slave, value)
                break

    def apply_offset(self, offset):
        for image in self.image_list.get_selected_images():
            for key in self.date_widget:
                value = getattr(image.metadata, 'date_' + key)
                if not value:
                    continue
                image.metadata.set_item('date_' + key, value.value + offset)
        for key in self.date_widget:
            self._update_datetime(key)

    def new_link(self):
        for key in self.link_widget:
            master = self.link_master[key]
            if self.link_widget[key].isChecked():
                value = self.date_widget[master].date.date()
                self._new_datetime_value(
                    key, self.date_widget[master].time.time())
                self._new_datetime_value(key, value)
                self.date_widget[key].setEnabled(False)
            else:
                self.date_widget[key].setEnabled(True)

    @QtCore.pyqtSlot(int)
    def new_orientation(self, index):
        value = self.orientation.itemData(index)
        if value < 1:
            self._update_orientation()
            return
        for image in self.image_list.get_selected_images():
            image.metadata.set_item('orientation', value)
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
            if model and self.link_lens.isChecked():
                aperture = image.metadata.aperture.value or 0.0
                focal_length = image.metadata.focal_length.value or 0.0
                if focal_length < self.lens_data.get_spec(model, 'min_fl'):
                    focal_length = self.lens_data.get_spec(model, 'min_fl')
                    aperture = max(aperture,
                                   self.lens_data.get_spec(model, 'min_fl_fn'))
                elif focal_length > self.lens_data.get_spec(model, 'max_fl'):
                    focal_length = self.lens_data.get_spec(model, 'max_fl')
                    aperture = max(aperture,
                                   self.lens_data.get_spec(model, 'max_fl_fn'))
                else:
                    aperture = max(aperture,
                                   self.lens_data.get_spec(model, 'min_fl_fn'),
                                   self.lens_data.get_spec(model, 'max_fl_fn'))
                image.metadata.set_item('aperture', aperture)
                image.metadata.set_item('focal_length', focal_length)
        if model and self.link_lens.isChecked():
            self._update_aperture()
            self._update_focal_length()

    def _add_lens_model(self):
        dialog = NewLensDialog(self)
        if dialog.exec_() == QtGui.QDialog.Accepted:
            model = self.lens_data.dialog_load(dialog)
            blocked = self.lens_model.blockSignals(True)
            self.lens_model.insertItem(0, model)
            self.lens_model.blockSignals(blocked)

    def new_aperture(self):
        value = self.aperture.text()
        if value != self.tr('<multiple values>'):
            for image in self.image_list.get_selected_images():
                image.metadata.set_item('aperture', value)

    def new_focal_length(self):
        value = self.focal_length.text()
        if value != self.tr('<multiple values>'):
            for image in self.image_list.get_selected_images():
                image.metadata.set_item('focal_length', value)

    def _new_datetime_value(self, key, value):
        if isinstance(value, QtCore.QTime):
            # update times, leaving date unchanged
            for image in self.image_list.get_selected_images():
                current = getattr(image.metadata, 'date_' + key)
                if current:
                    current = current.value
                else:
                    current = pyDateTime.today()
                image.metadata.set_item(
                    'date_' + key,
                    pyDateTime.combine(current.date(), value.toPyTime()))
        elif value == self.date_widget[key].date.minimumDate():
            # clear date & time
            for image in self.image_list.get_selected_images():
                image.metadata.del_item('date_' + key)
        else:
            # update dates, leaving times unchanged
            for image in self.image_list.get_selected_images():
                current = getattr(image.metadata, 'date_' + key)
                if current:
                    current = current.value
                else:
                    current = pyDateTime.min
                image.metadata.set_item(
                    'date_' + key,
                    pyDateTime.combine(value.toPyDate(), current.time()))
        self._update_datetime(key)

    def _update_datetime(self, key):
        dates = []
        times = []
        for image in self.image_list.get_selected_images():
            value = getattr(image.metadata, 'date_' + key)
            if value:
                dates.append(value.value.date())
                times.append(value.value.time())
            else:
                dates.append(None)
                times.append(None)
        value = dates[0]
        for new_value in dates[1:]:
            if new_value != value:
                self.date_widget[key].setMultipleDate()
                break
        else:
            if value is None:
                self.date_widget[key].clearDate()
            else:
                self.date_widget[key].setDate(value)
        value = times[0]
        for new_value in times[1:]:
            if new_value != value:
                self.date_widget[key].setMultipleTime()
                break
        else:
            if value is None:
                self.date_widget[key].clearTime()
            else:
                self.date_widget[key].setTime(value)

    def _update_orientation(self):
        value = None
        for image in self.image_list.get_selected_images():
            new_value = image.metadata.orientation
            if new_value:
                new_value = new_value.value
            else:
                new_value = None
            if value and new_value != value:
                value = -1
                break
            value = new_value
        if not value:
            value = 1
        self.orientation.setCurrentIndex(self.orientation.findData(value))

    def _update_lens_model(self):
        value = None
        for image in self.image_list.get_selected_images():
            new_value = image.metadata.lens_model.as_str()
            if value is not None and new_value != value:
                # multiple values
                self.lens_model.setCurrentIndex(self.lens_model.findData(-1))
                return
            value = new_value
        index = self.lens_model.findText(value)
        if index >= 0:
            self.lens_model.setCurrentIndex(index)
            return
        self.lens_data.image_load(
            value, self.image_list.get_selected_images()[0])
        blocked = self.lens_model.blockSignals(True)
        self.lens_model.insertItem(0, value)
        self.lens_model.setCurrentIndex(0)
        self.lens_model.blockSignals(blocked)

    def _update_aperture(self):
        value = None
        for image in self.image_list.get_selected_images():
            new_value = image.metadata.aperture
            if value and new_value.value != value.value:
                self.aperture.setText(self.tr('<multiple values>'))
                return
            value = new_value
        self.aperture.setText(value.as_str())

    def _update_focal_length(self):
        value = None
        for image in self.image_list.get_selected_images():
            new_value = image.metadata.focal_length
            if value and new_value.value != value.value:
                self.focal_length.setText(self.tr('<multiple values>'))
                return
            value = new_value
        self.focal_length.setText(value.as_str())

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        if not selection:
            for key in self.date_widget:
                self.date_widget[key].clearDate()
                self.date_widget[key].clearTime()
            self.orientation.setCurrentIndex(self.orientation.findData(1))
            self.lens_model.setCurrentIndex(self.orientation.findData(0))
            self.aperture.clear()
            self.focal_length.clear()
            self.setEnabled(False)
            return
        for key in self.date_widget:
            self._update_datetime(key)
        for key in self.link_widget:
            master = self.link_master[key]
            if (self.date_widget[key].date.date() ==
                                        self.date_widget[master].date.date() and
                    self.date_widget[key].time.time() ==
                                        self.date_widget[master].time.time()):
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
