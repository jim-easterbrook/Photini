# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-21  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import logging
import re
import sys

import photini.filemetadata # to find out if GObject is being used
from photini.pyqt import catch_all, QtCore, QtSignal, QtSlot, QtWidgets

enchant = None
Gspell = None

def import_enchant():
    global enchant
    # avoid "dll Hell" on Windows by getting PyEnchant to use GObject's
    # copy of libenchant and associated libraries
    if sys.platform == 'win32' and 'gi.repository' in sys.modules:
        # disable PyEnchant's forced use of its bundled DLLs
        sys.platform = 'win32x'
    try:
        import enchant
    except ImportError as ex:
        print(str(ex))
    if sys.platform == 'win32x':
        # reset sys.platform
        sys.platform = 'win32'

def import_Gspell():
    global gi, using_pgi, GSListPtr_to_list, GLib, GObject, Gspell
    try:
        from photini.gi import gi, using_pgi, GSListPtr_to_list
        gi.require_version('Gspell', '1')
        from gi.repository import GLib, GObject, Gspell
    except Exception as ex:
        print(str(ex))

if 'gi.repository' in sys.modules:
    # already using GObject, so its spell checker is "cheap"
    import_Gspell()

if not Gspell:
    # if not using GObject, PyEnchant is lighter weight
    import_enchant()

if not enchant and not Gspell:
    # use GObject, whatever the cost
    import_Gspell()

logger = logging.getLogger(__name__)

if enchant:
    spelling_version = 'PyEnchant ' + enchant.__version__
elif Gspell:
    spelling_version = 'Gspell {}, {} {}, GObject {}, GLib {}.{}.{}'.format(
        Gspell._version, ('PyGObject', 'pgi')[using_pgi],
        gi.__version__, GObject._version,
        GLib.MAJOR_VERSION, GLib.MINOR_VERSION, GLib.MICRO_VERSION)
else:
    spelling_version = None


class SpellCheck(QtCore.QObject):
    new_dict = QtSignal()

    def __init__(self, *arg, **kw):
        super(SpellCheck, self).__init__(*arg, **kw)
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.enable(self.config_store.get('spelling', 'enabled', True))
        self.set_language(self.config_store.get('spelling', 'language'))

    @staticmethod
    def available_languages():
        result = defaultdict(list)
        if Gspell:
            for lang in Gspell.Language.get_available():
                code = lang.get_code()
                name = lang.get_name()
                match = re.match('(.+)\s+\((.+?)\)', name)
                if match:
                    language = match.group(1)
                    country = match.group(2)
                    if country == 'any':
                        country = ''
                else:
                    language = name
                    country = ''
                result[language].append((country, code))
        elif enchant:
            for code in enchant.list_languages():
                locale = QtCore.QLocale(code)
                language = locale.languageToString(locale.language())
                if '_' in code and '_ANY' not in code:
                    country = locale.countryToString(locale.country())
                else:
                    country = ''
                result[language].append((country, code))
        else:
            return None
        for value in result.values():
            value.sort()
        return dict(result) or None

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
        self.config_store.set('spelling', 'enabled', enabled)
        self.enabled = enabled and bool(Gspell or enchant)
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
        else:
            return
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
        if word.isnumeric():
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
