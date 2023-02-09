# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-22  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from datetime import date, datetime
import logging

from photini.metadata import ImageMetadata
from photini.pyqt import *
from photini.widgets import (
    ComboBox, Label, LangAltWidget, MultiLineEdit, SingleLineEdit, Slider)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class RatingWidget(QtWidgets.QWidget):
    new_value = QtSignal(str, object)

    def __init__(self, key, *arg, **kw):
        super(RatingWidget, self).__init__(*arg, **kw)
        self._key = key
        self.multiple_values = multiple_values()
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        # slider
        self.slider = Slider(Qt.Orientation.Horizontal)
        self.slider.setFixedWidth(width_for_text(self.slider, 'x' * 25))
        self.slider.setRange(-2, 5)
        self.slider.setPageStep(1)
        self.slider.valueChanged.connect(self.set_display)
        self.slider.editing_finished.connect(self._new_value)
        self.layout().addWidget(self.slider)
        # display
        self.display = QtWidgets.QLineEdit()
        if self.display.isRightToLeft():
            self.display.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.display.setStyleSheet("* {background-color:rgba(0,0,0,0);}")
        self.display.setFrame(False)
        self.display.setReadOnly(True)
        self.display.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.display.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.layout().addWidget(self.display)
        # adopt child methods/signals
        self.is_multiple = self.slider.is_multiple

    @QtSlot()
    @catch_all
    def _new_value(self):
        self.new_value.emit(self._key, self.get_value())

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
        self.edit = SingleLineEdit(key, **kw)
        layout.addWidget(self.edit)
        # favourites drop down
        self.favourites = ComboBox()
        self.favourites.addItem(translate('DescriptiveTab', '<favourites>'))
        self.favourites.setFixedWidth(width_for_text(self.favourites, 'x' * 16))
        self.update_favourites()
        self.favourites.currentIndexChanged.connect(self.add_favourite)
        layout.addWidget(self.favourites)
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
            keywords = image.metadata.keywords or []
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
        self.new_value.emit(self.edit._key, new_value)


class TabWidget(QtWidgets.QScrollArea):
    @staticmethod
    def tab_name():
        return translate('DescriptiveTab', '&Descriptive metadata')

    def __init__(self, *arg, **kw):
        super(TabWidget, self).__init__(*arg, **kw)
        self.app = QtWidgets.QApplication.instance()
        self.setFrameStyle(QtWidgets.QFrame.Shape.NoFrame)
        self.setWidget(QtWidgets.QWidget())
        self.setWidgetResizable(True)
        layout = FormLayout()
        self.widget().setLayout(layout)
        # construct widgets
        self.widgets = {}
        # title
        self.widgets['title'] = LangAltWidget(
            'title', multi_line=False, spell_check=True,
            length_check=ImageMetadata.max_bytes('title'))
        self.widgets['title'].setToolTip('<p>{}</p>'.format(translate(
            'DescriptiveTab', 'Enter a short verbal and human readable name'
            ' for the image, this may be the file name.')))
        self.widgets['title'].new_value.connect(self.new_value)
        layout.addRow(translate('DescriptiveTab', 'Title / Object Name'),
                      self.widgets['title'])
        # headline
        self.widgets['headline'] = MultiLineEdit(
            'headline', spell_check=True,
            length_check=ImageMetadata.max_bytes('headline'))
        self.widgets['headline'].set_height(3)
        self.widgets['headline'].setToolTip('<p>{}</p>'.format(translate(
            'DescriptiveTab', 'Enter a brief publishable synopsis or summary'
            ' of the contents of the image.')))
        self.widgets['headline'].new_value.connect(self.new_value)
        layout.addRow(translate('DescriptiveTab', 'Headline'),
                      self.widgets['headline'])
        # description
        self.widgets['description'] = LangAltWidget(
            'description', spell_check=True,
            length_check=ImageMetadata.max_bytes('description'))
        self.widgets['description'].setToolTip('<p>{}</p>'.format(translate(
            'DescriptiveTab', 'Enter a "caption" describing the who, what,'
            ' and why of what is happening in this image, this might include'
            ' names of people, and/or their role in the action that is taking'
            ' place within the image.')))
        self.widgets['description'].new_value.connect(self.new_value)
        layout.addRow(translate('DescriptiveTab', 'Description / Caption'),
                      self.widgets['description'])
        # alt text
        self.widgets['alt_text'] = LangAltWidget(
            'alt_text', spell_check=True, length_check=250, length_always=True)
        self.widgets['alt_text'].set_height(3)
        self.widgets['alt_text'].setToolTip('<p>{}</p>'.format(translate(
            'DescriptiveTab', 'Enter text describing the appearance of the'
            ' image from a visual perspective, focusing on details that are'
            ' relevant to the purpose and meaning of the image.')))
        self.widgets['alt_text'].new_value.connect(self.new_value)
        layout.addRow(
            Label(translate('DescriptiveTab', 'Alt Text (Accessibility)'),
                  lines=2, layout=layout), self.widgets['alt_text'])
        # extended alt text
        self.widgets['alt_text_ext'] = LangAltWidget(
            'alt_text_ext', spell_check=True)
        self.widgets['alt_text_ext'].setToolTip('<p>{}</p>'.format(translate(
            'DescriptiveTab', 'A more detailed textual description of the'
            ' purpose and meaning of an image that elaborates on the'
            ' information provided by the Alt Text (Accessibility) property.'
            ' This property does not have a character limitation and is not'
            ' required if the Alt Text (Accessibility) field sufficiently'
            ' describes the image..')))
        self.widgets['alt_text_ext'].new_value.connect(self.new_value)
        layout.addRow(
            Label(translate('DescriptiveTab',
                            'Extended Description (Accessibility)'),
                  lines=2, layout=layout), self.widgets['alt_text_ext'])
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
        self.app.image_list.image_list_changed.connect(self.image_list_changed)
        # rating
        self.widgets['rating'] = RatingWidget('rating')
        self.widgets['rating'].new_value.connect(self.new_value)
        layout.addRow(translate('DescriptiveTab', 'Rating'),
                      self.widgets['rating'])
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

    @QtSlot(str, object)
    @catch_all
    def new_value(self, key, value):
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
