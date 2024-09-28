#  Photini - a simple photo metadata editor.
#  http://github.com/jim-easterbrook/Photini
#  Copyright (C) 2024  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from collections import defaultdict
from datetime import date
import json
import logging
import os

from photini.configstore import get_config_dir
from photini.metadata import ImageMetadata
from photini.pyqt import *
from photini.pyqt import qt_version_info
from photini.widgets import (
    ComboBox, Label, MultiLineEdit, TextEditMixin, WidgetMixin)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class KeywordsEditor(QtWidgets.QWidget):
    def __init__(self, key, **kw):
        super(KeywordsEditor, self).__init__()
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.league_table = {}
        for keyword, score in self.config_store.get(
                                'descriptive', 'keywords', {}).items():
            if isinstance(score, int):
                # old style keyword list
                self.league_table[keyword] = date.min.isoformat(), score // 50
            else:
                # new style keyword list
                self.league_table[keyword] = score
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # line edit box
        self.edit = MultiLineEdit(key, **kw)
        self.edit.set_height(3)
        layout.addWidget(self.edit)
        # favourites drop down
        self.favourites = ComboBox()
        self.favourites.addItem(translate('DescriptiveTab', '<favourites>'))
        self.favourites.setFixedWidth(width_for_text(self.favourites, 'x' * 16))
        self.update_favourites()
        self.favourites.currentIndexChanged.connect(self.add_favourite)
        layout.addWidget(self.favourites, 0, Qt.AlignmentFlag.AlignTop)
        self.setFixedHeight(self.sizeHint().height())
        # adopt child widget methods and signals
        self.get_value = self.edit.get_value
        self.set_value = self.edit.set_value
        self.set_multiple = self.edit.set_multiple
        self.is_multiple = self.edit.is_multiple
        self.new_value = self.edit.new_value
        self.emit_value = self.edit.emit_value

    def update_favourites(self):
        self.favourites.clear()
        self.favourites.addItem(translate('DescriptiveTab', '<favourites>'))
        keywords = list(self.league_table.keys())
        keywords.sort(key=lambda x: self.league_table[x], reverse=True)
        # limit size of league_table by deleting lowest scoring
        if len(keywords) > 100:
            threshold = self.league_table[keywords[100]]
            for keyword in keywords:
                if self.league_table[keyword] <= threshold:
                    del self.league_table[keyword]
        # select highest scoring for drop down list
        keywords = keywords[:20]
        keywords.sort(key=lambda x: x.lower())
        for keyword in keywords:
            self.favourites.addItem(keyword)
        self.favourites.set_dropdown_width()

    def update_league_table(self, images):
        today = date.today().isoformat()
        for image in images:
            keywords = image.metadata.keywords
            value = [x for x in keywords if ':' not in x]
            if not value:
                continue
            for keyword in value:
                if keyword not in self.league_table:
                    self.league_table[keyword] = today, 1
                elif self.league_table[keyword][0] != today:
                    self.league_table[keyword] = (
                        today, self.league_table[keyword][1] + 1)
        self.config_store.set('descriptive', 'keywords', self.league_table)
        self.update_favourites()

    @QtSlot(int)
    @catch_all
    def add_favourite(self, idx):
        if idx <= 0:
            return
        self.favourites.setCurrentIndex(0)
        new_value = self.favourites.itemText(idx)
        current_value = self.get_value()
        if current_value:
            new_value = current_value + '; ' + new_value
        self.set_value(new_value)
        self.edit.emit_value()


class KeywordCompleter(QtWidgets.QCompleter):
    def __init__(self, list_view, widget, *arg, **kw):
        super(KeywordCompleter, self).__init__(*arg, **kw)
        self.setModel(list_view)
        self.setModelSorting(self.ModelSorting.CaseInsensitivelySortedModel)
        self.setFilterMode(Qt.MatchFlag.MatchContains)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.popup().setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.setWidget(widget)

    @QtSlot(str)
    @catch_all
    def set_text(self, text):
        if len(text) < 2:
            return
        self.setCompletionPrefix(text)
        self.complete()


class HtmlTextEdit(QtWidgets.QTextEdit, TextEditMixin):
    def __init__(self, key, list_view, *arg, spell_check=False,
                 length_check=None, multi_string=False, length_always=False,
                 length_bytes=True, min_width=None, **kw):
        super(HtmlTextEdit, self).__init__(*arg, **kw)
        self.init_mixin(key,spell_check, length_check, length_always,
                        length_bytes, multi_string, min_width)
        self.setFixedHeight(QtWidgets.QLineEdit().sizeHint().height())
        self.setLineWrapMode(self.LineWrapMode.NoWrap)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.completer = KeywordCompleter(list_view, self)
        self.completer.activated.connect(self.completer_activated)
        self.textChanged.connect(self.text_changed)

    @QtSlot()
    @catch_all
    def text_changed(self):
        if not self.hasFocus():
            return
        self.completer.set_text(self.toPlainText())

    @QtSlot(str)
    @catch_all
    def completer_activated(self, text):
        self.set_value(text)
        self.emit_value()
        self.completer.popup().hide()

    @catch_all
    def focusOutEvent(self, event):
        self.emit_value()
        super(HtmlTextEdit, self).focusOutEvent(event)

    @catch_all
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return:
            event.ignore()
            return
        self.set_multiple(multiple=False)
        super(HtmlTextEdit, self).keyPressEvent(event)

    @catch_all
    def contextMenuEvent(self, event):
        self.context_menu_event(event)

    def get_value(self):
        return self.toPlainText()

    def set_value(self, value):
        self.set_multiple(multiple=False)
        if value:
            self.setHtml(value)
        else:
            self.clear()


class HierarchicalTagDataItem(QtGui.QStandardItem):
    flag_keys = ('is_set', 'copyable')
    sort_role = Qt.ItemDataRole.UserRole + 2

    # this ought to be __init__, but some versions of PySide2 crash if I
    # override QStandardItem.__init__()
    def initialise(self):
        self.setData(self.text().casefold(), self.sort_role)
        self.tick_boxes = {}
        for key in self.flag_keys:
            self.tick_boxes[key] = QtGui.QStandardItem()
            self.tick_boxes[key].setCheckable(True)
        self.setData('<p>{}</p>'.format(translate(
            'KeywordsTab', 'One "word" in a keyword hierarchy. This word and'
            ' its ancestors form a complete keyword.'
            )), Qt.ItemDataRole.ToolTipRole)
        self.tick_boxes['is_set'].setData('<p>{}</p>'.format(translate(
            'KeywordsTab', 'Tick this box to add this keyword to the selected'
            ' photographs. Untick the box to remove it from the selected'
            ' photographs.')), Qt.ItemDataRole.ToolTipRole)
        self.tick_boxes['copyable'].setData('<p>{}</p>'.format(translate(
            'KeywordsTab', 'Tick this box to allow this keyword to be copied'
            ' to or from the traditional "flat" keywords.'
            )), Qt.ItemDataRole.ToolTipRole)

    def type(self):
        return self.ItemType.UserType + 1

    def __lt__(self, other):
        return self.data(self.sort_role) < other.data(self.sort_role)

    def all_children(self):
        for row in range(self.rowCount()):
            child = self.child(row)
            yield child
            for grandchild in child.all_children():
                yield grandchild

    def extend(self, names):
        name = names[0]
        names = names[1:]
        for row in range(self.rowCount()):
            child = self.child(row)
            if child.text() == name:
                break
        else:
            child = HierarchicalTagDataItem(name)
            child.initialise()
            if not names:
                # last name is copyable by default
                child.set_checked('copyable', True)
            self.appendRow(child.get_row())
        if names:
            child.extend(names)

    def get_row(self):
        result = [self]
        for key in self.flag_keys:
            result.append(self.tick_boxes[key])
        return result

    def full_name(self):
        parent = self.parent()
        if parent:
            return parent.full_name() + '|' + self.text()
        return self.text()

    def checked(self, key):
        return self.tick_boxes[key].checkState() == Qt.CheckState.Checked

    def set_checked(self, key, checked):
        self.tick_boxes[key].setCheckState(
            (Qt.CheckState.Unchecked, Qt.CheckState.Checked)[checked])

    @staticmethod
    def json_default(self):
        flags = [key for key in self.tick_boxes
                 if key != 'is_set' and self.checked(key)]
        children = [self.child(row) for row in range(self.rowCount())]
        children.sort()
        return {'name': self.text(), 'flags': flags, 'children': children}

    @staticmethod
    def json_object_hook(dict_value):
        if 'name' in dict_value:
            self = HierarchicalTagDataItem(dict_value['name'])
            self.initialise()
            for key in self.flag_keys:
                self.set_checked(key, key in dict_value['flags'])
            for child in dict_value['children']:
                self.appendRow(child.get_row())
            return self
        return dict_value


class HierarchicalTagDataModel(QtGui.QStandardItemModel):
    def __init__(self, *args, **kwds):
        super(HierarchicalTagDataModel, self).__init__(*args, **kwds)
        self.setSortRole(HierarchicalTagDataItem.sort_role)
        self.setHorizontalHeaderLabels([
            translate('KeywordsTab', 'keyword'),
            translate('KeywordsTab', 'in photo'),
            translate('KeywordsTab', 'copyable'),
            ])
        self.file_name = os.path.join(get_config_dir(), 'keywords.json')
        self.load_file()
        # connect signals
        QtCore.QCoreApplication.instance().aboutToQuit.connect(self.save_file)
        self.itemChanged.connect(self.item_changed)

    def all_children(self):
        root = self.invisibleRootItem()
        return HierarchicalTagDataItem.all_children(root)

    def extend(self, value):
        root = self.invisibleRootItem()
        for full_name in value:
            HierarchicalTagDataItem.extend(root, full_name.split('|'))
        self.sort(0)

    def find_name(self, name, flags=None):
        flags = flags or Qt.MatchFlag.MatchFixedString
        return self.findItems(name, flags | Qt.MatchFlag.MatchRecursive)

    def find_full_name(self, full_name):
        names = full_name.split('|')
        for node in self.find_name(names[-1]):
            if node.full_name() == full_name:
                return node
        return None

    def formatted_name(self, full_name):
        node = self.find_full_name(full_name)
        if node:
            words = []
            while node:
                word = node.text()
                if not node.checked('copyable'):
                    word = '<i>{}</i>'.format(word)
                words.insert(0, word)
                node = node.parent()
        else:
            # value is not in model, last word is copyable
            words = full_name.split('|')
            words[0:-1] = ['<i>{}</i>'.format(word) for word in words[0:-1]]
            # add to model
            self.extend([full_name])
        return '|'.join(words)

    @QtSlot("QStandardItem*")
    @catch_all
    def item_changed(self, item):
        if item.text() or not isinstance(item, HierarchicalTagDataItem):
            return
        # user has deleted text, so delete item
        parent = item.parent() or self.invisibleRootItem()
        parent.removeRow(item.index().row())

    def load_file(self):
        root = self.invisibleRootItem()
        root.removeRows(0, root.rowCount())
        if os.path.exists(self.file_name):
            with open(self.file_name) as fp:
                children = json.load(
                    fp, object_hook=HierarchicalTagDataItem.json_object_hook)
            for child in children:
                root.appendRow(child.get_row())
        self.sort(0)

    def save_file(self):
        root = self.invisibleRootItem()
        children = [root.child(row) for row in range(root.rowCount())]
        with open(self.file_name, 'w') as fp:
            json.dump(children, fp, ensure_ascii=False,
                      default=HierarchicalTagDataItem.json_default, indent=2)


class HierarchicalTagsDialog(QtWidgets.QDialog):
    def __init__(self, *arg, **kw):
        super(HierarchicalTagsDialog, self).__init__(*arg, **kw)
        self.data_model = self.parent().data_model
        self.setWindowTitle(
            translate('KeywordsTab', 'Edit keyword hierarchy'))
        layout = FormLayout()
        self.setLayout(layout)
        width = width_for_text(self, 'x' * 100)
        height = width * 3 // 4
        self.setMinimumWidth(min(width, self.window().width() * 3 // 4))
        self.setMinimumHeight(min(height, self.window().height() * 3 // 4))
        # extend model
        self.initial_value = self.parent().get_value()
        self.data_model.extend(self.initial_value)
        # save model in current state
        self.data_model.save_file()
        # tree view of keywords
        self.tree_view = QtWidgets.QTreeView()
        self.tree_view.setUniformRowHeights(True)
        self.tree_view.setSizeAdjustPolicy(
            self.tree_view.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        self.tree_view.setModel(self.data_model)
        header = self.tree_view.header()
        header.setSectionsMovable(False)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, header.ResizeMode.Stretch)
        header.setSectionResizeMode(1, header.ResizeMode.Fixed)
        header.setSectionResizeMode(2, header.ResizeMode.Fixed)
        # set check boxes and expand all items in value
        for child in self.data_model.all_children():
            is_set = child.full_name() in self.initial_value
            child.set_checked('is_set', is_set)
            if is_set:
                parent = child.parent()
                while parent:
                    self.tree_view.expand(parent.index())
                    parent = parent.parent()
        layout.addWidget(self.tree_view)
        # search box
        self.search_box = QtWidgets.QLineEdit()
        self.search_box.setToolTip('<p>{}</p>'.format(translate(
            'KeywordsTab', 'Enter two or more letters to search the keyword'
            ' tree. When there are few enough results a popup menu will'
            ' be displayed.')))
        completer = KeywordCompleter(
            self.parent().list_view, self.search_box, parent=self)
        completer.activated.connect(self.completer_activated)
        self.search_box.textEdited.connect(completer.set_text)
        layout.addRow(QtWidgets.QLabel(translate('KeywordsTab', 'Search')),
                      self.search_box)
        # buttons
        button_box = QtWidgets.QDialogButtonBox()
        button_box.addButton(button_box.StandardButton.Ok
                             ).clicked.connect(self.clicked_ok)
        button_box.addButton(button_box.StandardButton.Apply
                             ).clicked.connect(self.clicked_apply)
        button_box.addButton(button_box.StandardButton.Cancel
                             ).clicked.connect(self.clicked_cancel)
        layout.addWidget(button_box)

    @QtSlot(str)
    @catch_all
    def completer_activated(self, text):
        index = self.data_model.find_full_name(text).index()
        self.tree_view.scrollTo(index)
        selection = self.tree_view.selectionModel()
        selection.select(index, selection.SelectionFlag.ClearAndSelect |
                                selection.SelectionFlag.Rows)

    @QtSlot()
    @catch_all
    def clicked_ok(self):
        self.clicked_apply()
        self.accept()

    @QtSlot()
    @catch_all
    def clicked_apply(self):
        # construct new value
        new_value = []
        for child in self.data_model.all_children():
            if child.checked('is_set'):
                new_value.append(child.full_name())
        self.parent().set_value(new_value)
        self.parent().emit_value()

    @QtSlot()
    @catch_all
    def clicked_cancel(self):
        self.data_model.load_file()
        self.parent().set_value(self.initial_value)
        self.parent().emit_value()
        self.reject()


class ListProxyModel(QtCore.QAbstractListModel):
    def __init__(self, data_model, *arg, **kw):
        super(ListProxyModel, self).__init__(*arg, **kw)
        self.data_model = data_model
        self.reset_row_map()
        self.data_model.rowsInserted.connect(self.model_rows_changed)
        self.data_model.rowsMoved.connect(self.model_rows_moved)
        self.data_model.rowsRemoved.connect(self.model_rows_changed)

    @QtSlot("QModelIndex", int, int)
    @catch_all
    def model_rows_changed(self, parent, first, last):
        self.reset_row_map()

    @QtSlot("QModelIndex", int, int)
    @catch_all
    def model_rows_moved(self, parent, start, end, destination, row):
        self.reset_row_map()

    def reset_row_map(self):
        self.beginResetModel()
        self.row_map = []
        for child in self.data_model.all_children():
            self.row_map.append(child)
        self.endResetModel()

    @catch_all
    def rowCount(self, parent=None):
        return len(self.row_map)

    @catch_all
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        item = self.row_map[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return item.full_name()
        return item.data(role)


class HierarchicalTagsEditor(QtWidgets.QScrollArea, WidgetMixin):
    update_value = QtSignal(str, str, str)

    def __init__(self, key, *args, **kwds):
        super(HierarchicalTagsEditor, self).__init__(*args, **kwds)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self._key = key
        self._is_multiple = False
        self._old_value = []
        self.setWidget(QtWidgets.QWidget())
        self.widget().setLayout(QtWidgets.QVBoxLayout())
        self.widget().layout().addStretch(1)
        self.setWidgetResizable(True)
        self.data_model = HierarchicalTagDataModel()
        self.list_view = ListProxyModel(self.data_model)
        self.set_rows()

    def set_rows(self, rows=1):
        layout = self.widget().layout()
        rows = max(rows, 1)
        idx = layout.count() - 1
        while idx < rows:
            widget = HtmlTextEdit(str(idx), self.list_view, spell_check=True)
            widget.setToolTip('<p>{}</p>'.format(translate(
                'KeywordsTab', 'Enter a hierarchy of keywords, terms or'
                ' phrases used to express the subject matter in the image.'
                ' Separate them with "|" or "/" characters.')))
            widget.new_value.connect(self._new_value)
            layout.insertWidget(idx, widget)
            idx += 1
        while idx > rows:
            idx -= 1
            layout.takeAt(idx).widget().setParent(None)

    @QtSlot(dict)
    @catch_all
    def _new_value(self, value):
        for idx, new_value in value.items():
            idx = int(idx)
            if idx < len(self._old_value):
                old_value = self._old_value[idx]
            else:
                old_value = ''
            self.update_value.emit(self._key, old_value, new_value)

    def get_value(self):
        layout = self.widget().layout()
        result = [layout.itemAt(idx).widget().get_value()
                  for idx in range(layout.count() - 1)]
        return [x for x in result if x]

    def set_value(self, value):
        if self._is_multiple:
            self._is_multiple = False
        value = value or []
        self._old_value = list(value)
        self.set_rows(len(value) + 1)
        layout = self.widget().layout()
        for idx in range(layout.count() - 1):
            widget = layout.itemAt(idx).widget()
            if idx < len(value):
                widget.set_value(self.data_model.formatted_name(value[idx]))
            else:
                widget.set_value(None)

    def set_multiple(self, choices=[]):
        self._is_multiple = True
        choice_dict = defaultdict(list)
        for idx, option in enumerate(choices):
            for tag in option:
                choice_dict[tag].append(idx)
        tag_list = list(choice_dict.keys())
        tag_list.sort(key=str.casefold)
        self._old_value = tag_list
        self.set_rows(len(tag_list) + 1)
        layout = self.widget().layout()
        for idx in range(layout.count() - 1):
            widget = layout.itemAt(idx).widget()
            if idx < len(tag_list):
                tag = tag_list[idx]
                if len(choice_dict[tag]) == len(choices):
                    widget.set_value(tag)
                else:
                    widget.set_multiple(choices=[tag])
            else:
                widget.set_value(None)

    def is_multiple(self):
        return self._is_multiple

    @QtSlot()
    @catch_all
    def open_tree_view(self):
        # do dialog
        dialog = HierarchicalTagsDialog(parent=self)
        execute(dialog)


class TabWidget(QtWidgets.QWidget):
    @staticmethod
    def tab_name():
        return translate('KeywordsTab', 'Keywords or tags',
                         'Full name of tab shown as a tooltip')

    @staticmethod
    def tab_short_name():
        return translate('KeywordsTab', '&Keywords',
                         'Shortest possible name used as tab label')

    def __init__(self, *arg, **kw):
        super(TabWidget, self).__init__(*arg, **kw)
        self.app = QtWidgets.QApplication.instance()
        layout = FormLayout()
        self.setLayout(layout)
        # construct widgets
        self.widgets = {}
        self.buttons = {}
        # keywords
        self.widgets['keywords'] = KeywordsEditor(
            'keywords', spell_check=True, multi_string=True,
            length_check=ImageMetadata.max_bytes('keywords'))
        self.widgets['keywords'].setToolTip('<p>{}</p>'.format(translate(
            'DescriptiveTab', 'Enter any number of keywords, terms or phrases'
            ' used to express the subject matter in the image.'
            ' Separate them with ";" characters.')))
        self.widgets['keywords'].new_value.connect(self.new_value)
        layout.addRow(translate('DescriptiveTab', 'Keywords'),
                      self.widgets['keywords'])
        # hierarchical keywords
        self.widgets['nested_tags'] = HierarchicalTagsEditor('nested_tags')
        self.widgets['nested_tags'].new_value.connect(self.new_value)
        self.widgets['nested_tags'].update_value.connect(self.update_value)
        label = Label(translate('KeywordsTab', 'Hierarchical keywords'),
                      lines=2, layout=layout)
        layout.addRow(label, self.widgets['nested_tags'])
        # buttons
        buttons = QtWidgets.QHBoxLayout()
        self.buttons['open_tree'] = QtWidgets.QPushButton(
            translate('KeywordsTab', 'Open tree view'))
        buttons.addWidget(self.buttons['open_tree'])
        buttons.addStretch(1)
        self.buttons['copy_from_flat'] = QtWidgets.QPushButton(
            translate('KeywordsTab', 'Copy to hierarchy'))
        self.buttons['copy_from_flat'].clicked.connect(self.copy_from_flat)
        buttons.addWidget(self.buttons['copy_from_flat'])
        self.buttons['copy_to_flat'] = QtWidgets.QPushButton(
            translate('KeywordsTab', 'Copy to keywords'))
        self.buttons['copy_to_flat'].clicked.connect(self.copy_to_flat)
        buttons.addWidget(self.buttons['copy_to_flat'])
        layout.addRow('', buttons)
        # make connections
        self.buttons['open_tree'].clicked.connect(
            self.widgets['nested_tags'].open_tree_view)
        self.app.image_list.image_list_changed.connect(self.image_list_changed)
        # disable until an image is selected
        self.setEnabled(False)

    @QtSlot()
    @catch_all
    def copy_from_flat(self):
        keywords = self.widgets['keywords'].get_value()
        if not keywords:
            return
        keywords = [x.strip() for x in keywords.split(';')]
        data_model = self.widgets['nested_tags'].data_model
        nested_tags = self.widgets['nested_tags'].get_value()
        for keyword in keywords:
            for match in data_model.find_name(keyword):
                if match.checked('copyable'):
                    full_name = match.full_name()
                    if full_name not in nested_tags:
                        nested_tags.append(full_name)
        self.widgets['nested_tags'].set_value(nested_tags)
        self.widgets['nested_tags'].emit_value()

    @QtSlot()
    @catch_all
    def copy_to_flat(self):
        nested_tags = self.widgets['nested_tags'].get_value()
        if not nested_tags:
            return
        data_model = self.widgets['nested_tags'].data_model
        keywords = self.widgets['keywords'].get_value()
        keywords = [x.strip() for x in keywords.split(';')]
        for nested_tag in nested_tags:
            match = data_model.find_full_name(nested_tag)
            if not match:
                # not in model, use last word
                name = nested_tag.split('|')[-1]
                if name not in keywords:
                    keywords.append(name)
                continue
            # ascend hierarchy, copying all copyable words
            while match:
                if match.checked('copyable'):
                    name = match.text()
                    if name not in keywords:
                        keywords.append(name)
                match = match.parent()
        self.widgets['keywords'].set_value('; '.join(keywords))
        self.widgets['keywords'].emit_value()

    def refresh(self):
        self.new_selection(self.app.image_list.get_selected_images())

    def do_not_close(self):
        return False

    @QtSlot()
    @catch_all
    def image_list_changed(self):
        self.widgets['keywords'].update_league_table(
            self.app.image_list.get_images())

    @QtSlot(str, str, str)
    @catch_all
    def update_value(self, key, old_value, new_value):
        images = self.app.image_list.get_selected_images()
        for image in images:
            value = list(getattr(image.metadata, key))
            if old_value in value:
                value.remove(old_value)
            if new_value not in value:
                value.append(new_value)
            setattr(image.metadata, key, value)
        self._update_widget(key, images)

    @QtSlot(dict)
    @catch_all
    def new_value(self, value):
        key, value = list(value.items())[0]
        images = self.app.image_list.get_selected_images()
        for image in images:
            setattr(image.metadata, key, value)
        self._update_widget(key, images)
        if key == 'keywords':
            self.widgets[key].update_league_table(images)

    def _update_widget(self, key, images):
        if not images:
            return
        values = []
        for image in images:
            value = getattr(image.metadata, key)
            if value not in values:
                values.append(value)
        if len(values) > 1:
            self.widgets[key].set_multiple(choices=[x for x in values if x])
        else:
            self.widgets[key].set_value(values[0])
        if key == 'nested_tags':
            self.buttons['open_tree'].setEnabled(
                not self.widgets[key].is_multiple())
            self.buttons['copy_to_flat'].setEnabled(
                bool(self.widgets[key].get_value()))
        elif key == 'keywords':
            self.buttons['copy_from_flat'].setEnabled(
                bool(self.widgets[key].get_value()))

    def new_selection(self, selection):
        if not selection:
            for key in self.widgets:
                self.widgets[key].set_value(None)
            self.setEnabled(False)
            return
        for key in self.widgets:
            self._update_widget(key, selection)
        self.setEnabled(True)
