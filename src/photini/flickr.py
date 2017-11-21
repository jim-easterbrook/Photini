# -*- coding: utf-8 -*-
##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-17  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import requests
import six
from six.moves.html_parser import HTMLParser
import time

import flickrapi

from photini.configstore import key_store
from photini.pyqt import (
    Busy, MultiLineEdit, Qt, QtCore, QtGui, QtWidgets, SingleLineEdit)
from photini.uploader import PhotiniUploader, UploaderSession

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate

flickr_version = 'flickrapi {}'.format(flickrapi.__version__)

class FlickrSession(UploaderSession):
    name = 'flickr'

    def permitted(self, level):
        stored_token = self.get_password()
        if not stored_token:
            self.api = None
            return False
        if not self.api:
            api_key    = key_store.get('flickr', 'api_key')
            api_secret = key_store.get('flickr', 'api_secret')
            token, token_secret = stored_token.split('&')
            token = flickrapi.auth.FlickrAccessToken(
                token, token_secret, 'write')
            self.api = flickrapi.FlickrAPI(
                api_key, api_secret, token=token, store_token=False)
        return self.api.token_valid(perms='write')

    def get_auth_url(self, level):
        api_key    = key_store.get('flickr', 'api_key')
        api_secret = key_store.get('flickr', 'api_secret')
        token = flickrapi.auth.FlickrAccessToken('', '', 'write')
        self.api = flickrapi.FlickrAPI(
            api_key, api_secret, token=token, store_token=False)
        self.api.get_request_token(oauth_callback='oob')
        return self.api.auth_url(perms='write')

    def get_access_token(self, auth_code, level):
        try:
            self.api.get_access_token(auth_code)
        except flickrapi.FlickrError as ex:
            logger.error(str(ex))
            self.api = None
            return False
        token = self.api.token_cache.token
        self.set_password(token.token + '&' + token.token_secret)
        self.api = None
        return self.permitted(level)

    def get_user(self):
        result = None, None
        rsp = self.api.auth.oauth.checkToken(format='parsed-json')
        if rsp['stat'] != 'ok':
            return result
        user = rsp['oauth']['user']
        result = user['fullname'], None
        rsp = self.api.people.getInfo(user_id=user['nsid'], format='parsed-json')
        if rsp['stat'] != 'ok':
            return result
        person = rsp['person']
        if person['iconserver'] != '0':
            icon_url = 'http://farm{}.staticflickr.com/{}/buddyicons/{}.jpg'.format(
                person['iconfarm'], person['iconserver'], person['nsid'])
        else:
            icon_url = 'https://www.flickr.com/images/buddyicon.gif'
        rsp = requests.get(icon_url)
        if rsp.status_code == 200:
            result = user['fullname'], rsp.content
        else:
            logger.error('HTTP error %d (%s)', rsp.status_code, icon_url)
        return result

    def do_upload(self, fileobj, image_type, image, params):
        # collect metadata
        kwargs = dict(params[0])
        title = image.metadata.title
        if title:
            kwargs['title'] = title
        description = image.metadata.description
        if description:
            kwargs['description'] = description
        keywords = image.metadata.keywords
        if keywords:
            kwargs['tags'] = ' '.join(['"' + x + '"' for x in keywords])
        # upload photo
        try:
            rsp = self.api.upload(image.path, fileobj=fileobj, **kwargs)
        except Exception as ex:
            return str(ex)
        status = rsp.attrib['stat']
        if status != 'ok':
            return status
        photo_id = rsp.find('photoid').text
        # set date and granularity
        date_taken = image.metadata.date_taken
        if date_taken:
            kwargs = {
                'photo_id'  : photo_id,
                'date_taken': date_taken.datetime.strftime('%Y-%m-%d %H:%M:%S'),
                }
            if date_taken.precision <= 2:
                kwargs['date_taken_granularity'] = 8 - (date_taken.precision * 2)
            for attempt in range(3):
                try:
                    rsp = self.api.photos_setDates(**kwargs)
                    status = rsp.attrib['stat']
                    if status == 'ok':
                        break
                except flickrapi.FlickrError as ex:
                    status = str(ex)
            else:
                return status
        # set location
        latlon = image.metadata.latlong
        if latlon:
            kwargs = {
                'photo_id': photo_id,
                'lat'     : '{:.6f}'.format(latlon.lat),
                'lon'     : '{:.6f}'.format(latlon.lon),
                }
            for attempt in range(3):
                try:
                    rsp = self.api.photos.geo.setLocation(**kwargs)
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
                # add to existing set
                try:
                    self.api.photosets_addPhoto(
                        photo_id=photo_id, photoset_id=p_set['id'])
                    continue
                except flickrapi.FlickrError as ex:
                    logger.error('Add to photoset "%s" failed: %s',
                                 p_set['title'], str(ex))
                    p_set['id'] = None
            # create new set
            try:
                rsp = self.api.photosets_create(
                    title=p_set['title'], description=p_set['description'],
                    primary_photo_id=photo_id)
            except flickrapi.FlickrError as ex:
                logger.error('Create photoset "%s" failed: %s',
                             p_set['title'], str(ex))
                continue
            if rsp.attrib['stat'] == 'ok':
                p_set['id'] = rsp.find('photoset').attrib['id']
            else:
                logger.error('Create photoset "%s" failed: %s',
                             p_set['title'], rsp.attrib['stat'])
        return ''

    # delegate all other attributes to api object
    def __getattr__(self, name):
        return getattr(self.api, name)


class FlickrUploadConfig(QtWidgets.QWidget):
    new_set = QtCore.pyqtSignal()

    def __init__(self, *arg, **kw):
        super(FlickrUploadConfig, self).__init__(*arg, **kw)
        self.setLayout(QtWidgets.QGridLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        # privacy settings
        self.privacy = {}
        privacy_group = QtWidgets.QGroupBox(self.tr('Who can see the photos?'))
        privacy_group.setLayout(QtWidgets.QVBoxLayout())
        self.privacy['private'] = QtWidgets.QRadioButton(self.tr('Only you'))
        privacy_group.layout().addWidget(self.privacy['private'])
        ff_group = QtWidgets.QGroupBox()
        ff_group.setFlat(True)
        ff_group.setLayout(QtWidgets.QVBoxLayout())
        ff_group.layout().setContentsMargins(10, 0, 0, 0)
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
        new_set_button = QtWidgets.QPushButton(self.tr('New album'))
        new_set_button.clicked.connect(self.new_set)
        self.layout().addWidget(new_set_button, 1, 1)
        # list of sets widget
        sets_group = QtWidgets.QGroupBox(self.tr('Add to albums'))
        sets_group.setLayout(QtWidgets.QVBoxLayout())
        scrollarea = QtWidgets.QScrollArea()
        scrollarea.setFrameStyle(QtWidgets.QFrame.NoFrame)
        scrollarea.setStyleSheet("QScrollArea { background-color: transparent }")
        self.sets_widget = QtWidgets.QWidget()
        self.sets_widget.setLayout(QtWidgets.QVBoxLayout())
        self.sets_widget.layout().setSpacing(0)
        self.sets_widget.layout().setSizeConstraint(
            QtWidgets.QLayout.SetMinAndMaxSize)
        scrollarea.setWidget(self.sets_widget)
        self.sets_widget.setAutoFillBackground(False)
        sets_group.layout().addWidget(scrollarea)
        self.layout().addWidget(sets_group, 0, 2, 2, 1)
        self.layout().setColumnStretch(2, 1)

    @QtCore.pyqtSlot(bool)
    def enable_ff(self, value):
        self.privacy['friends'].setEnabled(self.privacy['private'].isChecked())
        self.privacy['family'].setEnabled(self.privacy['private'].isChecked())

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
        return {
            'is_public'    : is_public,
            'is_friend'    : is_friend,
            'is_family'    : is_family,
            'content_type' : content_type,
            'hidden'       : hidden,
            }

    def clear_sets(self):
        for child in self.sets_widget.children():
            if child.isWidgetType():
                self.sets_widget.layout().removeWidget(child)
                child.setParent(None)

    def add_set(self, title, description, index=-1):
        widget = QtWidgets.QCheckBox(title.replace('&', '&&'))
        if description:
            h = HTMLParser()
            widget.setToolTip(h.unescape(description))
        if index >= 0:
            self.sets_widget.layout().insertWidget(index, widget)
        else:
            self.sets_widget.layout().addWidget(widget)
        return widget


class FlickrUploader(PhotiniUploader):
    session_factory = FlickrSession

    def __init__(self, *arg, **kw):
        self.upload_config = FlickrUploadConfig()
        super(FlickrUploader, self).__init__(self.upload_config, *arg, **kw)
        self.upload_config.new_set.connect(self.new_set)
        self.service_name = self.tr('Flickr')
        self.image_types = {
            'accepted': ('image/gif', 'image/jpeg', 'image/png',
                         'video/mp4', 'video/quicktime', 'video/riff'),
            'rejected': ('image/x-canon-cr2',),
            }

    def get_conversion_function(self, image):
        convert = super(FlickrUploader, self).get_conversion_function(image)
        if convert == 'omit':
            return convert
        max_size = 2 ** 30
        size = os.stat(image.path).st_size
        if size < max_size:
            return convert
        dialog = QtWidgets.QMessageBox(parent=self)
        dialog.setWindowTitle(
            translate('PhotiniUploader', 'Photini: too large'))
        dialog.setText(
            translate('PhotiniUploader', '<h3>File too large.</h3>'))
        dialog.setInformativeText(
            translate('PhotiniUploader',
                      'File "{0}" has {1} bytes and exceeds Flickr\'s limit' +
                      ' of {2} bytes.').format(
                          os.path.basename(image.path), size, max_size))
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        dialog.setStandardButtons(QtWidgets.QMessageBox.Ignore)
        dialog.exec_()
        return 'omit'

    def get_album_list(self):
        self.photosets = []
        self.upload_config.clear_sets()
        if self.connected:
            sets = self.session.photosets_getList()
            for item in sets.find('photosets').findall('photoset'):
                title = item.find('title').text
                description = item.find('description').text
                widget = self.upload_config.add_set(title, description)
                self.photosets.append({
                    'id'    : item.attrib['id'],
                    'title' : title,
                    'widget': widget,
                    })

    def get_upload_params(self):
        # get config params that apply to all photos
        fixed_params = self.upload_config.get_upload_params()
        # make list of sets to add photos to
        add_to_sets = []
        for item in self.photosets:
            if item['widget'].isChecked():
                add_to_sets.append(item)
        return fixed_params, add_to_sets

    def upload_finished(self):
        pass

    @QtCore.pyqtSlot()
    def new_set(self):
        dialog = QtWidgets.QDialog(parent=self)
        dialog.setWindowTitle(self.tr('Create new Flickr album'))
        dialog.setLayout(QtWidgets.QFormLayout())
        title = SingleLineEdit(spell_check=True)
        dialog.layout().addRow(self.tr('Title'), title)
        description = MultiLineEdit(spell_check=True)
        dialog.layout().addRow(self.tr('Description'), description)
        dialog.layout().addRow(QtWidgets.QLabel(
            self.tr('Album will be created when photos are uploaded')))
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
        widget = self.upload_config.add_set(title, description, index=0)
        widget.setChecked(True)
        self.photosets.insert(0, {
            'id'          : None,
            'title'       : title,
            'description' : description,
            'widget'      : widget,
            })
