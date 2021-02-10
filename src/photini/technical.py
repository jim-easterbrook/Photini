# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-21  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from photini.metadata import CameraModel, LensModel, LensSpec
from photini.pyqt import (
    catch_all, ComboBox, multiple, multiple_values, Qt, QtCore, QtGui,
    QtSignal, QtSlot, QtWidgets, scale_font, set_symbol_font, Slider,
    SquareButton, using_pyside2, width_for_text)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class DropdownEdit(ComboBox):
    extend_list = QtSignal()
    new_value = QtSignal(object)

    def __init__(self, extendable=False, **kw):
        super(DropdownEdit, self).__init__(**kw)
        if extendable:
            self.setContextMenuPolicy(Qt.CustomContextMenu)
            self.customContextMenuRequested.connect(self.remove_from_list)
            self.addItem(
                translate('TechnicalTab', '<new>'), self.extend_list.emit)
        self.addItem('', None)
        self.first_value_idx = self.count()
        self.addItem(multiple_values(), '<multiple>')
        self.setItemData(
            self.count() - 1, self.itemData(self.count() - 1), Qt.UserRole - 1)
        self.currentIndexChanged.connect(self.current_index_changed)

    @QtSlot(QtCore.QPoint)
    @catch_all
    def remove_from_list(self, pos):
        current_value = self.itemData(self.currentIndex())
        menu = QtWidgets.QMenu()
        for name, value in self.get_items():
            if value == current_value:
                continue
            action = QtWidgets.QAction(
                translate('TechnicalTab', 'Remove "{}"').format(name),
                parent=self)
            action.setData(value)
            menu.addAction(action)
        if menu.isEmpty():
            return
        action = menu.exec_(self.mapToGlobal(pos))
        if not action:
            return
        self.remove_item(action.data())

    @QtSlot(int)
    @catch_all
    def current_index_changed(self, idx):
        value = self.itemData(idx)
        if callable(value):
            (value)()
        else:
            self.new_value.emit(value)

    def add_item(self, text, value, ordered=True):
        blocked = self.blockSignals(True)
        position = self.count() - 1
        if ordered:
            for n in range(self.first_value_idx, self.count() - 1):
                if self.itemText(n).lower() > text.lower():
                    position = n
                    break
        self.insertItem(position, text, value)
        self.set_dropdown_width()
        self.blockSignals(blocked)

    def remove_item(self, value):
        blocked = self.blockSignals(True)
        self.removeItem(self.find_data(value))
        self.set_dropdown_width()
        self.blockSignals(blocked)

    def known_value(self, value):
        if not value:
            return True
        return self.find_data(value) >= 0

    def set_value(self, value):
        blocked = self.blockSignals(True)
        self.setCurrentIndex(self.find_data(value))
        self.blockSignals(blocked)

    def find_data(self, value):
        # Qt's findData only works for simple types
        for n in range(self.count()):
            if self.itemData(n) == value:
                return n
        return -1

    def get_items(self):
        for n in range(self.first_value_idx, self.count() - 1):
            yield self.itemText(n), self.itemData(n)

    def set_multiple(self):
        blocked = self.blockSignals(True)
        self.setCurrentIndex(self.count() - 1)
        self.blockSignals(blocked)


class CameraList(DropdownEdit):
    def __init__(self, **kw):
        super(CameraList, self).__init__(**kw)
        self.config_store = QtWidgets.QApplication.instance().config_store
        # read cameras from config, updating if neccessary
        camera_names = []
        for section in self.config_store.config.sections():
            if not section.startswith('camera '):
                continue
            camera_names.append(section[7:])
        for camera_name in camera_names:
            section = 'camera ' + camera_name
            camera = {}
            for key in 'make', 'model', 'serial_no':
                camera[key] = self.config_store.get(section, key)
            camera = CameraModel(camera)
            name = camera.get_name()
            if name != camera_name:
                self.config_store.remove_section(section)
            self.add_item(camera)

    def add_item(self, camera):
        name = camera.get_name()
        section = 'camera ' + name
        for key, value in camera.items():
            if value:
                self.config_store.set(section, key, value)
        super(CameraList, self).add_item(name, camera, ordered=True)

    def remove_item(self, camera):
        self.config_store.remove_section('camera ' + camera.get_name())
        super(CameraList, self).remove_item(camera)

    def set_value(self, camera):
        if not self.known_value(camera):
            self.add_item(camera)
        super(CameraList, self).set_value(camera)


class LensList(DropdownEdit):
    def __init__(self, **kw):
        super(LensList, self).__init__(**kw)
        self.config_store = QtWidgets.QApplication.instance().config_store
        # read lenses from config, updating if neccessary
        self.config_store.delete('technical', 'lenses')
        lens_names = []
        for section in self.config_store.config.sections():
            if not section.startswith('lens '):
                continue
            lens_names.append(section[5:])
        for lens_name in lens_names:
            section = 'lens ' + lens_name
            lens_model = {}
            for old_key, new_key in (('lens_make', 'make'),
                                     ('lens_model', 'model'),
                                     ('lens_serial', 'serial_no')):
                lens_model[new_key] = self.config_store.get(section, new_key)
                if not lens_model[new_key]:
                    lens_model[new_key] = self.config_store.get(section, old_key)
                self.config_store.delete(section, old_key)
            lens_model = LensModel(lens_model)
            lens_spec = LensSpec(self.config_store.get(section, 'lens_spec'))
            if lens_model.get_name() != lens_name:
                self.config_store.remove_section(section)
            self.add_item((lens_model, lens_spec))

    def add_item(self, value):
        lens_model, lens_spec = value
        name = lens_model.get_name()
        section = 'lens ' + name
        for k, v in lens_model.items():
            if v:
                self.config_store.set(section, k, v)
        if lens_spec:
            self.config_store.set(section, 'lens_spec', str(lens_spec))
        super(LensList, self).add_item(name, value, ordered=True)

    def remove_item(self, value):
        lens_model, lens_spec = value
        self.config_store.remove_section('lens ' + lens_model.get_name())
        super(LensList, self).remove_item(value)

    def set_value(self, value):
        if not self.known_value(value):
            self.add_item(value)
        super(LensList, self).set_value(value)


class AugmentSpinBox(object):
    new_value = QtSignal(object)

    def init_augment(self):
        self.set_value(None)
        self.editingFinished.connect(self.editing_finished)

    class ContextAction(QtWidgets.QAction):
        def __init__(self, value, *arg, **kw):
            super(AugmentSpinBox.ContextAction, self).__init__(*arg, **kw)
            self.setData(value)
            self.triggered.connect(self.set_value)

        @QtSlot()
        @catch_all
        def set_value(self):
            self.parent().setValue(self.data())

    def context_menu_event(self):
        if self.specialValueText() and self.choices:
            QtCore.QTimer.singleShot(0, self.extend_context_menu)

    @QtSlot()
    @catch_all
    def extend_context_menu(self):
        menu = self.findChild(QtWidgets.QMenu)
        if not menu:
            return
        sep = menu.insertSeparator(menu.actions()[0])
        for suggestion in self.choices:
            menu.insertAction(sep, self.ContextAction(
                suggestion, text=self.textFromValue(suggestion), parent=self))

    def clear_special_value(self):
        if self.specialValueText():
            self.set_value(self.default_value)
            self.selectAll()

    @QtSlot()
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
        self.init_augment()
        self.setSingleStep(1)
        lim = (2 ** 31) - 1
        self.setRange(-lim, lim)
        self.setButtonSymbols(self.NoButtons)

    @catch_all
    def contextMenuEvent(self, event):
        self.context_menu_event()
        return super(IntSpinBox, self).contextMenuEvent(event)

    @catch_all
    def keyPressEvent(self, event):
        self.clear_special_value()
        return super(IntSpinBox, self).keyPressEvent(event)

    @catch_all
    def stepBy(self, steps):
        self.clear_special_value()
        return super(IntSpinBox, self).stepBy(steps)

    @catch_all
    def fixup(self, text):
        if not self.cleanText():
            # user has deleted the value
            self.set_value(None)
            return ''
        return super(IntSpinBox, self).fixup(text)

    def set_faint(self, faint):
        if faint:
            self.setStyleSheet('QAbstractSpinBox {font-weight:200}')
        else:
            self.setStyleSheet('QAbstractSpinBox {font-weight:normal}')


class DoubleSpinBox(QtWidgets.QDoubleSpinBox, AugmentSpinBox):
    def __init__(self, *arg, **kw):
        self.default_value = 0
        self.multiple = multiple_values()
        super(DoubleSpinBox, self).__init__(*arg, **kw)
        self.init_augment()
        self.setSingleStep(0.1)
        self.setDecimals(4)
        lim = (2 ** 31) - 1
        self.setRange(-lim, lim)
        self.setButtonSymbols(self.NoButtons)

    @catch_all
    def contextMenuEvent(self, event):
        self.context_menu_event()
        return super(DoubleSpinBox, self).contextMenuEvent(event)

    @catch_all
    def keyPressEvent(self, event):
        self.clear_special_value()
        return super(DoubleSpinBox, self).keyPressEvent(event)

    @catch_all
    def stepBy(self, steps):
        self.clear_special_value()
        return super(DoubleSpinBox, self).stepBy(steps)

    @catch_all
    def fixup(self, text):
        if not self.cleanText():
            # user has deleted the value
            self.set_value(None)
            return ''
        return super(DoubleSpinBox, self).fixup(text)

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
        self.default_value = QtCore.QDateTime(
            QtCore.QDate.currentDate(), QtCore.QTime())
        self.multiple = multiple_values()
        # rename some methods for compatibility with AugmentSpinBox
        self.minimum = self.minimumDateTime
        self.setValue = self.setDateTime
        self.textFromValue = self.textFromDateTime
        self.value = self.dateTime
        super(DateTimeEdit, self).__init__(*arg, **kw)
        self.init_augment()
        self.setCalendarPopup(True)
        self.setCalendarWidget(CalendarWidget())
        self.precision = 1
        self.set_precision(7)

    @catch_all
    def contextMenuEvent(self, event):
        self.context_menu_event()
        return super(DateTimeEdit, self).contextMenuEvent(event)

    @catch_all
    def keyPressEvent(self, event):
        self.clear_special_value()
        return super(DateTimeEdit, self).keyPressEvent(event)

    @catch_all
    def stepBy(self, steps):
        self.clear_special_value()
        return super(DateTimeEdit, self).stepBy(steps)

    def clear_special_value(self):
        if self.specialValueText():
            self.set_value(self.default_value)
            self.setSelectedSection(self.YearSection)

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

    @QtSlot(int)
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
        self.init_augment()
        self.setRange(-14 * 60, 15 * 60)
        self.setSingleStep(15)
        self.setWrapping(True)

    @catch_all
    def contextMenuEvent(self, event):
        self.context_menu_event()
        return super(TimeZoneWidget, self).contextMenuEvent(event)

    @catch_all
    def keyPressEvent(self, event):
        self.clear_special_value()
        return super(TimeZoneWidget, self).keyPressEvent(event)

    @catch_all
    def stepBy(self, steps):
        self.clear_special_value()
        return super(TimeZoneWidget, self).stepBy(steps)

    @catch_all
    def fixup(self, text):
        if not self.cleanText():
            # user has deleted the value
            self.set_value(None)
            return ''
        return super(TimeZoneWidget, self).fixup(text)

    @catch_all
    def sizeHint(self):
        size = super(TimeZoneWidget, self).sizeHint()
        if not self.is_multiple():
            self.setFixedSize(size)
        return size

    @catch_all
    def validate(self, text, pos):
        if re.match(r'[+-]?\d{1,2}(:\d{0,2})?$', text):
            return QtGui.QValidator.Acceptable, text, pos
        if re.match(r'[+-]?$', text):
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


class PrecisionSlider(Slider):
    value_changed = QtSignal(int)

    def __init__(self, *arg, **kw):
        super(PrecisionSlider, self).__init__(*arg, **kw)
        self.valueChanged.connect(self._value_changed)

    def _value_changed(self, value):
        if value >= 4:
            value += 1
        self.value_changed.emit(value)

    def get_value(self):
        value = super(PrecisionSlider, self).get_value()
        if value >= 4:
            value += 1
        return value

    def set_value(self, value):
        if value is not None and value >= 5:
            value -= 1
        super(PrecisionSlider, self).set_value(value)


class DateAndTimeWidget(QtWidgets.QGridLayout):
    new_value = QtSignal(str, dict)

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
        self.members['precision'] = PrecisionSlider(Qt.Horizontal)
        self.members['precision'].setRange(1, 6)
        self.members['precision'].setValue(6)
        self.members['precision'].setPageStep(1)
        self.addWidget(self.members['precision'], 1, 1)
        # connections
        self.members['precision'].value_changed.connect(
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
                if using_pyside2:
                    new_value[key] = new_value[key].toPython()
                else:
                    new_value[key] = new_value[key].toPyDateTime()
        return new_value

    @QtSlot()
    @catch_all
    def editing_finished(self):
        self.new_value.emit(self.name, self.get_value())


class OffsetWidget(QtWidgets.QWidget):
    apply_offset = QtSignal(timedelta, object)

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
        add_button = SquareButton(chr(0x002b))
        add_button.setStyleSheet('QPushButton {padding: 0px}')
        set_symbol_font(add_button)
        scale_font(add_button, 170)
        add_button.clicked.connect(self.add)
        self.layout().addWidget(add_button)
        # subtract offset button
        sub_button = SquareButton(chr(0x2212))
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

    @QtSlot()
    @catch_all
    def new_value(self):
        value = self.offset.time()
        value = (value.hour(), value.minute(), value.second(),
                 self.time_zone.get_value())
        self.config_store.set('technical', 'offset', str(value))

    @QtSlot()
    @catch_all
    def add(self):
        self.do_inc(False)

    @QtSlot()
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


class NewItemDialog(QtWidgets.QDialog):
    def __init__(self, *arg, **kw):
        super(NewItemDialog, self).__init__(*arg, **kw)
        self.setLayout(QtWidgets.QVBoxLayout())
        # main dialog area
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.layout().addWidget(scroll_area)
        self.panel = QtWidgets.QWidget()
        self.panel.setLayout(QtWidgets.QFormLayout())
        self.panel.layout().setFieldGrowthPolicy(
            QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        # ok & cancel buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout().addWidget(button_box)
        # common data items
        self.model_widgets = {}
        for key, label in (
                ('make', translate('TechnicalTab', "Maker's name")),
                ('model', translate('TechnicalTab', 'Model name')),
                ('serial_no', translate('TechnicalTab', 'Serial number')),
                ):
            self.model_widgets[key] = QtWidgets.QLineEdit()
            self.model_widgets[key].setMinimumWidth(
                width_for_text(self.model_widgets[key], 'x' * 35))
            self.panel.layout().addRow(label, self.model_widgets[key])
        # add any other data items
        self.extend_data()
        # add panel to scroll area now its size is known
        scroll_area.setWidget(self.panel)

    def extend_data(self):
        pass

    def get_value(self):
        result = {}
        for key in self.model_widgets:
            result[key] = self.model_widgets[key].text()
        return result


class NewCameraDialog(NewItemDialog):
    def __init__(self, images, *arg, **kw):
        super(NewCameraDialog, self).__init__(*arg, **kw)
        self.setWindowTitle(translate('TechnicalTab', 'Photini: define camera'))
        # fill in any values we can from existing metadata
        for image in images:
            camera = image.metadata.camera_model
            for key in self.model_widgets:
                if camera[key]:
                    self.model_widgets[key].setText(camera[key])


class NewLensDialog(NewItemDialog):
    def __init__(self, images, *arg, **kw):
        super(NewLensDialog, self).__init__(*arg, **kw)
        self.setWindowTitle(translate('TechnicalTab', 'Photini: define lens'))
        # fill in any values we can from existing metadata
        for image in images:
            model = image.metadata.lens_model
            for key in self.model_widgets:
                if model and model[key]:
                    self.model_widgets[key].setText(model[key])
            spec = image.metadata.lens_spec
            for key in self.lens_spec:
                if spec and spec[key]:
                    self.lens_spec[key].set_value(spec[key])

    def extend_data(self):
        # add lens spec
        self.lens_spec = {}
        for key, label in (
                ('min_fl', translate('TechnicalTab', 'Minimum focal length')),
                ('min_fl_fn',
                 translate('TechnicalTab', 'Aperture at min. focal length')),
                ('max_fl', translate('TechnicalTab', 'Maximum focal length')),
                ('max_fl_fn',
                 translate('TechnicalTab', 'Aperture at max. focal length')),
                ):
            self.lens_spec[key] = DoubleSpinBox()
            self.lens_spec[key].setMinimum(0.0)
            if key.endswith('_fn'):
                self.lens_spec[key].setPrefix('ƒ/')
            else:
                self.lens_spec[key].setSingleStep(1.0)
                self.lens_spec[key].setSuffix(' mm')
            self.panel.layout().addRow(label, self.lens_spec[key])

    def get_value(self):
        lens_model = super(NewLensDialog, self).get_value()
        lens_model = LensModel(lens_model) or None
        min_fl = self.lens_spec['min_fl'].get_value() or 0
        max_fl = self.lens_spec['max_fl'].get_value() or min_fl
        min_fl_fn = self.lens_spec['min_fl_fn'].get_value() or 0
        max_fl_fn = self.lens_spec['max_fl_fn'].get_value() or min_fl_fn
        lens_spec = LensSpec((min_fl, max_fl, min_fl_fn, max_fl_fn)) or None
        return lens_model, lens_spec


class DateLink(QtWidgets.QCheckBox):
    new_link = QtSignal(str)

    def __init__(self, name, *arg, **kw):
        super(DateLink, self).__init__(*arg, **kw)
        self.name = name
        self.clicked.connect(self._clicked)

    @QtSlot()
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
            translate('TechnicalTab', 'normal'), 1, ordered=False)
        self.widgets['orientation'].add_item(
            translate('TechnicalTab', 'rotate -90'), 6, ordered=False)
        self.widgets['orientation'].add_item(
            translate('TechnicalTab', 'rotate +90'), 8, ordered=False)
        self.widgets['orientation'].add_item(
            translate('TechnicalTab', 'rotate 180'), 3, ordered=False)
        self.widgets['orientation'].add_item(
            translate('TechnicalTab', 'reflect left-right'), 2, ordered=False)
        self.widgets['orientation'].add_item(
            translate('TechnicalTab', 'reflect top-bottom'), 4, ordered=False)
        self.widgets['orientation'].add_item(
            translate('TechnicalTab', 'reflect tr-bl'), 5, ordered=False)
        self.widgets['orientation'].add_item(
            translate('TechnicalTab', 'reflect tl-br'), 7, ordered=False)
        self.widgets['orientation'].new_value.connect(self.new_orientation)
        other_group.layout().addRow(translate(
            'TechnicalTab', 'Orientation'), self.widgets['orientation'])
        # camera model
        self.widgets['camera_model'] = CameraList(extendable=True)
        self.widgets['camera_model'].setMinimumWidth(
            width_for_text(self.widgets['camera_model'], 'x' * 30))
        self.widgets['camera_model'].new_value.connect(self.new_camera_model)
        self.widgets['camera_model'].extend_list.connect(self.add_camera_model)
        other_group.layout().addRow(translate(
            'TechnicalTab', 'Camera'), self.widgets['camera_model'])
        # lens model
        self.widgets['lens_model'] = LensList(extendable=True)
        self.widgets['lens_model'].setMinimumWidth(
            width_for_text(self.widgets['lens_model'], 'x' * 30))
        self.widgets['lens_model'].new_value.connect(self.new_lens_model)
        self.widgets['lens_model'].extend_list.connect(self.add_lens_model)
        other_group.layout().addRow(translate(
            'TechnicalTab', 'Lens model'), self.widgets['lens_model'])
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

    @QtSlot(timedelta, object)
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

    @QtSlot(str)
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

    @QtSlot(object)
    @catch_all
    def new_orientation(self, value):
        for image in self.image_list.get_selected_images():
            image.metadata.orientation = value
            image.load_thumbnail()
        self._update_orientation()

    @QtSlot()
    @catch_all
    def add_camera_model(self):
        dialog = NewCameraDialog(
            self.image_list.get_selected_images(), parent=self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            value = dialog.get_value()
            if value:
                self.new_camera_model(value)
                return
        self._update_camera_model()

    @QtSlot(object)
    @catch_all
    def new_camera_model(self, value):
        delete_makernote = 'ask'
        for image in self.image_list.get_selected_images():
            if not image.metadata.camera_change_ok(value):
                if delete_makernote == 'ask':
                    msg = QtWidgets.QMessageBox(parent=self)
                    msg.setWindowTitle(translate(
                        'TechnicalTab', 'Photini: maker name change'))
                    msg.setText(translate(
                        'TechnicalTab', '<h3>Changing maker name will'
                        ' invalidate Exif makernote information.</h3>'))
                    msg.setInformativeText(translate(
                        'TechnicalTab',
                        'Do you want to delete the Exif makernote?'))
                    msg.setIcon(msg.Warning)
                    msg.setStandardButtons(msg.YesToAll | msg.NoToAll)
                    msg.setDefaultButton(msg.NoToAll)
                    delete_makernote = msg.exec_() == msg.YesToAll
                if delete_makernote:
                    image.metadata.set_delete_makernote()
            image.metadata.camera_model = value
        self._update_camera_model()

    @QtSlot()
    @catch_all
    def add_lens_model(self):
        dialog = NewLensDialog(
            self.image_list.get_selected_images(), parent=self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            value = dialog.get_value()
            if value[0]:
                self.new_lens_model(value)
                return
        self._update_lens_model()

    @QtSlot(object)
    @catch_all
    def new_lens_model(self, value):
        if value:
            lens_model, lens_spec = value
        else:
            lens_model, lens_spec = None, None
        for image in self.image_list.get_selected_images():
            image.metadata.lens_model = lens_model
            image.metadata.lens_spec = lens_spec
        self._update_lens_model()
        self._update_lens_spec()

    @QtSlot(object)
    @catch_all
    def new_aperture(self, value):
        for image in self.image_list.get_selected_images():
            image.metadata.aperture = value
        self._update_aperture()

    @QtSlot(object)
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

    @QtSlot(object)
    @catch_all
    def new_focal_length_35(self, value):
        for image in self.image_list.get_selected_images():
            image.metadata.focal_length_35 = value
            self.set_crop_factor(image.metadata)
        self._update_focal_length()
        self._update_focal_length_35()

    @QtSlot(str, dict)
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

    def _update_camera_model(self):
        images = self.image_list.get_selected_images()
        if not images:
            return
        value = images[0].metadata.camera_model
        for image in images[1:]:
            if image.metadata.camera_model != value:
                self.widgets['camera_model'].set_multiple()
                return
        self.widgets['camera_model'].set_value(value)

    def _update_lens_model(self):
        images = self.image_list.get_selected_images()
        if not images:
            return
        self.widgets['lens_model'].setToolTip('')
        value = images[0].metadata.lens_model, images[0].metadata.lens_spec
        for image in images[1:]:
            if (image.metadata.lens_model, image.metadata.lens_spec) != value:
                # multiple values
                self.widgets['lens_model'].set_multiple()
                return
        lens_model, lens_spec = value
        if lens_spec and not lens_model:
            lens_model = '{}'.format(float(lens_spec['min_fl']) or '')
            if lens_spec['max_fl'] != lens_spec['min_fl']:
                lens_model += '-{}'.format(float(lens_spec['max_fl']) or '')
            lens_model += ' mm'
            if lens_spec['min_fl_fn']:
                lens_model += ' 1:{}'.format(float(lens_spec['min_fl_fn']) or '')
            if lens_spec['max_fl_fn'] != lens_spec['min_fl_fn']:
                lens_model += '-{}'.format(float(lens_spec['max_fl_fn']) or '')
            lens_model = LensModel({'model': lens_model})
            value = lens_model, lens_spec
        if not lens_model:
            value = None
        self.widgets['lens_model'].set_value(value)
        if not lens_spec:
            lens_spec = LensSpec(None)
        tool_tip = ('<table><tr><th></th><th width="70">{th_min}</th>'
                    '<th width="70">{th_max}</th></tr>'
                    '<tr><th align="right">{th_fl}</th>'
                    '<td align="center">{min_fl}</td>'
                    '<td align="center">{max_fl}</td></tr>'
                    '<tr><th align="right">{th_ap}</th>'
                    '<td align="center">{min_fl_fn}</td>'
                    '<td align="center">{max_fl_fn}</td></tr></table>')
        tool_tip = tool_tip.format(
            th_min=translate('TechnicalTab', 'min'),
            th_max=translate('TechnicalTab', 'max'),
            th_fl=translate('TechnicalTab', 'Focal length'),
            th_ap=translate('TechnicalTab', 'Max aperture'),
            **dict([(x, float(y) or '') for (x, y) in lens_spec.items()]))
        self.widgets['lens_model'].setToolTip(tool_tip)

    def _update_lens_spec(self):
        images = self.image_list.get_selected_images()
        if not images:
            return
        spec = images[0].metadata.lens_spec
        if not spec:
            return
        for image in images[1:]:
            if image.metadata.lens_spec != spec:
                # multiple values
                return
        make_changes = False
        for image in images:
            new_aperture = image.metadata.aperture or 0
            new_fl = image.metadata.focal_length or 0
            if new_fl <= spec['min_fl']:
                new_fl = spec['min_fl']
                new_aperture = max(new_aperture, spec['min_fl_fn'])
            elif new_fl >= spec['max_fl']:
                new_fl = spec['max_fl']
                new_aperture = max(new_aperture, spec['max_fl_fn'])
            else:
                new_aperture = max(new_aperture,
                                   min(spec['min_fl_fn'], spec['max_fl_fn']))
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
            self.config_store.set(
                'crop factor', md.camera_model.get_name(inc_serial=False),
                'None')
        elif md.focal_length:
            crop_factor = float(md.focal_length_35) / md.focal_length
            self.config_store.set(
                'crop factor', md.camera_model.get_name(inc_serial=False),
                repr(crop_factor))

    def get_crop_factor(self, md):
        if md.camera_model:
            crop_factor = self.config_store.get(
                'crop factor', md.camera_model.get_name(inc_serial=False))
            if crop_factor:
                return eval(crop_factor)
        if not (md.resolution and md.sensor_size):
            return None
        if (md.resolution['x'] <= 0 or md.resolution['y'] <= 0 or
                md.sensor_size['x'] <= 0 or md.sensor_size['y'] <= 0):
            return None
        # calculate from image size and resolution
        w = md.sensor_size['x'] / md.resolution['x']
        h = md.sensor_size['y'] / md.resolution['y']
        d = math.sqrt((h ** 2) + (w ** 2))
        if md.resolution['unit'] == 3:
            # unit is cm
            d *= 10.0
        elif md.resolution['unit'] in (None, 1, 2):
            # unit is (assumed to be) inches
            d *= 25.4
        else:
            logger.info('Unknown resolution unit %d', md.resolution['unit'])
            return None
        # 35 mm film diagonal is 43.27 mm
        crop_factor = round(43.27 / d, 4)
        if md.camera_model:
            self.config_store.set(
                'crop factor', md.camera_model.get_name(inc_serial=False),
                str(crop_factor))
        return crop_factor

    def calc_35(self, md, value=None):
        crop_factor = self.get_crop_factor(md)
        value = value or md.focal_length
        if crop_factor and value:
            return int((float(value) * crop_factor) + 0.5)
        return md.focal_length_35

    @QtSlot(list)
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
        self._update_camera_model()
        self._update_lens_model()
        self._update_aperture()
        self._update_focal_length()
        self._update_focal_length_35()
        self.setEnabled(True)
