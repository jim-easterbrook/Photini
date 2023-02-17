##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2022-3  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
from photini.types import LangAltDict

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class ComboBox(QtWidgets.QComboBox):
    def __init__(self, *args, **kwds):
        super(ComboBox, self).__init__(*args, **kwds)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    @catch_all
    def wheelEvent(self, event):
        if self.hasFocus():
            return super(ComboBox, self).wheelEvent(event)
        event.ignore()
        return True

    def set_dropdown_width(self):
        width = 0
        for idx in range(self.count()):
            width = max(width, width_for_text(self, self.itemText(idx) + 'xx'))
        margin = self.view().verticalScrollBar().sizeHint().width()
        self.view().setMinimumWidth(width + margin)


class Label(QtWidgets.QLabel):
    def __init__(self, *args, lines=1, layout=None, **kwds):
        super(Label, self).__init__(*args, **kwds)
        if lines == 1:
            return
        self.setText(wrap_text(self, self.text(), lines))
        if not layout:
            return
        # match text alignment to form layout
        align_h = (layout.labelAlignment()
                   & Qt.AlignmentFlag.AlignHorizontal_Mask)
        align_v = self.alignment() & Qt.AlignmentFlag.AlignVertical_Mask
        self.setAlignment(align_h | align_v)
        # Qt internally makes labels in form layouts 7/4 as tall, which
        # is too much for multi=line labels
        height = self.sizeHint().height() * ((lines * 4) + 3) // (lines * 4)
        self.setFixedHeight(height)


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


class DropDownSelector(ComboBox):
    new_value = QtSignal(str, object)

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
            self.new_value.emit(self._key, self.itemData(idx))
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
        self.new_value.emit(self._key, data)

    def _last_idx(self):
        idx = self.count()
        if self._extendable:
            idx -= 1
        if self._with_multiple:
            idx -= 1
        return idx


class TextHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, spelling, length, length_always, multi_string, parent):
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
            self.length_check = length
            self.length_always = length_always
            self.length_formatter = QtGui.QTextCharFormat()
            self.length_formatter.setUnderlineColor(Qt.GlobalColor.blue)
            self.length_formatter.setUnderlineStyle(
                QtGui.QTextCharFormat.UnderlineStyle.SingleUnderline)
            if multi_string:
                # treat each keyword separately
                self.pattern = re.compile(r'\s*(.+?)(;|$)')
            else:
                # treat the entire block as one
                self.pattern = re.compile(r'(.+)')
        else:
            self.length_check = None

    @catch_all
    def highlightBlock(self, text):
        if not text:
            if self.length_check:
                self.setCurrentBlockState(self.previousBlockState())
            return
        if self.length_check:
            length_warning = self.length_always or self.config_store.get(
                'files', 'length_warning', True)
            if length_warning:
                consumed = max(self.previousBlockState(), 0)
                max_len = max(self.length_check - consumed, 0)
                for match in self.pattern.finditer(text):
                    start = match.start(1)
                    end = match.end(1)
                    truncated = text[start:end].encode('utf-8')
                    consumed += len(truncated)
                    truncated = truncated[:max_len]
                    start += len(truncated.decode('utf-8', errors='ignore'))
                    if start < end:
                        self.setFormat(start, end - start,
                                       self.length_formatter)
                self.setCurrentBlockState(max(consumed, 0))
        if self.spell_check:
            for word, start, end in self.find_words(text):
                if not self.spell_check.check(word):
                    self.setFormat(start, end - start, self.spell_formatter)


class MultiLineEdit(QtWidgets.QPlainTextEdit):
    new_value = QtSignal(str, object)

    def __init__(self, key, *arg, spell_check=False, length_check=None,
                 multi_string=False, length_always=False, **kw):
        super(MultiLineEdit, self).__init__(*arg, **kw)
        if self.isRightToLeft():
            self.set_text_alignment(Qt.AlignmentFlag.AlignRight)
        self._key = key
        self.multiple_values = multiple_values()
        self.setTabChangesFocus(True)
        self._is_multiple = False
        self.spell_check = spell_check
        self.highlighter = TextHighlighter(
            spell_check, length_check, length_always, multi_string,
            self.document())

    @catch_all
    def focusOutEvent(self, event):
        if not self._is_multiple:
            self.new_value.emit(self._key, self.get_value())
        super(MultiLineEdit, self).focusOutEvent(event)

    @catch_all
    def keyPressEvent(self, event):
        if self._is_multiple:
            self._is_multiple = False
            self.setPlaceholderText('')
        super(MultiLineEdit, self).keyPressEvent(event)

    @catch_all
    def contextMenuEvent(self, event):
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
                    action.setData(str(suggestion))
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
                self.new_value.emit(self._key, action.data())
            else:
                cursor.setPosition(block_pos + start)
                cursor.setPosition(block_pos + end, cursor.MoveMode.KeepAnchor)
                cursor.insertText(action.iconText())

    def set_height(self, rows):
        height = QtWidgets.QLineEdit().sizeHint().height()
        height += (rows - 1) * self.fontMetrics().lineSpacing()
        self.setMaximumHeight(height)

    def set_value(self, value):
        if self._is_multiple:
            self._is_multiple = False
            self.setPlaceholderText('')
        if not value:
            self.clear()
        else:
            self.setPlainText(str(value))

    def get_value(self):
        return self.toPlainText()

    def set_multiple(self, choices=[]):
        self._is_multiple = True
        self.choices = list(choices)
        self.setPlaceholderText(self.multiple_values)
        self.clear()

    def is_multiple(self):
        return self._is_multiple and not bool(self.get_value())

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


class LatLongDisplay(SingleLineEdit):
    changed = QtSignal()

    def __init__(self, *args, **kwds):
        super(LatLongDisplay, self).__init__('latlon', *args, **kwds)
        self.app = QtWidgets.QApplication.instance()
        self.label = QtWidgets.QLabel(translate('LatLongDisplay', 'Lat, long'))
        self.label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setFixedWidth(width_for_text(self, '8' * 23))
        self.setEnabled(False)
        self.new_value.connect(self.editing_finished)

    @QtSlot(str, object)
    @catch_all
    def editing_finished(self, key, value):
        selected_images = self.app.image_list.get_selected_images()
        new_value = value.strip() or None
        if new_value:
            try:
                new_value = [float(x) for x in new_value.split(',')]
                lat, lng = new_value
            except Exception:
                # user typed in an invalid value
                self.update_display(selected_images)
                return
        else:
            lat, lng = None, None
        for image in selected_images:
            gps = dict(image.metadata.gps_info or {})
            gps['lat'], gps['lon'] = lat, lng
            gps['method'] = 'MANUAL'
            image.metadata.gps_info = gps
        self.update_display(selected_images)
        self.changed.emit()

    def update_display(self, selected_images=None):
        if selected_images is None:
            selected_images = self.app.image_list.get_selected_images()
        if not selected_images:
            self.set_value(None)
            self.setEnabled(False)
            return
        values = []
        for image in selected_images:
            gps = image.metadata.gps_info
            if not (gps and gps['lat']):
                continue
            value = '{lat}, {lon}'.format(**gps)
            if value not in values:
                values.append(value)
        if not values:
            self.set_value(None)
        elif len(values) > 1:
            self.set_multiple(choices=values)
        else:
            self.set_value(values[0])
        self.setEnabled(True)


class Slider(QtWidgets.QSlider):
    editing_finished = QtSignal()

    def __init__(self, *arg, **kw):
        super(Slider, self).__init__(*arg, **kw)
        self._is_multiple = False
        self.sliderPressed.connect(self.slider_pressed)

    @catch_all
    def focusOutEvent(self, event):
        self.editing_finished.emit()
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


class LangAltWidget(QtWidgets.QWidget):
    new_value = QtSignal(str, object)

    def __init__(self, key, multi_line=True, **kw):
        super(LangAltWidget, self).__init__()
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self.value = LangAltDict()
        # text edit
        if multi_line:
            self.edit = MultiLineEdit(key, **kw)
        else:
            self.edit = SingleLineEdit(key, **kw)
        self.edit.new_value.connect(self._new_value)
        layout.addWidget(self.edit)
        # language drop down
        self.lang = DropDownSelector('', with_multiple=False, extendable=True)
        self.lang.setFixedWidth(width_for_text(self.lang, 'x' * 16))
        self.lang.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lang.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lang.new_value.connect(self._change_lang)
        self.lang.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.lang)
        layout.setAlignment(self.lang, Qt.AlignmentFlag.AlignTop)
        # adopt some child methods ...
        self.is_multiple = self.edit.is_multiple
        self.set_height = self.edit.set_height
        # ... and vice versa
        self.lang.define_new_value = self._define_new_lang

    @catch_all
    def setToolTip(self, text):
        self.edit.setToolTip(text)

    @QtSlot(str, object)
    @catch_all
    def _change_lang(self, key, lang):
        if lang == LangAltDict.DEFAULT:
            direction = self.layoutDirection()
        else:
            direction = QtCore.QLocale(lang).textDirection()
        if direction == Qt.LayoutDirection.RightToLeft:
            self.edit.set_text_alignment(Qt.AlignmentFlag.AlignRight)
        else:
            self.edit.set_text_alignment(Qt.AlignmentFlag.AlignLeft)
        self.edit.set_value(self.value[lang])

    @QtSlot(str, object)
    @catch_all
    def _new_value(self, key, value):
        if self.is_multiple():
            self.value = self.choices[value]
        else:
            self.value[self.lang.get_value()] = value
        self.new_value.emit(key, self.get_value())

    def _regularise_default(self):
        if (LangAltDict.DEFAULT not in self.value
                or not self.value[LangAltDict.DEFAULT]):
            return True
        prompt = QtCore.QLocale.system().bcp47Name()
        if prompt in self.value:
            prompt = None
        self.lang.set_value(LangAltDict.DEFAULT)
        self.edit.set_value(self.value[LangAltDict.DEFAULT])
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
        prompt = QtCore.QLocale.system().bcp47Name()
        if prompt in self.value:
            prompt = None
        lang, OK = QtWidgets.QInputDialog.getText(
            self, translate('LangAltWidget', 'New language'),
            wrap_text(self, translate(
                'LangAltWidget', 'What language would you like to add?'
                ' Please enter an RFC3066 language tag.'), 2), text=prompt)
        if not (OK and lang):
            return None, None
        self.value[lang] = ''
        self.new_value.emit(self.edit._key, self.get_value())
        return self.labeled_lang(lang)

    @QtSlot(QtCore.QPoint)
    @catch_all
    def _context_menu(self, pos):
        langs = []
        for n in range(self.lang.count()):
            lang = self.lang.itemData(n)
            if lang and lang != LangAltDict.DEFAULT:
                langs.append(lang)
        if not langs:
            return
        default_lang = self.value.get_default_lang()
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
        self.value.set_default_lang(lang)
        value = self.get_value()
        self.set_value(value)
        self.new_value.emit(self.edit._key, value)

    def labeled_lang(self, lang):
        if lang == LangAltDict.DEFAULT:
            if len(self.value) == 1:
                return translate('LangAltWidget', 'Language'), lang
            label = '-'
        else:
            label = lang
        label = translate('LangAltWidget', 'Lang: ',
                          'Short abbreviation of "Language: "') + label
        return label, lang

    def set_value(self, value):
        self.lang.setEnabled(True)
        self.value = LangAltDict(value)
        # use current language, if available
        lang = self.lang.get_value()
        if lang not in self.value:
            # choose language from locale
            lang = QtCore.QLocale.system().bcp47Name()
            if lang not in self.value:
                base_lang = lang.split('-')[0]
                for lang in self.value:
                    if lang.split('-')[0] == base_lang:
                        break
        if lang not in self.value:
            # use the default for this value
            lang = self.value.get_default_lang()
        # set language drop down
        self.lang.set_values(
            [self.labeled_lang(x) for x in self.value], default=lang)
        self._change_lang('', lang)

    def get_value(self):
        return self.value

    def set_multiple(self, choices=[]):
        self.choices = {}
        for choice in choices:
            self.choices[str(choice)] = LangAltDict(choice)
        self.edit.set_multiple(choices=self.choices.keys())
        self.lang.setEnabled(False)
