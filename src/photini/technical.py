# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-14  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
        clear_button = QtGui.QPushButton('clear')
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
        self.date.setSpecialValueText('<multiple>')
        self.date.setDate(self.date.minimumDate())

    def setMultipleTime(self):
        self.time.setSpecialValueText('<multi>')
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
        self.hours.setSuffix(' hours')
        layout.addWidget(self.hours)
        # minutes
        self.minutes = QtGui.QSpinBox()
        self.minutes.setRange(-60, 60)
        self.minutes.setSuffix(' minutes')
        layout.addWidget(self.minutes)
        # apply button
        apply_button = QtGui.QPushButton('apply')
        apply_button.clicked.connect(self._apply)
        layout.addWidget(apply_button)

    apply_offset = QtCore.pyqtSignal(timedelta)
    def _apply(self):
        offset = timedelta(hours=self.hours.value(),
                           minutes=self.minutes.value())
        self.apply_offset.emit(offset)

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
        # date and time
        date_group = QtGui.QGroupBox('Date and time')
        date_group.setLayout(QtGui.QFormLayout())
        # taken
        self.date_widget['taken'] = DateAndTimeWidget('taken')
        self.date_widget['taken'].date_changed.connect(self.new_datetime)
        self.date_widget['taken'].time_changed.connect(self.new_datetime)
        date_group.layout().addRow('Taken', self.date_widget['taken'])
        # link taken & digitised
        self.link_widget['digitised'] = QtGui.QCheckBox(
            "Link 'taken' and 'digitised'")
        self.link_widget['digitised'].clicked.connect(self.new_link)
        date_group.layout().addRow('', self.link_widget['digitised'])
        # digitised
        self.date_widget['digitised'] = DateAndTimeWidget('digitised')
        self.date_widget['digitised'].date_changed.connect(self.new_datetime)
        self.date_widget['digitised'].time_changed.connect(self.new_datetime)
        date_group.layout().addRow('Digitised', self.date_widget['digitised'])
        # link digitised & modified
        self.link_widget['modified'] = QtGui.QCheckBox(
            "Link 'digitised' and 'modified'")
        self.link_widget['modified'].clicked.connect(self.new_link)
        date_group.layout().addRow('', self.link_widget['modified'])
        # modified
        self.date_widget['modified'] = DateAndTimeWidget('modified')
        self.date_widget['modified'].date_changed.connect(self.new_datetime)
        self.date_widget['modified'].time_changed.connect(self.new_datetime)
        date_group.layout().addRow('Modified', self.date_widget['modified'])
        # offset
        self.offset_widget = OffsetWidget()
        self.offset_widget.apply_offset.connect(self.apply_offset)
        date_group.layout().addRow('Offset', self.offset_widget)
        self.layout().addWidget(date_group, 0, 0)
        # other
        other_group = QtGui.QGroupBox('Other')
        other_group.setLayout(QtGui.QFormLayout())
        # orientation
        self.orientation = QtGui.QComboBox()
        self.orientation.addItem('normal', 1)
        self.orientation.addItem('rotate -90', 6)
        self.orientation.addItem('rotate +90', 8)
        self.orientation.addItem('rotate 180', 3)
        self.orientation.addItem('reflect left-right', 2)
        self.orientation.addItem('reflect top-bottom', 4)
        self.orientation.addItem('reflect tr-bl', 5)
        self.orientation.addItem('reflect tl-br', 7)
        self.orientation.addItem('<multiple>', -1)
        self.orientation.currentIndexChanged.connect(self.new_orientation)
        other_group.layout().addRow('Orientation', self.orientation)
        self.layout().addWidget(other_group, 0, 1)
        # disable until an image is selected
        for key in self.date_widget:
            self.date_widget[key].setEnabled(False)
        self.offset_widget.setEnabled(False)
        self.orientation.setEnabled(False)

    def refresh(self):
        pass

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
                value = image.metadata.get_item('date_%s' % key)
                if value.empty():
                    continue
                image.metadata.set_item('date_%s' % key, value.value + offset)
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
        value, OK = self.orientation.itemData(index).toInt()
        if value < 1 or not OK:
            self._update_orientation()
            return
        for image in self.image_list.get_selected_images():
            image.metadata.set_item('orientation', value)
            image.pixmap = None
            image.load_thumbnail()

    def _new_datetime_value(self, key, value):
        if isinstance(value, QtCore.QTime):
            # update times, leaving date unchanged
            for image in self.image_list.get_selected_images():
                current = image.metadata.get_item('date_%s' % key)
                if current.empty():
                    current = pyDateTime.today()
                else:
                    current = current.value
                image.metadata.set_item(
                    'date_%s' % key,
                    pyDateTime.combine(current.date(), value.toPyTime()))
        elif value == self.date_widget[key].date.minimumDate():
            # clear date & time
            for image in self.image_list.get_selected_images():
                image.metadata.del_item('date_%s' % key)
        else:
            # update dates, leaving times unchanged
            for image in self.image_list.get_selected_images():
                current = image.metadata.get_item('date_%s' % key)
                if current.empty():
                    current = pyDateTime.min
                else:
                    current = current.value
                image.metadata.set_item(
                    'date_%s' % key,
                    pyDateTime.combine(value.toPyDate(), current.time()))
        self._update_datetime(key)

    def _update_datetime(self, key):
        dates = []
        times = []
        for image in self.image_list.get_selected_images():
            value = image.metadata.get_item('date_%s' % key)
            if value.empty():
                dates.append(None)
                times.append(None)
            else:
                dates.append(value.value.date())
                times.append(value.value.time())
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
            new_value = image.metadata.get_item('orientation')
            if new_value.empty():
                new_value = None
            else:
                new_value = new_value.value
            if value and new_value != value:
                value = -1
                break
            value = new_value
        if not value:
            value = 1
        self.orientation.setCurrentIndex(self.orientation.findData(value))

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        if not selection:
            for key in self.date_widget:
                self.date_widget[key].clearDate()
                self.date_widget[key].clearTime()
                self.date_widget[key].setEnabled(False)
            for key in self.link_widget:
                self.link_widget[key].setEnabled(False)
            self.offset_widget.setEnabled(False)
            self.orientation.setCurrentIndex(self.orientation.findData(1))
            self.orientation.setEnabled(False)
            return
        self.date_widget['taken'].setEnabled(True)
        for key in self.date_widget:
            self._update_datetime(key)
        for key in self.link_widget:
            master = self.link_master[key]
            self.link_widget[key].setEnabled(True)
            if (self.date_widget[key].date.date() ==
                                        self.date_widget[master].date.date() and
                    self.date_widget[key].time.time() ==
                                        self.date_widget[master].time.time()):
                self.date_widget[key].setEnabled(False)
                self.link_widget[key].setChecked(True)
            else:
                self.link_widget[key].setChecked(False)
                self.date_widget[key].setEnabled(True)
        self.offset_widget.setEnabled(True)
        self.orientation.setEnabled(True)
        self._update_orientation()
