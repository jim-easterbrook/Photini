#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2026  Jim Easterbrook  jim@jim-easterbrook.me.uk
#
#  This file is part of Photini.
#
#  Photini is free software: you can redistribute it and/or modify it
#  under the terms of the GNU General Public License as published by the
#  Free Software Foundation, either version 3 of the License, or (at
#  your option) any later version.
#
#  Photini is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Photini.  If not, see <http://www.gnu.org/licenses/>.

import logging

from photini.pyqt import *
from photini.pyqt import using_pyside
from photini.widgets import ChoicesContextMenu, WidgetMixin

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class CalendarWidget(QtWidgets.QCalendarWidget):
    last_date = None

    @catch_all
    def showEvent(self, event):
        if self.selectedDate() == self.minimumDate():
            if self.last_date:
                self.setSelectedDate(self.last_date)
            else:
                self.showToday()
        return super(CalendarWidget, self).showEvent(event)


class DateTimeEdit(QtWidgets.QDateTimeEdit, ChoicesContextMenu, WidgetMixin):
    def __init__(self, key, *arg, **kw):
        super(DateTimeEdit, self).__init__(*arg, **kw)
        self.setCalendarPopup(True)
        self.setCalendarWidget(CalendarWidget())
        self._key = key
        self._multiple = multiple_values()
        self.precision = 1
        self.set_precision(7)
        # ChoicesContextMenu needs these methods
        self.value_to_text = str

    @catch_all
    def contextMenuEvent(self, event):
        menu = self.lineEdit().createStandardContextMenu()
        self.add_choices_context_menu(menu, event)
        execute(menu, event.globalPos())

    @catch_all
    def dateTimeFromText(self, text):
        if not text:
            self.set_value(None)
            return self.dateTime()
        return super(DateTimeEdit, self).dateTimeFromText(text)

    @catch_all
    def focusOutEvent(self, event):
        self.emit_value()
        super(DateTimeEdit, self).focusOutEvent(event)

    @catch_all
    def keyPressEvent(self, event):
        if self.is_multiple() and event.key() in (
                Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self.set_value(None)
        super(DateTimeEdit, self).keyPressEvent(event)

    @catch_all
    def sizeHint(self):
        size = super(DateTimeEdit, self).sizeHint()
        if self.precision == 7:
            self.setFixedSize(size)
        return size

    @catch_all
    def stepBy(self, steps):
        if self.dateTime() == self.minimumDateTime():
            date = (self.calendarWidget().last_date
                    or QtCore.QDateTime.currentDateTime())
            self.setDateTime(date)
        super(DateTimeEdit, self).stepBy(steps)

    @catch_all
    def validate(self, text, pos):
        if not text:
            return QtGui.QValidator.State.Acceptable, text, pos
        return super(DateTimeEdit, self).validate(text, pos)

    def get_value(self):
        value = self.dateTime()
        if value == self.minimumDateTime():
            return None
        if using_pyside:
            return value.toPython()
        return value.toPyDateTime()

    def is_multiple(self):
        return (self.dateTime() == self.minimumDateTime()
                and self.specialValueText() == self._multiple)

    def is_valid(self):
        return not self.is_multiple()

    def set_multiple(self, choices=[]):
        self.choices = [x for x in choices if x is not None]
        self.setDateTime(self.minimumDateTime())
        self.setSpecialValueText(self._multiple)

    @QtSlot(int)
    @catch_all
    def set_precision(self, value):
        if value != self.precision:
            self.precision = value
            self.setDisplayFormat(
                ''.join(('yyyy', '-MM', '-dd',
                         ' hh', ':mm', ':ss', '.zzz')[:self.precision]))

    def set_value(self, value):
        if value is None:
            self.setSpecialValueText(' ')
            self.setDateTime(self.minimumDateTime())
        else:
            self.calendarWidget().last_date = value
            self.setDateTime(value)
            self.setSpecialValueText('')


class TimeZoneWidget(QtWidgets.QSpinBox, ChoicesContextMenu, WidgetMixin):
    def __init__(self, key, *arg, **kw):
        super(TimeZoneWidget, self).__init__(*arg, **kw)
        self.hour_validator = QtGui.QIntValidator(-14, 15, parent=self)
        self.minute_validator = QtGui.QIntValidator(0, 59, parent=self)
        self._key = key
        self.setRange(self.hour_validator.bottom() * 60,
                      self.hour_validator.top() * 60)
        self.setSingleStep(15)
        self.setWrapping(True)
        self._multiple = multiple()
        self.lineEdit().textEdited.connect(self._text_edited)
        # ChoicesContextMenu needs these methods
        self.value_to_text = self.textFromValue

    @QtSlot(str)
    @catch_all
    def _text_edited(self, text):
        self.lineEdit().setPlaceholderText('')

    @catch_all
    def contextMenuEvent(self, event):
        menu = self.lineEdit().createStandardContextMenu()
        self.add_choices_context_menu(menu, event)
        execute(menu, event.globalPos())

    @catch_all
    def focusOutEvent(self, event):
        self.emit_value()
        super(TimeZoneWidget, self).focusOutEvent(event)

    @catch_all
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self.lineEdit().setPlaceholderText('')
        super(TimeZoneWidget, self).keyPressEvent(event)

    @catch_all
    def textFromValue(self, value):
        if value < 0:
            sign = self.locale().negativeSign()
            value = -value
        else:
            sign = self.locale().positiveSign()
        return sign + QtCore.QTime(value // 60, value % 60).toString('hh:mm')

    @catch_all
    def validate(self, text, pos):
        if not text:
            return QtGui.QValidator.State.Acceptable, text, pos
        parts = text.split(':')
        if len(parts) > 2:
            return QtGui.QValidator.State.Invalid, text, pos
        offset = [text.index(x) for x in parts]
        state, parts[0], new_pos = self.hour_validator.validate(
            parts[0], pos - offset[0])
        if len(parts) < 2 or state != QtGui.QValidator.State.Acceptable:
            return state, text, new_pos + offset[0]
        state, parts[1], new_pos = self.minute_validator.validate(
            parts[1], pos - offset[1])
        return state, text, new_pos + offset[1]

    @catch_all
    def valueFromText(self, text):
        if not text.strip():
            return 0
        value = [self.locale().toInt(x) for x in text.split(':')]
        if len(value) > 2 or not all(x[1] for x in value):
            return 0
        hours = value[0][0]
        if len(value) > 1:
            minutes = value[1][0]
            minutes = int(15.0 * round(float(minutes) / 15.0))
            if hours < 0:
                minutes = -minutes
        else:
            minutes = 0
        return (hours * 60) + minutes

    def get_value(self):
        if not self.text():
            return None
        value = self.value()
        return value

    def is_multiple(self):
        return self.lineEdit().placeholderText() == self._multiple

    def is_valid(self):
        return self.lineEdit().placeholderText() == ''

    def set_multiple(self, choices=[]):
        self.choices = [x for x in choices if x is not None]
        self.lineEdit().setPlaceholderText(self._multiple)
        self.clear()

    def set_value(self, value):
        self.lineEdit().setPlaceholderText('')
        if value is None:
            self.clear()
        else:
            self.setValue(value)
