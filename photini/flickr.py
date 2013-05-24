# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-13  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import os
import time

import flickrapi
from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt

class UploadThread(QtCore.QThread):
    def __init__(self, flickr, upload_list, photosets):
        QtCore.QThread.__init__(self)
        self.flickr = flickr
        self.upload_list = upload_list
        self.photosets = photosets

    finished = QtCore.pyqtSignal()
    def run(self):
        self.file_count = 0
        for params in self.upload_list:
            params['callback'] = self.callback
            rsp = self.flickr.upload(**params)
            if rsp.attrib['stat'] == 'ok':
                photo_id = rsp.find('photoid').text
                for photoset_id in self.photosets:
                    self.flickr.photosets_addPhoto(
                        photo_id=photo_id, photoset_id=photoset_id)
            else:
                dialog = QtGui.QMessageBox()
                dialog.setWindowTitle('Photini: upload failed')
                dialog.setText('<h3>Upload failed.</h3>')
                dialog.setInformativeText(
                    'Upload of %s failed' % os.path.basename(params['filename']))
                dialog.setIcon(QtGui.QMessageBox.Warning)
                dialog.setStandardButtons(
                    QtGui.QMessageBox.Abort | QtGui.QMessageBox.Ignore)
                if dialog.exec_() == QtGui.QMessageBox.Abort:
                    break
            self.file_count += 1
        self.finished.emit()

    progress_report = QtCore.pyqtSignal(float, float)
    def callback(self, progress, done):
        total_progress = (
            (self.file_count * 100) + progress) / len(self.upload_list)
        self.progress_report.emit(progress, total_progress)

class FlickrUploader(QtGui.QWidget):
    def __init__(self, config_store, image_list, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.config_store = config_store
        self.image_list = image_list
        self.setLayout(QtGui.QGridLayout())
        self.flickr = None
        self.photosets = list()
        self.uploader = None
        # privacy settings
        self.privacy = dict()
        privacy_group = QtGui.QGroupBox('Who can see the photos?')
        privacy_group.setLayout(QtGui.QVBoxLayout())
        self.privacy['private'] = QtGui.QRadioButton('Only you')
        privacy_group.layout().addWidget(self.privacy['private'])
        ff_group = QtGui.QGroupBox()
        ff_group.setFlat(True)
        ff_group.setLayout(QtGui.QVBoxLayout())
        self.privacy['friends'] = QtGui.QCheckBox('Your friends')
        ff_group.layout().addWidget(self.privacy['friends'])
        self.privacy['family'] = QtGui.QCheckBox('Your family')
        ff_group.layout().addWidget(self.privacy['family'])
        privacy_group.layout().addWidget(ff_group)
        self.privacy['public'] = QtGui.QRadioButton('Anyone')
        self.privacy['public'].toggled.connect(self.enable_ff)
        self.privacy['public'].setChecked(True)
        privacy_group.layout().addWidget(self.privacy['public'])
        privacy_group.layout().addStretch(1)
        self.layout().addWidget(privacy_group, 0, 0, 2, 1)
        # content type
        self.content_type = dict()
        content_group = QtGui.QGroupBox('Content type')
        content_group.setLayout(QtGui.QVBoxLayout())
        self.content_type['photo'] = QtGui.QRadioButton('Photo')
        self.content_type['photo'].setChecked(True)
        content_group.layout().addWidget(self.content_type['photo'])
        self.content_type['screenshot'] = QtGui.QRadioButton('Screenshot')
        content_group.layout().addWidget(self.content_type['screenshot'])
        self.content_type['other'] = QtGui.QRadioButton('Art/Illustration')
        content_group.layout().addWidget(self.content_type['other'])
        content_group.layout().addStretch(1)
        self.layout().addWidget(content_group, 0, 1)
        # hidden
        self.hidden = QtGui.QCheckBox('Hidden from search')
        self.layout().addWidget(self.hidden, 1, 1)
        # 'go' button
        self.upload_button = QtGui.QPushButton('Upload now')
        self.upload_button.setEnabled(False)
        self.upload_button.clicked.connect(self.upload)
        self.layout().addWidget(self.upload_button, 1, 3)
        # progress bars
        self.layout().addWidget(QtGui.QLabel('File progress'), 3, 0, 1, 4)
        self.file_progress = QtGui.QProgressBar()
        self.layout().addWidget(self.file_progress, 4, 0, 1, 4)
        self.layout().addWidget(QtGui.QLabel('Overall progress'), 5, 0, 1, 4)
        self.total_progress = QtGui.QProgressBar()
        self.layout().addWidget(self.total_progress, 6, 0, 1, 4)
        # adjust spacing
        self.layout().setRowStretch(1, 1)

    def refresh(self):
        if self.flickr:
            return
        QtGui.QApplication.setOverrideCursor(Qt.WaitCursor)
        if not self.authorise():
            return
        sets = self.flickr.photosets_getList()
        for item in sets.find('photosets').findall('photoset'):
            self.photosets.append({
                'id'    : item.attrib['id'],
                'title' : item.find('title').text,
                })
        # list of sets widget
        if self.photosets:
            sets_group = QtGui.QGroupBox('Add to sets')
            sets_group.setLayout(QtGui.QVBoxLayout())
            sets_widget = QtGui.QWidget()
            self.sets = QtGui.QVBoxLayout()
            for item in self.photosets:
                self.sets.addWidget(
                    QtGui.QCheckBox(item['title'].replace('&', '&&')))
            sets_widget.setLayout(self.sets)
            scrollarea = QtGui.QScrollArea()
            scrollarea.setFrameStyle(QtGui.QFrame.NoFrame)
            scrollarea.setWidget(sets_widget)
            sets_group.layout().addWidget(scrollarea)
            self.layout().addWidget(sets_group, 0, 2, 2, 1)
        QtGui.QApplication.restoreOverrideCursor()

    @QtCore.pyqtSlot(bool)
    def enable_ff(self, value):
        self.privacy['friends'].setEnabled(self.privacy['private'].isChecked())
        self.privacy['family'].setEnabled(self.privacy['private'].isChecked())

    @QtCore.pyqtSlot()
    def upload(self):
        if not self.image_list.unsaved_files_dialog(with_discard=False):
            return
        is_public = ('0', '1')[self.privacy['public'].isChecked()]
        is_family = ('0', '1')[self.privacy['private'].isChecked() and
                               self.privacy['family'].isChecked()]
        is_friend = ('0', '1')[self.privacy['private'].isChecked() and
                               self.privacy['friends'].isChecked()]
        if self.content_type['photo'].isChecked():
            content_type = '1'
        elif self.content_type['screenshot'].isChecked():
            content_type = '2'
        else:
            content_type = '3'
        hidden = ('1', '2')[self.hidden.isChecked()]
        photosets = list()
        for idx in range(len(self.photosets)):
            if self.sets.itemAt(idx).widget().isChecked():
                photosets.append(self.photosets[idx]['id'])
        # make list of items to upload
        upload_list = list()
        for image in self.image_list.get_selected_images():
            title = image.metadata.get_item('title')
            if not title:
                title = os.path.basename(image.path)
            description = image.metadata.get_item('description')
            if not description:
                description = ''
            tags = image.metadata.get_item('keywords')
            if tags:
                tags = ' '.join(
                    map(lambda x: '"%s"' % x.strip(), tags.split(';')))
            else:
                tags = ''
            upload_list.append({
                'filename'     : image.path,
                'title'        : title,
                'description'  : description,
                'tags'         : tags,
                'is_public'    : is_public,
                'is_friend'    : is_friend,
                'is_family'    : is_family,
                'content_type' : content_type,
                'hidden'       : hidden,
                })
        # pass the list to a separate thread, so GUI can continue
        if self.authorise():
            self.upload_button.setEnabled(False)
            self.uploader = UploadThread(self.flickr, upload_list, photosets)
            self.uploader.progress_report.connect(self.upload_progress)
            self.uploader.finished.connect(self.upload_done)
            self.uploader.start()

    @QtCore.pyqtSlot(float, float)
    def upload_progress(self, progress, total_progress):
        self.file_progress.setValue(progress)
        self.total_progress.setValue(total_progress)

    @QtCore.pyqtSlot()
    def upload_done(self):
        self.upload_button.setEnabled(True)
        self.file_progress.setValue(0)
        self.total_progress.setValue(0)
        self.uploader = None

    def authorise(self):
        if self.flickr:
            return True
        api_key = 'b6263c4693e3406aadcfaebe005280a5'
        api_secret = '1e0d912f586d0ed1'
        token = self.config_store.get('flickr', 'token', '')
        self.flickr = flickrapi.FlickrAPI(
            api_key, api_secret, token=token, store_token=False)
        token, frob = self.flickr.get_token_part_one(perms='write')
        if not token:
            QtGui.QApplication.setOverrideCursor(Qt.BusyCursor)
            dialog = QtGui.QMessageBox()
            dialog.setWindowTitle('Photini: authorise Flickr')
            dialog.setText('<h3>Flickr authorisation.</h3>')
            dialog.setInformativeText(
                'Please use your web browser to authorise Photini, then click OK')
            dialog.setIcon(QtGui.QMessageBox.Question)
            dialog.setStandardButtons(QtGui.QMessageBox.Ok)
            result = dialog.exec_()
            QtGui.QApplication.restoreOverrideCursor()
        token = self.flickr.get_token_part_two((token, frob))
        if token:
            self.config_store.set('flickr', 'token', token)
            return True
        self.flickr = None
        return False

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        self.upload_button.setEnabled(
            len(selection) > 0 and self.flickr and not self.uploader)
