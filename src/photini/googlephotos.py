##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2019-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import keyring
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError
import requests
from requests_oauthlib import OAuth2Session

from photini.pyqt import (
    catch_all, execute, QtCore, QtSlot, QtWidgets, width_for_text)
from photini.uploader import PhotiniUploader, UploaderSession, UploaderUser

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate

# Google Photos API: https://developers.google.com/photos/library/reference/rest

class GooglePhotosSession(UploaderSession):
    oauth_url  = 'https://www.googleapis.com/oauth2/'
    photos_url = 'https://photoslibrary.googleapis.com/'

    def open_connection(self):
        if self.api:
            return
        self.api = OAuth2Session(
            client_id=self.client_data['client_id'],
            token=self.user_data['token'],
            auto_refresh_url=self.oauth_url + 'v4/token',
            auto_refresh_kwargs=self.client_data, token_updater=self.save_token)
        self.api.headers.update(self.headers)

    def save_token(self, token):
        self.user_data['token'] = token
        self.new_token.emit(token)

    def api_call(self, url, post=False, **params):
        self.open_connection()
        try:
            if post:
                rsp = self.api.post(url, timeout=5, **params)
            else:
                rsp = self.api.get(url, timeout=5, **params)
        except InvalidGrantError as ex:
            # probably an expired token, force new login
            self.close_connection()
            if keyring.get_password('photini', 'googlephotos'):
                keyring.delete_password('photini', 'googlephotos')
            return {}
        rsp = self.check_response(rsp)
        if not rsp:
            self.close_connection()
        return rsp

    def new_album(self, title):
        body = {'album': {'title': title}}
        return self.api_call(
            self.photos_url + 'v1/albums', json=body, post=True)

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
        rsp.raise_for_status()
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
            rsp.raise_for_status()
            self.upload_progress.emit({'value': offset * 100 // fileobj.len})
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
        if not (rsp and 'newMediaItemResults' in rsp):
            return 'failed to create media item'
        rsp = rsp['newMediaItemResults'][0]
        if 'status' in rsp:
            if rsp['status']['message'] not in ('Success', 'OK'):
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
    logger = logger
    config_section = 'googlephotos'
    scope = ('profile', 'https://www.googleapis.com/auth/photoslibrary')
    max_size = {'image': {'bytes': 200 * (2 ** 20)},
                'video': {'bytes': 10 * (2 ** 30)}}

    def on_connect(self, widgets):
        with self.session(parent=self) as session:
            # check auth
            yield 'connected', session.api.authorized
            # get user details
            rsp = session.api_call(session.oauth_url + 'v2/userinfo')
            if not rsp:
                yield 'connected', False
            if 'locale' in rsp:
                self.user_data['lang'] = rsp['locale']
            else:
                self.user_data['lang'] = None
            name = rsp['name']
            rsp = session.check_response(
                session.api.get(rsp['picture']), decode=False)
            picture = rsp and rsp.content
            yield 'user', (name, picture)
            # get albums
            params = {}
            while True:
                rsp = session.api_call(
                    session.photos_url + 'v1/albums', params=params)
                if not (rsp and 'albums' in rsp):
                    break
                for album in rsp['albums']:
                    if 'id' not in album:
                        logger.info('Malformed album', album)
                        continue
                    yield 'album', self.normalise_album(album)
                if 'nextPageToken' not in rsp:
                    break
                params['pageToken'] = rsp['nextPageToken']

    def load_user_data(self):
        refresh_token = self.get_password()
        if not refresh_token:
            return False
        # create an expired token
        self.user_data['token'] = {
            'access_token' : 'xxx',
            'refresh_token': refresh_token,
            'expires_in'   : -30,
            }
        return True

    @staticmethod
    def service_name():
        return translate('GooglePhotosTab', 'Google Photos')

    def new_session(self, **kw):
        session = GooglePhotosSession(
            user_data=self.user_data, client_data=self.client_data, **kw)
        session.new_token.connect(self.new_token)
        return session

    def auth_exchange(self, redirect_uri):
        code_verifier = ''
        while len(code_verifier) < 43:
            code_verifier += OAuth2Session().new_state()
        auth_params = {
            'code_verifier': code_verifier,
            'redirect_uri' : redirect_uri,
            }
        auth_params.update(self.client_data)
        url = 'https://accounts.google.com/o/oauth2/v2/auth'
        url += '?client_id=' + auth_params['client_id']
        url += '&redirect_uri=' + auth_params['redirect_uri']
        url += '&response_type=code'
        url += '&scope=' + urllib.parse.quote(' '.join(self.scope))
        url += '&code_challenge=' + auth_params['code_verifier']
        result = yield url
        if not 'code' in result:
            logger.info('No authorisaton code received')
            return
        data = {
            'code'      : result['code'][0],
            'grant_type': 'authorization_code',
            }
        data.update(auth_params)
        try:
            rsp = requests.post(GooglePhotosSession.oauth_url + 'v4/token',
                                data=data, timeout=5)
            rsp.raise_for_status()
            rsp = rsp.json()
        except Exception as ex:
            logger.error(str(ex))
            return
        if 'access_token' not in rsp:
            logger.info('No access token received')
            return
        self.new_token(rsp)
        self.connection_changed.emit(True)

    @QtSlot(dict)
    @catch_all
    def new_token(self, token):
        self.user_data['token'] = token
        self.set_password(self.user_data['token']['refresh_token'])

    @staticmethod
    def normalise_album(album):
        album['writeable'] = 'isWriteable' in album and album['isWriteable']
        album['description'] = None
        return album


class TabWidget(PhotiniUploader):
    logger = logger

    def __init__(self, *arg, **kw):
        self.user_widget = GooglePhotosUser()
        super(TabWidget, self).__init__(*arg, **kw)

    @staticmethod
    def tab_name():
        return translate('GooglePhotosTab', 'Google Photos upload',
                         'Full name of tab shown as a tooltip')

    @staticmethod
    def tab_short_name():
        return translate('GooglePhotosTab', '&Google',
                         'Shortest possible name used as tab label')

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
        yield column, 0
        ## last column is list of albums
        yield self.album_list(), 1

    def accepted_image_type(self, file_type):
        # see https://developers.google.com/photos/library/guides/upload-media#file-types-sizes
        return file_type in ('image/gif', 'image/heic', 'image/jpeg',
                             'image/png', 'image/tiff', 'image/webp',
                             'image/x-ms-bmp')

    def get_conversion_function(self, image, state, params):
        convert = super(
            TabWidget, self).get_conversion_function(image, state, params)
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

    def get_upload_params(self, image, state):
        lang = self.user_widget.user_data['lang']
        description = []
        if image.metadata.title:
            description.append(image.metadata.title.best_match(lang))
        if image.metadata.headline:
            description.append(image.metadata.headline)
        if image.metadata.description:
            description.append(image.metadata.description.best_match(lang))
        if description:
            description = '\n\n'.join(description)
        else:
            description = image.path
        params = {
            'description': description,
            'albums'     : self.widget['albums'].get_checked_ids(),
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
        with self.user_widget.session(parent=self) as session:
            album = session.new_album(title)
        if not album:
            return
        album = GooglePhotosUser.normalise_album(album)
        widget = self.widget['albums'].add_album(album, index=0)
        widget.setChecked(True)
