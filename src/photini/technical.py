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
    QtWidgets, scale_font, set_symbol_font, Slider, SquareButton,
    width_for_text)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class DropdownEdit(ComboBox):
    new_value = QtCore.pyqtSignal(object)

    def __init__(self, *arg, **kw):
        super(DropdownEdit, self).__init__(*arg, **kw)
        self.addItem(translate('TechnicalTab', '<clear>'), None)
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


class AugmentSpinBox(object):
    new_value = QtCore.pyqtSignal(object)

    def __init__(self, *arg, **kw):
        super(AugmentSpinBox, self).__init__(*arg, **kw)
        self.set_value(None)
        self.editingFinished.connect(self.editing_finished)

    class ContextAction(QtWidgets.QAction):
        def __init__(self, label, value, parent):
            super(AugmentSpinBox.ContextAction, self).__init__(label, parent)
            self.setData(value)
            self.triggered.connect(self.set_value)

        @QtCore.pyqtSlot()
        @catch_all
        def set_value(self):
            self.parent().setValue(self.data())

    @catch_all
    def contextMenuEvent(self, event):
        if self.specialValueText() and self.choices:
            QtCore.QTimer.singleShot(0, self.extend_context_menu)
        return super(self.__class__, self).contextMenuEvent(event)

    @QtCore.pyqtSlot()
    @catch_all
    def extend_context_menu(self):
        menu = self.findChild(QtWidgets.QMenu)
        if not menu:
            return
        sep = menu.insertSeparator(menu.actions()[0])
        for suggestion in self.choices:
            menu.insertAction(sep, self.ContextAction(
                self.textFromValue(suggestion), suggestion, self))

    @catch_all
    def keyPressEvent(self, event):
        if self.specialValueText():
            self.set_value(self.default_value)
            self.selectAll()
        return super(self.__class__, self).keyPressEvent(event)

    @catch_all
    def stepBy(self, steps):
        if self.specialValueText():
            self.set_value(self.default_value)
            self.selectAll()
        return super(self.__class__, self).stepBy(steps)

    @catch_all
    def fixup(self, text):
        if not self.cleanText():
            # user has deleted the value
            self.set_value(None)
            return ''
        return super(self.__class__, self).fixup(text)

    @QtCore.pyqtSlot()
    @catch_all
    def editing_finished(self):
        if self.is_multiple():
            return
        self.get_value(emit=True)

    def get_value(self, emit=False):
        value = self.value()
        if value == self.minimum() and self.specialValueText():
            value = None
        if emit:
            self.new_value.emit(value)
        return value

    def set_value(self, value):
        if value is None:
            self.setValue(self.minimum())
            self.setSpecialValueText(' ')
        else:
            self.setSpecialValueText('')
            self.setValue(value)

    def set_multiple(self, choices=[]):
        self.choices = list(filter(None, choices))
        self.setValue(self.minimum())
        self.setSpecialValueText(self.multiple)

    def is_multiple(self):
        return (self.value() == self.minimum()
                and self.specialValueText() == self.multiple)


class IntSpinBox(QtWidgets.QSpinBox, AugmentSpinBox):
    def __init__(self, *arg, **kw):
        self.default_value = 0
        self.multiple = multiple_values()
        super(IntSpinBox, self).__init__(*arg, **kw)
        self.setSingleStep(1)
        lim = (2 ** 31) - 1
        self.setRange(-lim, lim)
        self.setButtonSymbols(self.NoButtons)

    def set_faint(self, faint):
        if faint:
            self.setStyleSheet('QAbstractSpinBox {font-weight:200}')
        else:
            self.setStyleSheet('QAbstractSpinBox {}')


class DoubleSpinBox(QtWidgets.QDoubleSpinBox, AugmentSpinBox):
    def __init__(self, *arg, **kw):
        self.default_value = 0
        self.multiple = multiple_values()
        super(DoubleSpinBox, self).__init__(*arg, **kw)
        self.setSingleStep(0.1)
        self.setDecimals(4)
        lim = (2 ** 31) - 1
        self.setRange(-lim, lim)
        self.setButtonSymbols(self.NoButtons)

    @catch_all
    def textFromValue(self, value):
        # don't use QDoubleSpinBox's fixed number of decimals
        return str(round(value, self.decimals()))


class CalendarWidget(QtWidgets.QCalendarWidget):
    @catch_all
    def showEvent(self, event):
        if self.selectedDate() == self.minimumDate():
            self.setSelectedDate(QtCore.QDate.currentDate())
        return super(CalendarWidget, self).showEvent(event)


class DateTimeEdit(QtWidgets.QDateTimeEdit, AugmentSpinBox):
    def __init__(self, *arg, **kw):
        self.default_value = QtCore.QDateTime(QtCore.QDate.currentDate())
        self.multiple = multiple_values()
        # rename some methods for compatibility with AugmentSpinBox
        self.cleanText = self.text
        self.minimum = self.minimumDateTime
        self.setValue = self.setDateTime
        self.textFromValue = self.textFromDateTime
        self.value = self.dateTime
        super(DateTimeEdit, self).__init__(*arg, **kw)
        self.setCalendarPopup(True)
        self.setCalendarWidget(CalendarWidget())
        self.precision = 1
        self.set_precision(7)

    @catch_all
    def sizeHint(self):
        size = super(DateTimeEdit, self).sizeHint()
        if self.precision == 7 and not self.is_multiple():
            self.setFixedSize(size)
        return size

    @catch_all
    def dateTimeFromText(self, text):
        if not text:
            self.set_value(None)
            return self.dateTime()
        return super(DateTimeEdit, self).dateTimeFromText(text)

    @catch_all
    def validate(self, text, pos):
        if not text:
            return QtGui.QValidator.Acceptable, text, pos
        return super(DateTimeEdit, self).validate(text, pos)

    @QtCore.pyqtSlot(int)
    @catch_all
    def set_precision(self, value):
        if value != self.precision:
            self.precision = value
            self.setDisplayFormat(
                ''.join(('yyyy', '-MM', '-dd',
                         ' hh', ':mm', ':ss', '.zzz')[:self.precision]))


class TimeZoneWidget(QtWidgets.QSpinBox, AugmentSpinBox):
    def __init__(self, *arg, **kw):
        self.default_value = 0
        self.multiple = multiple()
        super(TimeZoneWidget, self).__init__(*arg, **kw)
        self.setRange(-14 * 60, 15 * 60)
        self.setSingleStep(15)
        self.setWrapping(True)

    @catch_all
    def sizeHint(self):
        size = super(TimeZoneWidget, self).sizeHint()
        if not self.is_multiple():
            self.setFixedSize(size)
        return size

    @catch_all
    def validate(self, text, pos):
        if re.match('[+-]?\d{1,2}(:\d{0,2})?$', text):
            return QtGui.QValidator.Acceptable, text, pos
        if re.match('[+-]?$', text):
            return QtGui.QValidator.Intermediate, text, pos
        return QtGui.QValidator.Invalid, text, pos

    @catch_all
    def valueFromText(self, text):
        if not text.strip():
            return 0
        hours, sep, minutes = text.partition(':')
        hours = int(hours)
        if minutes:
            minutes = int(15.0 * round(float(minutes) / 15.0))
            if hours < 0:
                minutes = -minutes
        else:
            minutes = 0
        return (hours * 60) + minutes

    @catch_all
    def textFromValue(self, value):
        if value is None:
            return ''
        if value < 0:
            sign = '-'
            value = -value
        else:
            sign = '+'
        return '{}{:02d}:{:02d}'.format(sign, value // 60, value % 60)


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
        self.addWidget(self.members['datetime'], 0, 0, 1, 2)
        # time zone
        self.members['tz_offset'] = TimeZoneWidget()
        self.addWidget(self.members['tz_offset'], 0, 2)
        # precision
        self.addWidget(
            QtWidgets.QLabel(translate('TechnicalTab', 'Precision:')), 1, 0)
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
            if key == 'datetime' and new_value[key]:
                new_value[key] = new_value[key].toPyDateTime()
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

    @catch_all
    def showEvent(self, event):
        super(OffsetWidget, self).showEvent(event)
        # On some Windows versions the initial sizeHint calculation is
        # wrong. Redoing it after the widget becomes visible gets a
        # better result. Calling setSpecialValueText is also required.
        self.offset.setSpecialValueText('')
        self.offset.updateGeometry()
        self.time_zone.setSpecialValueText(' ')
        self.time_zone.updateGeometry()

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
        for text, col in ((translate('TechnicalTab', 'min'), 1),
                          (translate('TechnicalTab', 'max'), 2)):
            label = QtWidgets.QLabel(text)
            label.setAlignment(Qt.AlignHCenter)
            self.layout().addWidget(label, 0, col)
        self.layout().addWidget(
            QtWidgets.QLabel(translate('TechnicalTab', 'Focal length')), 1, 0)
        self.layout().addWidget(
            QtWidgets.QLabel(translate('TechnicalTab', 'Max aperture')), 2, 0)
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


class LensData(object):
    def __init__(self):
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.lenses = eval(self.config_store.get('technical', 'lenses', '[]'))
        # update config
        for section in self.config_store.config.sections():
            if section.startswith('lens '):
                lens_id = section[5:]
                if lens_id not in self.lenses:
                    self.lenses.append(lens_id)
        for old_id in list(self.lenses):
            section = 'lens ' + old_id
            values = {}
            for key in ('lens_model', 'lens_make', 'lens_serial', 'lens_spec'):
                values[key] = self.config_store.get(section, key) or None
            if not values['lens_model']:
                values['lens_model'] = old_id
            new_id = self.get_id(values['lens_model'], values['lens_make'],
                                 values['lens_serial'])
            if new_id in self.lenses:
                continue
            self.delete_model(old_id)
            section = 'lens ' + new_id
            for key in ('lens_model', 'lens_make', 'lens_serial', 'lens_spec'):
                if values[key] is not None:
                    self.config_store.set(section, key, values[key])
            self.lenses.append(new_id)
        self.lenses.sort(key=self.get_name)

    @staticmethod
    def get_id(model, make, serial):
        lens_id = model or ''
        if make and make not in lens_id:
            lens_id = '({}){}'.format(make, lens_id)
        if serial:
            lens_id = '{}({})'.format(lens_id, serial)
        if lens_id:
            lens_id = lens_id.replace(' ', '')
        return lens_id

    def get_name(self, lens_id):
        section = 'lens ' + lens_id
        name = self.config_store.get(section, 'lens_model') or ''
        make = self.config_store.get(section, 'lens_make') or ''
        if make not in name:
            name = make + ' ' + name
        return name

    def delete_model(self, lens_id):
        if lens_id not in self.lenses:
            return
        self.config_store.remove_section('lens ' + lens_id)
        self.lenses.remove(lens_id)
        self.config_store.set('technical', 'lenses', repr(self.lenses))

    def save_to_image(self, lens_id, image):
        if not lens_id:
            for item in ('lens_model', 'lens_make', 'lens_serial', 'lens_spec'):
                setattr(image.metadata, item, None)
            return
        section = 'lens ' + lens_id
        for item in ('lens_model', 'lens_make', 'lens_serial', 'lens_spec'):
            value = self.config_store.get(section, item) or None
            if item == 'lens_spec' and value and ',' not in value:
                value = ','.join(value.split())
                self.config_store.set(section, item, value)
            setattr(image.metadata, item, value)

    def load_from_image(self, lens_id, image):
        section = 'lens ' + lens_id
        for item in ('lens_model', 'lens_make', 'lens_serial', 'lens_spec'):
            value = getattr(image.metadata, item)
            if value:
                self.config_store.set(section, item, str(value))
        if lens_id not in self.lenses:
            self.lenses.append(lens_id)
        self.lenses.sort(key=self.get_name)
        self.config_store.set('technical', 'lenses', repr(self.lenses))

    def load_from_dialog(self, dialog):
        model = dialog.lens_model.text().strip()
        if not model:
            return None
        min_fl = dialog.lens_spec['min_fl'].get_value()
        if not min_fl:
            return None
        max_fl = dialog.lens_spec['max_fl'].get_value() or min_fl
        min_fl_fn = dialog.lens_spec['min_fl_fn'].get_value() or 0
        max_fl_fn = dialog.lens_spec['max_fl_fn'].get_value() or min_fl_fn
        lens_spec = LensSpec((min_fl, max_fl, min_fl_fn, max_fl_fn))
        make = dialog.lens_make.text().strip()
        serial = dialog.lens_serial.text().strip()
        lens_id = self.get_id(model, make, serial)
        section = 'lens ' + lens_id
        self.config_store.set(section, 'lens_model', model)
        self.config_store.set(section, 'lens_make', make)
        self.config_store.set(section, 'lens_serial', serial)
        self.config_store.set(section, 'lens_spec', str(lens_spec))
        if lens_id not in self.lenses:
            self.lenses.append(lens_id)
        self.lenses.sort(key=self.get_name)
        self.config_store.set('technical', 'lenses', repr(self.lenses))
        return lens_id


class NewLensDialog(QtWidgets.QDialog):
    def __init__(self, images, *arg, **kw):
        super(NewLensDialog, self).__init__(*arg, **kw)
        self.setWindowTitle(translate('TechnicalTab', 'Photini: define lens'))
        self.setLayout(QtWidgets.QVBoxLayout())
        # main dialog area
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.layout().addWidget(scroll_area)
        panel = QtWidgets.QWidget()
        panel.setLayout(QtWidgets.QFormLayout())
        panel.layout().setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        # ok & cancel buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout().addWidget(button_box)
        # model
        self.lens_model = QtWidgets.QLineEdit()
        self.lens_model.setMinimumWidth(
            width_for_text(self.lens_model, 'x' * 35))
        panel.layout().addRow(
            translate('TechnicalTab', 'Model name'), self.lens_model)
        # maker
        self.lens_make = QtWidgets.QLineEdit()
        panel.layout().addRow(
            translate('TechnicalTab', "Maker's name"), self.lens_make)
        # serial number
        self.lens_serial = QtWidgets.QLineEdit()
        panel.layout().addRow(
            translate('TechnicalTab', 'Serial number'), self.lens_serial)
        ## spec has four items
        self.lens_spec = {}
        # min focal length
        self.lens_spec['min_fl'] = DoubleSpinBox()
        self.lens_spec['min_fl'].setMinimum(0.0)
        self.lens_spec['min_fl'].setSingleStep(1.0)
        self.lens_spec['min_fl'].setSuffix(' mm')
        panel.layout().addRow(translate('TechnicalTab', 'Minimum focal length'),
                              self.lens_spec['min_fl'])
        # min focal length aperture
        self.lens_spec['min_fl_fn'] = DoubleSpinBox()
        self.lens_spec['min_fl_fn'].setMinimum(0.0)
        self.lens_spec['min_fl_fn'].setPrefix('ƒ/')
        panel.layout().addRow(
            translate('TechnicalTab', 'Aperture at min. focal length'),
            self.lens_spec['min_fl_fn'])
        # max focal length
        self.lens_spec['max_fl'] = DoubleSpinBox()
        self.lens_spec['max_fl'].setMinimum(0.0)
        self.lens_spec['max_fl'].setSingleStep(1.0)
        self.lens_spec['max_fl'].setSuffix(' mm')
        panel.layout().addRow(translate('TechnicalTab', 'Maximum focal length'),
                              self.lens_spec['max_fl'])
        # max focal length aperture
        self.lens_spec['max_fl_fn'] = DoubleSpinBox()
        self.lens_spec['max_fl_fn'].setMinimum(0.0)
        self.lens_spec['max_fl_fn'].setPrefix('ƒ/')
        panel.layout().addRow(
            translate('TechnicalTab', 'Aperture at max. focal length'),
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
                    self.lens_spec[key].set_value(spec[key])


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

class TabWidget(QtWidgets.QWidget):
    @staticmethod
    def tab_name():
        return translate('TechnicalTab', '&Technical metadata')

    def __init__(self, image_list, *arg, **kw):
        super(TabWidget, self).__init__(*arg, **kw)
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.image_list = image_list
        self.setLayout(QtWidgets.QHBoxLayout())
        self.widgets = {}
        self.date_widget = {}
        self.link_widget = {}
        # store lens data in another object
        self.lens_data = LensData()
        # date and time
        date_group = QtWidgets.QGroupBox(
            translate('TechnicalTab', 'Date and time'))
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
            translate('TechnicalTab', "Link 'taken' and 'digitised'"))
        self.link_widget['digitised', 'modified'].setText(
            translate('TechnicalTab', "Link 'digitised' and 'modified'"))
        # add to layout
        date_group.layout().addRow(translate('TechnicalTab', 'Taken'),
                                   self.date_widget['taken'])
        date_group.layout().addRow('', self.link_widget['taken', 'digitised'])
        date_group.layout().addRow(translate('TechnicalTab', 'Digitised'),
                                   self.date_widget['digitised'])
        date_group.layout().addRow('', self.link_widget['digitised', 'modified'])
        date_group.layout().addRow(translate('TechnicalTab', 'Modified'),
                                   self.date_widget['modified'])
        # offset
        self.offset_widget = OffsetWidget()
        self.offset_widget.apply_offset.connect(self.apply_offset)
        date_group.layout().addRow(
            translate('TechnicalTab', 'Adjust times'), self.offset_widget)
        self.layout().addWidget(date_group)
        # other
        other_group = QtWidgets.QGroupBox(translate('TechnicalTab', 'Other'))
        other_group.setLayout(QtWidgets.QFormLayout())
        other_group.layout().setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        # orientation
        self.widgets['orientation'] = DropdownEdit()
        self.widgets['orientation'].add_item(
            translate('TechnicalTab', 'normal'), 1)
        self.widgets['orientation'].add_item(
            translate('TechnicalTab', 'rotate -90'), 6)
        self.widgets['orientation'].add_item(
            translate('TechnicalTab', 'rotate +90'), 8)
        self.widgets['orientation'].add_item(
            translate('TechnicalTab', 'rotate 180'), 3)
        self.widgets['orientation'].add_item(
            translate('TechnicalTab', 'reflect left-right'), 2)
        self.widgets['orientation'].add_item(
            translate('TechnicalTab', 'reflect top-bottom'), 4)
        self.widgets['orientation'].add_item(
            translate('TechnicalTab', 'reflect tr-bl'), 5)
        self.widgets['orientation'].add_item(
            translate('TechnicalTab', 'reflect tl-br'), 7)
        self.widgets['orientation'].new_value.connect(self.new_orientation)
        other_group.layout().addRow(translate(
            'TechnicalTab', 'Orientation'), self.widgets['orientation'])
        # lens model
        self.widgets['lens_model'] = DropdownEdit()
        self.widgets['lens_model'].setMinimumWidth(
            width_for_text(self.widgets['lens_model'], 'x' * 30))
        self.widgets['lens_model'].setContextMenuPolicy(Qt.CustomContextMenu)
        self.widgets['lens_model'].add_item(translate(
            'TechnicalTab', '<define new lens>'), '<add lens>')
        for lens_id in self.lens_data.lenses:
            self.widgets['lens_model'].add_item(
                self.lens_data.get_name(lens_id), lens_id)
        self.widgets['lens_model'].new_value.connect(self.new_lens_model)
        self.widgets['lens_model'].customContextMenuRequested.connect(
            self.remove_lens_model)
        other_group.layout().addRow(translate(
            'TechnicalTab', 'Lens model'), self.widgets['lens_model'])
        # lens specification
        self.widgets['lens_spec'] = LensSpecWidget()
        other_group.layout().addRow(translate(
            'TechnicalTab', 'Lens details'), self.widgets['lens_spec'])
        # focal length
        self.widgets['focal_length'] = DoubleSpinBox()
        self.widgets['focal_length'].setMinimum(0.0)
        self.widgets['focal_length'].setSuffix(' mm')
        self.widgets['focal_length'].new_value.connect(self.new_focal_length)
        other_group.layout().addRow(translate(
            'TechnicalTab', 'Focal length'), self.widgets['focal_length'])
        # 35mm equivalent focal length
        self.widgets['focal_length_35'] = IntSpinBox()
        self.widgets['focal_length_35'].setMinimum(0)
        self.widgets['focal_length_35'].setSuffix(' mm')
        self.widgets['focal_length_35'].new_value.connect(self.new_focal_length_35)
        other_group.layout().addRow(translate(
            'TechnicalTab', '35mm equiv'), self.widgets['focal_length_35'])
        # aperture
        self.widgets['aperture'] = DoubleSpinBox()
        self.widgets['aperture'].setMinimum(0.0)
        self.widgets['aperture'].setPrefix('ƒ/')
        self.widgets['aperture'].new_value.connect(self.new_aperture)
        other_group.layout().addRow(translate(
            'TechnicalTab', 'Aperture'), self.widgets['aperture'])
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
        self._update_links()

    @QtCore.pyqtSlot(six.text_type)
    @catch_all
    def new_link(self, master):
        slave = self._master_slave[master]
        if self.link_widget[master, slave].isChecked():
            for image in self.image_list.get_selected_images():
                temp = dict(getattr(image.metadata, 'date_' + master) or {})
                self._set_date_value(image, slave, temp)
            self._update_datetime()
            self._update_links()
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
        current_lens_id = self.widgets['lens_model'].get_value()
        menu = QtWidgets.QMenu()
        for lens_id in self.lens_data.lenses:
            if lens_id == current_lens_id:
                continue
            action = QtWidgets.QAction(translate(
                'TechnicalTab', 'Remove lens "{}"').format(
                    self.lens_data.get_name(lens_id)), self)
            action.setData(lens_id)
            menu.addAction(action)
        if menu.isEmpty():
            # no deletable lenses
            return
        action = menu.exec_(self.widgets['lens_model'].mapToGlobal(pos))
        if not action:
            return
        lens_id = action.data()
        self.lens_data.delete_model(lens_id)
        self.widgets['lens_model'].remove_item(lens_id)

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
        self._update_lens_spec(adjust_afl=True)

    def _add_lens_model(self):
        dialog = NewLensDialog(
            self.image_list.get_selected_images(), parent=self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        lens_id = self.lens_data.load_from_dialog(dialog)
        if not lens_id:
            return
        if not self.widgets['lens_model'].known_value(lens_id):
            self.widgets['lens_model'].add_item(
                self.lens_data.get_name(lens_id), lens_id)

    @QtCore.pyqtSlot(object)
    @catch_all
    def new_aperture(self, value):
        for image in self.image_list.get_selected_images():
            image.metadata.aperture = value
        self._update_aperture()

    @QtCore.pyqtSlot(object)
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

    @QtCore.pyqtSlot(object)
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
                    self.date_widget[slave].set_enabled(True)
                    break
            else:
                self.link_widget[master, slave].setChecked(True)
                self.date_widget[slave].set_enabled(False)

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
        make = images[0].metadata.lens_make
        serial = images[0].metadata.lens_serial
        for image in images[1:]:
            if (image.metadata.lens_model != model or
                    image.metadata.lens_make != make or
                    image.metadata.lens_serial != serial):
                # multiple values
                self.widgets['lens_model'].set_multiple()
                self.widgets['lens_model'].setToolTip('')
                return
        lens_id = self.lens_data.get_id(model, make, serial)
        if not self.widgets['lens_model'].known_value(lens_id):
            # new lens
            self.lens_data.load_from_image(lens_id, images[0])
            self.widgets['lens_model'].add_item(
                self.lens_data.get_name(lens_id), lens_id)
        self.widgets['lens_model'].set_value(lens_id)
        tool_tip = ''
        if serial:
            tool_tip = 'Serial number: ' + serial
        self.widgets['lens_model'].setToolTip(tool_tip)

    def _update_lens_spec(self, adjust_afl=False):
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
        if not (adjust_afl and spec):
            return
        make_changes = False
        for image in images:
            new_aperture = image.metadata.aperture or 0
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
                    self,
                    translate('TechnicalTab', 'Update aperture & focal length'),
                    translate('TechnicalTab', 'Adjust image aperture and focal'
                              ' length to agree with lens specification?'),
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
        values = []
        for image in images:
            value = image.metadata.aperture
            if value not in values:
                values.append(value)
        if len(values) > 1:
            self.widgets['aperture'].set_multiple(choices=values)
        else:
            self.widgets['aperture'].set_value(values[0])

    def _update_focal_length(self):
        images = self.image_list.get_selected_images()
        if not images:
            return
        values = []
        for image in images:
            value = image.metadata.focal_length
            if value not in values:
                values.append(value)
        if len(values) > 1:
            self.widgets['focal_length'].set_multiple(choices=values)
        else:
            self.widgets['focal_length'].set_value(values[0])

    def _update_focal_length_35(self):
        images = self.image_list.get_selected_images()
        if not images:
            return
        self.widgets['focal_length_35'].set_faint(False)
        # display real value if it exists
        values = []
        for image in images:
            value = image.metadata.focal_length_35
            if value not in values:
                values.append(value)
        if len(values) > 1:
            self.widgets['focal_length_35'].set_multiple(choices=values)
        else:
            self.widgets['focal_length_35'].set_value(values[0])
        if values[0]:
            return
        # otherwise display calculated value
        values = []
        for image in images:
            value = self.calc_35(image.metadata)
            if value not in values:
                values.append(value)
        if len(values) > 1:
            self.widgets['focal_length_35'].set_multiple(choices=values)
        elif values[0]:
            self.widgets['focal_length_35'].set_faint(True)
            self.widgets['focal_length_35'].set_value(values[0])

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
        if md.camera_model:
            crop_factor = self.config_store.get('crop factor', md.camera_model)
            if crop_factor:
                return eval(crop_factor)
        if not all((md.resolution_x, md.resolution_y,
                    md.dimension_x, md.dimension_y)):
            return None
        if (md.resolution_x <= 0 or md.resolution_y <= 0 or
                md.dimension_x <= 0 or md.dimension_y <= 0):
            return None
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
        crop_factor = round(43.27 / d, 4)
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
