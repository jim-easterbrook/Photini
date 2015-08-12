# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-15  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import imghdr
import logging
import os
import six
import time
import webbrowser

import flickrapi
import keyring

from .configstore import key_store
from .pyqt import Qt, QtCore, QtWidgets
from .utils import Busy, FileObjWithCallback

logger = logging.getLogger(__name__)

class FlickrSession(object):
    def __init__(self):
        self.session = None

    def valid(self):
        token = keyring.get_password('photini', 'flickr')
        if token and self.session:
            return True
        self.session = None
        return False

    def authorise(self, auth_dialog):
        token = keyring.get_password('photini', 'flickr')
        if token:
            if self.session:
                return True
            token, token_secret = token.split('&')
        else:
            token, token_secret = '', ''
        api_key    = key_store.get('flickr', 'api_key')
        api_secret = key_store.get('flickr', 'api_secret')
        with Busy():
            token = flickrapi.auth.FlickrAccessToken(token, token_secret, 'write')
            self.session = flickrapi.FlickrAPI(
                api_key, api_secret, token=token, store_token=False)
            if self.session.token_valid(perms='write'):
                return True
            self.session.get_request_token(oauth_callback='oob')
            auth_url = self.session.auth_url(perms='write')
        auth_code = auth_dialog(auth_url)
        if not auth_code:
            self.session = None
            return False
        with Busy():
            try:
                self.session.get_access_token(auth_code)
            except flickrapi.FlickrError as ex:
                logger.error(str(ex))
                self.session = None
                return False
        token = self.session.token_cache.token
        keyring.set_password(
            'photini', 'flickr', token.token + '&' + token.token_secret)
        return True

    def get_photosets(self):
        result = []
        sets = self.session.photosets_getList()
        for item in sets.find('photosets').findall('photoset'):
            result.append({
                'id'    : item.attrib['id'],
                'title' : item.find('title').text,
                })
        return result

    def photosets_create(self, title, description, primary_photo_id):
        rsp = self.session.photosets_create(
            title=title, description=description,
            primary_photo_id=primary_photo_id)
        if rsp.attrib['stat'] == 'ok':
            return rsp.find('photoset').attrib['id']
        logger.error('Create photoset %s failed: %s', title, rsp.attrib['stat'])
        return None

    def photosets_addPhoto(self, photo_id, photoset_id):
        self.session.photosets_addPhoto(
            photo_id=photo_id, photoset_id=photoset_id)

    def upload(self, filename, fileobj, **params):
        rsp = self.session.upload(filename, fileobj=fileobj, **params)
        if rsp.attrib['stat'] == 'ok':
            return rsp.find('photoid').text
        logger.error(
            'Upload %s failed: %s',
            os.path.basename(filename), rsp.attrib['stat'])
        return None


class UploadThread(QtCore.QThread):
    def __init__(self, flickr, fixed_params, upload_list, add_to_sets):
        QtCore.QThread.__init__(self)
        self.flickr = flickr
        self.fixed_params = fixed_params
        self.upload_list = upload_list
        self.add_to_sets = add_to_sets

    def run(self):
        logger = logging.getLogger(self.__class__.__name__)
        self.file_count = 0
        for image, convert in self.upload_list:
            params = dict(self.fixed_params)
            title = image.metadata.title
            if title:
                params['title'] = title
            description = image.metadata.description
            if description:
                params['description'] = description
            keywords = image.metadata.keywords
            if keywords:
                params['tags'] = ' '.join(['"' + x + '"' for x in keywords])
            if convert:
                path = image.as_jpeg()
            else:
                path = image.path
            with open(path, 'rb') as f:
                fileobj = FileObjWithCallback(f, self.callback)
                photo_id = self.flickr.upload(
                    image.path, fileobj=fileobj, **params)
            if convert:
                os.unlink(path)
            if photo_id:
                for p_set in self.add_to_sets:
                    if p_set['id']:
                        self.flickr.photosets_addPhoto(photo_id, p_set['id'])
                    else:
                        p_set['id'] = self.flickr.photosets_create(
                            p_set['title'], p_set['description'], photo_id)
            self.file_count += 1

    progress_report = QtCore.pyqtSignal(float, float)
    def callback(self, progress, done=None):
        total_progress = (
            (self.file_count * 100) + progress) / len(self.upload_list)
        self.progress_report.emit(progress, total_progress)

class FlickrUploader(QtWidgets.QWidget):
    def __init__(self, config_store, image_list, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        config_store.remove_section('flickr')
        self.image_list = image_list
        self.setLayout(QtWidgets.QGridLayout())
        self.flickr = FlickrSession()
        self.photosets = []
        self.uploader = None
        # privacy settings
        self.privacy = dict()
        privacy_group = QtWidgets.QGroupBox(self.tr('Who can see the photos?'))
        privacy_group.setLayout(QtWidgets.QVBoxLayout())
        self.privacy['private'] = QtWidgets.QRadioButton(self.tr('Only you'))
        privacy_group.layout().addWidget(self.privacy['private'])
        ff_group = QtWidgets.QGroupBox()
        ff_group.setFlat(True)
        ff_group.setLayout(QtWidgets.QVBoxLayout())
        self.privacy['friends'] = QtWidgets.QCheckBox(self.tr('Your friends'))
        ff_group.layout().addWidget(self.privacy['friends'])
        self.privacy['family'] = QtWidgets.QCheckBox(self.tr('Your family'))
        ff_group.layout().addWidget(self.privacy['family'])
        privacy_group.layout().addWidget(ff_group)
        self.privacy['public'] = QtWidgets.QRadioButton(self.tr('Anyone'))
        self.privacy['public'].toggled.connect(self.enable_ff)
        self.privacy['public'].setChecked(True)
        privacy_group.layout().addWidget(self.privacy['public'])
        # hidden
        self.hidden = QtWidgets.QCheckBox(self.tr('Hidden from search'))
        privacy_group.layout().addWidget(self.hidden)
        privacy_group.layout().addStretch(1)
        self.layout().addWidget(privacy_group, 0, 0, 3, 2)
        # content type
        self.content_type = dict()
        content_group = QtWidgets.QGroupBox(self.tr('Content type'))
        content_group.setLayout(QtWidgets.QVBoxLayout())
        self.content_type['photo'] = QtWidgets.QRadioButton(self.tr('Photo'))
        self.content_type['photo'].setChecked(True)
        content_group.layout().addWidget(self.content_type['photo'])
        self.content_type['screenshot'] = QtWidgets.QRadioButton(self.tr('Screenshot'))
        content_group.layout().addWidget(self.content_type['screenshot'])
        self.content_type['other'] = QtWidgets.QRadioButton(self.tr('Art/Illustration'))
        content_group.layout().addWidget(self.content_type['other'])
        content_group.layout().addStretch(1)
        self.layout().addWidget(content_group, 0, 2, 2, 1)
        # create new set
        new_set_button = QtWidgets.QPushButton(self.tr('New set'))
        new_set_button.clicked.connect(self.new_set)
        self.layout().addWidget(new_set_button, 2, 2)
        # list of sets widget
        sets_group = QtWidgets.QGroupBox(self.tr('Add to sets'))
        sets_group.setLayout(QtWidgets.QVBoxLayout())
        self.scrollarea = QtWidgets.QScrollArea()
        self.scrollarea.setFrameStyle(QtWidgets.QFrame.NoFrame)
        self.scrollarea.setStyleSheet(
            "QScrollArea { background-color: transparent }")
        sets_group.layout().addWidget(self.scrollarea)
        self.layout().addWidget(sets_group, 0, 3, 3, 1)
        # 'go' button
        self.upload_button = QtWidgets.QPushButton(self.tr('Upload\nnow'))
        self.upload_button.setEnabled(False)
        self.upload_button.clicked.connect(self.upload)
        self.layout().addWidget(self.upload_button, 2, 4)
        # progress bars
        self.layout().addWidget(QtWidgets.QLabel(self.tr('Progress')), 3, 0)
        self.total_progress = QtWidgets.QProgressBar()
        self.total_progress.sizePolicy().setHorizontalPolicy(
            QtWidgets.QSizePolicy.Expanding)
        self.layout().addWidget(self.total_progress, 3, 1, 1, 4)
        # adjust spacing
        self.layout().setColumnStretch(1, 1)
        self.layout().setColumnStretch(3, 100)
        self.layout().setRowStretch(1, 1)

    def refresh(self):
        if self.flickr.valid():
            return
        self.photosets = []
        self.scrollarea.setWidget(QtWidgets.QWidget())
        QtWidgets.QApplication.processEvents()
        if not self.flickr.authorise(self.auth_dialog):
            self.setEnabled(False)
            return
        with Busy():
            self.photosets = self.flickr.get_photosets()
        sets_widget = QtWidgets.QWidget()
        sets_widget.setLayout(QtWidgets.QVBoxLayout())
        for item in self.photosets:
            item['widget'] = QtWidgets.QCheckBox(item['title'].replace('&', '&&'))
            sets_widget.layout().addWidget(item['widget'])
        self.scrollarea.setWidget(sets_widget)
        sets_widget.setAutoFillBackground(False)

    def do_not_close(self):
        if not self.uploader or self.uploader.isFinished():
            return False
        dialog = QtWidgets.QMessageBox()
        dialog.setWindowTitle(self.tr('Photini: upload in progress'))
        dialog.setText(self.tr('<h3>Upload to Flickr has not finished.</h3>'))
        dialog.setInformativeText(
            self.tr('Closing now will terminate the upload.'))
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        dialog.setStandardButtons(
            QtWidgets.QMessageBox.Close | QtWidgets.QMessageBox.Cancel)
        dialog.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        result = dialog.exec_()
        return result == QtWidgets.QMessageBox.Cancel

    @QtCore.pyqtSlot(bool)
    def enable_ff(self, value):
        self.privacy['friends'].setEnabled(self.privacy['private'].isChecked())
        self.privacy['family'].setEnabled(self.privacy['private'].isChecked())

    @QtCore.pyqtSlot()
    def new_set(self):
        dialog = QtWidgets.QDialog()
        dialog.setWindowTitle(self.tr('Create new Flickr set'))
        dialog.setLayout(QtWidgets.QFormLayout())
        title = QtWidgets.QLineEdit()
        dialog.layout().addRow(self.tr('Title'), title)
        description = QtWidgets.QPlainTextEdit()
        dialog.layout().addRow(self.tr('Description'), description)
        dialog.layout().addRow(QtWidgets.QLabel(
            self.tr('Set will be created when photos are uploaded')))
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addRow(button_box)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        title = title.text()
        if not title:
            return
        description = description.toPlainText()
        check_box = QtWidgets.QCheckBox(title.replace('&', '&&'))
        check_box.setChecked(True)
        self.scrollarea.widget().layout().insertWidget(0, check_box)
        self.photosets.insert(0, {
            'id'          : None,
            'title'       : title,
            'description' : description,
            'widget'      : check_box,
            })

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
        fixed_params = {
            'is_public'    : is_public,
            'is_friend'    : is_friend,
            'is_family'    : is_family,
            'content_type' : content_type,
            'hidden'       : hidden,
            }
        # make list of sets to add photos to
        add_to_sets = []
        for item in self.photosets:
            if item['widget'].isChecked():
                add_to_sets.append(item)
        # make list of items to upload
        upload_list = []
        for image in self.image_list.get_selected_images():
            image_type = imghdr.what(image.path)
            if image_type not in ('gif', 'jpeg', 'png'):
                dialog = QtWidgets.QMessageBox()
                dialog.setWindowTitle(self.tr('Photini: incompatible type'))
                dialog.setText(self.tr('<h3>Incompatible image type.</h3>'))
                dialog.setInformativeText(self.tr(
                    'File "{0}" is of type "{1}", which Flickr may not handle correctly. Would you like to convert it to JPEG?').format(
                        os.path.basename(image.path), image_type))
                dialog.setIcon(QtWidgets.QMessageBox.Warning)
                dialog.setStandardButtons(QtWidgets.QMessageBox.Yes |
                                          QtWidgets.QMessageBox.No)
                dialog.setDefaultButton(QtWidgets.QMessageBox.Yes)
                convert = dialog.exec_() == QtWidgets.QMessageBox.Yes
            else:
                convert = False
            upload_list.append((image, convert))
        # pass the list to a separate thread, so GUI can continue
        if self.flickr.authorise(self.auth_dialog):
            self.upload_button.setEnabled(False)
            self.uploader = UploadThread(
                self.flickr, fixed_params, upload_list, add_to_sets)
            self.uploader.progress_report.connect(self.upload_progress)
            self.uploader.finished.connect(self.upload_done)
            self.uploader.start()
            # we've passed the flickr API object to a new thread, so
            # create a new one for safety
            self.flickr = FlickrSession()
            self.flickr.authorise(self.auth_dialog)

    @QtCore.pyqtSlot(float, float)
    def upload_progress(self, progress, total_progress):
        self.total_progress.setValue(total_progress)

    @QtCore.pyqtSlot()
    def upload_done(self):
        self.upload_button.setEnabled(True)
        self.total_progress.setValue(0)
        self.uploader = None

    def auth_dialog(self, auth_url):
        if webbrowser.open(auth_url, new=2, autoraise=0):
            info_text = self.tr('use your web browser')
        else:
            info_text = self.tr('open "{0}" in a web browser').format(auth_url)
        auth_code, OK = QtWidgets.QInputDialog.getText(
            self,
            self.tr('Photini: authorise Flickr'),
            self.tr("""Please {0} to grant access to Photini,
then enter the verification code:""").format(info_text))
        if OK:
            return six.text_type(auth_code).strip()
        return None

    @QtCore.pyqtSlot(list)
    def new_selection(self, selection):
        self.upload_button.setEnabled(
            len(selection) > 0 and self.flickr.valid() and not self.uploader)
