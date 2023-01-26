##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2019-23  Jim Easterbrook  jim@jim-easterbrook.me.uk
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
import os
import urllib

import requests
from requests_oauthlib import OAuth2Session

from photini.pyqt import (
    catch_all, execute, QtCore, QtSlot, QtWidgets, width_for_text)
from photini.uploader import PhotiniUploader, UploaderSession, UploaderUser

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate

# Google Photos API: https://developers.google.com/photos/library/reference/rest

class GooglePhotosSession(UploaderSession):
    name       = 'googlephotos'
    oauth_url  = 'https://www.googleapis.com/oauth2/'
    photos_url = 'https://photoslibrary.googleapis.com/'

    def open_connection(self):
        if self.timer:
            self.timer.start()
        self.api = OAuth2Session(
            client_id=self.client_data['client_id'], token=self.user_data)
        if self.user_data['expires_in'] < 600:
            # refresh token
            self.user_data = self.api.refresh_token(
                self.oauth_url + 'v4/token', **self.client_data)

    def set_user(self, user_data):
        self.close_connection()
        self.user_data = user_data
        if not self.user_data:
            self.authorised = False
            return
        self.open_connection()
        self.authorised = self.api.authorized

    def api_call(self, url, post=False, **params):
        if self.timer:
            self.timer.start()
        if not self.api:
            self.open_connection()
        if post:
            return self.check_response(self.api.post(url, **params))
        return self.check_response(self.api.get(url, **params))

    @staticmethod
    def check_response(rsp, decode=True):
        if rsp.status_code != 200:
            logger.error('HTTP error %d', rsp.status_code)
            return (None, {})[decode]
        if decode:
            return rsp.json()
        return rsp

    def get_user(self):
        rsp = self.api_call(self.oauth_url + 'v2/userinfo', timeout=5)
        name, picture = None, None
        if 'name' in rsp:
            name = rsp['name']
        if 'picture' in rsp:
            rsp = self.check_response(
                requests.get(rsp['picture']), decode=False)
            if rsp:
                picture = rsp.content
        return name, picture

    def get_albums(self):
        params = {}
        while True:
            rsp = self.api_call(
                self.photos_url + 'v1/albums', params=params, timeout=5)
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
        return self.api_call(
            self.photos_url + 'v1/albums', json=body, timeout=5, post=True)

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
        self.upload_progress.emit({'busy': False})
        headers = {'X-Goog-Upload-Command': 'upload'}
        offset = 0
        while offset < fileobj.len:
            chunk = fileobj.read(chunk_size)
            headers['X-Goog-Upload-Offset'] = str(offset)
            offset += len(chunk)
            if offset >= fileobj.len:
                headers['X-Goog-Upload-Command'] = 'upload, finalize'
            rsp = self.api.post(upload_url, headers=headers, data=chunk)
            self.upload_progress.emit({'value': offset * 100 // fileobj.len})
            rsp = self.check_response(rsp, decode=False)
            if not rsp:
                break
            if rsp.text:
                upload_token = rsp.text
        self.upload_progress.emit({'busy': True})
        if not upload_token:
            return 'no upload token received'
        # 3/ convert uploaded bytes to a media item
        body = {'newMediaItems': [{
            'description'    : params['description'],
            'simpleMediaItem': {'uploadToken': upload_token},
            }]}
        if params['albums']:
            body['albumId'] = params['albums'][0]
        rsp = self.api_call(self.photos_url + 'v1/mediaItems:batchCreate',
                            json=body, post=True)
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
                rsp = self.api_call(url, json=body, post=True)
        return ''


class GooglePhotosUser(UploaderUser):
    name       = 'googlephotos'
    scope      = ('profile', 'https://www.googleapis.com/auth/photoslibrary')

    def __init__(self, *arg, **kw):
        super(GooglePhotosUser, self).__init__(*arg, **kw)
        stored_token = self.get_password()
        if stored_token:
            # create an expired token
            if '&' in stored_token:
                access_token, refresh_token = stored_token.split('&')
            else:
                access_token, refresh_token = 'xxx', stored_token
            self.user_data = {
                'access_token' : access_token,
                'refresh_token': refresh_token,
                'expires_in'   : -30,
                }
        self.session = self.new_session(parent=self)

    @staticmethod
    def service_name():
        return translate('GooglePhotosTab', 'Google Photos')

    def new_session(self, **kw):
        return GooglePhotosSession(
            user_data=self.user_data, client_data=self.client_data, **kw)

    def get_auth_url(self, redirect_uri):
        code_verifier = ''
        while len(code_verifier) < 43:
            code_verifier += OAuth2Session().new_state()
        self.auth_params = {
            'code_verifier': code_verifier,
            'redirect_uri' : redirect_uri,
            }
        self.auth_params.update(self.client_data)
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
        rsp = GooglePhotosSession.check_response(
            requests.post(GooglePhotosSession.oauth_url + 'v4/token',
                          data=data, timeout=5))
        if 'access_token' not in rsp:
            logger.info('No access token received')
            return
        self.user_data = rsp
        self.set_password(self.user_data['access_token'] + '&' +
                          self.user_data['refresh_token'])
        self.session.set_user(self.user_data)
        self.connection_changed.emit(True)


class TabWidget(PhotiniUploader):
    logger = logger
    max_size = {'image': 200 * (2 ** 20),
                'video': 10 * (2 ** 30)}

    def __init__(self, *arg, **kw):
        self.user_widget = GooglePhotosUser()
        super(TabWidget, self).__init__(*arg, **kw)

    @staticmethod
    def tab_name():
        return translate('GooglePhotosTab', 'Google &Photos upload')

    def config_columns(self):
        ## first column
        column = QtWidgets.QGridLayout()
        column.setContentsMargins(0, 0, 0, 0)
        # create new set
        group = QtWidgets.QGroupBox()
        group.setMinimumWidth(width_for_text(group, 'x' * 23))
        column.addWidget(group, 0, 0)
        new_set_button = QtWidgets.QPushButton(
            translate('GooglePhotosTab', 'New album'))
        new_set_button.clicked.connect(self.new_set)
        column.addWidget(new_set_button, 1, 0)
        column.setRowStretch(0, 1)
        yield column

    def clear_albums(self):
        for child in self.widget['albums'].children():
            if child.isWidgetType():
                self.widget['albums'].layout().removeWidget(child)
                child.setParent(None)

    def checked_albums(self):
        result = []
        for child in self.widget['albums'].children():
            if child.isWidgetType() and child.isChecked():
                result.append(child.property('id'))
        return result

    def add_album(self, album, index=-1):
        widget = QtWidgets.QCheckBox(album['title'].replace('&', '&&'))
        widget.setProperty('id', album['id'])
        widget.setEnabled(album['isWriteable'])
        if index >= 0:
            self.widget['albums'].layout().insertWidget(index, widget)
        else:
            self.widget['albums'].layout().addWidget(widget)
        return widget

    def accepted_image_type(self, file_type):
        # see https://developers.google.com/photos/library/guides/upload-media#file-types-sizes
        return file_type in ('image/gif', 'image/heic', 'image/jpeg',
                             'image/png', 'image/tiff', 'image/webp',
                             'image/x-ms-bmp')

    def get_conversion_function(self, image, params):
        convert = super(
            TabWidget, self).get_conversion_function(image, params)
        if convert == 'omit':
            return convert
        # Google's docs say to remind user of storage limits if uploads
        # exceed 25 MB per user. We do it if any item exceeds 25 MB.
        max_size = 25 * 1024 * 1024
        size = os.stat(image.path).st_size
        if size <= max_size:
            return convert
        dialog = QtWidgets.QMessageBox(parent=self)
        dialog.setWindowTitle(
            translate('GooglePhotosTab', 'Photini: large file'))
        dialog.setText('<h3>{}</h3>'.format(
            translate('GooglePhotosTab', 'Large file.')))
        dialog.setInformativeText(
            translate('GooglePhotosTab',
                      'File "{file_name}" is over 25 MB. Remember that Photini '
                      'uploads count towards storage in your Google Account. '
                      'Upload it anyway?').format(
                          file_name=os.path.basename(image.path)))
        dialog.setIcon(dialog.Icon.Warning)
        dialog.setStandardButtons(dialog.StandardButton.Yes)
        self.add_skip_button(dialog)
        if execute(dialog) == dialog.StandardButton.Yes:
            return convert
        return 'omit'

    def get_upload_params(self, image):
        description = []
        if image.metadata.title:
            description.append(image.metadata.title.default_text())
        if image.metadata.headline:
            description.append(image.metadata.headline)
        if image.metadata.description:
            description.append(image.metadata.description.default_text())
        if description:
            description = '\n\n'.join(description)
        else:
            description = image.path
        params = {
            'description': description,
            'albums'     : self.checked_albums(),
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
        widget = self.add_album(album, index=0)
        widget.setChecked(True)
