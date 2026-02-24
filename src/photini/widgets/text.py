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
from photini.widgets import (ChoicesContextMenu, ComboBox, CompoundWidgetMixin,
                             ContextMenuMixin, WidgetMixin)

__all__ = (
    'LangAltWidget', 'MultiLineEdit', 'MultiStringEdit', 'SingleLineEdit')

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class TextHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, parent):
        super(TextHighlighter, self).__init__(parent)
        self.formatters = []

    @catch_all()
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
        self._lang = None
        highlighter.add_formatter(self)

    def add_spelling_context_menu(self, menu, cursor, callback):
        block = cursor.block()
        block_pos = block.position()
        for word, start, end in self.spell_check.find_words(block.text()):
            if start > cursor.positionInBlock():
                break
            if end <= cursor.positionInBlock():
                continue
            cursor.setPosition(block_pos + start)
            cursor.setPosition(block_pos + end, cursor.MoveMode.KeepAnchor)
            break
        suggestions = self.spell_check.suggest(
            cursor.selectedText(), lang=self._lang)
        if not suggestions:
            return False
        group = QtGui2.QActionGroup(menu)
        sep = menu.actions()[0]
        if not sep.isSeparator():
            sep = menu.insertSeparator(sep)
        for suggestion in suggestions:
            action = QtGui2.QAction(suggestion, parent=group)
            action.setData(cursor)
            menu.insertAction(sep, action)
        group.triggered.connect(callback)
        return True

    def highlight_block(self, text, highlighter):
        for word, start, end in self.spell_check.find_words(text):
            if not self.spell_check.check(word, lang=self._lang):
                highlighter.setFormat(start, end - start, self)

    def set_lang(self, lang):
        if lang == MD_LangAlt.DEFAULT:
            lang = None
        self._lang = lang
        self.spell_check.load_dict(lang)


class SpellCheckMixin(TextHighlighterMixin):
    _spell_check = None

    def add_spell_check(self):
        self._spell_check = SpellCheckFormatter(self.highlighter())
        self.context_menus['B'] = self.add_spelling_context_menu

    def add_spelling_context_menu(self, menu, event):
        if not self._spell_check:
            return False
        return self._spell_check.add_spelling_context_menu(
            menu, self.cursorForPosition(event.pos()),
            self._spelling_triggered)

    @QtSlot(QtGui2.QAction)
    @catch_all()
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


class TextEdit(QtWidgets.QTextEdit, ChoicesContextMenu, WidgetMixin):
    def __init__(self, key, *arg, **kw):
        super(TextEdit, self).__init__(*arg, **kw)
        self._key = key
        self._multiple_values = multiple_values()
        self.context_menus = {'A': self.add_choices_context_menu}
        if self.isRightToLeft():
            self.set_text_alignment(Qt.AlignmentFlag.AlignRight)
        self.setTabChangesFocus(True)
        if self._single_line:
            self.set_height(1)
            self.setLineWrapMode(self.LineWrapMode.NoWrap)
            self.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    @catch_all()
    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        for key in sorted(self.context_menus.keys()):
            add_context_menu = self.context_menus[key]
            if add_context_menu(menu, event):
                break
        execute(menu, event.globalPos())

    @catch_all()
    def focusOutEvent(self, event):
        self.emit_value()
        super(TextEdit, self).focusOutEvent(event)

    @catch_all()
    def insertFromMimeData(self, source):
        text = source.text()
        if self._single_line:
            text = text.replace('\n', ' ')
        self.insertPlainText(text)

    @catch_all()
    def keyPressEvent(self, event):
        if self._single_line and event.key() in (
                Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return
        self.handle_delete_key(event)
        super(TextEdit, self).keyPressEvent(event)
        if self.placeholderText() and self.toPlainText():
            # user has typed something over <multiple values>
            self.setPlaceholderText('')

    def get_value(self):
        if qt_version_info < (5, 9):
            return self.toPlainText()
        value = self.document().toRawText()
        value = value.replace('\u2029', '\n')
        return value

    def is_multiple(self):
        return self.placeholderText() == self._multiple_values

    def is_valid(self):
        return not bool(self.placeholderText())

    def set_height(self, rows):
        height = QtWidgets.QLineEdit().sizeHint().height()
        height += (rows - 1) * self.fontMetrics().lineSpacing()
        if rows == 1:
            self.setFixedHeight(height)
        else:
            self.setMaximumHeight(height)

    def set_multiple(self, choices=[]):
        self.choices = [x for x in choices if x]
        self.setPlaceholderText(self._multiple_values)
        self.clear()

    def set_text_alignment(self, h_alignment):
        options = self.document().defaultTextOption()
        v_alignment = options.alignment() & Qt.AlignmentFlag.AlignVertical_Mask
        options.setAlignment(h_alignment | v_alignment)
        self.document().setDefaultTextOption(options)

    def set_value(self, value, html=False):
        self.setPlaceholderText('')
        if value:
            if html:
                self.setHtml(value)
            else:
                self.setPlainText(str(value))
        else:
            self.clear()

    def value_to_text(self, value):
        if self._single_line:
            return str(value).replace('\n', ' ')
        return str(value)


class MultiLineEdit(TextEdit, SpellCheckMixin, LengthCheckMixin):
    _single_line = False


class SingleLineEdit(TextEdit, SpellCheckMixin, LengthCheckMixin):
    _single_line = True


class MultiStringEdit(SingleLineEdit):
    def set_value(self, value):
        if isinstance(value, (list, tuple)):
            value = '; '.join(value)
        super(MultiStringEdit, self).set_value(value)

    def get_value(self):
        value = super(MultiStringEdit, self).get_value().split(';')
        value = [x.strip() for x in value]
        return [x for x in value if x]


class LangAltWidgetText(TextEdit, SpellCheckMixin, LengthCheckMixin):
    def __init__(self, owner, single_line=True, **kw):
        self._single_line = single_line
        super(LangAltWidgetText, self).__init__('', **kw)
        self._owner = owner
        self.set_lang(None)
        self.set_default(False)
        self.context_menus['Z'] = self._owner.add_all_langs_context_menu

    def get_value_dict(self):
        if self.is_valid():
            result = {self._key: self.get_value()}
            if self.is_default():
                result[MD_LangAlt.DEFAULT] = result[self._key]
            return result
        return {}

    def is_default(self):
        return self._default

    def lang(self):
        return self._key

    def set_default(self, default):
        self._default = default

    def set_lang(self, lang):
        self._key = lang
        if lang:
            if self._spell_check:
                self._spell_check.set_lang(lang)
            locale = QtCore.QLocale(lang)
            option = self.document().defaultTextOption()
            option.setTextDirection(locale.textDirection())
            self.document().setDefaultTextOption(option)

    def _save_data(self, metadata, value):
        if self._key in value:
            metadata[self._key] = value[self._key]
            if self.is_default():
                metadata[MD_LangAlt.DEFAULT] = value[self._key]
        return False


class LangAltEditStack(QtWidgets.QStackedLayout):
    sw_new_value = QtSignal(dict)

    def __init__(self, owner, widget_kw, *arg, **kw):
        super(LangAltEditStack, self).__init__(*arg, **kw)
        self._owner = owner
        self._widget_kw = widget_kw
        self._widget_options = []

    def add_lang(self, lang):
        # find unused text edit
        for idx in range(self.count()):
            widget = self.widget(idx)
            if not widget.lang():
                widget.set_value(None)
                break
        else:
            # create new text edit
            widget = LangAltWidgetText(self._owner, **self._widget_kw)
            for func, arg, kw in self._widget_options:
                getattr(widget, func)(*arg, **kw)
            widget.new_value.connect(self.sw_new_value)
            self.addWidget(widget)
        widget.set_lang(lang)

    def add_length_check(self, *arg, **kw):
        self._widget_options.append(('add_length_check', arg, kw))

    def add_spell_check(self, *arg, **kw):
        self._widget_options.append(('add_spell_check', arg, kw))

    def find_lang(self, lang):
        for idx in range(self.count()):
            widget = self.widget(idx)
            if widget.lang() == lang:
                return widget
        return None

    def get_langs(self):
        langs = []
        default_lang = None
        for idx in range(self.count()):
            widget = self.widget(idx)
            lang = widget.lang()
            if lang:
                if widget.is_default():
                    default_lang = lang
                langs.append(lang)
        return langs, default_lang

    def set_default_lang(self, default_lang):
        for idx in range(self.count()):
            widget = self.widget(idx)
            lang = widget.lang()
            if lang:
                if lang == MD_LangAlt.DEFAULT and lang != default_lang:
                    widget.set_lang(None)
                else:
                    widget.set_default(lang == default_lang)

    def set_height(self, *arg, **kw):
        self._widget_options.append(('set_height', arg, kw))

    def set_langs(self, langs):
        for idx in range(self.count()):
            widget = self.widget(idx)
            widget.set_lang(None)
            widget.set_default(False)
        for lang in langs:
            self.add_lang(lang)

    @QtSlot(str)
    @catch_all()
    def show_lang(self, lang):
        for idx in range(self.count()):
            if self.widget(idx).lang() == lang:
                self.setCurrentIndex(idx)
                break

    def sub_widgets(self):
        for idx in range(self.count()):
            widget = self.widget(idx)
            if widget.lang():
                yield widget


class LangAltSelector(ComboBox):
    add_lang = QtSignal(str)
    show_lang = QtSignal(str)

    def __init__(self, owner, *arg, **kw):
        super(LangAltSelector, self).__init__(*arg, **kw)
        self._owner = owner
        self.long_text = translate('LangAltWidget', 'Language')
        self.short_text = translate('LangAltWidget', 'Lang: ',
                                    'Short abbreviation of "Language: "')
        self.setFixedWidth(max(
            width_for_text(self, self.long_text + ('x' * 5)),
            width_for_text(self, self.short_text + 'xx-XX' + ('x' * 5))))
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.activated.connect(self.lang_activated)
        self.currentIndexChanged.connect(self.current_index_changed)
        self.addItem(translate('Widgets', '<new>'))

    @catch_all()
    def contextMenuEvent(self, event):
        self._owner.lang_selector_context_menu(event)

    @QtSlot(int)
    @catch_all()
    def current_index_changed(self, idx):
        lang = self.itemData(idx)
        if lang:
            self.show_lang.emit(lang)

    @QtSlot(int)
    @catch_all()
    def lang_activated(self, idx):
        if idx < self.count() - 1:
            self.add_lang.emit('')
            return
        # user selected <new>
        prompt = self.locale().uiLanguages()[0]
        if self.findData(prompt) >= 0:
            prompt = None
        lang, OK = QtWidgets.QInputDialog.getText(
            self, translate('LangAltWidget', 'New language'),
            wrap_text(self, translate(
                'LangAltWidget', 'What language would you like to add?'
                ' Please enter an RFC3066 language tag.'), 2), text=prompt)
        if not (OK and lang):
            self.setCurrentIndex(0)
            return
        self.add_lang.emit(lang)

    def set_langs(self, langs, default_lang):
        langs.sort(key=lambda x: x.lower())
        if default_lang in langs:
            langs.remove(default_lang)
            langs.insert(0, default_lang)
        current_lang = self.currentData() or langs[0]
        blocked = self.blockSignals(True)
        while self.count() > 1 + len(langs):
            self.removeItem(0)
        while self.count() < 1 + len(langs):
            self.insertItem(0, '')
        for idx, lang in enumerate(langs):
            if lang == MD_LangAlt.DEFAULT:
                label = self.long_text
            else:
                label = self.short_text + lang
            self.setItemText(idx, label)
            self.setItemData(idx, lang)
        idx = max(self.findData(current_lang), 0)
        self.setCurrentIndex(idx)
        self.blockSignals(blocked)
        self.show_lang.emit(self.currentData())


class LangAltWidget(QtWidgets.QWidget, CompoundWidgetMixin, ContextMenuMixin):
    clipboard_key = 'LangAltWidget'
    dynamic = True

    def __init__(self, key, multi_line=True, label=None, **widget_kw):
        super(LangAltWidget, self).__init__()
        self.app = QtWidgets.QApplication.instance()
        self._key = key
        widget_kw['single_line'] = not multi_line
        layout = QtWidgets.QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(
            (layout.alignment() & Qt.AlignmentFlag.AlignHorizontal_Mask)
            | Qt.AlignmentFlag.AlignTop)
        layout.setColumnStretch(1, 1)
        self.setLayout(layout)
        # label
        if label:
            # put label and lang selector on line above edit box
            layout.addWidget(QtWidgets.QLabel(label), 0, 0)
            edit_pos = 1, 0, 1, 3
            layout.setRowStretch(1, 1)
        else:
            # put lang selector to right of edit box
            edit_pos = 0, 0, 1, 2
        # stack of text edit widgets
        self.edit_stack = LangAltEditStack(self, widget_kw)
        self.edit_stack.sw_new_value.connect(self.sw_new_value)
        layout.addLayout(self.edit_stack, *edit_pos)
        # language drop down
        self.long_text = translate('LangAltWidget', 'Language')
        self.short_text = translate('LangAltWidget', 'Lang: ',
                                    'Short abbreviation of "Language: "')
        self.lang = LangAltSelector(self)
        self.lang.show_lang.connect(self.edit_stack.show_lang)
        self.lang.add_lang.connect(self.add_lang)
        layout.addWidget(self.lang, 0, 2)
        layout.setAlignment(self.lang, Qt.AlignmentFlag.AlignTop)
        if not multi_line:
            self.setFixedHeight(self.sizeHint().height())
        # adopt some child methods
        self.add_length_check = self.edit_stack.add_length_check
        self.add_spell_check = self.edit_stack.add_spell_check
        self.set_height = self.edit_stack.set_height
        self.sub_widgets = self.edit_stack.sub_widgets

    @QtSlot(str)
    @catch_all()
    def add_lang(self, lang):
        if lang:
            self.edit_stack.add_lang(lang)
            self.update_lang_selector()
            self.lang.setCurrentIndex(self.lang.findData(lang))
        self.edit_stack.currentWidget().setFocus()

    def add_all_langs_context_menu(self, menu, event):
        # cut/paste menu for all languages
        sep = menu.insertSection(menu.actions()[0], translate(
            'LangAltWidget', 'This language'))
        temp = QtWidgets.QMenu()
        self.add_copy_paste_context_menu(temp)
        for action in temp.actions():
            temp.removeAction(action)
            action.setParent(menu)
            menu.insertAction(sep, action)
        menu.insertSection(menu.actions()[0], translate(
            'LangAltWidget', 'All languages'))

    def lang_selector_context_menu(self, event):
        menu = QtWidgets.QMenu()
        # set default language
        old_lang = self.lang.currentData()
        widget = self.edit_stack.find_lang(old_lang)
        group = QtGui2.QActionGroup(menu)
        action = QtGui2.QAction(translate(
            'LangAltWidget', 'Make "{language}" the default language.'
            ).format(language=old_lang), parent=group)
        if widget.is_default() or self.edit_stack.find_lang(MD_LangAlt.DEFAULT):
            action.setEnabled(False)
        action.setData(old_lang)
        menu.addAction(action)
        group.triggered.connect(self.set_default_lang)
        # change language
        new_lang = self.locale().uiLanguages()[0]
        group = QtGui2.QActionGroup(menu)
        action = QtGui2.QAction(translate(
            'LangAltWidget', 'Change language to "{language}".'
            ).format(language=new_lang), parent=group)
        if self.edit_stack.find_lang(new_lang):
            action.setEnabled(False)
        action.setData((old_lang, new_lang))
        menu.addAction(action)
        action = QtGui2.QAction(translate(
            'LangAltWidget', 'Change language to other.'), parent=group)
        action.setData((old_lang, None))
        menu.addAction(action)
        group.triggered.connect(self.set_text_lang)
        execute(menu, event.globalPos())

    @QtSlot(QtGui2.QAction)
    @catch_all()
    def set_default_lang(self, action):
        lang = action.data()
        self.edit_stack.set_default_lang(lang)
        self.edit_stack.find_lang(lang).emit_value()
        self.update_lang_selector()

    @QtSlot(QtGui2.QAction)
    @catch_all()
    def set_text_lang(self, action):
        old_lang, new_lang = action.data()
        if not new_lang:
            new_lang, OK = QtWidgets.QInputDialog.getText(
                self, translate('LangAltWidget', 'New language'),
                wrap_text(self, translate(
                    'LangAltWidget', 'What language would you like to change'
                    'to? Please enter an RFC3066 language tag.'), 2))
            if not (OK and new_lang):
                return
        old_widget = self.edit_stack.find_lang(old_lang)
        old_value = old_widget.get_value()
        new_widget = self.edit_stack.find_lang(new_lang)
        if new_widget:
            # merge widget values
            new_value = new_widget.get_value()
            if new_value in old_value:
                text = old_value
            elif old_value in new_value:
                text = new_value
            else:
                text = ' // '.join((new_value, old_value))
        else:
            # change widget lang
            new_widget = old_widget
            text = old_value
        old_widget.set_value(None)
        old_widget.emit_value()
        old_widget.set_lang(None)
        new_widget.set_lang(new_lang)
        if old_widget.is_default():
            new_widget.set_default(True)
        new_widget.set_value(text)
        new_widget.emit_value()
        self.update_lang_selector()
        self.lang.setCurrentIndex(self.lang.findData(new_lang))

    def update_lang_selector(self):
        langs, default_lang = self.edit_stack.get_langs()
        self.lang.set_langs(langs, default_lang)

    def after_load(self):
        langs, default_lang = self.edit_stack.get_langs()
        if self.is_multiple():
            default_lang = MD_LangAlt.DEFAULT
        else:
            default_widget = self.edit_stack.find_lang(MD_LangAlt.DEFAULT)
            if default_widget:
                default_lang = MD_LangAlt.DEFAULT
                default_text = default_widget.get_value()
                for lang in langs:
                    if lang == MD_LangAlt.DEFAULT:
                        continue
                    widget = self.edit_stack.find_lang(lang)
                    if widget.get_value() == default_text:
                        default_lang = lang
                        langs.remove(MD_LangAlt.DEFAULT)
                        break
        self.edit_stack.set_default_lang(default_lang)
        self.lang.set_langs(langs, default_lang)

    def set_default_widget(self, default_idx):
        for idx in range(self.edit_stack.count()):
            self.edit_stack.widget(idx).set_default(idx == default_idx)

    def set_subwidgets(self, keys):
        keys = keys or [self.locale().uiLanguages()[0]]
        self.edit_stack.set_langs(keys)

    def set_enabled(self, enabled):
        self.lang.setEnabled(enabled)
        super(LangAltWidget, self).set_enabled(enabled)
