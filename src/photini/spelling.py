#!/usr/bin/env python
# -*- coding: utf-8 -*-

##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-18  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import ctypes
import logging
import os
import re
import site
import sys

try:
    import pgi
    pgi.install_as_gi()
    using_pgi = True
except ImportError:
    using_pgi = False
import gi
try:
    gi.require_version('Gspell', '1')
except ValueError:
    pass
spelling_version = None
try:
    from gi.repository import GLib, Gspell
    spelling_version = 'Gspell ' + Gspell._version
except ImportError:
    Gspell = None

from photini.pyqt import safe_slot

logger = logging.getLogger(__name__)

if not Gspell:
    # avoid "dll Hell" on Windows by getting PyEnchant to use GObject's
    # copy of libenchant and associated libraries
    if sys.platform == 'win32':
        # disable PyEnchant's forced use of its bundled DLLs
        sys.platform = 'win32x'
        # add gnome DLLs to PATH
        for name in site.getsitepackages():
            gnome_path = os.path.join(name, 'gnome')
            if os.path.isdir(gnome_path) and gnome_path not in os.environ['PATH']:
                os.environ['PATH'] = gnome_path + ';' + os.environ['PATH']
                break

    try:
        import enchant
        spelling_version = 'enchant ' + enchant.__version__
    except ImportError:
        enchant = None

    if sys.platform == 'win32x':
        # reset sys.platform
        sys.platform = 'win32'
        # using PyGObject's copy of libenchant means it won't find the
        # dictionaries installed with PyEnchant
        if enchant:
            for name in site.getsitepackages():
                dict_path = os.path.join(
                    name, 'enchant', 'share', 'enchant', 'myspell')
                if os.path.isdir(dict_path):
                    enchant.set_param('enchant.myspell.dictionary.path', dict_path)
                    break

from photini.pyqt import Qt, QtCore, QtGui, QtWidgets

class SpellCheck(QtCore.QObject):
    new_dict = QtCore.pyqtSignal()

    def __init__(self, *arg, **kw):
        super(SpellCheck, self).__init__(*arg, **kw)
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.enable(eval(self.config_store.get('spelling', 'enabled', 'True')))
        self.set_dict(self.config_store.get('spelling', 'language'))

    @staticmethod
    def available_languages():
        result = []
        if Gspell:
            for lang in Gspell.Language.get_available():
                result.append((lang.get_name(), lang.get_code()))
        elif enchant:
            languages = enchant.list_languages()
            languages.sort()
            for lang in languages:
                result.append((lang, lang))
        return result

    def current_language(self):
        if not self.dict:
            return ''
        if Gspell:
            language = self.dict.get_language()
            if language:
                return language.get_code()
        elif enchant:
            return self.dict.tag
        return ''

    @safe_slot(bool)
    def enable(self, enabled):
        self.enabled = enabled and bool(Gspell or enchant)
        self.config_store.set('spelling', 'enabled', str(self.enabled))
        self.new_dict.emit()

    @safe_slot(QtWidgets.QAction)
    def set_language(self, action):
        self.set_dict(action.data())

    def set_dict(self, code):
        if code:
            logger.debug('Setting dictionary %s', code)
        self.dict = None
        if Gspell:
            self.dict = Gspell.Checker.new(Gspell.Language.lookup(code))
        elif enchant:
            if code and enchant.dict_exists(code):
                self.dict = enchant.Dict(code)
        if code and not self.dict:
            logger.warning('Failed to set dictionary %s', code)
        self.config_store.set('spelling', 'language', self.current_language())
        self.new_dict.emit()

    words = re.compile(r"\w+([-'’]\w+)*", flags=re.IGNORECASE | re.UNICODE)

    def find_words(self, text):
        for word in self.words.finditer(text):
            yield word.group(), word.start(), word.end()

    def check(self, word):
        if not (word and self.enabled and self.dict):
            return True
        if Gspell:
            return self.dict.check_word(word, len(word.encode('utf_8')))
        elif enchant:
            return self.dict.check(word)

    def suggest(self, word):
        if self.check(word):
            return []
        if Gspell:
            suggestions = self.dict.get_suggestions(word, len(word.encode('utf_8')))
            if using_pgi:
                result = []
                for i in range(suggestions.length):
                    c_str = ctypes.c_char_p(suggestions.nth_data(i))
                    result.append(c_str.value.decode('utf_8'))
                return result
            else:
                return suggestions
        elif enchant:
            return self.dict.suggest(word)
