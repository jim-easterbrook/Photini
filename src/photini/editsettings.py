#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2012-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
#
#  This program is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see
#  <http://www.gnu.org/licenses/>.

import logging

from photini.pyqt import (
    available_packages, catch_all, execute, FormLayout, qt_lib, QtCore, QtGui,
    QtSlot, QtWidgets, width_for_text)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class EditSettings(QtWidgets.QDialog):
    def __init__(self, *arg, **kw):
        super(EditSettings, self).__init__(*arg, **kw)
        self.app = QtWidgets.QApplication.instance()
        self.config_store = self.app.config_store
        self.setWindowTitle(translate('EditSettings', 'Photini: settings'))
        self.setLayout(QtWidgets.QVBoxLayout())
        # main dialog area
        scroll_area = QtWidgets.QScrollArea()
        self.layout().addWidget(scroll_area)
        panel = QtWidgets.QWidget()
        layout = FormLayout()
        panel.setLayout(layout)
        if layout.rowWrapPolicy() == layout.RowWrapPolicy.DontWrapRows:
            layout.setRowWrapPolicy(layout.RowWrapPolicy.WrapLongRows)
        # apply & cancel buttons
        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Apply |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        self.button_box.clicked.connect(self.button_clicked)
        self.layout().addWidget(self.button_box)
        # IPTC data
        if self.config_store.get('files', 'force_iptc'):
            self.config_store.set('files', 'iptc_iim', 'create')
        self.config_store.delete('files', 'force_iptc')
        iptc_mode = self.config_store.get('files', 'iptc_iim', 'preserve')
        button_group = QtWidgets.QButtonGroup(parent=self)
        self.iptc_always = QtWidgets.QRadioButton(
            translate('EditSettings', 'Always write'))
        button_group.addButton(self.iptc_always)
        self.iptc_always.setChecked(iptc_mode == 'create')
        self.iptc_always.setMinimumWidth(
            width_for_text(self.iptc_always, 'x' * 35))
        panel.layout().addRow(
            translate('EditSettings', 'IPTC-IIM metadata'), self.iptc_always)
        self.iptc_auto = QtWidgets.QRadioButton(
            translate('EditSettings', 'Write if exists'))
        button_group.addButton(self.iptc_auto)
        self.iptc_auto.setChecked(iptc_mode == 'preserve')
        panel.layout().addRow('', self.iptc_auto)
        self.iptc_delete = QtWidgets.QRadioButton(
            translate('EditSettings', 'Always delete'))
        button_group.addButton(self.iptc_delete)
        self.iptc_delete.setChecked(iptc_mode == 'delete')
        panel.layout().addRow('', self.iptc_delete)
        # show IPTC-IIM length limits
        length_warning = self.config_store.get('files', 'length_warning', True)
        self.length_warning = QtWidgets.QCheckBox(
            translate('EditSettings', 'Show IPTC-IIM length limits'))
        self.length_warning.setChecked(length_warning)
        panel.layout().addRow('', self.length_warning)
        # sidecar files
        if_mode = self.config_store.get('files', 'image', True)
        sc_mode = self.config_store.get('files', 'sidecar', 'auto')
        if not if_mode:
            sc_mode = 'always'
        button_group = QtWidgets.QButtonGroup(parent=self)
        self.sc_always = QtWidgets.QRadioButton(
            translate('EditSettings', 'Always create'))
        button_group.addButton(self.sc_always)
        self.sc_always.setChecked(sc_mode == 'always')
        panel.layout().addRow(
            translate('EditSettings', 'Sidecar files'), self.sc_always)
        self.sc_auto = QtWidgets.QRadioButton(
            translate('EditSettings', 'Create if necessary'))
        button_group.addButton(self.sc_auto)
        self.sc_auto.setChecked(sc_mode == 'auto')
        self.sc_auto.setEnabled(if_mode)
        panel.layout().addRow('', self.sc_auto)
        self.sc_delete = QtWidgets.QRadioButton(
            translate('EditSettings', 'Delete when possible'))
        button_group.addButton(self.sc_delete)
        self.sc_delete.setChecked(sc_mode == 'delete')
        self.sc_delete.setEnabled(if_mode)
        panel.layout().addRow('', self.sc_delete)
        # image file locking
        self.write_if = QtWidgets.QCheckBox(
            translate('EditSettings', '(when possible)'))
        self.write_if.setChecked(if_mode)
        self.write_if.clicked.connect(self.new_write_if)
        panel.layout().addRow(
            translate('EditSettings', 'Write to image file'), self.write_if)
        # preserve file timestamps
        keep_time = self.config_store.get('files', 'preserve_timestamps', 'now')
        if isinstance(keep_time, bool):
            # old config format
            keep_time = ('now', 'keep')[keep_time]
        button_group = QtWidgets.QButtonGroup(parent=self)
        self.keep_time = QtWidgets.QRadioButton(
            translate('EditSettings', 'Keep original'))
        button_group.addButton(self.keep_time)
        self.keep_time.setChecked(keep_time=='keep')
        panel.layout().addRow(
            translate('EditSettings', 'File timestamps'), self.keep_time)
        self.time_taken = QtWidgets.QRadioButton(
            translate('EditSettings', 'Set to when photo was taken'))
        button_group.addButton(self.time_taken)
        self.time_taken.setChecked(keep_time=='taken')
        panel.layout().addRow('', self.time_taken)
        button = QtWidgets.QRadioButton(
            translate('EditSettings', 'Set to when file is saved'))
        button_group.addButton(button)
        button.setChecked(keep_time=='now')
        panel.layout().addRow('', button)
        # import GPX altitude
        if self.app.gpx_importer:
            self.gpx_altitude = QtWidgets.QCheckBox(
                translate('EditSettings', 'set altitude'))
            self.gpx_altitude.setChecked(
                self.config_store.get('map', 'gpx_altitude', True))
            panel.layout().addRow(
                translate('EditSettings', 'GPX importer'), self.gpx_altitude)
        # map icon colours
        self.map_pin = {}
        self.map_pin[True] = {'button': QtWidgets.QPushButton(
            translate('EditSettings', 'location pin (selected)'))}
        self.map_pin[True]['button'].clicked.connect(self._get_map_pin_true)
        panel.layout().addRow(translate('EditSettings', 'Map icon colours'),
                              self.map_pin[True]['button'])
        self.map_pin[False] = {'button': QtWidgets.QPushButton(
            translate('EditSettings', 'location pin (unselected)'))}
        self.map_pin[False]['button'].clicked.connect(self._get_map_pin_false)
        panel.layout().addRow('', self.map_pin[False]['button'])
        for active in self.map_pin:
            self.map_pin[active]['colour'] = QtGui.QColor(
                self.config_store.get('map', 'pin_colour_{}'.format(active)))
            self.map_pin[active]['button'].setFlat(True)
            self.map_pin[active]['button'].setFixedHeight(
                self.iptc_always.sizeHint().height())
            self._set_map_pin_button_colour(self.map_pin[active])
            self.map_pin[active]['button'].setStyleSheet('text-align: left;')
        self.map_gps = {}
        if self.app.gpx_importer:
            self.map_gps[True] = {'button': QtWidgets.QPushButton(
                translate('EditSettings', 'GPS track point (selected)'))}
            self.map_gps[True]['button'].clicked.connect(self._get_map_gps_true)
            panel.layout().addRow('', self.map_gps[True]['button'])
            self.map_gps[False] = {'button': QtWidgets.QPushButton(
                translate('EditSettings', 'GPS track point (unselected)'))}
            self.map_gps[False]['button'].clicked.connect(self._get_map_gps_false)
            panel.layout().addRow('', self.map_gps[False]['button'])
            for active in self.map_gps:
                self.map_gps[active]['colour'] = QtGui.QColor(
                    self.config_store.get('map', 'gps_colour_{}'.format(active)))
                self.map_gps[active]['button'].setFlat(True)
                self.map_gps[active]['button'].setFixedHeight(
                    self.iptc_always.sizeHint().height())
                self._set_map_pin_button_colour(self.map_gps[active])
                self.map_gps[active]['button'].setStyleSheet('text-align: left;')
        # Qt package
        self.qt_package = {}
        if len(available_packages) > 1:
            lhs = translate('EditSettings', 'Qt package')
            button_group = QtWidgets.QButtonGroup(parent=self)
            for package in available_packages:
                self.qt_package[package] = QtWidgets.QRadioButton(package)
                self.qt_package[package].setChecked(qt_lib == package)
                button_group.addButton(self.qt_package[package])
                panel.layout().addRow(lhs, self.qt_package[package])
                lhs = ''
        # add panel to scroll area after its size is known
        scroll_area.viewport().setMinimumWidth(panel.sizeHint().width())
        scroll_area.setWidget(panel)

    def _set_map_pin_button_colour(self, details):
        icon = QtGui.QPixmap(details['button'].iconSize())
        icon.fill(details['colour'])
        details['button'].setIcon(QtGui.QIcon(icon))

    @QtSlot()
    @catch_all
    def _get_map_pin_true(self):
        self.do_colour_dialog(self.map_pin[True])

    @QtSlot()
    @catch_all
    def _get_map_pin_false(self):
        self.do_colour_dialog(self.map_pin[False])

    @QtSlot()
    @catch_all
    def _get_map_gps_true(self):
        self.do_colour_dialog(self.map_gps[True])

    @QtSlot()
    @catch_all
    def _get_map_gps_false(self):
        self.do_colour_dialog(self.map_gps[False])

    def do_colour_dialog(self, details):
        colour = QtWidgets.QColorDialog.getColor(
            initial=details['colour'], parent=self)
        if not colour.isValid():
            return
        details['colour'] = colour
        self._set_map_pin_button_colour(details)

    @QtSlot()
    @catch_all
    def new_write_if(self):
        if_mode = self.write_if.isChecked()
        self.sc_auto.setEnabled(if_mode)
        self.sc_delete.setEnabled(if_mode)
        if not if_mode:
            self.sc_always.setChecked(True)

    @QtSlot(QtWidgets.QAbstractButton)
    @catch_all
    def button_clicked(self, button):
        if button != self.button_box.button(
                QtWidgets.QDialogButtonBox.StandardButton.Apply):
            return self.reject()
        # change config
        if self.iptc_always.isChecked():
            iptc_mode = 'create'
        elif self.iptc_auto.isChecked():
            iptc_mode = 'preserve'
        else:
            iptc_mode = 'delete'
        self.config_store.set('files', 'iptc_iim', iptc_mode)
        self.config_store.set(
            'files', 'length_warning', self.length_warning.isChecked())
        if self.sc_always.isChecked():
            sc_mode = 'always'
        elif self.sc_auto.isChecked():
            sc_mode = 'auto'
        else:
            sc_mode = 'delete'
        self.config_store.set('files', 'sidecar', sc_mode)
        self.config_store.set('files', 'image', self.write_if.isChecked())
        if self.keep_time.isChecked():
            keep_time = 'keep'
        elif self.time_taken.isChecked():
            keep_time = 'taken'
        else:
            keep_time = 'now'
        self.config_store.set('files', 'preserve_timestamps', keep_time)
        if self.app.gpx_importer:
            self.config_store.set(
                'map', 'gpx_altitude', self.gpx_altitude.isChecked())
        for active in self.map_pin:
            self.config_store.set(
                'map', 'pin_colour_{}'.format(active),
                self.map_pin[active]['colour'].name())
        for active in self.map_gps:
            self.config_store.set(
                'map', 'gps_colour_{}'.format(active),
                self.map_gps[active]['colour'].name())
        self.app.map_icon_factory.new_colours()
        for package, button in self.qt_package.items():
            if button.isChecked():
                if package != qt_lib:
                    self.config_store.set('pyqt', 'qt_lib', package)
                    dialog = QtWidgets.QMessageBox(parent=self)
                    dialog.setWindowTitle(translate(
                        'EditSettings', 'Photini: restart required'))
                    dialog.setText('<h3>{}</h3>'.format(translate(
                        'EditSettings', 'Restart required.')))
                    dialog.setInformativeText(translate(
                        'EditSettings', 'The change of Qt package will take'
                        ' effect when Photini is restarted.'))
                    dialog.setIcon(dialog.Icon.Information)
                    execute(dialog)
                    break
        return self.accept()
