# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-13  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from datetime import datetime as pyDateTime, date as pyDate, time as pyTime

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
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        layout = QtGui.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # date
        self.date = DateEdit()
        self.date.setDisplayFormat(' yyyy-MM-dd')
        self.date.setCalendarPopup(True)
        self.date.setSpecialValueText(' ')
        self.date.editingFinished.connect(self._new_date)
        layout.addWidget(self.date)
        # time
        self.time = TimeEdit()
        self.time.setDisplayFormat(' hh:mm:ss')
        self.time.setSpecialValueText(' ')
        self.time.editingFinished.connect(self._new_time)
        layout.addWidget(self.time)
        # clear button
        clear_button = QtGui.QPushButton('clear')
        clear_button.clicked.connect(self._clear)
        layout.addWidget(clear_button)

    date_changed = QtCore.pyqtSignal(pyDate)
    def _new_date(self):
        date = self.date.date()
        self.date_changed.emit(date.toPyDate())

    time_changed = QtCore.pyqtSignal(pyTime)
    def _new_time(self):
        time = self.time.time()
        self.time_changed.emit(time.toPyTime())

    def _clear(self):
        self.clearDate()
        self.clearTime()
        self.time_changed.emit(pyTime.min)
        self.date_changed.emit(pyDate.min)

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
        self.time.setSpecialValueText('<multiple>')
        self.time.setTime(self.time.minimumTime())

    def setDate(self, value):
        self.date.setDate(value)

    def setTime(self, value):
        self.time.setSpecialValueText('')
        self.time.setTime(value)

class Technical(QtGui.QWidget):
    def __init__(self, config_store, image_list, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.config_store = config_store
        self.image_list = image_list
        self.setLayout(QtGui.QGridLayout())
        self.widgets = dict()
        # date and time
        date_group = QtGui.QGroupBox('Date and time')
        date_group.setLayout(QtGui.QFormLayout())
        # taken
        self.widgets['taken'] = DateAndTimeWidget()
        self.widgets['taken'].date_changed.connect(self.new_taken)
        self.widgets['taken'].time_changed.connect(self.new_taken)
        date_group.layout().addRow('Taken', self.widgets['taken'])
        # digitised
        self.widgets['digitised'] = DateAndTimeWidget()
        self.widgets['digitised'].date_changed.connect(self.new_digitised)
        self.widgets['digitised'].time_changed.connect(self.new_digitised)
        date_group.layout().addRow('Digitised', self.widgets['digitised'])
        # modified
        self.widgets['modified'] = DateAndTimeWidget()
        self.widgets['modified'].date_changed.connect(self.new_modified)
        self.widgets['modified'].time_changed.connect(self.new_modified)
        date_group.layout().addRow('Modified', self.widgets['modified'])
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
        self.orientation.addItem('multiple', -1)
        self.orientation.currentIndexChanged.connect(self.new_orientation)
        other_group.layout().addRow('Orientation', self.orientation)
        self.layout().addWidget(other_group, 0, 1)
        # disable until an image is selected
        for key in self.widgets:
            self.widgets[key].setEnabled(False)
        self.orientation.setEnabled(False)

    def refresh(self):
        pass

    def new_taken(self, value):
        self._new_value('taken', value)

    def new_digitised(self, value):
        self._new_value('digitised', value)

    def new_modified(self, value):
        self._new_value('modified', value)

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

    def _new_value(self, key, value):
        if isinstance(value, pyTime):
            # update times, leaving date unchanged
            for image in self.image_list.get_selected_images():
                current = image.metadata.get_item('date_%s' % key)
                if not current:
                    current = pyDateTime.today()
                image.metadata.set_item(
                    'date_%s' % key, pyDateTime.combine(current.date(), value))
        elif value == pyDate.min:
            # clear date & time
            for image in self.image_list.get_selected_images():
                image.metadata.del_item('date_%s' % key)
        else:
            # update dates, leaving times unchanged
            for image in self.image_list.get_selected_images():
                current = image.metadata.get_item('date_%s' % key)
                if not current:
                    current = pyDateTime.min
                image.metadata.set_item(
                    'date_%s' % key, pyDateTime.combine(value, current.time()))
        self._update_datetime(key)

    def _update_datetime(self, key):
        dates = []
        times = []
        for image in self.image_list.get_selected_images():
            value = image.metadata.get_item('date_%s' % key)
            if value:
                dates.append(value.date())
                times.append(value.time())
            else:
                dates.append(None)
                times.append(None)
        value = dates[0]
        for new_value in dates[1:]:
            if new_value != value:
                self.widgets[key].setMultipleDate()
                break
        else:
            if value is None:
                self.widgets[key].clearDate()
            else:
                self.widgets[key].setDate(value)
        value = times[0]
        for new_value in times[1:]:
            if new_value != value:
                self.widgets[key].setMultipleTime()
                break
        else:
            if value is None:
                self.widgets[key].clearTime()
            else:
                self.widgets[key].setTime(value)

    def _update_orientation(self):
        value = None
        for image in self.image_list.get_selected_images():
            new_value = image.metadata.get_item('orientation')
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
            for key in self.widgets:
                self.widgets[key].clearDate()
                self.widgets[key].clearTime()
                self.widgets[key].setEnabled(False)
            self.orientation.setCurrentIndex(self.orientation.findData(1))
            self.orientation.setEnabled(False)
            return
        for key in self.widgets:
            self.widgets[key].setEnabled(True)
            self._update_datetime(key)
        self.orientation.setEnabled(True)
        self._update_orientation()
