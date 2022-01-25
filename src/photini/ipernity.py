##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2022  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

import html
import logging
import os
import urllib

import requests
from requests_oauthlib import OAuth1Session
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

from photini.pyqt import (Busy, catch_all, ComboBox, MultiLineEdit, Qt, QtCore,
                          QtGui, QtSignal, QtSlot, QtWidgets, SingleLineEdit)
from photini.uploader import PhotiniUploader, UploaderSession

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate

ID_TAG = 'ipernity:doc_id'

# Ipernity API: http://www.ipernity.com/help/api
# OAuth1Session: https://requests-oauthlib.readthedocs.io/en/latest/api.html
# requests: https://docs.python-requests.org/

class IpernitySession(UploaderSession):
    name = 'ipernity'
    oauth_url = 'http://www.ipernity.com/apps/oauth/'

    def open_connection(self):
        self.cached_data = {}
        stored_token = self.get_password()
        if not stored_token:
            return False
        token, token_secret = stored_token.split('&')
        self.api = OAuth1Session(
            client_key=self.api_key, client_secret=self.api_secret,
            resource_owner_key=token, resource_owner_secret=token_secret,
            )
        if not self.api:
            return None
        authorized = self.api.authorized
        self.connection_changed.emit(authorized)
        return authorized

    def get_auth_url(self, redirect_uri):
        # initialise oauth1 session
        if self.api:
            self.api.close()
        self.api = OAuth1Session(
            client_key=self.api_key, client_secret=self.api_secret)
        try:
            self.api.fetch_request_token(
                self.oauth_url + 'request', timeout=20)
            return self.api.authorization_url(
                self.oauth_url + 'authorize', perm_doc='write',
                oauth_callback=redirect_uri)
        except Exception as ex:
            logger.error(str(ex))
            self.close_connection()
        return ''

    def get_access_token(self, result):
        oauth_token = str(result['oauth_token'][0])
        try:
            token = self.api.fetch_access_token(
                self.oauth_url + 'access', verifier=oauth_token,
                timeout=20)
        except Exception as ex:
            logger.error(str(ex))
            self.close_connection()
            return
        self.set_password(
            token['oauth_token'] + '&' + token['oauth_token_secret'])
        self.connection_changed.emit(self.api.authorized)

    def api_call(self, method, post=False, **params):
        if not self.api:
            return {}
        url = 'http://api.ipernity.com/api/' + method
        try:
            if post:
                rsp = self.api.post(url, timeout=20, data=params)
            else:
                rsp = self.api.get(url, timeout=20, params=params)
        except Exception as ex:
            logger.error(str(ex))
            self.close_connection()
            return {}
        if rsp.status_code != 200:
            logger.error('HTTP error %d', rsp.status_code)
            return {}
        rsp = rsp.json()
        if rsp['api']['status'] != 'ok':
            logger.error('API error %s', str(rsp['api']))
            return {}
        return rsp

    def get_user(self):
        if 'user' in self.cached_data:
            return self.cached_data['user']
        name, picture = None, None
        # get user_id of logged in user
        rsp = self.api_call('auth.checkToken')
        if not rsp:
            return name, picture
        user_id = rsp['auth']['user']['user_id']
        # get user info
        rsp = self.api_call('user.get', user_id=user_id)
        if not rsp:
            return name, picture
        name = rsp['user']['username']
        icon_url = rsp['user']['icon']
        # get icon
        rsp = requests.get(icon_url)
        if rsp.status_code == 200:
            picture = rsp.content
        else:
            logger.error('HTTP error %d (%s)', rsp.status_code, icon_url)
        self.cached_data['user'] = name, picture
        return self.cached_data['user']

    def get_albums(self):
        if 'albums' in self.cached_data:
            return self.cached_data['albums']
        # get list of album ids
        album_ids = []
        params = {'empty': '1'}
        while True:
            rsp = self.api_call('album.getList', **params)
            if not rsp:
                break
            albums = rsp['albums']
            for album in albums['album']:
                album_ids.append(album['album_id'])
            if albums['page'] == albums['pages']:
                break
            params['page'] = str(int(albums['page']) + 1)
        # get details of each album
        self.cached_data['albums'] = []
        for album_id in album_ids:
            rsp = self.api_call('album.get', album_id=album_id)
            if not rsp:
                continue
            album = rsp['album']
            self.cached_data['albums'].append((
                album['title'], album['description'], album['album_id']))
        return self.cached_data['albums']

    def progress(self, monitor):
        self.upload_progress.emit(monitor.bytes_read * 100 // monitor.len)

    def do_upload(self, fileobj, image_type, image, params):
        doc_id = params['doc_id']
        if params['function']:
            # upload or replace photo
            url = 'http://api.ipernity.com/api/' + params['function']
            if params['function'] == 'upload.file':
                data = {}
                # set some metadata with upload function
                for key in ('visibility', 'permissions', 'meta', 'location'):
                    if key in params and params[key]:
                        data.update(params[key])
                        del(params[key])
            else:
                data = {'doc_id': doc_id}
            data['async'] = '0'
            # get the headers (without 'file') from a dummy Request, an idea
            # I've stolen from https://github.com/sybrenstuvel/flickrapi
            request = requests.Request('POST', url, data=data)
            headers = self.api.prepare_request(request).headers
            # add file to parameters now we've got the headers without it
            data['file'] = ('dummy_name', fileobj)
            data = MultipartEncoderMonitor(
                MultipartEncoder(fields=data), self.progress)
            headers = {'Authorization': headers['Authorization'],
                       'Content-Type': data.content_type}
            # use requests to post data
            rsp = requests.post(url, data=data, headers=headers, timeout=20)
            if rsp.status_code != 200:
                logger.error('HTTP error %d', rsp.status_code)
                return 'HTTP error {}'.format(rsp.status_code)
            # parse response
            rsp = rsp.json()
            if rsp['api']['status'] != 'ok':
                return params['function'] + ' ' + str(rsp['api'])
            doc_id = rsp['doc_id']
        # store photo id in image keywords
        keyword = '{}={}'.format(ID_TAG, doc_id)
        if not image.metadata.keywords:
            image.metadata.keywords = [keyword]
        elif keyword not in image.metadata.keywords:
            image.metadata.keywords = list(image.metadata.keywords) + [keyword]
        # set remaining metadata after uploading image
        metadata_set_func = {
            'visibility' : 'doc.setPerms',
            'permissions': 'doc.setPerms',
            'meta'       : 'doc.set',
            'keywords'   : 'doc.tags.edit',
            'location'   : 'doc.setGeo',
            }
        for key in params:
            if params[key] and key in metadata_set_func:
                rsp = self.api_call(metadata_set_func[key], post=True,
                                    doc_id=doc_id, **params[key])
                if not rsp:
                    return 'Failed to set ' + key
        # add to or remove from albums
        if 'albums' not in params:
            return ''
        current_albums = []
        if params['function'] != 'upload.file':
            # get albums existing photo is in
            rsp = self.api_call('doc.getContainers', doc_id=doc_id)
            if not rsp:
                return 'Failed to get album list'
            for album in rsp['albums']['album']:
                current_albums.append(album['album_id'])
        for album_id in params['albums']:
            if album_id in current_albums:
                # photo is already in the set
                current_albums.remove(album_id)
            else:
                # add to existing album
                rsp = self.api_call('album.docs.add', post=True,
                                    album_id=album_id, doc_id=doc_id)
                if not rsp:
                    return 'Failed to set album'
        # remove from any other albums
        for album_id in current_albums:
            self.api_call('album.docs.remove', post=True,
                          album_id=album_id, doc_id=doc_id)
        return ''


class PermissionWidget(ComboBox):
    def __init__(self, default='5', *arg, **kw):
        super(PermissionWidget, self).__init__(*arg, **kw)
        self.addItem(translate('IpernityTab', 'Only you'), '0')
        self.addItem(translate('IpernityTab', 'Friends and family'), '3')
        self.addItem(translate('IpernityTab', 'Contacts'), '4')
        self.addItem(translate('IpernityTab', 'Everyone'), '5')
        self.setCurrentIndex(self.findData(default))
        self.set_dropdown_width()

    def value(self):
        return self.itemData(self.currentIndex())


class IpernityUploadConfig(QtWidgets.QWidget):
    new_album = QtSignal()

    def __init__(self, *arg, **kw):
        super(IpernityUploadConfig, self).__init__(*arg, **kw)
        self.setLayout(QtWidgets.QGridLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        # privacy settings
        self.privacy = {}
        privacy_group = QtWidgets.QGroupBox(
            translate('IpernityTab', 'Who can see the photos?'))
        privacy_group.setLayout(QtWidgets.QVBoxLayout())
        self.privacy['private'] = QtWidgets.QRadioButton(
            translate('IpernityTab', 'Only you (private)'))
        privacy_group.layout().addWidget(self.privacy['private'])
        ff_group = QtWidgets.QGroupBox()
        ff_group.setFlat(True)
        ff_group.setLayout(QtWidgets.QVBoxLayout())
        ff_group.layout().setContentsMargins(10, 0, 0, 0)
        self.privacy['family'] = QtWidgets.QCheckBox(
            translate('IpernityTab', 'Your family'))
        ff_group.layout().addWidget(self.privacy['family'])
        self.privacy['friends'] = QtWidgets.QCheckBox(
            translate('IpernityTab', 'Your friends'))
        ff_group.layout().addWidget(self.privacy['friends'])
        privacy_group.layout().addWidget(ff_group)
        self.privacy['public'] = QtWidgets.QRadioButton(
            translate('IpernityTab', 'Everyone (public)'))
        self.privacy['public'].toggled.connect(self.enable_ff)
        self.privacy['public'].setChecked(True)
        privacy_group.layout().addWidget(self.privacy['public'])
        privacy_group.layout().addStretch(1)
        self.layout().addWidget(privacy_group, 0, 0, 3, 1)
        # comment and tagging settings
        self.perms = {}
        perms_group = QtWidgets.QGroupBox(
            translate('IpernityTab', 'Who can comment or tag?'))
        perms_group.setLayout(QtWidgets.QFormLayout())
        perms_group.layout().setRowWrapPolicy(QtWidgets.QFormLayout.WrapAllRows)
        self.perms['perm_comment'] = PermissionWidget()
        perms_group.layout().addRow(
            translate('IpernityTab', 'Post a comment'),
            self.perms['perm_comment'])
        self.perms['perm_tag'] = PermissionWidget(default='4')
        perms_group.layout().addRow(
            translate('IpernityTab', 'Add keywords or notes'),
            self.perms['perm_tag'])
        self.perms['perm_tagme'] = PermissionWidget(default='4')
        perms_group.layout().addRow(
            translate('IpernityTab', 'Identify people'),
            self.perms['perm_tagme'])
        self.layout().addWidget(perms_group, 0, 1, 2, 1)
        # create new album
        new_album_button = QtWidgets.QPushButton(
            translate('IpernityTab', 'New album'))
        new_album_button.clicked.connect(self.new_album)
        self.layout().addWidget(new_album_button, 2, 1)
        # list of albums widget
        albums_group = QtWidgets.QGroupBox(
            translate('IpernityTab', 'Add to albums'))
        albums_group.setLayout(QtWidgets.QVBoxLayout())
        scrollarea = QtWidgets.QScrollArea()
        scrollarea.setFrameStyle(QtWidgets.QFrame.NoFrame)
        scrollarea.setStyleSheet("QScrollArea { background-color: transparent }")
        self.albums_widget = QtWidgets.QWidget()
        self.albums_widget.setLayout(QtWidgets.QVBoxLayout())
        self.albums_widget.layout().setSpacing(0)
        self.albums_widget.layout().setSizeConstraint(
            QtWidgets.QLayout.SetMinAndMaxSize)
        scrollarea.setWidget(self.albums_widget)
        self.albums_widget.setAutoFillBackground(False)
        albums_group.layout().addWidget(scrollarea)
        self.layout().addWidget(albums_group, 0, 2, 3, 1)
        self.layout().setColumnStretch(2, 1)

    @QtSlot(bool)
    @catch_all
    def enable_ff(self, value):
        self.privacy['friends'].setEnabled(self.privacy['private'].isChecked())
        self.privacy['family'].setEnabled(self.privacy['private'].isChecked())

    def get_fixed_params(self):
        is_public = str(int(self.privacy['public'].isChecked()))
        is_family = str(int(self.privacy['private'].isChecked() and
                            self.privacy['family'].isChecked()))
        is_friend = str(int(self.privacy['private'].isChecked() and
                            self.privacy['friends'].isChecked()))
        return {
            'visibility': {
                'is_public': is_public,
                'is_friend': is_friend,
                'is_family': is_family,
                },
            'permissions': {
                'perm_comment': self.perms['perm_comment'].value(),
                'perm_tag'    : self.perms['perm_tag'].value(),
                'perm_tagme'  : self.perms['perm_tagme'].value(),
                },
            }

    def clear_albums(self):
        for child in self.albums_widget.children():
            if child.isWidgetType():
                self.albums_widget.layout().removeWidget(child)
                child.setParent(None)

    def checked_albums(self):
        result = []
        for child in self.albums_widget.children():
            if child.isWidgetType() and child.isChecked():
                result.append(child.property('album_id'))
        return result

    def add_album(self, title, description, album_id, index=-1):
        widget = QtWidgets.QCheckBox(title.replace('&', '&&'))
        if description:
            widget.setToolTip(html.unescape(description))
        widget.setProperty('album_id', album_id)
        if index >= 0:
            self.albums_widget.layout().insertWidget(index, widget)
        else:
            self.albums_widget.layout().addWidget(widget)
        return widget


class TabWidget(PhotiniUploader):
    session_factory = IpernitySession

    @staticmethod
    def tab_name():
        return translate('IpernityTab', '&Ipernity upload')

    def __init__(self, *arg, **kw):
        self.service_name = translate('IpernityTab', 'Ipernity')
        self.upload_config = IpernityUploadConfig()
        super(TabWidget, self).__init__(self.upload_config, *arg, **kw)
        self.upload_config.new_album.connect(self.new_album)
        self.image_types = {
            'accepted': ('image/gif', 'image/jpeg', 'image/png',
                         'video/mp4', 'video/quicktime', 'video/riff'),
            'rejected': ('image/x-canon-cr2',),
            }
        self.replace_prefs = {
            'set_metadata'   : True,
            'set_visibility' : False,
            'set_permissions': False,
            'set_albums'     : False,
            'replace_image'  : False,
            'new_photo'      : False,
            }

    def get_conversion_function(self, image, params):
        if not params['function']:
            return None
        convert = super(
            TabWidget, self).get_conversion_function(image, params)
        if convert == 'omit':
            return convert
        max_size = 2 ** 30
        size = os.stat(image.path).st_size
        if size < max_size:
            return convert
        dialog = QtWidgets.QMessageBox(parent=self)
        dialog.setWindowTitle(
            translate('IpernityTab', 'Photini: too large'))
        dialog.setText(
            translate('IpernityTab', '<h3>File too large.</h3>'))
        dialog.setInformativeText(
            translate('IpernityTab',
                      'File "{0}" has {1} bytes and exceeds Ipernity\'s limit' +
                      ' of {2} bytes.').format(
                          os.path.basename(image.path), size, max_size))
        dialog.setIcon(QtWidgets.QMessageBox.Warning)
        dialog.setStandardButtons(QtWidgets.QMessageBox.Ignore)
        dialog.exec_()
        return 'omit'

    def show_album_list(self, albums):
        self.upload_config.clear_albums()
        for item in albums:
            self.upload_config.add_album(*item)

    def get_upload_params(self, image):
        option, doc_id = self._replace_dialog(image)
        if not option or not any(option.values()):
            # user chose to do nothing
            return None
        # set upload function
        if option['new_photo']:
            params = {'function': 'upload.file'}
            doc_id = None
        elif option['replace_image']:
            params = {'function': 'upload.replace'}
        else:
            params = {'function': None}
        params['doc_id'] = doc_id
        # set config params that apply to all photos
        fixed_params = self.upload_config.get_fixed_params()
        if option['new_photo'] or option['set_visibility']:
            params['visibility'] = fixed_params['visibility']
        if option['new_photo'] or option['set_permissions']:
            params['permissions'] = fixed_params['permissions']
        # add metadata
        if option['new_photo'] or option['set_metadata']:
            # title & description
            params['meta'] = {
                'title'      : image.metadata.title or image.name,
                'description': image.metadata.description or '',
                }
            # keywords
            keywords = ['uploaded:by=photini']
            for keyword in image.metadata.keywords or []:
                if not keyword.startswith(ID_TAG):
                    keyword = keyword.replace('"', "'")
                    if ',' in keyword:
                        keyword = '"' + keyword + '"'
                    keywords.append(keyword)
            params['keywords'] = {'keywords': ','.join(keywords)}
            # location
            if image.metadata.latlong:
                params['location'] = {
                    'lat': '{:.6f}'.format(
                        float(image.metadata.latlong['lat'])),
                    'lng': '{:.6f}'.format(
                        float(image.metadata.latlong['lon'])),
                    }
            else:
                # clear any existing location
                params['location'] = {'lat': '-999', 'lng': '-999'}
        # make list of albums to add photos to
        if option['new_photo'] or option['set_albums']:
            params['albums'] = self.upload_config.checked_albums()
        return params

    def _replace_dialog(self, image):
        # has image already been uploaded?
        for keyword in image.metadata.keywords or []:
            name_pred, sep, doc_id = keyword.partition('=')
            if name_pred == ID_TAG:
                break
        else:
            # new upload
            return {
                'set_metadata'   : True,
                'set_visibility' : True,
                'set_permissions': True,
                'set_albums'     : True,
                'replace_image'  : False,
                'new_photo'      : True,
                }, None
        # get user preferences
        dialog = QtWidgets.QDialog(parent=self)
        dialog.setWindowTitle(translate('IpernityTab', 'Replace photo'))
        dialog.setLayout(QtWidgets.QVBoxLayout())
        message = QtWidgets.QLabel(translate(
            'IpernityTab', 'File {0} has already been uploaded to Ipernity.'
            ' How would you like to update it?').format(
                os.path.basename(image.path)))
        message.setWordWrap(True)
        dialog.layout().addWidget(message)
        widget = {}
        widget['set_metadata'] = QtWidgets.QCheckBox(
            translate('IpernityTab', 'Replace metadata'))
        widget['set_visibility'] = QtWidgets.QCheckBox(
            translate('IpernityTab', 'Change who can see it'))
        widget['set_permissions'] = QtWidgets.QCheckBox(
            translate('IpernityTab', 'Change who can comment or tag'))
        widget['set_albums'] = QtWidgets.QCheckBox(
            translate('IpernityTab', 'Change album membership'))
        widget['replace_image'] = QtWidgets.QCheckBox(
            translate('IpernityTab', 'Replace image'))
        widget['new_photo'] = QtWidgets.QCheckBox(
            translate('IpernityTab', 'Upload as new photo'))
        widget['new_photo'].toggled.connect(widget['set_metadata'].setDisabled)
        widget['new_photo'].toggled.connect(widget['set_visibility'].setDisabled)
        widget['new_photo'].toggled.connect(widget['set_permissions'].setDisabled)
        widget['new_photo'].toggled.connect(widget['set_albums'].setDisabled)
        no_upload = QtWidgets.QCheckBox(
            translate('IpernityTab', 'No image upload'))
        no_upload.setChecked(True)
        button_group = QtWidgets.QButtonGroup()
        button_group.addButton(widget['replace_image'])
        button_group.addButton(widget['new_photo'])
        button_group.addButton(no_upload)
        for key in ('set_metadata', 'set_visibility', 'set_permissions',
                    'set_albums', 'replace_image', 'new_photo'):
            dialog.layout().addWidget(widget[key])
            widget[key].setChecked(self.replace_prefs[key])
        dialog.layout().addWidget(no_upload)
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addWidget(button_box)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return None, doc_id
        for key in self.replace_prefs:
            self.replace_prefs[key] = widget[key].isChecked()
        return dict(self.replace_prefs), doc_id

    @QtSlot()
    @catch_all
    def new_album(self):
        dialog = QtWidgets.QDialog(parent=self)
        dialog.setWindowTitle(translate(
            'IpernityTab', 'Create new Ipernity album'))
        dialog.setLayout(QtWidgets.QFormLayout())
        title = SingleLineEdit(spell_check=True)
        dialog.layout().addRow(translate('IpernityTab', 'Title'), title)
        description = MultiLineEdit(spell_check=True)
        dialog.layout().addRow(translate(
            'IpernityTab', 'Description'), description)
        perm_comment = PermissionWidget()
        dialog.layout().addRow(translate(
            'IpernityTab', 'Who can comment<br>on album'), perm_comment)
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addRow(button_box)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        params = {
            'title': title.toPlainText(),
            'description': description.toPlainText(),
            'perm_comment': perm_comment.value(),
            }
        if not params['title']:
            return
        rsp = self.session.api_call('album.create', post=True, **params)
        if not rsp:
            return
        widget = self.upload_config.add_album(
            params['title'], params['description'],
            rsp['album']['album_id'], index=0)
        widget.setChecked(True)
