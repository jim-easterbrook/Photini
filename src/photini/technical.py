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

from .metadata import LensSpec
from .pyqt import QtCore, QtGui, QtWidgets
from .utils import multiple


class DropdownEdit(QtWidgets.QComboBox):
    new_value = QtCore.pyqtSignal()

    def __init__(self, *arg, **kw):
        super(DropdownEdit, self).__init__(*arg, **kw)
        self.addItem('', None)
        self.addItem(multiple)
        self.currentIndexChanged.connect(self._new_value)

    @QtCore.pyqtSlot(int)
    def _new_value(self, index):
        if index >= 0:
            self.new_value.emit()

    def add_item(self, text, data=None):
        if data is None:
            data = text
        blocked = self.blockSignals(True)
        self.insertItem(self.count() - 2, text, str(data))
        self.blockSignals(blocked)

    def known_value(self, value):
        if value is None:
            return True
        return self.findData(str(value)) >= 0

    def set_value(self, value):
        if value is None:
            self.setCurrentIndex(self.count() - 2)
        else:
            self.setCurrentIndex(self.findData(str(value)))

    def get_value(self):
        return self.itemData(self.currentIndex())

    def set_multiple(self):
        self.setCurrentIndex(self.count() - 1)

    def is_multiple(self):
        return self.currentIndex() == self.count() - 1


class FloatEdit(QtWidgets.QLineEdit):
    def __init__(self, *arg, **kw):
        super(FloatEdit, self).__init__(*arg, **kw)
        self.setValidator(DoubleValidator())
        self._is_multiple = False

    def set_value(self, value):
        self._is_multiple = False
        if value is None:
            self.clear()
            self.setPlaceholderText('')
        else:
            self.setText('{:g}'.format(float(value)))

    def get_value(self):
        return self.text()

    def set_multiple(self):
        self._is_multiple = True
        self.setPlaceholderText(multiple)
        self.clear()

    def is_multiple(self):
        return self._is_multiple and not bool(self.get_value())


class DateTimeEdit(QtWidgets.QHBoxLayout):
    new_value = QtCore.pyqtSignal(object)

    def __init__(self, is_date, *arg, **kw):
        super(DateTimeEdit, self).__init__(*arg, **kw)
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
        # get internals of QDateTimeEdit widget
        self.line_edit = self.datetime.findChild(QtWidgets.QLineEdit)

    def _clear(self):
        self.new_value.emit(None)

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
            self.line_edit.setText('')
        else:
            self.is_none = False
            if self.is_date:
                self.datetime.setDate(value)
            else:
                self.datetime.setTime(value)

    def set_multiple(self):
        self.is_none = True
        # first time setText is called sometimes doesn't show
        self.line_edit.setText(multiple)
        self.line_edit.setText(multiple)

    def editing_finished(self):
        self.is_none = False
        self.new_value.emit(self.get_value())

    def set_enabled(self, enabled):
        for n in range(self.count()):
            self.itemAt(n).widget().setEnabled(enabled)


class DateAndTimeWidget(QtWidgets.QHBoxLayout):
    def __init__(self, *arg, **kw):
        super(DateAndTimeWidget, self).__init__(*arg, **kw)
        self.setContentsMargins(0, 0, 0, 0)
        # date
        self.date = DateTimeEdit(True)
        self.addLayout(self.date)
        self.addStretch(1)
        # time
        self.time = DateTimeEdit(False)
        self.addLayout(self.time)

    def set_date(self, value):
        self.date.set_value(value)
        self.time.set_enabled(value is not None)

    def set_time(self, value):
        self.time.set_value(value)

    def set_multiple_date(self):
        self.date.set_multiple()
        self.time.set_enabled(False)

    def set_multiple_time(self):
        self.time.set_multiple()


class OffsetWidget(QtWidgets.QWidget):
    apply_offset = QtCore.pyqtSignal(timedelta)

    def __init__(self, *arg, **kw):
        super(OffsetWidget, self).__init__(*arg, **kw)
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
        if not model:
            for item in ('lens_make', 'lens_serial', 'lens_spec'):
                setattr(image.metadata, item, None)
            return
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
        if not model:
            return None
        section = 'lens ' + model
        spec = self.config_store.get(section, 'lens_spec')
        if not spec:
            return None
        return LensSpec.from_string(spec)


class NewLensDialog(QtWidgets.QDialog):
    def __init__(self, *arg, **kw):
        super(NewLensDialog, self).__init__(*arg, **kw)
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
        self.widgets['lens_model'] = QtWidgets.QLineEdit()
        panel.layout().addRow(self.tr('Model name'), self.widgets['lens_model'])
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
        self.lens_spec['min_fl'].setValidator(QtGui.QDoubleValidator(bottom=0.0))
        panel.layout().addRow(self.tr('Minimum focal length (mm)'),
                              self.lens_spec['min_fl'])
        # min focal length aperture
        self.lens_spec['min_fl_fn'] = QtWidgets.QLineEdit()
        self.lens_spec['min_fl_fn'].setValidator(DoubleValidator(bottom=0.0))
        panel.layout().addRow(self.tr('Aperture at min. focal length f/'),
                              self.lens_spec['min_fl_fn'])
        # max focal length
        self.lens_spec['max_fl'] = QtWidgets.QLineEdit()
        self.lens_spec['max_fl'].setValidator(QtGui.QDoubleValidator(bottom=0.0))
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
    def __init__(self, config_store, image_list, *arg, **kw):
        super(Technical, self).__init__(*arg, **kw)
        self.config_store = config_store
        self.image_list = image_list
        self.setLayout(QtWidgets.QGridLayout())
        self.widgets = {}
        self.date_widget = {}
        self.link_widget = {}
        # store lens data in another object
        self.lens_data = LensData(self.config_store)
        # date and time
        date_group = QtWidgets.QGroupBox(self.tr('Date and time'))
        date_group.setLayout(QtWidgets.QFormLayout())
        # taken
        self.date_widget['taken'] = DateAndTimeWidget()
        self.date_widget['taken'].date.new_value.connect(self.new_date_taken)
        self.date_widget['taken'].time.new_value.connect(self.new_time_taken)
        date_group.layout().addRow(self.tr('Taken'), self.date_widget['taken'])
        # link taken & digitised
        self.link_widget['taken', 'digitised'] = QtWidgets.QCheckBox(
            self.tr("Link 'taken' and 'digitised'"))
        self.link_widget[
            'taken', 'digitised'].clicked.connect(self.new_link_digitised)
        date_group.layout().addRow('', self.link_widget['taken', 'digitised'])
        # digitised
        self.date_widget['digitised'] = DateAndTimeWidget()
        self.date_widget['digitised'].date.new_value.connect(self.new_date_digitised)
        self.date_widget['digitised'].time.new_value.connect(self.new_time_digitised)
        date_group.layout().addRow(
            self.tr('Digitised'), self.date_widget['digitised'])
        # link digitised & modified
        self.link_widget['digitised', 'modified'] = QtWidgets.QCheckBox(
            self.tr("Link 'digitised' and 'modified'"))
        self.link_widget[
            'digitised', 'modified'].clicked.connect(self.new_link_modified)
        date_group.layout().addRow('', self.link_widget['digitised', 'modified'])
        # modified
        self.date_widget['modified'] = DateAndTimeWidget()
        self.date_widget['modified'].date.new_value.connect(self.new_date_modified)
        self.date_widget['modified'].time.new_value.connect(self.new_time_modified)
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
        self.widgets['orientation'] = DropdownEdit()
        self.widgets['orientation'].add_item(self.tr('normal'), 1)
        self.widgets['orientation'].add_item(self.tr('rotate -90'), 6)
        self.widgets['orientation'].add_item(self.tr('rotate +90'), 8)
        self.widgets['orientation'].add_item(self.tr('rotate 180'), 3)
        self.widgets['orientation'].add_item(self.tr('reflect left-right'), 2)
        self.widgets['orientation'].add_item(self.tr('reflect top-bottom'), 4)
        self.widgets['orientation'].add_item(self.tr('reflect tr-bl'), 5)
        self.widgets['orientation'].add_item(self.tr('reflect tl-br'), 7)
        self.widgets['orientation'].new_value.connect(self.new_orientation)
        other_group.layout().addRow(
            self.tr('Orientation'), self.widgets['orientation'])
        # lens model
        self.widgets['lens_model'] = DropdownEdit()
        self.widgets['lens_model'].add_item(
            self.tr('<define new lens>'), '<add lens>')
        for model in self.lens_data.lenses:
            self.widgets['lens_model'].add_item(model)
        self.widgets['lens_model'].new_value.connect(self.new_lens_model)
        other_group.layout().addRow(
            self.tr('Lens model'), self.widgets['lens_model'])
        # link lens to aperture & focal length
        self.link_lens = QtWidgets.QCheckBox(
            self.tr("Link lens model to\nfocal length && aperture"))
        self.link_lens.setChecked(True)
        other_group.layout().addRow('', self.link_lens)
        # focal length
        self.widgets['focal_length'] = FloatEdit()
        self.widgets['focal_length'].validator().setBottom(0.1)
        self.widgets['focal_length'].setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.widgets['focal_length'].editingFinished.connect(self.new_focal_length)
        other_group.layout().addRow(
            self.tr('Focal length (mm)'), self.widgets['focal_length'])
        # aperture
        self.widgets['aperture'] = FloatEdit()
        self.widgets['aperture'].validator().setBottom(0.1)
        self.widgets['aperture'].setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.widgets['aperture'].editingFinished.connect(self.new_aperture)
        other_group.layout().addRow(
            self.tr('Aperture f/'), self.widgets['aperture'])
        self.layout().addWidget(other_group, 0, 1)
        self.layout().setColumnStretch(0, 1)
        self.layout().setColumnStretch(1, 1)
        # disable until an image is selected
        self.setEnabled(False)

    def refresh(self):
        pass

    def do_not_close(self):
        return False

    @QtCore.pyqtSlot(object)
    def new_date_taken(self, value):
        self._new_date_value('taken', value)
        if self.link_widget['taken', 'digitised'].isChecked():
            self.new_date_digitised(value)

    @QtCore.pyqtSlot(object)
    def new_date_digitised(self, value):
        self._new_date_value('digitised', value)
        if self.link_widget['digitised', 'modified'].isChecked():
            self.new_date_modified(value)

    @QtCore.pyqtSlot(object)
    def new_date_modified(self, value):
        self._new_date_value('modified', value)

    @QtCore.pyqtSlot(object)
    def new_time_taken(self, value):
        self._new_time_value('taken', value)
        if self.link_widget['taken', 'digitised'].isChecked():
            self.new_time_digitised(value)

    @QtCore.pyqtSlot(object)
    def new_time_digitised(self, value):
        self._new_time_value('digitised', value)
        if self.link_widget['digitised', 'modified'].isChecked():
            self.new_time_modified(value)

    @QtCore.pyqtSlot(object)
    def new_time_modified(self, value):
        self._new_time_value('modified', value)

    @QtCore.pyqtSlot(timedelta)
    def apply_offset(self, offset):
        for image in self.image_list.get_selected_images():
            value = image.metadata.date_taken
            if value is None:
                continue
            value = value.datetime() + offset
            image.metadata.date_taken = value.date(), value.time()
            if self.link_widget['taken', 'digitised'].isChecked():
                image.metadata.date_digitised = value.date(), value.time()
                if self.link_widget['digitised', 'modified'].isChecked():
                    image.metadata.date_modified = value.date(), value.time()
        for key in self.date_widget:
            self._update_datetime(key)

    def new_link_digitised(self):
        if self.link_widget['taken', 'digitised'].isChecked():
            self.date_widget['digitised'].setEnabled(False)
            self.new_date_digitised(self.date_widget['taken'].date.get_value())
            self.new_time_digitised(self.date_widget['taken'].time.get_value())
        else:
            self.date_widget['digitised'].setEnabled(True)

    def new_link_modified(self):
        if self.link_widget['digitised', 'modified'].isChecked():
            self.date_widget['modified'].setEnabled(False)
            self.new_date_modified(self.date_widget['digitised'].date.get_value())
            self.new_time_modified(self.date_widget['digitised'].time.get_value())
        else:
            self.date_widget['modified'].setEnabled(True)

    @QtCore.pyqtSlot()
    def new_orientation(self):
        if self.widgets['orientation'].is_multiple():
            self._update_orientation()
            return
        value = self.widgets['orientation'].get_value()
        if value is not None:
            value = int(value)
        for image in self.image_list.get_selected_images():
            image.metadata.orientation = value
            image.pixmap = None
            image.load_thumbnail()

    @QtCore.pyqtSlot()
    def new_lens_model(self):
        if self.widgets['lens_model'].is_multiple():
            self._update_lens_model()
            return
        value = self.widgets['lens_model'].get_value()
        if value == '<add lens>':
            self._add_lens_model()
            self._update_lens_model()
            return
        for image in self.image_list.get_selected_images():
            self.lens_data.image_save(value, image)
        spec = self.lens_data.get_spec(value)
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
        self.widgets['lens_model'].add_item(model)

    def new_aperture(self):
        if not self.widgets['aperture'].is_multiple():
            value = self.widgets['aperture'].get_value()
            for image in self.image_list.get_selected_images():
                image.metadata.aperture = value

    def new_focal_length(self):
        if not self.widgets['focal_length'].is_multiple():
            value = self.widgets['focal_length'].get_value()
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
                self.date_widget[key].set_multiple_date()
                break
        else:
            self.date_widget[key].set_date(date)
        for image in images[1:]:
            new_value = getattr(image.metadata, 'date_' + key)
            if new_value is not None:
                new_value = new_value.time
            if new_value != time:
                self.date_widget[key].set_multiple_time()
                break
        else:
            self.date_widget[key].set_time(time)

    def _update_orientation(self):
        images = self.image_list.get_selected_images()
        value = images[0].metadata.orientation
        for image in images[1:]:
            if image.metadata.orientation != value:
                # multiple values
                self.widgets['orientation'].set_multiple()
                return
        self.widgets['orientation'].set_value(value)

    def _update_lens_model(self):
        images = self.image_list.get_selected_images()
        value = images[0].metadata.lens_model
        for image in images[1:]:
            if image.metadata.lens_model != value:
                # multiple values
                self.widgets['lens_model'].set_multiple()
                return
        if not self.widgets['lens_model'].known_value(value):
            # new lens
            self.lens_data.image_load(value, images[0])
            self.widgets['lens_model'].add_item(value)
        self.widgets['lens_model'].set_value(value)

    def _update_aperture(self):
        images = self.image_list.get_selected_images()
        value = images[0].metadata.aperture
        for image in images[1:]:
            if image.metadata.aperture != value:
                self.widgets['aperture'].set_multiple()
                return
        self.widgets['aperture'].set_value(value)

    def _update_focal_length(self):
        images = self.image_list.get_selected_images()
        value = images[0].metadata.focal_length
        for image in images[1:]:
            if image.metadata.focal_length != value:
                self.widgets['focal_length'].set_multiple()
                return
        self.widgets['focal_length'].set_value(value)

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        if not selection:
            for key in self.date_widget:
                self.date_widget[key].set_date(None)
                self.date_widget[key].set_time(None)
            for key in self.widgets:
                self.widgets[key].set_value(None)
            self.setEnabled(False)
            return
        for key in self.date_widget:
            self._update_datetime(key)
        for master, slave in self.link_widget:
            if (self.date_widget[slave].date.get_value() ==
                                self.date_widget[master].date.get_value() and
                    self.date_widget[slave].time.get_value() ==
                                self.date_widget[master].time.get_value()):
                self.date_widget[slave].setEnabled(False)
                self.link_widget[master, slave].setChecked(True)
            else:
                self.date_widget[slave].setEnabled(True)
                self.link_widget[master, slave].setChecked(False)
        self._update_orientation()
        self._update_lens_model()
        self._update_aperture()
        self._update_focal_length()
        self.setEnabled(True)
