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
import logging

from photini.metadata import ImageMetadata
from photini.pyqt import *
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


class HtmlTextEdit(QtWidgets.QTextEdit, TextEditMixin):
    def __init__(self, key, *arg, spell_check=False, length_check=None,
                 multi_string=False, length_always=False, length_bytes=True,
                 min_width=None, **kw):
        super(HtmlTextEdit, self).__init__(*arg, **kw)
        self.init_mixin(key,spell_check, length_check, length_always,
                        length_bytes, multi_string, min_width)
        self.setFixedHeight(QtWidgets.QLineEdit().sizeHint().height())
        self.setLineWrapMode(self.LineWrapMode.NoWrap)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    @catch_all
    def focusOutEvent(self, event):
        self.emit_value()
        super(HtmlTextEdit, self).focusOutEvent(event)

    @catch_all
    def keyPressEvent(self, event):
        self.set_multiple(multiple=False)
        super(HtmlTextEdit, self).keyPressEvent(event)

    @catch_all
    def contextMenuEvent(self, event):
        self.context_menu_event(event)

    def get_value(self):
        return self.toPlainText()


class HierarchicalTagDataItem(QtGui.QStandardItem):
    def __lt__(self, other):
        return self.text().lower() < other.text().lower()

class HierarchicalTagDataModel(QtGui.QStandardItemModel):
    def __init__(self, *args, **kwds):
        super(HierarchicalTagDataModel, self).__init__(*args, **kwds)
        self.setHorizontalHeaderLabels([
            translate('KeywordsTab', 'keyword'),
            translate('KeywordsTab', 'set'),
            ])
        self.sort(0)

    def find_tag(self, tag, create=True):
        parent = self.invisibleRootItem()
        for part in tag.split('|'):
            for row in range(parent.rowCount()):
                child = parent.child(row)
                if child.text() == part:
                    break
            else:
                if not create:
                    return None
                child = HierarchicalTagDataItem(part)
                set_item = QtGui.QStandardItem()
                set_item.setCheckable(True)
                parent.appendRow([child, set_item])
            parent = child
        return child

    def all_rows(self, parent=None):
        parent = parent or {'name': '', 'node': self.invisibleRootItem()}
        for row in range(parent['node'].rowCount()):
            nodes = [parent['node'].child(row, column)
                     for column in range(parent['node'].columnCount())]
            name = parent['name'] + nodes[0].text()
            yield name, nodes
            for result in self.all_rows({'name': name + '|', 'node': nodes[0]}):
                yield result


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
        self.set_rows()
        # initialise vocabulary model
        self.data_model = HierarchicalTagDataModel()

    def set_rows(self, rows=1):
        layout = self.widget().layout()
        rows = max(rows, 1)
        idx = layout.count() - 1
        while idx < rows:
            widget = HtmlTextEdit(str(idx), spell_check=True)
            widget.new_value.connect(self._new_value)
            layout.insertWidget(idx, widget)
            idx += 1
        while idx > rows:
            idx -= 1
            widget = layout.itemAt(idx).widget()
            layout.removeWidget(widget)

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
                widget.set_value(value[idx])
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
        dialog = QtWidgets.QDialog(parent=self)
        dialog.setWindowTitle(
            translate('KeywordsTab', 'Edit keyword hierarchy'))
        dialog.setLayout(QtWidgets.QVBoxLayout())
        # find tags in model, adding them if necessary
        value = self.get_value()
        tag_idx = []
        for tag in value:
            child = self.data_model.find_tag(tag)
            tag_idx.append(child.index())
        # sort model
        self.data_model.sort(0)
        # tree view of keywords
        tree = QtWidgets.QTreeView()
        tree.setUniformRowHeights(True)
        tree.setSizeAdjustPolicy(
            tree.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        tree.setModel(self.data_model)
        # set check boxes and expand all items in value
        for tag, nodes in self.data_model.all_rows():
            set_item = nodes[1]
            if tag in value:
                set_item.setCheckState(Qt.CheckState.Checked)
                parent = nodes[0].parent()
                while parent:
                    tree.expand(parent.index())
                    parent = parent.parent()
            else:
                set_item.setCheckState(Qt.CheckState.Unchecked)
        tree.resizeColumnToContents(0)
        dialog.layout().addWidget(tree)
        # buttons
        button_box = QtWidgets.QDialogButtonBox()
        button_box.addButton(
            button_box.StandardButton.Ok).clicked.connect(dialog.accept)
        button_box.addButton(
            button_box.StandardButton.Apply).clicked.connect(self.apply_changes)
        button_box.addButton(
            button_box.StandardButton.Cancel).clicked.connect(dialog.reject)
        dialog.layout().addWidget(button_box)
        if execute(dialog) == QtWidgets.QDialog.DialogCode.Accepted:
            self.apply_changes()
        else:
            self.set_value(value)
            self.emit_value()

    @QtSlot()
    @catch_all
    def apply_changes(self):
        # construct new value
        new_value = []
        for tag, nodes in self.data_model.all_rows():
            set_item = nodes[1]
            if set_item.checkState() == Qt.CheckState.Checked:
                new_value.append(tag)
        self.set_value(new_value)
        self.emit_value()


class TabWidget(QtWidgets.QWidget):
    @staticmethod
    def tab_name():
        return translate('KeywordsTab', '&Keywords')

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
        layout.addRow('', buttons)
        # make connections
        self.buttons['open_tree'].clicked.connect(
            self.widgets['nested_tags'].open_tree_view)
        self.app.image_list.image_list_changed.connect(self.image_list_changed)
        # disable until an image is selected
        self.setEnabled(False)

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

    def new_selection(self, selection):
        if not selection:
            for key in self.widgets:
                self.widgets[key].set_value(None)
            self.setEnabled(False)
            return
        for key in self.widgets:
            self._update_widget(key, selection)
        self.setEnabled(True)
        self.buttons['open_tree'].setEnabled(
            not self.widgets['nested_tags'].is_multiple())
