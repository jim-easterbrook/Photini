##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2022-26  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import enum
import logging

from photini.pyqt import *
from photini.pyqt import qt_version_info

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class WidgetMixin(object):
    class Flags(enum.Flag):
        multiple = enum.auto()
        faint = enum.auto()
        is_none = enum.auto()
        invalid_mask = multiple | faint

    new_value = QtSignal(dict)

    def append_value(self, value):
        self.set_value(value)

    def handle_delete_key(self, event):
        if self.is_multiple() and event.key() in (
                Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self.set_value(None)

    @QtSlot()
    @catch_all()
    def emit_value(self):
        if self.is_valid():
            self.new_value.emit(self.get_value_dict())

    def get_value_dict(self):
        if self.is_valid():
            return {self._key: self.get_value()}
        return {}

    def has_value(self):
        return bool(self.get_value()) or self.is_multiple()

    def set_enabled(self, enabled):
        self.setEnabled(enabled)

    def set_value_dict(self, value):
        self.set_value(value.get(self._key))

    def _load_data(self, md_list):
        choices = []
        for md in md_list:
            value = None
            if self._key in md:
                value = md[self._key]
            if value not in choices:
                choices.append(value)
        if len(choices) > 1:
            self.set_multiple(choices=choices)
        else:
            choices = choices or [None]
            self.set_value(choices[0])

    def _save_data(self, metadata, value):
        if self._key in value:
            metadata[self._key] = value[self._key]
        return False


class CompoundWidgetMixin(WidgetMixin):
    dynamic = False

    def after_load(self):
        pass

    def get_value(self):
        result = {}
        for widget in self.sub_widgets():
            result.update(widget.get_value_dict())
        return result

    def has_value(self):
        return any(w.has_value() for w in self.sub_widgets())

    def is_multiple(self):
        return any(w.is_multiple() for w in self.sub_widgets())

    def is_valid(self):
        return all(w.is_valid() for w in self.sub_widgets())

    def set_enabled(self, enabled):
        for widget in self.sub_widgets():
            widget.set_enabled(enabled)

    def set_value(self, value):
        value = value or {}
        if self.dynamic:
            keys = [k for k in value if value[k]]
            self.set_subwidgets(keys)
        for widget in self.sub_widgets():
            widget.set_value_dict(value)
        self.after_load()

    def _load_data(self, md_list):
        md_list = [md[self._key] for md in md_list]
        if self.dynamic:
            keys = set()
            for md in md_list:
                keys |= {k for k in md if md[k]}
            self.set_subwidgets(keys)
        for widget in self.sub_widgets():
            widget._load_data(md_list)
        self.after_load()

    def _save_data(self, metadata, value):
        reload = False
        if self._key in value:
            value = value[self._key]
            if value:
                # update metadata
                md = dict(metadata[self._key])
            else:
                # clear metadata
                md = {}
            for widget in self.sub_widgets():
                if widget._save_data(md, value):
                    reload = True
            metadata[self._key] = md
        return reload

    @QtSlot(dict)
    @catch_all()
    def sw_new_value(self, value):
        self.new_value.emit({self._key: value})


class ListWidgetMixin(CompoundWidgetMixin):
    def append_value(self, value):
        values = list(self.get_value().values())
        for value in value.values():
            if value not in values:
                values.append(value)
        self.set_value(dict(enumerate(values)))

    def get_value(self):
        values = []
        for widget in self.sub_widgets():
            if widget.has_value():
                values.append(widget.get_value())
        return dict(enumerate(values))

    def _load_data(self, md_list):
        md_list = [md[self._key] for md in md_list]
        if self.dynamic:
            count = max(len(x) for x in md_list)
            self.set_subwidgets(list(range(count)))
        copy_list = [list(md) for md in md_list]
        for widget in self.sub_widgets():
            for md in copy_list:
                while len(md) <= widget._key:
                    md.append(self.item_type())
            widget._load_data(copy_list)
        self.after_load()

    def _save_data(self, metadata, value):
        reload = False
        if self._key in value:
            value = value[self._key]
            if value:
                # update metadata
                md = list(metadata[self._key])
            else:
                # clear metadata
                md = []
            for widget in self.sub_widgets():
                while len(md) <= widget._key:
                    md.append(self.item_type())
                if widget._save_data(md, value):
                    reload = True
            metadata[self._key] = md
        return reload


class TopLevelWidgetMixin(WidgetMixin):
    @QtSlot()
    @catch_all()
    def emit_value(self):
        self.save_data(self.get_value())

    def load_data(self, images):
        if not images:
            for widget in self.sub_widgets():
                widget.set_value(None)
                widget.set_enabled(False)
        else:
            metadata = [im.metadata for im in images]
            for widget in self.sub_widgets():
                widget.set_enabled(True)
                widget._load_data(metadata)
        self.load_finished(images)

    def load_finished(self, images):
        pass

    @QtSlot(dict)
    @catch_all()
    def save_data(self, value, images=None):
        reload = False
        images = images or self.app.image_list.get_selected_images()
        for image in images:
            for widget in self.sub_widgets():
                if widget._save_data(image.metadata, value):
                    reload = True
        self.save_finished(value, images)
        if reload:
            self.load_data(images)

    def save_finished(self, value, images):
        pass


class ChoicesContextMenu(object):
    # mixin for <multiple values> to allow choosing one
    def add_choices_context_menu(self, menu, event):
        if not (self.is_multiple() and self.choices):
            return None
        sub_menu = QtWidgets.QMenu(translate(
            'Widgets', 'Choose value'), parent=menu)
        group = QtGui2.QActionGroup(sub_menu)
        fm = sub_menu.fontMetrics()
        for suggestion in self.choices:
            text = self.value_to_text(suggestion)
            text = fm.elidedText(
                text, Qt.TextElideMode.ElideMiddle, self.width())
            action = QtGui2.QAction(text, parent=group)
            action.setData(suggestion)
            sub_menu.addAction(action)
        group.triggered.connect(self._choice_triggered)
        return sub_menu

    @QtSlot(QtGui2.QAction)
    @catch_all()
    def _choice_triggered(self, action):
        self.set_value(action.data())
        self.emit_value()


class ComboBox(QtWidgets.QComboBox):
    def __init__(self, *args, **kwds):
        super(ComboBox, self).__init__(*args, **kwds)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    @catch_all()
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
        value = value or None
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

    def is_valid(self):
        return self.currentIndex() < self._last_idx()

    def set_multiple(self, choices=[]):
        if self._with_multiple:
            blocked = self.blockSignals(True)
            self._old_idx = self.count() - 1
            self.setCurrentIndex(self._old_idx)
            self.blockSignals(blocked)

    @catch_all(exc_return=-1)
    def findData(self, data):
        # Qt's findData only works with simple types
        for n in range(self._last_idx()):
            if self.itemData(n) == data:
                return n
        return -1

    @QtSlot(int)
    @catch_all()
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


class TabWidgetEx(QtWidgets.QTabWidget):
    def set_placeholder(self, widget, placeholder):
        idx = self.indexOf(widget)
        palette = self.tabBar().palette()
        if not placeholder:
            colour = palette.color(palette.ColorGroup.Normal,
                                   palette.ColorRole.Text)
        elif qt_version_info >= (5, 12):
            colour = palette.color(palette.ColorGroup.Normal,
                                   palette.ColorRole.PlaceholderText)
        else:
            colour = palette.text().color()
            colour.setAlpha(128)
        self.tabBar().setTabTextColor(idx, colour)


class Slider(QtWidgets.QSlider, WidgetMixin):
    def __init__(self, key, *arg, **kw):
        super(Slider, self).__init__(*arg, **kw)
        self._key = key
        self._flags = self.Flags(0)
        self.sliderPressed.connect(self._clear_flags)

    @catch_all()
    def focusOutEvent(self, event):
        self.emit_value()
        super(Slider, self).focusOutEvent(event)

    @QtSlot()
    @catch_all()
    def _clear_flags(self):
        self._flags = self.Flags(0)

    def get_value(self):
        if self._flags & self.Flags.is_none:
            return None
        return self.value()

    def set_value(self, value):
        self._clear_flags()
        if value is None:
            self._flags |= self.Flags.is_none
            value = self.minimum()
        if not isinstance(value, int):
            value = int(value)
        if self.value() == value:
            self.valueChanged.emit(value)
        else:
            self.setValue(value)

    def set_multiple(self, choices=[]):
        self._clear_flags()
        self._flags |= self.Flags.multiple
        value = self.value()
        for choice in choices:
            if choice is not None:
                value = max(value, choice)
        if self.value() == value:
            self.valueChanged.emit(value)
        else:
            self.setValue(value)

    def is_multiple(self):
        return bool(self._flags & self.Flags.multiple)

    def is_valid(self):
        return not bool(self._flags & self.Flags.invalid_mask)


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


class ContextMenuMixin(object):
    # adds a cut/copy/paste/delete context menu to any widget
    # requires self.app and self.clipboard_key to be set
    def compound_context_menu(self, event, title=None):
        if not self.isEnabled():
            return
        title = title or translate(
            'Widgets', 'All "{tab_name}" data').format(
                tab_name=self.tab_short_name().replace('&', ''))
        menu = QtWidgets.QMenu()
        action = QtWidgets.QWidgetAction(menu)
        action.setDefaultWidget(QtWidgets.QLabel(
            '<div style="font-weight: 500">{}</div>'.format(title)))
        menu.addAction(action)
        self.add_copy_paste_context_menu(menu)
        execute(menu, event.globalPos())

    def add_copy_paste_context_menu(self, menu):
        if qt_version_info >= (6, 7):
            icons = {'Cut': QtGui.QIcon.ThemeIcon.EditCut,
                     'Copy': QtGui.QIcon.ThemeIcon.EditCopy,
                     'Paste': QtGui.QIcon.ThemeIcon.EditPaste,
                     'Delete': QtGui.QIcon.ThemeIcon.EditDelete}
        else:
            icons = {'Cut': 'edit-cut',
                     'Copy': 'edit-copy',
                     'Paste': 'edit-paste',
                     'Delete': 'edit-delete'}
        functions = {'Cut': self.do_cut,
                     'Copy': self.do_copy,
                     'Paste': self.do_paste,
                     'Delete': self.do_delete}
        for key in ('Cut', 'Copy', 'Paste', 'Delete'):
            action = menu.addAction(QtGui.QIcon.fromTheme(icons[key]),
                                    translate('QShortcut', key), functions[key])
            if key == 'Paste':
                action.setEnabled(self.clipboard_key in self.app.clipboard)
            elif key == 'Delete':
                action.setEnabled(self.has_value())
            else:
                action.setEnabled(self.has_value() and self.is_valid())

    @QtSlot()
    @catch_all()
    def do_cut(self):
        self.do_copy()
        self.do_delete()

    @QtSlot()
    @catch_all()
    def do_copy(self):
        self.app.clipboard[self.clipboard_key] = self.get_value()

    @QtSlot()
    @catch_all()
    def do_paste(self):
        self.paste_value(self.app.clipboard[self.clipboard_key])

    @QtSlot()
    @catch_all()
    def do_delete(self):
        self.set_value({})
        self.emit_value()

    def paste_value(self, value):
        self.append_value(value)
        self.emit_value()
