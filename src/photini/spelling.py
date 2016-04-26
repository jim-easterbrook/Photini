#!/usr/bin/env python
# -*- coding: utf-8 -*-

##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-16  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import os
import re
import site
import sys

logger = logging.getLogger(__name__)

# avoid "dll Hell" on Windows by getting PyEnchant to use PyGObject's
# copy of libenchant and associated libraries
if sys.platform == 'win32':
    # disable PyEnchant's forced use of its bundled DLLs
    sys.platform = 'win32x'
    # add gnome DLLs to PATH
    for name in site.getsitepackages():
        gnome_path = os.path.join(name, 'gnome')
        if os.path.isdir(gnome_path):
            os.environ['PATH'] = gnome_path + ';' + os.environ['PATH']
            break

try:
    import enchant
    enchant_version = 'enchant {}'.format(enchant.__version__)
except ImportError:
    enchant = None
    enchant_version = None

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

from .configstore import config_store
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
        if tag:
            logger.info('Setting dictionary %s', tag)
        if not bool(enchant):
            self.dict = None
        elif tag and enchant.dict_exists(tag):
            self.dict = enchant.Dict(tag)
        else:
            self.dict = None
        if self.dict:
            self.tag = self.dict.tag
        else:
            if tag:
                logger.warning('Failed to set dictionary %s', tag)
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
    def __init__(self, *arg, **kw):
        super(SpellingManager, self).__init__(*arg, **kw)
        self.enable(eval(config_store.get('spelling', 'enabled', 'True')))
        self.set_dict(config_store.get('spelling', 'language'))
        # adopt some SpellCheck methods
        self.available_languages = _spell_check.available_languages

    def current_language(self):
        return _spell_check.tag

    def enabled(self):
        return _spell_check.enabled

    @QtCore.pyqtSlot(bool)
    def enable(self, enabled):
        _spell_check.set_enabled(enabled)
        config_store.set('spelling', 'enabled', str(self.enabled()))

    @QtCore.pyqtSlot(QtWidgets.QAction)
    def set_language(self, action):
        self.set_dict(action.text().replace('&', ''))

    def set_dict(self, tag):
        _spell_check.set_dict(tag)
        config_store.set('spelling', 'language', self.current_language())


class SpellingHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, *arg, **kw):
        super(SpellingHighlighter, self).__init__(*arg, **kw)
        self.words = re.compile('[\w]+', flags=re.IGNORECASE | re.UNICODE)
        _spell_check.new_dict.connect(self.rehighlight)

    def highlightBlock(self, text):
        if not (_spell_check.enabled and _spell_check.dict):
            return
        formatter = QtGui.QTextCharFormat()
        formatter.setUnderlineColor(Qt.red)
        formatter.setUnderlineStyle(QtGui.QTextCharFormat.SpellCheckUnderline)
        for word in self.words.finditer(text):
            if not _spell_check.dict.check(word.group()):
                self.setFormat(
                    word.start(), word.end() - word.start(), formatter)

    def suggestions(self, word):
        if not (_spell_check.enabled and _spell_check.dict):
            return []
        if _spell_check.dict.check(word):
            return []
        return _spell_check.dict.suggest(word)

