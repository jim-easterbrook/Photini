##  Photini - a simple photo metedata editor.
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

class TextMetadata(QtGui.QWidget):
    def __init__(self, config_store, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.config_store = config_store
        self.selection = list()
        self.form = QtGui.QFormLayout()
        self.setLayout(self.form)
        self.title = QtGui.QLineEdit()
        self.form.addRow('Title / Object Name', self.title)
        self.description = QtGui.QPlainTextEdit()
        self.form.addRow('Description / Caption', self.description)
        self.keywords = QtGui.QLineEdit()
        self.form.addRow('Keywords', self.keywords)
        self.copyright = QtGui.QLineEdit()
        self.form.addRow('Copyright', self.copyright)
        self.creator = QtGui.QLineEdit()
        self.form.addRow('Creator / Artist', self.creator)

    title_keys = ('Xmp.dc.title', 'Iptc.Application2.ObjectName',
                  'Exif.Image.ImageDescription')
    creator_keys = ('Xmp.dc.creator', 'Iptc.Application2.Byline',
                    'Exif.Image.Artist')
    description_keys = ('Xmp.dc.description', 'Iptc.Application2.Caption')
    keywords_keys = ('Xmp.dc.subject', 'Iptc.Application2.Keywords')
    copyright_keys = ('Xmp.dc.rights', 'Xmp.tiff.Copyright',
                      'Iptc.Application2.Copyright', 'Exif.Image.Copyright')

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

