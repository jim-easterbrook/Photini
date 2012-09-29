# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt

class MultiLineEdit(QtGui.QPlainTextEdit):
    editingFinished = QtCore.pyqtSignal()
    def focusOutEvent(self, event):
        self.editingFinished.emit()

class LineEditWithAuto(QtGui.QWidget):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        layout = QtGui.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        # line edit box
        self.edit = QtGui.QLineEdit()
        layout.addWidget(self.edit)
        # auto complete button
        self.auto = QtGui.QPushButton('Auto')
        layout.addWidget(self.auto)
        # adopt child widget methods and signals
        self.editingFinished = self.edit.editingFinished
        self.setText = self.edit.setText
        self.clear = self.edit.clear
        self.text = self.edit.text
        self.autoComplete = self.auto.clicked

class TextMetadata(QtGui.QWidget):
    def __init__(self, config_store, image_list, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.config_store = config_store
        self.image_list = image_list
        self.selection = list()
        self.form = QtGui.QFormLayout()
        self.setLayout(self.form)
        # title
        self.title = QtGui.QLineEdit()
        self.title.editingFinished.connect(self.new_title)
        self.form.addRow('Title / Object Name', self.title)
        # description
        self.description = MultiLineEdit()
        self.description.editingFinished.connect(self.new_description)
        self.form.addRow('Description / Caption', self.description)
        # keywords
        self.keywords = QtGui.QLineEdit()
        self.keywords.editingFinished.connect(self.new_keywords)
        self.form.addRow('Keywords', self.keywords)
        # copyright
        self.copyright = LineEditWithAuto()
        self.copyright.editingFinished.connect(self.new_copyright)
        self.copyright.autoComplete.connect(self.auto_copyright)
        self.form.addRow('Copyright', self.copyright)
        # creator
        self.creator = QtGui.QLineEdit()
        self.creator.editingFinished.connect(self.new_creator)
        self.form.addRow('Creator / Artist', self.creator)

    date_keys = ('Exif.Photo.DateTimeOriginal', 'Exif.Photo.DateTimeDigitized',
                 'Exif.Image.DateTime')
    title_keys = ('Xmp.dc.title', 'Iptc.Application2.ObjectName',
                  'Exif.Image.ImageDescription')
    creator_keys = ('Xmp.dc.creator', 'Iptc.Application2.Byline',
                    'Exif.Image.Artist')
    description_keys = ('Xmp.dc.description', 'Iptc.Application2.Caption')
    keywords_keys = ('Xmp.dc.subject', 'Iptc.Application2.Keywords')
    copyright_keys = ('Xmp.dc.rights', 'Xmp.tiff.Copyright',
                      'Iptc.Application2.Copyright', 'Exif.Image.Copyright')

    def new_title(self):
        value = [unicode(self.title.text()).strip()]
        for image in self.selection:
            image.set_metadata(self.title_keys, value)

    def new_description(self):
        value = [unicode(self.description.toPlainText()).strip()]
        for image in self.selection:
            image.set_metadata(self.description_keys, value)

    def new_keywords(self):
        value = map(lambda x: unicode(x).strip(),
                    self.keywords.text().split(';'))
        for image in self.selection:
            image.set_metadata(self.keywords_keys, value)

    def new_copyright(self):
        value = [unicode(self.copyright.text()).strip()]
        for image in self.selection:
            image.set_metadata(self.copyright_keys, value)

    def auto_copyright(self):
        name = self.config_store.get('user', 'copyright_name')
        if not name:
            name, OK = QtGui.QInputDialog.getText(
                self, 'Input name', "Please type in the copyright holder's name")
            if OK and name:
                name = unicode(name)
                self.config_store.set('user', 'copyright_name', name)
            else:
                name = ''
        for image in self.selection:
            date = image.get_metadata(self.date_keys)
            value = u'Copyright ©%d %s. All rights reserved.' % (date.year, name)
            image.set_metadata(self.copyright_keys, [value])
        self.new_selection(self.selection)

    def new_creator(self):
        value = [unicode(self.creator.text()).strip()]
        for image in self.selection:
            image.set_metadata(self.creator_keys, value)

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        self.selection = selection
        if not self.selection:
            self.title.clear()
            self.description.clear()
            self.keywords.clear()
            self.copyright.clear()
            self.creator.clear()
            return
        # get info from first image
        image = self.selection[0]
        new_title = image.get_metadata(self.title_keys)
        new_description = image.get_metadata(self.description_keys)
        new_keywords = image.get_metadata(self.keywords_keys)
        new_copyright = image.get_metadata(self.copyright_keys)
        new_creator = image.get_metadata(self.creator_keys)
        # check remaining images
        for image in self.selection[1:]:
            if new_title != image.get_metadata(self.title_keys):
                new_title = [u'<multiple values>']
                break
        for image in self.selection[1:]:
            if new_description != image.get_metadata(self.description_keys):
                new_description = [u'<multiple values>']
                break
        for image in self.selection[1:]:
            if new_keywords != image.get_metadata(self.keywords_keys):
                new_keywords = [u'<multiple values>']
                break
        for image in self.selection[1:]:
            if new_copyright != image.get_metadata(self.copyright_keys):
                new_copyright = [u'<multiple values>']
                break
        for image in self.selection[1:]:
            if new_creator != image.get_metadata(self.creator_keys):
                new_creator = [u'<multiple values>']
                break
        # update GUI
        if new_title:
            self.title.setText(new_title[0])
        else:
            self.title.clear()
        if new_description:
            self.description.setPlainText(new_description[0])
        else:
            self.description.clear()
        if new_keywords:
            self.keywords.setText('; '.join(new_keywords))
        else:
            self.keywords.clear()
        if new_copyright:
            self.copyright.setText(new_copyright[0])
        else:
            self.copyright.clear()
        if new_creator:
            self.creator.setText(new_creator[0])
        else:
            self.creator.clear()

