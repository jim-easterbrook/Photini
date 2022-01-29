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

import hashlib
import html
import logging
import os
import time

import requests
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

from photini.pyqt import (
    Busy, catch_all, DropDownSelector, execute, MultiLineEdit, Qt, QtCore,
    QtGui, QtSignal, QtSlot, QtWidgets, SingleLineEdit, width_for_text)
from photini.uploader import ConfigFormLayout, PhotiniUploader, UploaderSession

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate

ID_TAG = 'ipernity:doc_id'

# Ipernity API: http://www.ipernity.com/help/api
# requests: https://docs.python-requests.org/

class IpernitySession(UploaderSession):
    name = 'ipernity'

    def open_connection(self):
        self.cached_data = {}
        self.auth_token = self.get_password()
        if not self.auth_token:
            return False
        rsp = self.api_call('auth.checkToken')
        authorised = rsp and rsp['auth']['permissions']['doc'] == 'write'
        if authorised:
            self.cached_data['user_id'] = rsp['auth']['user']['user_id']
        self.connection_changed.emit(authorised)
        return authorised

    def get_frob(self):
        rsp = self.api_call('auth.getFrob', auth=False)
        if not rsp:
            return ''
        return rsp['auth']['frob']

    def get_auth_url(self, frob):
        params = {'frob': frob, 'perm_doc': 'write'}
        params = self.sign_request('', False, params)
        request = requests.Request(
            'GET', 'http://www.ipernity.com/apps/authorize', params=params)
        return request.prepare().url

    def get_access_token(self, frob):
        if not frob:
            return
        rsp = self.api_call('auth.getToken', auth=False, frob=frob)
        if not rsp:
            return
        self.set_password(rsp['auth']['token'])
        self.open_connection()

    def sign_request(self, method, auth, params):
        params = dict(params)
        params['api_key'] = self.api_key
        if auth:
            params['auth_token'] = self.auth_token
        string = ''
        for key in sorted(params):
            string += key + params[key]
        string += method + self.api_secret
        params['api_sig'] = hashlib.md5(string.encode('utf-8')).hexdigest()
        return params

    def api_call(self, method, post=False, auth=True, **params):
        if not self.api:
            self.api = requests.session()
        url = 'http://api.ipernity.com/api/' + method
        params = self.sign_request(method, auth, params)
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
            logger.error('HTTP error %s: %d', method, rsp.status_code)
            return {}
        rsp = rsp.json()
        if rsp['api']['status'] != 'ok':
            logger.error('API error %s: %s', method, str(rsp['api']))
            return {}
        return rsp

    def get_user(self):
        if 'user' in self.cached_data:
            return self.cached_data['user']
        name, picture = None, None
        # get user info
        rsp = self.api_call(
            'user.get', auth=False, user_id=self.cached_data['user_id'])
        if not rsp:
            return name, picture
        name = rsp['user']['username']
        icon_url = rsp['user']['icon']
        # get icon
        rsp = self.api.get(icon_url)
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
        self.upload_progress.emit(
            {'value': monitor.bytes_read * 100 // monitor.len})

    def do_upload(self, fileobj, image_type, image, params):
        doc_id = params['doc_id']
        if params['function']:
            # upload or replace photo
            self.upload_progress.emit({'busy': False})
            url = 'http://api.ipernity.com/api/' + params['function']
            if params['function'] == 'upload.file':
                data = {}
                # set some metadata with upload function
                for key in ('visibility', 'permissions', 'licence', 'meta',
                            'location'):
                    if key in params and params[key]:
                        data.update(params[key])
                        del(params[key])
            else:
                data = {'doc_id': doc_id}
            data['async'] = '1'
            # sign the request before including the file to upload
            data = self.sign_request(params['function'], True, data)
            # create multi-part data encoder
            data['file'] = ('dummy_name', fileobj)
            data = MultipartEncoderMonitor(
                MultipartEncoder(fields=data), self.progress)
            headers = {'Content-Type': data.content_type}
            # post data
            rsp = self.api.post(url, data=data, headers=headers, timeout=20)
            if rsp.status_code != 200:
                logger.error('HTTP error %d', rsp.status_code)
                return 'HTTP error {}'.format(rsp.status_code)
            # parse response
            rsp = rsp.json()
            if rsp['api']['status'] != 'ok':
                return params['function'] + ' ' + str(rsp['api'])
            ticket = rsp['ticket']
            # wait for processing to finish
            self.upload_progress.emit({'busy': True})
            # upload.checkTickets returns an eta but it's very
            # unreliable (e.g. saying 360 seconds for something that
            # then takes 15). Easier to poll every two seconds.
            while True:
                time.sleep(2)
                rsp = self.api_call('upload.checkTickets', tickets=ticket)
                if not rsp:
                    return 'Wait for processing failed'
                if rsp['tickets']['done'] != '0':
                    break
            doc_id = rsp['tickets']['ticket'][0]['doc_id']
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
            'licence'    : 'doc.setLicense',
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


class PermissionWidget(DropDownSelector):
    def __init__(self, default='5'):
        super(PermissionWidget, self).__init__(
            ((translate('IpernityTab', 'Only you'), '0'),
             (translate('IpernityTab', 'Family & friends'), '3'),
             (translate('IpernityTab', 'Contacts'), '4'),
             (translate('IpernityTab', 'Everyone'), '5')),
            default=default)


class LicenceWidget(DropDownSelector):
    def __init__(self, default='0'):
        super(LicenceWidget, self).__init__(
            ((translate('IpernityTab', 'Copyright (all rights reserved)'), '0'),
             (translate('IpernityTab', 'Attribution'), '1'),
             (translate('IpernityTab', 'Attribution + non commercial'), '3'),
             (translate('IpernityTab', 'Attribution + no derivative'), '5'),
             (translate('IpernityTab', 'Attribution + share alike'), '9'),
             (translate('IpernityTab',
                        'Attribution + non commercial + no derivative'), '7'),
             (translate('IpernityTab',
                        'Attribution + non commercial + share alike'), '11'),
             (translate(
                 'IpernityTab',
                 'Free use (copyright surrendered, no licence)'), '255')),
            default=default)


class TabWidget(PhotiniUploader):
    session_factory = IpernitySession

    @staticmethod
    def tab_name():
        return translate('IpernityTab', '&Ipernity upload')

    def config_columns(self):
        self.service_name = translate('IpernityTab', 'Ipernity')
        self.replace_prefs = {'metadata': True}
        self.upload_prefs = {}
        # dictionary of all widgets with parameter settings
        self.widget = {}
        ## first column
        column = QtWidgets.QGridLayout()
        column.setContentsMargins(0, 0, 0, 0)
        group = QtWidgets.QGroupBox()
        group.setMinimumWidth(width_for_text(group, 'x' * 23))
        group.setLayout(ConfigFormLayout(wrapped=True))
        # visibility
        self.widget['visibility'] = DropDownSelector(
            ((translate('IpernityTab', 'Everyone (public)'),
              {'is_friend': '0', 'is_family': '0', 'is_public': '1'}),
             (translate('IpernityTab', 'Only me (private)'),
              {'is_friend': '0', 'is_family': '0', 'is_public': '0'}),
             (translate('IpernityTab', 'Friends'),
              {'is_friend': '1', 'is_family': '0', 'is_public': '0'}),
             (translate('IpernityTab', 'Family'),
              {'is_friend': '0', 'is_family': '1', 'is_public': '0'}),
             (translate('IpernityTab', 'Family & friends'),
              {'is_friend': '1', 'is_family': '1', 'is_public': '0'})),
            default={'is_friend': '0', 'is_family': '0', 'is_public': '1'})
        group.layout().addRow(translate('IpernityTab', 'Who can: see it'),
                              self.widget['visibility'])
        # comment and tagging settings
        self.widget['perm_comment'] = PermissionWidget()
        group.layout().addRow(translate('IpernityTab', ' add comments'),
                              self.widget['perm_comment'])
        self.widget['perm_tag'] = PermissionWidget(default='4')
        group.layout().addRow(translate('IpernityTab', ' add keywords, notes'),
                              self.widget['perm_tag'])
        self.widget['perm_tagme'] = PermissionWidget(default='4')
        group.layout().addRow(translate('IpernityTab', ' identify people'),
                              self.widget['perm_tagme'])
        column.addWidget(group, 0, 0)
        yield column
        ## second column
        column = QtWidgets.QGridLayout()
        column.setContentsMargins(0, 0, 0, 0)
        group = QtWidgets.QGroupBox()
        group.setMinimumWidth(width_for_text(group, 'x' * 23))
        group.setLayout(ConfigFormLayout(wrapped=True))
        # licence
        self.widget['license'] = LicenceWidget()
        group.layout().addRow(
            translate('IpernityTab', 'Licence'), self.widget['license'])
        column.addWidget(group, 0, 0)
        # create new album
        new_album_button = QtWidgets.QPushButton(
            translate('IpernityTab', 'New album'))
        new_album_button.clicked.connect(self.new_album)
        column.addWidget(new_album_button, 1, 0)
        yield column
        ## 3rd column
        column = QtWidgets.QGridLayout()
        column.setContentsMargins(0, 0, 0, 0)
        # list of albums widget
        group = QtWidgets.QGroupBox()
        group.setLayout(QtWidgets.QVBoxLayout())
        group.layout().addWidget(QtWidgets.QLabel(
            translate('IpernityTab', 'Add to albums')))
        scrollarea = QtWidgets.QScrollArea()
        scrollarea.setFrameStyle(QtWidgets.QFrame.NoFrame)
        scrollarea.setStyleSheet("QScrollArea { background-color: transparent }")
        self.widget['albums'] = QtWidgets.QWidget()
        self.widget['albums'].setLayout(QtWidgets.QVBoxLayout())
        self.widget['albums'].layout().setSpacing(0)
        self.widget['albums'].layout().setSizeConstraint(
            QtWidgets.QLayout.SetMinAndMaxSize)
        scrollarea.setWidget(self.widget['albums'])
        self.widget['albums'].setAutoFillBackground(False)
        group.layout().addWidget(scrollarea)
        column.addWidget(group, 0, 0)
        yield column

    def get_fixed_params(self):
        albums = []
        for child in self.widget['albums'].children():
            if child.isWidgetType() and child.isChecked():
                albums.append(child.property('album_id'))
        return {
            'visibility': self.widget['visibility'].value(),
            'permissions': {
                'perm_comment': self.widget['perm_comment'].value(),
                'perm_tag'    : self.widget['perm_tag'].value(),
                'perm_tagme'  : self.widget['perm_tagme'].value(),
                },
            'licence': {
                'license': self.widget['license'].value(),
                },
            'albums': albums,
            }

    def clear_albums(self):
        for child in self.widget['albums'].children():
            if child.isWidgetType():
                self.widget['albums'].layout().removeWidget(child)
                child.setParent(None)

    def add_album(self, title, description, album_id, index=-1):
        widget = QtWidgets.QCheckBox(title.replace('&', '&&'))
        if description:
            widget.setToolTip(html.unescape(description))
        widget.setProperty('album_id', album_id)
        if index >= 0:
            self.widget['albums'].layout().insertWidget(index, widget)
        else:
            self.widget['albums'].layout().addWidget(widget)
        return widget

    def accepted_file_type(self, file_type):
        # ipernity accepts most RAW formats!
        return file_type.split('/')[0] in ('image', 'video')

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
        execute(dialog)
        return 'omit'

    def show_album_list(self, albums):
        self.clear_albums()
        for item in albums:
            self.add_album(*item)

    def get_upload_params(self, image):
        # get user preferences for this upload
        upload_prefs, replace_prefs, doc_id = self._replace_dialog(image)
        if not upload_prefs:
            # user cancelled dialog
            return None
        # get config params that apply to all photos
        fixed_params = self.get_fixed_params()
        # set upload function and params
        if upload_prefs['new_photo']:
            params = {'function': 'upload.file'}
            # apply all "fixed" params
            params.update(fixed_params)
            params['doc_id'] = None
        else:
            if upload_prefs['replace_image']:
                params = {'function': 'upload.replace'}
            else:
                params = {'function': None}
                if not any(replace_prefs.values()):
                    # user chose to do nothing
                    return None
            # only apply the "fixed" params the user wants to change
            for key in fixed_params:
                if replace_prefs[key]:
                    params[key] = fixed_params[key]
            params['doc_id'] = doc_id
        # add metadata
        if upload_prefs['new_photo'] or replace_prefs['metadata']:
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
        return params

    def _replace_dialog(self, image):
        # has image already been uploaded?
        for keyword in image.metadata.keywords or []:
            name_pred, sep, doc_id = keyword.partition('=')
            if name_pred == ID_TAG:
                break
        else:
            # new upload
            return {'new_photo': True}, {}, None
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
        replace_options = {}
        replace_options['metadata'] = QtWidgets.QCheckBox(
            translate('IpernityTab', 'Replace metadata'))
        replace_options['visibility'] = QtWidgets.QCheckBox(
            translate('IpernityTab', 'Change who can see it'))
        replace_options['permissions'] = QtWidgets.QCheckBox(
            translate('IpernityTab', 'Change who can comment or tag'))
        replace_options['licence'] = QtWidgets.QCheckBox(
            translate('IpernityTab', 'Change the licence'))
        replace_options['albums'] = QtWidgets.QCheckBox(
            translate('IpernityTab', 'Change album membership'))
        for key in self.replace_prefs:
            replace_options[key].setChecked(self.replace_prefs[key])
        upload_options = {}
        upload_options['replace_image'] = QtWidgets.QRadioButton(
            translate('IpernityTab', 'Replace image'))
        upload_options['new_photo'] = QtWidgets.QRadioButton(
            translate('IpernityTab', 'Upload as new photo'))
        upload_options['no_upload'] = QtWidgets.QRadioButton(
            translate('IpernityTab', 'No image upload'))
        for key in self.upload_prefs:
            if self.upload_prefs[key]:
                upload_options[key].setChecked(True)
                break
        else:
            upload_options['no_upload'].setChecked(True)
        two_columns = QtWidgets.QHBoxLayout()
        column = QtWidgets.QVBoxLayout()
        for key in replace_options:
            upload_options['new_photo'].toggled.connect(
                replace_options[key].setDisabled)
            column.addWidget(replace_options[key])
        two_columns.addLayout(column)
        column = QtWidgets.QVBoxLayout()
        for key in upload_options:
            column.addWidget(upload_options[key])
        column.addStretch(1)
        two_columns.addLayout(column)
        dialog.layout().addLayout(two_columns)
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addWidget(button_box)
        if execute(dialog) != QtWidgets.QDialog.Accepted:
            return {}, {}, doc_id
        for key in replace_options:
            self.replace_prefs[key] = replace_options[key].isChecked()
        for key in upload_options:
            self.upload_prefs[key] = upload_options[key].isChecked()
        return self.upload_prefs, self.replace_prefs, doc_id

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
        if execute(dialog) != QtWidgets.QDialog.Accepted:
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
        widget = self.add_album(
            params['title'], params['description'],
            rsp['album']['album_id'], index=0)
        widget.setChecked(True)
