#!/usr/bin/env python
# -*- coding: utf-8 -*-

##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-15  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import re

try:
    import enchant
except ImportError:
    enchant = None

from .pyqt import Qt, QtCore, QtGui, QtWidgets
from .utils import Busy, image_types


class SpellCheck(QtCore.QObject):
    new_dict = QtCore.pyqtSignal()

    def __init__(self, *arg, **kw):
        super(SpellCheck, self).__init__(*arg, **kw)
        self.set_dict(None)
        self.enabled = False

    def set_enabled(self, enabled):
        self.enabled = bool(enchant) and enabled
        self.new_dict.emit()

    def set_dict(self, tag):
        if tag is None or not enchant.dict_exists(tag):
            self.dict = enchant.Dict()
        else:
            self.dict = enchant.Dict(tag)
        self.new_dict.emit()

    def available_languages(self):
        if enchant is None:
            return []
        result = enchant.list_languages()
        result.sort()
        return result


# one SpellCheck object for the entire application
_spell_check = SpellCheck()


class SpellingManager(QtCore.QObject):
    # configure the application's SpellCheck object
    def __init__(self, config_store, *arg, **kw):
        super(SpellingManager, self).__init__(*arg, **kw)
        self.config_store = config_store
        self.enable(eval(self.config_store.get('spelling', 'enabled', 'True')))
        self.set_dict(self.config_store.get('spelling', 'language'))
        # adopt some SpellCheck methods
        self.available_languages = _spell_check.available_languages

    def current_language(self):
        return _spell_check.dict.tag

    def enabled(self):
        return _spell_check.enabled

    @QtCore.pyqtSlot(bool)
    def enable(self, enabled):
        _spell_check.set_enabled(enabled)
        self.config_store.set('spelling', 'enabled', str(self.enabled()))

    @QtCore.pyqtSlot(QtWidgets.QAction)
    def set_language(self, action):
        self.set_dict(action.text())

    def set_dict(self, tag):
        _spell_check.set_dict(tag)
        self.config_store.set('spelling', 'language', self.current_language())


class SpellingHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, *arg, **kw):
        super(SpellingHighlighter, self).__init__(*arg, **kw)
        self.words = re.compile('(?iu)[\w\']+')
        _spell_check.new_dict.connect(self.rehighlight)

    def highlightBlock(self, text):
        if not _spell_check.enabled:
            return
        formatter = QtGui.QTextCharFormat()
        formatter.setUnderlineColor(Qt.red)
        formatter.setUnderlineStyle(QtGui.QTextCharFormat.SpellCheckUnderline)
        for word in self.words.finditer(text):
            if not _spell_check.dict.check(word.group()):
                self.setFormat(
                    word.start(), word.end() - word.start(), formatter)

