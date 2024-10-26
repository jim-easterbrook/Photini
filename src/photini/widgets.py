##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2022-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import logging
import re

from photini.pyqt import *
from photini.pyqt import qt_version_info
from photini.types import MD_LangAlt

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class WidgetMixin(object):
    new_value = QtSignal(dict)

    @QtSlot()
    @catch_all
    def emit_value(self):
        if not self.is_multiple():
            self.new_value.emit(self.get_value_dict())

    def get_value_dict(self):
        if self.is_multiple():
            return {}
        return {self._key: self.get_value()}

    def set_value_list(self, values):
        if not values:
            self.setEnabled(False)
            self.set_value(None)
            return
        self.setEnabled(True)
        choices = []
        for value_dict in values:
            value = None
            if self._key in value_dict:
                value = value_dict[self._key]
            if value not in choices:
                choices.append(value)
        if len(choices) > 1:
            self.set_multiple(choices=[x for x in choices if x])
        else:
            self.set_value(choices and choices[0])


class ComboBox(QtWidgets.QComboBox):
    def __init__(self, *args, **kwds):
        super(ComboBox, self).__init__(*args, **kwds)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    @catch_all
    def wheelEvent(self, event):
        if self.hasFocus():
            return super(ComboBox, self).wheelEvent(event)
        event.ignore()

    def set_dropdown_width(self):
        width = 0
        for idx in range(self.count()):
            width = max(width, width_for_text(self, self.itemText(idx) + 'xx'))
        margin = self.view().verticalScrollBar().sizeHint().width()
        self.view().setMinimumWidth(width + margin)


class Label(QtWidgets.QLabel):
    def __init__(self, *args, lines=1, layout=None, **kwds):
        super(Label, self).__init__(*args, **kwds)
        layout = layout or QtWidgets.QFormLayout()
        # match text alignment to form layout
        align_h = (layout.labelAlignment()
                   & Qt.AlignmentFlag.AlignHorizontal_Mask)
        self.setAlignment(align_h | Qt.AlignmentFlag.AlignTop)
        padding = (QtWidgets.QLineEdit().sizeHint().height() -
                   self.sizeHint().height()) // 2
        margins = self.contentsMargins()
        margins.setTop(margins.top() + padding)
        self.setContentsMargins(margins)
        if lines != 1:
            self.setText(wrap_text(self, self.text(), lines))


class PushButton(QtWidgets.QPushButton):
    def __init__(self, *args, lines=1, **kwds):
        super(PushButton, self).__init__(*args, **kwds)
        if lines != 1:
            self.setText(wrap_text(self, self.text(), lines))


class CompactButton(QtWidgets.QPushButton):
    def __init__(self, *args, **kwds):
        super(CompactButton, self).__init__(*args, **kwds)
        if QtWidgets.QApplication.style().objectName() in ('breeze',):
            self.setStyleSheet('padding: 2px;')
        scale_font(self, 80)


class DropDownSelector(ComboBox, WidgetMixin):
    def __init__(self, key, values=[], default=None,
                 with_multiple=True, extendable=False, ordered=False):
        super(DropDownSelector, self).__init__()
        self._key = key
        self._with_multiple = with_multiple
        self._extendable = extendable
        self._ordered = ordered
        self._old_idx = 0
        self.setSizeAdjustPolicy(
            self.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.set_values(values, default=default)
        self.currentIndexChanged.connect(self._index_changed)

    def add_item(self, text, data, adjust_width=True):
        idx = self.findText(text)
        if idx >= 0:
            return idx
        idx = self._last_idx()
        if self._ordered:
            for n in range(idx):
                if self.itemText(n).lower() > text.lower():
                    idx = n
                    break
        blocked = self.blockSignals(True)
        self.insertItem(idx, text, data)
        self.blockSignals(blocked)
        if adjust_width:
            self.set_dropdown_width()
        return idx

    def remove_item(self, data, adjust_width=True):
        idx = self.findData(data)
        if idx < 0:
            return
        blocked = self.blockSignals(True)
        self.removeItem(idx)
        self.blockSignals(blocked)

    def set_values(self, values, default=None):
        blocked = self.blockSignals(True)
        self.clear()
        if self._extendable:
            self.addItem(translate('Widgets', '<new>'))
        if self._with_multiple:
            self.addItem(multiple_values())
            self.setItemData(self.count() - 1, '', Qt.ItemDataRole.UserRole - 1)
        for text, data in values:
            self.add_item(text, data, adjust_width=False)
        self.set_dropdown_width()
        self.blockSignals(blocked)
        if default is not None:
            self.set_value(default)

    def get_value(self):
        return self.itemData(self.currentIndex())

    def set_value(self, value):
        self._old_idx = self.findData(value)
        if self._old_idx < 0:
            self._old_idx = self.add_item(self.data_to_text(value), value)
        blocked = self.blockSignals(True)
        self.setCurrentIndex(self._old_idx)
        self.blockSignals(blocked)

    def data_to_text(self, data):
        return str(data)

    def is_multiple(self):
        return self._with_multiple and self.currentIndex() == self.count() - 1

    def set_multiple(self, choices=[]):
        if self._with_multiple:
            blocked = self.blockSignals(True)
            self._old_idx = self.count() - 1
            self.setCurrentIndex(self._old_idx)
            self.blockSignals(blocked)

    @catch_all
    def findData(self, data):
        # Qt's findData only works with simple types
        for n in range(self._last_idx()):
            if self.itemData(n) == data:
                return n
        return -1

    @QtSlot(int)
    @catch_all
    def _index_changed(self, idx):
        if idx < self._last_idx():
            # normal item selection
            self._old_idx = idx
            self.emit_value()
            return
        # user must have clicked '<new>'
        blocked = self.blockSignals(True)
        self.setCurrentIndex(self._old_idx)
        self.blockSignals(blocked)
        text, data = self.define_new_value()
        if not text:
            return
        blocked = self.blockSignals(True)
        self._old_idx = self.findText(text)
        if self._old_idx >= 0:
            # update existing item
            self.setItemData(self._old_idx, data)
        else:
            # add new item
            self._old_idx = self.add_item(text, data)
        self.setCurrentIndex(self._old_idx)
        self.blockSignals(blocked)
        self.emit_value()

    def _last_idx(self):
        idx = self.count()
        if self._extendable:
            idx -= 1
        if self._with_multiple:
            idx -= 1
        return idx


class TextHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, spelling, length, length_always, length_bytes,
                 multi_string, parent):
        super(TextHighlighter, self).__init__(parent)
        self.config_store = QtWidgets.QApplication.instance().config_store
        if spelling:
            self.spell_check = QtWidgets.QApplication.instance().spell_check
            self.spell_check.new_dict.connect(self.rehighlight)
            self.spell_formatter = QtGui.QTextCharFormat()
            self.spell_formatter.setUnderlineColor(Qt.GlobalColor.red)
            self.spell_formatter.setUnderlineStyle(
                QtGui.QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
            self.find_words = self.spell_check.find_words
            self.suggest = self.spell_check.suggest
        else:
            self.spell_check = None
        if length:
            self._length = {
                'length': length, 'always': length_always,
                'bytes': length_bytes, 'formatter': QtGui.QTextCharFormat()}
            self._length['formatter'].setUnderlineColor(Qt.GlobalColor.blue)
            self._length['formatter'].setUnderlineStyle(
                QtGui.QTextCharFormat.UnderlineStyle.SingleUnderline)
            if multi_string:
                # treat each keyword separately
                self._length['regex'] = re.compile(r'\s*(.+?)(;|$)')
            else:
                # treat the entire block as one
                self._length['regex'] = re.compile(r'(.+)')
        else:
            self._length = None

    @catch_all
    def highlightBlock(self, text):
        if not text:
            if self._length:
                self.setCurrentBlockState(self.previousBlockState())
            return
        if self._length:
            length_warning = self._length['always'] or self.config_store.get(
                'files', 'length_warning', True)
            if length_warning:
                consumed = max(self.previousBlockState(), 0)
                max_len = max(self._length['length'] - consumed, 0)
                for match in self._length['regex'].finditer(text):
                    start = match.start(1)
                    end = match.end(1)
                    truncated = text[start:end]
                    if self._length['bytes']:
                        truncated = truncated.encode('utf-8')
                    consumed += len(truncated)
                    truncated = truncated[:max_len]
                    if self._length['bytes']:
                        truncated = truncated.decode('utf-8', errors='ignore')
                    start += len(truncated)
                    if start < end:
                        self.setFormat(
                            start, end - start, self._length['formatter'])
                self.setCurrentBlockState(max(consumed, 0))
        if self.spell_check:
            for word, start, end in self.find_words(text):
                if not self.spell_check.check(word):
                    self.setFormat(start, end - start, self.spell_formatter)


class TextEditMixin(WidgetMixin):
    def init_mixin(self, key, spell_check, length_check, length_always,
                   length_bytes, multi_string, min_width):
        self._key = key
        self._multiple_values = multiple_values()
        self._is_multiple = False
        self.spell_check = spell_check
        self.highlighter = TextHighlighter(
            spell_check, length_check, length_always, length_bytes,
            multi_string, self.document())
        if min_width:
            self.setMinimumWidth(width_for_text(self, 'x' * min_width))
        if self.isRightToLeft():
            self.set_text_alignment(Qt.AlignmentFlag.AlignRight)
        self.setTabChangesFocus(True)

    def context_menu_event(self, event):
        menu = self.createStandardContextMenu()
        suggestion_group = QtGui2.QActionGroup(menu)
        if self._is_multiple:
            if self.choices:
                sep = menu.insertSeparator(menu.actions()[0])
                fm = menu.fontMetrics()
                for suggestion in self.choices:
                    label = str(suggestion).replace('\n', ' ')
                    label = fm.elidedText(
                        label, Qt.TextElideMode.ElideMiddle, self.width())
                    action = QtGui2.QAction(label, suggestion_group)
                    action.setData(suggestion)
                    menu.insertAction(sep, action)
        elif self.spell_check:
            cursor = self.cursorForPosition(event.pos())
            block_pos = cursor.block().position()
            for word, start, end in self.highlighter.find_words(
                                                        cursor.block().text()):
                if start > cursor.positionInBlock():
                    break
                if end <= cursor.positionInBlock():
                    continue
                cursor.setPosition(block_pos + start)
                cursor.setPosition(block_pos + end, cursor.MoveMode.KeepAnchor)
                break
            suggestions = self.highlighter.suggest(cursor.selectedText())
            if suggestions:
                sep = menu.insertSeparator(menu.actions()[0])
                for suggestion in suggestions:
                    action = QtGui2.QAction(suggestion, suggestion_group)
                    menu.insertAction(sep, action)
        action = execute(menu, event.globalPos())
        if action and action.actionGroup() == suggestion_group:
            if self._is_multiple:
                self.set_value(action.data())
                self.emit_value()
            else:
                cursor.setPosition(block_pos + start)
                cursor.setPosition(block_pos + end, cursor.MoveMode.KeepAnchor)
                cursor.insertText(action.iconText())

    def set_length(self, length):
        self.highlighter._length['length'] = length

    def set_value(self, value):
        self.set_multiple(multiple=False)
        if value:
            self.setPlainText(str(value))
        else:
            self.clear()

    def set_multiple(self, choices=[], multiple=True):
        self._is_multiple = multiple
        self.choices = list(choices)
        if multiple:
            self.setPlaceholderText(self._multiple_values)
            self.clear()
        else:
            self.setPlaceholderText('')

    def is_multiple(self):
        return self._is_multiple and not bool(self.get_value())


class MultiLineEdit(QtWidgets.QPlainTextEdit, TextEditMixin):
    def __init__(self, key, *arg, spell_check=False, length_check=None,
                 multi_string=False, length_always=False, length_bytes=True,
                 min_width=None, **kw):
        super(MultiLineEdit, self).__init__(*arg, **kw)
        self.init_mixin(key,spell_check, length_check, length_always,
                        length_bytes, multi_string, min_width)

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


class Slider(QtWidgets.QSlider, WidgetMixin):
    def __init__(self, key, *arg, **kw):
        super(Slider, self).__init__(*arg, **kw)
        self._key = key
        self._is_multiple = False
        self.sliderPressed.connect(self.slider_pressed)

    @catch_all
    def focusOutEvent(self, event):
        self.emit_value()
        super(Slider, self).focusOutEvent(event)

    @QtSlot()
    @catch_all
    def slider_pressed(self):
        self._is_multiple = False

    def get_value(self):
        return self.value()

    def set_value(self, value):
        self._is_multiple = False
        if value is not None:
            self.setValue(value)

    def set_multiple(self, choices=[]):
        self._is_multiple = True
        value = self.value()
        for choice in choices:
            if choice is not None:
                value = max(value, choice)
        self.setValue(value)

    def is_multiple(self):
        return self._is_multiple


class StartStopButton(QtWidgets.QPushButton):
    click_start = QtSignal()
    click_stop = QtSignal()

    def __init__(self, start_text, stop_text, lines=1):
        super(StartStopButton, self).__init__()
        if lines != 1:
            start_text = wrap_text(self, start_text, lines)
            stop_text = wrap_text(self, stop_text, lines)
        self.start_text = start_text
        self.stop_text = stop_text
        self.checked = False
        self.clicked.connect(self.do_clicked)
        # get a size big enough for either text
        self.setText(self.stop_text)
        stop_size = super(StartStopButton, self).sizeHint()
        self.setText(self.start_text)
        start_size = super(StartStopButton, self).sizeHint()
        self.minimum_size = stop_size.expandedTo(start_size)

    @catch_all
    def sizeHint(self):
        return self.minimum_size

    def is_checked(self):
        return self.checked

    def set_checked(self, value):
        self.checked = value
        if self.checked:
            self.setText(self.stop_text)
        else:
            self.setText(self.start_text)

    @QtSlot()
    def do_clicked(self):
        if self.checked:
            self.click_stop.emit()
        else:
            self.click_start.emit()


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
        self.is_multiple = self.edit.is_multiple
        self.set_height = self.edit.set_height
        # ... and vice versa
        self.lang.define_new_value = self._define_new_lang

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
            self.value = self.choices[value]
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
        self.lang.setEnabled(True)
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
            self.choices[str(choice)] = MD_LangAlt(choice, strip=False)
        self.edit.set_multiple(choices=self.choices.keys())
        self.lang.setEnabled(False)


class AugmentSpinBoxBase(WidgetMixin):
    def __init__(self, *arg, **kw):
        self._is_multiple = False
        self._prefix = ''
        self._suffix = ''
        super(AugmentSpinBoxBase, self).__init__(*arg, **kw)
        if self.isRightToLeft():
            self.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.set_value(None)
        self.editingFinished.connect(self.emit_value)

    class ContextAction(QtGui2.QAction):
        def __init__(self, value, *arg, **kw):
            super(AugmentSpinBoxBase.ContextAction, self).__init__(*arg, **kw)
            self.setData(value)
            self.triggered.connect(self.set_value)

        @QtSlot()
        @catch_all
        def set_value(self):
            self.parent().set_value(self.data())
            self.parent().emit_value()

    def context_menu_event(self):
        if self.is_multiple() and self.choices:
            QtCore.QTimer.singleShot(0, self.extend_context_menu)

    @QtSlot()
    @catch_all
    def extend_context_menu(self):
        menu = self.findChild(QtWidgets.QMenu)
        if not menu:
            return
        sep = menu.insertSeparator(menu.actions()[0])
        for suggestion in self.choices:
            menu.insertAction(sep, self.ContextAction(
                suggestion, text=self.textFromValue(suggestion), parent=self))

    def fix_up(self):
        if self.is_multiple():
            return True
        if self.cleanText():
            return False
        # user has deleted the value
        self.set_value(None)
        return True

    def init_stepping(self):
        if self.get_value() is None:
            self.setValue(self.default_value)

    def get_value(self):
        value = self.value()
        if value == self.minimum() and self.specialValueText():
            value = None
        return value

    def set_value(self, value):
        self.set_not_multiple()
        if value is None:
            self.setValue(self.minimum())
            self.setSpecialValueText(' ')
        else:
            self.setSpecialValueText('')
            self.setValue(value)


class AugmentDateTime(AugmentSpinBoxBase):
    def set_not_multiple(self):
        if self._is_multiple:
            self._is_multiple = False
            self.set_value(self.default_value)

    def set_multiple(self, choices=[]):
        self.choices = list(filter(None, choices))
        self._is_multiple = True
        self.setValue(self.minimum())
        self.setSpecialValueText(self.multiple)

    def is_multiple(self):
        return self._is_multiple and self.value() == self.minimum()


class AugmentSpinBox(AugmentSpinBoxBase):
    def set_not_multiple(self):
        if self._is_multiple:
            self._is_multiple = False
            self.set_value(self.default_value)
            if self._prefix:
                self.setPrefix(self._prefix)
            if self._suffix:
                self.setSuffix(self._suffix)
            self.lineEdit().setPlaceholderText('')

    def set_multiple(self, choices=[]):
        self.choices = list(filter(None, choices))
        self._is_multiple = True
        if self._prefix:
            self.setPrefix('')
        if self._suffix:
            self.setSuffix('')
        self.lineEdit().setPlaceholderText(self.multiple)
        self.clear()

    def is_multiple(self):
        return self._is_multiple and bool(self.lineEdit().placeholderText())

    def set_prefix(self, prefix):
        self._prefix = prefix
        self.setPrefix(prefix)

    def set_suffix(self, suffix):
        self._suffix = suffix
        self.setSuffix(suffix)


class LatLongDisplay(AugmentSpinBox, QtWidgets.QAbstractSpinBox):
    def __init__(self, *args, **kwds):
        self._key = ('exif:GPSLatitude', 'exif:GPSLongitude')
        self.default_value = ''
        self.multiple = multiple_values()
        super(LatLongDisplay, self).__init__(*args, **kwds)
        self.lat_validator = QtGui.QDoubleValidator(
            -90.0, 90.0, 20, parent=self)
        self.lng_validator = QtGui.QDoubleValidator(
            -180.0, 180.0, 20, parent=self)
        self.setButtonSymbols(self.ButtonSymbols.NoButtons)
        self.label = Label(translate(
            'LatLongDisplay', 'Lat, long',
            'Short abbreviation of "Latitude, longitude"'))
        self.setFixedWidth(width_for_text(self, '8' * 22))
        self.setToolTip('<p>{}</p>'.format(translate(
            'LatLongDisplay', 'Latitude and longitude (in degrees) as two'
            ' decimal numbers separated by a space.')))

    @catch_all
    def focusOutEvent(self, event):
        self.emit_value()
        super(LatLongDisplay, self).focusOutEvent(event)

    @catch_all
    def keyPressEvent(self, event):
        self.set_not_multiple()
        super(LatLongDisplay, self).keyPressEvent(event)

    @catch_all
    def contextMenuEvent(self, event):
        if self.isReadOnly():
            return
        menu = self.lineEdit().createStandardContextMenu()
        suggestion_group = QtGui2.QActionGroup(menu)
        if self._is_multiple and self.choices:
            sep = menu.insertSeparator(menu.actions()[0])
            for suggestion in self.choices:
                label = str(suggestion)
                action = QtGui2.QAction(label, suggestion_group)
                action.setData(str(suggestion))
                menu.insertAction(sep, action)
        action = execute(menu, event.globalPos())
        if action and action.actionGroup() == suggestion_group:
            if self._is_multiple:
                self.set_value(action.data())
                self.emit_value()

    def stepEnabled(self):
        return self.StepEnabledFlag.StepNone

    @catch_all
    def validate(self, text, pos):
        if not text:
            return QtGui.QValidator.State.Acceptable, text, pos
        parts = text.split()
        if len(parts) > 2:
            return QtGui.QValidator.State.Invalid, text, pos
        result = self.lat_validator.validate(parts[0], pos)[0]
        if result != QtGui.QValidator.State.Invalid and len(parts) > 1:
            lng_result = self.lng_validator.validate(parts[1], pos)[0]
            if lng_result == QtGui.QValidator.State.Invalid:
                result = lng_result
            elif result == QtGui.QValidator.State.Acceptable:
                result = lng_result
        return result, text, pos

    @catch_all
    def fixup(self, value):
        value = self.text_to_value(value)
        if len(value) != 2:
            return
        value[0] = min(max(value[0], -90.0), 90.0)
        value[1] = ((value[1] + 180.0) % 360.0) - 180.0
        self.lineEdit().setText(self.value_to_text(value))

    def text_to_value(self, text):
        value = [self.locale().toDouble(x) for x in text.split()]
        if not all(x[1] for x in value):
            # float conversion failed
            return []
        return [x[0] for x in value]

    def value_to_text(self, value):
        return ' '.join(self.locale().toString(float(x), 'f', 6) for x in value)

    def get_value(self):
        value = self.text_to_value(self.text())
        if len(value) != 2:
            return None
        return value

    def get_value_dict(self):
        if self.is_multiple():
            return {}
        return dict(zip(self._key, self.get_value() or (None, None)))

    def set_value(self, value):
        self.set_not_multiple()
        if not value:
            self.clear()
        else:
            if not isinstance(value, str):
                value = self.value_to_text(value)
            self.lineEdit().setText(value)

    def set_value_list(self, values):
        choices = set()
        if not values:
            self.setEnabled(False)
            self.set_value(None)
            return
        self.setEnabled(True)
        for value in values:
            if value:
                lat = value['exif:GPSLatitude']
                lon = value['exif:GPSLongitude']
                if lat and lon:
                    choices.add(self.value_to_text((lat, lon)))
                    continue
            choices.add(None)
        if len(choices) > 1:
            self.set_multiple(choices=[x for x in choices if x])
        else:
            self.set_value(choices and choices.pop())


class DoubleSpinBox(AugmentSpinBox, QtWidgets.QDoubleSpinBox):
    def __init__(self, key, *arg, **kw):
        self._key = key
        self.default_value = 0
        self.multiple = multiple_values()
        super(DoubleSpinBox, self).__init__(*arg, **kw)
        self.setSingleStep(0.1)
        self.setDecimals(4)
        lim = (2 ** 31) - 1
        self.setRange(-lim, lim)
        self.setButtonSymbols(self.ButtonSymbols.NoButtons)

    @catch_all
    def contextMenuEvent(self, event):
        self.context_menu_event()
        return super(DoubleSpinBox, self).contextMenuEvent(event)

    @catch_all
    def keyPressEvent(self, event):
        self.set_not_multiple()
        return super(DoubleSpinBox, self).keyPressEvent(event)

    @catch_all
    def stepBy(self, steps):
        self.set_not_multiple()
        self.init_stepping()
        return super(DoubleSpinBox, self).stepBy(steps)

    @catch_all
    def fixup(self, text):
        if not self.fix_up():
            super(DoubleSpinBox, self).fixup(text)

    @catch_all
    def textFromValue(self, value):
        # don't use QDoubleSpinBox's fixed number of decimals
        decimals = self.decimals()
        value = round(float(value), decimals)
        while decimals > 1 and round(value, decimals - 1) == value:
            decimals -= 1
        return self.locale().toString(value, 'f', decimals)


class AltitudeDisplay(DoubleSpinBox):
    def __init__(self, *args, **kwds):
        super(AltitudeDisplay, self).__init__('exif:GPSAltitude', *args, **kwds)
        self.set_suffix(translate('AltitudeDisplay', ' m', 'metres altitude'))
        self.setToolTip('<p>{}</p>'.format(translate(
            'AltitudeDisplay', 'Altitude of the location in metres.')))
        self.label = Label(translate('AltitudeDisplay', 'Altitude'))
