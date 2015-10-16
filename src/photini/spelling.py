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

import os
import re
import shutil
import site
import sys

# avoid "dll Hell" on Windows by copying PyGObject's copies of some dlls
if sys.platform == 'win32':
    enchant_dir = None
    gnome_dir = None
    for name in site.getsitepackages():
        dir_name = os.path.join(name, 'enchant')
        if os.path.isdir(dir_name):
            enchant_dir = dir_name
        dir_name = os.path.join(name, 'gnome')
        if os.path.isdir(dir_name):
            gnome_dir = dir_name
    if enchant_dir and gnome_dir:
        for name in (
                'libenchant-1.dll', 'libglib-2.0-0.dll', 'libgmodule-2.0-0.dll'):
            src = os.path.join(gnome_dir, name)
            if os.path.exists(src):
                shutil.copy(src, enchant_dir)

try:
    import enchant
except ImportError:
    enchant = None

from .pyqt import Qt, QtCore, QtGui, QtWidgets

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
        if not bool(enchant):
            self.dict = None
        elif tag and enchant.dict_exists(tag):
            self.dict = enchant.Dict(tag)
        else:
            self.dict = enchant.Dict()
        if self.dict:
            self.tag = self.dict.tag
        else:
            self.tag = ''
        self.new_dict.emit()

    def available_languages(self):
        if not bool(enchant):
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
        return _spell_check.tag

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
        self.words = re.compile('[\w]+', flags=re.IGNORECASE | re.UNICODE)
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

    def suggestions(self, word):
        if not _spell_check.enabled:
            return []
        if _spell_check.dict.check(word):
            return []
        return _spell_check.dict.suggest(word)

