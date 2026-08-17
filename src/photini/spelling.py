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
import logging
import re
import sys

try:
    import enchant
except ImportError as ex:
    enchant = None
    print(str(ex))

from photini.pyqt import (
    catch_all, QtCore, QtSignal, QtSlot, QtWidgets, qt_version_info)
from photini.types import MD_LangAlt

logger = logging.getLogger(__name__)

if enchant:
    spelling_version = 'PyEnchant ' + enchant.__version__
else:
    spelling_version = None


class Dictionary(QtCore.QObject):
    # one instance per language in use, does the actual checking
    def __init__(self, spell_check, enchant_dict, *arg, **kw):
        super(Dictionary, self).__init__(*arg, **kw)
        self.spell_check = spell_check
        self._dict = enchant_dict

    def copy_dict(self, other):
        # the MD_LangAlt.DEFAULT dictionary can have its language changed
        self._dict = other._dict

    def check(self, word):
        if not (word and self._dict and self.spell_check.enabled):
            return True
        if word.isnumeric():
            return True
        return self._dict.check(word)

    def suggest(self, word):
        if self.check(word):
            return []
        return self._dict.suggest(word)

    def get_lang(self):
        if self._dict:
            return self._dict.tag
        return ''

    words = re.compile(r"\w+([-'’]\w+)*", flags=re.IGNORECASE | re.UNICODE)

    def find_words(self, text):
        for word in self.words.finditer(text):
            yield word.group(), word.start(), word.end()


class SpellCheck(QtCore.QObject):
    # controller class, one instance is created and stored in app.spell_check
    rehighlight = QtSignal()

    def __init__(self, *arg, **kw):
        super(SpellCheck, self).__init__(*arg, **kw)
        app = QtWidgets.QApplication.instance()
        self.config_store = app.config_store
        self.dictionaries = {MD_LangAlt.DEFAULT: Dictionary(self, None)}
        self.enable(self.config_store.get('spelling', 'enabled', True))
        self.set_language(self.config_store.get('spelling', 'language'))

    @staticmethod
    def available_languages():
        if not enchant:
            return None
        result = defaultdict(list)
        for code in enchant.list_languages():
            locale = QtCore.QLocale(code)
            language = locale.languageToString(locale.language())
            if '_' in code and '_ANY' not in code:
                if qt_version_info < (6, 2):
                    country = locale.countryToString(locale.country())
                else:
                    country = locale.territoryToString(locale.territory())
            else:
                country = ''
            result[language].append((country, code))
        for value in result.values():
            value.sort()
        return dict(result) or None

    def current_language(self):
        return self.dictionaries[MD_LangAlt.DEFAULT].get_lang()

    @QtSlot(bool)
    @catch_all()
    def enable(self, enabled):
        self.config_store.set('spelling', 'enabled', enabled)
        self.enabled = enabled
        self.rehighlight.emit()

    def get_dict(self, lang):
        # normalise lang
        if lang:
            lang = lang.replace('_', '-').lower()
        else:
            lang = None
        if lang in self.dictionaries:
            return self.dictionaries[lang]
        if lang and enchant:
            # enchant interprets lang and may return unlisted dictionary
            try:
                dictionary = Dictionary(self, enchant.request_dict(lang))
            except enchant.errors.DictNotFoundError:
                dictionary = self.get_dict(None)
        else:
            dictionary = Dictionary(self, None)
        self.dictionaries[lang] = dictionary
        return self.dictionaries[lang]

    def set_language(self, code):
        if code:
            logger.debug('Setting dictionary %s', code)
        if not (enchant and code):
            return
        dictionary = self.get_dict(code)
        if not dictionary.get_lang():
            logger.warning('Failed to set dictionary %s', code)
        self.dictionaries[MD_LangAlt.DEFAULT].copy_dict(dictionary)
        self.config_store.set('spelling', 'language', self.current_language())
        self.rehighlight.emit()
