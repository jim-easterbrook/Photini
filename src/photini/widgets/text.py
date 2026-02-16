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
import re

from photini.pyqt import *
from photini.pyqt import qt_version_info
from photini.types import MD_LangAlt
from photini.widgets import ChoicesContextMenu, DropDownSelector, WidgetMixin

__all__ = ('LangAltWidget', 'MultiLineEdit', 'MultiStringEdit', 'SingleLineEdit')

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class TextHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, parent):
        super(TextHighlighter, self).__init__(parent)
        self.formatters = []

    @catch_all
    def highlightBlock(self, text):
        for formatter in self.formatters:
            formatter.highlight_block(text, self)

    def add_formatter(self, formatter):
        self.formatters.append(formatter)


class TextHighlighterMixin(object):
    _highlighter = None

    def highlighter(self):
        if not self._highlighter:
            self._highlighter = TextHighlighter(self.document())
        return self._highlighter


class SpellCheckFormatter(QtGui.QTextCharFormat):
    def __init__(self, highlighter):
        super(SpellCheckFormatter, self).__init__()
        self.setUnderlineColor(Qt.GlobalColor.red)
        self.setUnderlineStyle(self.UnderlineStyle.SpellCheckUnderline)
        self.spell_check = QtWidgets.QApplication.instance().spell_check
        self.spell_check.new_dict.connect(highlighter.rehighlight)
        highlighter.add_formatter(self)

    def add_spelling_context_menu(self, menu, cursor, callback):
        block_pos = cursor.block().position()
        for word, start, end in self.spell_check.find_words(
                                                    cursor.block().text()):
            if start > cursor.positionInBlock():
                break
            if end <= cursor.positionInBlock():
                continue
            cursor.setPosition(block_pos + start)
            cursor.setPosition(block_pos + end, cursor.MoveMode.KeepAnchor)
            break
        suggestions = self.spell_check.suggest(cursor.selectedText())
        if not suggestions:
            return
        group = QtGui2.QActionGroup(menu)
        sep = menu.insertSeparator(menu.actions()[0])
        for suggestion in suggestions:
            action = QtGui2.QAction(suggestion, parent=group)
            action.setData(cursor)
            menu.insertAction(sep, action)
        group.triggered.connect(callback)

    def highlight_block(self, text, highlighter):
        for word, start, end in self.spell_check.find_words(text):
            if not self.spell_check.check(word):
                highlighter.setFormat(start, end - start, self)


class SpellCheckMixin(TextHighlighterMixin):
    _spell_check = None

    def add_spell_check(self):
        self._spell_check = SpellCheckFormatter(self.highlighter())
        self.context_menus.append(self.add_spelling_context_menu)

    def add_spelling_context_menu(self, menu, event):
        if self.is_multiple() or not self._spell_check:
            return
        self._spell_check.add_spelling_context_menu(
            menu, self.cursorForPosition(event.pos()),
            self._spelling_triggered)

    @QtSlot(QtGui2.QAction)
    @catch_all
    def _spelling_triggered(self, action):
        cursor = action.data()
        cursor.insertText(action.iconText())


class LengthFormatter(QtGui.QTextCharFormat):
    def __init__(self, highlighter, length,
                 length_always=True, length_bytes=True, multi_string=False):
        super(LengthFormatter, self).__init__()
        self.setUnderlineColor(Qt.GlobalColor.blue)
        self.setUnderlineStyle(self.UnderlineStyle.SingleUnderline)
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.length = length
        self.length_always = length_always
        self.length_bytes = length_bytes
        if multi_string:
            # treat each keyword separately
            self.regex = re.compile(r'\s*(.+?)(;|$)')
        else:
            # treat the entire block as one
            self.regex = re.compile(r'(.+)')
        highlighter.add_formatter(self)

    def highlight_block(self, text, highlighter):
        if not text:
            highlighter.setCurrentBlockState(highlighter.previousBlockState())
            return
        length_warning = self.length_always or self.config_store.get(
            'files', 'length_warning', True)
        if length_warning:
            consumed = max(highlighter.previousBlockState(), 0)
            max_len = max(self.length - consumed, 0)
            for match in self.regex.finditer(text):
                start = match.start(1)
                end = match.end(1)
                truncated = text[start:end]
                if self.length_bytes:
                    truncated = truncated.encode('utf-8')
                consumed += len(truncated)
                truncated = truncated[:max_len]
                if self.length_bytes:
                    truncated = truncated.decode('utf-8', errors='ignore')
                start += len(truncated)
                if start < end:
                    highlighter.setFormat(start, end - start, self)
            highlighter.setCurrentBlockState(max(consumed, 0))

    def set_length(self, length):
        self.length = length


class LengthCheckMixin(TextHighlighterMixin):
    _length_check = None

    def add_length_check(self, length, length_always=True, length_bytes=True,
                         multi_string=False):
        if not length:
            return
        self._length_check = LengthFormatter(
            self.highlighter(), length, length_always=length_always,
            length_bytes=length_bytes, multi_string=multi_string)

    def set_length(self, length):
        if self._length_check:
            self._length_check.set_length(length)


class TextEditMixin(ChoicesContextMenu, WidgetMixin):
    def init_mixin(self, key):
        self._key = key
        self._multiple_values = multiple_values()
        self._is_multiple = False
        self.context_menus = [self.add_choices_context_menu]
        if self.isRightToLeft():
            self.set_text_alignment(Qt.AlignmentFlag.AlignRight)
        self.setTabChangesFocus(True)

    def context_menu_event(self, event):
        menu = self.createStandardContextMenu()
        for add_context_menu in self.context_menus:
            add_context_menu(menu, event)
        execute(menu, event.globalPos())

    def set_value(self, value):
        self.set_multiple(multiple=False)
        if value:
            self.setPlainText(str(value))
        else:
            self.clear()

    def set_multiple(self, choices=[], multiple=True):
        self._is_multiple = multiple
        self.choices = [x for x in choices if x]
        if multiple:
            self.setPlaceholderText(self._multiple_values)
            self.clear()
        else:
            self.setPlaceholderText('')

    def is_multiple(self):
        return self._is_multiple and not bool(self.get_value())

    def is_valid(self):
        return not bool(self.placeholderText())

    def value_to_text(self, value):
        return str(value).replace('\n', ' ')


class MultiLineEdit(QtWidgets.QPlainTextEdit, TextEditMixin, SpellCheckMixin,
                    LengthCheckMixin):
    def __init__(self, key, *arg, **kw):
        super(MultiLineEdit, self).__init__(*arg, **kw)
        self.init_mixin(key)

    @catch_all
    def focusOutEvent(self, event):
        self.emit_value()
        super(MultiLineEdit, self).focusOutEvent(event)

    @catch_all
    def keyPressEvent(self, event):
        self.set_multiple(multiple=False)
        super(MultiLineEdit, self).keyPressEvent(event)

    @catch_all
    def contextMenuEvent(self, event):
        self.context_menu_event(event)

    def set_height(self, rows):
        height = QtWidgets.QLineEdit().sizeHint().height()
        height += (rows - 1) * self.fontMetrics().lineSpacing()
        self.setMaximumHeight(height)

    def get_value(self):
        if qt_version_info < (5, 9):
            return self.toPlainText()
        value = self.document().toRawText()
        value = value.replace('\u2029', '\n')
        return value

    def set_text_alignment(self, alignment):
        options = self.document().defaultTextOption()
        options.setAlignment(alignment)
        self.document().setDefaultTextOption(options)


class SingleLineEdit(MultiLineEdit):
    def __init__(self, *arg, **kw):
        super(SingleLineEdit, self).__init__(*arg, **kw)
        self.setFixedHeight(QtWidgets.QLineEdit().sizeHint().height())
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    @catch_all
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return:
            event.ignore()
            return
        super(SingleLineEdit, self).keyPressEvent(event)

    @catch_all
    def insertFromMimeData(self, source):
        self.insertPlainText(source.text().replace('\n', ' '))


class MultiStringEdit(SingleLineEdit):
    def set_value(self, value):
        if isinstance(value, (list, tuple)):
            value = '; '.join(value)
        super(MultiStringEdit, self).set_value(value)

    def get_value(self):
        value = super(MultiStringEdit, self).get_value().split(';')
        value = [x.strip() for x in value]
        return [x for x in value if x]


class LangAltWidget(QtWidgets.QWidget, WidgetMixin):
    def __init__(self, key, multi_line=True, label=None, **kw):
        super(LangAltWidget, self).__init__()
        layout = QtWidgets.QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(
            (layout.alignment() & Qt.AlignmentFlag.AlignHorizontal_Mask)
            | Qt.AlignmentFlag.AlignTop)
        layout.setColumnStretch(1, 1)
        self.setLayout(layout)
        self._key = key
        self.choices = {}
        self.value = MD_LangAlt()
        # label
        if label:
            # put label and lang selector on line above edit box
            layout.addWidget(QtWidgets.QLabel(label), 0, 0)
            edit_pos = 1, 0, 1, 3
            layout.setRowStretch(1, 1)
        else:
            # put lang selector to right of edit box
            edit_pos = 0, 0, 1, 2
        # text edit
        if multi_line:
            self.edit = MultiLineEdit(key, **kw)
        else:
            self.edit = SingleLineEdit(key, **kw)
        self.edit.new_value.connect(self._new_value)
        layout.addWidget(self.edit, *edit_pos)
        # language drop down
        self.long_text = translate('LangAltWidget', 'Language')
        self.short_text = translate('LangAltWidget', 'Lang: ',
                                    'Short abbreviation of "Language: "')
        self.lang = DropDownSelector(
            'lang', with_multiple=False, extendable=True)
        self.lang.setFixedWidth(max(
            width_for_text(self.lang, self.long_text + ('x' * 5)),
            width_for_text(self.lang, self.short_text + 'xx-XX' + ('x' * 5))))
        self.lang.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lang.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lang.new_value.connect(self._change_lang)
        self.lang.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.lang, 0, 2)
        layout.setAlignment(self.lang, Qt.AlignmentFlag.AlignTop)
        self.set_value('')
        if not multi_line:
            self.setFixedHeight(self.sizeHint().height())
        # adopt some child methods ...
        self.add_length_check = self.edit.add_length_check
        self.add_spell_check = self.edit.add_spell_check
        self.is_multiple = self.edit.is_multiple
        self.is_valid = self.edit.is_valid
        self.set_height = self.edit.set_height
        # ... and vice versa
        self.lang.define_new_value = self._define_new_lang

    @catch_all
    def set_enabled(self, enabled):
        self.edit.setEnabled(enabled)
        self.lang.setEnabled(enabled)

    @catch_all
    def setToolTip(self, text):
        self.edit.setToolTip(text)

    @QtSlot(dict)
    @catch_all
    def _change_lang(self, value):
        lang = value['lang']
        if lang == MD_LangAlt.DEFAULT:
            direction = self.layoutDirection()
        else:
            direction = QtCore.QLocale(lang).textDirection()
        if direction == Qt.LayoutDirection.RightToLeft:
            self.edit.set_text_alignment(Qt.AlignmentFlag.AlignRight)
        else:
            self.edit.set_text_alignment(Qt.AlignmentFlag.AlignLeft)
        self.edit.set_value(self.value[lang])

    @QtSlot(dict)
    @catch_all
    def _new_value(self, value):
        value = value[self.edit._key]
        if value in self.choices:
            # value pasted in by <multiple values> context menu
            self.set_value(self.choices[value])
        else:
            default_lang = self.value.default_lang
            new_value = dict(self.value)
            new_value[self.lang.get_value()] = value
            self.value = MD_LangAlt(
                new_value, default_lang=default_lang, strip=False)
        self.emit_value()

    def _regularise_default(self):
        if not self.value[MD_LangAlt.DEFAULT]:
            return True
        prompt = self.locale().bcp47Name()
        if prompt in self.value:
            prompt = None
        self.lang.set_value(MD_LangAlt.DEFAULT)
        self.edit.set_value(self.value[MD_LangAlt.DEFAULT])
        lang, OK = QtWidgets.QInputDialog.getText(
            self, translate('LangAltWidget', 'New language'),
            wrap_text(self, translate(
                'LangAltWidget', 'What language is the current text in?'
                ' Please enter an RFC3066 language tag.'), 2), text=prompt)
        if OK and lang:
            self._set_default_lang(lang)
        return OK

    def _define_new_lang(self):
        if not self._regularise_default():
            return None, None
        prompt = self.locale().bcp47Name()
        if prompt in self.value:
            prompt = None
        lang, OK = QtWidgets.QInputDialog.getText(
            self, translate('LangAltWidget', 'New language'),
            wrap_text(self, translate(
                'LangAltWidget', 'What language would you like to add?'
                ' Please enter an RFC3066 language tag.'), 2), text=prompt)
        if not (OK and lang):
            return None, None
        default_lang = self.value.default_lang
        text = self.value[lang]
        new_value = dict(self.value)
        new_value[lang] = text
        self.value = MD_LangAlt(
            new_value, default_lang=default_lang, strip=False)
        self.emit_value()
        return self.labeled_lang(lang)

    @QtSlot(QtCore.QPoint)
    @catch_all
    def _context_menu(self, pos):
        langs = []
        for n in range(self.lang.count()):
            lang = self.lang.itemData(n)
            if lang and lang != MD_LangAlt.DEFAULT:
                langs.append(lang)
        if not langs:
            return
        default_lang = self.value.default_lang
        menu = QtWidgets.QMenu()
        menu.addAction(translate('LangAltWidget', 'Set default language'))
        for lang in langs:
            action = menu.addAction(lang)
            action.setCheckable(True)
            action.setChecked(lang == default_lang)
        action = execute(menu, self.lang.mapToGlobal(pos))
        if not (action and action.isCheckable()):
            return
        if not self._regularise_default():
            return
        self._set_default_lang(action.text())

    def _set_default_lang(self, lang):
        self.value = MD_LangAlt(self.value, default_lang=lang, strip=False)
        self.emit_value()

    def labeled_lang(self, lang):
        if lang == MD_LangAlt.DEFAULT:
            if len(self.value) == 1:
                return self.long_text, lang
            label = '-'
        else:
            label = lang
        label = self.short_text + label
        return label, lang

    def set_value(self, value):
        self.choices = {}
        self.lang.setEnabled(self.edit.isEnabled())
        self.value = MD_LangAlt(value, strip=False)
        # use current language, if available
        lang = self.lang.get_value()
        if lang not in self.value:
            # choose language from locale
            lang = self.locale().bcp47Name()
            if lang not in self.value:
                base_lang = lang.split('-')[0]
                for lang in self.value:
                    if lang.split('-')[0] == base_lang:
                        break
        if lang in self.value:
            lang = self.value.find_key(lang)
        elif self.value:
            # use the default for this value
            lang = self.value.default_lang
        else:
            self.value = MD_LangAlt(default_lang=lang)
        # set language drop down
        self.lang.set_values(
            [self.labeled_lang(x) for x in self.value.languages()],
            default=lang)
        self._change_lang({'lang': lang})

    def get_value(self):
        return self.value

    def set_multiple(self, choices=[]):
        self.choices = {}
        for choice in choices:
            if choice:
                self.choices[str(choice)] = MD_LangAlt(choice, strip=False)
        self.edit.set_multiple(choices=self.choices.keys())
        self.lang.setEnabled(False)
