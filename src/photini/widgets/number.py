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
from photini.widgets import WidgetMixin

__all__ = ('DoubleValidator', 'IntValidator', 'NumericalWidget')

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

    @catch_all
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
        return self.locale().toString(value)


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

    @catch_all
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


class NumericalWidget(QtWidgets.QLineEdit, WidgetMixin):
    def __init__(self, key, validator, *arg, **kw):
        super(NumericalWidget, self).__init__(*arg, **kw)
        self._key = key
        self.setValidator(validator)
        self._multiple_values = multiple_values()
        self.textEdited.connect(self._text_edited)

    @QtSlot(str)
    @catch_all
    def _text_edited(self, text):
        self.setPlaceholderText('')

    @catch_all
    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        suggestion_group = QtGui2.QActionGroup(menu)
        if self.is_multiple() and self.choices:
            sep = menu.insertSeparator(menu.actions()[0])
            validator = self.validator()
            for suggestion in self.choices:
                text = validator.value_to_text(suggestion)
                text, pos = validator.decorate(text, 0)
                action = QtGui2.QAction(text, suggestion_group)
                action.setData(suggestion)
                menu.insertAction(sep, action)
        action = execute(menu, event.globalPos())
        if action and action.actionGroup() == suggestion_group:
            self.set_value(action.data())
            self.emit_value()

    @catch_all
    def focusOutEvent(self, event):
        self.emit_value()
        super(NumericalWidget, self).focusOutEvent(event)

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
        validator = self.validator()
        text = validator.value_to_text(value)
        text, pos = validator.decorate(text, 0)
        if faint:
            self.setPlaceholderText(text)
            self.clear()
        else:
            self.setText(text)
            self.setPlaceholderText('')
