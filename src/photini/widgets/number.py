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
from photini.widgets import (
    ChoicesContextMenu, CompoundWidgetMixin, Label, WidgetMixin)

__all__ = ('AltitudeDisplay', 'DoubleValidator', 'GPSInfoWidgets',
           'IntValidator', 'LatLongDisplay', 'NumericalWidget')

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class DecoratorMixin(object):
    def init_decorator(self, prefix, suffix):
        self._prefix = prefix
        self._suffix = suffix

    def decorate(self, text, pos):
        if not text:
            return text, pos
        return self._prefix + text + self._suffix, len(self._prefix) + pos

    def undecorate(self, text, pos):
        if self._prefix and text.startswith(self._prefix):
            count = len(self._prefix)
            pos -= count
            text = text[count:]
        if self._suffix and text.endswith(self._suffix):
            count = len(self._suffix)
            text = text[:-count]
            pos = min(pos, len(text))
        return text, pos


class IntValidator(QtGui.QIntValidator, DecoratorMixin):
    def __init__(self, *arg, minimum=None, maximum=None,
                 prefix='', suffix='', **kw):
        super(IntValidator, self).__init__(*arg, **kw)
        if minimum is not None:
            self.setBottom(minimum)
        if maximum is not None:
            self.setTop(maximum)
        self.init_decorator(prefix, suffix)

    @catch_all(exc_return=(QtGui.QValidator.State.Invalid, '', 0))
    def validate(self, text, pos):
        text, pos = self.undecorate(text, pos)
        state, text, pos = super(IntValidator, self).validate(text, pos)
        text, pos = self.decorate(text, pos)
        return state, text, pos

    def text_to_value(self, text):
        value, OK = self.locale().toInt(text)
        if OK:
            return value
        return None

    def value_to_text(self, value):
        return self.locale().toString(int(value))


class DoubleValidator(QtGui.QDoubleValidator, DecoratorMixin):
    def __init__(self, *arg, minimum=None, maximum=None,
                 prefix='', suffix='', **kw):
        super(DoubleValidator, self).__init__(*arg, **kw)
        self.setNotation(self.Notation.StandardNotation)
        if minimum is not None:
            self.setBottom(minimum)
        if maximum is not None:
            self.setTop(maximum)
        self.init_decorator(prefix, suffix)

    @catch_all(exc_return=(QtGui.QValidator.State.Invalid, '', 0))
    def validate(self, text, pos):
        text, pos = self.undecorate(text, pos)
        state, text, pos = super(DoubleValidator, self).validate(text, pos)
        text, pos = self.decorate(text, pos)
        return state, text, pos

    def text_to_value(self, text):
        value, OK = self.locale().toDouble(text)
        if OK:
            return value
        return None

    def value_to_text(self, value):
        return self.locale().toString(float(value))


class NumericalWidget(QtWidgets.QLineEdit, ChoicesContextMenu, WidgetMixin):
    def __init__(self, key, validator, *arg, **kw):
        super(NumericalWidget, self).__init__(*arg, **kw)
        self._key = key
        self.setValidator(validator)
        self._multiple_values = multiple_values()
        self.textEdited.connect(self._text_edited)

    @QtSlot(str)
    @catch_all()
    def _text_edited(self, text):
        self.setPlaceholderText('')

    @catch_all()
    def contextMenuEvent(self, event):
        if self.isReadOnly():
            return
        menu = self.createStandardContextMenu()
        self.add_choices_context_menu(menu, event)
        execute(menu, event.globalPos())

    @catch_all()
    def focusOutEvent(self, event):
        self.emit_value()
        super(NumericalWidget, self).focusOutEvent(event)

    @catch_all()
    def keyPressEvent(self, event):
        self.handle_delete_key(event)
        super(NumericalWidget, self).keyPressEvent(event)

    def has_value(self):
        return bool(self.text()) or bool(self.placeholderText())

    def is_multiple(self):
        return self.placeholderText() == self._multiple_values

    def is_valid(self):
        return self.placeholderText() == ''

    def set_multiple(self, choices=[]):
        self.choices = [x for x in choices if x is not None]
        self.setPlaceholderText(self._multiple_values)
        self.clear()

    def get_value(self):
        text = self.text()
        if text:
            validator = self.validator()
            text, pos = validator.undecorate(text, 0)
            return validator.text_to_value(text)
        return None

    def set_value(self, value, faint=False):
        if value is None:
            self.setPlaceholderText('')
            self.clear()
            return
        text = self.value_to_text(value)
        if faint:
            self.setPlaceholderText(text)
            self.clear()
        else:
            self.setText(text)
            self.setPlaceholderText('')

    def value_to_text(self, value):
        validator = self.validator()
        text = validator.value_to_text(value)
        text, pos = validator.decorate(text, 0)
        return text


class LatLongValidator(QtGui.QValidator):
    def __init__(self, *arg, **kw):
        super(LatLongValidator, self).__init__(*arg, **kw)
        self.lat_validator = QtGui.QDoubleValidator(
            -90.0, 90.0, 20, parent=self)
        self.lng_validator = QtGui.QDoubleValidator(
            -180.0, 180.0, 20, parent=self)

    @catch_all(exc_return=(QtGui.QValidator.State.Invalid, '', 0))
    def validate(self, text, pos):
        if not text:
            return QtGui.QValidator.State.Acceptable, text, pos
        parts = text.split(' ')
        if any(x == '' for x in parts[:-1]):
            return QtGui.QValidator.State.Invalid, text, pos
        if len(parts) > 2:
            return QtGui.QValidator.State.Invalid, text, pos
        offset = [text.index(x) for x in parts]
        state, parts[0], new_pos = self.lat_validator.validate(
            parts[0], pos - offset[0])
        if len(parts) < 2 or state != self.State.Acceptable:
            return state, text, new_pos + offset[0]
        state, parts[1], new_pos = self.lng_validator.validate(
            parts[1], pos - offset[1])
        return state, text, new_pos + offset[1]

    @catch_all(exc_return='')
    def fixup(self, text):
        value = self.text_to_value(text)
        if value == (None, None):
            return ''
        value = (min(max(value[0], -90.0), 90.0),
                 ((value[1] + 180.0) % 360.0) - 180.0)
        return self.value_to_text(value)

    def decorate(self, text, pos):
        return text, pos

    def undecorate(self, text, pos):
        return text, pos

    def text_to_value(self, text):
        value = [self.locale().toDouble(x) for x in text.split()]
        if len(value) != 2 or not all(x[1] for x in value):
            # float conversion failed
            return (None, None)
        return tuple(x[0] for x in value)

    def value_to_text(self, value):
        return ' '.join(self.locale().toString(float(x), 'f', 6)
                        for x in value if x is not None)


class LatLongDisplay(NumericalWidget):
    lat_key = 'exif:GPSLatitude'
    lng_key = 'exif:GPSLongitude'

    def __init__(self, *arg, **kw):
        validator = LatLongValidator()
        super(LatLongDisplay, self).__init__('', validator, *arg, **kw)
        self.label = Label(translate(
            'LatLongDisplay', 'Lat, long',
            'Short abbreviation of "Latitude, longitude"'))
        self.setFixedWidth(width_for_text(self, '8' * 22))
        self.setToolTip('<p>{}</p>'.format(translate(
            'LatLongDisplay', 'Latitude and longitude (in degrees) as two'
            ' decimal numbers separated by a space.')))

    def get_value_dict(self):
        if self.is_valid():
            value = self.get_value() or (None, None)
            return {self.lat_key: value[0], self.lng_key: value[1]}
        return {}

    def set_value_dict(self, value):
        value = value or {}
        self.set_value(self.dict_to_value(value))

    @classmethod
    def dict_to_value(cls, value):
        return (value.get(cls.lat_key), value.get(cls.lng_key))

    def _load_data(self, md_list):
        md_list = [self.dict_to_value(md) for md in md_list]
        choices = []
        for value in md_list:
            if value not in choices:
                choices.append(value)
        if len(choices) > 1:
            self.set_multiple(choices=[
                x for x in choices if x != None])
        else:
            self.set_value(choices and choices[0])

    def _save_data(self, metadata, value):
        if self.lat_key in value and self.lng_key in value:
            metadata[self.lat_key] = value[self.lat_key]
            metadata[self.lng_key] = value[self.lng_key]
        return False


class AltitudeDisplay(NumericalWidget):
    def __init__(self, *args, **kwds):
        validator = DoubleValidator(
            suffix=translate('AltitudeDisplay', ' m', 'metres altitude'))
        super(AltitudeDisplay, self).__init__(
            'exif:GPSAltitude', validator, *args, **kwds)
        self.setToolTip('<p>{}</p>'.format(translate(
            'AltitudeDisplay', 'Altitude of the location in metres.')))
        self.label = Label(translate('AltitudeDisplay', 'Altitude'))


class GPSInfoWidgets(QtCore.QObject, CompoundWidgetMixin):
    _key = 'gps_info'

    def __init__(self, *arg, **kw):
        super(GPSInfoWidgets, self).__init__(*arg, **kw)
        # child widgets
        self.latlon = LatLongDisplay()
        self.alt = AltitudeDisplay()
        for widget in self.sub_widgets():
            widget.new_value.connect(self.sw_new_value)

    def sub_widgets(self):
        return (self.latlon, self.alt)
