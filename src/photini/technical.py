##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-26  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
from photini.widgets import (CompoundWidgetMixin, DropDownSelector, Slider,
                             TopLevelWidgetMixin)
from photini.widgets.datetime import DateTimeEdit, TimeZoneWidget
from photini.widgets.number import *

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
        # read cameras from config, updating if necessary
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
        # read lenses from config, updating if necessary
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

    def set_value(self, value):
        super(LensList, self).set_value(value)
        if not (value and value['spec'] and value['spec']['min_fl']):
            self.setToolTip('')
            return
        spec = dict((k, float(v) or '') for k, v in value['spec'].items())
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
            th_ap=translate('TechnicalTab', 'Max aperture'), **spec)
        self.setToolTip(tool_tip)


class PrecisionSlider(Slider):
    value_changed = QtSignal(int)

    def __init__(self, *arg, **kw):
        super(PrecisionSlider, self).__init__(*arg, **kw)
        self.setOrientation(Qt.Orientation.Horizontal)
        self.setRange(1, 6)
        self.setValue(6)
        self.setPageStep(1)
        self.valueChanged.connect(self._value_changed)

    @QtSlot(int)
    @catch_all
    def _value_changed(self, value):
        if value >= 4:
            value += 1
        self.value_changed.emit(value)

    def get_value(self):
        value = super(PrecisionSlider, self).get_value()
        if value is not None and value >= 4:
            value += 1
        return value

    def set_value(self, value):
        if value is not None and value >= 5:
            value -= 1
        super(PrecisionSlider, self).set_value(value)


class DateAndTimeWidget(QtWidgets.QGridLayout, CompoundWidgetMixin):
    def __init__(self, key, *arg, **kw):
        super(DateAndTimeWidget, self).__init__(*arg, **kw)
        self._key = key
        self.setVerticalSpacing(0)
        self.setColumnStretch(3, 1)
        self.members = {}
        # date & time
        self.members['datetime'] = DateTimeEdit('datetime')
        self.addWidget(self.members['datetime'], 0, 0, 1, 2)
        # time zone
        self.members['tz_offset'] = TimeZoneWidget('tz_offset')
        self.addWidget(self.members['tz_offset'], 0, 2)
        # precision
        self.addWidget(
            QtWidgets.QLabel(translate('TechnicalTab', 'Precision')), 1, 0)
        self.members['precision'] = PrecisionSlider('precision')
        self.addWidget(self.members['precision'], 1, 1)
        # connections
        self.members['precision'].value_changed.connect(
            self.members['datetime'].set_precision)
        for widget in self.sub_widgets():
            widget.new_value.connect(self.sw_new_value)

    def sub_widgets(self):
        return self.members.values()

    def paste_value(self, value):
        for key, value in value.items():
            self.members[key].set_value(value)
            self.members[key].emit_value()


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
        self.offset.setDisplayFormat("'{}:'HH' {}:'mm' {}:'ss".format(
            translate('TechnicalTab', 'h',
                      'single letter abbreviation of "hours"'),
            translate('TechnicalTab', 'm',
                      'single letter abbreviation of "minutes"'),
            translate('TechnicalTab', 's',
                      'single letter abbreviation of "seconds"')))
        self.layout().addWidget(self.offset)
        self.layout().addSpacing(spacing)
        # time zone
        self.time_zone = TimeZoneWidget('time_zone')
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
        self.time_zone.setSpecialValueText('')
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
            if not camera:
                continue
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
        if self.lens_spec['max_fl'].get_value() == self.lens_spec[
                                                    'min_fl'].get_value():
            self.lens_spec['max_fl'].set_value(None)
            self.lens_spec['max_fl_fn'].set_value(None)

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
            if key.endswith('_fn'):
                self.lens_spec[key] = NumericalWidget(
                    key, DoubleValidator(minimum=0.0, prefix=translate(
                        'TechnicalTab', 'ƒ/', 'lens aperture')))
            else:
                self.lens_spec[key] = NumericalWidget(
                    key, IntValidator(minimum=0.0, suffix=translate(
                        'TechnicalTab', ' mm', 'millimetres focal length')))
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
    def __init__(self, src, dst, *arg, **kw):
        super(DateLink, self).__init__(*arg, **kw)
        self.src = src
        self.dst = dst
        self.clicked.connect(self._clicked)
        self.src.new_value.connect(self.link_input)

    @QtSlot(dict)
    @catch_all
    def link_input(self, value):
        if self.isChecked():
            self.dst.paste_value(value[self.src._key])

    @QtSlot()
    @catch_all
    def _clicked(self):
        checked = self.isChecked()
        self.dst.set_enabled(not checked)
        if checked:
            self.src.emit_value()


class FocalLengthCompound(QtCore.QObject, CompoundWidgetMixin):
    _key = 'focal_length'

    def __init__(self, *arg, **kw):
        super(FocalLengthCompound, self).__init__(*arg, **kw)
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.crop_factor = None
        self.image_crop_factor = None
        self.camera_name = None
        suffix = translate('TechnicalTab', ' mm', 'millimetres focal length')
        # actual focal length
        self.fl = NumericalWidget(
            'fl', DoubleValidator(minimum=0.0, suffix=suffix))
        # 35mm equivalent focal length
        self.fl35 = NumericalWidget(
            'fl35', IntValidator(minimum=0, suffix=suffix))
        for widget in self.sub_widgets():
            widget.new_value.connect(self.sw_new_value)

    def sub_widgets(self):
        return (self.fl, self.fl35)

    def after_load(self):
        if self.is_multiple() or bool(self.fl35.get_value()) or not (
                self.fl.has_value() and self.crop_factor):
            return
        self.fl35.set_value(
            int((float(self.fl.get_value()) * self.crop_factor) + 0.5),
            faint=True)

    def context_menu_event(self, event):
        if not self.camera_name:
            return
        menu = QtWidgets.QMenu()
        action = menu.addAction(
            translate('TechnicalTab', 'Set "crop factor"'),
            self.define_crop_factor)
        execute(menu, event.globalPos())

    @QtSlot()
    @catch_all
    def define_crop_factor(self):
        crop_factor, OK = QtWidgets.QInputDialog.getDouble(
            self.parent(), translate('TechnicalTab', 'Set "crop factor"'),
            translate('TechnicalTab', 'Crop factor'), self.crop_factor,
            0, 10000, 2)
        if not OK:
            return
        if crop_factor:
            self.crop_factor = crop_factor
            self.config_store.set('crop factor', self.camera_name, crop_factor)
        else:
            self.crop_factor = self.image_crop_factor
            self.config_store.delete('crop factor', self.camera_name)
        self.after_load()

    def set_crop_factor(self, md):
        if md.camera_model:
            self.camera_name = md.camera_model.get_name(inc_serial=False)
        self.crop_factor = None
        if self.fl.has_value() and bool(self.fl35.get_value()):
            self.crop_factor = self.fl35.get_value() / self.fl.get_value()
            self.image_crop_factor = self.crop_factor
        if not self.image_crop_factor:
            self.image_crop_factor = md.get_crop_factor()
        if not self.crop_factor and self.camera_name:
            self.crop_factor = self.config_store.get(
                'crop factor', self.camera_name)
        if not self.crop_factor:
            self.crop_factor = self.image_crop_factor
        self.after_load()


class TabWidget(QtWidgets.QWidget, TopLevelWidgetMixin):
    @staticmethod
    def tab_name():
        return translate('TechnicalTab', 'Technical metadata',
                         'Full name of tab shown as a tooltip')

    @staticmethod
    def tab_short_name():
        return translate('TechnicalTab', '&Technical',
                         'Shortest possible name used as tab label')

    def __init__(self, *arg, **kw):
        super(TabWidget, self).__init__(*arg, **kw)
        self.app = QtWidgets.QApplication.instance()
        self.setLayout(QtWidgets.QHBoxLayout())
        self.widgets = {}
        self.link_widget = {}
        # date and time
        date_group = QtWidgets.QGroupBox(
            translate('TechnicalTab', 'Date and time'))
        date_group.setLayout(FormLayout())
        # create date and link widgets
        for key in ('date_taken', 'date_digitised', 'date_modified'):
            self.widgets[key] = DateAndTimeWidget(key)
        for src, dst in self._linked_date.items():
            self.link_widget[src] = DateLink(
                self.widgets[src], self.widgets[dst])
        self.link_widget['date_taken'].setText(
            translate('TechnicalTab', "Link 'taken' and 'digitised'"))
        self.link_widget['date_digitised'].setText(
            translate('TechnicalTab', "Link 'digitised' and 'modified'"))
        # add to layout
        date_group.layout().addRow(translate('TechnicalTab', 'Taken'),
                                   self.widgets['date_taken'])
        date_group.layout().addRow('', self.link_widget['date_taken'])
        date_group.layout().addRow(translate('TechnicalTab', 'Digitised'),
                                   self.widgets['date_digitised'])
        date_group.layout().addRow('', self.link_widget['date_digitised'])
        date_group.layout().addRow(translate('TechnicalTab', 'Modified'),
                                   self.widgets['date_modified'])
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
        self.widgets['orientation'].setFocusPolicy(Qt.FocusPolicy.NoFocus)
        other_group.layout().addRow(translate('TechnicalTab', 'Orientation'),
                                    self.widgets['orientation'])
        # camera model
        self.widgets['camera_model'] = CameraList('camera_model')
        self.widgets['camera_model'].setMinimumWidth(
            width_for_text(self.widgets['camera_model'], 'x' * 30))
        other_group.layout().addRow(translate('TechnicalTab', 'Camera'),
                                    self.widgets['camera_model'])
        # lens model
        self.widgets['lens_model'] = LensList('lens_model')
        self.widgets['lens_model'].setMinimumWidth(
            width_for_text(self.widgets['lens_model'], 'x' * 30))
        other_group.layout().addRow(translate('TechnicalTab', 'Lens model'),
                                    self.widgets['lens_model'])
        # focal lengths
        self.widgets['focal_length'] = FocalLengthCompound(parent=self)
        other_group.layout().addRow(translate('TechnicalTab', 'Focal length'),
                                    self.widgets['focal_length'].fl)
        other_group.layout().addRow(translate('TechnicalTab', '35mm equiv'),
                                    self.widgets['focal_length'].fl35)
        # aperture
        self.widgets['aperture'] = NumericalWidget(
            'aperture', DoubleValidator(minimum=0.0, prefix=translate(
                'TechnicalTab', 'ƒ/', 'lens aperture')))
        other_group.layout().addRow(translate('TechnicalTab', 'Aperture'),
                                    self.widgets['aperture'])
        self.layout().addWidget(other_group, stretch=1)
        # connect signals
        for widget in self.sub_widgets():
            widget.new_value.connect(self.save_data)

    def sub_widgets(self):
        return self.widgets.values()

    _linked_date = {
        'date_taken'    : 'date_digitised',
        'date_digitised': 'date_modified',
        }

    def refresh(self):
        self.new_selection(self.app.image_list.get_selected_images())

    def do_not_close(self):
        return False

    @QtSlot(timedelta, object)
    @catch_all
    def apply_offset(self, offset, tz_offset):
        images = self.app.image_list.get_selected_images()
        for image in images:
            date_taken = dict(image.metadata.date_taken)
            if not date_taken:
                continue
            date_taken['datetime'] += offset
            if tz_offset is not None:
                tz = (date_taken['tz_offset'] or 0) + tz_offset
                tz = min(max(tz, -14 * 60), 15 * 60)
                date_taken['tz_offset'] = tz
            self._set_date_value(image, 'date_taken', date_taken)
        self.load_data(images)

    def _set_date_value(self, image, key, new_value):
        setattr(image.metadata, key, new_value)
        if key in self.link_widget and self.link_widget[key].isChecked():
            self._set_date_value(image, self._linked_date[key], new_value)

    def save_finished(self, value, images):
        for key, value in value.items():
            if key == 'camera_model':
                delete_makernote = 'ask'
                for image in images:
                    delete_makernote = self.ask_delete_makernote(
                        delete_makernote, image, value)
            elif key == 'orientation':
                for image in images:
                    image.load_thumbnail()
            elif key == 'lens_model':
                self.update_focal_length_aperture(images)

    def ask_delete_makernote(self, delete_makernote, image, value):
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
        return delete_makernote

    def update_focal_length_aperture(self, images):
        value = self.widgets['lens_model'].get_value()
        spec = value['spec']
        if not (spec and spec['min_fl']):
            return
        make_changes = False
        for image in images:
            md = image.metadata
            new_aperture = md.aperture or 0
            new_fl = md.focal_length['fl'] or 0
            if not (new_aperture or new_fl):
                continue
            if new_fl <= spec['min_fl']:
                new_fl = spec['min_fl']
                new_aperture = max(new_aperture, spec['min_fl_fn'])
            elif new_fl >= spec['max_fl']:
                new_fl = spec['max_fl']
                new_aperture = max(new_aperture, spec['max_fl_fn'])
            else:
                new_aperture = max(new_aperture,
                                   min(spec['min_fl_fn'], spec['max_fl_fn']))
            if (new_aperture == md.aperture and
                      new_fl == md.focal_length['fl']):
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
                md.aperture = new_aperture
            if new_fl:
                md.focal_length = md.focal_length.reset_focal_length(new_fl)
        if make_changes:
            self.load_data(images)

    def new_selection(self, selection):
        self.load_data(selection)

    def load_finished(self, images):
        if not images:
            return
        if not (self.widgets['focal_length'].is_multiple() or
                self.widgets['camera_model'].is_multiple()):
            self.widgets['focal_length'].set_crop_factor(images[0].metadata)
        md_list = [im.metadata for im in images]
        for src, dst in self._linked_date.items():
            for md in md_list:
                if md[src] != md[dst]:
                    self.link_widget[src].setChecked(False)
                    self.widgets[dst].set_enabled(True)
                    break
            else:
                self.link_widget[src].setChecked(True)
                self.widgets[dst].set_enabled(False)
