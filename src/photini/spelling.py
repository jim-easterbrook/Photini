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

logger = logging.getLogger(__name__)

if enchant:
    spelling_version = 'PyEnchant ' + enchant.__version__
else:
    spelling_version = None


class SpellCheck(QtCore.QObject):
    new_dict = QtSignal()

    def __init__(self, *arg, **kw):
        super(SpellCheck, self).__init__(*arg, **kw)
        app = QtWidgets.QApplication.instance()
        self.config_store = app.config_store
        self.dictionaries = {}
        self.default_lang = app.locale.uiLanguages()[0]
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
        if self.default_lang in self.dictionaries:
            return self.dictionaries[self.default_lang].tag
        return ''

    @QtSlot(bool)
    @catch_all()
    def enable(self, enabled):
        self.config_store.set('spelling', 'enabled', enabled)
        self.enabled = enabled and bool(enchant)
        self.new_dict.emit()

    def load_dict(self, lang):
        if not (lang and self.enabled):
            return
        if lang in self.dictionaries:
            return
        test = lang.replace('-', '_')
        if test in self.dictionaries:
            self.dictionaries[lang] = self.dictionaries[test]
            return
        for test in test, test.split('_')[0]:
            for code in enchant.list_languages():
                if code.startswith(test):
                    self.dictionaries[lang] = enchant.request_dict(code)
                    return
        self.dictionaries[lang] = self.dictionaries[self.default_lang]
        return

    def set_language(self, code):
        if code:
            logger.debug('Setting dictionary %s', code)
        if not (enchant and code):
            return
        self.default_lang = code
        self.load_dict(code)
        if code and not self.dictionaries[code]:
            logger.warning('Failed to set dictionary %s', code)
        self.config_store.set('spelling', 'language', self.current_language())
        self.new_dict.emit()

    words = re.compile(r"\w+([-'’]\w+)*", flags=re.IGNORECASE | re.UNICODE)

    def find_words(self, text):
        for word in self.words.finditer(text):
            yield word.group(), word.start(), word.end()

    def check(self, word, lang=None):
        if not (word and self.enabled):
            return True
        if word.isnumeric():
            return True
        lang = lang or self.default_lang
        return self.dictionaries[lang].check(word)

    def suggest(self, word, lang=None):
        lang = lang or self.default_lang
        if self.check(word, lang=lang):
            return []
        return self.dictionaries[lang].suggest(word)
