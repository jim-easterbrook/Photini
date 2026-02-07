##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-26  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from photini.metadata import ImageMetadata
from photini.pyqt import *
from photini.widgets import (
    CompoundWidgetMixin, ContextMenuMixin, Label, LangAltWidget, MultiLineEdit,
    SingleLineEdit, Slider, TopLevelWidgetMixin)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class RatingWidget(QtWidgets.QWidget):
    def __init__(self, key, *arg, **kw):
        super(RatingWidget, self).__init__(*arg, **kw)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        self.multiple_values = multiple_values()
        self._key = key
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        # slider
        self.slider = Slider(key)
        self.slider.setOrientation(Qt.Orientation.Horizontal)
        self.slider.setFixedWidth(width_for_text(self.slider, 'x' * 25))
        self.slider.setRange(-2, 5)
        self.slider.setPageStep(1)
        self.slider.valueChanged.connect(self.set_display)
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
        self.emit_value = self.slider.emit_value
        self.get_value_dict = self.slider.get_value_dict
        self.is_multiple = self.slider.is_multiple
        self.new_value = self.slider.new_value
        self.set_enabled = self.slider.set_enabled
        self.set_value_dict = self.slider.set_value_dict
        self._load_data = self.slider._load_data
        self._save_data = self.slider._save_data
        # over-ride child methods
        self.slider.get_value = self.get_value
        self.slider.set_value = self.set_value

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
            self.slider.setValue(-2)
        else:
            self.slider.setValue(int(value + 1.5) - 1)
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


class DescriptiveData(QtWidgets.QWidget, TopLevelWidgetMixin,
                      ContextMenuMixin, CompoundWidgetMixin):
    clipboard_key = 'DescriptiveTab'

    def __init__(self, *arg, **kw):
        super(DescriptiveData, self).__init__(*arg, **kw)
        self.app = QtWidgets.QApplication.instance()
        layout = FormLayout()
        self.setLayout(layout)
        # construct widgets
        self.widgets = {}
        # title
        self.widgets['title'] = LangAltWidget(
            'title', multi_line=False, spell_check=True,
            length_check=ImageMetadata.max_bytes('title'))
        self.widgets['title'].setToolTip('<p>{}</p>'.format(translate(
            'DescriptiveTab', 'Enter a short verbal and human readable name'
            ' for the image, this may be the file name.')))
        self.widgets['title'].new_value.connect(self.save_data)
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
        self.widgets['headline'].new_value.connect(self.save_data)
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
        self.widgets['description'].new_value.connect(self.save_data)
        layout.addRow(translate('DescriptiveTab', 'Description / Caption'),
                      self.widgets['description'])
        # alt text
        self.widgets['alt_text'] = LangAltWidget(
            'alt_text', spell_check=True, length_check=250,
            length_always=True, length_bytes=False)
        self.widgets['alt_text'].set_height(3)
        self.widgets['alt_text'].setToolTip('<p>{}</p>'.format(translate(
            'DescriptiveTab', 'Enter text describing the appearance of the'
            ' image from a visual perspective, focusing on details that are'
            ' relevant to the purpose and meaning of the image.')))
        self.widgets['alt_text'].new_value.connect(self.save_data)
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
        self.widgets['alt_text_ext'].new_value.connect(self.save_data)
        layout.addRow(
            Label(translate('DescriptiveTab',
                            'Extended Description (Accessibility)'),
                  lines=2, layout=layout), self.widgets['alt_text_ext'])
        # people
        self.widgets['people'] = SingleLineEdit(
            'people', spell_check=True, multi_string=True)
        self.widgets['people'].setToolTip('<p>{}</p>'.format(translate(
            'DescriptiveTab', 'Enter the name(s) of the person(s) shown in this'
            ' image. Separate them with ";" characters.')))
        self.widgets['people'].new_value.connect(self.save_data)
        layout.addRow(translate('DescriptiveTab', 'Person(s) shown'),
                      self.widgets['people'])
        # rating
        self.widgets['rating'] = RatingWidget('rating')
        self.widgets['rating'].new_value.connect(self.save_data)
        layout.addRow(translate('DescriptiveTab', 'Rating'),
                      self.widgets['rating'])

    def sub_widgets(self):
        return self.widgets.values()


class TabWidget(QtWidgets.QScrollArea):
    @staticmethod
    def tab_name():
        return translate('DescriptiveTab', 'Descriptive metadata',
                         'Full name of tab shown as a tooltip')

    @staticmethod
    def tab_short_name():
        return translate('DescriptiveTab', '&Descriptive',
                         'Shortest possible name used as tab label')

    def __init__(self, *arg, **kw):
        super(TabWidget, self).__init__(*arg, **kw)
        self.app = QtWidgets.QApplication.instance()
        self.setFrameStyle(QtWidgets.QFrame.Shape.NoFrame)
        self.setWidget(QtWidgets.QWidget())
        self.setWidgetResizable(True)
        form = DescriptiveData()
        form.tab_short_name = self.tab_short_name
        self.setWidget(form)

    @catch_all
    def contextMenuEvent(self, event):
        self.widget().compound_context_menu(event)

    def refresh(self):
        self.new_selection(self.app.image_list.get_selected_images())

    def do_not_close(self):
        return False

    def new_selection(self, selection):
        self.widget().load_data(selection)
