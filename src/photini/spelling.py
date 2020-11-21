# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-20  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import logging
import re
import sys

from photini.gi import Gspell, GSListPtr_to_list
from photini.pyqt import catch_all, QtCore, QtSignal, QtSlot, QtWidgets

spelling_version = None

if not Gspell:
    # avoid "dll Hell" on Windows by getting PyEnchant to use GObject's
    # copy of libenchant and associated libraries
    if sys.platform == 'win32':
        # disable PyEnchant's forced use of its bundled DLLs
        sys.platform = 'win32x'
    try:
        import enchant
        spelling_version = 'enchant ' + enchant.__version__
    except ImportError:
        enchant = None
    if sys.platform == 'win32x':
        # reset sys.platform
        sys.platform = 'win32'

logger = logging.getLogger(__name__)

class SpellCheck(QtCore.QObject):
    new_dict = QtSignal()

    def __init__(self, *arg, **kw):
        super(SpellCheck, self).__init__(*arg, **kw)
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.enable(eval(self.config_store.get('spelling', 'enabled', 'True')))
        self.set_language(self.config_store.get('spelling', 'language'))

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
        else:
            return None
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

    @QtSlot(bool)
    @catch_all
    def enable(self, enabled):
        self.enabled = enabled and bool(Gspell or enchant)
        self.config_store.set('spelling', 'enabled', str(self.enabled))
        self.new_dict.emit()

    def set_language(self, code):
        if code:
            logger.debug('Setting dictionary %s', code)
        self.dict = None
        if Gspell:
            if code:
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
            return self.dict.check_word(word, -1)
        if enchant:
            return self.dict.check(word)
        return True

    def suggest(self, word):
        if self.check(word):
            return []
        if Gspell:
            return GSListPtr_to_list(self.dict.get_suggestions(word, -1))
        if enchant:
            return self.dict.suggest(word)
        return []
