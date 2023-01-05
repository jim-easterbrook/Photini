# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-22  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from collections import defaultdict
from datetime import datetime, timedelta
import logging
import re

from photini.pyqt import *
from photini.pyqt import set_symbol_font, using_pyside
from photini.types import MD_CameraModel, MD_LensModel
from photini.widgets import DropDownSelector, Slider

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class DropdownEdit(DropDownSelector):
    def __init__(self, key, *arg, **kw):
        super(DropdownEdit, self).__init__(
            key, *arg, extendable=True, ordered=True, **kw)
        self.app = QtWidgets.QApplication.instance()
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    @QtSlot(QtGui.QContextMenuEvent)
    @catch_all
    def contextMenuEvent(self, event):
        menu = QtWidgets.QMenu()
        for n in range(self._last_idx()):
            if n == self.currentIndex():
                continue
            name = self.itemText(n)
            if not name:
                continue
            action = QtGui2.QAction(
                translate('TechnicalTab', 'Remove "{camera_or_lens}"'
                          ).format(camera_or_lens=name),
                parent=self)
            action.setData(self.itemData(n))
            menu.addAction(action)
        if menu.isEmpty():
            return
        action = execute(menu, event.globalPos())
        if not action:
            return
        self.remove_item(action.data())


class CameraList(DropdownEdit):
    def __init__(self, *args, **kwds):
        super(CameraList, self).__init__(*args, **kwds)
        values = [('', None)]
        # read cameras from config, updating if neccessary
        sections = []
        for section in self.app.config_store.config.sections():
            if not section.startswith('camera '):
                continue
            camera = {}
            for key in 'make', 'model', 'serial_no':
                camera[key] = self.app.config_store.get(section, key)
            camera = MD_CameraModel(camera)
            name = camera.get_name()
            if name != section[7:]:
                self.app.config_store.remove_section(section)
            values.append((name, camera))
        self.set_values(values)

    def define_new_value(self):
        dialog = NewCameraDialog(
            self.app.image_list.get_selected_images(), parent=self)
        if execute(dialog) != QtWidgets.QDialog.DialogCode.Accepted:
            return None, None
        camera = MD_CameraModel(dialog.get_value())
        if not camera:
            return None, None
        name = camera.get_name()
        section = 'camera ' + name
        for key, value in camera.items():
            if value:
                self.app.config_store.set(section, key, value)
        return name, camera

    def remove_item(self, camera, **kwds):
        self.app.config_store.remove_section('camera ' + camera.get_name())
        return super(CameraList, self).remove_item(camera, **kwds)

    def data_to_text(self, camera):
        return camera.get_name()


class LensList(DropdownEdit):
    def __init__(self, *args, **kwds):
        super(LensList, self).__init__(*args, **kwds)
        values = [('', None)]
        # read lenses from config, updating if neccessary
        self.app.config_store.delete('technical', 'lenses')
        for section in self.app.config_store.config.sections():
            if not section.startswith('lens '):
                continue
            lens_model = {}
            for old_key, new_key in (('lens_make', 'make'),
                                     ('lens_model', 'model'),
                                     ('lens_serial', 'serial_no'),
                                     ('lens_spec', 'spec')):
                lens_model[new_key] = self.app.config_store.get(section, new_key)
                if not lens_model[new_key]:
                    lens_model[new_key] = self.app.config_store.get(section, old_key)
                self.app.config_store.delete(section, old_key)
            lens_model = MD_LensModel(lens_model)
            name = lens_model.get_name()
            if name != section[5:]:
                self.app.config_store.remove_section(section)
            values.append((name, lens_model))
        self.set_values(values)

    def define_new_value(self):
        dialog = NewLensDialog(
            self.app.image_list.get_selected_images(), parent=self)
        if execute(dialog) != QtWidgets.QDialog.DialogCode.Accepted:
            return None, None
        lens_model = dialog.get_value()
        if not lens_model:
            return None, None
        name = lens_model.get_name()
        section = 'lens ' + name
        for key, value in lens_model.items():
            if value:
                self.app.config_store.set(section, key, str(value))
        return name, lens_model

    def remove_item(self, lens_model, **kwds):
        self.app.config_store.remove_section('lens ' + lens_model.get_name())
        return super(LensList, self).remove_item(lens_model, **kwds)

    def data_to_text(self, lens_model):
        return lens_model.get_name()


class AugmentSpinBox(object):
    new_value = QtSignal(object)

    def __init__(self):
        super(AugmentSpinBox, self).__init__()
        if self.isRightToLeft():
            self.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.set_value(None)
        self.editingFinished.connect(self.editing_finished)

    class ContextAction(QtGui2.QAction):
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

    def fix_up(self):
        if self.cleanText():
            return False
        # user has deleted the value
        self.set_value(None)
        return True

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
        AugmentSpinBox.__init__(self)
        self.setSingleStep(1)
        lim = (2 ** 31) - 1
        self.setRange(-lim, lim)
        self.setButtonSymbols(self.ButtonSymbols.NoButtons)

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
        return self.fix_up() or super(IntSpinBox, self).fixup(text)

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
        AugmentSpinBox.__init__(self)
        self.setSingleStep(0.1)
        self.setDecimals(4)
        lim = (2 ** 31) - 1
        self.setRange(-lim, lim)
        self.setButtonSymbols(self.ButtonSymbols.NoButtons)

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
        return self.fix_up() or super(DoubleSpinBox, self).fixup(text)

    @catch_all
    def textFromValue(self, value):
        # don't use QDoubleSpinBox's fixed number of decimals
        return str(round(float(value), self.decimals()))


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
        AugmentSpinBox.__init__(self)
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
            return QtGui.QValidator.State.Acceptable, text, pos
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
        AugmentSpinBox.__init__(self)
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
        return self.fix_up() or super(TimeZoneWidget, self).fixup(text)

    @catch_all
    def sizeHint(self):
        size = super(TimeZoneWidget, self).sizeHint()
        if not self.is_multiple():
            self.setFixedSize(size)
        return size

    @catch_all
    def validate(self, text, pos):
        if re.match(r'[+-]?\d{1,2}(:\d{0,2})?$', text):
            return QtGui.QValidator.State.Acceptable, text, pos
        if re.match(r'[+-]?$', text):
            return QtGui.QValidator.State.Intermediate, text, pos
        return QtGui.QValidator.State.Invalid, text, pos

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
            QtWidgets.QLabel(translate('TechnicalTab', 'Precision')), 1, 0)
        self.members['precision'] = PrecisionSlider(Qt.Orientation.Horizontal)
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
                if using_pyside:
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
        self.app = QtWidgets.QApplication.instance()
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
        add_button = QtWidgets.QPushButton(chr(0x002b))
        add_button.setStyleSheet('QPushButton {padding: 0px}')
        set_symbol_font(add_button)
        scale_font(add_button, 170)
        add_button.setFixedWidth(self.offset.sizeHint().height())
        add_button.setFixedHeight(self.offset.sizeHint().height())
        add_button.clicked.connect(self.add)
        self.layout().addWidget(add_button)
        # subtract offset button
        sub_button = QtWidgets.QPushButton(chr(0x2212))
        sub_button.setStyleSheet('QPushButton {padding: 0px}')
        set_symbol_font(sub_button)
        scale_font(sub_button, 170)
        sub_button.setFixedWidth(self.offset.sizeHint().height())
        sub_button.setFixedHeight(self.offset.sizeHint().height())
        sub_button.clicked.connect(self.sub)
        self.layout().addWidget(sub_button)
        self.layout().addStretch(1)
        # restore stored values
        value = self.app.config_store.get('technical', 'offset')
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
        self.app.config_store.set('technical', 'offset', value)

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
        self.panel.setLayout(FormLayout())
        # ok & cancel buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
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
            if not model:
                continue
            for key in self.model_widgets:
                if model[key]:
                    self.model_widgets[key].setText(model[key])
            spec = model['spec']
            if not spec:
                continue
            for key in self.lens_spec:
                if spec[key]:
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
        min_fl = self.lens_spec['min_fl'].get_value() or 0
        max_fl = self.lens_spec['max_fl'].get_value() or min_fl
        min_fl_fn = self.lens_spec['min_fl_fn'].get_value() or 0
        max_fl_fn = self.lens_spec['max_fl_fn'].get_value() or min_fl_fn
        lens_model['spec'] = (min_fl, max_fl, min_fl_fn, max_fl_fn)
        return MD_LensModel(lens_model) or None


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

    def __init__(self, *arg, **kw):
        super(TabWidget, self).__init__(*arg, **kw)
        self.app = QtWidgets.QApplication.instance()
        self.setLayout(QtWidgets.QHBoxLayout())
        self.widgets = {}
        self.date_widget = {}
        self.link_widget = {}
        # date and time
        date_group = QtWidgets.QGroupBox(
            translate('TechnicalTab', 'Date and time'))
        date_group.setLayout(FormLayout())
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
        date_group.layout().addRow(translate('TechnicalTab', 'Adjust times'),
                                   self.offset_widget)
        self.layout().addWidget(date_group)
        # other
        other_group = QtWidgets.QGroupBox(translate('TechnicalTab', 'Other'))
        other_group.setLayout(FormLayout())
        # orientation
        self.widgets['orientation'] = DropDownSelector(
            'orientation', values=(
                ('', None),
                (translate('TechnicalTab', 'normal',
                           'orientation dropdown, no transformation'), 1),
                (translate('TechnicalTab', 'rotate -90°',
                           'orientation dropdown'), 6),
                (translate('TechnicalTab', 'rotate +90°',
                           'orientation dropdown'), 8),
                (translate('TechnicalTab', 'rotate 180°',
                           'orientation dropdown'), 3),
                (translate('TechnicalTab', 'reflect left to right',
                           'orientation dropdown, horizontal reflection'), 2),
                (translate('TechnicalTab', 'reflect top to bottom',
                           'orientation dropdown, vertical reflection'), 4),
                (translate('TechnicalTab', 'reflect top right to bottom left',
                           'orientation dropdown, diagonal reflection'), 5),
                (translate('TechnicalTab', 'reflect top left to bottom right',
                           'orientation dropdown, diagonal reflection'), 7)))
        self.widgets['orientation'].new_value.connect(self.new_orientation)
        self.widgets['orientation'].setFocusPolicy(Qt.FocusPolicy.NoFocus)
        other_group.layout().addRow(translate('TechnicalTab', 'Orientation'),
                                    self.widgets['orientation'])
        # camera model
        self.widgets['camera_model'] = CameraList('camera_model')
        self.widgets['camera_model'].setMinimumWidth(
            width_for_text(self.widgets['camera_model'], 'x' * 30))
        self.widgets['camera_model'].new_value.connect(self.new_camera_model)
        other_group.layout().addRow(translate('TechnicalTab', 'Camera'),
                                    self.widgets['camera_model'])
        # lens model
        self.widgets['lens_model'] = LensList('lens_model')
        self.widgets['lens_model'].setMinimumWidth(
            width_for_text(self.widgets['lens_model'], 'x' * 30))
        self.widgets['lens_model'].new_value.connect(self.new_lens_model)
        other_group.layout().addRow(translate('TechnicalTab', 'Lens model'),
                                    self.widgets['lens_model'])
        # focal length
        self.widgets['focal_length'] = DoubleSpinBox()
        self.widgets['focal_length'].setMinimum(0.0)
        self.widgets['focal_length'].setSuffix(' mm')
        self.widgets['focal_length'].new_value.connect(self.new_focal_length)
        other_group.layout().addRow(translate('TechnicalTab', 'Focal length'),
                                    self.widgets['focal_length'])
        # 35mm equivalent focal length
        self.widgets['focal_length_35'] = IntSpinBox()
        self.widgets['focal_length_35'].setMinimum(0)
        self.widgets['focal_length_35'].setSuffix(' mm')
        self.widgets['focal_length_35'].new_value.connect(self.new_focal_length_35)
        other_group.layout().addRow(translate('TechnicalTab', '35mm equiv'),
                                    self.widgets['focal_length_35'])
        # aperture
        self.widgets['aperture'] = DoubleSpinBox()
        self.widgets['aperture'].setMinimum(0.0)
        self.widgets['aperture'].setPrefix('ƒ/')
        self.widgets['aperture'].new_value.connect(self.new_aperture)
        other_group.layout().addRow(translate('TechnicalTab', 'Aperture'),
                                    self.widgets['aperture'])
        self.layout().addWidget(other_group, stretch=1)
        # disable until an image is selected
        self.setEnabled(False)

    _master_slave = {
        'taken'    : 'digitised',
        'digitised': 'modified',
        'modified' : None
        }

    def refresh(self):
        self.new_selection(self.app.image_list.get_selected_images())

    def do_not_close(self):
        return False

    @QtSlot(timedelta, object)
    @catch_all
    def apply_offset(self, offset, tz_offset):
        for image in self.app.image_list.get_selected_images():
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
            for image in self.app.image_list.get_selected_images():
                temp = dict(getattr(image.metadata, 'date_' + master) or {})
                self._set_date_value(image, slave, temp)
            self._update_datetime()
            self._update_links()
        else:
            self.date_widget[slave].set_enabled(True)

    @QtSlot(str, object)
    @catch_all
    def new_orientation(self, key, value):
        for image in self.app.image_list.get_selected_images():
            image.metadata.orientation = value
            image.load_thumbnail()
        self._update_orientation()

    @QtSlot(str, object)
    @catch_all
    def new_camera_model(self, key, value):
        delete_makernote = 'ask'
        for image in self.app.image_list.get_selected_images():
            if not image.metadata.camera_change_ok(value):
                if delete_makernote == 'ask':
                    msg = QtWidgets.QMessageBox(parent=self)
                    msg.setWindowTitle(translate(
                        'TechnicalTab', 'Photini: maker name change'))
                    msg.setText('<h3>{}</h3>'.format(translate(
                        'TechnicalTab', 'Changing maker name will'
                        ' invalidate Exif makernote information.')))
                    msg.setInformativeText(translate(
                        'TechnicalTab',
                        'Do you want to delete the Exif makernote?'))
                    msg.setIcon(msg.Icon.Warning)
                    msg.setStandardButtons(msg.StandardButton.YesToAll |
                                           msg.StandardButton.NoToAll)
                    msg.setDefaultButton(msg.StandardButton.NoToAll)
                    delete_makernote = (
                        execute(msg) == msg.StandardButton.YesToAll)
                if delete_makernote:
                    image.metadata.set_delete_makernote()
            image.metadata.camera_model = value
        self._update_camera_model()

    @QtSlot(str, object)
    @catch_all
    def new_lens_model(self, key, value):
        for image in self.app.image_list.get_selected_images():
            image.metadata.lens_model = value
        self._update_lens_model()

    @QtSlot(object)
    @catch_all
    def new_aperture(self, value):
        for image in self.app.image_list.get_selected_images():
            image.metadata.aperture = value
        self._update_aperture()

    @QtSlot(object)
    @catch_all
    def new_focal_length(self, value):
        for image in self.app.image_list.get_selected_images():
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
        for image in self.app.image_list.get_selected_images():
            image.metadata.focal_length_35 = value
            self.set_crop_factor(image.metadata)
        self._update_focal_length()
        self._update_focal_length_35()

    @QtSlot(str, dict)
    @catch_all
    def new_date_value(self, key, new_value):
        for image in self.app.image_list.get_selected_images():
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
        images = self.app.image_list.get_selected_images()
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
        images = self.app.image_list.get_selected_images()
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
        images = self.app.image_list.get_selected_images()
        if not images:
            return
        value = images[0].metadata.orientation
        for image in images[1:]:
            if image.metadata.orientation != value:
                # multiple values
                self.widgets['orientation'].set_multiple()
                return
        self.widgets['orientation'].set_value(value and int(value))

    def _update_camera_model(self):
        images = self.app.image_list.get_selected_images()
        if not images:
            return
        value = images[0].metadata.camera_model
        for image in images[1:]:
            if image.metadata.camera_model != value:
                self.widgets['camera_model'].set_multiple()
                return
        self.widgets['camera_model'].set_value(value)

    def _update_lens_model(self):
        images = self.app.image_list.get_selected_images()
        if not images:
            return
        self.widgets['lens_model'].setToolTip('')
        value = images[0].metadata.lens_model
        for image in images[1:]:
            if image.metadata.lens_model != value:
                # multiple values
                self.widgets['lens_model'].set_multiple()
                return
        self.widgets['lens_model'].set_value(value)
        if not value:
            return
        spec = value['spec']
        if not spec:
            return
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
            **dict([(x, float(y) or '') for (x, y) in spec.items()]))
        self.widgets['lens_model'].setToolTip(tool_tip)
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
                    QtWidgets.QMessageBox.StandardButton.Yes |
                    QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.No
                    ) == QtWidgets.QMessageBox.StandardButton.No:
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
        images = self.app.image_list.get_selected_images()
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
        images = self.app.image_list.get_selected_images()
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
        images = self.app.image_list.get_selected_images()
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
            self.app.config_store.delete(
                'crop factor', md.camera_model.get_name(inc_serial=False))
        elif md.focal_length:
            crop_factor = float(md.focal_length_35) / md.focal_length
            self.app.config_store.set(
                'crop factor', md.camera_model.get_name(inc_serial=False),
                crop_factor)

    def get_crop_factor(self, md):
        if md.camera_model:
            crop_factor = self.app.config_store.get(
                'crop factor', md.camera_model.get_name(inc_serial=False))
            if crop_factor:
                return crop_factor
        crop_factor = md.get_crop_factor()
        if crop_factor and md.camera_model:
            self.app.config_store.set(
                'crop factor', md.camera_model.get_name(inc_serial=False),
                crop_factor)
        return crop_factor

    def calc_35(self, md, value=None):
        crop_factor = self.get_crop_factor(md)
        value = value or md.focal_length
        if crop_factor and value:
            return int((float(value) * crop_factor) + 0.5)
        return md.focal_length_35

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
