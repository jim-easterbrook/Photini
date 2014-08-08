# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-14  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import logging
import os
import time
import webbrowser

import flickrapi
from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import Qt

from .utils import Busy

api2 = flickrapi.__version__ >= '2.0'

class FileWithCallback(object):
    def __init__(self, path, callback):
        self.file = open(path, 'rb')
        self.callback = callback
        # the following attributes and methods are used by
        # requests_tools.MultipartEncoder
        self.len = os.path.getsize(path)
        self.fileno = self.file.fileno
        self.tell = self.file.tell

    def read(self, size):
        if self.callback:
            self.callback(self.tell() * 100 // self.len)
        return self.file.read(size)

class UploadThread(QtCore.QThread):
    def __init__(self, flickr, upload_list, photosets, new_photosets):
        QtCore.QThread.__init__(self)
        self.flickr = flickr
        self.upload_list = upload_list
        self.photosets = photosets
        self.new_photosets = new_photosets

    reload_sets = QtCore.pyqtSignal()
    def run(self):
        logger = logging.getLogger(self.__class__.__name__)
        self.file_count = 0
        for params in self.upload_list:
            if api2:
                params['fileobj'] = FileWithCallback(params['filename'], self.callback)
            else:
                params['callback'] = self.callback
            rsp = self.flickr.upload(**params)
            if rsp.attrib['stat'] == 'ok':
                photo_id = rsp.find('photoid').text
                for photoset_id in self.photosets:
                    self.flickr.photosets_addPhoto(
                        photo_id=photo_id, photoset_id=photoset_id)
                if self.new_photosets:
                    for title, description in self.new_photosets:
                        rsp2 = self.flickr.photosets_create(
                            title=title, description=description,
                            primary_photo_id=photo_id)
                        if rsp2.attrib['stat'] == 'ok':
                            self.photosets.append(
                                rsp2.find('photoset').attrib['id'])
                    self.new_photosets = []
                    self.reload_sets.emit()
            else:
                logger.error(
                    'Upload %s failed: %s',
                    os.path.basename(params['filename']), rsp.attrib['stat'])
            self.file_count += 1

    progress_report = QtCore.pyqtSignal(float, float)
    def callback(self, progress, done=None):
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
        self.new_sets = []
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
        # hidden
        self.hidden = QtGui.QCheckBox('Hidden from search')
        privacy_group.layout().addWidget(self.hidden)
        privacy_group.layout().addStretch(1)
        self.layout().addWidget(privacy_group, 0, 0, 3, 2)
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
        self.layout().addWidget(content_group, 0, 2, 2, 1)
        # create new set
        new_set_button = QtGui.QPushButton('New set')
        new_set_button.clicked.connect(self.new_set)
        self.layout().addWidget(new_set_button, 2, 2)
        # list of sets widget
        sets_group = QtGui.QGroupBox('Add to sets')
        sets_group.setLayout(QtGui.QVBoxLayout())
        self.scrollarea = QtGui.QScrollArea()
        self.scrollarea.setFrameStyle(QtGui.QFrame.NoFrame)
        sets_group.layout().addWidget(self.scrollarea)
        self.layout().addWidget(sets_group, 0, 3, 3, 1)
        # 'go' button
        self.upload_button = QtGui.QPushButton('Upload\nnow')
        self.upload_button.setEnabled(False)
        self.upload_button.clicked.connect(self.upload)
        self.layout().addWidget(self.upload_button, 2, 4)
        # progress bars
        self.layout().addWidget(QtGui.QLabel('Progress'), 3, 0)
        self.total_progress = QtGui.QProgressBar()
        self.total_progress.sizePolicy().setHorizontalPolicy(
            QtGui.QSizePolicy.Expanding)
        self.layout().addWidget(self.total_progress, 3, 1, 1, 4)
        # adjust spacing
        self.layout().setColumnStretch(1, 1)
        self.layout().setColumnStretch(3, 100)
        self.layout().setRowStretch(1, 1)

    def refresh(self):
        if self.flickr:
            return
        self.get_photosets()

    @QtCore.pyqtSlot()
    def get_photosets(self):
        if not self.authorise():
            return
        with Busy():
            self.photosets = []
            sets = self.flickr.photosets_getList()
        for item in sets.find('photosets').findall('photoset'):
            self.photosets.append({
                'id'    : item.attrib['id'],
                'title' : item.find('title').text,
                })
        sets_widget = QtGui.QWidget()
        self.sets = QtGui.QVBoxLayout()
        sets_widget.setLayout(self.sets)
        for item in self.photosets:
            self.sets.addWidget(
                QtGui.QCheckBox(item['title'].replace('&', '&&')))
        self.scrollarea.setWidget(sets_widget)
        sets_widget.setAutoFillBackground(False)

    @QtCore.pyqtSlot(bool)
    def enable_ff(self, value):
        self.privacy['friends'].setEnabled(self.privacy['private'].isChecked())
        self.privacy['family'].setEnabled(self.privacy['private'].isChecked())

    @QtCore.pyqtSlot()
    def new_set(self):
        dialog = QtGui.QDialog()
        dialog.setWindowTitle('Create new Flickr set')
        dialog.setLayout(QtGui.QFormLayout())
        title = QtGui.QLineEdit()
        dialog.layout().addRow('Title', title)
        description = QtGui.QPlainTextEdit()
        dialog.layout().addRow('Description', description)
        dialog.layout().addRow(QtGui.QLabel(
            'Set will be created when photos are uploaded'))
        buttons = QtGui.QHBoxLayout()
        buttons.addStretch(3)
        cancel = QtGui.QPushButton('cancel')
        cancel.setAutoDefault(False)
        cancel.clicked.connect(dialog.reject)
        buttons.addWidget(cancel)
        OK = QtGui.QPushButton('OK')
        OK.setAutoDefault(False)
        OK.clicked.connect(dialog.accept)
        buttons.addWidget(OK)
        buttons.setStretchFactor(cancel, 1)
        buttons.setStretchFactor(OK, 1)
        dialog.layout().addRow(buttons)
        if dialog.exec_() != QtGui.QDialog.Accepted:
            return
        title = unicode(title.text())
        if not title:
            return
        description = unicode(description.toPlainText())
        self.new_sets.append((title, description))
        check_box = QtGui.QCheckBox(title.replace('&', '&&'))
        check_box.setChecked(True)
        check_box.setEnabled(False)
        self.sets.insertWidget(0, check_box)

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
            if self.sets.itemAt(idx + len(self.new_sets)).widget().isChecked():
                photosets.append(self.photosets[idx]['id'])
        new_photosets = self.new_sets
        self.new_sets = []
        # make list of items to upload
        upload_list = list()
        for image in self.image_list.get_selected_images():
            title = image.metadata.get_item('title').as_str()
            if not title:
                title = os.path.basename(image.path)
            description = image.metadata.get_item('description').as_str()
            tags = image.metadata.get_item('keywords')
            if tags.empty():
                tags = ''
            else:
                tags = ' '.join(map(lambda x: '"%s"' % x, tags.value))
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
            self.uploader = UploadThread(
                self.flickr, upload_list, photosets, new_photosets)
            self.uploader.progress_report.connect(self.upload_progress)
            self.uploader.finished.connect(self.upload_done)
            self.uploader.reload_sets.connect(self.get_photosets)
            self.uploader.start()
            # we've passed the flickr API object to a new thread, so
            # create a new one for safety
            self.flickr = None
            self.authorise()

    @QtCore.pyqtSlot(float, float)
    def upload_progress(self, progress, total_progress):
        self.total_progress.setValue(total_progress)

    @QtCore.pyqtSlot()
    def upload_done(self):
        self.upload_button.setEnabled(True)
        self.total_progress.setValue(0)
        self.uploader = None

    def authorise(self):
        if self.flickr:
            return True
        api_key = 'b6263c4693e3406aadcfaebe005280a5'
        api_secret = '1e0d912f586d0ed1'
        if api2:
            api_key = unicode(api_key)
            api_secret = unicode(api_secret)
            token        = self.config_store.get('flickr', 'token', '')
            token_secret = self.config_store.get('flickr', 'token_secret', '')
            token = flickrapi.auth.FlickrAccessToken(
                token, token_secret, 'write')
        else:
            token = self.config_store.get('flickr', 'token', '')
        self.flickr = flickrapi.FlickrAPI(
            api_key, api_secret, token=token, store_token=False)
        if api2:
            if self.flickr.token_valid(perms='write'):
                return True
        else:
            token, frob = self.flickr.get_token_part_one(perms='write')
            if token:
                token = self.flickr.get_token_part_two((token, frob))
            if token:
                return True
        if api2:
            self.flickr.get_request_token(oauth_callback='oob')
            auth_url = self.flickr.auth_url(perms='write')
            if webbrowser.open(auth_url, new=2, autoraise=0):
                info_text = 'use your web browser'
            else:
                info_text = 'open "%s" in a web browser' % auth_url
            auth_code, OK = QtGui.QInputDialog.getText(
                self,
                'Photini: authorise Flickr',
                'Please %s to grant access to Photini,\n' % (info_text) +
                'then enter the verification code:')
            if not OK:
                self.flickr = None
                return False
            try:
                self.flickr.get_access_token(unicode(auth_code))
            except Exception, ex:
                self.flickr = None
                return False
        else:
            button = QtGui.QMessageBox.question(
                self,
                'Photini: authorise Flickr',
                'Please use your web browser to grant\n' +
                'access to Photini, then click OK.')
            try:
                token = self.flickr.get_token_part_two((token, frob))
            except flickrapi.exceptions.FlickrError:
                self.flickr = None
                return False
        if api2:
            token = self.flickr.token_cache.token
            self.config_store.set('flickr', 'token',        token.token)
            self.config_store.set('flickr', 'token_secret', token.token_secret)
        else:
            self.config_store.set('flickr', 'token', token)
        return True

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        self.upload_button.setEnabled(
            len(selection) > 0 and self.flickr and not self.uploader)
