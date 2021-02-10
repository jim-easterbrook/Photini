##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2019-21  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import urllib

import requests
from requests_oauthlib import OAuth2Session

from photini.configstore import key_store
from photini.pyqt import catch_all, QtCore, QtSignal, QtSlot, QtWidgets
from photini.uploader import PhotiniUploader, UploaderSession

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate


class GooglePhotosSession(UploaderSession):
    name       = 'googlephotos'
    oauth_url  = 'https://www.googleapis.com/oauth2/'
    photos_url = 'https://photoslibrary.googleapis.com/'
    scope      = ('profile', 'https://www.googleapis.com/auth/photoslibrary')

    def __init__(self, *arg, **kwds):
        super(GooglePhotosSession, self).__init__(*arg, **kwds)
        self.api = None

    def open_connection(self, token=None):
        self.cached_data = {}
        refresh_token = self.get_password()
        if not refresh_token:
            return False
        if not token:
            # create expired token
            token = {
                'access_token' : 'xxx',
                'refresh_token': refresh_token,
                'expires_in'   : -30,
                }
        client_id = key_store.get('googlephotos', 'client_id')
        client_secret = key_store.get('googlephotos', 'client_secret')
        auto_refresh_kwargs = {
            'client_id'    : client_id,
            'client_secret': client_secret,
            }
        token_url = self.oauth_url + 'v4/token'
        self.api = OAuth2Session(
            client_id=client_id, token=token, token_updater=self.save_token,
            auto_refresh_kwargs=auto_refresh_kwargs,
            auto_refresh_url=token_url)
        if token['expires_in'] < 0:
            # refresh token
            self.api.refresh_token(token_url, **auto_refresh_kwargs)
        self.connection_changed.emit(self.api.authorized)
        return self.api.authorized

    def close_connection(self):
        self.connection_changed.emit(False)
        if self.api:
            self.api.close()
            self.api = None

    def check_response(self, rsp, decode=True):
        if rsp.status_code != 200:
            logger.error('HTTP error %d', rsp.status_code)
            return (None, {})[decode]
        if decode:
            return rsp.json()
        return rsp

    def get_auth_url(self, redirect_uri):
        code_verifier = ''
        while len(code_verifier) < 43:
            code_verifier += OAuth2Session().new_state()
        self.auth_params = {
            'client_id'    : key_store.get('googlephotos', 'client_id'),
            'client_secret': key_store.get('googlephotos', 'client_secret'),
            'code_verifier': code_verifier,
            'redirect_uri' : redirect_uri,
            }
        url = 'https://accounts.google.com/o/oauth2/v2/auth'
        url += '?client_id=' + self.auth_params['client_id']
        url += '&redirect_uri=' + self.auth_params['redirect_uri']
        url += '&response_type=code'
        url += '&scope=' + urllib.parse.quote(' '.join(self.scope))
        url += '&code_challenge=' + self.auth_params['code_verifier']
        return url

    def get_access_token(self, result):
        if not 'code' in result:
            logger.info('No authorisaton code received')
            return
        data = {
            'code'      : result['code'][0],
            'grant_type': 'authorization_code',
            }
        data.update(self.auth_params)
        rsp = self.check_response(
            requests.post(self.oauth_url + 'v4/token', data=data, timeout=5))
        if 'access_token' not in rsp:
            logger.info('No access token received')
            return
        self.save_token(rsp)
        self.open_connection(token=rsp)

    def save_token(self, token):
        self.set_password(token['refresh_token'])

    def get_user(self):
        if 'user' in self.cached_data:
            return self.cached_data['user']
        rsp = self.check_response(
            self.api.get(self.oauth_url + 'v2/userinfo', timeout=5))
        name, picture = None, None
        if 'name' in rsp:
            name = rsp['name']
        if 'picture' in rsp:
            rsp = self.check_response(
                requests.get(rsp['picture']), decode=False)
            if rsp:
                picture = rsp.content
        self.cached_data['user'] = name, picture
        return self.cached_data['user']

    def get_albums(self):
        params = {}
        while True:
            rsp = self.check_response(self.api.get(
                self.photos_url + 'v1/albums', params=params, timeout=5))
            if 'albums' not in rsp:
                break
            for album in rsp['albums']:
                if 'id' in album:
                    safe_album = {'title': '', 'isWriteable': False}
                    safe_album.update(album)
                    yield safe_album
                else:
                    logger.info('Malformed album', album)
            if 'nextPageToken' not in rsp:
                break
            params['pageToken'] = rsp['nextPageToken']

    def new_album(self, title):
        body = {'album': {'title': title}}
        return self.check_response(self.api.post(
            self.photos_url + 'v1/albums', json=body, timeout=5))

    def do_upload(self, fileobj, image_type, image, params):
        # see https://developers.google.com/photos/library/guides/upload-media
        # 1/ initiate a resumable upload session (to do file in chunks)
        headers = {
            'X-Goog-Upload-Command'     : 'start',
            'X-Goog-Upload-Content-Type': image_type,
            'X-Goog-Upload-File-Name'   : os.path.basename(image.path),
            'X-Goog-Upload-Protocol'    : 'resumable',
            'X-Goog-Upload-Raw-Size'    : str(fileobj.len),
            }
        rsp = self.api.post(self.photos_url + 'v1/uploads', headers=headers)
        rsp = self.check_response(rsp, decode=False)
        if not rsp:
            return 'upload failed'
        upload_url = rsp.headers['X-Goog-Upload-URL']
        chunk_size = int(rsp.headers['X-Goog-Upload-Chunk-Granularity'])
        # 2/ upload data in chunks, size set by google
        headers = {'X-Goog-Upload-Command': 'upload'}
        offset = 0
        while offset < fileobj.len:
            chunk = fileobj.read(chunk_size)
            headers['X-Goog-Upload-Offset'] = str(offset)
            offset += len(chunk)
            if offset >= fileobj.len:
                headers['X-Goog-Upload-Command'] = 'upload, finalize'
            rsp = self.api.post(upload_url, headers=headers, data=chunk)
            rsp = self.check_response(rsp, decode=False)
            if not rsp:
                break
            if rsp.text:
                upload_token = rsp.text
        fileobj._callback(100)
        if not upload_token:
            return 'no upload token received'
        # 3/ convert uploaded bytes to a media item
        body = {'newMediaItems': [{
            'description'    : params['description'],
            'simpleMediaItem': {'uploadToken': upload_token},
            }]}
        if params['albums']:
            body['albumId'] = params['albums'][0]
        rsp = self.check_response(self.api.post(
            self.photos_url + 'v1/mediaItems:batchCreate',
            json=body))
        if 'newMediaItemResults' not in rsp:
            return 'failed to create media item'
        rsp = rsp['newMediaItemResults'][0]
        if 'status' in rsp:
            if rsp['status']['message'] != 'Success':
                return str(rsp['status'])
        media_id = rsp['mediaItem']['id']
        # 4/ add media item to more albums
        if len(params['albums']) > 1:
            body = {'mediaItemIds': [media_id]}
            for album_id in params['albums'][1:]:
                url = (self.photos_url + 'v1/albums/' +
                       album_id + ':batchAddMediaItems')
                rsp = self.check_response(self.api.post(url, json=body))
        return ''


class GoogleUploadConfig(QtWidgets.QWidget):
    new_set = QtSignal()

    def __init__(self, *arg, **kw):
        super(GoogleUploadConfig, self).__init__(*arg, **kw)
        self.setLayout(QtWidgets.QGridLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        # create new set
        new_set_button = QtWidgets.QPushButton(
            translate('GooglePhotosTab', 'New album'))
        new_set_button.clicked.connect(self.new_set)
        self.layout().addWidget(new_set_button, 2, 1)
        # list of sets widget
        sets_group = QtWidgets.QGroupBox(
            translate('GooglePhotosTab', 'Add to albums'))
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
        self.layout().addWidget(sets_group, 0, 2, 3, 1)
        self.layout().setColumnStretch(2, 1)

    def clear_sets(self):
        for child in self.sets_widget.children():
            if child.isWidgetType():
                self.sets_widget.layout().removeWidget(child)
                child.setParent(None)

    def checked_albums(self):
        result = []
        for child in self.sets_widget.children():
            if child.isWidgetType() and child.isChecked():
                result.append(child.property('id'))
        return result

    def add_album(self, album, index=-1):
        widget = QtWidgets.QCheckBox(album['title'].replace('&', '&&'))
        widget.setProperty('id', album['id'])
        widget.setEnabled(album['isWriteable'])
        if index >= 0:
            self.sets_widget.layout().insertWidget(index, widget)
        else:
            self.sets_widget.layout().addWidget(widget)
        return widget


class TabWidget(PhotiniUploader):
    session_factory = GooglePhotosSession

    @staticmethod
    def tab_name():
        return translate('GooglePhotosTab', 'Google &Photos upload')

    def __init__(self, *arg, **kw):
        self.service_name = translate('GooglePhotosTab', 'Google Photos')
        self.upload_config = GoogleUploadConfig()
        super(TabWidget, self).__init__(self.upload_config, *arg, **kw)
        self.upload_config.new_set.connect(self.new_set)
        self.image_types = {
            'accepted': ('image/gif', 'image/jpeg', 'image/png',
                         'video/mp4', 'video/quicktime', 'video/riff'),
            'rejected': ('image/x-canon-cr2',),
            }

    def get_conversion_function(self, image, params):
        convert = super(
            TabWidget, self).get_conversion_function(image, params)
        if convert == 'omit':
            return convert
        max_size = 25 * 1024 * 1024
        size = os.stat(image.path).st_size
        if size < max_size:
            return convert
        dialog = QtWidgets.QMessageBox(parent=self)
        dialog.setWindowTitle(
            translate('GooglePhotosTab', 'Photini: large file'))
        dialog.setText(
            translate('GooglePhotosTab', '<h3>Large file.</h3>'))
        dialog.setInformativeText(
            translate('GooglePhotosTab',
                      'File "{0}" is over 25MB. Remember that Photini '
                      'uploads count towards storage in your Google Account. '
                      'Upload it anyway?').format(os.path.basename(image.path)))
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        dialog.setStandardButtons(
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Ignore)
        dialog.exec_()
        return 'omit'

    def show_album_list(self, albums):
        self.upload_config.clear_sets()
        for album in albums:
            self.upload_config.add_album(album)

    def get_upload_params(self, image):
        title = image.metadata.title
        description = image.metadata.description
        if title and description:
            description = title + '\n\n' + description
        elif title:
            description = title
        elif not description:
            description = image.path
        params = {
            'description': description,
            'albums'     : self.upload_config.checked_albums(),
            }
        return params

    @QtSlot()
    @catch_all
    def new_set(self):
        title, OK = QtWidgets.QInputDialog.getText(
            self, translate('GooglePhotosTab', 'Album title'),
            translate('GooglePhotosTab', 'Please enter a title for the album'))
        if not OK or not title:
            return
        album = self.session.new_album(title)
        if not album:
            return
        widget = self.upload_config.add_album(album, index=0)
        widget.setChecked(True)
