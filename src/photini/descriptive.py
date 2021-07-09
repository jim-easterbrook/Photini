# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-21  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from collections import defaultdict
from datetime import datetime
import logging

from photini.exiv2 import ImageMetadata
from photini.pyqt import (
    catch_all, ComboBox, multiple_values, MultiLineEdit, Qt, QtCore, QtGui,
    QtSlot, QtWidgets, SingleLineEdit, Slider)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class LineEditWithAuto(QtWidgets.QWidget):
    def __init__(self, **kw):
        super(LineEditWithAuto, self).__init__()
        self._is_multiple = False
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # line edit box
        self.edit = SingleLineEdit(**kw)
        layout.addWidget(self.edit)
        # auto complete button
        self.auto = QtWidgets.QPushButton(translate('DescriptiveTab', 'Auto'))
        layout.addWidget(self.auto)
        # adopt child widget methods and signals
        self.set_value = self.edit.set_value
        self.get_value = self.edit.get_value
        self.set_multiple = self.edit.set_multiple
        self.is_multiple = self.edit.is_multiple
        self.editingFinished = self.edit.editingFinished
        self.autoComplete = self.auto.clicked


class RatingWidget(QtWidgets.QWidget):
    def __init__(self, *arg, **kw):
        super(RatingWidget, self).__init__(*arg, **kw)
        self.multiple_values = multiple_values()
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        # slider
        self.slider = Slider(Qt.Horizontal)
        self.slider.setFixedWidth(200)
        self.slider.setRange(-2, 5)
        self.slider.setPageStep(1)
        self.slider.valueChanged.connect(self.set_display)
        self.layout().addWidget(self.slider)
        # display
        self.display = QtWidgets.QLineEdit()
        self.display.setStyleSheet("* {background-color:rgba(0,0,0,0);}")
        self.display.setFrame(False)
        self.display.setReadOnly(True)
        self.display.setContextMenuPolicy(Qt.NoContextMenu)
        self.display.setFocusPolicy(Qt.NoFocus)
        self.layout().addWidget(self.display)
        # adopt child methods/signals
        self.is_multiple = self.slider.is_multiple
        self.editing_finished = self.slider.editing_finished

    @QtSlot(int)
    @catch_all
    def set_display(self, value):
        self.display.setPlaceholderText('')
        if value == -2:
            self.display.clear()
        elif value == -1:
            self.display.setText(translate('DescriptiveTab', 'reject'))
        else:
            self.display.setText((chr(0x2605) * value) +
                                 (chr(0x2606) * (5 - value)))

    def set_value(self, value):
        if not value:
            self.slider.set_value(-2)
        else:
            self.slider.set_value(int(value + 1.5) - 1)
        self.set_display(self.slider.value())

    def get_value(self):
        value = self.slider.value()
        if value == -2:
            return None
        return value

    def set_multiple(self, choices=[]):
        self.slider.set_multiple()
        self.slider.setValue(-2)
        self.display.setPlaceholderText(self.multiple_values)


class KeywordsEditor(QtWidgets.QWidget):
    def __init__(self, **kw):
        super(KeywordsEditor, self).__init__()
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.league_table = defaultdict(int)
        for keyword, score in eval(self.config_store.get(
            'descriptive', 'keywords', '{}')).items():
            self.league_table[keyword] = score
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # line edit box
        self.edit = SingleLineEdit(**kw)
        layout.addWidget(self.edit)
        # favourites drop down
        self.favourites = ComboBox()
        self.update_favourites()
        self.favourites.setFixedWidth(self.favourites.title_width())
        self.favourites.currentIndexChanged.connect(self.add_favourite)
        layout.addWidget(self.favourites)
        # adopt child widget methods and signals
        self.get_value = self.edit.get_value
        self.set_value = self.edit.set_value
        self.set_multiple = self.edit.set_multiple
        self.is_multiple = self.edit.is_multiple
        self.editingFinished = self.edit.editingFinished

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
        for image in images:
            value = list(filter(lambda x: not x.startswith('flickr:photo_id'),
                                image.metadata.keywords or []))
            if not value:
                continue
            for keyword in self.league_table:
                self.league_table[keyword] = max(
                    self.league_table[keyword] - 1, -5)
            for keyword in value:
                self.league_table[keyword] = min(
                    self.league_table[keyword] + 10, 1000)
        self.config_store.set(
            'descriptive', 'keywords', str(dict(self.league_table)))
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
        self.editingFinished.emit()


class TabWidget(QtWidgets.QWidget):
    @staticmethod
    def tab_name():
        return translate('DescriptiveTab', '&Descriptive metadata')

    def __init__(self, image_list, *arg, **kw):
        super(TabWidget, self).__init__(*arg, **kw)
        self.config_store = QtWidgets.QApplication.instance().config_store
        self.image_list = image_list
        self.form = QtWidgets.QFormLayout()
        self.setLayout(self.form)
        # construct widgets
        self.widgets = {}
        # title
        self.widgets['title'] = SingleLineEdit(
            spell_check=True,
            length_check=ImageMetadata.max_bytes('title'))
        self.widgets['title'].setToolTip(translate(
            'DescriptiveTab', 'Enter a short verbal and human readable name'
            ' for the image, this may be the file name.'))
        self.widgets['title'].editingFinished.connect(self.new_title)
        self.form.addRow(translate(
            'DescriptiveTab', 'Title / Object Name'), self.widgets['title'])
        # description
        self.widgets['description'] = MultiLineEdit(
            spell_check=True,
            length_check=ImageMetadata.max_bytes('description'))
        self.widgets['description'].setToolTip(translate(
            'DescriptiveTab', 'Enter a "caption" describing the who, what,'
            ' and why of what is happening in this image,\nthis might include'
            ' names of people, and/or their role in the action that is taking'
            ' place within the image.'))
        self.widgets['description'].editingFinished.connect(
            self.new_description)
        self.form.addRow(
            translate('DescriptiveTab', 'Description / Caption'),
            self.widgets['description'])
        # keywords
        self.widgets['keywords'] = KeywordsEditor(
            spell_check=True, length_check=ImageMetadata.max_bytes('keywords'),
            multi_string=True)
        self.widgets['keywords'].setToolTip(translate(
            'DescriptiveTab', 'Enter any number of keywords, terms or phrases'
            ' used to express the subject matter in the image.'
            '\nSeparate them with ";" characters.'))
        self.widgets['keywords'].editingFinished.connect(self.new_keywords)
        self.form.addRow(translate(
            'DescriptiveTab', 'Keywords'), self.widgets['keywords'])
        self.image_list.image_list_changed.connect(self.image_list_changed)
        # rating
        self.widgets['rating'] = RatingWidget()
        self.widgets['rating'].editing_finished.connect(self.new_rating)
        self.form.addRow(translate(
            'DescriptiveTab', 'Rating'), self.widgets['rating'])
        # copyright
        self.widgets['copyright'] = LineEditWithAuto(
            length_check=ImageMetadata.max_bytes('copyright'))
        self.widgets['copyright'].setToolTip(translate(
            'OwnerTab', 'Enter a notice on the current owner of the'
            ' copyright for this image, such as "©2008 Jane Doe".'))
        self.widgets['copyright'].editingFinished.connect(self.new_copyright)
        self.widgets['copyright'].autoComplete.connect(self.auto_copyright)
        self.form.addRow(translate(
            'DescriptiveTab', 'Copyright'), self.widgets['copyright'])
        # creator
        self.widgets['creator'] = LineEditWithAuto(
            length_check=ImageMetadata.max_bytes('creator'), multi_string=True)
        self.widgets['creator'].setToolTip(translate(
            'OwnerTab',
            'Enter the name of the person that created this image.'))
        self.widgets['creator'].editingFinished.connect(self.new_creator)
        self.widgets['creator'].autoComplete.connect(self.auto_creator)
        self.form.addRow(translate(
            'DescriptiveTab', 'Creator / Artist'), self.widgets['creator'])
        # disable until an image is selected
        self.setEnabled(False)

    def refresh(self):
        images = self.image_list.get_selected_images()
        for key in self.widgets:
            self._update_widget(key, images)

    def do_not_close(self):
        return False

    @QtSlot()
    @catch_all
    def image_list_changed(self):
        self.widgets['keywords'].update_league_table(
            self.image_list.get_images())

    @QtSlot()
    @catch_all
    def new_title(self):
        self._new_value('title')

    @QtSlot()
    @catch_all
    def new_description(self):
        self._new_value('description')

    @QtSlot()
    @catch_all
    def new_keywords(self):
        self._new_value('keywords')
        self.widgets['keywords'].update_league_table(
            self.image_list.get_selected_images())

    @QtSlot()
    @catch_all
    def new_rating(self):
        self._new_value('rating')

    @QtSlot()
    @catch_all
    def new_copyright(self):
        self._new_value('copyright')

    @QtSlot()
    @catch_all
    def new_creator(self):
        self._new_value('creator')

    @QtSlot()
    @catch_all
    def auto_copyright(self):
        name = self.config_store.get('user', 'copyright_name')
        if not name:
            name, OK = QtWidgets.QInputDialog.getText(
                self, translate('DescriptiveTab', 'Photini: input name'),
                translate('DescriptiveTab',
                          "Please type in the copyright holder's name"),
                text=self.config_store.get('user', 'creator_name', ''))
            if OK and name:
                self.config_store.set('user', 'copyright_name', name)
            else:
                name = ''
        copyright_text = self.config_store.get(
            'user', 'copyright_text',
            translate('DescriptiveTab',
                      'Copyright ©{year} {name}. All rights reserved.'))
        images = self.image_list.get_selected_images()
        for image in images:
            date_taken = image.metadata.date_taken
            if date_taken is None:
                date_taken = datetime.now()
            else:
                date_taken = date_taken['datetime']
            value = copyright_text.format(year=date_taken.year, name=name)
            image.metadata.copyright = value
        self._update_widget('copyright', images)

    @QtSlot()
    @catch_all
    def auto_creator(self):
        name = self.config_store.get('user', 'creator_name')
        if not name:
            name, OK = QtWidgets.QInputDialog.getText(
                self, translate('DescriptiveTab', 'Photini: input name'),
                translate('DescriptiveTab', "Please type in the creator's name"),
                text=self.config_store.get('user', 'copyright_name', ''))
            if OK and name:
                self.config_store.set('user', 'creator_name', name)
            else:
                name = ''
        images = self.image_list.get_selected_images()
        for image in images:
            image.metadata.creator = name
        self._update_widget('creator', images)

    def _new_value(self, key):
        images = self.image_list.get_selected_images()
        if not self.widgets[key].is_multiple():
            value = self.widgets[key].get_value()
            for image in images:
                setattr(image.metadata, key, value)
        self._update_widget(key, images)

    def _update_widget(self, key, images):
        if not images:
            return
        values = []
        for image in images:
            value = getattr(image.metadata, key)
            if value not in values:
                values.append(value)
        if len(values) > 1:
            self.widgets[key].set_multiple(choices=filter(None, values))
        else:
            self.widgets[key].set_value(values[0])

    @QtSlot(list)
    @catch_all
    def new_selection(self, selection):
        if not selection:
            for key in self.widgets:
                self.widgets[key].set_value(None)
            self.setEnabled(False)
            return
        for key in self.widgets:
            self._update_widget(key, selection)
        self.setEnabled(True)
