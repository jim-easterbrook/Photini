##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2022-24  Jim Easterbrook  jim@jim-easterbrook.me.uk
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

from datetime import datetime
import html
import hashlib
import io
import logging
import os
import time

import requests
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

from photini.pyqt import *
from photini.types import MD_ImageRegion
from photini.uploader import PhotiniUploader, UploaderSession, UploaderUser
from photini.widgets import (
    DropDownSelector, Label, MultiLineEdit, SingleLineEdit)

logger = logging.getLogger(__name__)
translate = QtCore.QCoreApplication.translate

# Ipernity API: http://www.ipernity.com/help/api
# requests: https://docs.python-requests.org/

class IpernitySession(UploaderSession):
    api_url = 'https://api.ipernity.com/api/'
    auth_url = 'https://www.ipernity.com/apps/authorize'

    def sign_request(self, method, params):
        params = dict(params)
        params['api_key'] = self.client_data['api_key']
        if 'auth_token' in self.user_data:
            params['auth_token'] = self.user_data['auth_token']
        string = ''
        for key in sorted(params):
            string += key + params[key]
        string += method + self.client_data['api_secret']
        params['api_sig'] = hashlib.md5(string.encode('utf-8')).hexdigest()
        return params

    def api_call(self, method, post=False, **params):
        self.open_connection()
        url = self.api_url + method
        params = self.sign_request(method, params)
        if post:
            rsp = self.api.post(url, timeout=20, data=params)
        else:
            rsp = self.api.get(url, timeout=20, params=params)
        rsp = self.check_response(rsp)
        if rsp is None:
            self.close_connection()
        elif rsp['api']['status'] != 'ok':
            logger.error('in method %s: API error %s: %s',
                         method, rsp['api']['code'], rsp['api']['message'])
            return None
        return rsp

    def get_auth_url(self, frob):
        params = self.sign_request('', {'frob': frob, 'perm_doc': 'write'})
        request = requests.Request('GET', self.auth_url, params=params)
        return request.prepare().url

    def find_photos(self, min_taken_date, max_taken_date):
        # search Ipernity
        params = {
            'user_id': self.user_data['user_id'],
            'media': 'photo,video',
            'created_min': min_taken_date.strftime('%Y-%m-%d %H:%M:%S'),
            'created_max': max_taken_date.strftime('%Y-%m-%d %H:%M:%S'),
            'extra': 'dates',
            'thumbsize': '100',
            }
        while True:
            rsp = self.api_call('doc.search', **params)
            if not (rsp and 'doc' in rsp['docs'] and rsp['docs']['doc']):
                return
            for photo in rsp['docs']['doc']:
                date_taken = datetime.strptime(
                    photo['dates']['created'], '%Y-%m-%d %H:%M:%S')
                yield photo['doc_id'], date_taken, photo['thumb']['url']
            page = int(rsp['docs']['page'])
            if page == int(rsp['docs']['pages']):
                return
            params['page'] = str(page + 1)

    def upload_image(self, params, data, fileobj, image_type):
        data = dict(data)
        # sign the request before including the file to upload
        data = self.sign_request(params['function'], data)
        # create multi-part data encoder
        data['file'] = 'dummy_name', fileobj, image_type
        data = MultipartEncoderMonitor(
            MultipartEncoder(fields=data), self.progress)
        headers = {'Content-Type': data.content_type}
        # post data
        url = self.api_url + params['function']
        self.upload_progress.emit({'busy': False})
        rsp = self.check_response(
            self.api.post(url, data=data, headers=headers, timeout=20))
        self.upload_progress.emit({'busy': True})
        if not rsp:
            return 'Ipernity upload failed', None
        # parse response
        if rsp['api']['status'] != 'ok':
            return params['function'] + ' ' + str(rsp['api']), None
        return '', rsp['ticket']

    metadata_set_func = {
        'visibility' : 'doc.setPerms',
        'permissions': 'doc.setPerms',
        'licence'    : 'doc.setLicense',
        'metadata'   : 'doc.set',
        'keywords'   : 'doc.tags.edit',
        'location'   : 'doc.setGeo',
        }

    def set_metadata(self, params, doc_id):
        if 'visibility' in params and 'permissions' in params:
            params['permissions'].update(params['visibility'])
            del params['visibility']
        for key in list(params):
            if params[key] and key in self.metadata_set_func:
                rsp = self.api_call(self.metadata_set_func[key], post=True,
                                    doc_id=doc_id, **params[key])
                if rsp is None:
                    return 'Failed to set ' + key
                del params[key]
        return ''

    def set_albums(self, params, doc_id):
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
                if rsp is None:
                    return 'Failed to add to album'
        # remove from any other albums
        for album_id in current_albums:
            rsp = self.api_call('album.docs.remove', post=True,
                                album_id=album_id, doc_id=doc_id)
            if rsp is None:
                return 'Failed to remove from album'
        return ''

    def get_notes(self, doc_id, photo=[]):
        if not photo:
            rsp = self.api_call('doc.get', doc_id=doc_id, extra='notes')
            if rsp:
                photo = rsp['doc']
        if 'notes' in photo:
            for note in photo['notes']['note']:
                note['is_person'] = 'member_id' in note
                if note['is_person']:
                    note['content'] = note['membername']
                note['authorrealname'] = note['username']
                yield note

    def set_notes(self, params, doc_id):
        if params['function'] != 'upload.file':
            # delete non-existent notes
            for note in self.get_notes(doc_id):
                local_note = dict((k, note[k]) for k in (
                    'x', 'y', 'w', 'h', 'content', 'is_person'))
                if local_note in params['notes']:
                    params['notes'].remove(local_note)
                    continue
                rsp = self.api_call('doc.notes.delete',
                                    post=True, note_id=note['note_id'])
                if rsp is None:
                    return 'Failed to delete note'
        # add new notes
        if 'notes' in params:
            for note in params['notes']:
                if (note['is_person']
                        and note['content'] == self.user_data['realname']):
                    note['member_id'] = self.user_data['user_id']
                del note['is_person']
                rsp = self.api_call(
                    'doc.notes.add', post=True, doc_id=doc_id, **note)
                if rsp is None:
                    return 'Failed to add note'
        return ''

    def upload_files(self, upload_list):
        upload_count = 0
        uploads = list(upload_list)
        tickets = {}
        metadata = []
        ticket_poll = 0.0
        while uploads or tickets or metadata:
            if uploads:
                # upload an image
                image, convert, params = uploads.pop(0)
                upload_count += 1
                self.upload_progress.emit({
                    'label': '{} ({}/{})'.format(
                        os.path.basename(image.path),
                        upload_count, len(upload_list)),
                    'busy': True})
                if params['function']:
                    # upload or replace photo
                    data = {'async': '1'}
                    if params['function'] == 'upload.file':
                        # set some metadata with upload function
                        for key in ('visibility', 'permissions', 'licence',
                                    'metadata', 'dates', 'location'):
                            if key in params and params[key]:
                                data.update(params[key])
                                del params[key]
                    else:
                        data['doc_id'] = params['doc_id']
                    with self.open_file(
                            image, convert) as (image_type, fileobj):
                        error, ticket = self.upload_image(
                            params, data, fileobj, image_type)
                    if error:
                        self.upload_progress.emit({'error': (image, error)})
                        continue
                    # add ticket and details to ticket queue
                    tickets[ticket] = image, params
                else:
                    # add details to metadata queue
                    metadata.append((image, params))
            if tickets:
                # check images currently being processed
                pause = ticket_poll - time.time()
                if pause > 0:
                    time.sleep(pause)
                ticket_poll = time.time() + 2.0
                rsp = self.api_call('upload.checkTickets',
                                    tickets=','.join(tickets.keys()))
                if not rsp:
                    self.upload_progress.emit({
                        'error': (image, 'Wait for processing failed')})
                for ticket in rsp['tickets']['ticket']:
                    if not ('done' in ticket and ticket['done'] == '1'):
                        continue
                    image, params = tickets[ticket['id']]
                    params['doc_id'] = ticket['doc_id']
                    del tickets[ticket['id']]
                    # add details to metadata queue
                    metadata.append((image, params))
                    # store photo id in image keywords, in main thread
                    self.upload_progress.emit({
                        'keyword': (image, 'ipernity:id=' + params['doc_id'])})
            while metadata:
                # set remaining metadata after uploading images
                image, params = metadata.pop(0)
                error = self.set_metadata(params, params['doc_id'])
                if error:
                    self.upload_progress.emit({'error': (image, error)})
                    continue
                # add notes
                error = self.set_notes(params, params['doc_id'])
                if error:
                    self.upload_progress.emit({'error': (image, error)})
                    continue
                # add to or remove from albums
                if 'albums' in params:
                    error = self.set_albums(params, params['doc_id'])
                    if error:
                        self.upload_progress.emit({'error': (image, error)})


class PermissionWidget(DropDownSelector):
    def __init__(self, *args, default='5'):
        super(PermissionWidget, self).__init__(
            *args, values=(
                (translate('IpernityTab', 'Only you'), '0'),
                (translate('IpernityTab', 'Family & friends'), '3'),
                (translate('IpernityTab', 'Contacts'), '4'),
                (translate('IpernityTab', 'Everyone'), '5')),
            default=default, with_multiple=False)


class LicenceWidget(DropDownSelector):
    def __init__(self, *args, default='0'):
        super(LicenceWidget, self).__init__(
            *args, values=(
                (translate('IpernityTab',
                           'Copyright (all rights reserved)'), '0'),
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
            default=default, with_multiple=False)


class IpernityUser(UploaderUser):
    logger = logger
    config_section = 'ipernity'
    max_size = {'image': {'bytes': 2 ** 30},
                'video': {'bytes': 2 ** 30}}

    def on_connect(self, widgets):
        with self.session(parent=self) as session:
            # check auth
            rsp = session.api_call('auth.checkToken')
            if not rsp:
                yield 'connected', False
            self.user_data['user_id'] = rsp['auth']['user']['user_id']
            self.user_data['realname'] = rsp['auth']['user']['realname']
            self.user_data['lang'] = rsp['auth']['user']['lg']
            if rsp['auth']['user']['is_pro'] == '0':
                # guest user can upload 2.5 MB photos and no videos
                self.max_size = {'image': {'bytes': (2 ** 20) * 5 // 2},
                                 'video': {'bytes': 0}}
            yield 'connected', rsp['auth']['permissions']['doc'] == 'write'
            # get user icon
            rsp = session.api_call(
                'user.get', user_id=self.user_data['user_id'])
            if not rsp:
                yield 'connected', False
            rsp = session.check_response(
                session.api.get(rsp['user']['icon']), decode=False)
            picture = rsp and rsp.content
            yield 'user', (self.user_data['realname'], picture)
            # get albums
            params = {'empty': '1', 'per_page': '10'}
            page = 1
            while True:
                params['page'] = str(page)
                # get list of album ids
                rsp = session.api_call('album.getList', **params)
                if not rsp:
                    yield 'connected', False
                albums = rsp['albums']
                # get details of each album
                for album in albums['album']:
                    rsp = session.api_call(
                        'album.get', album_id=album['album_id'])
                    if not rsp:
                        yield 'connected', False
                    yield 'album', {
                        'title': rsp['album']['title'],
                        'description': rsp['album']['description'],
                        'id': rsp['album']['album_id'],
                        'writeable': True,
                        }
                if int(albums['page']) >= int(albums['pages']):
                    break
                page += 1

    def load_user_data(self):
        stored_token = self.get_password()
        if not stored_token:
            return False
        self.user_data['auth_token'] = stored_token
        return True

    @staticmethod
    def service_name():
        return translate('IpernityTab', 'Ipernity')

    def new_session(self, **kw):
        return IpernitySession(
            user_data=self.user_data, client_data=self.client_data, **kw)

    def get_frob(self):
        with self.session(parent=self) as session:
            rsp = session.api_call('auth.getFrob')
        if not rsp:
            return ''
        return rsp['auth']['frob']

    def auth_exchange(self, frob):
        with self.session(parent=self) as session:
            response = yield session.get_auth_url(frob)
            rsp = session.api_call('auth.getToken', frob=frob)
        if not rsp:
            return
        self.user_data['auth_token'] = rsp['auth']['token']
        self.set_password(self.user_data['auth_token'])
        self.connection_changed.emit(True)


class TabWidget(PhotiniUploader):
    logger = logger

    def __init__(self, *arg, **kw):
        self.user_widget = IpernityUser()
        super(TabWidget, self).__init__(*arg, **kw)

    @staticmethod
    def tab_name():
        return translate('IpernityTab', 'Ipernity upload',
                         'Full name of tab shown as a tooltip')

    @staticmethod
    def tab_short_name():
        return translate('IpernityTab', '&Ipernity',
                         'Shortest possible name used as tab label')

    def config_columns(self):
        self.replace_prefs = {'metadata': True}
        self.upload_prefs = {}
        ## first column
        column = QtWidgets.QGridLayout()
        column.setContentsMargins(0, 0, 0, 0)
        # "who can" group spans two columns
        group = QtWidgets.QGroupBox()
        group.setMinimumWidth(width_for_text(group, 'x' * 46))
        group.setLayout(QtWidgets.QGridLayout())
        group.layout().addWidget(QtWidgets.QLabel(
            translate('IpernityTab', 'Who can:')), 0, 0)
        # visibility
        self.widget['visibility'] = DropDownSelector(
            'visibility', values=(
                (translate('IpernityTab', 'Everyone (public)'), '4'),
                (translate('IpernityTab', 'Only you (private)'), '0'),
                (translate('IpernityTab', 'Friends'), '2'),
                (translate('IpernityTab', 'Family'), '1'),
                (translate('IpernityTab', 'Family & friends'), '3')),
            default='4', with_multiple=False)
        self.widget['visibility'].new_value.connect(self.new_value)
        group.layout().addWidget(QtWidgets.QLabel(
            translate('IpernityTab', 'see the photo')), 1, 0)
        group.layout().addWidget(self.widget['visibility'], 2, 0)
        # comment permission
        self.widget['perm_comment'] = PermissionWidget('perm_comment')
        self.widget['perm_comment'].new_value.connect(self.new_value)
        group.layout().addWidget(QtWidgets.QLabel(
            translate('IpernityTab', 'post a comment')), 1, 1)
        group.layout().addWidget(self.widget['perm_comment'], 2, 1)
        # keywords & notes permission
        self.widget['perm_tag'] = PermissionWidget('perm_tag', default='4')
        self.widget['perm_tag'].new_value.connect(self.new_value)
        group.layout().addWidget(QtWidgets.QLabel(
            translate('IpernityTab', 'add keywords, notes')), 3, 0)
        group.layout().addWidget(self.widget['perm_tag'], 4, 0)
        # people permission
        self.widget['perm_tagme'] = PermissionWidget('perm_tagme', default='4')
        self.widget['perm_tagme'].new_value.connect(self.new_value)
        group.layout().addWidget(QtWidgets.QLabel(
            translate('IpernityTab', 'identify people')), 3, 1)
        group.layout().addWidget(self.widget['perm_tagme'], 4, 1)
        group.layout().setRowStretch(5, 1)
        column.addWidget(group, 0, 0, 1, 2)
        # left hand column group
        group = QtWidgets.QGroupBox()
        group.setMinimumWidth(width_for_text(group, 'x' * 23))
        group.setLayout(FormLayout(wrapped=True))
        # licence
        self.widget['license'] = LicenceWidget('license')
        self.widget['license'].new_value.connect(self.new_value)
        group.layout().addRow(
            translate('IpernityTab', 'Licence'), self.widget['license'])
        column.addWidget(group, 1, 0, 2, 1)
        # synchronise metadata
        self.buttons['sync'] = QtWidgets.QPushButton(
            translate('IpernityTab', 'Synchronise'))
        self.buttons['sync'].clicked.connect(self.sync_metadata)
        column.addWidget(self.buttons['sync'], 1, 1)
        # create new album
        new_album_button = QtWidgets.QPushButton(
            translate('IpernityTab', 'New album'))
        new_album_button.clicked.connect(self.new_album)
        column.addWidget(new_album_button, 2, 1)
        column.setRowStretch(0, 1)
        yield column, 0
        ## last column is list of albums
        yield self.album_list(), 1
        # load user's preferences
        if not self.app.config_store.has_section('ipernity'):
            return
        for key in self.app.config_store.config.options('ipernity'):
            if key in self.widget:
                self.widget[key].set_value(
                    self.app.config_store.get('ipernity', key))

    @QtSlot(dict)
    @catch_all
    def new_value(self, value):
        (key, value), = value.items()
        self.app.config_store.set('ipernity', key, value)

    def accepted_image_type(self, file_type):
        # ipernity accepts most RAW formats!
        return True

    def get_params(self, image, upload_prefs, replace_prefs, doc_id):
        params = {'doc_id': doc_id}
        # set upload function
        if upload_prefs['new_photo']:
            params['function'] = 'upload.file'
        else:
            params['function'] = None
        # add metadata
        if upload_prefs['new_photo'] or replace_prefs['metadata']:
            # date_taken
            date_taken = image.metadata.date_taken
            if date_taken:
                params['dates'] = {
                    'created_at':
                    date_taken['datetime'].strftime('%Y-%m-%d %H:%M:%S')
                    }
            # location
            gps = image.metadata.gps_info
            if gps and gps['exif:GPSLatitude']:
                params['location'] = {
                    'lat': '{:.6f}'.format(float(gps['exif:GPSLatitude'])),
                    'lng': '{:.6f}'.format(float(gps['exif:GPSLongitude'])),
                    }
            else:
                # clear any existing location
                params['location'] = {'lat': '-999', 'lng': '-999'}
        # visibility
        if upload_prefs['new_photo'] or replace_prefs['visibility']:
            params['visibility'] = {
                '0': {'is_friend': '0', 'is_family': '0', 'is_public': '0'},
                '1': {'is_friend': '0', 'is_family': '1', 'is_public': '0'},
                '2': {'is_friend': '1', 'is_family': '0', 'is_public': '0'},
                '3': {'is_friend': '1', 'is_family': '1', 'is_public': '0'},
                '4': {'is_friend': '0', 'is_family': '0', 'is_public': '1'},
                }[self.widget['visibility'].get_value()]
        # permissions
        if upload_prefs['new_photo'] or replace_prefs['permissions']:
            params['permissions'] = {
                'perm_comment': self.widget['perm_comment'].get_value(),
                'perm_tag'    : self.widget['perm_tag'].get_value(),
                'perm_tagme'  : self.widget['perm_tagme'].get_value(),
                }
        # licence
        if upload_prefs['new_photo'] or replace_prefs['licence']:
            params['licence'] = {'license': self.widget['license'].get_value()}
        # albums
        if upload_prefs['new_photo'] or replace_prefs['albums']:
            params['albums'] = self.widget['albums'].get_checked_ids()
        # notes
        if upload_prefs['new_photo'] or replace_prefs['notes']:
            params['notes'] = list(
                image.metadata.image_region.to_notes(image, 560))
        return params

    def replace_dialog(self, image):
        return super(TabWidget, self).replace_dialog(image, (
            ('metadata', translate('IpernityTab', 'Replace metadata')),
            ('visibility', translate('IpernityTab', 'Change who can see it')),
            ('permissions',
             translate('IpernityTab', 'Change who can comment or tag')),
            ('licence', translate('IpernityTab', 'Change the licence')),
            ('albums', translate('IpernityTab', 'Change album membership')),
            ('notes', translate('IpernityTab', 'Replace image region notes'))
            ), replace=False)

    def merge_metadata(self, session, doc_id, image):
        rsp = session.api_call('doc.get', doc_id=doc_id, extra='tags,geo,notes')
        if not rsp:
            return
        photo = rsp['doc']
        data = {
            'title': photo['title'],
            'description': photo['description'],
            'keywords': [x['tag'] for x in photo['tags']['tag']
                         if x['type'] == 'keyword'],
            'date_taken': {
                'datetime': datetime.strptime(photo['dates']['created'],
                                              '%Y-%m-%d %H:%M:%S'),
                'precision': 6, 'tz_offset': None}
            }
        if 'geo' in photo:
            data['gps_info'] = {'exif:GPSLatitude': photo['geo']['lat'],
                                'exif:GPSLongitude': photo['geo']['lng'],
                                'method': 'MANUAL'}
        # get annotated image regions
        notes = session.get_notes(doc_id, photo=photo)
        if notes:
            data['image_region'] = image.metadata.image_region.from_notes(
                notes, image, 560)
        self.merge_metadata_items(image, data)

    @QtSlot()
    @catch_all
    def new_album(self):
        dialog = self.new_album_dialog()
        title = SingleLineEdit('title', spell_check=True)
        dialog.layout().addRow(translate('IpernityTab', 'Title'), title)
        description = MultiLineEdit('description', spell_check=True)
        dialog.layout().addRow(
            translate('IpernityTab', 'Description'), description)
        perm_comment = PermissionWidget('comment')
        dialog.layout().addRow(Label(
            translate('IpernityTab', 'Who can comment on album'),
            lines=2, layout=dialog.layout()), perm_comment)
        if not self.exec_album_dialog(dialog):
            return
        album = {
            'title': title.toPlainText(),
            'description': description.toPlainText(),
            'perm_comment': perm_comment.get_value(),
            }
        if not album['title']:
            return
        with self.user_widget.session(parent=self) as session:
            rsp = session.api_call('album.create', post=True, **album)
        if not rsp:
            return
        album['id'] = rsp['album']['album_id']
        album['writeable'] = True
        widget = self.widget['albums'].add_album(album, index=0)
        widget.setChecked(True)
