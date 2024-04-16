##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.enable(self.config_store.get('spelling', 'enabled', True))
        self.set_language(self.config_store.get('spelling', 'language'))

    @staticmethod
    def available_languages():
        result = defaultdict(list)
        if enchant:
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
        else:
            return None
        for value in result.values():
            value.sort()
        return dict(result) or None

    def current_language(self):
        if not self.dict:
            return ''
        if enchant:
            return self.dict.tag
        return ''

    @QtSlot(bool)
    @catch_all
    def enable(self, enabled):
        self.config_store.set('spelling', 'enabled', enabled)
        self.enabled = enabled and bool(enchant)
        self.new_dict.emit()

    def set_language(self, code):
        if code:
            logger.debug('Setting dictionary %s', code)
        self.dict = None
        if enchant:
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
        if enchant:
            return self.dict.check(word)
        return True

    def suggest(self, word):
        if self.check(word):
            return []
        if enchant:
            return self.dict.suggest(word)
        return []
