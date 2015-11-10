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

import logging
import os
import six
import time

import flickrapi
import keyring

from .configstore import key_store
from .descriptive import MultiLineEdit, SingleLineEdit
from .pyqt import Busy, QtCore, QtWidgets
from .uploader import PhotiniUploader

logger = logging.getLogger(__name__)

flickr_version = 'flickrapi {}'.format(flickrapi.__version__)

class FlickrSession(object):
    def __init__(self):
        self.session = None

    def authorise(self, auth_dialog=None):
        token = keyring.get_password('photini', 'flickr')
        if token and self.session:
            return True
        logger.info('using %s', keyring.get_keyring().__module__)
        if token:
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
            if not auth_dialog:
                self.session = None
                return False
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

    def do_upload(self, fileobj, image_type, image, params):
        # collect metadata
        kwargs = dict(params[0])
        title = image.metadata.title
        if title:
            kwargs['title'] = title.value
        description = image.metadata.description
        if description:
            kwargs['description'] = description.value
        keywords = image.metadata.keywords
        if keywords:
            kwargs['tags'] = ' '.join(['"' + x + '"' for x in keywords.value])
        # upload photo
        try:
            rsp = self.session.upload(image.path, fileobj=fileobj, **kwargs)
        except Exception as ex:
            return str(ex)
        status = rsp.attrib['stat']
        if status != 'ok':
            return status
        photo_id = rsp.find('photoid').text
        # set date granularity
        date_taken = image.metadata.date_taken
        if date_taken and date_taken.precision <= 2:
            granularity = 8 - (date_taken.precision * 2)
            for attempt in range(3):
                try:
                    rsp = self.session.photos_setDates(
                        photo_id=photo_id,
                        date_taken_granularity=granularity)
                    status = rsp.attrib['stat']
                    if status == 'ok':
                        break
                except flickrapi.FlickrError as ex:
                    status = str(ex)
            else:
                return status
        # add to sets
        for p_set in params[1]:
            if p_set['id']:
                self.photosets_addPhoto(photo_id, p_set['id'])
            else:
                p_set['id'] = self.photosets_create(
                    p_set['title'], p_set['description'], photo_id)
        return ''


class FlickrUploadConfig(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(FlickrUploadConfig, self).__init__(parent)
        self.service_name = self.tr('Flickr')
        self.convert = {
            'types'   : ('gif', 'jpeg', 'png'),
            'msg'     : self.tr(
                'File "{0}" is of type "{1}", which Flickr may not' +
                ' handle correctly. Would you like to convert it to JPEG?'),
            'buttons' : QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            }
        self.setLayout(QtWidgets.QGridLayout())
        # privacy settings
        self.privacy = {}
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
        self.hidden = QtWidgets.QCheckBox(self.tr('Hidden from search'))
        privacy_group.layout().addWidget(self.hidden)
        privacy_group.layout().addStretch(1)
        self.layout().addWidget(privacy_group, 0, 0, 2, 1)
        # content type
        self.content_type = {}
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
        self.layout().addWidget(content_group, 0, 1)
        # create new set
        new_set_button = QtWidgets.QPushButton(self.tr('New set'))
        new_set_button.clicked.connect(self.new_set)
        self.layout().addWidget(new_set_button, 1, 1)
        # list of sets widget
        sets_group = QtWidgets.QGroupBox(self.tr('Add to sets'))
        sets_group.setLayout(QtWidgets.QVBoxLayout())
        self.scrollarea = QtWidgets.QScrollArea()
        self.scrollarea.setFrameStyle(QtWidgets.QFrame.NoFrame)
        self.scrollarea.setStyleSheet(
            "QScrollArea { background-color: transparent }")
        sets_group.layout().addWidget(self.scrollarea)
        self.layout().addWidget(sets_group, 0, 2, 2, 1)

    def set_session(self, session):
        self.session = session

    @QtCore.pyqtSlot(bool)
    def enable_ff(self, value):
        self.privacy['friends'].setEnabled(self.privacy['private'].isChecked())
        self.privacy['family'].setEnabled(self.privacy['private'].isChecked())

    @QtCore.pyqtSlot()
    def new_set(self):
        dialog = QtWidgets.QDialog()
        dialog.setWindowTitle(self.tr('Create new Flickr set'))
        dialog.setLayout(QtWidgets.QFormLayout())
        title = SingleLineEdit(spell_check=True)
        dialog.layout().addRow(self.tr('Title'), title)
        description = MultiLineEdit(spell_check=True)
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
        title = title.toPlainText()
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

    def clear_sets(self):
        self.photosets = []
        self.scrollarea.setWidget(QtWidgets.QWidget())

    def load_sets(self):
        with Busy():
            self.photosets = self.session.get_photosets()
        sets_widget = QtWidgets.QWidget()
        sets_widget.setLayout(QtWidgets.QVBoxLayout())
        for item in self.photosets:
            item['widget'] = QtWidgets.QCheckBox(item['title'].replace('&', '&&'))
            sets_widget.layout().addWidget(item['widget'])
        self.scrollarea.setWidget(sets_widget)
        sets_widget.setAutoFillBackground(False)

    def get_upload_params(self):
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
        return fixed_params, add_to_sets

    def upload_started(self):
        pass

    def upload_finished(self):
        pass


def FlickrUploader(config_store, image_list, parent=None):
    config_store.remove_section('flickr')
    return PhotiniUploader(
        FlickrUploadConfig(), FlickrSession, image_list, parent)
