# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-19  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
from datetime import datetime, timedelta
import logging
import math
import re

import six

from photini.metadata import LensSpec
from photini.pyqt import (
    catch_all, ComboBox, multiple, multiple_values, Qt, QtCore, QtGui,
    QtWidgets, scale_font, set_symbol_font, Slider, SquareButton)

logger = logging.getLogger(__name__)


class DropdownEdit(ComboBox):
    new_value = QtCore.pyqtSignal(object)

    def __init__(self, *arg, **kw):
        super(DropdownEdit, self).__init__(*arg, **kw)
        self.addItem(self.tr('<clear>'), None)
        self.addItem('', None)
        self.setItemData(1, 0, Qt.UserRole - 1)
        self.addItem(multiple_values(), None)
        self.setItemData(2, 0, Qt.UserRole - 1)
        self.currentIndexChanged.connect(self.current_index_changed)

    @QtCore.pyqtSlot(int)
    @catch_all
    def current_index_changed(self, int):
        self.new_value.emit(self.get_value())

    def add_item(self, text, data):
        blocked = self.blockSignals(True)
        self.insertItem(self.count() - 3, text, six.text_type(data))
        self.set_dropdown_width()
        self.blockSignals(blocked)

    def remove_item(self, data):
        blocked = self.blockSignals(True)
        self.removeItem(self.findData(six.text_type(data)))
        self.set_dropdown_width()
        self.blockSignals(blocked)

    def known_value(self, value):
        if not value:
            return True
        return self.findData(six.text_type(value)) >= 0

    def set_value(self, value):
        blocked = self.blockSignals(True)
        if not value:
            self.setCurrentIndex(self.count() - 2)
        else:
            self.setCurrentIndex(self.findData(six.text_type(value)))
        self.blockSignals(blocked)

    def get_value(self):
        return self.itemData(self.currentIndex())

    def set_multiple(self):
        blocked = self.blockSignals(True)
        self.setCurrentIndex(self.count() - 1)
        self.blockSignals(blocked)


class NumberEdit(QtWidgets.QLineEdit):
    new_value = QtCore.pyqtSignal(six.text_type)

    def __init__(self, *arg, **kw):
        super(NumberEdit, self).__init__(*arg, **kw)
        self.multiple = multiple_values()
        self.textEdited.connect(self.text_edited)
        self.editingFinished.connect(self.editing_finished)

    @QtCore.pyqtSlot(six.text_type)
    @catch_all
    def text_edited(self, text):
        self.setPlaceholderText('')

    @QtCore.pyqtSlot()
    @catch_all
    def editing_finished(self):
        if self.placeholderText() != self.multiple:
            self.new_value.emit(self.text())

    def set_value(self, value):
        self.setPlaceholderText('')
        if value:
            self.setText(str(value))
        else:
            self.clear()

    def set_multiple(self):
        self.setPlaceholderText(self.multiple)
        self.clear()


class DateTimeEdit(QtWidgets.QDateTimeEdit):
    def __init__(self, *arg, **kw):
        super(DateTimeEdit, self).__init__(*arg, **kw)
        self.precision = 1
        self.multiple = multiple_values()
        # get size at full precision
        self.set_value(QtCore.QDateTime.currentDateTime())
        self.set_precision(7)
        self.minimum_size = super(DateTimeEdit, self).sizeHint()
        # clear display
        self.set_value(None)

    def sizeHint(self):
        return self.minimum_size

    @catch_all
    def contextMenuEvent(self, event):
        if not self.is_multiple():
            return super(DateTimeEdit, self).contextMenuEvent(event)
        menu = QtWidgets.QMenu(self)
        for suggestion in self.choices:
            if suggestion:
                menu.addAction(self.textFromDateTime(suggestion))
        action = menu.exec_(event.globalPos())
        if action:
            self.set_value(self.dateTimeFromText(action.iconText()))

    def dateTimeFromText(self, text):
        if not text:
            self.set_value(None)
            return self.dateTime()
        return super(DateTimeEdit, self).dateTimeFromText(text)

    def validate(self, text, pos):
        if self.is_multiple():
            self.set_value(None)
            text = ''
        if not text:
            return QtGui.QValidator.Acceptable, text, pos
        return super(DateTimeEdit, self).validate(text, pos)

    def get_value(self):
        if self.specialValueText() == ' ':
            return None
        return self.dateTime().toPyDateTime()

    def set_value(self, value):
        if value is None:
            self.setSpecialValueText(' ')
            self.setMinimumDateTime(self.dateTime())
        else:
            self.setSpecialValueText('')
            txt = self.specialValueText()
            self.clearMinimumDateTime()
            self.setDateTime(value)

    @QtCore.pyqtSlot(int)
    @catch_all
    def set_precision(self, value):
        if value != self.precision:
            self.precision = value
            self.setDisplayFormat(
                ''.join(('yyyy', '-MM', '-dd',
                         ' hh', ':mm', ':ss', '.zzz')[:self.precision]))

    def set_multiple(self, choices=[]):
        self.choices = choices
        self.setSpecialValueText(self.multiple)
        self.setMinimumDateTime(self.dateTime())

    def is_multiple(self):
        return self.specialValueText() == self.multiple


class TimeZoneWidget(QtWidgets.QSpinBox):
    def __init__(self, *arg, **kw):
        super(TimeZoneWidget, self).__init__(*arg, **kw)
        self.multiple = multiple()
        self.setRange(-14 * 60, 15 * 60)
        self.setSingleStep(15)
        self.setWrapping(True)
        # set fixed width
        self.setValue(-8 * 60)
        self.setFixedWidth(super(TimeZoneWidget, self).sizeHint().width())

    @catch_all
    def contextMenuEvent(self, event):
        if not self.is_multiple():
            return super(TimeZoneWidget, self).contextMenuEvent(event)
        menu = QtWidgets.QMenu(self)
        for suggestion in self.choices:
            if suggestion is not None:
                menu.addAction(self.textFromValue(suggestion))
        action = menu.exec_(event.globalPos())
        if action:
            self.set_value(self.valueFromText(action.iconText()))

    def validate(self, text, pos):
        if self.is_multiple():
            self.unset_multiple()
            text = text[pos - 1]
        if not text.strip():
            return QtGui.QValidator.Acceptable, text, pos
        if re.match('[+-]?\d{1,2}(:\d{0,2})?$', text):
            return QtGui.QValidator.Acceptable, text, pos
        if re.match('[+-]?$', text):
            return QtGui.QValidator.Intermediate, text, pos
        return QtGui.QValidator.Invalid, text, pos

    def valueFromText(self, text):
        if not text.strip():
            self.set_value(None)
            return self.value()
        hours, sep, minutes = text.partition(':')
        hours = int(hours)
        if minutes:
            minutes = int(15.0 * round(float(minutes) / 15.0))
            if hours < 0:
                minutes = -minutes
        else:
            minutes = 0
        return (hours * 60) + minutes

    def textFromValue(self, value):
        if value < 0:
            sign = '-'
            value = -value
        else:
            sign = '+'
        return '{}{:02d}:{:02d}'.format(sign, value // 60, value % 60)

    def get_value(self):
        if self.specialValueText() == ' ':
            return None
        return self.value()

    def set_value(self, value):
        if value is None:
            self.setSpecialValueText(' ')
            self.setMinimum(self.value())
        else:
            self.unset_multiple()
            self.setValue(value)

    def set_multiple(self, choices=[]):
        self.choices = choices
        self.setSpecialValueText(self.multiple)
        self.setMinimum(self.value())

    def unset_multiple(self):
        self.setSpecialValueText('')
        self.setMinimum(-14 * 60)

    def is_multiple(self):
        return self.specialValueText() == self.multiple


class DateAndTimeWidget(QtWidgets.QGridLayout):
    new_value = QtCore.pyqtSignal(six.text_type, dict)

    def __init__(self, name, *arg, **kw):
        super(DateAndTimeWidget, self).__init__(*arg, **kw)
        self.name = name
        self.setVerticalSpacing(0)
        self.setColumnStretch(3, 1)
        self.members = {}
        # date & time
        self.members['datetime'] = DateTimeEdit()
        self.members['datetime'].setCalendarPopup(True)
        self.addWidget(self.members['datetime'], 0, 0, 1, 2)
        # time zone
        self.members['tz_offset'] = TimeZoneWidget()
        self.addWidget(self.members['tz_offset'], 0, 2)
        # precision
        self.addWidget(QtWidgets.QLabel(self.tr('Precision:')), 1, 0)
        self.members['precision'] = Slider(Qt.Horizontal)
        self.members['precision'].setRange(1, 7)
        self.members['precision'].setPageStep(1)
        self.addWidget(self.members['precision'], 1, 1)
        # connections
        self.members['precision'].valueChanged.connect(
            self.members['datetime'].set_precision)
        self.members['datetime'].editingFinished.connect(self.editing_finished)
        self.members['tz_offset'].editingFinished.connect(self.editing_finished)
        self.members['precision'].editing_finished.connect(self.editing_finished)

    def set_enabled(self, enabled):
        for widget in self.members.values():
            widget.setEnabled(enabled)

    def get_value(self):
        new_value = {}
        for key in self.members:
            if self.members[key].is_multiple():
                continue
            new_value[key] = self.members[key].get_value()
        return new_value

    @QtCore.pyqtSlot()
    @catch_all
    def editing_finished(self):
        self.new_value.emit(self.name, self.get_value())


class OffsetWidget(QtWidgets.QWidget):
    apply_offset = QtCore.pyqtSignal(timedelta, object)

    def __init__(self, *arg, **kw):
        super(OffsetWidget, self).__init__(*arg, **kw)
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        spacing = self.layout().spacing()
        self.layout().setSpacing(0)
        # offset value
        self.offset = QtWidgets.QTimeEdit()
        self.offset.setDisplayFormat("'h:'hh 'm:'mm 's:'ss")
        self.layout().addWidget(self.offset)
        self.layout().addSpacing(spacing)
        # time zone
        self.time_zone = TimeZoneWidget()
        self.time_zone.set_value(None)
        self.layout().addWidget(self.time_zone)
        self.layout().addSpacing(spacing)
        # add offset button
        add_button = SquareButton(six.unichr(0x002b))
        add_button.setStyleSheet('QPushButton {padding: 0px}')
        set_symbol_font(add_button)
        scale_font(add_button, 170)
        add_button.clicked.connect(self.add)
        self.layout().addWidget(add_button)
        # subtract offset button
        sub_button = SquareButton(six.unichr(0x2212))
        sub_button.setStyleSheet('QPushButton {padding: 0px}')
        set_symbol_font(sub_button)
        scale_font(sub_button, 170)
        sub_button.clicked.connect(self.sub)
        self.layout().addWidget(sub_button)
        self.layout().addStretch(1)
        # restore stored values
        value = eval(self.config_store.get('technical', 'offset', 'None'))
        if value:
            self.offset.setTime(QtCore.QTime(*value[0:3]))
            self.time_zone.set_value(value[3])
        # connections
        self.offset.editingFinished.connect(self.new_value)
        self.time_zone.editingFinished.connect(self.new_value)

    @QtCore.pyqtSlot()
    @catch_all
    def new_value(self):
        value = self.offset.time()
        value = (value.hour(), value.minute(), value.second(),
                 self.time_zone.get_value())
        self.config_store.set('technical', 'offset', str(value))

    @QtCore.pyqtSlot()
    @catch_all
    def add(self):
        self.do_inc(False)

    @QtCore.pyqtSlot()
    @catch_all
    def sub(self):
        self.do_inc(True)

    def do_inc(self, negative):
        value = self.offset.time()
        offset = timedelta(
            hours=value.hour(), minutes=value.minute(), seconds=value.second())
        tz_offset = self.time_zone.get_value()
        if negative:
            if tz_offset is not None:
                tz_offset = -tz_offset
            offset = -offset
        self.apply_offset.emit(offset, tz_offset)


class LensSpecWidget(QtWidgets.QGroupBox):
    def __init__(self, *arg, **kw):
        super(LensSpecWidget, self).__init__(*arg, **kw)
        self.setLayout(QtWidgets.QGridLayout())
        self.layout().setContentsMargins(6, 0, 6, 0)
        self.layout().setVerticalSpacing(0)
        for text, col in (self.tr('min'), 1), (self.tr('max'), 2):
            label = QtWidgets.QLabel(text)
            label.setAlignment(Qt.AlignHCenter)
            self.layout().addWidget(label, 0, col)
        self.layout().addWidget(QtWidgets.QLabel(self.tr('Focal length')), 1, 0)
        self.layout().addWidget(QtWidgets.QLabel(self.tr('Max aperture')), 2, 0)
        self.multiple = QtWidgets.QLabel(multiple_values())
        self.layout().addWidget(self.multiple, 1, 1, 2, 2)
        self.multiple.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.multiple.hide()
        self.values = {
            'min_fl'    : QtWidgets.QLabel(),
            'max_fl'    : QtWidgets.QLabel(),
            'min_fl_fn' : QtWidgets.QLabel(),
            'max_fl_fn' : QtWidgets.QLabel(),
            }
        for key in self.values:
            self.values[key].setAlignment(Qt.AlignHCenter)
        self.layout().addWidget(self.values['min_fl'], 1, 1)
        self.layout().addWidget(self.values['max_fl'], 1, 2)
        self.layout().addWidget(self.values['min_fl_fn'], 2, 1)
        self.layout().addWidget(self.values['max_fl_fn'], 2, 2)

    def set_value(self, value):
        self.multiple.hide()
        for key in self.values:
            sub_val = getattr(value, key, None)
            if sub_val:
                self.values[key].setText('{:g}'.format(float(sub_val)))
            else:
                self.values[key].clear()
            self.values[key].show()

    def set_multiple(self):
        for key in self.values:
            self.values[key].hide()
        self.multiple.show()


class DoubleValidator(QtGui.QDoubleValidator):
    def validate(self, input_, pos):
        # accept empty string as valid, to allow metadata to be cleared
        if input_ == '':
            return QtGui.QValidator.Acceptable, input_, pos
        return super(DoubleValidator, self).validate(input_, pos)


class IntValidator(QtGui.QIntValidator):
    def validate(self, input_, pos):
        # accept empty string as valid, to allow metadata to be cleared
        if input_ == '':
            return QtGui.QValidator.Acceptable, input_, pos
        return super(IntValidator, self).validate(input_, pos)


class LensData(object):
    def __init__(self):
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.lenses = eval(self.config_store.get('technical', 'lenses', '[]'))
        self.lenses.sort()

    def delete_model(self, model):
        if model not in self.lenses:
            return
        self.config_store.remove_section('lens ' + model)
        self.lenses.remove(model)
        self.config_store.set('technical', 'lenses', repr(self.lenses))

    def save_to_image(self, model, image):
        image.metadata.lens_model = model
        if not model:
            for item in ('lens_make', 'lens_serial', 'lens_spec'):
                setattr(image.metadata, item, None)
            return
        section = 'lens ' + model
        for item in ('lens_make', 'lens_serial', 'lens_spec'):
            value = self.config_store.get(section, item) or None
            if item == 'lens_spec' and value and ',' not in value:
                value = ','.join(value.split())
                self.config_store.set(section, item, value)
            setattr(image.metadata, item, value)

    def load_from_image(self, model, image):
        section = 'lens ' + model
        for item in ('lens_make', 'lens_serial', 'lens_spec'):
            value = getattr(image.metadata, item)
            if value:
                self.config_store.set(section, item, str(value))
        if model not in self.lenses:
            self.lenses.append(model)
        self.lenses.sort()
        self.config_store.set('technical', 'lenses', repr(self.lenses))

    def load_from_dialog(self, dialog):
        model = dialog.lens_model.text()
        if not model:
            return None
        min_fl = dialog.lens_spec['min_fl'].text()
        if not min_fl:
            return None
        max_fl = dialog.lens_spec['max_fl'].text() or min_fl
        min_fl_fn = dialog.lens_spec['min_fl_fn'].text() or '0'
        max_fl_fn = dialog.lens_spec['max_fl_fn'].text() or min_fl_fn
        lens_spec = LensSpec((min_fl, max_fl, min_fl_fn, max_fl_fn))
        section = 'lens ' + model
        self.config_store.set(section, 'lens_make', dialog.lens_make.text())
        self.config_store.set(section, 'lens_serial', dialog.lens_serial.text())
        self.config_store.set(section, 'lens_spec', str(lens_spec))
        if model not in self.lenses:
            self.lenses.append(model)
        self.lenses.sort()
        self.config_store.set('technical', 'lenses', repr(self.lenses))
        return model


class NewLensDialog(QtWidgets.QDialog):
    def __init__(self, images, *arg, **kw):
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
        self.lens_model = QtWidgets.QLineEdit()
        self.lens_model.setMinimumWidth(
            self.lens_model.fontMetrics().width('x' * 35))
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
        # fill in any values we can from existing metadata
        for image in images:
            if image.metadata.lens_model:
                self.lens_model.setText(image.metadata.lens_model)
            if image.metadata.lens_make:
                self.lens_make.setText(image.metadata.lens_make)
            if image.metadata.lens_serial:
                self.lens_serial.setText(image.metadata.lens_serial)
            spec = image.metadata.lens_spec
            for key in self.lens_spec:
                if spec and spec[key]:
                    self.lens_spec[key].setText(
                        '{:g}'.format(float(spec[key])))


class DateLink(QtWidgets.QCheckBox):
    new_link = QtCore.pyqtSignal(six.text_type)

    def __init__(self, name, *arg, **kw):
        super(DateLink, self).__init__(*arg, **kw)
        self.name = name
        self.clicked.connect(self._clicked)

    @QtCore.pyqtSlot()
    @catch_all
    def _clicked(self):
        self.new_link.emit(self.name)

class Technical(QtWidgets.QWidget):
    def __init__(self, image_list, *arg, **kw):
        super(Technical, self).__init__(*arg, **kw)
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.image_list = image_list
        self.setLayout(QtWidgets.QHBoxLayout())
        self.widgets = {}
        self.date_widget = {}
        self.link_widget = {}
        # store lens data in another object
        self.lens_data = LensData()
        # date and time
        date_group = QtWidgets.QGroupBox(self.tr('Date and time'))
        date_group.setLayout(QtWidgets.QFormLayout())
        # create date and link widgets
        for master in self._master_slave:
            self.date_widget[master] = DateAndTimeWidget(master)
            self.date_widget[master].new_value.connect(self.new_date_value)
            slave = self._master_slave[master]
            if slave:
                self.link_widget[master, slave] = DateLink(master)
                self.link_widget[master, slave].new_link.connect(self.new_link)
        self.link_widget['taken', 'digitised'].setText(
            self.tr("Link 'taken' and 'digitised'"))
        self.link_widget['digitised', 'modified'].setText(
            self.tr("Link 'digitised' and 'modified'"))
        # add to layout
        date_group.layout().addRow(self.tr('Taken'),
                                   self.date_widget['taken'])
        date_group.layout().addRow('', self.link_widget['taken', 'digitised'])
        date_group.layout().addRow(self.tr('Digitised'),
                                   self.date_widget['digitised'])
        date_group.layout().addRow('', self.link_widget['digitised', 'modified'])
        date_group.layout().addRow(self.tr('Modified'),
                                   self.date_widget['modified'])
        # offset
        self.offset_widget = OffsetWidget()
        self.offset_widget.apply_offset.connect(self.apply_offset)
        date_group.layout().addRow(self.tr('Adjust times'), self.offset_widget)
        self.layout().addWidget(date_group)
        # other
        other_group = QtWidgets.QGroupBox(self.tr('Other'))
        other_group.setLayout(QtWidgets.QFormLayout())
        other_group.layout().setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
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
        self.widgets['lens_model'].setMinimumWidth(
            self.widgets['lens_model'].fontMetrics().width('x' * 30))
        self.widgets['lens_model'].setContextMenuPolicy(Qt.CustomContextMenu)
        self.widgets['lens_model'].add_item(
            self.tr('<define new lens>'), '<add lens>')
        for model in self.lens_data.lenses:
            self.widgets['lens_model'].add_item(model, model)
        self.widgets['lens_model'].new_value.connect(self.new_lens_model)
        self.widgets['lens_model'].customContextMenuRequested.connect(
            self.remove_lens_model)
        other_group.layout().addRow(
            self.tr('Lens model'), self.widgets['lens_model'])
        # lens specification
        self.widgets['lens_spec'] = LensSpecWidget()
        other_group.layout().addRow(
            self.tr('Lens details'), self.widgets['lens_spec'])
        # focal length
        self.widgets['focal_length'] = NumberEdit()
        self.widgets['focal_length'].setValidator(DoubleValidator())
        self.widgets['focal_length'].validator().setBottom(0.1)
        self.widgets['focal_length'].new_value.connect(self.new_focal_length)
        other_group.layout().addRow(
            self.tr('Focal length (mm)'), self.widgets['focal_length'])
        # 35mm equivalent focal length
        self.widgets['focal_length_35'] = NumberEdit()
        self.widgets['focal_length_35'].setValidator(IntValidator())
        self.widgets['focal_length_35'].validator().setBottom(1)
        self.widgets['focal_length_35'].new_value.connect(self.new_focal_length_35)
        other_group.layout().addRow(
            self.tr('35mm equiv (mm)'), self.widgets['focal_length_35'])
        # aperture
        self.widgets['aperture'] = NumberEdit()
        self.widgets['aperture'].setValidator(DoubleValidator())
        self.widgets['aperture'].validator().setBottom(0.1)
        self.widgets['aperture'].new_value.connect(self.new_aperture)
        other_group.layout().addRow(
            self.tr('Aperture f/'), self.widgets['aperture'])
        self.layout().addWidget(other_group, stretch=1)
        # disable until an image is selected
        self.setEnabled(False)

    _master_slave = {
        'taken'    : 'digitised',
        'digitised': 'modified',
        'modified' : None
        }

    def refresh(self):
        pass

    def do_not_close(self):
        return False

    @QtCore.pyqtSlot(timedelta, object)
    @catch_all
    def apply_offset(self, offset, tz_offset):
        for image in self.image_list.get_selected_images():
            date_taken = dict(image.metadata.date_taken or {})
            if not date_taken:
                continue
            date_taken['datetime'] += offset
            if tz_offset is not None:
                tz = (date_taken['tz_offset'] or 0) + tz_offset
                tz = min(max(tz, -14 * 60), 15 * 60)
                date_taken['tz_offset'] = tz
            self._set_date_value(image, 'taken', date_taken)
        self._update_datetime()

    @QtCore.pyqtSlot(six.text_type)
    @catch_all
    def new_link(self, master):
        slave = self._master_slave[master]
        if self.link_widget[master, slave].isChecked():
            self.date_widget[slave].set_enabled(False)
            for image in self.image_list.get_selected_images():
                temp = dict(getattr(image.metadata, 'date_' + master) or {})
                self._set_date_value(image, slave, temp)
            self._update_datetime()
        else:
            self.date_widget[slave].set_enabled(True)

    @QtCore.pyqtSlot(object)
    @catch_all
    def new_orientation(self, value):
        for image in self.image_list.get_selected_images():
            image.metadata.orientation = value
            image.load_thumbnail()
        self._update_orientation()

    @QtCore.pyqtSlot(QtCore.QPoint)
    @catch_all
    def remove_lens_model(self, pos):
        current_model = self.widgets['lens_model'].get_value()
        menu = QtWidgets.QMenu()
        for model in self.lens_data.lenses:
            if model == current_model:
                continue
            action = QtWidgets.QAction(
                self.tr('Remove lens "{}"').format(model), self)
            action.setData(model)
            menu.addAction(action)
        if menu.isEmpty():
            # no deletable lenses
            return
        action = menu.exec_(self.widgets['lens_model'].mapToGlobal(pos))
        if not action:
            return
        model = action.data()
        self.lens_data.delete_model(model)
        self.widgets['lens_model'].remove_item(model)

    @QtCore.pyqtSlot(object)
    @catch_all
    def new_lens_model(self, value):
        if value == '<add lens>':
            self._add_lens_model()
            self._update_lens_model()
            return
        for image in self.image_list.get_selected_images():
            self.lens_data.save_to_image(value, image)
        self._update_lens_model()
        self._update_lens_spec()

    def _add_lens_model(self):
        dialog = NewLensDialog(
            self.image_list.get_selected_images(), parent=self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        model = self.lens_data.load_from_dialog(dialog)
        if not model:
            return
        if not self.widgets['lens_model'].known_value(model):
            self.widgets['lens_model'].add_item(model, model)

    @QtCore.pyqtSlot(six.text_type)
    @catch_all
    def new_aperture(self, value):
        for image in self.image_list.get_selected_images():
            image.metadata.aperture = value

    @QtCore.pyqtSlot(six.text_type)
    @catch_all
    def new_focal_length(self, value):
        for image in self.image_list.get_selected_images():
            # only update 35mm equiv if already set
            if image.metadata.focal_length_35:
                image.metadata.focal_length_35 = self.calc_35(
                    image.metadata, value)
            image.metadata.focal_length = value
        self._update_focal_length()
        self._update_focal_length_35()

    @QtCore.pyqtSlot(six.text_type)
    @catch_all
    def new_focal_length_35(self, value):
        for image in self.image_list.get_selected_images():
            image.metadata.focal_length_35 = value
            self.set_crop_factor(image.metadata)
        self._update_focal_length()
        self._update_focal_length_35()

    @QtCore.pyqtSlot(six.text_type, dict)
    @catch_all
    def new_date_value(self, key, new_value):
        for image in self.image_list.get_selected_images():
            temp = dict(getattr(image.metadata, 'date_' + key) or {})
            temp.update(new_value)
            if 'datetime' not in temp:
                continue
            if temp['datetime'] is None:
                temp = None
            self._set_date_value(image, key, temp)
        self._update_datetime()

    def _set_date_value(self, image, master, new_value):
        while True:
            setattr(image.metadata, 'date_' + master, new_value)
            slave = self._master_slave[master]
            if not slave or not self.link_widget[master, slave].isChecked():
                break
            master = slave

    def _update_datetime(self):
        images = self.image_list.get_selected_images()
        for name in self.date_widget:
            attribute = 'date_' + name
            widget = self.date_widget[name]
            values = defaultdict(list)
            for image in images:
                image_datetime = getattr(image.metadata, attribute) or {}
                for key in widget.members:
                    value = None
                    if key in image_datetime:
                        value = image_datetime[key]
                    if value not in values[key]:
                        values[key].append(value)
            for key in widget.members:
                if len(values[key]) > 1:
                    widget.members[key].set_multiple(choices=values[key])
                else:
                    widget.members[key].set_value(values[key][0])

    def _update_links(self):
        images = self.image_list.get_selected_images()
        for master, slave in self.link_widget:
            for image in images:
                if (getattr(image.metadata, 'date_' + master) !=
                        getattr(image.metadata, 'date_' + slave)):
                    self.link_widget[master, slave].setChecked(False)
                    break
            else:
                self.link_widget[master, slave].setChecked(True)

    def _update_orientation(self):
        images = self.image_list.get_selected_images()
        if not images:
            return
        value = images[0].metadata.orientation
        for image in images[1:]:
            if image.metadata.orientation != value:
                # multiple values
                self.widgets['orientation'].set_multiple()
                return
        self.widgets['orientation'].set_value(value)

    def _update_lens_model(self):
        images = self.image_list.get_selected_images()
        if not images:
            return
        model = images[0].metadata.lens_model
        for image in images[1:]:
            if image.metadata.lens_model != model:
                # multiple values
                self.widgets['lens_model'].set_multiple()
                self.widgets['lens_model'].setToolTip('')
                return
        if not self.widgets['lens_model'].known_value(model):
            # new lens
            self.lens_data.load_from_image(model, images[0])
            self.widgets['lens_model'].add_item(model, model)
        self.widgets['lens_model'].set_value(model)
        tool_tip = ''
        if images[0].metadata.lens_make:
            tool_tip = images[0].metadata.lens_make + ' '
        if images[0].metadata.lens_model:
            tool_tip += images[0].metadata.lens_model + ' '
        if images[0].metadata.lens_serial:
            tool_tip += '(' + images[0].metadata.lens_serial + ')'
        self.widgets['lens_model'].setToolTip(tool_tip)

    def _update_lens_spec(self):
        images = self.image_list.get_selected_images()
        if not images:
            return
        spec = images[0].metadata.lens_spec
        for image in images[1:]:
            if image.metadata.lens_spec != spec:
                # multiple values
                self.widgets['lens_spec'].set_multiple()
                return
        self.widgets['lens_spec'].set_value(spec)
        if not spec:
            return
        make_changes = False
        for image in images:
            if image.metadata.aperture:
                new_aperture = image.metadata.aperture
            else:
                new_aperture = 0
            new_fl = image.metadata.focal_length or 0
            if new_fl <= spec.min_fl:
                new_fl = spec.min_fl
                new_aperture = max(new_aperture, spec.min_fl_fn)
            elif new_fl >= spec.max_fl:
                new_fl = spec.max_fl
                new_aperture = max(new_aperture, spec.max_fl_fn)
            else:
                new_aperture = max(new_aperture,
                                   min(spec.min_fl_fn, spec.max_fl_fn))
            if new_aperture == 0 and new_fl == 0:
                continue
            if (new_aperture == image.metadata.aperture and
                      new_fl == image.metadata.focal_length):
                continue
            if make_changes:
                pass
            elif QtWidgets.QMessageBox.question(
                    self, self.tr('Update aperture & focal length'),
                    self.tr('Adjust image aperture and focal length to' +
                            ' agree with lens specification?'),
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No
                    ) == QtWidgets.QMessageBox.No:
                return
            make_changes = True
            if new_aperture:
                image.metadata.aperture = new_aperture
            if new_fl:
                # only update 35mm equiv if already set
                if image.metadata.focal_length_35:
                    image.metadata.focal_length_35 = self.calc_35(
                        image.metadata, new_fl)
                image.metadata.focal_length = new_fl
        if make_changes:
            self._update_aperture()
            self._update_focal_length()
            self._update_focal_length_35()

    def _update_aperture(self):
        images = self.image_list.get_selected_images()
        if not images:
            return
        value = images[0].metadata.aperture
        for image in images[1:]:
            if image.metadata.aperture != value:
                self.widgets['aperture'].set_multiple()
                return
        self.widgets['aperture'].set_value(value)

    def _update_focal_length(self):
        images = self.image_list.get_selected_images()
        if not images:
            return
        value = images[0].metadata.focal_length
        for image in images[1:]:
            if image.metadata.focal_length != value:
                self.widgets['focal_length'].set_multiple()
                return
        self.widgets['focal_length'].set_value(value)

    def _update_focal_length_35(self):
        images = self.image_list.get_selected_images()
        if not images:
            return
        # display real value if it exists
        value = images[0].metadata.focal_length_35
        for image in images[1:]:
            if image.metadata.focal_length_35 != value:
                self.widgets['focal_length_35'].set_multiple()
                return
        self.widgets['focal_length_35'].set_value(value)
        if value:
            return
        # otherwise display calculated value
        value = self.calc_35(images[0].metadata)
        for image in images[1:]:
            fl_35 = self.calc_35(image.metadata)
            if fl_35 != value:
                self.widgets['focal_length_35'].set_multiple()
                return
        if value:
            # display as placeholder so it's shown faintly
            self.widgets['focal_length_35'].setPlaceholderText(str(value))

    def set_crop_factor(self, md):
        if not md.camera_model:
            return
        if not md.focal_length_35:
            self.config_store.set('crop factor', md.camera_model, 'None')
        elif md.focal_length:
            crop_factor = float(md.focal_length_35) / md.focal_length
            self.config_store.set(
                'crop factor', md.camera_model, str(crop_factor))

    def get_crop_factor(self, md):
        crop_factor = None
        if md.focal_length and md.focal_length_35:
            crop_factor = float(md.focal_length_35) / md.focal_length
            if md.camera_model:
                self.config_store.set(
                    'crop factor', md.camera_model, str(crop_factor))
        if md.camera_model and not crop_factor:
            crop_factor = eval(self.config_store.get(
                'crop factor', md.camera_model, 'None'))
        if not crop_factor and (md.resolution_x and md.resolution_x > 0 and
                                md.resolution_y and md.resolution_y > 0 and
                                md.dimension_x and md.dimension_x > 0 and
                                md.dimension_y and md.dimension_y > 0):
            # calculate from image size and resolution
            w = md.dimension_x / md.resolution_x
            h = md.dimension_y / md.resolution_y
            d = math.sqrt((h ** 2) + (w ** 2))
            if md.resolution_unit == 3:
                # unit is cm
                d *= 10.0
            elif md.resolution_unit in (None, 1, 2):
                # unit is (assumed to be) inches
                d *= 25.4
            # 35 mm film diagonal is 43.27 mm
            crop_factor = 43.27 / d
            if md.camera_model:
                self.config_store.set(
                    'crop factor', md.camera_model, str(crop_factor))
        return crop_factor

    def calc_35(self, md, value=None):
        crop_factor = self.get_crop_factor(md)
        value = value or md.focal_length
        if crop_factor and value:
            return int((float(value) * crop_factor) + 0.5)
        return md.focal_length_35

    @QtCore.pyqtSlot(list)
    @catch_all
    def new_selection(self, selection):
        if not selection:
            self.setEnabled(False)
            for widget in self.date_widget.values():
                for sub_widget in widget.members.values():
                    sub_widget.set_value(None)
            for widget in self.widgets.values():
                widget.set_value(None)
            return
        self._update_datetime()
        self._update_links()
        self._update_orientation()
        self._update_lens_model()
        self._update_aperture()
        self._update_focal_length()
        self._update_focal_length_35()
        self._update_lens_spec()
        self.setEnabled(True)
